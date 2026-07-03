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
    """Den **Original-Verkaufs-Auftrag** der gewählten (verkauften) Instanzen ableiten: je
    Instanz ihr **jüngster** Auftrag mit bezahltem Verkauf (``Sale kind='sale' status='paid'``,
    via ``instance_order_links``). Alle gewählten Instanzen müssen aus **demselben** Verkauf
    stammen (sonst ist der Erstattungsbetrag nicht eindeutig)."""
    obj_ids = [i.object_id for i in instances]
    links = (
        db.query(InstanceOrderLink.instance_object_id, InstanceOrderLink.order_id)
        .filter(InstanceOrderLink.instance_object_id.in_(obj_ids),
                InstanceOrderLink.is_active == True)
        .all()
    )
    if not links:
        raise HTTPException(409, detail="Zu diesen Instanzen ist kein Verkauf auffindbar")
    link_orders = {row.order_id for row in links}
    paid_sale_ids = {
        o.id for o in
        db.query(Order.id)
        .join(Sale, Sale.order_id == Order.id)
        .filter(Order.id.in_(link_orders), Sale.kind == "sale",
                Sale.status == "paid", Sale.is_active == True)
        .all()
    }
    if not paid_sale_ids:
        raise HTTPException(409, detail="Zu diesen Instanzen ist kein bezahlter Verkauf auffindbar")
    # FIX: Vorher genügte EIN weiterer historischer Verkauf in der Instanz-Historie für den
    # 400er – eine Instanz, die verkauft, retourniert, wieder eingelagert und ERNEUT verkauft
    # wurde, war damit nie mehr retournierbar. Massgeblich ist je Instanz der JÜNGSTE bezahlte
    # Verkauf; nur wenn DIESE auseinanderfallen, ist der Betrag nicht eindeutig.
    latest_per_instance: dict[int, int] = {}
    for row in links:
        if row.order_id in paid_sale_ids:
            cur = latest_per_instance.get(row.instance_object_id)
            if cur is None or row.order_id > cur:
                latest_per_instance[row.instance_object_id] = row.order_id
    latest_ids = set(latest_per_instance.values())
    if len(latest_ids) > 1:
        raise HTTPException(
            400, detail="Bitte nur Instanzen desselben Verkaufs erstatten – die gewählten stammen "
                        "aus verschiedenen Verkäufen")
    order_id = latest_ids.pop()
    return db.query(Order).filter(Order.id == order_id).first()
