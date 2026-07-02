"""Retoure/Erstattung – Hilfen rund um den **Original-Verkauf**.

Eine Retoure entsteht **wie jeder andere Auftrag**: bei «Instanz wählen» werden statt Lager-
Instanzen die **verkauften** Instanzen gewählt (`routers/orders._set_chosen_instances`). Das
markiert den Auftrag als Retoure (`orders.reason='return'`, festes Subjekt wie eine Abweichung –
keine FIFO-Reservierung, kein Eltern-Pause) und setzt `parent_order_id` = den **Original-Verkauf**.

Der `sale`-Schritt bedient beide Modi (Modus aus dem Subjekt abgeleitet): normaler Auftrag →
Verkauf (`kind='sale'`), Retoure → Gutschrift (`kind='credit'`, Betrag aus dem Original abgeleitet,
Stripe-Refund). Der physische Rückfluss (sold → in_stock) läuft über die **Bewegung**.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import InstanceOrderLink, Order, Sale


def original_sale_order(db: Session, instances: list) -> Order:
    """Den **Original-Verkaufs-Auftrag** der gewählten (verkauften) Instanzen ableiten: der
    Auftrag mit einem **bezahlten Verkauf** (``Sale kind='sale' status='paid'``), der diese
    Instanzen als Subjekt verarbeitet hat (``instance_order_links``). Alle gewählten Instanzen
    müssen aus **demselben** Verkauf stammen (sonst ist der Erstattungsbetrag nicht eindeutig)."""
    obj_ids = [i.object_id for i in instances]
    link_orders = {
        row.order_id
        for row in db.query(InstanceOrderLink.order_id)
        .filter(InstanceOrderLink.instance_object_id.in_(obj_ids),
                InstanceOrderLink.is_active == True)
        .all()
    }
    if not link_orders:
        raise HTTPException(409, detail="Zu diesen Instanzen ist kein Verkauf auffindbar")
    sale_orders = (
        db.query(Order)
        .join(Sale, Sale.order_id == Order.id)
        .filter(Order.id.in_(link_orders), Sale.kind == "sale",
                Sale.status == "paid", Sale.is_active == True)
        .order_by(Order.id.desc())
        .all()
    )
    if not sale_orders:
        raise HTTPException(409, detail="Zu diesen Instanzen ist kein bezahlter Verkauf auffindbar")
    if len({o.id for o in sale_orders}) > 1:
        raise HTTPException(
            400, detail="Bitte nur Instanzen desselben Verkaufs erstatten – die gewählten stammen "
                        "aus verschiedenen Verkäufen")
    return sale_orders[0]
