"""Das **Subjekt** eines Auftrags – die Instanzen, auf die er wirkt.

Die Subjektart wird aus der **Gestalt des Auftrags abgeleitet** (kein Modus-Flag):

  • **produce** – Artikel + Menge, KEINE eigenen Schritte → der Auftrag fährt den
    Prozess des Artikels und ERZEUGT neue Instanzen.
  • **stock**   – eigene Schritte ohne vorgewählte Instanzen → das Subjekt wird per
    Artikel + Menge **FIFO ab Lager** allokiert (z. B. Verkauf über den Shop).
  • **chosen**  – ausgewählte, vorhandene Instanzen (``subject_of_order_id`` bei der
    Anlage gesetzt) → genau diese sind das Subjekt (Reklamation, gezielter Verkauf).

Das Subjekt wird bei der **Freigabe** hergestellt und – beim Bestands-Zugriff (stock/
chosen) – zugleich für genau diesen Auftrag **reserviert** (kein Doppelverkauf/-verbrauch).
Enthält der Ablauf einen Verkauf, verlassen die Subjekte bei Abschluss den Bestand
(``sold``, siehe ``process._finalize_subjects``); sonst bleibt der Verbleib unverändert.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, Order
from .admin import log_audit
from .inventory import allocate, available_qty, fifo_candidates
from .objects import next_object_id
from .processes import has_custom_steps
from .serialization import create_instances_for_order


def chosen_subjects(db: Session, order: Order) -> list[Instance]:
    """Die bei der Anlage ausgewählten Subjekt-Instanzen (Bestands-Auftrag)."""
    return (
        db.query(Instance)
        .filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


def subject_kind(db: Session, order: Order) -> str:
    """Abgeleitete Subjektart (Artikel ist immer der Anker):

    ``produce`` – KEINE eigenen Schritte → der Auftrag fährt den Artikel-Prozess und
      ERZEUGT neue Instanzen.
    ``stock``   – eigene Schritte (oder vorgewählte Instanzen) → der Auftrag wirkt auf
      vorhandene Instanzen des Artikels: ``quantity`` Stück, FIFO ab Lager, optional
      durch fixierte (gepinnte) Instanzen ergänzt/ersetzt."""
    if has_custom_steps(db, order) or chosen_subjects(db, order):
        return "stock"
    return "produce"


def order_instances(db: Session, order: Order) -> list[Instance]:
    """Die Instanzen, auf die der Auftrag wirkt (einheitlich, ohne Modus-Flag): die ihm
    zugeordneten Subjekte (Bestands-Zugriff) – sonst die unter ihm erzeugten."""
    subjects = chosen_subjects(db, order)
    if subjects:
        return subjects
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


def materialize_subject(db: Session, order: Order, actor_id: int) -> None:
    """Bei Freigabe das Subjekt herstellen. Committet NICHT – der Aufrufer schliesst ab.

    stock   → ``quantity`` Instanzen des Artikels binden: zuerst die fixierten (gepinnten)
      Instanzen, den Rest **FIFO ab Lager** auffüllen – alle für diesen Auftrag reserviert.
    produce → neue Bestands-Instanzen erzeugen (Serialisierung aus dem Artikel)."""
    if has_custom_steps(db, order) or chosen_subjects(db, order):
        _allocate_stock_subject(db, order, actor_id)
        return
    create_instances_for_order(db, order, actor_id)


def _allocate_stock_subject(db: Session, order: Order, actor_id: int) -> None:
    """Subjekt eines Bestands-Auftrags binden: die bereits fixierten (gepinnten) Instanzen
    zählen, den **Rest FIFO ab Lager** auffüllen (Charge bei Bedarf geteilt). Gepinnte
    Instanzen sind bereits beim Anheften reserviert; hier kommt nur die Auffüllung dazu."""
    if not order.article_id or not order.quantity:
        raise HTTPException(400, detail="Artikel und Menge sind für diesen Auftrag erforderlich")
    pinned_qty = sum(i.quantity for i in chosen_subjects(db, order))
    remaining = order.quantity - pinned_qty
    if remaining <= 0:
        return                                             # vollständig durch fixierte gedeckt
    cands = fifo_candidates(db, order.article_id, for_order_id=None)   # nur unreservierte
    have = available_qty(cands)
    if have < remaining:
        raise HTTPException(
            409, detail=f"Nicht genügend Bestand am Lager: benötigt {remaining} weitere, verfügbar {have}")
    for cand, take in zip(cands, allocate(remaining, [c.quantity for c in cands])):
        if take <= 0:
            continue
        if take == cand.quantity:
            cand.subject_of_order_id = order.id           # ganze Instanz binden
            cand.reserved_for_order_id = order.id
        else:
            cand.quantity -= take                          # Charge teilen
            db.add(Instance(
                object_id=next_object_id(db, "instance"), article_id=cand.article_id,
                order_id=cand.order_id, kind=cand.kind, quantity=take,
                quality="passed", disposition="in_stock",
                released_at=cand.released_at or cand.created_at,
                location_type=cand.location_type, location_id=cand.location_id,
                subject_of_order_id=order.id, reserved_for_order_id=order.id))
            db.flush()
    log_audit(db, "instances", None, "Bestand für Auftrag reserviert", actor_id, object_id=order.object_id)
