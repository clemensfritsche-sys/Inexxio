"""Öffentliche Rechtsdokumente (AGB/Datenschutz/…) für die Website (D).

Löst den am Unternehmen gepflegten **Artikel-Zeiger** (``company_settings.legal_documents``)
auf: nimmt die erste freigegebene Instanz des hinterlegten Artikels (bzw. – über die
``replaced_by_id``-Kette – der neuesten Fassung mit freigegebenem Beleg) und liefert deren
Inhalt + Nummer + Datum. Kein Auth (öffentliche Website-Seiten). Ist kein Zeiger gesetzt/
auflösbar → 404, dann fällt die Website auf ihren eingebauten Rechtstext zurück.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..schemas.document import DocumentContent
from ..services import legal

router = APIRouter(prefix="/api/v1/legal", tags=["legal"])


class LegalDocument(BaseModel):
    kind: str
    object_number: Optional[int] = None
    document_date: Optional[str] = None
    content: Optional[DocumentContent] = None


@router.get("/{kind}", response_model=LegalDocument)
async def get_legal_document(kind: str, db: Session = Depends(get_db)):
    resolved = legal.resolve(db, kind)
    if resolved is None:
        raise HTTPException(404, detail="Kein Rechtsdokument hinterlegt")
    return LegalDocument(
        kind=resolved["kind"],
        object_number=resolved["object_number"],
        document_date=resolved["document_date"].isoformat() if resolved["document_date"] else None,
        content=resolved["content"],
    )
