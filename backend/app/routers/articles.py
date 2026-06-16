from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, PurchaseOrder, UserProfile
from ..schemas.article import ArticleCreate, ArticleResponse, ArticleUpdate
from ..schemas.instance import InstanceResponse
from ..services.admin import log_audit
from ..services.lifecycle import ensure_mutable
from ..services.objects import next_object_id

router = APIRouter(prefix="/api/v1/erp/articles", tags=["articles"])

# Bestellstatus, deren Preise als „akzeptiert" in die Stückpreis-Spanne zählen
_PRICED_STATUS = ("ordered", "received")


def _get_active(db: Session, object_id: int) -> Article:
    article = (
        db.query(Article)
        .filter(Article.object_id == object_id, Article.is_active == True)
        .first()
    )
    if not article:
        raise HTTPException(404, detail="Artikel nicht gefunden")
    return article


def _price_ranges(db: Session, article_ids: list[int]) -> dict[int, tuple]:
    """Min/Max Stückpreis (Bestellsumme ÷ Menge) je Artikel über akzeptierte Bestellungen."""
    if not article_ids:
        return {}
    per_unit = PurchaseOrder.order_total / PurchaseOrder.quantity
    rows = (
        db.query(
            PurchaseOrder.article_id,
            func.min(per_unit),
            func.max(per_unit),
        )
        .filter(
            PurchaseOrder.article_id.in_(article_ids),
            PurchaseOrder.is_active == True,
            PurchaseOrder.order_total.isnot(None),
            PurchaseOrder.quantity > 0,
            PurchaseOrder.status.in_(_PRICED_STATUS),
        )
        .group_by(PurchaseOrder.article_id)
        .all()
    )
    return {aid: (low, high) for aid, low, high in rows}


def _to_response(article: Article, price_range: tuple | None) -> ArticleResponse:
    resp = ArticleResponse.model_validate(article)
    if price_range:
        low, high = price_range
        resp.unit_cost_low = low
        resp.unit_cost_high = high
    elif article.landed_unit_cost is not None:
        resp.unit_cost_low = article.landed_unit_cost
        resp.unit_cost_high = article.landed_unit_cost
    return resp


@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    articles = (
        db.query(Article)
        .filter(Article.is_active == True)
        .order_by(Article.object_id)
        .all()
    )
    ranges = _price_ranges(db, [a.id for a in articles])
    return [_to_response(a, ranges.get(a.id)) for a in articles]


@router.post("", response_model=ArticleResponse, status_code=201)
async def create_article(
    data: ArticleCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = Article(
        object_id=next_object_id(db),
        status="draft",
        name=data.name,
        unit=data.unit,
        serialization=data.serialization,
        size=data.size,
        weight_kg=data.weight_kg,
    )
    db.add(article)
    db.flush()
    log_audit(db, "articles", None, f"Artikel '{article.name}' angelegt",
              current_user.id, object_id=article.object_id)
    db.commit()
    db.refresh(article)
    return _to_response(article, None)


@router.get("/{object_id}", response_model=ArticleResponse)
async def get_article(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    article = _get_active(db, object_id)
    return _to_response(article, _price_ranges(db, [article.id]).get(article.id))


@router.patch("/{object_id}", response_model=ArticleResponse)
async def update_article(
    object_id: int,
    data: ArticleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = _get_active(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    ensure_mutable(article.status, payload, "Artikel")
    for key, value in payload.items():
        old_val = getattr(article, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "articles", key, new_str, current_user.id,
                      object_id=article.object_id, old_value=old_str)
        setattr(article, key, value)
    db.commit()
    db.refresh(article)
    return _to_response(article, _price_ranges(db, [article.id]).get(article.id))


@router.get("/{object_id}/instances", response_model=list[InstanceResponse])
async def list_article_instances(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Bestand des Artikels: alle serialisierten Instanzen (Reiter «Bestand»)."""
    article = _get_active(db, object_id)
    rows = (
        db.query(Instance)
        .filter(Instance.article_id == article.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )
    order_ids = {r.order_id for r in rows}
    order_map = {
        o.id: o.object_id
        for o in db.query(Order).filter(Order.id.in_(order_ids)).all()
    } if order_ids else {}
    out: list[InstanceResponse] = []
    for r in rows:
        resp = InstanceResponse.model_validate(r)
        resp.order_object_id = order_map.get(r.order_id)
        resp.article_name = article.name
        out.append(resp)
    return out
