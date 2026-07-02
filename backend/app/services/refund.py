"""Retoure/Erstattung als **ganz normaler Auftrag** (kein Button, kein Sonderobjekt).

Eine Retoure entsteht wie jeder andere Auftrag: Artikel wählen, die **verkauften** Instanzen
als Subjekt fixieren, dann den Ablauf definieren – in aller Regel **Bewegung** (Ware zurück ins
Lager) + **Rückerstattung** (``refund``-Schritt = Geld zurück), danach frei weiteres (Prüfung,
Verschrotten …).

Modellierung: der Auftrag bekommt ``reason='return'`` (festes Subjekt wie eine Abweichung –
keine FIFO-Reservierung, kein Eltern-Pause) und ``parent_order_id`` = der **Original-Verkauf**,
aus dem die gewählten Instanzen stammen. Der Parent ist die Grundlage der Gutschrift (Betrag/
MWST/Kunde/Stripe-PaymentIntent, siehe ``sale.original_sale_for``).

Der **physische** Rückfluss (sold → in_stock) passiert bei Auftrags-**Abschluss**, wenn die
Instanz per Bewegung an einem Lagerplatz gelandet ist (``process._finalize_subjects``); die
**Geld**-Seite erledigt der ``refund``-Schritt (Sale ``kind='credit'`` + Stripe-Refund).
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, InstanceOrderLink, Order, Sale
from .admin import log_audit
from .events import emit


def _sold_instances(db: Session, object_ids: list[int]) -> list[Instance]:
    """Die gewählten Instanzen prüfen: vorhanden, aktiv, **verkauft** (nur verkaufte Teile
    sind erstattbar)."""
    rows: list[Instance] = []
    for oid in dict.fromkeys(object_ids):
        inst = db.query(Instance).filter(Instance.object_id == oid, Instance.is_active == True).first()
        if not inst:
            raise HTTPException(400, detail=f"Instanz {oid} nicht gefunden")
        if inst.disposition != "sold":
            raise HTTPException(
                409, detail=f"Instanz {oid} ist nicht verkauft – nur verkaufte Teile sind erstattbar")
        rows.append(inst)
    return rows


def original_sale_order(db: Session, instances: list[Instance]) -> Order:
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


def bind_refund_subject(db: Session, order: Order, object_ids: list[int], actor_id: int) -> None:
    """Die **verkauften** Instanzen als Subjekt eines Retoure-Auftrags (Entwurf) fixieren –
    macht den Auftrag zur Retoure (``reason='return'`` + ``parent_order_id`` = Original-Verkauf).
    Leere Auswahl hebt die Retoure wieder auf. Committet NICHT (der Aufrufer schliesst ab)."""
    if order.status != "draft":
        raise HTTPException(409, detail="Das Subjekt lässt sich nur im Entwurf ändern")
    # bisherige Fixierung lösen
    for prev in db.query(Instance).filter(
            Instance.subject_of_order_id == order.id, Instance.is_active == True).all():
        prev.subject_of_order_id = None
    if not object_ids:
        order.reason = None
        order.parent_order_id = None
        return
    insts = _sold_instances(db, object_ids)
    parent = original_sale_order(db, insts)
    order.reason = "return"
    order.parent_order_id = parent.object_id
    # Anker angleichen: bei genau EINEM Artikel diesen führen, Menge = Anzahl gewählter
    # Instanzen (nur Anzeige – die Freigabe nutzt das feste Subjekt, nicht Artikel/Menge).
    article_ids = {i.article_id for i in insts}
    order.article_id = next(iter(article_ids)) if len(article_ids) == 1 else None
    order.quantity = len(insts) if order.article_id is not None else None
    for inst in insts:
        inst.subject_of_order_id = order.id
    log_audit(db, "orders", None, f"Retoure zu Verkauf {parent.object_id} – {len(insts)} Instanz(en)",
              actor_id, object_id=order.object_id)
    emit(db, "order.refund_subject_set", object_type="order", object_id=order.object_id,
         payload={"parent": parent.object_id, "instances": [i.object_id for i in insts]}, actor_id=actor_id)
