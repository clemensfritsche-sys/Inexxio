"""Instanzen und Einzelinstanzen – **lesen**.

Die Instanz ist ein Ordner mit einer Objektnummer; gearbeitet wird an der Einzelinstanz.
Alles, was hier eine Menge nennt, hat sie gezählt – gespeichert ist sie nirgends.

**Es gibt keinen Schreib-Endpunkt mehr.** Eine Einzelinstanz entsteht ausschliesslich
mit ihrer Instanz, und die ausschliesslich mit einem Auftrag (Testnotiz #678); und
gelöscht wird sie nie – ihre Nummer ist eine Identität, keine Position (#679). Die
früheren drei Wege daneben (Instanz anlegen, Einzelinstanz nachschieben, Einzelinstanz
deaktivieren) waren Türen, durch die Material ohne Auftrag, ohne Prozess und ohne
Ereignis in die Welt kam und wieder verschwand.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, InstanceUnit, UserProfile
from ..schemas.instance import InstanceResponse, InstanceSummary, InstanceUnitResponse
from ..services import instances as inst_svc

router = APIRouter(prefix="/api/v1/erp/instances", tags=["instances"])


def _article(db: Session, instance: Instance) -> Article | None:
    return db.query(Article).filter(Article.id == instance.article_id).first()


def _unit_out(instance: Instance, unit: InstanceUnit) -> InstanceUnitResponse:
    return InstanceUnitResponse(
        id=unit.id,
        suffix=unit.suffix,
        number=inst_svc.unit_number(instance, unit),
        status=unit.status,
        created_at=unit.created_at,
    )


def _detail(db: Session, instance: Instance) -> InstanceResponse:
    article = _article(db, instance)
    units = inst_svc.units_of(db, instance)
    return InstanceResponse(
        id=instance.id,
        object_id=instance.object_id,
        article_id=instance.article_id,
        article_object_id=article.object_id if article else None,
        article_name=article.name if article else None,
        kind=instance.kind,
        label=instance.label,
        quantity=len(units),
        units=[_unit_out(instance, u) for u in units],
        created_at=instance.created_at,
        updated_at=instance.updated_at,
        is_active=instance.is_active,
    )


def _get(db: Session, object_id: int) -> Instance:
    instance = db.query(Instance).filter(Instance.object_id == object_id).first()
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Instanz {object_id} nicht gefunden.")
    return instance


@router.get("", response_model=list[InstanceSummary])
def list_instances(
    search: str | None = Query(None),
    article_object_id: int | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    q = db.query(Instance).filter(Instance.is_active.is_(True))
    if article_object_id is not None:
        article = db.query(Article).filter(Article.object_id == article_object_id).first()
        if article is None:
            raise HTTPException(status_code=404, detail=f"Artikel {article_object_id} nicht gefunden.")
        q = q.filter(Instance.article_id == article.id)
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.join(Article, Article.id == Instance.article_id, isouter=True).filter(
            or_(cast(Instance.object_id, String).ilike(like), Article.name.ilike(like))
        )
    rows = q.order_by(Instance.object_id.desc()).limit(limit).offset(offset).all()

    counts = inst_svc.quantities(db, [i.id for i in rows])
    names = {
        a.id: a.name
        for a in db.query(Article).filter(Article.id.in_([i.article_id for i in rows])).all()
    } if rows else {}
    return [
        InstanceSummary(
            id=i.id, object_id=i.object_id, article_id=i.article_id,
            article_name=names.get(i.article_id), kind=i.kind,
            label=i.label, quantity=counts.get(i.id, 0),
            created_at=i.created_at, updated_at=i.updated_at, is_active=i.is_active,
        )
        for i in rows
    ]


@router.get("/{object_id}", response_model=InstanceResponse)
def get_instance(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _detail(db, _get(db, object_id))
