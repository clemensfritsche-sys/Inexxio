"""Vergabe der universellen 9-stelligen Objektnummern (100'000'001–999'999'999).

Der Nummernkreis gilt objekttyp-übergreifend: UserProfile, Article und künftige
Entitäten teilen sich denselben Bereich. Die nächste Nummer ergibt sich aus dem
Maximum über alle Objekttabellen + 1 – so kollidieren verschiedene Typen nicht.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Article, Order, PurchaseOrder, StorageLocation, UserProfile

OBJ_ID_START = 100_000_001

# Alle Spalten, die Objektnummern aus dem gemeinsamen Kreis vergeben.
_OBJECT_ID_COLUMNS = (
    UserProfile.object_id,
    Article.object_id,
    Order.object_id,
    PurchaseOrder.object_id,
    StorageLocation.object_id,
)


def current_max_object_id(db: Session) -> int:
    """Höchste vergebene Objektnummer über alle Objekttypen (oder START-1)."""
    values = [db.query(func.max(col)).scalar() for col in _OBJECT_ID_COLUMNS]
    present = [v for v in values if v is not None]
    return max(present) if present else OBJ_ID_START - 1


def next_object_id(db: Session) -> int:
    """Nächste freie Objektnummer aus dem gemeinsamen Nummernkreis."""
    return current_max_object_id(db) + 1
