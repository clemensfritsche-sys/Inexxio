from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Claim, UserProfile
from ..schemas.claim import ClaimCreate, ClaimResponse, ClaimUpdate
from ..services.admin import log_audit
from ..services.claims import create_claim, ensure_claim_mutable, to_claim_response

router = APIRouter(prefix="/api/v1/erp/claims", tags=["claims"])


def _get_active(db: Session, object_id: int) -> Claim:
    claim = (
        db.query(Claim)
        .filter(Claim.object_id == object_id, Claim.is_active == True)
        .first()
    )
    if not claim:
        raise HTTPException(404, detail="Reklamation nicht gefunden")
    return claim


@router.get("", response_model=list[ClaimResponse])
async def list_claims(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    claims = (
        db.query(Claim)
        .filter(Claim.is_active == True)
        .order_by(Claim.object_id.desc())
        .all()
    )
    return [to_claim_response(db, c) for c in claims]


@router.post("", response_model=ClaimResponse, status_code=201)
async def create_claim_endpoint(
    data: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    claim = create_claim(db, data, current_user)
    return to_claim_response(db, claim)


@router.get("/{object_id}", response_model=ClaimResponse)
async def get_claim(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return to_claim_response(db, _get_active(db, object_id))


@router.patch("/{object_id}", response_model=ClaimResponse)
async def update_claim(
    object_id: int,
    data: ClaimUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    claim = _get_active(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    ensure_claim_mutable(claim.status, payload)
    for key, value in payload.items():
        old_val = getattr(claim, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "claims", key, new_str, current_user.id,
                      object_id=claim.object_id, old_value=old_str)
        setattr(claim, key, value)
    db.commit()
    db.refresh(claim)
    return to_claim_response(db, claim)
