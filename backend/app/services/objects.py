"""Vergabe der universellen 9-stelligen Objektnummern (100'000'001–999'999'999).

Der Nummernkreis gilt objekttyp-übergreifend: UserProfile, Article und künftige
Entitäten teilen sich denselben Bereich. Die nächste Nummer ergibt sich aus dem
Maximum über alle Objekttabellen + 1 – so kollidieren verschiedene Typen nicht.

Das Maximum wird in EINER Query (UNION ALL der Objektnummer-Spalten) ermittelt,
nicht in einer Abfrage je Tabelle. Für Massenanlagen (z. B. N Instanzen bei der
Auftragsfreigabe) gibt ``next_object_ids`` einen ganzen Block auf einmal aus –
das vermeidet eine Query je Einzelobjekt.
"""

from sqlalchemy import func, select, union_all
from sqlalchemy.orm import Session

from ..models import Article, Claim, Instance, Order, StorageLocation, UserProfile

OBJ_ID_START = 100_000_001

# Alle Spalten, die Objektnummern aus dem gemeinsamen Kreis vergeben.
# Bestellungen/Eingangskontrollen bekommen KEINE eigene Nummer (laufen unter dem
# Auftrag); Instanzen und Reklamationen hingegen sind eigenständige Objekte.
_OBJECT_ID_COLUMNS = (
    UserProfile.object_id,
    Article.object_id,
    Order.object_id,
    Instance.object_id,
    StorageLocation.object_id,
    Claim.object_id,
)


def current_max_object_id(db: Session) -> int:
    """Höchste vergebene Objektnummer über alle Objekttypen (oder START-1).

    EINE Query: UNION ALL aller Objektnummer-Spalten, dann das Maximum darüber."""
    parts = [select(col.label("object_id")) for col in _OBJECT_ID_COLUMNS]
    combined = union_all(*parts).subquery()
    max_id = db.query(func.max(combined.c.object_id)).scalar()
    return max_id if max_id is not None else OBJ_ID_START - 1


def next_object_id(db: Session) -> int:
    """Nächste freie Objektnummer aus dem gemeinsamen Nummernkreis."""
    return current_max_object_id(db) + 1


def next_object_ids(db: Session, count: int) -> list[int]:
    """Block aufeinanderfolgender Objektnummern (eine Query statt einer je Objekt).

    Für Massenanlagen wie die Instanz-Erzeugung bei der Auftragsfreigabe."""
    if count <= 0:
        return []
    start = current_max_object_id(db) + 1
    return list(range(start, start + count))
