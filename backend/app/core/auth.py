
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from ..models import UserProfile

settings = get_settings()
security = HTTPBearer(auto_error=False)
_firebase_initialized = False


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


def _detect_language(request: Request) -> str:
    header = request.headers.get("accept-language", "")
    tag = header.split(",")[0].split(";")[0].split("-")[0].lower().strip()
    return tag if tag in ("de", "en") else "de"


def _create_user(db: Session, uid: str, email: str, decoded: dict, language: str = "de") -> UserProfile:
    email_is_admin = (
        settings.initial_admin_email
        and email.lower() == settings.initial_admin_email.lower()
    )
    # ``user`` = «darf nicht ins ERP» (Testnotiz #1043). Ob jemand Kunde oder Lieferant
    # ist, entscheidet der Vorgang, in dem er vorkommt – nicht eine Spalte an der Person.
    # Admin wird nur ``initial_admin_email`` – nie «wer zuerst kommt» (Cleanup 2026-10).
    role = "admin" if email_is_admin else "user"
    firebase_name = decoded.get("name", "").strip()
    name_parts = firebase_name.split(maxsplit=1) if firebase_name else []
    first = name_parts[0] if name_parts else None
    last = name_parts[1] if len(name_parts) > 1 else None
    from ..services.objects import next_object_id
    user = UserProfile(
        firebase_uid=uid,
        email=email.strip().lower(),
        object_id=next_object_id(db, "user"),
        first_name=first,
        last_name=last,
        photo_url=decoded.get("picture"),
        role=role,
        language=language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _verify_firebase_token(token: str) -> dict:
    """Verify a Firebase ID token and return its decoded claims. Raises on invalid token."""
    _init_firebase()
    return firebase_auth.verify_id_token(token)


def _resolve_user(db: Session, uid: str, email: str, decoded: dict, request: Request) -> UserProfile:
    """Load the profile for this identity, handling Firebase-UID resets, else provision one.

    **Deaktiviert = gesperrt, NICHT neu:** ein deaktivierter Benutzer (Soft-Delete) bekommt
    beim Re-Login KEIN frisches Profil mehr, sondern 403. Vorher entstand still ein neues
    Profil mit NEUER Objektnummer – sämtliche objektnummern-basierten Referenzen der alten
    Identität (Signoffs, Publikum, Kunde/Lieferant von Aufträgen) verwaisten und der
    «gelöschte» Benutzer war einfach wieder drin.

    **Setzen kann diesen Zustand nichts mehr** (Testnotiz #755): man deaktiviert keinen
    Benutzer, man wechselt seine Rolle. Die Abweisung bleibt trotzdem stehen – sie ist
    genau der Schutz gegen das stille Wiederauferstehen, und sie kostet eine Zeile."""
    from ..services.people import by_email
    user = db.query(UserProfile).filter(UserProfile.firebase_uid == uid).first()
    if user is None and email:
        # ►►► **Übernahme über die E-Mail – nur, wenn sie BESTÄTIGT ist** (CRM Schritt 1).
        # Eine intern angelegte Person (oder ein Firebase-Reset) hat schon einen Datensatz
        # mit dieser Adresse; wer sie nachweislich besitzt, ist diese Person. Ohne
        # Bestätigung bekäme jeder, der eine Adresse eintippt, fremde Historie.
        user = by_email(db, email)
        if user is not None and not decoded.get("email_verified"):
            raise HTTPException(
                status_code=403,
                detail=(f"Zu «{email}» gibt es bereits ein Konto – bitte über den "
                        f"Anmeldelink per E-Mail anmelden, damit die Adresse bestätigt ist."),
            )
        if user is not None and user.is_active:
            user.firebase_uid = uid
            db.commit()
    if user is not None:
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Dieses Konto wurde deaktiviert. Bitte an die Administration wenden.",
            )
        return user

    return _create_user(db, uid, email, decoded, _detect_language(request))


def _sync_user_profile(db: Session, user: UserProfile, email: str, decoded: dict) -> None:
    """Keep role/email/photo aligned with the identity provider. Writes only on change."""
    changed = False

    email_is_admin = bool(
        settings.initial_admin_email
        and email.lower() == settings.initial_admin_email.lower()
    )
    # Die hinterlegte Adresse ist immer Admin – sonst niemand von selbst.
    if user.role != "admin" and email_is_admin:
        user.role = "admin"
        changed = True

    email = (email or "").strip().lower()
    if email and user.email != email:
        collision = db.query(UserProfile).filter(
            func.lower(UserProfile.email) == email,
            UserProfile.id != user.id,
            UserProfile.is_active == True,
        ).first()
        if not collision:
            user.email = email
            changed = True

    new_photo = decoded.get("picture")
    if new_photo and user.photo_url != new_photo:
        user.photo_url = new_photo
        changed = True

    # Anmeldeweg mitschreiben (steht im ID-Token): google.com | password | emailLink |
    # custom (= Passkey, wir stellen dafür ein Custom Token aus).
    provider = (decoded.get("firebase") or {}).get("sign_in_provider")
    if provider and user.last_sign_in_provider != provider:
        user.last_sign_in_provider = provider
        changed = True

    if changed:
        db.commit()


def get_current_user(
    request: Request,
    credentials_: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserProfile:
    """Authenticate the request and return the matching profile.

    Token verification (read-only) is separated from profile provisioning and
    sync (writes): only an invalid token yields 401, genuine server/DB errors
    surface as 500 instead of masquerading as an auth failure.
    """
    if not credentials_:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        decoded = _verify_firebase_token(credentials_.credentials)
    except Exception as e:
        # FIX: Die rohe Exception (Firebase-Interna/Projekt-Details) gehört ins Log,
        # nicht in die unauthentifizierte 401-Antwort.
        print(f"WARNING: token verification failed: {e}", flush=True)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    uid = decoded["uid"]
    email = decoded.get("email", "")
    user = _resolve_user(db, uid, email, decoded, request)
    _sync_user_profile(db, user, email, decoded)
    return user


def get_optional_user(
    request: Request,
    credentials_: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserProfile | None:
    """Wie ``get_current_user``, aber ohne Token → ``None`` (öffentliche Endpunkte,
    die für eingeloggte Nutzer mehr zeigen, z. B. der Shop). Ein **ungültiges** Token
    liefert ebenfalls ``None`` (kein 401 – die Seite ist öffentlich)."""
    if not credentials_:
        return None
    try:
        decoded = _verify_firebase_token(credentials_.credentials)
    except Exception:
        return None
    uid = decoded["uid"]
    email = decoded.get("email", "")
    user = _resolve_user(db, uid, email, decoded, request)
    _sync_user_profile(db, user, email, decoded)
    return user


def require_role(*roles: str):
    def checker(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return checker


require_admin = require_role("admin")
require_employee = require_role("admin", "employee")
