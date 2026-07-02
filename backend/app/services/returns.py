"""Retouren (Rücknahmen) + die «Rücknahme»-Fachlogik.

Eine **Retoure** ist ein Unter-Auftrag (``orders.reason='return'``) eines abgeschlossenen
Verkaufs-Auftrags, dessen Subjekt **verkaufte** Instanzen des Eltern sind. Sie pausiert den
Eltern NICHT (der Verkauf ist durch) und komponiert bestehende Module:

    return (Rücknahme)  →  optional inspection/scrap  →  sale (Kredit-Modus = Gutschrift)

``create_return`` legt den Unter-Auftrag an (Spiegel von ``deviation.create_deviation``, nur
auf verkaufte Instanzen). ``record_return`` führt den Rücknahme-Schritt aus – das **Spiegel-
bild von** ``scrap.record_scrap``: die zurückkommenden Instanzen erhalten ihre Menge zurück,
``disposition`` wechselt ``sold`` → ``in_stock`` (bzw. Qualität ``pending`` zur Nachprüfung),
Standort gesetzt, **Bestands-Zugang** als Event.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Instance, Order, ReturnReceipt
from ..models.base import utcnow
from . import process
from .admin import log_audit
from .events import emit
from .locations import ensure_receiving_location, validate_location
from .objects import next_object_id
from .subject import order_instances, record_link


def _sold_subjects(db: Session, parent: Order, instance_object_ids: list[int]) -> list[Instance]:
    """Die zu retournierenden Instanzen: gewählte, **verkaufte** Instanzen des Eltern-Auftrags."""
    if not instance_object_ids:
        raise HTTPException(400, detail="Bitte mindestens eine verkaufte Instanz für die Retoure wählen")
    by_obj = {i.object_id: i for i in order_instances(db, parent)}
    rows: list[Instance] = []
    for oid in dict.fromkeys(instance_object_ids):
        inst = by_obj.get(oid)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {oid} gehört nicht zu diesem Verkauf")
        if inst.disposition != "sold":
            raise HTTPException(409, detail=f"Instanz {oid} ist nicht verkauft – nur verkaufte Teile sind retournierbar")
        rows.append(inst)
    return rows


def create_return(db: Session, parent: Order, instance_object_ids: list[int], actor_id: int) -> Order:
    """Eine **Retoure** (Unter-Auftrag) zu einem Verkaufs-Auftrag anlegen, die auf die gewählten
    verkauften Instanzen wirkt. Entwurf; der Nutzer definiert die Auflösung (Rücknahme + Gutschrift,
    optional Prüfung/Verschrottung) und gibt frei. Committet NICHT (der Aufrufer schliesst ab)."""
    if not process.has_step(db, parent, "sale"):
        raise HTTPException(400, detail="Retoure nur zu einem Verkaufs-Auftrag möglich")
    insts = _sold_subjects(db, parent, instance_object_ids)
    ret = Order(
        object_id=next_object_id(db, "order"), status="draft",
        article_id=parent.article_id, quantity=len(insts),
        parent_order_id=parent.object_id, reason="return",
        title=f"Retoure zu {parent.object_id}",
    )
    db.add(ret)
    db.flush()
    for inst in insts:
        inst.subject_of_order_id = ret.id
        record_link(db, inst.object_id, ret.id)
    log_audit(db, "orders", None, f"Retoure zu {parent.object_id} angelegt", actor_id, object_id=ret.object_id)
    emit(db, "order.return_opened", object_type="order", object_id=ret.object_id,
         payload={"parent": parent.object_id, "instances": [i.object_id for i in insts]}, actor_id=actor_id)
    return ret


def record_return(db: Session, order: Order, data, actor_id: int) -> ReturnReceipt:
    """Schritt «Rücknahme» ausführen – Spiegel von ``scrap.record_scrap``: die gewählten
    (verkauften) Instanzen kommen zurück ins Lager. Menge wiederhergestellt, ``disposition``
    ``sold`` → ``in_stock``; ``quality`` = ``passed`` (sofort wieder verkäuflich) bzw.
    ``pending`` (``to_inspection`` – erst prüfen). Standort = gewählt / Wareneingang."""
    step = process.resolve_exec_step(db, order, "return", getattr(data, "step_id", None))

    instances = order_instances(db, order)   # inkl. verkaufter (terminaler) Subjekt-Instanzen
    if not instances:
        raise HTTPException(409, detail="Keine Instanzen für die Rücknahme vorhanden")
    by_obj = {i.object_id: i for i in instances}

    # Auswahl vereinheitlichen: {instance_object_id: menge|None} (None = 1 Stück/ganze Rücknahme).
    chosen: dict[int, int | None] = {}
    for oid in (getattr(data, "instance_ids", None) or []):
        chosen.setdefault(oid, None)
    for it in (getattr(data, "items", None) or []):
        chosen[it.instance_id] = it.quantity
    if not chosen:
        raise HTTPException(400, detail="Bitte mindestens eine Instanz zurücknehmen")

    # Zielstandort: gewählt oder – Vorgabe – automatischer Wareneingang («nie ohne Standort»).
    loc_type = getattr(data, "location_type", None)
    loc_id = getattr(data, "location_id", None)
    if loc_type and loc_id:
        validate_location(db, loc_type, loc_id)
    else:
        loc_type, loc_id = "lagerplatz", ensure_receiving_location(db)
    to_inspection = bool(getattr(data, "to_inspection", False))
    now = utcnow()

    taken = 0
    for oid, qty in chosen.items():
        inst = by_obj.get(oid)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {oid} gehört nicht zu dieser Retoure")
        if inst.disposition == "in_stock":
            continue                                  # idempotent: schon zurückgenommen
        back = qty if (qty and qty > 0) else 1        # zurückkommende Menge (Default 1 Stück)
        inst.quantity = (inst.quantity or 0) + back   # Menge wiederherstellen (Spiegel consume)
        inst.disposition = "in_stock"
        inst.quality = "pending" if to_inspection else "passed"
        inst.location_type = loc_type
        inst.location_id = loc_id
        inst.released_at = now                         # FIFO-Basis: ab jetzt wieder am Lager
        log_audit(db, "instances", "disposition", inst.disposition, actor_id,
                  object_id=inst.object_id, old_value="sold")
        emit(db, "inventory.increased", object_type="instance", object_id=inst.object_id,
             payload={"quantity": back, "delta": back, "polarity": event_types.INCREASE,
                      "reason": "return", "order": order.object_id})
        taken += 1

    rec = process.fact_for_step(db, order, step)
    if not rec:
        rec = ReturnReceipt(order_id=order.id, step_id=step.id)
        db.add(rec)
    rec.note = (getattr(data, "note", None) or "").strip() or None
    rec.received_by_id = actor_id
    rec.location_type = loc_type
    rec.location_id = loc_id
    rec.to_inspection = to_inspection
    db.flush()

    log_audit(db, "return_receipts", None, f"{taken} Instanz(en) zurückgenommen", actor_id, object_id=order.object_id)
    emit(db, "return.recorded", object_type="order", object_id=order.object_id,
         payload={"count": taken}, actor_id=actor_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(rec)
    return rec
