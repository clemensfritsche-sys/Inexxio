"""Kunden-Retoure aus «Meine Bestellungen» (Online-Shop-Logik).

Der Kunde stösst eine Rückgabe zu einer **abgeschlossenen** Bestellung an (innerhalb des
Rückgabefensters). Das erzeugt – wie eine im ERP angelegte Retoure – einen **Unter-Auftrag**
(`reason='return'`, Subjekt = die verkauften Instanzen der Bestellung, `parent`=Original-Verkauf)
und legt ihm gleich den üblichen Ablauf an: **Bewegung** (Ware kommt zurück ins Lager) +
**Verkauf im Kredit-Modus** (Gutschrift/Rückerstattung). Das Personal verarbeitet ihn im ERP
(Wareneingang buchen, Gutschrift bestätigen → Stripe-Refund). Der Kunde sieht den Status.
"""

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Order, Sale
from .admin import log_audit
from .events import emit
from .objects import next_object_id
from .process_steps import sync_locked_movements
from .subject import order_instances, record_link

# Rückgabefenster (Tage ab Abschluss der Bestellung). Bewusst grosszügig (Online-Shop-üblich).
RETURN_WINDOW_DAYS = 30


def _customer_sale(db: Session, order: Order, customer_id: int) -> Sale | None:
    """Der (bezahlte) Verkaufsbeleg dieser Bestellung für genau diesen Kunden."""
    return (
        db.query(Sale)
        .filter(Sale.order_id == order.id, Sale.kind == "sale",
                Sale.customer_id == customer_id, Sale.is_active == True)
        .first()
    )


def _existing_return(db: Session, order: Order) -> Order | None:
    return (
        db.query(Order)
        .filter(Order.parent_order_id == order.object_id, Order.reason == "return",
                Order.is_active == True)
        .first()
    )


def requested_return_parents(db: Session, order_object_ids: set[int]) -> set[int]:
    """**Batch**-Variante von ``_existing_return`` für Listen («Meine Bestellungen»):
    EIN Query für alle Bestellungen statt einem je Zeile (N+1)."""
    if not order_object_ids:
        return set()
    return {
        row[0] for row in
        db.query(Order.parent_order_id)
        .filter(Order.parent_order_id.in_(order_object_ids), Order.reason == "return",
                Order.is_active == True)
        .all()
    }


def return_status(db: Session, order: Order, sale: Sale,
                  requested: bool | None = None) -> dict:
    """Retoure-Status einer Bestellung aus Kundensicht: ist sie retournierbar, bis wann,
    oder wurde schon eine Retoure angefragt? (Für «Meine Bestellungen».) ``requested``:
    vorab (batch) ermittelt – erspart Listen den Query je Zeile."""
    deadline = (order.completed_at.date() + timedelta(days=RETURN_WINDOW_DAYS)) if order.completed_at else None
    if requested is None:
        requested = _existing_return(db, order) is not None
    if requested:
        return {"returnable": False, "return_requested": True, "return_deadline": deadline}
    # Günstige Checks zuerst – der Instanz-Scan läuft nur noch für Bestellungen, die
    # überhaupt im Rückgabefenster liegen (bounded), nicht für die ganze Historie.
    ok = (
        sale.kind == "sale" and not order.reason and order.status == "completed"
        and (deadline is None or date.today() <= deadline)
        and any(i.disposition == "sold" for i in order_instances(db, order))
    )
    return {"returnable": bool(ok), "return_requested": False, "return_deadline": deadline}


def request_return(db: Session, order_object_id: int, customer_id: int, reason: str | None) -> Order:
    """Eine Kunden-Retoure zu einer abgeschlossenen Bestellung anlegen (Unter-Auftrag + Ablauf).
    Committet NICHT (der Aufrufer schliesst ab)."""
    order = db.query(Order).filter(Order.object_id == order_object_id, Order.is_active == True).first()
    if not order:
        raise HTTPException(404, detail="Bestellung nicht gefunden")
    sale = _customer_sale(db, order, customer_id)
    if not sale:
        raise HTTPException(403, detail="Diese Bestellung gehört nicht zu diesem Konto")
    st = return_status(db, order, sale)
    if st["return_requested"]:
        raise HTTPException(409, detail="Für diese Bestellung wurde bereits eine Retoure angefragt")
    if not st["returnable"]:
        raise HTTPException(400, detail="Diese Bestellung ist nicht (mehr) retournierbar")

    sold = [i for i in order_instances(db, order) if i.disposition == "sold"]
    ret = Order(
        object_id=next_object_id(db, "order"), status="draft",
        article_id=order.article_id, quantity=len(sold),
        parent_order_id=order.object_id, reason="return",
        title=(f"Retoure: {reason.strip()}" if (reason and reason.strip()) else f"Retoure zu {order.object_id}"),
    )
    db.add(ret)
    db.flush()
    for inst in sold:
        inst.subject_of_order_id = ret.id
        record_link(db, inst.object_id, ret.id)
    # Üblichen Ablauf gleich anlegen, damit das Personal nur noch ausführen muss:
    #   Bewegung (Ware zurück ins Lager) + Verkauf im Kredit-Modus (Gutschrift).
    db.add(ArticleProcessStep(order_id=ret.id, step_type="movement", position=1, is_active=True))
    db.add(ArticleProcessStep(order_id=ret.id, step_type="sale", position=2, is_active=True))
    db.flush()
    sync_locked_movements(db, order_id=ret.id)
    log_audit(db, "orders", None, f"Kunden-Retoure zu {order.object_id}", customer_id, object_id=ret.object_id)
    emit(db, "order.customer_return_requested", object_type="order", object_id=ret.object_id,
         payload={"parent": order.object_id, "reason": reason, "instances": [i.object_id for i in sold]},
         actor_id=customer_id)
    return ret
