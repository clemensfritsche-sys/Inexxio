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

from ..models import (
    Article, CompanySettings, Instance, ObjectRef, Order,
    StorageLocation, UserProfile,
)

OBJ_ID_START = 100_000_001
OBJECT_ID_SEQUENCE = "object_id_seq"

# Objekttyp ↔ Modell (für Registry-Backfill und -Pflege). Prozesse sind KEINE
# eigenständigen Objekte mehr (Schritte hängen am Artikel/Auftrag, ohne Nummer).
_TYPE_MODELS = {
    "user": UserProfile,
    "article": Article,
    "order": Order,
    "instance": Instance,
    # Das Dokument trägt KEINE eigene Nummer – seine Nummer ist die Instanz-Objektnummer
    # (der Liefergegenstand des Auftrags). Deshalb NICHT in der Nummernkreis-Registry.
    "storage_location": StorageLocation,
    # Das Unternehmen selbst (Singleton) ist ebenfalls ein nummerierter ERP-Datensatz.
    "organization": CompanySettings,
}

# Alle Spalten, die Objektnummern aus dem gemeinsamen Kreis vergeben.
# Bestellungen/Eingangskontrollen bekommen KEINE eigene Nummer (laufen unter dem
# Auftrag); Instanzen hingegen sind eigenständige Objekte. Abweichungen sind
# Unteraufträge (parent_order_id) und laufen daher als Auftrag mit Objektnummer.
_OBJECT_ID_COLUMNS = tuple(m.object_id for m in _TYPE_MODELS.values())


def _register(db: Session, ids: list[int], object_type: str | None) -> None:
    """Vergebene Objektnummern in der zentralen Registry eintragen (sofern Typ
    bekannt). Läuft in der Transaktion des Aufrufers mit."""
    if not object_type:
        return
    for oid in ids:
        db.add(ObjectRef(object_id=oid, object_type=object_type))


def current_max_object_id(db: Session) -> int:
    """Höchste vergebene Objektnummer über alle Objekttypen (oder START-1).

    EINE Query (UNION ALL aller Objektnummer-Spalten). Wird für die Sequence-
    Ausrichtung und Backfills genutzt – NICHT mehr für die laufende Vergabe."""
    parts = [select(col.label("object_id")) for col in _OBJECT_ID_COLUMNS]
    combined = union_all(*parts).subquery()
    max_id = db.query(func.max(combined.c.object_id)).scalar()
    return max_id if max_id is not None else OBJ_ID_START - 1


def next_object_id(db: Session, object_type: str | None = None) -> int:
    """Nächste freie Objektnummer – atomar aus der Sequence (race-sicher). Mit
    ``object_type`` wird die Nummer zugleich in der Objekt-Registry eingetragen."""
    nid = int(db.execute(text(f"SELECT nextval('{OBJECT_ID_SEQUENCE}')")).scalar())
    _register(db, [nid], object_type)
    return nid


def next_object_ids(db: Session, count: int, object_type: str | None = None) -> list[int]:
    """Block aufeinanderfolgender Objektnummern – ein Roundtrip, atomar. Mit
    ``object_type`` werden alle Nummern in der Objekt-Registry eingetragen.

    Für Massenanlagen wie die Instanz-Erzeugung bei der Auftragsfreigabe."""
    if count <= 0:
        return []
    rows = db.execute(
        text(f"SELECT nextval('{OBJECT_ID_SEQUENCE}') FROM generate_series(1, :n)"),
        {"n": count},
    ).scalars().all()
    ids = [int(r) for r in rows]
    _register(db, ids, object_type)
    return ids


def resolve_object_type(db: Session, object_id: int) -> str | None:
    """Objekttyp einer Nummer in O(1) aus der Registry; Fallback: Fachtabellen
    absuchen (für Nummern, die noch nicht registriert wurden)."""
    ref = db.query(ObjectRef.object_type).filter(ObjectRef.object_id == object_id).first()
    if ref:
        return ref[0]
    for otype, model in _TYPE_MODELS.items():
        if db.query(model.id).filter(model.object_id == object_id).first():
            return otype
    return None


def backfill_registry(db: Session) -> None:
    """Registry idempotent mit allen vorhandenen Objektnummern auffüllen
    (Altdaten + alles, was ohne Typ vergeben wurde). ON CONFLICT DO NOTHING."""
    for otype, model in _TYPE_MODELS.items():
        db.execute(text(
            f"INSERT INTO objects (object_id, object_type, created_at) "
            f"SELECT object_id, :t, now() FROM {model.__tablename__} "
            f"WHERE object_id IS NOT NULL ON CONFLICT (object_id) DO NOTHING"
        ), {"t": otype})


# Quer-Referenzen (Spalte → objects.object_id) für FK-Integrität. Alle nullable;
# ON DELETE SET NULL (wir löschen ohnehin nur soft, Registry bleibt bestehen).
_FOREIGN_KEYS = (
    ("articles", "fk_articles_replaced_by", "replaced_by_id"),
    ("orders", "fk_orders_replaced_by", "replaced_by_id"),
    ("storage_locations", "fk_storage_locations_replaced_by", "replaced_by_id"),
    ("instances", "fk_instances_location", "location_id"),
)


def ensure_foreign_keys(db: Session) -> None:
    """FK-Constraints der Quer-Referenzen auf die Registry idempotent anlegen
    (nach dem Backfill). Best-effort je Constraint: schlägt eines fehl (z. B. wegen
    Altdaten), werden die übrigen trotzdem gesetzt."""
    for table, name, col in _FOREIGN_KEYS:
        if db.execute(text("SELECT 1 FROM pg_constraint WHERE conname = :n"), {"n": name}).first():
            continue
        try:
            db.execute(text(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} "
                f"FOREIGN KEY ({col}) REFERENCES objects(object_id) ON DELETE SET NULL"
            ))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"WARNING: FK {name} not added: {e}", flush=True)
