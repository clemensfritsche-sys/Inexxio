"""Wartungs-Lauf (E): Haltbarkeits-Sweep + Meldebestand-Auswertung.

Ein Lauf, der (a) abgelaufene Instanzen ausbucht und (b) alle Artikel unter Meldebestand
nachbestellt. Manuell durch Personal auslösbar (Knopf) und geeignet für einen künftigen
Cloud Scheduler (periodisch), damit auch verkaufsbedingte Bestandsabgänge erfasst werden.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..services import expiry, replenishment

router = APIRouter(prefix="/api/v1/erp/maintenance", tags=["maintenance"])


class SweepResult(BaseModel):
    expired: int          # abgelaufene, ausgebuchte Instanzen
    reordered: int        # ausgelöste Nachbestellungen (gesamt)


@router.post("/sweep", response_model=SweepResult)
async def run_sweep(db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    """Haltbarkeit ausbuchen, dann alle Artikel auf Meldebestand prüfen (Auto-Nachbestellung)."""
    result = expiry.sweep(db, user.id)
    reordered = len(replenishment.evaluate_all(db, user.id))
    db.commit()
    return SweepResult(expired=result["expired"], reordered=result["reordered"] + reordered)
