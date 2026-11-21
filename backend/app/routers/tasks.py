"""Aufgaben – wer macht was (Projektakte `docs/konzept/aufgaben.md`, ``services/tasks``)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import DB
from ..models import UserProfile
from ..schemas.tasks import TasksOut
from ..services import tasks

router = APIRouter(prefix="/api/v1/erp", tags=["tasks"])


@router.get("/tasks", response_model=TasksOut)
def read_tasks(db: Session = DB, actor: UserProfile = Depends(require_employee)):
    """Meine eine Aufgabe und die roten Zeichen, die ich sehe – teilt vorher zu (``tasks.dispatch``)."""
    return tasks.view(db, actor)


@router.post("/tasks/{key}/hand", response_model=TasksOut)
def hand_task(key: str, db: Session = DB, actor: UserProfile = Depends(require_employee)):
    """Meine Aufgabe abgeben – ohne Grund; sie geht an die nächste freie Person, die sie kann."""
    tasks.hand(db, actor, key)
    return tasks.view(db, actor)
