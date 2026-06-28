from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Event, UserProfile
from ..schemas.event import EventResponse

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("", response_model=list[EventResponse])
async def list_events(
    after_id: int = Query(0, ge=0, description="Nur Events mit id > after_id (Vorwärts-Cursor für Konsumenten)"),
    object_id: Optional[int] = Query(None, description="Nur Events zu dieser Objektnummer"),
    object_type: Optional[str] = Query(None, description="z. B. order | instance | article"),
    event_type: Optional[str] = Query(None, description="z. B. order.completed"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Domain-Event-Strom (Outbox) – chronologisch vorwärts, lückenlos paginierbar.

    KI-/Automatisierungs-Konsumenten lesen ab ``after_id`` (zuletzt verarbeitete
    Event-id) und merken sich die höchste zurückgegebene id als nächsten Cursor."""
    q = db.query(Event).filter(Event.id > after_id)
    if object_id is not None:
        q = q.filter(Event.object_id == object_id)
    if object_type:
        q = q.filter(Event.object_type == object_type)
    if event_type:
        q = q.filter(Event.event_type == event_type)
    rows = q.order_by(Event.id).limit(limit).all()
    return [EventResponse.model_validate(e) for e in rows]
