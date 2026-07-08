"""Consent-Gate-Endpunkte: offene Pflicht-Bestätigungen abrufen und quittieren.

Für JEDE angemeldete Rolle (Mitarbeiter, Lieferant, Kunde, Admin) – ``get_current_user``,
nicht ``require_employee``. Das Frontend blockiert die Oberfläche, solange ``/pending``
Einträge liefert.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.consent import (
    Acknowledgement, AcknowledgeRequest, MyHistoryDocument, MySignoffDocument, PendingDocument,
)
from ..schemas.document import SignoffAction
from ..services import consent
from ..services import document as document_svc

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
    consent.acknowledge(db, current_user, data.kind, data.object_number)
    return consent.pending_documents(db, current_user)


@router.get("/my-documents", response_model=list[MySignoffDocument])
async def my_documents(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dokumente, auf die ich als **Freigabe-Partei** noch handeln muss (unterschreiben/
    bestätigen) – für die persönliche «Meine Dokumente»-Ansicht (jede Rolle)."""
    return document_svc.my_pending_signoffs(db, current_user)


@router.post("/signoffs/{signoff_id}", response_model=list[MySignoffDocument])
async def act_signoff(
    signoff_id: int,
    data: SignoffAction,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Als benannte Freigabe-Partei handeln (unterschreiben/bestätigen/ablehnen/zurückziehen);
    liefert die **verbleibenden** offenen Dokumente zurück."""
    signoff = document_svc.get_signoff(db, signoff_id)
    document_svc.act_on_signoff(db, signoff, data, current_user)
    return document_svc.my_pending_signoffs(db, current_user)


@router.get("/my-history", response_model=list[MyHistoryDocument])
async def my_history(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Erledigte Dokument-Vorgänge des Nutzers (Unterschriften/Bestätigungen + Anerkennungen)
    – damit ein bereits akzeptiertes/unterschriebenes Dokument in «Meine Dokumente» sichtbar bleibt."""
    return consent.my_document_history(db, current_user)


@router.get("/acknowledgements/{user_object_id}", response_model=list[Acknowledgement])
async def user_acknowledgements(
    user_object_id: int,
    _: UserProfile = Depends(require_employee),
    db: Session = Depends(get_db),
):
    """Bestätigungen eines Nutzers (für den Benutzer-ERP-Datensatz) – Personal-Sicht."""
    user = (
        db.query(UserProfile)
        .filter(UserProfile.object_id == user_object_id, UserProfile.is_active == True)
        .first()
    )
    if not user:
        raise HTTPException(404, detail="Benutzer nicht gefunden")
    return consent.acknowledgements_for(db, user)
