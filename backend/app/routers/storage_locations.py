from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import StorageLocation, UserProfile
from ..schemas.instance import InstanceReference
from ..schemas.storage_location import (
    StorageLocationCreate,
    StorageLocationResponse,
    StorageLocationUpdate,
)
from ..services import deactivation
from ..services.admin import log_audit
from ..services.lifecycle import ensure_mutable
from ..services.objects import next_object_id
from ..services.references import storage_location_references

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


def _to_resp(db: Session, loc: StorageLocation) -> StorageLocationResponse:
    resp = StorageLocationResponse.model_validate(loc)
    if loc.object_id:
        pred = (
            db.query(StorageLocation.object_id)
            .filter(StorageLocation.replaced_by_id == loc.object_id)
            .first()
        )
        resp.replaces_id = pred[0] if pred else None
    return resp


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
    return [_to_resp(db, loc) for loc in locs]


@router.post("", response_model=StorageLocationResponse, status_code=201)
async def create_storage_location(
    data: StorageLocationCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    loc = StorageLocation(
        object_id=next_object_id(db),
        status="draft",
        name="Lagerplatz",
        **data.model_dump(exclude_none=True),
    )
    db.add(loc)
    db.flush()
    log_audit(db, "storage_locations", None, "Lagerplatz angelegt",
              current_user.id, object_id=loc.object_id)
    db.commit()
    db.refresh(loc)
    return _to_resp(db, loc)


@router.get("/{object_id}", response_model=StorageLocationResponse)
async def get_storage_location(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _to_resp(db, _get_active(db, object_id))


@router.get("/{object_id}/references", response_model=list[InstanceReference])
async def list_storage_location_references(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Verwendung des Lagerplatzes: lagernde Instanzen + referenzierende Artikel."""
    loc = _get_active(db, object_id)
    return storage_location_references(db, loc)


@router.patch("/{object_id}", response_model=StorageLocationResponse)
async def update_storage_location(
    object_id: int,
    data: StorageLocationUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    loc = _get_active(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    ensure_mutable(loc.status, payload, "Lagerplatz")
    # Inaktiv nur, wenn leer (keine lagernden Instanzen) – sonst zuerst umlagern.
    if payload.get("status") == "inactive" and loc.status != "inactive" and deactivation.storage_location_in_use(db, loc):
        raise HTTPException(409, detail="Lagerplatz enthält noch Instanzen – bitte zuerst umlagern")
    for key, value in payload.items():
        old_val = getattr(loc, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "storage_locations", key, new_str, current_user.id,
                      object_id=loc.object_id, old_value=old_str)
        setattr(loc, key, value)
    db.commit()
    db.refresh(loc)
    return _to_resp(db, loc)


@router.post("/{object_id}/replace", response_model=StorageLocationResponse)
async def replace_storage_location(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ersetzen: Duplikat als Entwurf anlegen, verknüpfen, Original inaktiv setzen
    (nur wenn leer). Liefert den **neuen** Lagerplatz zurück."""
    loc = _get_active(db, object_id)
    if loc.status == "inactive":
        raise HTTPException(400, detail="Lagerplatz ist bereits inaktiv")
    if deactivation.storage_location_in_use(db, loc):
        raise HTTPException(409, detail="Lagerplatz enthält noch Instanzen – bitte zuerst umlagern")
    new = deactivation.duplicate_storage_location(db, loc, current_user.id)
    log_audit(db, "storage_locations", "replaced_by_id", str(new.object_id),
              current_user.id, object_id=loc.object_id)
    loc.replaced_by_id = new.object_id
    loc.status = "inactive"
    db.commit()
    db.refresh(new)
    return _to_resp(db, new)
