"""Der Verlauf eines Datensatzes – EIN Endpunkt für jede Nummer (``services/history``)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.history import HistoryPage
from ..services import history as svc

router = APIRouter(prefix="/api/v1/erp/history", tags=["history"])


@router.get("/{object_id}", response_model=HistoryPage)
def history(object_id: int, before: Optional[str] = Query(None),
            limit: int = Query(svc.communication.PAGE, ge=1, le=100),
            db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    """Eine Seite des Verlaufs – Nachrichten, Dokumente und Änderungen, die neuesten zuerst;
    ``before`` ist der Cursor der vorigen Seite."""
    return svc.page(db, object_id, user, before=before, limit=limit)
