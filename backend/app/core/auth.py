from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Depends, HTTPException, status
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


def _create_user(db: Session, uid: str, email: str, decoded: dict) -> UserProfile:
    role = (
        "admin"
        if settings.initial_admin_email and email.lower() == settings.initial_admin_email.lower()
        else "customer"
    )
    user = UserProfile(
        firebase_uid=uid,
        email=email,
        display_name=decoded.get("name") or email.split("@")[0],
        photo_url=decoded.get("picture"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
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
            return _create_user(db, uid, email, decoded)

        changed = False
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
