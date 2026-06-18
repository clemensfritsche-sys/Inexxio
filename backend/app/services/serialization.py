"""Erzeugung der Bestands-Instanzen eines Auftrags – bei der **Freigabe**.

Es gibt keinen eigenen Prozessschritt «Serialisierung» mehr: Sobald ein Auftrag
freigegeben wird, legt das System sofort die Bestands-Instanzen an. Das schafft
Rückverfolgbarkeit ab dem ersten Moment (Standort, Seriennummer, Reklamation …).

Abgeleitet aus der Artikel-Einstellung ``serialization``:
    unit  → N Einzel-Instanzen (je quantity=1, eigene Nummer)
    batch → 1 Charge-Instanz mit quantity = Bestellmenge

Startstandort:
    - Gibt es einen Beschaffungsschritt mit Lieferant, starten die Instanzen
      direkt **beim Lieferanten** (``location_type='user'``). Der Wareneingang
      erfolgt mit dem Bestell-Status «received» – dann wechseln die Instanzen an
      den Wareneingang (siehe ``services/purchase.py``).
    - Sonst (Webshop / keine Beschaffung) starten sie direkt im **Wareneingang**.
"""

from sqlalchemy.orm import Session

from ..models import Article, Instance, Order, PurchaseOrder, UserProfile
from ..models.base import utcnow
from . import process
from .admin import log_audit
from .locations import resolve_receiving_location
from .objects import next_object_id


def _initial_location(db: Session, order: Order) -> tuple[str, int]:
    """Startstandort neuer Instanzen: Lieferant (falls bekannt), sonst Wareneingang."""
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .first()
    )
    if po and po.mode == "supplier" and po.supplier_id:
        sup = (
            db.query(UserProfile)
            .filter(UserProfile.id == po.supplier_id, UserProfile.is_active == True)
            .first()
        )
        if sup and sup.object_id:
            return ("user", sup.object_id)
    return ("lagerplatz", resolve_receiving_location(db, po))


def create_instances_for_order(db: Session, order: Order, actor_id: int) -> list[Instance]:
    """Bei Auftragsfreigabe die Bestands-Instanzen anlegen (idempotent).

    Committet NICHT – der Aufrufer (Auftragsfreigabe) schliesst die Transaktion ab.
    """
    existing = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .all()
    )
    if existing:
        return existing
    art = db.query(Article).filter(Article.id == order.article_id).first()
    if not art or not order.quantity:
        return []

    # Ohne nachgelagerte Eingangskontrolle gilt die Ware direkt als freigegeben
    qc = "pending" if process.has_step(db, order, "inspection") else "passed"
    released = utcnow() if qc == "passed" else None   # Basis für FIFO-Verbrauch
    loc_type, loc_id = _initial_location(db, order)

    created: list[Instance] = []
    if art.serialization == "batch":
        inst = Instance(
            object_id=next_object_id(db), article_id=art.id, order_id=order.id,
            kind="batch", quantity=order.quantity, qc_status=qc, released_at=released,
            location_type=loc_type, location_id=loc_id,
        )
        db.add(inst); db.flush()
        created.append(inst)
    else:  # unit → je Stück eine Instanz
        for _ in range(order.quantity):
            inst = Instance(
                object_id=next_object_id(db), article_id=art.id, order_id=order.id,
                kind="unit", quantity=1, qc_status=qc, released_at=released,
                location_type=loc_type, location_id=loc_id,
            )
            db.add(inst); db.flush()
            created.append(inst)

    log_audit(db, "instances", None, f"{len(created)} Instanz(en) bei Freigabe angelegt",
              actor_id, object_id=order.object_id)
    return created
