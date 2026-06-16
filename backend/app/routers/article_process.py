from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, ArticleProcessStep, UserProfile
from ..schemas.article_process_step import (
    ArticleProcessStepCreate,
    ArticleProcessStepResponse,
    ArticleProcessStepUpdate,
)
from ..services.admin import log_audit
from ..services.lifecycle import ensure_article_draft

router = APIRouter(prefix="/api/v1/erp/articles", tags=["article-process"])


def _get_article(db: Session, object_id: int) -> Article:
    article = (
        db.query(Article)
        .filter(Article.object_id == object_id, Article.is_active == True)
        .first()
    )
    if not article:
        raise HTTPException(404, detail="Artikel nicht gefunden")
    return article


def _supplier_name(db: Session, supplier_id: int | None) -> str | None:
    if not supplier_id:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == supplier_id).first()
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def _to_response(db: Session, step: ArticleProcessStep) -> ArticleProcessStepResponse:
    resp = ArticleProcessStepResponse.model_validate(step)
    resp.supplier_name = _supplier_name(db, step.supplier_id)
    return resp


def _validate_supplier(db: Session, supplier_id: int | None) -> None:
    if supplier_id is None:
        return
    u = db.query(UserProfile).filter(
        UserProfile.id == supplier_id, UserProfile.is_active == True
    ).first()
    if not u or u.role != "supplier":
        raise HTTPException(400, detail="Gewählter Benutzer ist kein aktiver Lieferant")


@router.get("/{object_id}/process-steps", response_model=list[ArticleProcessStepResponse])
async def list_steps(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    article = _get_article(db, object_id)
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article.id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position)
        .all()
    )
    return [_to_response(db, s) for s in steps]


@router.post("/{object_id}/process-steps", response_model=ArticleProcessStepResponse, status_code=201)
async def create_step(
    object_id: int,
    data: ArticleProcessStepCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = _get_article(db, object_id)
    ensure_article_draft(article)
    _validate_supplier(db, data.supplier_id)
    count = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article.id, ArticleProcessStep.is_active == True)
        .count()
    )
    step = ArticleProcessStep(
        article_id=article.id,
        position=count + 1,
        step_type=data.step_type,
        mode=data.mode,
        supplier_id=data.supplier_id if data.mode == "supplier" else None,
        webshop_url=data.webshop_url if data.mode == "webshop" else None,
        shared_fields=data.shared_fields,
    )
    db.add(step)
    db.flush()
    log_audit(db, "article_process_steps", None, f"Prozessschritt '{data.step_type}' hinzugefügt",
              current_user.id, object_id=article.object_id)
    db.commit()
    db.refresh(step)
    return _to_response(db, step)


def _get_step(db: Session, article: Article, step_id: int) -> ArticleProcessStep:
    step = (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.id == step_id,
            ArticleProcessStep.article_id == article.id,
            ArticleProcessStep.is_active == True,
        )
        .first()
    )
    if not step:
        raise HTTPException(404, detail="Prozessschritt nicht gefunden")
    return step


@router.patch("/{object_id}/process-steps/{step_id}", response_model=ArticleProcessStepResponse)
async def update_step(
    object_id: int,
    step_id: int,
    data: ArticleProcessStepUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = _get_article(db, object_id)
    ensure_article_draft(article)
    step = _get_step(db, article, step_id)
    payload = data.model_dump(exclude_unset=True)
    if "supplier_id" in payload:
        _validate_supplier(db, payload["supplier_id"])
    for key, value in payload.items():
        setattr(step, key, value)
    # Konsistenz: nur das zum Modus passende Bezugsfeld behalten
    if step.mode == "supplier":
        step.webshop_url = None
    elif step.mode == "webshop":
        step.supplier_id = None
    log_audit(db, "article_process_steps", "update", str(payload), current_user.id,
              object_id=article.object_id)
    db.commit()
    db.refresh(step)
    return _to_response(db, step)


@router.delete("/{object_id}/process-steps/{step_id}")
async def delete_step(
    object_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = _get_article(db, object_id)
    ensure_article_draft(article)
    step = _get_step(db, article, step_id)
    step.is_active = False
    log_audit(db, "article_process_steps", "is_active", "false", current_user.id,
              object_id=article.object_id, old_value="true")
    db.commit()
    return {"deleted": True}
