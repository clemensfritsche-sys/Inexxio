"""Vergabe der universellen 9-stelligen Objektnummern (100'000'001–999'999'999).

Der Nummernkreis gilt objekttyp-übergreifend: UserProfile, Article und künftige
Entitäten teilen sich denselben Bereich. Die Vergabe läuft über eine **Postgres-
Sequence** (``object_id_seq``) – atomar und race-sicher, auch unter Last und ohne
Tabellen-Scan. ``current_max_object_id`` (Maximum über alle Objekttabellen) dient
nur noch der einmaligen Ausrichtung der Sequence beim Start (siehe ``main.py``)
sowie der Backfill-Logik für Altdaten.
"""

from sqlalchemy import func, select, text, union_all
from sqlalchemy.orm import Session

from ..models import Article, Claim, Instance, Order, StorageLocation, UserProfile

OBJ_ID_START = 100_000_001
OBJECT_ID_SEQUENCE = "object_id_seq"

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

    EINE Query (UNION ALL aller Objektnummer-Spalten). Wird für die Sequence-
    Ausrichtung und Backfills genutzt – NICHT mehr für die laufende Vergabe."""
    parts = [select(col.label("object_id")) for col in _OBJECT_ID_COLUMNS]
    combined = union_all(*parts).subquery()
    max_id = db.query(func.max(combined.c.object_id)).scalar()
    return max_id if max_id is not None else OBJ_ID_START - 1


def next_object_id(db: Session) -> int:
    """Nächste freie Objektnummer – atomar aus der Sequence (race-sicher)."""
    return int(db.execute(text(f"SELECT nextval('{OBJECT_ID_SEQUENCE}')")).scalar())


def next_object_ids(db: Session, count: int) -> list[int]:
    """Block aufeinanderfolgender Objektnummern – ein Roundtrip, atomar.

    Für Massenanlagen wie die Instanz-Erzeugung bei der Auftragsfreigabe."""
    if count <= 0:
        return []
    rows = db.execute(
        text(f"SELECT nextval('{OBJECT_ID_SEQUENCE}') FROM generate_series(1, :n)"),
        {"n": count},
    ).scalars().all()
    return [int(r) for r in rows]
