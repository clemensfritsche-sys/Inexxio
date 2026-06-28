"""Geschäftslogik für den Prozessschritt «Verschrotten».

Verschrotten ist die definierte **Auflösung** einer Abweichung (oder eines regulären
Bestands-Auftrags): ein defektes/nicht mehr benötigtes Teil verlässt den Bestand. Die
gewählten Instanzen werden auf ``disposition='scrapped'`` gesetzt; ein ``Disposal``-
Datensatz markiert den Abschluss des Schritts (analog zur Bewegung – keine eigene Nummer).

So gibt es keine „herumliegenden, undefinierten Teile": ein physisch vorhandenes Teil
bekommt einen ehrlichen Endzustand (verschrottet) statt einfach zu verschwinden.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Disposal, Order
from . import process
from .admin import log_audit
from .events import emit
from .reservation import release
from .subject import order_instances


def record_scrap(db: Session, order: Order, data, actor_id: int) -> Disposal:
    """Die gewählten Instanzen des Auftrags verschrotten + den Schritt abschliessen."""
    step = process.resolve_exec_step(db, order, "scrap", getattr(data, "step_id", None))

    instances = order_instances(db, order)
    if not instances:
        raise HTTPException(409, detail="Keine Instanzen zum Verschrotten vorhanden")

    by_obj = {i.object_id: i for i in instances}
    chosen_ids = list(dict.fromkeys(data.instance_ids or []))   # Reihenfolge, ohne Duplikate
    if not chosen_ids:
        raise HTTPException(400, detail="Bitte mindestens eine Instanz zum Verschrotten wählen")

    scrapped = 0
    for oid in chosen_ids:
        inst = by_obj.get(oid)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {oid} gehört nicht zu diesem Auftrag")
        if inst.disposition == "scrapped":
            continue                                # idempotent: schon verschrottet
        old = inst.disposition
        inst.disposition = "scrapped"
        release(inst, order.id)                     # etwaige Reservierung dieses Auftrags lösen
        log_audit(db, "instances", "disposition", "scrapped", actor_id,
                  object_id=inst.object_id, old_value=old)
        emit(db, "inventory.decreased", object_type="instance", object_id=inst.object_id,
             payload={"quantity": inst.quantity or 0, "delta": -(inst.quantity or 0),
                      "polarity": event_types.DECREASE, "reason": "scrapped",
                      "order": order.object_id})
        scrapped += 1

    disp = process.fact_for_step(db, order, step)
    if not disp:
        disp = Disposal(order_id=order.id, step_id=step.id)
        db.add(disp)
    disp.note = (data.note or "").strip() or None
    disp.scrapped_by_id = actor_id
    db.flush()

    log_audit(db, "disposals", None, f"{scrapped} Instanz(en) verschrottet", actor_id,
              object_id=order.object_id)
    emit(db, "scrap.recorded", object_type="order", object_id=order.object_id,
         payload={"count": scrapped}, actor_id=actor_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(disp)
    return disp
