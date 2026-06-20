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

from ..models import Article, Instance, Order, UserProfile
from . import process
from .admin import log_audit
from .events import emit
from .locations import ensure_receiving_location
from .objects import next_object_ids


def _initial_location(db: Session, order: Order) -> tuple[str, int]:
    """Startstandort neuer Instanzen.

    Beginnt der Prozess mit einer **Lieferanten-Beschaffung** (erster Schritt =
    ``purchase``/supplier), starten die Instanzen beim **Lieferanten** – der
    physische Wareneingang erfolgt danach über die Pflicht-Bewegung. Sonst (in-
    house gefertigt, z. B. Lohnveredelung mit Beschaffung erst mitten im Prozess)
    starten sie intern im Wareneingang."""
    defs = process.step_defs(db, order.article_id) if order.article_id else []
    first = defs[0] if defs else None
    if first and first.step_type == "purchase" and first.mode == "supplier" and first.supplier_id:
        sup = (
            db.query(UserProfile)
            .filter(UserProfile.id == first.supplier_id, UserProfile.is_active == True)
            .first()
        )
        if sup and sup.object_id:
            return ("user", sup.object_id)
    return ("lagerplatz", ensure_receiving_location(db))


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

    # Neue Instanzen sind «Im Prozess» (pending) – sie werden erst zu «Freigegeben»
    # (passed, verbrauchbar), wenn ihr Auftrag vollständig abgeschlossen ist
    # (`process.recompute_completion`) bzw. eine Eingangskontrolle sie freigibt.
    loc_type, loc_id = _initial_location(db, order)

    created: list[Instance] = []
    if art.serialization == "batch":
        count = 1
    else:  # unit → je Stück eine Instanz
        count = order.quantity
    # Objektnummern als Block vergeben (eine Query statt einer je Instanz).
    obj_ids = next_object_ids(db, count)
    kind = "batch" if art.serialization == "batch" else "unit"
    for i in range(count):
        inst = Instance(
            object_id=obj_ids[i], article_id=art.id, order_id=order.id,
            kind=kind, quantity=order.quantity if kind == "batch" else 1,
            qc_status="pending", released_at=None,
            location_type=loc_type, location_id=loc_id,
        )
        db.add(inst)
        created.append(inst)
    db.flush()

    log_audit(db, "instances", None, f"{len(created)} Instanz(en) bei Freigabe angelegt",
              actor_id, object_id=order.object_id)
    emit(db, "instances.created", object_type="order", object_id=order.object_id,
         payload={"count": len(created), "kind": kind}, actor_id=actor_id)
    return created
