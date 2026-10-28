"""Anmeldung: das Firebase-ID-Token prüfen, die Person dazu finden oder anlegen.

►►► **Eine unbestätigte Adresse bekommt nichts** ◄◄◄: angelegt, übernommen (eine Person mit
dieser E-Mail), auf eine neue E-Mail umgestellt und zum Admin befördert wird nur mit
``email_verified`` im Token. Magic Link und Google bestätigen die Adresse; eine Anmeldung mit
Passkey trägt die Angaben des bestehenden Firebase-Kontos und findet die Person über die UID.
"""

from datetime import datetime, timezone
from typing import Optional

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from ..models import UserProfile
from ..services import people
from ..services.admin import log_audit
from ..services.people import STAFF_ROLES

settings = get_settings()
security = HTTPBearer(auto_error=False)
_firebase_initialized = False

#: Der Satz für jede Abweisung einer unbestätigten Adresse.
UNVERIFIED = ("Die E-Mail-Adresse «{email}» ist nicht bestätigt – bitte über den "
              "Anmeldelink per E-Mail anmelden.")


def _init_firebase() -> None:
    global _firebase_initialized
    if _firebase_initialized:
        return
    try:
        if settings.firebase_service_account_path:
            cred = credentials.Certificate(settings.firebase_service_account_path)
            firebase_admin.initialize_app(cred)
        elif settings.firebase_project_id:
            firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        else:
            firebase_admin.initialize_app()
        _firebase_initialized = True
    except ValueError:
        _firebase_initialized = True


def _verified(decoded: dict) -> bool:
    return decoded.get("email_verified") is True


def _is_initial_admin(email: str) -> bool:
    return bool(settings.initial_admin_email
                and people.normalize_email(email) == people.normalize_email(settings.initial_admin_email))


def _create_user(db: Session, uid: str, email: str, decoded: dict) -> UserProfile:
    """Eine neue Person zur bestätigten Adresse (``people.ensure``). ``user`` = darf nicht ins
    ERP; Admin wird nur ``initial_admin_email``."""
    role = "admin" if _is_initial_admin(email) else "user"
    name = (decoded.get("name") or "").strip().split(maxsplit=1)
    user = people.ensure(db, email, uid=uid, role=role,
                         first=name[0] if name else None,
                         last=name[1] if len(name) > 1 else None,
                         photo_url=decoded.get("picture"))
    db.commit()
    db.refresh(user)
    return user


def _verify_firebase_token(token: str) -> dict:
    """Das ID-Token prüfen und seine Angaben zurückgeben – wirft bei einem ungültigen."""
    _init_firebase()
    return firebase_auth.verify_id_token(token)


def _resolve_user(db: Session, uid: str, email: str, decoded: dict) -> UserProfile:
    """Die Person zu dieser Anmeldung: über die UID, sonst über die **bestätigte** E-Mail
    (eine intern angelegte Person, ein Firebase-Reset), sonst neu – ebenfalls nur bestätigt.
    Eine deaktivierte Person bekommt 403, nie ein frisches Profil (das verwaiste ihre
    Historie)."""
    user = db.query(UserProfile).filter(UserProfile.firebase_uid == uid).first()
    if user is None:
        if not email or not _verified(decoded):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail=UNVERIFIED.format(email=email or "ohne Adresse"))
        user = people.by_email(db, email)
        if user is not None and user.is_active:
            user.firebase_uid = uid
            db.commit()
    if user is None:
        return _create_user(db, uid, email, decoded)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="Dieses Konto wurde deaktiviert. Bitte an die Administration wenden.")
    return user


def _login_time(decoded: dict) -> Optional[datetime]:
    at = decoded.get("auth_time")
    return datetime.fromtimestamp(int(at), timezone.utc) if isinstance(at, (int, float)) else None


def _sync_user_profile(db: Session, user: UserProfile, email: str, decoded: dict) -> None:
    """Rolle, E-Mail, Bild, Anmeldeweg und letzte Anmeldung wie im Token – geschrieben nur bei
    einer Änderung. Befördert und umgestellt wird nur mit bestätigter Adresse."""
    changed = False
    verified = _verified(decoded)
    if user.role != "admin" and verified and _is_initial_admin(email):
        user.role = "admin"
        changed = True
    # Die Anmelde-E-Mail ändert das Konto über einen Bestätigungslink an die NEUE Adresse
    # (``verifyBeforeUpdateEmail``); hier landet sie mit dem Token – dieselbe Regel wie vor
    # dem Link (``people.email_problem``).
    email = people.normalize_email(email)
    if (verified and email and user.email != email
            and people.email_problem(db, user, email) is None):
        log_audit(db, "user_profiles", "email", email, user.id,
                  object_id=user.object_id, old_value=user.email)
        user.email = email
        changed = True
    new_photo = decoded.get("picture")
    if new_photo and user.photo_url != new_photo:
        user.photo_url = new_photo
        changed = True
    # google.com | emailLink | custom (= Passkey, ein Custom Token von uns)
    provider = (decoded.get("firebase") or {}).get("sign_in_provider")
    if provider and user.last_sign_in_provider != provider:
        user.last_sign_in_provider = provider
        changed = True
    login = _login_time(decoded)
    if login is not None and user.last_login_at != login:
        user.last_login_at = login
        changed = True
    if changed:
        db.commit()


def get_current_user(
    request: Request,
    credentials_: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserProfile:
    """Die angemeldete Person. Nur ein ungültiges Token ist 401 – ein Fehler beim Anlegen oder
    Abgleichen bleibt ein Serverfehler."""
    if not credentials_:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        decoded = _verify_firebase_token(credentials_.credentials)
    except Exception as e:
        print(f"WARNING: token verification failed: {e}", flush=True)   # nie in die Antwort
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    uid = decoded["uid"]
    email = decoded.get("email", "")
    user = _resolve_user(db, uid, email, decoded)
    _sync_user_profile(db, user, email, decoded)
    request.state.user_id = user.id     # für das Log jeder schreibenden Anfrage
    return user


def require_role(*roles: str):
    def checker(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return checker


require_admin = require_role("admin")
require_employee = require_role(*STAFF_ROLES)
