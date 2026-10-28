"""►►► **Die Rechtstexte einmal in die Ablage** – beim Start (``main._adopt_documents``). ◄◄◄

AGB und Datenschutz sind Pflichtfelder jeder eigenen Gesellschaft. Gibt es noch **nirgends**
ein Rechtstext-Feld (eine frische Datenbank, der erste Start einer Umgebung), wird die
Vorlage das Dokument jeder eigenen Gesellschaft – sonst stünde die Website ohne AGB da.
Danach nie wieder: eine neue Gesellschaft wählt ihre Texte selbst («zu tun», «Aus Vorlage»).

Ältere Daten (Papiere als HTML, Fotos im Korb) werden nicht mehr übernommen – es braucht
keine Rückwärtskompatibilität.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import CompanySettings, DocumentRef
from . import documents, legal


def run(db: Session) -> dict[str, int]:
    """Übernehmen, was noch nicht übernommen ist – gibt zurück, wie viel es war."""
    done = {"legal": _legal(db)}
    db.flush()
    return done


def _legal(db: Session) -> int:
    if (db.query(DocumentRef.id).filter(DocumentRef.field.in_(tuple(legal.FIELD_OF.values())))
            .first() is not None):
        return 0
    count = 0
    own = (db.query(CompanySettings).filter(CompanySettings.is_own.is_(True),
                                            CompanySettings.is_active.is_(True)).all())
    for kind, field in legal.FIELD_OF.items():
        found = legal.template(kind)
        if found is None:
            continue
        for company in own:
            if not company.object_id:
                continue
            doc = legal._file_template(db, company, kind, found, found[0], None)
            documents.set_field(db, document_object_id=doc.object_id,
                                object_id=company.object_id, part=None, field=field,
                                actor=None)
            count += 1
    return count
