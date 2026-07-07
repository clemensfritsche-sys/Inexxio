"""Consent-Gate-Endpunkte: offene Pflicht-Bestätigungen abrufen und quittieren.

Für JEDE angemeldete Rolle (Mitarbeiter, Lieferant, Kunde, Admin) – ``get_current_user``,
nicht ``require_employee``. Das Frontend blockiert die Oberfläche, solange ``/pending``
Einträge liefert.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.consent import AcknowledgeRequest, PendingDocument
from ..services import consent

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


@router.get("/pending", response_model=list[PendingDocument])
async def list_pending(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Noch zu bestätigende Pflichtdokumente des aktuellen Nutzers (aktuelle Version)."""
    return consent.pending_documents(db, current_user)


@router.post("/acknowledge", response_model=list[PendingDocument])
async def acknowledge(
    data: AcknowledgeRequest,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ein Dokument bestätigen; liefert die **verbleibenden** offenen Bestätigungen zurück."""
    consent.acknowledge(db, current_user, data.kind)
    return consent.pending_documents(db, current_user)
