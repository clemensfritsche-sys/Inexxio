"""Das **Subjekt** eines Auftrags – die Instanzen, auf die er wirkt.

    MAKE   – bei Freigabe ERZEUGTE Instanzen          (Instance.order_id == order.id)
    CUSTOM – die AUSGEWÄHLTEN, vorhandenen Instanzen   (Instance.subject_of_order_id == order.id)

``order_instances`` liefert einheitlich diese Liste; darauf bauen Datenerfassung,
Bewegung, Ressource und Verkauf auf – unabhängig vom Modus.
"""

from sqlalchemy.orm import Session

from ..models import Instance, Order
from .serialization import create_instances_for_order


def order_instances(db: Session, order: Order) -> list[Instance]:
    """Die Instanzen, auf die der Auftrag wirkt (einheitlich über beide Modi)."""
    if order.mode == "custom":
        q = db.query(Instance).filter(
            Instance.subject_of_order_id == order.id, Instance.is_active == True)
    else:
        q = db.query(Instance).filter(
            Instance.order_id == order.id, Instance.is_active == True)
    return q.order_by(Instance.object_id).all()


def materialize_subject(db: Session, order: Order, actor_id: int) -> None:
    """Bei Auftragsfreigabe das Subjekt herstellen.

    CUSTOM: die ausgewählten Instanzen sind bereits markiert (``subject_of_order_id``,
    bei der Anlage) – es wird nichts erzeugt. MAKE: neue Bestands-Instanzen anlegen
    (Serialisierung aus dem Artikel). Committet NICHT – der Aufrufer schliesst ab."""
    if order.mode == "custom":
        return
    create_instances_for_order(db, order, actor_id)
