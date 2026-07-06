"""Lagerplätze – API-Form stabil, aber über **Artikel + Instanz** abgebildet (F).

Ein Lagerplatz IST eine Instanz eines ``is_location``-Artikels (siehe
``services/location_records``). Pfade und Response-Form (``StorageLocationResponse``)
bleiben unverändert; ``location_type='lagerplatz'`` zeigt jetzt auf die **Instanz** des
Lagerplatzes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.instance import ObjectReference
from ..schemas.storage_location import (
    StorageLocationCreate,
    StorageLocationResponse,
    StorageLocationUpdate,
)
from ..services import location_records
from ..services.lifecycle import ensure_version
from ..services.references import storage_location_references

router = APIRouter(prefix="/api/v1/erp/storage-locations", tags=["storage-locations"])


@router.get("", response_model=list[StorageLocationResponse])
async def list_storage_locations(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return location_records.list_locations(db)


@router.post("", response_model=StorageLocationResponse, status_code=201)
async def create_storage_location(
    data: StorageLocationCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    return location_records.create(db, data, current_user.id)


@router.get("/{object_id}", response_model=StorageLocationResponse)
async def get_storage_location(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return location_records.to_response(db, location_records.get_instance(db, object_id))


@router.get("/{object_id}/references", response_model=list[ObjectReference])
async def list_storage_location_references(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Verwendung des Lagerplatzes: lagernde Instanzen + referenzierende Artikel."""
    inst = location_records.get_instance(db, object_id)
    return storage_location_references(db, inst)


@router.patch("/{object_id}", response_model=StorageLocationResponse)
async def update_storage_location(
    object_id: int,
    data: StorageLocationUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    inst = location_records.get_instance(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    ensure_version(inst, payload.pop("expected_updated_at", None))
    if payload.get("status") == "inactive" and location_records.in_use(db, inst):
        raise HTTPException(409, detail="Lagerplatz enthält noch Instanzen – bitte zuerst umlagern")
    return location_records.update(db, inst, payload, current_user.id)


@router.post("/{object_id}/replace", response_model=StorageLocationResponse)
async def replace_storage_location(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ersetzen: Duplikat als Entwurf anlegen, verknüpfen, Original inaktiv (nur wenn leer)."""
    inst = location_records.get_instance(db, object_id)
    if location_records.in_use(db, inst):
        raise HTTPException(409, detail="Lagerplatz enthält noch Instanzen – bitte zuerst umlagern")
    return location_records.replace(db, inst, current_user.id)
