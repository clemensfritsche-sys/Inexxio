from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, UserProfile
from ..schemas.instance import InstanceReference, InstanceResponse
from ..services.admin import log_audit
from ..services.events import emit
from ..services.locations import location_label, physical_location_label
from ..services.references import instance_references

router = APIRouter(prefix="/api/v1/erp/instances", tags=["instances"])


class CountResponse(BaseModel):
    count: int


def _apply_search(q, search: str):
    """Server-seitige Suche: Instanz-Objektnummer, Artikelname oder Artikel-Nummer."""
    s = search.strip()
    if not s:
        return q
    like = f"%{s}%"
    return q.join(Article, Article.id == Instance.article_id, isouter=True).filter(
        or_(
            cast(Instance.object_id, String).ilike(like),
            Article.name.ilike(like),
            cast(Article.object_id, String).ilike(like),
        )
    )


def _denorm(db: Session, rows: list[Instance]) -> list[InstanceResponse]:
    art_ids = {r.article_id for r in rows}
    ord_ids = {r.order_id for r in rows}
    art_rows = db.query(Article).filter(Article.id.in_(art_ids)).all() if art_ids else []
    arts_name = {a.id: a.name for a in art_rows}
    arts_oid = {a.id: a.object_id for a in art_rows}
    resv_ids = {r.reserved_for_order_id for r in rows if r.reserved_for_order_id}
    all_ord_ids = ord_ids | resv_ids
    ords = {o.id: o.object_id for o in db.query(Order).filter(Order.id.in_(all_ord_ids)).all()} if all_ord_ids else {}
    out: list[InstanceResponse] = []
    for r in rows:
        resp = InstanceResponse.model_validate(r)
        resp.article_name = arts_name.get(r.article_id)
        resp.article_object_id = arts_oid.get(r.article_id)
        resp.order_object_id = ords.get(r.order_id)
        resp.reserved_for_order_object_id = ords.get(r.reserved_for_order_id) if r.reserved_for_order_id else None
        resp.location_label = location_label(db, r.location_type, r.location_id)
        if r.location_type == "instance":
            resp.physical_location_label = physical_location_label(db, r.location_type, r.location_id)
        out.append(resp)
    return out


@router.get("", response_model=list[InstanceResponse])
async def list_instances(
    limit: int = Query(0, ge=0, le=1000, description="0 = keine Begrenzung; sonst Seitengröße"),
    offset: int = Query(0, ge=0),
    search: str = Query("", description="Suche: Objektnummer, Artikelname oder Artikel-Nummer"),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Instanz-Feed (höchste Kardinalität) – server-seitig paginierbar
    (``limit``/``offset``, neueste zuerst) und durchsuchbar (``search``)."""
    q = _apply_search(
        db.query(Instance).filter(Instance.is_active == True), search
    ).order_by(Instance.object_id.desc())
    if limit:
        q = q.offset(offset).limit(limit)
    rows = q.all()
    return _denorm(db, rows)


@router.get("/count", response_model=CountResponse)
async def count_instances(
    search: str = Query(""),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Gesamtzahl (matchender) Instanzen – für die Feed-Zähler/Pagination."""
    q = _apply_search(db.query(Instance.id).filter(Instance.is_active == True), search)
    return CountResponse(count=int(q.count()))


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


@router.get("/{object_id}/references", response_model=list[InstanceReference])
async def list_instance_references(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Verwendungsnachweise: wo wird diese Instanz überall referenziert (neu→alt)."""
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == object_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Instanz nicht gefunden")
    return [InstanceReference(**r) for r in instance_references(db, inst)]


@router.post("/{object_id}/scrap", response_model=InstanceResponse)
async def scrap_instance(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Instanz verschrotten (manuell): ``disposition`` → ``scrapped``. Aus Bestand/FIFO
    raus, bleibt aber für die Rückverfolgung sichtbar. Verbaute Instanzen
    (``consumed``) können nicht verschrottet werden."""
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == object_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Instanz nicht gefunden")
    if inst.disposition == "consumed":
        raise HTTPException(400, detail="Verbaute Instanz kann nicht verschrottet werden")
    if inst.disposition == "scrapped":
        raise HTTPException(400, detail="Instanz ist bereits verschrottet")
    old = inst.disposition
    inst.disposition = "scrapped"
    inst.reserved_for_order_id = None
    log_audit(db, "instances", "disposition", "scrapped", current_user.id,
              object_id=inst.object_id, old_value=old)
    emit(db, "instance.scrapped", object_type="instance", object_id=inst.object_id,
         actor_id=current_user.id)
    db.commit()
    return _denorm(db, [inst])[0]
