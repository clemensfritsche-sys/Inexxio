"""Wartungs-Lauf (E): Meldebestand-Auswertung (Auto-Nachbestellung).

Ein Lauf, der alle Artikel unter ihrem Meldebestand nachbestellt. Manuell durch Personal
auslösbar (Knopf) und geeignet für einen künftigen Cloud Scheduler (periodisch), damit auch
verkaufsbedingte Bestandsabgänge erfasst werden.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..services import replenishment

router = APIRouter(prefix="/api/v1/erp/maintenance", tags=["maintenance"])


class SweepResult(BaseModel):
    reordered: int        # ausgelöste Nachbestellungen (gesamt)


@router.post("/sweep", response_model=SweepResult)
async def run_sweep(db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    """Alle Artikel auf ihren Meldebestand prüfen und fehlenden Bestand nachbestellen."""
    reordered = len(replenishment.evaluate_all(db, user.id))
    db.commit()
    return SweepResult(reordered=reordered)
