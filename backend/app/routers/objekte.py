from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import UserProfile
from ..models.items import Item
from ..models.objekte import Objekt, ObjektStatus
from ..models.objects import ObjectType, UniversalObject
from ..schemas.objekte import ObjektCreate, ObjektResponse, ObjektUpdate

router = APIRouter(prefix="/api/v1/objekte", tags=["objekte"])


@router.get("")
async def list_objekte(
    item_id: Optional[int] = Query(None),
    auftrag_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    typ: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    query = db.query(Objekt)
    if item_id:
        query = query.filter(Objekt.item_id == item_id)
    if auftrag_id:
        query = query.filter(Objekt.auftrag_id == auftrag_id)
    if status_filter:
        query = query.filter(Objekt.status == status_filter)
    if typ:
        query = query.filter(Objekt.typ == typ)

    total = query.count()
    objekte = (
        query.order_by(Objekt.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for o in objekte:
        resp = ObjektResponse.model_validate(o)
        results.append(resp.model_copy(update={"item_name": o.item.name if o.item else None}))

    return {"total": total, "page": page, "page_size": page_size, "items": results}


@router.post("", response_model=ObjektResponse, status_code=status.HTTP_201_CREATED)
async def create_objekt(
    data: ObjektCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    item = db.query(Item).filter(Item.id == data.item_id, Item.is_active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != "FREIGEGEBEN":
        raise HTTPException(status_code=400, detail="Objekte können nur für FREIGEGEBEN Items erstellt werden")

    if data.typ == "batch" and not data.batch_menge:
        raise HTTPException(status_code=400, detail="batch_menge ist erforderlich für Batch-Objekte")

    obj = UniversalObject(
        object_type=ObjectType.OBJEKT,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(obj)
    db.flush()

    objekt = Objekt(
        id=obj.id,
        batch_verbleibend=data.batch_menge if data.typ == "batch" else None,
        **data.model_dump(),
    )
    db.add(objekt)
    db.commit()
    db.refresh(objekt)

    resp = ObjektResponse.model_validate(objekt)
    return resp.model_copy(update={"item_name": item.name})


@router.get("/{objekt_id}", response_model=ObjektResponse)
async def get_objekt(
    objekt_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    objekt = db.query(Objekt).filter(Objekt.id == objekt_id).first()
    if not objekt:
        raise HTTPException(status_code=404, detail="Objekt not found")

    resp = ObjektResponse.model_validate(objekt)
    return resp.model_copy(update={"item_name": objekt.item.name if objekt.item else None})


@router.patch("/{objekt_id}", response_model=ObjektResponse)
async def update_objekt(
    objekt_id: int,
    data: ObjektUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    objekt = db.query(Objekt).filter(Objekt.id == objekt_id).first()
    if not objekt:
        raise HTTPException(status_code=404, detail="Objekt not found")
    if objekt.status == ObjektStatus.AUSGEMUSTERT:
        raise HTTPException(status_code=400, detail="Ausgemusterte Objekte können nicht geändert werden")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(objekt, key, value)

    db.commit()
    db.refresh(objekt)

    resp = ObjektResponse.model_validate(objekt)
    return resp.model_copy(update={"item_name": objekt.item.name if objekt.item else None})
