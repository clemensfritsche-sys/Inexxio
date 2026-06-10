from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import require_admin, require_employee
from ..core.database import get_db
from ..models.audit import UserProfile
from ..schemas.admin import ErpAdminUpdate, UserProfileResponse
from ..services.admin import log_audit

router = APIRouter(prefix="/api/v1/erp", tags=["erp"])

_OBJ_ID_START = 100_000_001


def _assign_object_ids(db: Session) -> None:
    pending = (
        db.query(UserProfile)
        .filter(UserProfile.object_id.is_(None), UserProfile.is_active == True)
        .order_by(UserProfile.id)
        .all()
    )
    if not pending:
        return
    max_id = db.query(func.max(UserProfile.object_id)).scalar()
    next_id = max(max_id + 1 if max_id else _OBJ_ID_START, _OBJ_ID_START)
    for u in pending:
        u.object_id = next_id
        next_id += 1
    db.commit()


@router.get("/records", response_model=list[UserProfileResponse])
async def list_erp_records(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    _assign_object_ids(db)
    users = (
        db.query(UserProfile)
        .filter(UserProfile.is_active == True)
        .order_by(UserProfile.object_id)
        .all()
    )
    return [UserProfileResponse.model_validate(u) for u in users]


@router.get("/records/{object_id}", response_model=UserProfileResponse)
async def get_erp_record(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    user = db.query(UserProfile).filter(
        UserProfile.object_id == object_id, UserProfile.is_active == True
    ).first()
    if not user:
        raise HTTPException(404, detail="Record not found")
    return UserProfileResponse.model_validate(user)


@router.patch("/records/{object_id}", response_model=UserProfileResponse)
async def update_erp_record(
    object_id: int,
    data: ErpAdminUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    user = db.query(UserProfile).filter(
        UserProfile.object_id == object_id, UserProfile.is_active == True
    ).first()
    if not user:
        raise HTTPException(404, detail="Record not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        old_val = getattr(user, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "user_profiles", key, new_str, current_user.id,
                      object_id=user.object_id, old_value=old_str)
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return UserProfileResponse.model_validate(user)
