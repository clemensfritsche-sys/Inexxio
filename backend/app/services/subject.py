"""Das **Subjekt** eines Auftrags – worauf er wirkt – je nach Prozess-Quelle.

    produce   → bei Freigabe ERZEUGTE Instanzen   (Instance.order_id == order.id)
    stock     → FIFO-gewählte, für den Auftrag reservierte Bestands-Instanzen
                (Instance.subject_of_order_id == order.id)
    instance  → die EINE referenzierte Instanz    (order.subject_instance_id)

``order_instances`` liefert einheitlich diese Liste – darauf bauen Datenerfassung,
Bewegung, Ressource und Verkauf auf (egal, wie die Instanzen entstanden sind).
``materialize_subject`` stellt das Subjekt bei der Freigabe her.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, Order
from . import processes
from .admin import log_audit
from .serialization import create_instances_for_order


def order_source(db: Session, order: Order) -> str:
    proc = processes.process_for_order(db, order)
    return proc.source if proc else "produce"


def order_instances(db: Session, order: Order) -> list[Instance]:
    """Die Instanzen, auf die der Auftrag wirkt (einheitlich über alle Quellen)."""
    src = order_source(db, order)
    if src == "stock":
        return (
            db.query(Instance)
            .filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
            .order_by(Instance.object_id)
            .all()
        )
    if src == "instance":
        if not order.subject_instance_id:
            return []
        inst = (
            db.query(Instance)
            .filter(Instance.object_id == order.subject_instance_id, Instance.is_active == True)
            .first()
        )
        return [inst] if inst else []
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


def _pick_stock_subjects(db: Session, order: Order, actor_id: int) -> None:
    """Quelle ``stock``: FIFO genau ``quantity`` aus freigegebenem Bestand wählen und
    als **Subjekt** des Auftrags reservieren (Charge bei Bedarf teilen)."""
    from .inventory import allocate
    from .objects import next_object_id
    from .resource import fifo_candidates

    if not order.article_id or not order.quantity:
        raise HTTPException(400, detail="Zur Freigabe sind Artikel und Menge erforderlich")
    if order_instances(db, order):
        return  # idempotent
    need = order.quantity
    cands = fifo_candidates(db, order.article_id, for_order_id=None)
    have = sum(c.quantity for c in cands)
    if have < need:
        raise HTTPException(409, detail=f"Nicht genügend Bestand: benötigt {need}, verfügbar {have}")
    for cand, take in zip(cands, allocate(need, [c.quantity for c in cands])):
        if take <= 0:
            continue
        if take == cand.quantity:
            cand.subject_of_order_id = order.id
            cand.reserved_for_order_id = order.id
        else:
            cand.quantity -= take  # Charge teilen: Rest bleibt frei im Lager
            db.add(Instance(
                object_id=next_object_id(db, "instance"), article_id=cand.article_id,
                order_id=cand.order_id, kind=cand.kind, quantity=take,
                quality="passed", disposition="in_stock",
                released_at=cand.released_at or cand.created_at,
                location_type=cand.location_type, location_id=cand.location_id,
                subject_of_order_id=order.id, reserved_for_order_id=order.id,
            ))
            db.flush()
    log_audit(db, "instances", None, f"{need} Bestands-Instanz(en) als Subjekt gewählt",
              actor_id, object_id=order.object_id)


def _bind_instance_subject(db: Session, order: Order) -> None:
    """Quelle ``instance``: die referenzierte Instanz prüfen; Artikel daraus ableiten."""
    if not order.subject_instance_id:
        raise HTTPException(400, detail="Bitte eine Instanz als Subjekt wählen")
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == order.subject_instance_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(400, detail="Subjekt-Instanz nicht gefunden")
    if order.article_id != inst.article_id:
        order.article_id = inst.article_id


def materialize_subject(db: Session, order: Order, actor_id: int) -> None:
    """Bei Auftragsfreigabe das Subjekt herstellen (je nach Prozess-Quelle).

    Committet NICHT – der Aufrufer (Auftragsfreigabe) schliesst die Transaktion ab."""
    src = order_source(db, order)
    if src == "instance":
        _bind_instance_subject(db, order)
    elif src == "stock":
        _pick_stock_subjects(db, order, actor_id)
    else:
        create_instances_for_order(db, order, actor_id)
