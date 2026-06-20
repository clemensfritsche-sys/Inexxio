from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, ArticleProcessStep, UserProfile
from ..schemas.article_process_step import (
    ArticleProcessStepCreate,
    ArticleProcessStepResponse,
    ArticleProcessStepUpdate,
    ResourceLineView,
    StepReorder,
    normalize_capture_fields,
)
from ..services.admin import log_audit
from ..services.lifecycle import ensure_article_draft
from ..services.process_steps import sync_locked_movements

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


def _resource_line_views(db: Session, raw_lines: list | None) -> list[ResourceLineView]:
    out: list[ResourceLineView] = []
    for line in raw_lines or []:
        art = db.query(Article).filter(Article.id == line["article_id"]).first()
        out.append(ResourceLineView(
            article_id=line["article_id"], quantity=line.get("quantity", 1),
            mode=line.get("mode", "consume"),
            article_name=art.name if art else None,
            article_object_id=art.object_id if art else None,
            unit=art.unit if art else None,
            serialization=art.serialization if art else None,
        ))
    return out


def _to_response(db: Session, step: ArticleProcessStep) -> ArticleProcessStepResponse:
    resp = ArticleProcessStepResponse.model_validate(step)
    resp.supplier_name = _supplier_name(db, step.supplier_id)
    resp.resource_lines = _resource_line_views(db, step.resource_lines)
    return resp


def _validate_supplier(db: Session, supplier_id: int | None) -> None:
    if supplier_id is None:
        return
    u = db.query(UserProfile).filter(
        UserProfile.id == supplier_id, UserProfile.is_active == True
    ).first()
    if not u or u.role != "supplier":
        raise HTTPException(400, detail="Gewählter Benutzer ist kein aktiver Lieferant")


def _validate_resource_lines(db: Session, raw_lines: list | None) -> None:
    """Nur freigegebene, existierende Artikel sind als Ressource referenzierbar."""
    for line in raw_lines or []:
        art = db.query(Article).filter(
            Article.id == line["article_id"], Article.is_active == True
        ).first()
        if not art:
            raise HTTPException(400, detail="Ressourcen-Artikel nicht gefunden")
        if art.status != "released":
            raise HTTPException(400, detail="Nur freigegebene Artikel sind als Ressource referenzierbar")


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
        .order_by(ArticleProcessStep.id)
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
    is_purchase = data.step_type == "purchase"
    if is_purchase:
        _validate_supplier(db, data.supplier_id)
    if data.position is not None:
        position = data.position
    else:
        max_pos = (
            db.query(func.max(ArticleProcessStep.position))
            .filter(ArticleProcessStep.article_id == article.id, ArticleProcessStep.is_active == True)
            .scalar()
        )
        position = (max_pos or 0) + 1
    is_movement = data.step_type == "movement"
    is_resource = data.step_type == "resource"
    # Zielstandort nur bei der Bewegung. Die Lieferadresse/der Wareneingang kommt
    # bei der Beschaffung aus der Systemkonfiguration bzw. wird beim Wareneingang erfasst.
    keeps_target = is_movement
    resource_raw = [l.model_dump() for l in (data.resource_lines or [])] if is_resource else None
    if is_resource:
        _validate_resource_lines(db, resource_raw)
    step = ArticleProcessStep(
        article_id=article.id,
        position=position,
        step_type=data.step_type,
        mode=data.mode,
        supplier_id=data.supplier_id if (is_purchase and data.mode == "supplier") else None,
        webshop_url=data.webshop_url if (is_purchase and data.mode == "webshop") else None,
        shared_fields=data.shared_fields if is_purchase else None,
        sample_percent=data.sample_percent if data.step_type == "inspection" else None,
        capture_fields=normalize_capture_fields(data.capture_fields) if data.step_type == "inspection" else None,
        target_location_type=data.target_location_type if keeps_target else None,
        target_location_id=data.target_location_id if keeps_target else None,
        resource_lines=resource_raw,
    )
    db.add(step)
    db.flush()
    log_audit(db, "article_process_steps", None, f"Prozessschritt '{data.step_type}' hinzugefügt",
              current_user.id, object_id=article.object_id)
    # Pflicht-Bewegungen rund um Beschaffungsschritte automatisch herstellen.
    sync_locked_movements(db, article.id)
    db.commit()
    db.refresh(step)
    return _to_response(db, step)


@router.patch("/{object_id}/process-steps/reorder", response_model=list[ArticleProcessStepResponse])
async def reorder_steps(
    object_id: int,
    data: StepReorder,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Reihenfolge der frei sortierbaren Schritte setzen. Pflicht-Bewegungen werden
    serverseitig automatisch (neu) eingefügt und positioniert."""
    article = _get_article(db, object_id)
    ensure_article_draft(article)
    free = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article.id,
                ArticleProcessStep.is_active == True, ArticleProcessStep.locked == False)
        .all()
    )
    by_id = {s.id: s for s in free}
    if set(data.ordered_ids) != set(by_id):
        raise HTTPException(400, detail="Reihenfolge passt nicht zu den vorhandenen Schritten")
    for i, sid in enumerate(data.ordered_ids):
        by_id[sid].position = i * 2   # eindeutig & geordnet; sync renummeriert final
    db.flush()
    sync_locked_movements(db, article.id)
    log_audit(db, "article_process_steps", "reorder", str(data.ordered_ids),
              current_user.id, object_id=article.object_id)
    db.commit()
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article.id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )
    return [_to_response(db, s) for s in steps]


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
    if step.locked:
        raise HTTPException(400, detail="Pflicht-Bewegung ist nicht editierbar (Standort wird beim Ausführen gesetzt)")
    payload = data.model_dump(exclude_unset=True)
    if "supplier_id" in payload:
        _validate_supplier(db, payload["supplier_id"])
    if "capture_fields" in payload:
        payload["capture_fields"] = normalize_capture_fields(payload["capture_fields"])
    if "resource_lines" in payload:
        _validate_resource_lines(db, payload["resource_lines"])
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
    if step.locked:
        raise HTTPException(400, detail="Pflicht-Bewegung zu einer Beschaffung – nicht löschbar")
    step.is_active = False
    log_audit(db, "article_process_steps", "is_active", "false", current_user.id,
              object_id=article.object_id, old_value="true")
    # Verwaiste Pflicht-Bewegungen (z. B. nach Entfernen einer Beschaffung) bereinigen.
    sync_locked_movements(db, article.id)
    db.commit()
    return {"deleted": True}
