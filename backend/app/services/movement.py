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
from . import process
from .admin import log_audit
from .events import emit
from .locations import validate_location
from .subject import order_instances


def record_movement(db: Session, order: Order, data, actor_id: int) -> Movement:
    step = process.resolve_exec_step(db, order, "movement", getattr(data, "step_id", None))

    instances = order_instances(db, order)
    if not instances:
        raise HTTPException(409, detail="Keine Instanzen zum Bewegen vorhanden")

    by_obj = {i.object_id: i for i in instances}
    for t in (data.targets or []):
        inst = by_obj.get(t.instance_id)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {t.instance_id} gehört nicht zu diesem Auftrag")
        if t.location_type == "instance" and t.location_id == inst.object_id:
            raise HTTPException(400, detail="Eine Instanz kann nicht in sich selbst liegen")
        validate_location(db, t.location_type, t.location_id)
        if (inst.location_type, inst.location_id) != (t.location_type, t.location_id):
            log_audit(db, "instances", "location", f"{t.location_type}:{t.location_id}",
                      actor_id, object_id=inst.object_id,
                      old_value=f"{inst.location_type}:{inst.location_id}")
            inst.location_type = t.location_type
            inst.location_id = t.location_id

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
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(mv)
    return mv
