from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.admin import UserProfileResponse, UserProfileUpdate
from ..services import people

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
    # Selbstbedienung auf die EIGENEN Daten – derselbe Datensatz, derselbe Schreibpfad
    # wie am ERP-Benutzer-Datensatz (inkl. Audit-Log; Akteur ist die Person selbst).
    people.apply_profile_update(db, current_user, data, current_user.id)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/terms-accept", response_model=UserProfileResponse)
async def accept_terms(
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.terms_accepted_at = datetime.now(timezone.utc)
    current_user.terms_version = "1.0"
    db.commit()
    db.refresh(current_user)
    return current_user
