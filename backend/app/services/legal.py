"""Öffentliche Rechtsdokumente (AGB/Datenschutz/…) – «Zeiger, kein Ersetzen» (D).

Ein Rechtsdokument ist append-only: jede Fassung ist eine eigene, unveränderliche
**Dokument-Instanz** (Nummer = Instanz-Objektnummer, Datum = Freigabe). Welche gerade
GILT, ist ein **Zeiger am Unternehmen** (``company_settings.legal_documents``), nicht eine
Eigenschaft der Instanz. Diese Stelle löst den Zeiger → Inhalt/Nummer/Datum auf; die
Website rendert das Ergebnis mit derselben Ansicht wie das PDF (DocumentView).

Die frühere Fassung bleibt immer über ihre Objektnummer erreichbar – wichtig, um im
Streitfall zu zeigen, welche AGB ein Kunde an welchem Tag akzeptiert hat.
"""

from typing import Optional

from sqlalchemy.orm import Session

from ..models import Instance
from .admin import get_or_create_settings
from .document import instance_document_embeds


def pointer(db: Session, kind: str) -> Optional[int]:
    """Objektnummer der gültigen Dokument-Instanz für ``kind`` (oder None)."""
    settings = get_or_create_settings(db)
    mapping = settings.legal_documents or {}
    val = mapping.get(kind)
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def resolve(db: Session, kind: str) -> Optional[dict]:
    """Gültiges Rechtsdokument für ``kind`` auflösen → ``{kind, object_number,
    document_date, content}`` – oder None (dann fällt die Website auf ihren
    eingebauten Text zurück)."""
    obj_id = pointer(db, kind)
    if obj_id is None:
        return None
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == obj_id, Instance.is_active == True)
        .first()
    )
    if inst is None:
        return None
    embeds = instance_document_embeds(db, inst)
    # Ein ausgestelltes Dokument mit Inhalt (die erste Fachzeile des Auftrags).
    doc = next((e for e in embeds if e.content), embeds[0] if embeds else None)
    if doc is None:
        return None
    return {
        "kind": kind,
        "object_number": doc.object_number,
        "document_date": doc.document_date,
        "content": doc.content,
    }
