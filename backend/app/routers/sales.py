"""ERP-Endpunkte der **Verkaufs-Ebene am Artikel** (Personal): Profil, Preise, Zielgruppe.

Bewusst getrennt vom allgemeinen Artikel-PATCH (``routers/articles.py``): so bleiben
Verkaufs-Daten **immer** editierbar (auch bei status='released') – die Freigabe friert
nur Spezifikation + Prozess ein, nicht den Verkauf.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, UserProfile
from ..schemas.sales import (
    ArticlePriceCreate, ArticlePriceResponse, ArticlePriceUpdate,
    ArticleSalesProfile, ArticleSalesUpdate, AudienceAdd, AudienceMember, PriceView,
)
from ..services import sales as sales_svc

router = APIRouter(prefix="/api/v1/erp/articles", tags=["sales"])


def _get_article(db: Session, object_id: int) -> Article:
    article = db.query(Article).filter(
        Article.object_id == object_id, Article.is_active == True).first()
    if not article:
        raise HTTPException(404, detail="Artikel nicht gefunden")
    return article


def _profile(db: Session, article: Article) -> ArticleSalesProfile:
    return ArticleSalesProfile(
        object_id=article.object_id,
        status=article.status,
        sales_published=article.sales_published,
        sales_visibility=article.sales_visibility,
        sales_fulfillment=article.sales_fulfillment,
        sales_content=article.sales_content,
        prices=[ArticlePriceResponse.model_validate(p) for p in sales_svc.prices_for(db, article.id)],
        audience=[AudienceMember(**m) for m in sales_svc.audience_for(db, article.id)],
        previews=[PriceView(**v) for v in sales_svc.previews(db, article)],
    )


# ─── Profil ──────────────────────────────────────────────────────────────────────

@router.get("/{object_id}/sales", response_model=ArticleSalesProfile)
async def get_sales(object_id: int, db: Session = Depends(get_db),
                    _: UserProfile = Depends(require_employee)):
    return _profile(db, _get_article(db, object_id))


@router.patch("/{object_id}/sales", response_model=ArticleSalesProfile)
async def update_sales(object_id: int, data: ArticleSalesUpdate, db: Session = Depends(get_db),
                       user: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    sales_svc.update_profile(db, article, data, user.id)
    return _profile(db, article)


# ─── Preise ──────────────────────────────────────────────────────────────────────

@router.get("/{object_id}/sales/prices", response_model=list[ArticlePriceResponse])
async def list_prices(object_id: int, db: Session = Depends(get_db),
                      _: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    return [ArticlePriceResponse.model_validate(p) for p in sales_svc.prices_for(db, article.id)]


@router.post("/{object_id}/sales/prices", response_model=ArticlePriceResponse, status_code=201)
async def create_price(object_id: int, data: ArticlePriceCreate, db: Session = Depends(get_db),
                       user: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    return ArticlePriceResponse.model_validate(sales_svc.create_price(db, article, data, user.id))


@router.patch("/{object_id}/sales/prices/{price_id}", response_model=ArticlePriceResponse)
async def update_price(object_id: int, price_id: int, data: ArticlePriceUpdate,
                       db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    return ArticlePriceResponse.model_validate(sales_svc.update_price(db, article, price_id, data, user.id))


@router.delete("/{object_id}/sales/prices/{price_id}")
async def delete_price(object_id: int, price_id: int, db: Session = Depends(get_db),
                       user: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    sales_svc.delete_price(db, article, price_id, user.id)
    return {"deleted": True}


# ─── Zielgruppe (private/unlisted) ───────────────────────────────────────────────

@router.get("/{object_id}/sales/audience", response_model=list[AudienceMember])
async def list_audience(object_id: int, db: Session = Depends(get_db),
                        _: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    return [AudienceMember(**m) for m in sales_svc.audience_for(db, article.id)]


@router.post("/{object_id}/sales/audience", response_model=list[AudienceMember], status_code=201)
async def add_audience(object_id: int, data: AudienceAdd, db: Session = Depends(get_db),
                       user: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    sales_svc.add_audience(db, article, data.user_id, user.id)
    return [AudienceMember(**m) for m in sales_svc.audience_for(db, article.id)]


@router.delete("/{object_id}/sales/audience/{row_id}")
async def remove_audience(object_id: int, row_id: int, db: Session = Depends(get_db),
                          user: UserProfile = Depends(require_employee)):
    article = _get_article(db, object_id)
    sales_svc.remove_audience(db, article, row_id, user.id)
    return {"removed": True}
