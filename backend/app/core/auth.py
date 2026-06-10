from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from ..models.audit import UserProfile

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


def _no_admin_exists(db: Session) -> bool:
    return not db.query(UserProfile).filter(
        UserProfile.role == "admin", UserProfile.is_active == True
    ).first()


def _create_user(db: Session, uid: str, email: str, decoded: dict, language: str = "de") -> UserProfile:
    email_is_admin = (
        settings.initial_admin_email
        and email.lower() == settings.initial_admin_email.lower()
    )
    role = "admin" if (email_is_admin or _no_admin_exists(db)) else "customer"
    firebase_name = decoded.get("name", "").strip()
    name_parts = firebase_name.split(maxsplit=1) if firebase_name else []
    first = name_parts[0] if name_parts else None
    last = name_parts[1] if len(name_parts) > 1 else None
    user = UserProfile(
        firebase_uid=uid,
        email=email,
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


def get_current_user(
    request: Request,
    credentials_: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserProfile:
    if not credentials_:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        _init_firebase()
        decoded = firebase_auth.verify_id_token(credentials_.credentials)
        uid = decoded["uid"]
        email = decoded.get("email", "")

        user = db.query(UserProfile).filter(
            UserProfile.firebase_uid == uid, UserProfile.is_active == True
        ).first()

        if not user:
            # Firebase was reset: same email, new UID → reuse existing profile
            if email:
                user = db.query(UserProfile).filter(
                    UserProfile.email == email, UserProfile.is_active == True
                ).first()
            if user:
                user.firebase_uid = uid
                db.commit()
            else:
                return _create_user(db, uid, email, decoded, _detect_language(request))

        changed = False
        email_is_admin = (
            settings.initial_admin_email
            and email.lower() == settings.initial_admin_email.lower()
        )
        if user.role != "admin" and (email_is_admin or _no_admin_exists(db)):
            user.role = "admin"
            changed = True
        if email and user.email != email:
            collision = db.query(UserProfile).filter(
                UserProfile.email == email,
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
        if changed:
            db.commit()

        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


def require_role(*roles: str):
    def checker(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return checker


require_admin = require_role("admin")
require_employee = require_role("admin", "employee")
