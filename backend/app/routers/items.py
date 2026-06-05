from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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
from ..schemas.items import (
    InvalidateRequest, ItemCreate, ItemListResponse, ItemResponse,
    ItemSignatureResponse, ItemUpdate, SetReplacementRequest,
)

router = APIRouter(prefix="/api/v1/items", tags=["items"])


def _values_equal(old_val, new_val) -> bool:
    if old_val == new_val:
        return True
    if old_val is None or new_val is None:
        return False
    try:
        return Decimal(str(old_val)) == Decimal(str(new_val))
    except (InvalidOperation, TypeError):
        return str(old_val) == str(new_val)


def _create_object(db: Session, user_id: int) -> UniversalObject:
    obj = UniversalObject(object_type=ObjectType.ITEM, created_by=user_id, updated_by=user_id)
    db.add(obj)
    db.flush()
    return obj


def _get_item_weight(db: Session, item_id: int, visited: set) -> Optional[Decimal]:
    """Recursively calculate weight, following BOM hierarchy at any depth."""
    if item_id in visited:
        return None  # cycle protection
    visited.add(item_id)
    bom = db.query(BOM).filter(BOM.parent_item_id == item_id, BOM.is_active == True).first()
    if bom:
        # Use explicit query to avoid lazy-loading issues in recursive calls
        lines = db.query(BOMLine).filter(BOMLine.bom_id == bom.id).all()
        if lines:
            total = Decimal("0")
            for line in lines:
                child_weight = _get_item_weight(db, line.component_item_id, set(visited))
                if child_weight is None:
                    return None
                total += child_weight * Decimal(str(line.quantity))
            return total
    item = db.query(Item).filter(Item.id == item_id).first()
    return item.weight_g if item else None


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

    # Calculate BOM weight recursively across all BOM levels
    bom_has_lines: bool = False
    bom_weight_g: Optional[Decimal] = None
    bom = db.query(BOM).filter(BOM.parent_item_id == item_id, BOM.is_active == True).first()
    if bom:
        bom_lines = db.query(BOMLine).filter(BOMLine.bom_id == bom.id).all()
        if bom_lines:
            bom_has_lines = True
            bom_weight_g = _get_item_weight(db, item_id, set())

    # Resolve replacement item names
    replaced_by_name: Optional[str] = None
    replaces_item_name: Optional[str] = None
    if item.replaced_by_id:
        rep = db.query(Item).filter(Item.id == item.replaced_by_id).first()
        replaced_by_name = rep.name if rep else None
    if item.replaces_id:
        orig = db.query(Item).filter(Item.id == item.replaces_id).first()
        replaces_item_name = orig.name if orig else None

    # Build response with names
    resp = ItemResponse.model_validate(item)
    updated_sigs = []
    for sig in item.signatures:
        sig_resp = ItemSignatureResponse.model_validate(sig)
        updated_sigs.append(sig_resp.model_copy(update={"signed_by_name": user_map.get(sig.signed_by)}))

    # Count where-used
    where_used_count = (
        db.query(BOMLine)
        .join(BOM, BOM.id == BOMLine.bom_id)
        .join(Item, Item.id == BOM.parent_item_id)
        .filter(
            BOMLine.component_item_id == item_id,
            BOM.is_active == True,
            Item.is_active == True,
        )
        .count()
    )

    return resp.model_copy(update={
        "created_by_name": user_map.get(created_by_id) if created_by_id else None,
        "submitted_by_name": user_map.get(item.submitted_by) if item.submitted_by else None,
        "approved_by_name": user_map.get(item.approved_by) if item.approved_by else None,
        "signatures": updated_sigs,
        "bom_weight_g": bom_weight_g,
        "bom_has_lines": bom_has_lines,
        "where_used_count": where_used_count,
        "replaced_by_name": replaced_by_name,
        "replaces_item_name": replaces_item_name,
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
        old_val = getattr(item, key, None)
        setattr(item, key, value)
        if not _values_equal(old_val, value):
            db.add(AuditLog(
                object_id=item_id,
                table_name="items",
                field_name=key,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(value) if value is not None else None,
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
    if item.status not in (ItemStatus.ENTWURF, ItemStatus.IN_FREIGABE):
        raise HTTPException(status_code=400, detail="Only ENTWURF or IN_FREIGABE items can be approved")

    now = datetime.now(timezone.utc)
    old_status = item.status

    if item.status == ItemStatus.ENTWURF:
        item.submitted_at = now
        item.submitted_by = current_user.id

    item.status = ItemStatus.FREIGEGEBEN
    item.approved_at = now
    item.approved_by = current_user.id
    db.add(ItemSignature(item_id=item_id, signed_by=current_user.id))
    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="status",
        old_value=old_status,
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


@router.get("/{item_id}/history")
async def get_item_history(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.object_id == item_id, AuditLog.table_name == "items")
        .order_by(AuditLog.changed_at_utc.desc())
        .all()
    )
    user_ids = {e.user_id for e in entries if e.user_id}
    user_map: dict[int, str] = {}
    if user_ids:
        profiles = db.query(UserProfile).filter(UserProfile.id.in_(user_ids)).all()
        for p in profiles:
            parts = [p.first_name, p.last_name]
            user_map[p.id] = " ".join(x for x in parts if x) or p.display_name or p.email
    return [
        {
            "id": e.id,
            "field_name": e.field_name,
            "old_value": e.old_value,
            "new_value": e.new_value,
            "user_name": user_map.get(e.user_id) if e.user_id else None,
            "changed_at": e.changed_at_utc.isoformat(),
        }
        for e in entries
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
    data: InvalidateRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status in (ItemStatus.UNGUELTIG, ItemStatus.ERSETZT):
        raise HTTPException(status_code=400, detail="Item is already inactive")

    old_status = item.status
    item.status = ItemStatus.UNGUELTIG  # Always UNGUELTIG

    if data.replaced_by_id is not None:
        replacement = db.query(Item).filter(
            Item.id == data.replaced_by_id,
            Item.is_active == True,
            Item.status == ItemStatus.FREIGEGEBEN,
        ).first()
        if not replacement:
            raise HTTPException(status_code=400, detail="Replacement item not found or not FREIGEGEBEN")
        item.replaced_by_id = data.replaced_by_id
        replacement.replaces_id = item_id
        db.add(AuditLog(
            object_id=item_id,
            table_name="items",
            field_name="replaced_by_id",
            old_value=None,
            new_value=str(data.replaced_by_id),
            user_id=current_user.id,
        ))

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


@router.post("/{item_id}/set-replacement", response_model=ItemResponse)
async def set_replacement(
    item_id: int,
    data: SetReplacementRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status not in (ItemStatus.UNGUELTIG, ItemStatus.ERSETZT):
        raise HTTPException(status_code=400, detail="Only UNGUELTIG or ERSETZT items can have replacement added")
    if item.replaced_by_id is not None:
        raise HTTPException(status_code=400, detail="Replacement already set")

    replacement = db.query(Item).filter(
        Item.id == data.replaced_by_id,
        Item.is_active == True,
        Item.status == ItemStatus.FREIGEGEBEN,
    ).first()
    if not replacement:
        raise HTTPException(status_code=400, detail="Replacement item not found or not FREIGEGEBEN")

    item.replaced_by_id = data.replaced_by_id
    replacement.replaces_id = item_id
    # Status stays unchanged (UNGUELTIG or ERSETZT)

    db.add(AuditLog(
        object_id=item_id,
        table_name="items",
        field_name="replaced_by_id",
        old_value=None,
        new_value=str(data.replaced_by_id),
        user_id=current_user.id,
    ))

    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


@router.get("/{item_id}/history")
async def get_item_history(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.object_id == item_id, AuditLog.table_name == "items")
        .order_by(AuditLog.changed_at_utc.asc())
        .all()
    )

    user_ids = {e.user_id for e in entries if e.user_id}
    user_map: dict[int, str] = {}
    if user_ids:
        profiles = db.query(UserProfile).filter(UserProfile.id.in_(user_ids)).all()
        for p in profiles:
            parts = [p.first_name, p.last_name]
            name = " ".join(x for x in parts if x) or p.display_name or p.email
            user_map[p.id] = name

    return [
        {
            "id": e.id,
            "field_name": e.field_name,
            "old_value": e.old_value,
            "new_value": e.new_value,
            "user_name": user_map.get(e.user_id) if e.user_id else None,
            "changed_at": e.changed_at_utc.isoformat() if e.changed_at_utc else None,
        }
        for e in entries
    ]


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
