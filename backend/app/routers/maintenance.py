"""Wartungs-Lauf (E): Meldebestand-Auswertung (Auto-Nachbestellung) + Intent-Reaper.

Ein Lauf, der (1) alle Artikel unter ihrem Meldebestand nachbestellt und (2) verlassene
Checkout-Intents storniert (Reservierungs-Leak: nie bezahlte Warenkörbe – v. a. beim
manual-Provider ohne Ablauf-Ereignis bzw. bei verlorenen Stripe-expired-Webhooks).
Manuell durch Personal auslösbar (Knopf) und geeignet für einen künftigen Cloud
Scheduler (periodisch), damit auch verkaufsbedingte Bestandsabgänge erfasst werden.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..services import replenishment, selling

router = APIRouter(prefix="/api/v1/erp/maintenance", tags=["maintenance"])


class SweepResult(BaseModel):
    reordered: int         # ausgelöste Nachbestellungen (gesamt)
    reaped_intents: int    # stornierte, verlassene Checkout-Intents


@router.post("/sweep", response_model=SweepResult)
async def run_sweep(db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    """Meldebestände prüfen/nachbestellen + verlassene Checkout-Intents stornieren."""
    reordered = len(replenishment.evaluate_all(db, user.id))
    db.commit()
    reaped = selling.reap_stale_intents(db, user.id)
    return SweepResult(reordered=reordered, reaped_intents=reaped)
