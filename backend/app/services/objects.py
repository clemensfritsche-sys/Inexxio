"""Vergabe der universellen 9-stelligen Objektnummern (100'000'001–999'999'999).

Der Nummernkreis gilt objekttyp-übergreifend: UserProfile, Article und künftige
Entitäten teilen sich denselben Bereich. Die Vergabe läuft über eine **Postgres-
Sequence** (``object_id_seq``) – atomar und race-sicher, auch unter Last und ohne
Tabellen-Scan. Jede vergebene Nummer steht mit ihrem Typ in der Registry ``objects``.
"""

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Article, CompanySettings, Document, Instance, ObjectRef, Order, UserProfile

def obj_nr(object_id: int | None) -> str:
    """9-stellige Objektnummer als Text – die EINE Formatierung (Spiegel des Frontend
    ``formatObjectId``). Ohne Nummer der Gedankenstrich, damit Belege/Labels nie «None» zeigen."""
    return str(object_id).zfill(9) if object_id else "—"
OBJECT_ID_SEQUENCE = "object_id_seq"

@dataclass(frozen=True)
class Kind:
    model: Any
    word: str       # dasselbe Wort wie im Feed


#: ►►► **Die Typen, die eine Nummer tragen – EINE Tabelle** (Typ → Tabelle, Wort). ◄◄◄
#: Hier steht nur, was ein Endpunkt auch liefern kann; Prozesse sind keine eigenen Objekte
#: (Schritte hängen am Artikel/Auftrag, ohne Nummer).
TYPES: dict[str, Kind] = {
    "user": Kind(UserProfile, "Benutzer"),
    "article": Kind(Article, "Artikel"),
    "order": Kind(Order, "Auftrag"),
    "instance": Kind(Instance, "Instanz"),
    "organization": Kind(CompanySettings, "Unternehmen"),
    "document": Kind(Document, "Dokument"),
}

# **Der Nummernraum ist eine andere Aussage als der Typ.** Ein Typ kann verschwinden,
# eine vergebene Nummer nie – sie ein zweites Mal auszugeben hiesse, zwei Dinge unter
# derselben Kennung zu führen. Darum hält die **Registry** ``objects`` jede je vergebene
# Nummer, auch die eines Typs, den es nicht mehr gibt; die Sequence vergibt nie rückwärts.


def _register(db: Session, ids: list[int], object_type: str) -> None:
    """Vergebene Objektnummern in der zentralen Registry eintragen – in der Transaktion
    des Aufrufers. Ohne Typ keine Nummer: die Registry ist die eine Auskunft."""
    if object_type not in TYPES:
        raise ValueError(f"Objekttyp «{object_type}» gibt es nicht.")
    for oid in ids:
        db.add(ObjectRef(object_id=oid, object_type=object_type))


def next_object_id(db: Session, object_type: str) -> int:
    """Nächste freie Objektnummer – atomar aus der Sequence (race-sicher). Mit
    ``object_type`` wird die Nummer zugleich in der Objekt-Registry eingetragen."""
    nid = int(db.execute(text(f"SELECT nextval('{OBJECT_ID_SEQUENCE}')")).scalar())
    _register(db, [nid], object_type)
    return nid


def next_object_ids(db: Session, count: int, object_type: str) -> list[int]:
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
    """Objekttyp einer Nummer aus der Registry – jede Vergabe trägt sich dort ein
    (``next_object_id`` verlangt den Typ)."""
    ref = db.query(ObjectRef.object_type).filter(ObjectRef.object_id == object_id).first()
    return ref[0] if ref else None


def types_of(db: Session, object_ids: Iterable[int]) -> dict[int, str]:
    """Der Typ jeder Nummer aus der Registry – eine Abfrage für alle."""
    ids = {int(i) for i in object_ids if i}
    if not ids:
        return {}
    rows = db.query(ObjectRef.object_id, ObjectRef.object_type).filter(ObjectRef.object_id.in_(ids))
    return {oid: t for oid, t in rows if t in TYPES}
