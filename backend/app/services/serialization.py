"""Geschäftslogik für den Prozessschritt «Serialisierung».

Erzeugt aus der Artikel-Einstellung ``serialization`` die Bestands-Instanzen:
    unit  → N Einzel-Instanzen (je quantity=1, eigene Nummer)
    batch → 1 Charge-Instanz mit quantity = Bestellmenge
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Instance, Order
from . import process
from .admin import log_audit
from .locations import ensure_receiving_location
from .objects import next_object_id


def serialize_for_order(db: Session, order: Order, actor_id: int) -> list[Instance]:
    existing = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .all()
    )
    if existing:
        return existing
    if not process.is_step_active(db, order, "serialization"):
        raise HTTPException(409, detail="Serialisierung ist (noch) nicht an der Reihe")
    art = db.query(Article).filter(Article.id == order.article_id).first()
    if not art or not order.quantity:
        raise HTTPException(400, detail="Artikel oder Menge fehlt")

    # Ohne nachgelagerte Eingangskontrolle gilt die Ware direkt als freigegeben
    qc = "pending" if process.has_step(db, order, "inspection") else "passed"

    # Neue Instanzen starten IMMER mit einem Standort – dem Wareneingang.
    recv_id = ensure_receiving_location(db)

    created: list[Instance] = []
    if art.serialization == "batch":
        created.append(Instance(
            object_id=next_object_id(db), article_id=art.id, order_id=order.id,
            kind="batch", quantity=order.quantity, qc_status=qc,
            location_type="lagerplatz", location_id=recv_id,
        ))
        db.add(created[-1]); db.flush()
    else:  # unit → je Stück eine Instanz
        for _ in range(order.quantity):
            inst = Instance(
                object_id=next_object_id(db), article_id=art.id, order_id=order.id,
                kind="unit", quantity=1, qc_status=qc,
                location_type="lagerplatz", location_id=recv_id,
            )
            db.add(inst); db.flush()
            created.append(inst)

    log_audit(db, "instances", None, f"{len(created)} Instanz(en) serialisiert",
              actor_id, object_id=order.object_id)
    process.recompute_completion(db, order)
    db.commit()
    for inst in created:
        db.refresh(inst)
    return created
