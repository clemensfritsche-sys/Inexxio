from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import UserProfile
from ..models.auftraege import Auftrag, AuftragStatus
from ..models.items import Item
from ..models.objects import ObjectType, UniversalObject
from ..schemas.auftraege import AuftragCreate, AuftragListResponse, AuftragResponse, AuftragUpdate

router = APIRouter(prefix="/api/v1/auftraege", tags=["auftraege"])


@router.get("")
async def list_auftraege(
    q: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    item_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    query = db.query(Auftrag).join(Item, Item.id == Auftrag.item_id)
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))
    if status_filter:
        query = query.filter(Auftrag.status == status_filter)
    if item_id:
        query = query.filter(Auftrag.item_id == item_id)

    total = query.count()
    auftraege = (
        query.order_by(Auftrag.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for a in auftraege:
        resp = AuftragListResponse.model_validate(a)
        results.append(resp.model_copy(update={"item_name": a.item.name if a.item else None}))

    return {"total": total, "page": page, "page_size": page_size, "items": results}


@router.post("", response_model=AuftragResponse, status_code=status.HTTP_201_CREATED)
async def create_auftrag(
    data: AuftragCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == data.item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    obj = UniversalObject(
        object_type=ObjectType.AUFTRAG,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(obj)
    db.flush()

    auftrag = Auftrag(
        id=obj.id,
        created_by=current_user.id,
        **data.model_dump(),
    )
    db.add(auftrag)
    db.commit()
    db.refresh(auftrag)

    resp = AuftragResponse.model_validate(auftrag)
    return resp.model_copy(update={"item_name": item.name})


@router.get("/{auftrag_id}", response_model=AuftragResponse)
async def get_auftrag(
    auftrag_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    auftrag = db.query(Auftrag).filter(Auftrag.id == auftrag_id).first()
    if not auftrag:
        raise HTTPException(status_code=404, detail="Auftrag not found")

    resp = AuftragResponse.model_validate(auftrag)
    return resp.model_copy(update={"item_name": auftrag.item.name if auftrag.item else None})


@router.patch("/{auftrag_id}", response_model=AuftragResponse)
async def update_auftrag(
    auftrag_id: int,
    data: AuftragUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    auftrag = db.query(Auftrag).filter(Auftrag.id == auftrag_id).first()
    if not auftrag:
        raise HTTPException(status_code=404, detail="Auftrag not found")
    if auftrag.status == AuftragStatus.ABGESCHLOSSEN:
        raise HTTPException(status_code=400, detail="Abgeschlossene Aufträge können nicht geändert werden")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(auftrag, key, value)

    db.commit()
    db.refresh(auftrag)

    resp = AuftragResponse.model_validate(auftrag)
    return resp.model_copy(update={"item_name": auftrag.item.name if auftrag.item else None})


@router.delete("/{auftrag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auftrag(
    auftrag_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    auftrag = db.query(Auftrag).filter(Auftrag.id == auftrag_id).first()
    if not auftrag:
        raise HTTPException(status_code=404, detail="Auftrag not found")
    if auftrag.status not in (AuftragStatus.OFFEN, AuftragStatus.ABGEBROCHEN):
        raise HTTPException(status_code=400, detail="Nur offene oder abgebrochene Aufträge können gelöscht werden")

    db.delete(auftrag)
    db.commit()
