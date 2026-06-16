from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, UserProfile
from ..schemas.instance import InstanceResponse

router = APIRouter(prefix="/api/v1/erp/instances", tags=["instances"])


def _denorm(db: Session, rows: list[Instance]) -> list[InstanceResponse]:
    art_ids = {r.article_id for r in rows}
    ord_ids = {r.order_id for r in rows}
    arts = {a.id: a.name for a in db.query(Article).filter(Article.id.in_(art_ids)).all()} if art_ids else {}
    ords = {o.id: o.object_id for o in db.query(Order).filter(Order.id.in_(ord_ids)).all()} if ord_ids else {}
    out: list[InstanceResponse] = []
    for r in rows:
        resp = InstanceResponse.model_validate(r)
        resp.article_name = arts.get(r.article_id)
        resp.order_object_id = ords.get(r.order_id)
        out.append(resp)
    return out


@router.get("", response_model=list[InstanceResponse])
async def list_instances(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    rows = (
        db.query(Instance)
        .filter(Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )
    return _denorm(db, rows)


@router.get("/{object_id}", response_model=InstanceResponse)
async def get_instance(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == object_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Instanz nicht gefunden")
    return _denorm(db, [inst])[0]
