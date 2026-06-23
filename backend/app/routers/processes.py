"""Prozesse: Artikel-eigene Prozesse **und** globale Standardprozesse.

- ``/articles/{id}/processes``: die für einen Artikel wählbaren Prozesse (eigene +
  geerbte freigegebene Standardprozesse) lesen / eigenen Prozess anlegen.
- ``/processes`` (+ ``/{object_id}``): Standardprozesse verwalten (Feed-Typ),
  als «Standard» freigeben/zurückziehen.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, ArticleProcessStep, Process, UserProfile
from ..schemas.process import ProcessCreate, ProcessResponse, ProcessUpdate
from ..services import processes as processes_svc
from ..services.admin import log_audit
from ..services.objects import next_object_id

router = APIRouter(prefix="/api/v1/erp", tags=["processes"])


def _step_counts(db: Session, process_ids: list[int]) -> dict[int, int]:
    if not process_ids:
        return {}
    rows = (
        db.query(ArticleProcessStep.process_id, func.count(ArticleProcessStep.id))
        .filter(ArticleProcessStep.process_id.in_(process_ids),
                ArticleProcessStep.is_active == True)
        .group_by(ArticleProcessStep.process_id)
        .all()
    )
    return {pid: cnt for pid, cnt in rows}


def _to_response(db: Session, proc: Process, counts: dict[int, int] | None = None) -> ProcessResponse:
    resp = ProcessResponse.model_validate(proc)
    if counts is None:
        counts = _step_counts(db, [proc.id])
    resp.step_count = counts.get(proc.id, 0)
    return resp


def _get_article(db: Session, object_id: int) -> Article:
    art = db.query(Article).filter(Article.object_id == object_id, Article.is_active == True).first()
    if not art:
        raise HTTPException(404, detail="Artikel nicht gefunden")
    return art


# ─── Artikel-Prozesse ──────────────────────────────────────────────────────────

@router.get("/articles/{object_id}/processes", response_model=list[ProcessResponse])
async def list_article_processes(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Wählbare Prozesse des Artikels: eigene + geerbte freigegebene Standardprozesse."""
    art = _get_article(db, object_id)
    rows = processes_svc.available_processes(db, art)
    counts = _step_counts(db, [p.id for p in rows])
    return [_to_response(db, p, counts) for p in rows]


@router.post("/articles/{object_id}/processes", response_model=ProcessResponse, status_code=201)
async def create_article_process(
    object_id: int,
    data: ProcessCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    art = _get_article(db, object_id)
    max_pos = (
        db.query(func.max(Process.position))
        .filter(Process.article_id == art.id, Process.is_active == True)
        .scalar()
    )
    proc = Process(
        article_id=art.id, name=data.name, source=data.source,
        is_standard=False, status="released",
        position=data.position if data.position is not None else (max_pos or 0) + 1,
    )
    db.add(proc)
    db.flush()
    log_audit(db, "processes", None, f"Prozess '{data.name}' angelegt",
              current_user.id, object_id=art.object_id)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


@router.patch("/articles/{object_id}/processes/{process_id}", response_model=ProcessResponse)
async def update_article_process(
    object_id: int,
    process_id: int,
    data: ProcessUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    art = _get_article(db, object_id)
    proc = (
        db.query(Process)
        .filter(Process.id == process_id, Process.article_id == art.id, Process.is_active == True)
        .first()
    )
    if not proc:
        raise HTTPException(404, detail="Prozess nicht gefunden")
    payload = data.model_dump(exclude_unset=True)
    payload.pop("status", None)   # Artikel-Prozesse haben keinen eigenen Lebenszyklus
    for key, value in payload.items():
        setattr(proc, key, value)
    log_audit(db, "processes", "update", str(payload), current_user.id, object_id=art.object_id)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


@router.delete("/articles/{object_id}/processes/{process_id}")
async def delete_article_process(
    object_id: int,
    process_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    art = _get_article(db, object_id)
    proc = (
        db.query(Process)
        .filter(Process.id == process_id, Process.article_id == art.id, Process.is_active == True)
        .first()
    )
    if not proc:
        raise HTTPException(404, detail="Prozess nicht gefunden")
    if proc.source == "produce":
        others = (
            db.query(Process)
            .filter(Process.article_id == art.id, Process.is_active == True,
                    Process.source == "produce", Process.id != proc.id)
            .count()
        )
        if others == 0:
            raise HTTPException(400, detail="Der Entstehungs-Prozess kann nicht entfernt werden")
    proc.is_active = False
    log_audit(db, "processes", "is_active", "false", current_user.id,
              object_id=art.object_id, old_value="true")
    db.commit()
    return {"deleted": True}


# ─── Standardprozesse (global, Feed-Typ) ─────────────────────────────────────────

@router.get("/processes", response_model=list[ProcessResponse])
async def list_standard_processes(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Alle Standardprozesse (inkl. Entwürfe) – für die Verwaltung / den Feed."""
    rows = (
        db.query(Process)
        .filter(Process.is_standard == True, Process.article_id.is_(None), Process.is_active == True)
        .order_by(Process.object_id.desc())
        .all()
    )
    counts = _step_counts(db, [p.id for p in rows])
    return [_to_response(db, p, counts) for p in rows]


@router.post("/processes", response_model=ProcessResponse, status_code=201)
async def create_standard_process(
    data: ProcessCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Standardprozess anlegen (eigene Objektnummer; startet als Entwurf)."""
    proc = Process(
        object_id=next_object_id(db, "process"),
        article_id=None, name=data.name, source=data.source,
        is_standard=True, status="draft",
        position=data.position if data.position is not None else 1,
    )
    db.add(proc)
    db.flush()
    log_audit(db, "processes", None, f"Standardprozess '{data.name}' angelegt",
              current_user.id, object_id=proc.object_id)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


def _get_standard(db: Session, object_id: int) -> Process:
    proc = (
        db.query(Process)
        .filter(Process.object_id == object_id, Process.is_standard == True,
                Process.is_active == True)
        .first()
    )
    if not proc:
        raise HTTPException(404, detail="Standardprozess nicht gefunden")
    return proc


@router.get("/processes/{object_id}", response_model=ProcessResponse)
async def get_standard_process(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _to_response(db, _get_standard(db, object_id))


@router.patch("/processes/{object_id}", response_model=ProcessResponse)
async def update_standard_process(
    object_id: int,
    data: ProcessUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    proc = _get_standard(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("status") == "released":
        if not _step_counts(db, [proc.id]).get(proc.id):
            raise HTTPException(400, detail="Standardprozess ohne Schritt kann nicht freigegeben werden")
    for key, value in payload.items():
        old = getattr(proc, key, None)
        if str(old) != str(value):
            log_audit(db, "processes", key, str(value), current_user.id,
                      object_id=proc.object_id, old_value=str(old))
        setattr(proc, key, value)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


@router.delete("/processes/{object_id}")
async def delete_standard_process(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    proc = _get_standard(db, object_id)
    proc.is_active = False
    log_audit(db, "processes", "is_active", "false", current_user.id,
              object_id=proc.object_id, old_value="true")
    db.commit()
    return {"deleted": True}
