from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_staff
from ..core.database import get_db
from ..models.audit import AuditLog, UserProfile
from ..models.items import Item
from ..models.objects import ObjectType, UniversalObject
from ..schemas.items import ItemCreate, ItemListResponse, ItemResponse, ItemUpdate

router = APIRouter(prefix="/api/v1/items", tags=["items"])


def _create_object(db: Session, user_id: int, obj_type: str) -> UniversalObject:
    obj = UniversalObject(
        object_type=obj_type, created_by=user_id, updated_by=user_id
    )
    db.add(obj)
    db.flush()
    return obj


@router.get("")
async def list_items(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_approved: Optional[bool] = Query(None),
    is_equipment: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    query = db.query(Item).filter(Item.is_active == True)
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))
    if category:
        query = query.filter(Item.category == category)
    if is_approved is not None:
        query = query.filter(Item.is_approved == is_approved)
    if is_equipment is not None:
        query = query.filter(Item.is_equipment == is_equipment)

    total = query.count()
    items = (
        query.order_by(Item.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ItemListResponse.model_validate(item) for item in items],
    }


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = _create_object(db, current_user.id, ObjectType.ITEM)
    item = Item(id=obj.id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemResponse.model_validate(item)


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    data: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        old_value = str(getattr(item, key, None))
        setattr(item, key, value)
        audit = AuditLog(
            object_id=item_id,
            table_name="items",
            field_name=key,
            old_value=old_value,
            new_value=str(value),
            user_id=current_user.id,
        )
        db.add(audit)

    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.post("/{item_id}/approve", response_model=ItemResponse)
async def approve_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.is_approved:
        raise HTTPException(status_code=400, detail="Item already approved")

    item.is_approved = True
    item.approved_by = current_user.id
    item.approved_at = datetime.now(timezone.utc)

    audit = AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="is_approved",
        old_value="false",
        new_value="true",
        user_id=current_user.id,
    )
    db.add(audit)
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.is_active = False
    db.commit()
