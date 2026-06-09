from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..core.auth import require_admin, require_staff
from ..core.database import get_db
from ..models.audit import UserProfile
from ..models.objekttypen import ObjektTyp

router = APIRouter(prefix="/api/v1/admin/objekttypen", tags=["objekttypen"])


class ObjektTypCreate(BaseModel):
    name: str
    farbe: str = "blue"


class ObjektTypResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    farbe: str
    created_at: datetime


@router.get("", response_model=list[ObjektTypResponse])
async def list_objekttypen(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_staff),
):
    return (
        db.query(ObjektTyp)
        .filter(ObjektTyp.is_active == True)  # noqa: E712
        .order_by(ObjektTyp.name)
        .all()
    )


@router.post("", response_model=ObjektTypResponse, status_code=status.HTTP_201_CREATED)
async def create_objekttyp(
    data: ObjektTypCreate,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
    typ = ObjektTyp(name=name, farbe=data.farbe)
    db.add(typ)
    db.commit()
    db.refresh(typ)
    return typ


@router.delete("/{typ_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_objekttyp(
    typ_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    typ = db.get(ObjektTyp, typ_id)
    if not typ or not typ.is_active:
        raise HTTPException(status_code=404, detail="Objekttyp nicht gefunden")
    typ.is_active = False
    db.commit()
