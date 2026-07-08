"""Geschäftslogik für den Prozessschritt «Bewegung».

Der Lagerist weist jeder Instanz des Auftrags einen Zielstandort zu (Lagerplatz,
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


def record_movement(db: Session, order: Order, data, actor_id: int) -> Movement:
    step = process.resolve_exec_step(db, order, "movement", getattr(data, "step_id", None))

    # Bewegbare Instanzen: normal nur aktive (verschrottet/verbaut sind endgültig «raus»).
    # **Verkaufte** Instanzen bleiben aber bewegbar, wenn die Bewegung sie physisch bewegt:
    # der **Pflicht-Versand zum Kunden** (mode='customer', die eben verkaufte Ware geht raus)
    # und die **Retoure** (reason='return', die verkaufte Ware kommt zurück). Sonst sind sold
    # Teile «raus».
    from .subject import is_return, order_instances
    if is_return(order) or step.mode == "customer":
        instances = [i for i in order_instances(db, order)
                     if (i.disposition or "") not in ("scrapped", "consumed")]
    else:
        instances = order_active_instances(db, order)
    if not instances:
        raise HTTPException(409, detail="Keine Instanzen zum Bewegen vorhanden")

    # **Pflicht-Versand zum Kunden** (mode='customer'): das Ziel ist NICHT frei – es geht IMMER
    # an den Kunden des Verkaufs. Die Ziel-Eingaben des Clients werden dafür überschrieben
    # (serverseitige Erzwingung; das Panel zeigt den Kunden ohnehin als festes Ziel).
    targets = data.targets or []
    if step.mode == "customer":
        from .sale import customer_for_order
        cust = customer_for_order(db, order)
        if not cust:
            raise HTTPException(
                400, detail="Der Kunde dieses Verkaufs ist noch nicht gesetzt – bitte zuerst den Verkauf bestätigen")
        targets = [type("T", (), {"instance_id": i.object_id, "location_type": "user",
                                  "location_id": cust.object_id})() for i in instances]

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
    db.flush()

    log_audit(db, "movements", None, "Bewegung erfasst", actor_id, object_id=order.object_id)
    emit(db, "movement.recorded", object_type="order", object_id=order.object_id, actor_id=actor_id)
    # Label-Wechsel dann, wann es wirklich passiert: hat die Rückgabe-Bewegung die verkaufte Ware
    # an einen Lagerplatz gebracht, ist sie sofort wieder «freigegeben» (sold → in_stock), nicht
    # erst am Auftragsende. Idempotent; Kulanz (nicht bewegt) bleibt sold.
    if is_return(order):
        process.return_subjects_to_stock(db, order)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(mv)
    return mv
