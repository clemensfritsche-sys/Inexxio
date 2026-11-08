"""**Die Seite eines Dokuments nach aussen** – über seinen Link, ohne Anmeldung
(``services/signing``). Wer den Link hat, sieht genau dieses Dokument und unterschreibt oder
lehnt ab, wenn er als Unterzeichner verlangt ist. Ist es gelöscht: 410 mit einem Satz."""

from fastapi import APIRouter
from sqlalchemy.orm import Session

from ..core.actor import public
from ..core.database import DB
from ..schemas.documents import DeclineIn, PublicDocument, SignIn
from ..services import log
from ..services import signing

router = APIRouter(prefix="/api/v1/public/document", tags=["public"])


@router.get("/{token}", response_model=PublicDocument, dependencies=[public("link")])
def view(token: str, db: Session = DB):
    """Die Seite eines gesendeten Dokuments – **geöffnet** steht im Log (``document.viewed``,
    mit dem Empfänger des Links)."""
    link = signing.by_token(db, token)
    out = signing.view(db, link)
    log.event(db, "document.viewed", signing.doc_of(db, link).object_id,
              {"person": link.person_object_id}, table="document_links", row=link.id)
    db.flush()
    return out


@router.post("/{token}/sign", response_model=PublicDocument, dependencies=[public("link")])
def sign(token: str, data: SignIn, db: Session = DB):
    """**Unterschreiben** – endgültig."""
    link = signing.by_token(db, token)
    signing.sign(db, link, data.image)
    db.flush()
    return signing.view(db, link)


@router.post("/{token}/decline", response_model=PublicDocument, dependencies=[public("link")])
def decline(token: str, data: DeclineIn, db: Session = DB):
    """**Ablehnen** – mit Grund; danach unterschreibt niemand mehr."""
    link = signing.by_token(db, token)
    signing.decline(db, link, data.reason)
    db.flush()
    return signing.view(db, link)
