"""Passkey / WebAuthn-Zeremonien + Firebase-Custom-Token-Brücke.

Firebase Authentication kennt keinen nativen Passkey-Provider. Wir führen die FIDO2/
WebAuthn-Zeremonie darum selbst im Backend (``py_webauthn``) und stellen bei Erfolg
einen Firebase **Custom Token** aus. Das Frontend meldet sich damit via
``signInWithCustomToken`` an – ab da ist es eine ganz normale Firebase-Session
(ID-Token → ``get_current_user``). So bleibt der gesamte übrige Auth-Fluss unberührt.

RP-ID (Domain-Bindung des Passkeys) und erwartete Origin werden pro Request aus dem
``Origin``-Header abgeleitet und gegen die erlaubten Origins geprüft – dasselbe
Deployment läuft damit auf localhost, inexxio-dev.web.app und inexxio-prod.web.app.

Custom-Token-Signierung (Deployment-Hinweis): Läuft das Backend ohne Service-Account-
Key (nur ADC, z. B. Cloud Run), muss der Laufzeit-Service-Account die Rolle
``roles/iam.serviceAccountTokenCreator`` auf sich selbst besitzen, sonst kann das
Admin SDK den Token nicht signieren (siehe ``docs/passkeys.md``).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..core.auth import _init_firebase
from ..core.config import get_settings
from ..models import UserProfile, WebAuthnChallenge, WebAuthnCredential

settings = get_settings()

CHALLENGE_TTL = timedelta(minutes=5)


# ── RP / Origin ───────────────────────────────────────────────────────────────

def _allowed_origins() -> set[str]:
    origins = set(settings.cors_origins) | set(settings.webauthn_extra_origins)
    return {o.rstrip("/") for o in origins if o}


def _resolve_rp(request: Request) -> tuple[str, str]:
    """(rp_id, origin) aus dem Origin-Header ableiten und gegen die Allowlist prüfen."""
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin or origin not in _allowed_origins():
        raise HTTPException(400, detail="Diese Domain ist für Passkeys nicht freigegeben.")
    host = urlparse(origin).hostname or ""
    rp_id = settings.webauthn_rp_id or host
    if not rp_id:
        raise HTTPException(400, detail="Passkey-Domain konnte nicht bestimmt werden.")
    return rp_id, origin


# ── Challenge-Handling (Einmalgebrauch, mit Ablauf) ───────────────────────────

def _issue_challenge(db: Session, purpose: str, user_id: int | None) -> bytes:
    _purge_expired(db)
    challenge = secrets.token_bytes(32)
    db.add(WebAuthnChallenge(
        challenge=bytes_to_base64url(challenge),
        purpose=purpose,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + CHALLENGE_TTL,
    ))
    db.commit()
    return challenge


def _consume_challenge(db: Session, credential: dict, purpose: str) -> bytes:
    """Challenge aus der signierten ``clientDataJSON`` lesen, in der DB nachschlagen
    (muss von uns ausgestellt, passend, nicht abgelaufen sein) und einmalig löschen."""
    try:
        client_data_b64 = credential["response"]["clientDataJSON"]
        client_data = json.loads(base64url_to_bytes(client_data_b64))
        challenge_b64 = client_data["challenge"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, detail="Ungültige Passkey-Antwort.")

    row = (
        db.query(WebAuthnChallenge)
        .filter(WebAuthnChallenge.challenge == challenge_b64, WebAuthnChallenge.purpose == purpose)
        .first()
    )
    if not row:
        raise HTTPException(400, detail="Passkey-Anfrage abgelaufen oder ungültig. Bitte erneut versuchen.")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    expired = expires < datetime.now(timezone.utc)
    db.delete(row)
    db.commit()
    if expired:
        raise HTTPException(400, detail="Passkey-Anfrage abgelaufen. Bitte erneut versuchen.")
    return base64url_to_bytes(challenge_b64)


def _purge_expired(db: Session) -> None:
    db.query(WebAuthnChallenge).filter(
        WebAuthnChallenge.expires_at < datetime.now(timezone.utc)
    ).delete(synchronize_session=False)
    db.commit()


# ── Registrierung (Nutzer ist angemeldet, fügt einen Passkey hinzu) ───────────

def begin_registration(db: Session, user: UserProfile, request: Request) -> dict:
    rp_id, _ = _resolve_rp(request)
    existing = (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.user_id == user.id, WebAuthnCredential.is_active == True)
        .all()
    )
    exclude = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
        for c in existing
    ]
    challenge = _issue_challenge(db, "register", user.id)
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=settings.webauthn_rp_name,
        user_name=user.email,
        user_id=str(user.id).encode("utf-8"),
        user_display_name=user.display_name,
        challenge=challenge,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    return json.loads(options_to_json(options))


def complete_registration(
    db: Session, user: UserProfile, request: Request, credential: dict, device_name: str | None
) -> WebAuthnCredential:
    rp_id, origin = _resolve_rp(request)
    challenge = _consume_challenge(db, credential, "register")
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
        )
    except Exception as e:
        print(f"WARNING: passkey registration verify failed: {e}", flush=True)
        raise HTTPException(400, detail="Passkey konnte nicht verifiziert werden.")

    credential_id = bytes_to_base64url(verified.credential_id)
    if db.query(WebAuthnCredential).filter(
        WebAuthnCredential.credential_id == credential_id
    ).first():
        raise HTTPException(409, detail="Dieser Passkey ist bereits registriert.")

    transports = (credential.get("response") or {}).get("transports")
    dev_type = verified.credential_device_type
    device_type = getattr(dev_type, "value", None) or (str(dev_type) if dev_type else None)
    # Name ist optional – ohne Eingabe automatisch vergeben (durchnummeriert), damit der
    # Nutzer beim Hinzufügen nichts eintippen muss.
    name = (device_name or "").strip()[:80]
    if not name:
        n = db.query(WebAuthnCredential).filter(
            WebAuthnCredential.user_id == user.id, WebAuthnCredential.is_active == True).count()
        name = f"Passkey {n + 1}"
    row = WebAuthnCredential(
        user_id=user.id,
        credential_id=credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        rp_id=rp_id,
        transports=transports if isinstance(transports, list) else None,
        device_name=name,
        device_type=device_type,
        backed_up=bool(verified.credential_backed_up),
        last_used_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── Anmeldung (passwortlos, usernamelos über discoverable credentials) ────────

def begin_authentication(db: Session, request: Request) -> dict:
    rp_id, _ = _resolve_rp(request)
    challenge = _issue_challenge(db, "authenticate", None)
    options = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return json.loads(options_to_json(options))


def complete_authentication(db: Session, request: Request, credential: dict) -> str:
    """Assertion prüfen, passenden Nutzer ermitteln, Firebase Custom Token ausstellen."""
    rp_id, origin = _resolve_rp(request)

    raw_id = credential.get("id") or credential.get("rawId")
    if not raw_id:
        raise HTTPException(400, detail="Ungültige Passkey-Antwort.")
    row = (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.credential_id == raw_id, WebAuthnCredential.is_active == True)
        .first()
    )
    if not row:
        raise HTTPException(404, detail="Passkey nicht bekannt. Bitte melden Sie sich anders an.")

    challenge = _consume_challenge(db, credential, "authenticate")
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=row.public_key,
            credential_current_sign_count=row.sign_count,
        )
    except Exception as e:
        print(f"WARNING: passkey authentication verify failed: {e}", flush=True)
        raise HTTPException(401, detail="Passkey konnte nicht verifiziert werden.")

    user = (
        db.query(UserProfile)
        .filter(UserProfile.id == row.user_id, UserProfile.is_active == True)
        .first()
    )
    if not user:
        raise HTTPException(403, detail="Konto nicht aktiv.")

    now = datetime.now(timezone.utc)
    row.sign_count = verified.new_sign_count
    row.last_used_at = now
    user.last_login_at = now
    db.commit()

    return mint_firebase_token(user)


# ── Firebase Custom Token ─────────────────────────────────────────────────────

def mint_firebase_token(user: UserProfile) -> str:
    from firebase_admin import auth as firebase_auth

    _init_firebase()
    try:
        token = firebase_auth.create_custom_token(user.firebase_uid)
    except Exception as e:
        print(f"ERROR: Firebase custom token creation failed: {e}", flush=True)
        raise HTTPException(
            500,
            detail=(
                "Anmelde-Token konnte nicht ausgestellt werden. Dem Cloud-Run-Service-"
                "Account fehlt vermutlich die Rolle 'Service Account Token Creator'."
            ),
        )
    return token.decode("utf-8") if isinstance(token, bytes) else token


# ── Verwaltung ────────────────────────────────────────────────────────────────

def list_passkeys(db: Session, user: UserProfile) -> list[WebAuthnCredential]:
    return (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.user_id == user.id, WebAuthnCredential.is_active == True)
        .order_by(WebAuthnCredential.created_at.desc())
        .all()
    )


def delete_passkey(db: Session, user: UserProfile, passkey_id: int) -> None:
    row = (
        db.query(WebAuthnCredential)
        .filter(
            WebAuthnCredential.id == passkey_id,
            WebAuthnCredential.user_id == user.id,
            WebAuthnCredential.is_active == True,
        )
        .first()
    )
    if not row:
        raise HTTPException(404, detail="Passkey nicht gefunden.")
    row.is_active = False
    db.commit()
