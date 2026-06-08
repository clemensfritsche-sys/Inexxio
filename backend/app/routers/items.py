import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import AuditLog, UserProfile
from ..models.item_config import ItemCategory, ItemName, ItemSurface
from ..models.items import Item, ItemSignature, ItemStatus
from ..models.objects import ObjectType, UniversalObject
from ..models.prozess_schritte import ProzessSchritt
from ..schemas.items import (
    InvalidateRequest, ItemCreate, ItemListResponse, ItemResponse,
    ItemSignatureResponse, ItemUpdate, SetReplacementRequest,
)
from ..schemas.prozess_schritte import (
    ProzessSchrittCreate, ProzessSchrittResponse, ProzessSchrittUpdate,
)

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

    rows = db.execute(
        text(
            "SELECT DISTINCT item_id FROM prozess_schritte "
            "WHERE is_active = true "
            "AND ressourcen @> :filter::jsonb"
        ),
        {"filter": json.dumps([{"objekt_id": item_id, "modus": "konsumieren"}])},
    ).fetchall()

    for (parent_id,) in rows:
        parent = db.query(Item).filter(Item.id == parent_id, Item.is_active == True).first()
        if parent and parent.status not in (ItemStatus.UNGUELTIG, ItemStatus.ERSETZT):
            old = parent.status
            parent.status = ItemStatus.UNGUELTIG
            db.add(AuditLog(
                object_id=parent_id,
                table_name="items",
                field_name="status",
                old_value=old,
                new_value=ItemStatus.UNGUELTIG,
                user_id=user_id,
            ))
            _cascade_invalidate(db, parent_id, user_id, visited)


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

    user_ids: set[int] = {uid for uid in [item.submitted_by, item.approved_by] if uid}
    user_ids |= {sig.signed_by for sig in item.signatures}

    obj = db.query(UniversalObject).filter(UniversalObject.id == item_id).first()
    created_by_id: int | None = obj.created_by if obj else None
    if created_by_id:
        user_ids.add(created_by_id)

    user_map: dict[int, str] = {}
    if user_ids:
        profiles = db.query(UserProfile).filter(UserProfile.id.in_(user_ids)).all()
        for p in profiles:
            parts = [p.first_name, p.last_name]
            name = " ".join(x for x in parts if x) or p.display_name or p.email
            user_map[p.id] = name

    replaced_by_name: Optional[str] = None
    replaces_item_name: Optional[str] = None
    if item.replaced_by_id:
        rep = db.query(Item).filter(Item.id == item.replaced_by_id).first()
        replaced_by_name = rep.name if rep else None
    if item.replaces_id:
        orig = db.query(Item).filter(Item.id == item.replaces_id).first()
        replaces_item_name = orig.name if orig else None

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
        "bom_weight_g": None,
        "bom_has_lines": False,
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
    """Returns all items whose process steps consume this item."""
    rows = db.execute(
        text(
            "SELECT ps.item_id, ps.position, ps.beschreibung, "
            "       i.name AS parent_name, i.status AS parent_status, "
            "       res.value->>'menge' AS menge "
            "FROM prozess_schritte ps "
            "JOIN items i ON i.id = ps.item_id "
            "JOIN jsonb_array_elements(ps.ressourcen) AS res(value) ON true "
            "WHERE ps.is_active = true "
            "  AND i.is_active = true "
            "  AND (res.value->>'objekt_id')::bigint = :item_id "
            "  AND res.value->>'modus' = 'konsumieren' "
            "ORDER BY i.name"
        ),
        {"item_id": item_id},
    ).fetchall()

    return [
        {
            "parent_item_id": r.item_id,
            "parent_item_name": r.parent_name,
            "parent_item_status": r.parent_status,
            "schritt_position": r.position,
            "schritt_beschreibung": r.beschreibung,
            "menge": r.menge,
        }
        for r in rows
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
        raise HTTPException(status_code=400, detail="Item is already inactive or replaced")

    old_status = item.status

    if data.replaced_by_id is not None:
        replacement = db.query(Item).filter(
            Item.id == data.replaced_by_id,
            Item.is_active == True,
            Item.status == ItemStatus.FREIGEGEBEN,
        ).first()
        if not replacement:
            raise HTTPException(status_code=400, detail="Replacement item not found or not FREIGEGEBEN")
        item.status = ItemStatus.ERSETZT
        item.replaced_by_id = data.replaced_by_id
        replacement.replaces_id = item_id
        db.add(AuditLog(
            object_id=item_id, table_name="items", field_name="status",
            old_value=old_status, new_value=ItemStatus.ERSETZT, user_id=current_user.id,
        ))
        db.add(AuditLog(
            object_id=item_id, table_name="items", field_name="replaced_by_id",
            old_value=None, new_value=str(data.replaced_by_id), user_id=current_user.id,
        ))
    else:
        item.status = ItemStatus.UNGUELTIG
        db.add(AuditLog(
            object_id=item_id, table_name="items", field_name="status",
            old_value=old_status, new_value=ItemStatus.UNGUELTIG, user_id=current_user.id,
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

    old_status = item.status
    item.replaced_by_id = data.replaced_by_id
    if item.status == ItemStatus.UNGUELTIG:
        item.status = ItemStatus.ERSETZT
    replacement.replaces_id = item_id

    db.add(AuditLog(
        object_id=item_id, table_name="items", field_name="replaced_by_id",
        old_value=None, new_value=str(data.replaced_by_id), user_id=current_user.id,
    ))
    if old_status != item.status:
        db.add(AuditLog(
            object_id=item_id, table_name="items", field_name="status",
            old_value=old_status, new_value=item.status, user_id=current_user.id,
        ))

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
        object_id=item_id, table_name="items", field_name="is_active",
        old_value="true", new_value="false", user_id=current_user.id,
    ))
    db.commit()


# ── Prozess-Schritte sub-resource ─────────────────────────────────────────────

@router.get("/{item_id}/prozess-schritte", response_model=list[ProzessSchrittResponse])
async def list_prozess_schritte(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    schritte = (
        db.query(ProzessSchritt)
        .filter(ProzessSchritt.item_id == item_id, ProzessSchritt.is_active == True)
        .order_by(ProzessSchritt.position)
        .all()
    )
    return [ProzessSchrittResponse.model_validate(s) for s in schritte]


@router.post(
    "/{item_id}/prozess-schritte",
    response_model=ProzessSchrittResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prozess_schritt(
    item_id: int,
    data: ProzessSchrittCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Prozessschritte können nur bei ENTWURF Items bearbeitet werden")

    schritt = ProzessSchritt(item_id=item_id, **data.model_dump())
    db.add(schritt)
    db.commit()
    db.refresh(schritt)
    return ProzessSchrittResponse.model_validate(schritt)


@router.patch(
    "/{item_id}/prozess-schritte/{schritt_id}",
    response_model=ProzessSchrittResponse,
)
async def update_prozess_schritt(
    item_id: int,
    schritt_id: int,
    data: ProzessSchrittUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Prozessschritte können nur bei ENTWURF Items bearbeitet werden")

    schritt = db.query(ProzessSchritt).filter(
        ProzessSchritt.id == schritt_id,
        ProzessSchritt.item_id == item_id,
        ProzessSchritt.is_active == True,
    ).first()
    if not schritt:
        raise HTTPException(status_code=404, detail="Prozessschritt not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(schritt, key, value)

    db.commit()
    db.refresh(schritt)
    return ProzessSchrittResponse.model_validate(schritt)


@router.delete(
    "/{item_id}/prozess-schritte/{schritt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_prozess_schritt(
    item_id: int,
    schritt_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Prozessschritte können nur bei ENTWURF Items bearbeitet werden")

    schritt = db.query(ProzessSchritt).filter(
        ProzessSchritt.id == schritt_id,
        ProzessSchritt.item_id == item_id,
        ProzessSchritt.is_active == True,
    ).first()
    if not schritt:
        raise HTTPException(status_code=404, detail="Prozessschritt not found")

    schritt.is_active = False
    db.commit()


@router.post(
    "/{item_id}/prozess-schritte/reorder",
    response_model=list[ProzessSchrittResponse],
)
async def reorder_prozess_schritte(
    item_id: int,
    order: list[int],
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    """Accepts an ordered list of step IDs, updates their positions."""
    item = db.query(Item).filter(Item.id == item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Prozessschritte können nur bei ENTWURF Items bearbeitet werden")

    schritte = {
        s.id: s
        for s in db.query(ProzessSchritt).filter(
            ProzessSchritt.item_id == item_id, ProzessSchritt.is_active == True
        ).all()
    }
    for pos, step_id in enumerate(order, start=1):
        if step_id in schritte:
            schritte[step_id].position = pos

    db.commit()
    return [
        ProzessSchrittResponse.model_validate(schritte[sid])
        for sid in order
        if sid in schritte
    ]
