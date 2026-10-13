"""Kommunikation – Verlauf lesen, Nachricht anlegen, offene zählen (nur Personal)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.communication import ChannelOut, MessageIn, MessageOut, OpenCount
from ..services import communication as svc

router = APIRouter(prefix="/api/v1/erp/messages", tags=["communication"])


@router.get("/channels", response_model=list[ChannelOut])
def list_channels(_: UserProfile = Depends(require_employee)):
    return svc.channels()


@router.get("/open", response_model=list[OpenCount])
def open_counts(db: Session = Depends(get_db), _: UserProfile = Depends(require_employee)):
    """Je Person die offenen Nachrichten im Verlauf – das Zeichen am Symbol im Feed."""
    return svc.open_counts(db)


@router.get("", response_model=list[MessageOut])
def history(
    person: Optional[int] = Query(None),
    company: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Der Verlauf einer Person oder aller Personen einer Firma – chronologisch."""
    if not person and not company:
        raise HTTPException(400, detail="Person oder Firma angeben.")
    return svc.history(db, person=person, company=company)


@router.post("", response_model=MessageOut)
def create(
    data: MessageIn,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    msg = svc.create(db, data, user)
    db.commit()
    return next(m for m in svc.load(db, [msg.id]))
