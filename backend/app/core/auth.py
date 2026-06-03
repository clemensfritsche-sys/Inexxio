import json
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db

_firebase_initialized = False
bearer_scheme = HTTPBearer(auto_error=False)


def init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    try:
        key_data = json.loads(settings.firebase_service_account_key)
        if key_data and key_data.get("type") == "service_account":
            cred = credentials.Certificate(key_data)
            firebase_admin.initialize_app(cred)
        else:
            # Dev mode: no service account key – token verification still works
            # via Firebase's public keys (projectId is enough)
            firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        _firebase_initialized = True
    except Exception:
        firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        _firebase_initialized = True


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    try:
        # check_revoked=False is fine for dev; enable for production
        decoded = firebase_auth.verify_id_token(token, check_revoked=False)
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth error")

    from app.models.user import User
    result = await db.execute(select(User).where(User.firebase_uid == decoded["uid"]))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not registered",
            headers={"X-Register-Required": "true"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    return user


async def get_admin_user(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
