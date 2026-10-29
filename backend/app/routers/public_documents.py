"""**Die Seite eines Dokuments nach aussen** – über seinen Link, ohne Anmeldung
(``services/signing``). Wer den Link hat, sieht genau dieses Dokument und unterschreibt oder
lehnt ab, wenn er als Unterzeichner verlangt ist. Ist es gelöscht: 410 mit einem Satz."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..schemas.documents import DeclineIn, PublicDocument, SignIn
from ..services import signing

router = APIRouter(prefix="/api/v1/public/document", tags=["public"])


@router.get("/{token}", response_model=PublicDocument)
def view(token: str, db: Session = Depends(get_db)):
    return signing.view(db, signing.by_token(db, token))


@router.post("/{token}/sign", response_model=PublicDocument)
def sign(token: str, data: SignIn, db: Session = Depends(get_db)):
    """**Unterschreiben** – endgültig."""
    link = signing.by_token(db, token)
    signing.sign(db, link, data.image)
    db.commit()
    return signing.view(db, link)


@router.post("/{token}/decline", response_model=PublicDocument)
def decline(token: str, data: DeclineIn, db: Session = Depends(get_db)):
    """**Ablehnen** – mit Grund; danach unterschreibt niemand mehr."""
    link = signing.by_token(db, token)
    signing.decline(db, link, data.reason)
    db.commit()
    return signing.view(db, link)
