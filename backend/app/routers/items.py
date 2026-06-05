from datetime import datetime, timezone
from decimal import Decimal
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
from ..schemas.items import ItemCreate, ItemListResponse, ItemResponse, ItemSignatureResponse, ItemUpdate

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
    page_size: int = Query(20, ge=1, le=500),
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

    # Collect user IDs to resolve names
    user_ids: set[int] = {uid for uid in [item.submitted_by, item.approved_by] if uid}
    user_ids |= {sig.signed_by for sig in item.signatures}

    # Also get creator from UniversalObject
    obj = db.query(UniversalObject).filter(UniversalObject.id == item_id).first()
    created_by_id: int | None = obj.created_by if obj else None
    if created_by_id:
        user_ids.add(created_by_id)

    # Fetch user profiles and build name map
    user_map: dict[int, str] = {}
    if user_ids:
        profiles = db.query(UserProfile).filter(UserProfile.id.in_(user_ids)).all()
        for p in profiles:
            parts = [p.first_name, p.last_name]
            name = " ".join(x for x in parts if x) or p.display_name or p.email
            user_map[p.id] = name

    # Calculate BOM weight (sum of component weights × quantity, only if all have weight_g)
    bom_weight_g: Optional[Decimal] = None
    bom_has_lines: bool = False
    bom = db.query(BOM).filter(BOM.parent_item_id == item_id, BOM.is_active == True).first()
    if bom and bom.lines:
        bom_has_lines = True
        total = Decimal("0")
        all_have_weight = True
        for line in bom.lines:
            comp = db.query(Item).filter(Item.id == line.component_item_id, Item.is_active == True).first()
            if comp and comp.weight_g is not None:
                total += comp.weight_g * Decimal(str(line.quantity))
            else:
                all_have_weight = False
                break
        if all_have_weight:
            bom_weight_g = total

    # Build response with names
    resp = ItemResponse.model_validate(item)
    updated_sigs = []
    for sig in item.signatures:
        sig_resp = ItemSignatureResponse.model_validate(sig)
        updated_sigs.append(sig_resp.model_copy(update={"signed_by_name": user_map.get(sig.signed_by)}))

    return resp.model_copy(update={
        "created_by_name": user_map.get(created_by_id) if created_by_id else None,
        "submitted_by_name": user_map.get(item.submitted_by) if item.submitted_by else None,
        "approved_by_name": user_map.get(item.approved_by) if item.approved_by else None,
        "signatures": updated_sigs,
        "bom_weight_g": bom_weight_g,
        "bom_has_lines": bom_has_lines,
    })


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


@router.post("/{item_id}/recall", response_model=ItemResponse)
async def recall_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.IN_FREIGABE:
        raise HTTPException(status_code=400, detail="Only IN_FREIGABE items can be recalled")

    item.status = ItemStatus.ENTWURF
    item.submitted_at = None
    item.submitted_by = None
    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="status",
        old_value=ItemStatus.IN_FREIGABE,
        new_value=ItemStatus.ENTWURF,
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


@router.get("/{item_id}/where-used")
async def get_item_where_used(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    """Returns all assemblies (parent items) that include this item as a BOM component."""
    rows = (
        db.query(BOMLine, BOM, Item)
        .join(BOM, BOM.id == BOMLine.bom_id)
        .join(Item, Item.id == BOM.parent_item_id)
        .filter(
            BOMLine.component_item_id == item_id,
            BOM.is_active == True,
            Item.is_active == True,
        )
        .order_by(Item.name)
        .all()
    )
    return [
        {
            "bom_id": bom.id,
            "parent_item_id": item.id,
            "parent_item_name": item.name,
            "parent_item_status": item.status,
            "position": line.position,
            "quantity": str(line.quantity),
            "unit": line.unit,
        }
        for line, bom, item in rows
    ]


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
