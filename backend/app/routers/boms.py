from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import UserProfile
from ..models.boms import BOM, BOMLine
from ..models.objects import ObjectType, UniversalObject
from ..schemas.boms import BOMCreate, BOMResponse, BOMUpdate

router = APIRouter(prefix="/api/v1/boms", tags=["boms"])


@router.get("")
async def list_boms(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    boms = (
        db.query(BOM)
        .filter(BOM.is_active == True)
        .order_by(BOM.updated_at.desc())
        .limit(100)
        .all()
    )
    return [BOMResponse.model_validate(b) for b in boms]


@router.post("", response_model=BOMResponse, status_code=status.HTTP_201_CREATED)
async def create_bom(
    data: BOMCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = UniversalObject(
        object_type=ObjectType.BOM,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(obj)
    db.flush()

    bom = BOM(id=obj.id, parent_item_id=data.parent_item_id, note=data.note)
    db.add(bom)
    db.flush()

    for line_data in data.lines:
        line = BOMLine(bom_id=bom.id, **line_data.model_dump())
        db.add(line)

    db.commit()
    db.refresh(bom)
    return BOMResponse.model_validate(bom)


@router.get("/by-item/{item_id}", response_model=list[BOMResponse])
async def get_boms_for_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    boms = (
        db.query(BOM)
        .filter(BOM.parent_item_id == item_id, BOM.is_active == True)
        .all()
    )
    return [BOMResponse.model_validate(b) for b in boms]


@router.get("/{bom_id}", response_model=BOMResponse)
async def get_bom(
    bom_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    bom = db.query(BOM).filter(BOM.id == bom_id, BOM.is_active == True).first()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")
    return BOMResponse.model_validate(bom)


@router.patch("/{bom_id}", response_model=BOMResponse)
async def update_bom(
    bom_id: int,
    data: BOMUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    bom = db.query(BOM).filter(BOM.id == bom_id, BOM.is_active == True).first()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")

    if data.note is not None:
        bom.note = data.note

    if data.lines is not None:
        # Replace all lines
        for existing_line in bom.lines:
            db.delete(existing_line)
        db.flush()
        for line_data in data.lines:
            line = BOMLine(bom_id=bom.id, **line_data.model_dump())
            db.add(line)

    db.commit()
    db.refresh(bom)
    return BOMResponse.model_validate(bom)


@router.delete("/{bom_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_bom(
    bom_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    bom = db.query(BOM).filter(BOM.id == bom_id, BOM.is_active == True).first()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")
    bom.is_active = False
    db.commit()
