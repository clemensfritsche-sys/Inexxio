"""Positionen eines **Mehrpositionen-Auftrags** (``orders.article_id IS NULL``).

Reiner Lese-Helfer – die Anlage lebt in ``routers/orders.py: create_order`` (dort
entsteht die Zeile zusammen mit dem Auftrag und ggf. fixierten Instanzen)."""

from sqlalchemy.orm import Session

from ..models import Order, OrderLine


def lines_for(db: Session, order: Order) -> list[OrderLine]:
    """Aktive Positionen eines Mehrpositionen-Auftrags, in Reihenfolge. Leer für einen
    gewöhnlichen Einzel-Artikel-Auftrag (``order.article_id`` gesetzt)."""
    if order.article_id is not None:
        return []
    return (
        db.query(OrderLine)
        .filter(OrderLine.order_id == order.id, OrderLine.is_active == True)
        .order_by(OrderLine.position, OrderLine.id)
        .all()
    )


def is_multiline(order: Order) -> bool:
    """Mehrpositionen-Auftrag? – erkennbar allein daran, dass ``article_id`` fehlt
    (Anker für den Einzel-Artikel-Fall)."""
    return order.article_id is None
