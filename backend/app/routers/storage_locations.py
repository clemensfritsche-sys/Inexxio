from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import StorageLocation, UserProfile
from ..schemas.storage_location import (
    StorageLocationCreate,
    StorageLocationResponse,
    StorageLocationUpdate,
)
from ..services.admin import log_audit
from ..services.objects import next_object_id

router = APIRouter(prefix="/api/v1/erp/storage-locations", tags=["storage-locations"])


def _get_active(db: Session, object_id: int) -> StorageLocation:
    loc = (
        db.query(StorageLocation)
        .filter(StorageLocation.object_id == object_id, StorageLocation.is_active == True)
        .first()
    )
    if not loc:
        raise HTTPException(404, detail="Lagerplatz nicht gefunden")
    return loc


@router.get("", response_model=list[StorageLocationResponse])
async def list_storage_locations(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    locs = (
        db.query(StorageLocation)
        .filter(StorageLocation.is_active == True)
        .order_by(StorageLocation.object_id)
        .all()
    )
    return [StorageLocationResponse.model_validate(loc) for loc in locs]


@router.post("", response_model=StorageLocationResponse, status_code=201)
async def create_storage_location(
    data: StorageLocationCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    loc = StorageLocation(
        object_id=next_object_id(db),
        status="draft",
        **data.model_dump(exclude_none=True),
    )
    db.add(loc)
    db.flush()
    log_audit(db, "storage_locations", None, f"Lagerplatz '{loc.name}' angelegt",
              current_user.id, object_id=loc.object_id)
    db.commit()
    db.refresh(loc)
    return StorageLocationResponse.model_validate(loc)


@router.get("/{object_id}", response_model=StorageLocationResponse)
async def get_storage_location(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return StorageLocationResponse.model_validate(_get_active(db, object_id))


@router.patch("/{object_id}", response_model=StorageLocationResponse)
async def update_storage_location(
    object_id: int,
    data: StorageLocationUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    loc = _get_active(db, object_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        old_val = getattr(loc, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "storage_locations", key, new_str, current_user.id,
                      object_id=loc.object_id, old_value=old_str)
        setattr(loc, key, value)
    db.commit()
    db.refresh(loc)
    return StorageLocationResponse.model_validate(loc)
