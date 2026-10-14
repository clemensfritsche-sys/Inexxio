"""Testnotizen der Oberfläche («Pin setzen und Kommentar hinterlassen»).

Offen für **jede angemeldete Rolle** – auch Kunde und Lieferant sollen aus ihrer Sicht
melden können. Die Sichtbarkeit regelt ``services/feedback.py`` (eigene Notizen; Personal
sieht alles). Ausserhalb der Testumgebung existiert der Endpunkt nicht (404).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import FeedbackNote, UserProfile
from ..schemas.feedback import FeedbackCreate, FeedbackNoteResponse, FeedbackUpdate
from ..services import feedback as feedback_svc

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


def _require_enabled() -> None:
    if not feedback_svc.is_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Feedback module disabled")


@router.get("", response_model=list[FeedbackNoteResponse])
async def list_feedback(
    route: str | None = Query(None, description="Nur Notizen dieser Seite (Pfad)"),
    note_status: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    _require_enabled()
    notes = feedback_svc.list_notes(db, user, route=route, status=note_status)
    return [feedback_svc.to_response(db, n, user) for n in notes]


@router.post("", response_model=FeedbackNoteResponse, status_code=201)
async def create_feedback(
    data: FeedbackCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    _require_enabled()
    note = feedback_svc.create_note(db, user, data)
    db.commit()
    db.refresh(note)
    return feedback_svc.to_response(db, note, user)


@router.delete("", status_code=200)
async def clear_feedback(
    scope: str = Query("done", description="'done' = Erledigte/Verworfene, 'all' = alles"),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Aufräumen bzw. zurücksetzen – wirkt nur auf die eigenen sichtbaren Notizen."""
    _require_enabled()
    try:
        removed = feedback_svc.delete_many(db, user, scope)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    db.commit()
    return {"deleted": removed}


@router.delete("/{note_id}", status_code=204)
async def delete_feedback(
    note_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    _require_enabled()
    note = feedback_svc.visible_query(db, user).filter(FeedbackNote.id == note_id).first()
    if not note:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    feedback_svc.delete_note(db, note)
    db.commit()
    return None


@router.patch("/{note_id}", response_model=FeedbackNoteResponse)
async def update_feedback(
    note_id: int,
    data: FeedbackUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Erledigt/verworfen setzen – durch den Melder selbst oder durch Personal."""
    _require_enabled()
    note = feedback_svc.visible_query(db, user).filter(FeedbackNote.id == note_id).first()
    if not note:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notiz nicht gefunden")
    feedback_svc.apply_update(db, note, user, data)
    db.commit()
    db.refresh(note)
    return feedback_svc.to_response(db, note, user)
