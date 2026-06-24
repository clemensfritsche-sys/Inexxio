"""Prozesse – **eigenständige Objekte** (Feed-Typ «Prozesse») und ihre Zuordnung
zu Artikeln über die **Prozessstückliste** (``article_process_links``).

- ``/processes`` (+ ``/{object_id}``): alle Prozesse verwalten (Feed), freigeben/
  deaktivieren/ersetzen; ``is_standard`` nur bei der Anlage wählbar.
- ``/articles/{id}/processes``: wählbare Prozesse eines Artikels (Stückliste +
  geerbte Standards). ``/articles/{id}/process-links``: Stückliste pflegen
  (Prozess hinzufügen/entfernen/sortieren) – das wirkt nur auf **diesen** Artikel.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, ArticleProcessStep, Process, UserProfile
from ..schemas.process import (
    ProcessCreate, ProcessLinkCreate, ProcessLinkReorder, ProcessResponse, ProcessUpdate,
)
from ..services import processes as processes_svc
from ..services.admin import log_audit
from ..services.objects import next_object_id
from ..services.process_steps import sync_locked_movements

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
    resp.stock_effect = processes_svc.stock_effect(db, proc)
    resp.linked_article_count = processes_svc.linked_article_count(db, proc.id)
    if proc.object_id:
        pred = db.query(Process.object_id).filter(Process.replaced_by_id == proc.object_id).first()
        resp.replaces_id = pred[0] if pred else None
    return resp


def _get_article(db: Session, object_id: int) -> Article:
    art = db.query(Article).filter(Article.object_id == object_id, Article.is_active == True).first()
    if not art:
        raise HTTPException(404, detail="Artikel nicht gefunden")
    return art


def _get_process_obj(db: Session, object_id: int) -> Process:
    proc = (
        db.query(Process)
        .filter(Process.object_id == object_id, Process.is_active == True)
        .first()
    )
    if not proc:
        raise HTTPException(404, detail="Prozess nicht gefunden")
    return proc


def _copy_steps(db: Session, src: Process, dst: Process) -> None:
    """Frei sortierbare Schritte eines Prozesses kopieren (für Ersetzen). Pflicht-
    Bewegungen werden danach neu abgeleitet (``sync_locked_movements``)."""
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.process_id == src.id, ArticleProcessStep.is_active == True,
                ArticleProcessStep.locked == False)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )
    for s in steps:
        db.add(ArticleProcessStep(
            process_id=dst.id, article_id=dst.article_id, position=s.position, step_type=s.step_type,
            mode=s.mode, supplier_id=s.supplier_id, webshop_url=s.webshop_url,
            shared_fields=s.shared_fields, sample_percent=s.sample_percent,
            capture_fields=s.capture_fields, target_location_type=s.target_location_type,
            target_location_id=s.target_location_id, resource_lines=s.resource_lines,
        ))
    db.flush()
    sync_locked_movements(db, dst.id)


# ─── Prozessstückliste eines Artikels ────────────────────────────────────────────

@router.get("/articles/{object_id}/processes", response_model=list[ProcessResponse])
async def list_article_processes(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Wählbare Prozesse des Artikels: Stückliste + geerbte freigegebene Standards."""
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
    """Neuen Prozess anlegen (eigene Objektnummer, Entwurf) und der Stückliste
    dieses Artikels hinzufügen."""
    art = _get_article(db, object_id)
    proc = Process(
        object_id=next_object_id(db, "process"),
        article_id=art.id, name=data.name, source=data.source,
        is_standard=bool(data.is_standard), status="draft",
        position=data.position if data.position is not None else 1,
    )
    db.add(proc)
    db.flush()
    if not proc.is_standard:
        processes_svc.link_process(db, art.id, proc.id, data.position)
    log_audit(db, "processes", None, f"Prozess '{data.name}' angelegt",
              current_user.id, object_id=proc.object_id)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


