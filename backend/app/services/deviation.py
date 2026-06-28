"""Abweichungen – vereinheitlicht Abbruch-Folgeauftrag, Fehler/Reklamation, Nacharbeit.

Eine **Abweichung** ist ein **Unter-Auftrag** (``orders.parent_order_id``), der aus einem
laufenden Eltern-Auftrag heraus entsteht und auf dessen Instanzen wirkt. Der Eltern-Auftrag
**pausiert**, solange die Abweichung offen ist (``process._is_paused_by_deviation``).

Sonderfall **Abbruch**: «Abbrechen» bricht NICHT sofort ab, sondern erzwingt einen
**Folgeauftrag** (eine Abweichung), der die im Prozess befindlichen Instanzen übernimmt.
Das Original wird erst **inaktiv**, wenn der Folgeauftrag **freigegeben** ist – so liegen
nie undefinierte Teile herum.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Order
from .admin import log_audit
from .events import emit
from .objects import next_object_id
from .subject import order_instances


def open_deviations(db: Session, parent: Order) -> list[Order]:
    """Aktive (Entwurf/freigegeben) Abweichungs-Unteraufträge eines Auftrags."""
    if not parent.object_id:
        return []
    return (
        db.query(Order)
        .filter(Order.parent_order_id == parent.object_id, Order.is_active == True,
                Order.status.in_(("draft", "released")))
        .order_by(Order.object_id)
        .all()
    )


def create_abort_followup(db: Session, order: Order, actor_id: int) -> Order:
    """Beim Abbruch einen **Folgeauftrag** (Abweichung) erzeugen, der die im Prozess
    befindlichen Instanzen übernimmt. Committet NICHT (der Aufrufer schliesst ab)."""
    if order.status != "released":
        raise HTTPException(400, detail="Nur ein freigegebener Auftrag braucht einen Folgeauftrag")
    if order.abort_into_id:
        raise HTTPException(409, detail="Für diesen Auftrag ist bereits ein Folgeauftrag offen")
    insts = order_instances(db, order)
    follow = Order(
        object_id=next_object_id(db, "order"), status="draft",
        article_id=order.article_id, quantity=len(insts) or order.quantity,
        parent_order_id=order.object_id, title=f"Abbruch von {order.object_id}",
    )
    db.add(follow)
    db.flush()
    for inst in insts:                       # Instanzen an den Folgeauftrag binden
        inst.subject_of_order_id = follow.id
    order.abort_into_id = follow.object_id   # Original = «Abbruch ausstehend»
    log_audit(db, "orders", "abort_into_id", str(follow.object_id), actor_id, object_id=order.object_id)
    emit(db, "order.abort_requested", object_type="order", object_id=order.object_id,
         payload={"followup": follow.object_id}, actor_id=actor_id)
    return follow


def apply_abort_on_release(db: Session, followup: Order, actor_id: int) -> None:
    """Wird ein Abbruch-Folgeauftrag **freigegeben**, das Original endgültig **abbrechen**:
    Reservierungen lösen, ABER die übernommenen Instanzen NICHT deaktivieren (sie gehören
    jetzt dem Folgeauftrag). Committet NICHT."""
    if not followup.parent_order_id:
        return
    parent = db.query(Order).filter(Order.object_id == followup.parent_order_id).first()
    if not parent or parent.abort_into_id != followup.object_id or parent.status == "inactive":
        return
    from .deactivation import cancel_order_effects
    old = parent.status
    parent.status = "inactive"
    cancel_order_effects(db, parent, actor_id, keep_instances=True)
    log_audit(db, "orders", "status", "inactive", actor_id, object_id=parent.object_id, old_value=old)
    emit(db, "order.aborted", object_type="order", object_id=parent.object_id,
         payload={"followup": followup.object_id}, actor_id=actor_id)
