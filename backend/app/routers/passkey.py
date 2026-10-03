"""Passkey-Endpunkte (WebAuthn/FIDO2) unter ``/api/v1/auth/passkeys``.

Registrierung + Verwaltung erfordern eine Anmeldung (``get_current_user``); die
eigentliche **Anmeldung** per Passkey ist naturgemäss unauthentifiziert (sie ersetzt
ja die Anmeldung) und liefert einen Firebase Custom Token zurück.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.passkey import (
    PasskeyLoginResult,
    PasskeyLoginVerify,
    PasskeyRegisterVerify,
    PasskeyResponse,
)
from ..services import passkey

router = APIRouter(prefix="/api/v1/auth/passkeys", tags=["passkeys"])


# ── Registrierung (angemeldet) ────────────────────────────────────────────────

@router.post("/register/options")
async def register_options(
    request: Request,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Registrierungs-Optionen (Challenge) für ``navigator.credentials.create``."""
    return passkey.begin_registration(db, current_user, request)


@router.post("/register/verify", response_model=PasskeyResponse)
async def register_verify(
    data: PasskeyRegisterVerify,
    request: Request,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registrierung abschliessen: Attestation prüfen und Passkey speichern."""
    return passkey.complete_registration(
        db, current_user, request, data.credential, data.device_name
    )


@router.get("", response_model=list[PasskeyResponse])
async def list_passkeys(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Die registrierten Passkeys des angemeldeten Nutzers (Verwaltung im Konto)."""
    return passkey.list_passkeys(db, current_user)


@router.delete("/{passkey_id}", status_code=204)
async def delete_passkey(
    passkey_id: int,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Einen Passkey entfernen (Soft-Delete)."""
    passkey.delete_passkey(db, current_user, passkey_id)
    return Response(status_code=204)


# ── Anmeldung (passwortlos, unauthentifiziert) ────────────────────────────────

@router.post("/login/options")
async def login_options(request: Request, db: Session = Depends(get_db)) -> dict:
    """Anmelde-Optionen (Challenge) für ``navigator.credentials.get`` – usernamelos."""
    return passkey.begin_authentication(db, request)


@router.post("/login/verify", response_model=PasskeyLoginResult)
async def login_verify(
    data: PasskeyLoginVerify,
    request: Request,
    db: Session = Depends(get_db),
):
    """Anmeldung abschliessen: Assertion prüfen → Firebase Custom Token zurückgeben."""
    token = passkey.complete_authentication(db, request, data.credential)
    return PasskeyLoginResult(firebase_token=token)