@router.post("/articles/{object_id}/process-links", response_model=ProcessResponse, status_code=201)
async def add_process_link(
    object_id: int,
    data: ProcessLinkCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Bestehenden Prozess der Stückliste hinzufügen (wirkt nur auf diesen Artikel)."""
    art = _get_article(db, object_id)
    proc = (
        db.query(Process)
        .filter(Process.id == data.process_id, Process.is_active == True)
        .first()
    )
    if not proc:
        raise HTTPException(404, detail="Prozess nicht gefunden")
    if proc.is_standard:
        raise HTTPException(400, detail="Standardprozesse gelten automatisch – kein Link nötig")
    processes_svc.link_process(db, art.id, proc.id, data.position)
    log_audit(db, "article_process_links", None, f"Prozess {proc.object_id} verlinkt",
              current_user.id, object_id=art.object_id)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


@router.patch("/articles/{object_id}/process-links/reorder", response_model=list[ProcessResponse])
async def reorder_process_links(
    object_id: int,
    data: ProcessLinkReorder,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Reihenfolge der Prozessstückliste setzen (Prozess-IDs in Zielreihenfolge)."""
    art = _get_article(db, object_id)
    current = set(processes_svc.linked_process_ids(db, art.id))
    if set(data.ordered_process_ids) != current:
        raise HTTPException(400, detail="Reihenfolge passt nicht zur Stückliste")
    for i, pid in enumerate(data.ordered_process_ids):
        processes_svc.link_process(db, art.id, pid, position=i + 1)
    log_audit(db, "article_process_links", "reorder", str(data.ordered_process_ids),
              current_user.id, object_id=art.object_id)
    db.commit()
    rows = processes_svc.available_processes(db, art)
    counts = _step_counts(db, [p.id for p in rows])
    return [_to_response(db, p, counts) for p in rows]


@router.delete("/articles/{object_id}/process-links/{process_id}")
async def remove_process_link(
    object_id: int,
    process_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Prozess aus der Stückliste entfernen (nur den Link – das Prozess-Objekt
    bleibt für andere Artikel bestehen)."""
    art = _get_article(db, object_id)
    proc = db.query(Process).filter(Process.id == process_id).first()
    if proc and proc.source == "produce":
        others = [
            p for p in processes_svc.own_processes(db, art.id)
            if p.source == "produce" and p.id != process_id
        ]
        if not others:
            raise HTTPException(400, detail="Der Entstehungs-Prozess kann nicht entfernt werden")
    if not processes_svc.unlink_process(db, art.id, process_id):
        raise HTTPException(404, detail="Prozess ist nicht in der Stückliste")
    log_audit(db, "article_process_links", "is_active", "false", current_user.id,
              object_id=art.object_id, old_value="true")
    db.commit()
    return {"unlinked": True}


# ─── Prozesse (Feed-Typ, alle) ───────────────────────────────────────────────────

@router.get("/processes", response_model=list[ProcessResponse])
async def list_processes(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Alle Prozesse (Artikel-Prozesse + Standards), neueste zuerst – für den Feed."""
    rows = (
        db.query(Process)
        .filter(Process.is_active == True)
        .order_by(Process.object_id.desc())
        .all()
    )
    counts = _step_counts(db, [p.id for p in rows])
    return [_to_response(db, p, counts) for p in rows]


@router.post("/processes", response_model=ProcessResponse, status_code=201)
async def create_process(
    data: ProcessCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Eigenständigen Prozess anlegen (Objektnummer, startet als Entwurf). Ohne
    Artikel-Bindung – die Zuordnung erfolgt über die Stückliste je Artikel."""
    proc = Process(
        object_id=next_object_id(db, "process"),
        article_id=None, name=data.name, source=data.source,
        is_standard=bool(data.is_standard), status="draft",
        position=data.position if data.position is not None else 1,
    )
    db.add(proc)
    db.flush()
    log_audit(db, "processes", None, f"Prozess '{data.name}' angelegt",
              current_user.id, object_id=proc.object_id)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


@router.get("/processes/{object_id}", response_model=ProcessResponse)
async def get_process(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _to_response(db, _get_process_obj(db, object_id))


@router.patch("/processes/{object_id}", response_model=ProcessResponse)
async def update_process(
    object_id: int,
    data: ProcessUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    proc = _get_process_obj(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    # is_standard nur im Entwurf wählbar (danach gesperrt).
    if "is_standard" in payload and bool(payload["is_standard"]) != proc.is_standard:
        if proc.status != "draft":
            raise HTTPException(409, detail="Standard-Markierung ist nach Freigabe gesperrt")
    # Inhalt (Quelle) nach Freigabe gesperrt – Änderung = Ersetzen.
    if "source" in payload and payload["source"] != proc.source and proc.status != "draft":
        raise HTTPException(409, detail="Quelle ist nach Freigabe gesperrt – bitte Prozess ersetzen")
    # Freigeben nur mit mindestens einem Schritt.
    if payload.get("status") == "released" and proc.status != "released":
        if not _step_counts(db, [proc.id]).get(proc.id):
            raise HTTPException(400, detail="Prozess ohne Schritt kann nicht freigegeben werden")
    for key, value in payload.items():
        old = getattr(proc, key, None)
        if str(old) != str(value):
            log_audit(db, "processes", key, str(value), current_user.id,
                      object_id=proc.object_id, old_value=str(old))
        setattr(proc, key, value)
    db.commit()
    db.refresh(proc)
    return _to_response(db, proc)


@router.post("/processes/{object_id}/replace", response_model=ProcessResponse)
async def replace_process(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ersetzen: Nachfolger (Entwurf, mit kopierten Schritten) anlegen, alle
    Stücklisten-Links auf ihn umhängen, Original deaktivieren + verknüpfen.
    Betrifft **alle** Artikel, die den Prozess führen (gemeinsames Objekt)."""
    proc = _get_process_obj(db, object_id)
    if proc.status == "inactive":
        raise HTTPException(400, detail="Inaktive Prozesse können nicht ersetzt werden")
    new = Process(
        object_id=next_object_id(db, "process"), article_id=proc.article_id,
        name=proc.name, source=proc.source, is_standard=proc.is_standard,
        status="draft", position=proc.position,
    )
    db.add(new)
    db.flush()
    _copy_steps(db, proc, new)
    # Stücklisten-Links auf den Nachfolger umhängen.
    for aid in processes_svc.linked_article_ids(db, proc.id):
        processes_svc.unlink_process(db, aid, proc.id)
        processes_svc.link_process(db, aid, new.id)
    proc.replaced_by_id = new.object_id
    proc.status = "inactive"
    log_audit(db, "processes", "replaced_by_id", str(new.object_id), current_user.id,
              object_id=proc.object_id)
    db.commit()
    db.refresh(new)
    return _to_response(db, new)


@router.delete("/processes/{object_id}")
async def delete_process(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Prozess-Objekt deaktivieren (soft). Verschwindet aus allen Stücklisten/
    Auswahllisten; laufende Aufträge behalten ihren Prozess."""
    proc = _get_process_obj(db, object_id)
    proc.is_active = False
    log_audit(db, "processes", "is_active", "false", current_user.id,
              object_id=proc.object_id, old_value="true")
    db.commit()
    return {"deleted": True}
