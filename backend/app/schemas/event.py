from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EventResponse(BaseModel):
    """Ein Domain-Event aus dem Outbox-Strom (read-only, unveränderlich)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int] = None
    object_type: str
    event_type: str
    payload: Optional[dict] = None
    actor_id: Optional[int] = None
    created_at: datetime
