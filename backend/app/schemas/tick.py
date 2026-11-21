from typing import Literal, Optional

from pydantic import BaseModel


class TickTaskOut(BaseModel):
    """Eine Aufgabe des Takts (``services/tick.TASKS``) in diesem Lauf."""
    name: str
    state: Literal["ok", "skipped", "failed"]
    #: Warum übersprungen oder gescheitert (ein Satz).
    detail: Optional[str] = None
    #: Was sie getan hat – nur Zahlen über null (``{}`` = nichts zu tun).
    done: dict[str, int] = {}


class TickOut(BaseModel):
    tasks: list[TickTaskOut]
