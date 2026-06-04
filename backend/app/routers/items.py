from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import AuditLog, UserProfile
from ..models.boms import BOM, BOMLine
from ..models.item_config import ItemCategory, ItemName, ItemSurface
from ..models.items import Item, ItemSignature, ItemStatus
from ..models.objects import ObjectType, UniversalObject
from ..schemas.items import ItemCreate, ItemListResponse, ItemResponse, ItemUpdate

router = APIRouter(prefix="/api/v1/items", tags=["items"])


def _create_object(db: Session, user_id: int) -> UniversalObject:
    obj = UniversalObject(object_type=ObjectType.ITEM, created_by=user_id, updated_by=user_id)
    db.add(obj)
    db.flush()
    return obj


def _cascade_invalidate(db: Session, item_id: int, user_id: int, visited: set) -> None:
    if item_id in visited:
        return
    visited.add(item_id)

    bom_lines = db.query(BOMLine).filter(BOMLine.component_item_id == item_id).all()
    bom_ids = {line.bom_id for line in bom_lines}
    if not bom_ids:
        return

    for bom in db.query(BOM).filter(BOM.id.in_(bom_ids)).all():
        parent = db.query(Item).filter(Item.id == bom.parent_item_id, Item.is_active == True).first()
        if parent and parent.status not in (ItemStatus.UNGUELTIG, ItemStatus.ERSETZT):
            old = parent.status
            parent.status = ItemStatus.UNGUELTIG
            db.add(AuditLog(
                object_id=parent.id,
                table_name="items",
                field_name="status",
                old_value=old,
                new_value=ItemStatus.UNGUELTIG,
                user_id=user_id,
            ))
            _cascade_invalidate(db, parent.id, user_id, visited)


@router.get("")
async def list_items(
    q: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    is_sales_product: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    query = db.query(Item).filter(Item.is_active == True)
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))
    if status_filter:
        query = query.filter(Item.status == status_filter)
    if is_sales_product is not None:
        query = query.filter(Item.is_sales_product == is_sales_product)

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
        "items": [ItemListResponse.model_validate(i) for i in items],
    }


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = _create_object(db, current_user.id)
    item = Item(id=obj.id, status=ItemStatus.ENTWURF, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
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
    if item.status != ItemStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Only ENTWURF items can be edited")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        old_value = str(getattr(item, key, None))
        setattr(item, key, value)
        db.add(AuditLog(
            object_id=item_id,
            table_name="items",
            field_name=key,
            old_value=old_value,
            new_value=str(value),
            user_id=current_user.id,
        ))

    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.post("/{item_id}/submit", response_model=ItemResponse)
async def submit_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Only ENTWURF items can be submitted")

    old_status = item.status
    item.status = ItemStatus.IN_FREIGABE
    item.submitted_at = datetime.now(timezone.utc)
    item.submitted_by = current_user.id
    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="status",
        old_value=old_status,
        new_value=ItemStatus.IN_FREIGABE,
        user_id=current_user.id,
    ))
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
    if item.status != ItemStatus.IN_FREIGABE:
        raise HTTPException(status_code=400, detail="Only IN_FREIGABE items can be approved")

    item.status = ItemStatus.FREIGEGEBEN
    item.approved_at = datetime.now(timezone.utc)
    item.approved_by = current_user.id
    db.add(ItemSignature(item_id=item_id, signed_by=current_user.id))
    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="status",
        old_value=ItemStatus.IN_FREIGABE,
        new_value=ItemStatus.FREIGEGEBEN,
        user_id=current_user.id,
    ))
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.post("/{item_id}/replace", response_model=ItemResponse)
async def replace_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.FREIGEGEBEN:
        raise HTTPException(status_code=400, detail="Only FREIGEGEBEN items can be replaced")

    old_status = item.status
    item.status = ItemStatus.ERSETZT
    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="status",
        old_value=old_status,
        new_value=ItemStatus.ERSETZT,
        user_id=current_user.id,
    ))
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.post("/{item_id}/invalidate", response_model=ItemResponse)
async def invalidate_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status == ItemStatus.UNGUELTIG:
        raise HTTPException(status_code=400, detail="Item is already invalid")

    old_status = item.status
    item.status = ItemStatus.UNGUELTIG
    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="status",
        old_value=old_status,
        new_value=ItemStatus.UNGUELTIG,
        user_id=current_user.id,
    ))
    _cascade_invalidate(db, item_id, current_user.id, set())
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Only ENTWURF items can be deleted")

    item.is_active = False
    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="is_active",
        old_value="true",
        new_value="false",
        user_id=current_user.id,
    ))
    db.commit()
