from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models.audit import UserProfile
from ..schemas.admin import UserProfileResponse, UserProfileUpdate

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: UserProfile = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
async def update_me(
    data: UserProfileUpdate,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/terms-accept")
async def accept_terms(
    version: str,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.terms_accepted_at = datetime.now(timezone.utc)
    current_user.terms_version = version
    db.commit()
    return {"accepted": True, "version": version}


@router.post("/logout")
async def logout(current_user: UserProfile = Depends(get_current_user)):
    """Signal logout — Firebase token revocation happens client-side."""
    return {"logged_out": True}
