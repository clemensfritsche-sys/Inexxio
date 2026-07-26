"""Geschäftslogik für den Prozessschritt «Bewegung».

Der Lagerist weist jeder Instanz des Auftrags einen Zielstandort zu (Person,
Person oder andere Instanz). Die Standorte werden direkt auf den Instanzen
gespeichert; ein ``Movement``-Datensatz markiert den Abschluss des Schritts
(analog zur Datenerfassung). Instanzen eines Auftrags können dabei an
unterschiedliche Standorte gehen – je Instanz ein eigener Eintrag.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Movement, Order
from . import location_split, process
from .admin import log_audit
from .events import emit
from .locations import validate_location
from .quantity import to_qty
from .reservation import reserved_for
from .subject import is_fixed_subject, order_active_instances


def movable_instances(db: Session, order: Order, step) -> list:
    """Die Instanzen, die dieser Bewegungs-Schritt physisch bewegt – die EINE Auswahlregel
    für Ausführung (``record_movement``), Embed (``orders._movement_embed``) und Versand-Beleg
    (Paket-/Gefahrgut-Basis).

    * **Retoure** (reason='return'): genau die **verkauften** Instanzen (die Ware kommt
      zurück). Chargen-**Slices** (Teilmengen-Verkauf: die Instanz besteht weiter, nur eine
      Teilmenge kommt zurück) werden NICHT umgelagert – die Rest-Charge bleibt am Lager,
      die Rückgabe bucht die Teilmenge mengengenau zurück (``process.return_subjects_to_stock``).
    * **Pflicht-Versand zum Kunden** (mode='customer'): nur was wirklich zum Kunden geht –
      verkaufte (``sold``) und im Prozess befindliche eigene (``in_process``, make) Instanzen
      sowie ganz für diesen Auftrag reservierte Lager-Instanzen (Deckung). FIX: eine
      ``in_stock``-Instanz OHNE volle Reservierung ist der **unverkaufte Rest** (z. B. der
      Rest einer teilverkauften Charge – der Verkauf hat seine Teilmenge bereits abgebucht)
      und bleibt am Lager; vorher wurde die ganze Rest-Charge per ``set_single`` zum Kunden
      «bewegt» und stand danach fälschlich als freier Bestand beim Kunden.
    * sonst: nur aktive Instanzen (verschrottet/verkauft/verbaut sind «raus»)."""
    from .subject import is_return, order_instances
    if is_return(order):
        return [i for i in order_instances(db, order) if (i.disposition or "") == "sold"]
    if getattr(step, "mode", None) == "customer":
        out = []
        for i in order_instances(db, order):
            d = i.disposition or "in_process"
            if d in ("scrapped", "consumed"):
                continue
            if d == "in_stock" and reserved_for(i, order.id) < to_qty(i.quantity):
                continue   # unverkaufter (Rest-)Bestand – bleibt am Lager
            out.append(i)
        return out
    return order_active_instances(db, order)


def _assert_something_to_move(db: Session, order: Order, step, instances: list) -> None:
    """Leere Instanzliste ist nur dann ein Fehler, wenn auch mengenmässig nichts bewegt wird.

    Teilmengen-Charge: der verkaufte Anteil hat KEINE eigene Instanz (die FIFO-Teilentnahme
    senkt nur die Menge) – physisch geht er beim Kunden-Versand trotzdem raus bzw. kommt bei
    der Retoure zurück. Der Schritt wird dann als reine **Quittierung** abgeschlossen (nichts
    umzulagern), statt dauerhaft mit 409 zu blockieren; den Slice-Rückfluss bucht
    ``process.return_subjects_to_stock``."""
    from .subject import is_return
    if instances:
        return
    if is_return(order):
        moved = bool(process.sold_amounts_for_order(db, order.parent_order_id))
    else:
        moved = (step.mode == "customer"
                 and bool(process.sold_amounts_for_order(db, order.object_id)))
    if not moved:
        raise HTTPException(409, detail="Keine Instanzen zum Bewegen vorhanden")


def _resolve_targets(db: Session, order: Order, step, data, instances: list) -> list:
    """Die Ziel-Zuweisungen dieses Schritts. Beim **Versand zum Kunden** (mode='customer')
    ist das Ziel NICHT frei – es geht IMMER an den Kunden des Verkaufs, die Client-Eingaben
    werden überschrieben (serverseitige Erzwingung; das Panel zeigt den Kunden ohnehin als
    festes Ziel)."""
    if step.mode != "customer":
        return data.targets or []
    from .sale import customer_for_order
    cust = customer_for_order(db, order)
    if not cust:
        raise HTTPException(
            400, detail="Der Kunde dieses Verkaufs ist noch nicht gesetzt – bitte zuerst den Verkauf bestätigen")
    return [type("T", (), {"instance_id": i.object_id, "location_type": "user",
                           "location_id": cust.object_id})() for i in instances]


def record_movement(db: Session, order: Order, data, actor_id: int) -> Movement:
    from .subject import is_return
    step = process.resolve_exec_step(db, order, "movement", getattr(data, "step_id", None))
    instances = movable_instances(db, order, step)
    _assert_something_to_move(db, order, step, instances)
    targets = _resolve_targets(db, order, step, data, instances)

    # **Teilmengen-Bewegung ist auftragsgetrieben** (kein Ad-hoc an der Instanz): der Auftrag
    # legt fest, WIE VIEL einer Charge bewegt wird. Ein Bestands-Auftrag über z. B. 10 Stück
    # reserviert mengengenau 10 der 1000er-Charge (FIFO, ``subject._allocate_stock_for``); der
    # Bewegungsschritt verlagert dann **genau diese reservierte Teilmenge** an das Ziel – der
    # Rest der Charge bleibt, wo er war (die Objektnummer bleibt, keine neue Instanz). Ist der
    # Auftrag über die GANZE Instanz (oder eine Erzeugung/Retoure/ein Kunden-Versand → keine
    # Teil-Reservierung), wird sie als Ganzes eingelagert und eine verteilte Charge dabei wieder
    # zusammengeführt (``location_split.set_single``).
    partial_ok = not is_fixed_subject(order) and step.mode != "customer"
    by_obj = {i.object_id: i for i in instances}
    for t in targets:
        inst = by_obj.get(t.instance_id)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {t.instance_id} gehört nicht zu diesem Auftrag")
        if t.location_type == "instance" and t.location_id == inst.object_id:
            raise HTTPException(400, detail="Eine Instanz kann nicht in sich selbst liegen")
        validate_location(db, t.location_type, t.location_id)
        share = reserved_for(inst, order.id) if partial_ok else to_qty(0)
        if to_qty(0) < share < to_qty(inst.quantity):
            # Nur die vom Auftrag beanspruchte Teilmenge der Charge verlagern.
            log_audit(db, "instances", "location", f"{t.location_type}:{t.location_id}",
                      actor_id, object_id=inst.object_id,
                      old_value=f"{share} Stk aus {inst.location_type}:{inst.location_id}")
            location_split.move(inst, t.location_type, t.location_id, share)
        elif (inst.location_type, inst.location_id) != (t.location_type, t.location_id) or inst.locations:
            log_audit(db, "instances", "location", f"{t.location_type}:{t.location_id}",
                      actor_id, object_id=inst.object_id,
                      old_value=f"{inst.location_type}:{inst.location_id}")
            location_split.set_single(inst, t.location_type, t.location_id)

    mv = process.fact_for_step(db, order, step)
    if not mv:
        mv = Movement(order_id=order.id, step_id=step.id)
        db.add(mv)
    mv.note = (data.note or "").strip() or None
    mv.moved_by_id = actor_id
    # Versand zum Kunden (outbound): optionale Sendungsverfolgung.
    mv.tracking_number = (getattr(data, "tracking_number", None) or "").strip() or None
    mv.carrier = (getattr(data, "carrier", None) or "").strip() or None
    # Versand-Beleg (ADR 005) abschliessen: das Quittieren der Bewegung IST die physische
    # Übergabe (purchased → done); Tracking/Carrier aus dem gekauften Label übernehmen,
    # wenn der Lagerist nichts eigenes erfasst hat.
    from . import logistics
    ship = logistics.complete_for_movement(db, order, step)
    if ship:
        mv.tracking_number = mv.tracking_number or ship.tracking_number
        mv.carrier = mv.carrier or ship.carrier
    db.flush()

    log_audit(db, "movements", None, "Bewegung erfasst", actor_id, object_id=order.object_id)
    emit(db, "movement.recorded", object_type="order", object_id=order.object_id, actor_id=actor_id)
    # Label-Wechsel dann, wann es wirklich passiert: hat die Rückgabe-Bewegung die verkaufte Ware
    # vom Kunden weg gebracht, ist sie sofort wieder «freigegeben» (sold → in_stock), nicht
    # erst am Auftragsende. Idempotent; Kulanz (nicht bewegt) bleibt sold.
    if is_return(order):
        process.return_subjects_to_stock(db, order)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(mv)
    return mv
