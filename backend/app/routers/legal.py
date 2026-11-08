"""**Die Rechtstexte für jeden** – AGB, Datenschutz, Impressum als A4-Dokument (``/agb``,
``/datenschutz``, ``/impressum``). Die Papiere eines Belegs zeigt die eine Seite eines
Dokuments (``routers/public_documents``).
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.actor import public
from ..core.database import DB
from ..services import document, geoip, legal

router = APIRouter(prefix="/api/v1/public", tags=["public"])


class LegalOut(BaseModel):
    """Ein Rechtstext, wie er heute gilt – Art, Wort, Titel, Datum und das A4-Dokument; ist
    er eine andere Datei (PDF), steht statt des Papiers ihr Link da."""
    kind: str
    word: str
    title: str
    valid_from: str = ""
    html: Optional[str] = None
    url: Optional[str] = None


@router.get("/legal/{kind}", response_model=LegalOut, dependencies=[public("web")])
def legal_text(kind: str, request: Request, country: Optional[str] = None,
               db: Session = DB) -> Any:
    """**AGB, Datenschutz oder Impressum, wie sie heute gelten** – als A4-Dokument in der
    Vorlage aller Dokumente. Die AGB sind die der Gesellschaft zum Land des Besuchers
    (``?country=XX`` übersteuert), Datenschutz und Impressum die des Betreibers."""
    if kind not in legal.KINDS:
        raise HTTPException(status_code=404, detail=f"Einen Rechtstext «{kind}» gibt es nicht.")
    if country is None:
        ip = geoip.client_ip(request.headers, request.client.host if request.client else None)
        country = geoip.country_of(ip)
    text, url, values = legal.for_visitor(db, kind, country or None)
    word, title = legal.KINDS[kind]
    if url:
        return LegalOut(kind=kind, word=word, title=title, url=url)
    if text is None:
        raise HTTPException(status_code=404, detail=f"Der Rechtstext «{kind}» ist nicht hinterlegt.")
    return LegalOut(kind=kind, word=text.word, title=text.title, valid_from=text.key,
                    html=document.standalone(text, sender=legal.sender_line(values)))
