"""Erzeugung der Bestands-Instanzen eines Auftrags – bei der **Freigabe**.

Es gibt keinen eigenen Prozessschritt «Serialisierung» mehr: Sobald ein Auftrag
freigegeben wird, legt das System sofort die Bestands-Instanzen an. Das schafft
Rückverfolgbarkeit ab dem ersten Moment (Standort, Seriennummer, Abweichung …).

Abgeleitet aus der Artikel-Einstellung ``serialization``:
    unit  → N Einzel-Instanzen (je quantity=1, eigene Nummer)
    batch → 1 Charge-Instanz mit quantity = Bestellmenge

Startstandort:
    - Beginnt der Prozess mit einer **Lieferanten-Beschaffung** (erster Schritt),
      starten die Instanzen direkt **beim Lieferanten** (``location_type='user'``);
      der physische Wareneingang erfolgt danach über die Pflicht-Bewegung.
    - Sonst (in-house gefertigt, oder die Beschaffung kommt erst später) starten
      sie **ohne Standort** (``NULL`` = «noch nicht festgelegt»). Den realen Ort
      legt der erste Bewegungs-/Wareneingangsschritt fest. So wird keine Instanz
      fälschlich dem Wareneingang zugeschlagen, obwohl noch nichts angekommen ist.
"""

from sqlalchemy.orm import Session

from ..models import Article, Instance, Order, UserProfile
from . import process
from .admin import log_audit
from .events import emit
from .objects import next_object_ids


def _initial_location(db: Session, order: Order) -> tuple[str | None, int | None]:
    """Startstandort neuer Instanzen.

    Beginnt der Prozess mit einer **Lieferanten-Beschaffung** (erster Schritt =
    ``purchase``/supplier), starten die Instanzen beim **Lieferanten**. Sonst gibt
    es (noch) keinen physischen Standort → ``(None, None)``; er wird durch den
    ersten Bewegungs-Schritt gesetzt."""
    defs = process.order_step_defs(db, order)
    first = defs[0] if defs else None
    if first and first.step_type == "purchase" and first.mode == "supplier" and first.supplier_id:
        sup = (
            db.query(UserProfile)
            .filter(UserProfile.id == first.supplier_id, UserProfile.is_active == True)
            .first()
        )
        if sup and sup.object_id:
            return ("user", sup.object_id)
    return (None, None)


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
    obj_ids = next_object_ids(db, count, "instance")
    kind = "batch" if art.serialization == "batch" else "unit"
    for i in range(count):
        inst = Instance(
            object_id=obj_ids[i], article_id=art.id, order_id=order.id,
            kind=kind, quantity=order.quantity if kind == "batch" else 1,
            quality="pending", disposition="in_process", released_at=None,
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
