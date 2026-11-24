"""Aussortierte Anfragen der Website – «Kein Spam» oder «Spam» (``services/spam``)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import DB
from ..models import UserProfile
from ..schemas.spam import HeldOut, ReleasedOut
from ..services import spam

router = APIRouter(prefix="/api/v1/erp/inquiries", tags=["communication"])


def _out(h: spam.Held) -> HeldOut:
    p = h.payload
    return HeldOut(id=h.id, at=h.at, company=h.company, name=p.get("name", ""),
                   email=p.get("email", ""), phone=p.get("phone", ""), firm=p.get("company", ""),
                   message=p.get("message", ""), source=p.get("source", ""),
                   reason=p.get("reason", ""),
                   files=[{"name": f.get("name", ""), "url": f.get("url", "")}
                          for f in p.get("files") or []])


@router.get("/held", response_model=list[HeldOut])
def read_held(company: int = Query(..., description="Objektnummer der eigenen Gesellschaft."),
              db: Session = DB, actor: UserProfile = Depends(require_employee)):
    """Die aussortierten Anfragen einer Gesellschaft, über die noch niemand entschieden hat."""
    return [_out(h) for h in spam.open_held(db, company)]


@router.post("/held/{held_id}/release", response_model=ReleasedOut)
def release_held(held_id: int, db: Session = DB, actor: UserProfile = Depends(require_employee)):
    """Kein Spam: die aussortierte Anfrage wird angelegt wie eben gekommen, samt Bestätigung."""
    return ReleasedOut(message=spam.release(db, held_id))


@router.post("/held/{held_id}/discard", status_code=204)
def discard_held(held_id: int, db: Session = DB, actor: UserProfile = Depends(require_employee)):
    """Spam: entschieden – es entsteht nichts, die Anfrage bleibt im Log."""
    spam.discard(db, held_id)
