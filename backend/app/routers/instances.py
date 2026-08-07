"""Instanzen und Einzelinstanzen.

Die Instanz ist ein Ordner mit einer Objektnummer; gearbeitet wird an der Einzelinstanz.
Alles, was hier eine Menge nennt, hat sie gezählt – gespeichert ist sie nirgends.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, InstanceUnit, UserProfile
from ..schemas.instance import (
    InstanceCreate,
    InstanceResponse,
    InstanceSummary,
    InstanceUnitResponse,
    InstanceUnitsAdd,
)
from ..services import instances as inst_svc
from ..services.admin import log_audit

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
        # Abgeleitet, nicht gespeichert – eine Gruppe ist im Prozess, solange eines
        # ihrer Stücke es ist (``services/instances.status_of``).
        status=inst_svc.status_of(units),
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
    states = inst_svc.statuses(db, [i.id for i in rows])
    names = {
        a.id: a.name
        for a in db.query(Article).filter(Article.id.in_([i.article_id for i in rows])).all()
    } if rows else {}
    return [
        InstanceSummary(
            id=i.id, object_id=i.object_id, article_id=i.article_id,
            article_name=names.get(i.article_id), kind=i.kind,
            status=states[i.id],
            label=i.label, quantity=counts.get(i.id, 0),
            created_at=i.created_at, updated_at=i.updated_at, is_active=i.is_active,
        )
        for i in rows
    ]


@router.post("", response_model=InstanceResponse, status_code=201)
def create_instance(
    data: InstanceCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    article = db.query(Article).filter(Article.object_id == data.article_object_id).first()
    if article is None:
        raise HTTPException(
            status_code=404, detail=f"Artikel {data.article_object_id} nicht gefunden.")

    instance = inst_svc.create_instance(
        db, article=article, kind=data.kind, count=data.count, label=data.label)
    log_audit(db, "instances", "create", f"{data.kind}, {data.count} Einzelinstanzen",
              user_id=user.id, object_id=instance.object_id)
    db.commit()
    db.refresh(instance)
    return _detail(db, instance)


@router.get("/{object_id}", response_model=InstanceResponse)
def get_instance(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _detail(db, _get(db, object_id))


@router.post("/{object_id}/units", response_model=InstanceResponse, status_code=201)
def add_units(
    object_id: int,
    data: InstanceUnitsAdd,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    instance = _get(db, object_id)
    created = inst_svc.add_units(db, instance, data.count)
    log_audit(db, "instances", "add_units",
              f"+{data.count} (Suffix {created[0].suffix}–{created[-1].suffix})",
              user_id=user.id, object_id=instance.object_id)
    db.commit()
    db.refresh(instance)
    return _detail(db, instance)


@router.delete("/{object_id}/units/{suffix}", response_model=InstanceResponse)
def deactivate_unit(
    object_id: int,
    suffix: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Einzelinstanz deaktivieren (soft). Ihre Nummer bleibt vergeben – sie kommt nie zurück."""
    instance = _get(db, object_id)
    unit = (
        db.query(InstanceUnit)
        .filter(InstanceUnit.instance_id == instance.id, InstanceUnit.suffix == suffix)
        .first()
    )
    if unit is None:
        raise HTTPException(
            status_code=404,
            detail=f"Einzelinstanz {inst_svc.obj_nr(instance.object_id)}-{suffix} nicht gefunden.",
        )
    if not unit.is_active:
        raise HTTPException(status_code=409, detail="Diese Einzelinstanz ist bereits deaktiviert.")
    unit.is_active = False
    log_audit(db, "instance_units", "deactivate", "inaktiv",
              user_id=user.id, object_id=instance.object_id, old_value="aktiv")
    db.commit()
    db.refresh(instance)
    return _detail(db, instance)
