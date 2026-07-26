from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pydantic import BaseModel

from ..core.auth import require_admin, require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.admin import ErpAdminUpdate, UserProfileResponse
from ..schemas.shop import CustomerOrder
from ..services import selling as selling_svc
from ..services.admin import log_audit
from ..services.objects import next_object_ids, resolve_object_type

router = APIRouter(prefix="/api/v1/erp", tags=["erp"])


class ObjectResolution(BaseModel):
    """Auflösung einer universellen Objektnummer auf ihren Typ (für Scan/Quer-Refs)."""

    object_id: int
    object_type: str


@router.get("/objects/{object_id}", response_model=ObjectResolution)
async def resolve_object(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Typ einer Objektnummer in O(1) auflösen (zentrale Registry, Fallback Scan)."""
    otype = resolve_object_type(db, object_id)
    if not otype:
        raise HTTPException(404, detail="Objekt nicht gefunden")
    return ObjectResolution(object_id=object_id, object_type=otype)


def _assign_object_ids(db: Session) -> None:
    pending = (
        db.query(UserProfile)
        .filter(UserProfile.object_id.is_(None), UserProfile.is_active == True)
        .order_by(UserProfile.id)
        .all()
    )
    if not pending:
        return
    # Aus der gemeinsamen Sequence vergeben (atomar, über alle Objekttypen hinweg).
    ids = next_object_ids(db, len(pending), "user")
    for u, oid in zip(pending, ids):
        u.object_id = oid
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


@router.get("/records/{object_id}/orders", response_model=list[CustomerOrder])
async def get_erp_record_orders(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Bestellungen/Abos eines Benutzers (ERP-Reiter «Bestellungen»)."""
    user = db.query(UserProfile).filter(
        UserProfile.object_id == object_id, UserProfile.is_active == True
    ).first()
    if not user:
        raise HTTPException(404, detail="Record not found")
    return [CustomerOrder(**o) for o in selling_svc.list_customer_orders(db, user.id)]


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
    # System-KI-Identität (ADR 004): Rolle ist fix – der Rest (Anzeige-Daten) bleibt editierbar.
    if user.role == "ai" and data.model_dump(exclude_unset=True).get("role") not in (None, "ai"):
        raise HTTPException(409, detail="Die System-KI-Identität kann keine andere Rolle erhalten")
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
