from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, UserProfile
from ..schemas.article import ArticleCreate, ArticleResponse, ArticleUpdate
from ..services.admin import log_audit
from ..services.objects import next_object_id

router = APIRouter(prefix="/api/v1/erp/articles", tags=["articles"])


def _get_active(db: Session, object_id: int) -> Article:
    article = (
        db.query(Article)
        .filter(Article.object_id == object_id, Article.is_active == True)
        .first()
    )
    if not article:
        raise HTTPException(404, detail="Artikel nicht gefunden")
    return article


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
    return [ArticleResponse.model_validate(a) for a in articles]


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
    return ArticleResponse.model_validate(article)


@router.get("/{object_id}", response_model=ArticleResponse)
async def get_article(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return ArticleResponse.model_validate(_get_active(db, object_id))


@router.patch("/{object_id}", response_model=ArticleResponse)
async def update_article(
    object_id: int,
    data: ArticleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = _get_active(db, object_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        old_val = getattr(article, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "articles", key, new_str, current_user.id,
                      object_id=article.object_id, old_value=old_str)
        setattr(article, key, value)
    db.commit()
    db.refresh(article)
    return ArticleResponse.model_validate(article)
