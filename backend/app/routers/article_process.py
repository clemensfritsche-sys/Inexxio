"""Prozessschritte – verwaltet am **Artikel** (wie etwas entsteht) oder am
**Auftrag** (individueller Ablauf auf bestehende Instanzen, CUSTOM-Modus).

Es gibt kein eigenständiges Prozess-Objekt mehr: ein Schritt hängt entweder an
``article_id`` (Artikel-Prozess) oder an ``order_id`` (Auftrags-Prozess). Beide
nutzen dieselbe CRUD-Logik über die ``_Owner``-Abstraktion. Editierbar, solange
der Träger im Entwurf ist (Auftrag zusätzlich: nur im CUSTOM-Modus).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..domain import event_types
from ..models import Article, ArticleProcessStep, Order, UserProfile
from ..schemas.article_process_step import (
    ArticleProcessStepCreate,
    ArticleProcessStepResponse,
    ArticleProcessStepUpdate,
    ResourceLineView,
    StepReorder,
    normalize_capture_fields,
    normalize_doc_signers,
)
from ..services.admin import log_audit
from ..services.process_steps import sync_locked_movements

router = APIRouter(prefix="/api/v1/erp", tags=["process-steps"])


# ─── Owner-Abstraktion (Artikel- oder Auftrags-Prozess) ──────────────────────────

class _Owner:
    def __init__(self, kind: str, record):
        self.kind = kind                       # 'article' | 'order'
        self.record = record
        self.object_id = record.object_id
        self.article_id = record.id if kind == "article" else None
        self.order_id = record.id if kind == "order" else None
        # Zulässige Schritttypen je Kontext (Herstellung vs. Bestands-Operation) –
        # erzwingt die Kompatibilität der Prozessschritte (siehe domain.event_types).
        self.allowed_step_types = event_types.allowed_step_types(kind)

    def ensure_editable(self) -> None:
        if self.kind == "article" and self.record.status != "draft":
            raise HTTPException(409, detail="Spezifikation ist freigegeben und gesperrt – zum Ändern bitte ersetzen")
        # Ein Auftrag trägt eigene Schritte (Bestands-Ablauf), solange er im Entwurf ist –
        # unabhängig davon, ob er auf Artikel+Menge (FIFO) oder gewählte Instanzen wirkt.
        if self.kind == "order" and self.record.status != "draft":
            raise HTTPException(409, detail="Auftrag ist freigegeben und gesperrt")

    def filter(self):
        if self.kind == "order":
            return ArticleProcessStep.order_id == self.order_id
        return and_(ArticleProcessStep.article_id == self.article_id,
                    ArticleProcessStep.order_id.is_(None))

    def sync(self, db: Session) -> None:
        # Ein Mehrpositionen-Auftrag hat genau EINEN Verkaufs-Schritt (mehrere Belege
        # teilen sich ihn, ``services/sale.py``) – die Pflicht-Bewegungs-Synchronisation
        # zieht dafür wie gewohnt GENAU EINE «Versand zum Kunden»-Bewegung nach, keine
        # Sonderbehandlung nötig.
        sync_locked_movements(db, article_id=self.article_id, order_id=self.order_id)

    def new_step_kwargs(self) -> dict:
        return {"article_id": self.article_id, "order_id": self.order_id}


def _article_owner(db: Session, object_id: int) -> _Owner:
    art = db.query(Article).filter(Article.object_id == object_id, Article.is_active == True).first()
    if not art:
        raise HTTPException(404, detail="Artikel nicht gefunden")
    return _Owner("article", art)


def _order_owner(db: Session, object_id: int) -> _Owner:
    o = db.query(Order).filter(Order.object_id == object_id, Order.is_active == True).first()
    if not o:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    return _Owner("order", o)


# ─── Gemeinsame Helfer ───────────────────────────────────────────────────────────

def _supplier_name(db: Session, supplier_id: int | None) -> str | None:
    if not supplier_id:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == supplier_id).first()
    return u.display_name if u else None


def _resource_line_views(db: Session, raw_lines: list | None) -> list[ResourceLineView]:
    if not raw_lines:
        return []
    # Artikel BATCH laden (vorher ein Query je Zeile – bei jeder Schrittliste, N+1)
    art_ids = {line["article_id"] for line in raw_lines}
    arts = {a.id: a for a in db.query(Article).filter(Article.id.in_(art_ids)).all()}
    out: list[ResourceLineView] = []
    for line in raw_lines:
        art = arts.get(line["article_id"])
        m = line.get("mode")
        out.append(ResourceLineView(
            article_id=line["article_id"], quantity=line.get("quantity", 1),
            mode=m if m in ("consume", "tool") else "consume",
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
        UserProfile.id == supplier_id, UserProfile.is_active == True).first()
    if not u or u.role != "supplier":
        raise HTTPException(400, detail="Gewählter Benutzer ist kein aktiver Lieferant")


def _validate_resource_lines(db: Session, raw_lines: list | None) -> None:
    for line in raw_lines or []:
        art = db.query(Article).filter(
            Article.id == line["article_id"], Article.is_active == True).first()
        if not art:
            raise HTTPException(400, detail="Ressourcen-Artikel nicht gefunden")
        if art.status != "released":
            raise HTTPException(400, detail="Nur freigegebene Artikel sind als Ressource referenzierbar")


def _validate_doc_signers(db: Session, signers: list | None) -> None:
    """Jede deklarierte Freigabe-Partei muss eine aktive Person (Objektnummer) sein."""
    for s in signers or []:
        obj = getattr(s, "signer_object_id", None) if not isinstance(s, dict) else s.get("signer_object_id")
        if obj is None:
            continue
        u = db.query(UserProfile).filter(
            UserProfile.object_id == int(obj), UserProfile.is_active == True).first()
        if not u:
            raise HTTPException(400, detail=f"Freigabe-Partei {obj} ist keine aktive Person")


def _active_steps(db: Session, owner: _Owner) -> list[ArticleProcessStep]:
    return (
        db.query(ArticleProcessStep)
        .filter(owner.filter(), ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def _get_step(db: Session, owner: _Owner, step_id: int) -> ArticleProcessStep:
    step = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.id == step_id, owner.filter(),
                ArticleProcessStep.is_active == True)
        .first()
    )
    if not step:
        raise HTTPException(404, detail="Prozessschritt nicht gefunden")
    return step


# ─── CRUD (owner-agnostisch) ─────────────────────────────────────────────────────

def _create(db: Session, owner: _Owner, data: ArticleProcessStepCreate, user: UserProfile) -> ArticleProcessStepResponse:
    owner.ensure_editable()
    # Kompatibilität erzwingen: nur kontext-zulässige Schritttypen. Am Auftrag sind ALLE
    # Typen erlaubt (Schema-Whitelist = ORDER_STEP_TYPES) – greifen kann das nur am Artikel.
    if data.step_type not in owner.allowed_step_types:
        raise HTTPException(400, detail=(
            "Im Artikel-Prozess (Herstellung) sind nur Beschaffung, Ressource, Datenerfassung, "
            "Bewegung und Dokument zulässig – kein Verkauf/Verschrotten."))
    # Jedes Prozessschrittmodul ist universell einsetzbar – auch bei einem Mehrpositionen-
    # Auftrag (``order_lines`` statt Einzel-``article_id``): Beschaffung/Datenerfassung
    # legen je Position eine eigene Fachzeile an (analog Verkauf, ``services/purchase.py``);
    # Ressource/Verschrotten/Bewegung wirken ohnehin artikel-unabhängig auf die gesamte
    # Instanzmenge des Auftrags. Einzige inhaltliche Einschränkung bleibt die Abo-Regel
    # beim Verkauf (siehe unten) – KEINE Schritttyp-Whitelist mehr.
    if data.step_type == "sale" and owner.kind == "order":
        from ..services import order_lines as order_lines_svc, sale as sale_svc
        lines = order_lines_svc.lines_for(db, owner.record)
        article_ids = {l.article_id for l in lines} if lines else (
            {owner.record.article_id} if owner.record.article_id else set())
        sale_svc.assert_sale_compatible(db, article_ids)
    is_purchase = data.step_type == "purchase"
    if is_purchase:
        _validate_supplier(db, data.supplier_id)
    if data.position is not None:
        position = data.position
    else:
        max_pos = (
            db.query(func.max(ArticleProcessStep.position))
            .filter(owner.filter(), ArticleProcessStep.is_active == True).scalar()
        )
        position = (max_pos or 0) + 1
    is_resource = data.step_type == "resource"
    is_document = data.step_type == "document"
    keeps_target = data.step_type == "movement"
    resource_raw = [l.model_dump() for l in (data.resource_lines or [])] if is_resource else None
    if is_resource:
        _validate_resource_lines(db, resource_raw)
    if is_document:
        _validate_doc_signers(db, data.doc_signers)
    step = ArticleProcessStep(
        **owner.new_step_kwargs(),
        position=position,
        step_type=data.step_type,
        mode=data.mode,
        supplier_id=data.supplier_id if (is_purchase and data.mode == "supplier") else None,
        webshop_url=data.webshop_url if (is_purchase and data.mode == "webshop") else None,
        shared_fields=data.shared_fields if is_purchase else None,
        sample_percent=data.sample_percent if data.step_type == "inspection" else None,
        capture_fields=normalize_capture_fields(data.capture_fields) if data.step_type == "inspection" else None,
        require_signature=bool(data.require_signature) if data.step_type == "inspection" else False,
        signer_ids=([int(x) for x in data.signer_ids] if data.signer_ids else None) if data.step_type == "inspection" else None,
        require_photo=bool(data.require_photo) if data.step_type == "inspection" else False,
        photo_instruction=((data.photo_instruction or "").strip() or None) if data.step_type == "inspection" else None,
        target_location_type=data.target_location_type if keeps_target else None,
        target_location_id=data.target_location_id if keeps_target else None,
        transport_mode=(data.transport_mode or "auto") if data.step_type == "movement" else "auto",
        resource_lines=resource_raw,
        doc_signers=normalize_doc_signers(data.doc_signers) if is_document else None,
        sign_sequential=bool(data.sign_sequential) if is_document else False,
        doc_audience=data.doc_audience if is_document else None,
        doc_audience_roles=(data.doc_audience_roles or None) if is_document else None,
        doc_audience_person_ids=([int(x) for x in data.doc_audience_person_ids]
                                 if data.doc_audience_person_ids else None) if is_document else None,
        doc_visibility=(data.doc_visibility or "internal") if is_document else "internal",
    )
    db.add(step)
    db.flush()
    log_audit(db, "article_process_steps", None, f"Prozessschritt '{data.step_type}' hinzugefügt",
              user.id, object_id=owner.object_id)
    owner.sync(db)
    db.commit()
    db.refresh(step)
    return _to_response(db, step)


def _reorder(db: Session, owner: _Owner, data: StepReorder, user: UserProfile) -> list[ArticleProcessStepResponse]:
    owner.ensure_editable()
    free = (
        db.query(ArticleProcessStep)
        .filter(owner.filter(), ArticleProcessStep.is_active == True, ArticleProcessStep.locked == False)
        .all()
    )
    by_id = {s.id: s for s in free}
    if set(data.ordered_ids) != set(by_id):
        raise HTTPException(400, detail="Reihenfolge passt nicht zu den vorhandenen Schritten")
    for i, sid in enumerate(data.ordered_ids):
        by_id[sid].position = i * 2
    db.flush()
    owner.sync(db)
    log_audit(db, "article_process_steps", "reorder", str(data.ordered_ids), user.id,
              object_id=owner.object_id)
    db.commit()
    return [_to_response(db, s) for s in _active_steps(db, owner)]


def _update(db: Session, owner: _Owner, step_id: int, data: ArticleProcessStepUpdate, user: UserProfile) -> ArticleProcessStepResponse:
    owner.ensure_editable()
    step = _get_step(db, owner, step_id)
    payload = data.model_dump(exclude_unset=True)
    if step.locked:
        if step.target_location_type == "user":
            raise HTTPException(400, detail="Versand zum Lieferanten ist fix – nicht editierbar")
        if set(payload) - {"target_location_type", "target_location_id"}:
            raise HTTPException(400, detail="Bei dieser Pflicht-Bewegung ist nur das Ziel editierbar")
        ttype = payload.get("target_location_type")
        if ttype not in (None, "lagerplatz"):
            raise HTTPException(400, detail="Wareneingang-Ziel muss ein Lagerplatz sein")
        step.target_location_type = ttype
        step.target_location_id = payload.get("target_location_id") if ttype else None
        db.commit()
        db.refresh(step)
        return _to_response(db, step)
    if "supplier_id" in payload:
        _validate_supplier(db, payload["supplier_id"])
    if "capture_fields" in payload:
        payload["capture_fields"] = normalize_capture_fields(payload["capture_fields"])
    if "resource_lines" in payload:
        _validate_resource_lines(db, payload["resource_lines"])
    if "doc_signers" in payload:
        _validate_doc_signers(db, payload["doc_signers"])
        payload["doc_signers"] = normalize_doc_signers(payload["doc_signers"])
    for key, value in payload.items():
        setattr(step, key, value)
    if step.mode == "supplier":
        step.webshop_url = None
    elif step.mode == "webshop":
        step.supplier_id = None
    # FIX: Anders als _create/_reorder/_delete zog _update die Pflicht-Bewegungen NICHT nach –
    # ein Lieferanten-/Modus-Wechsel am Beschaffungs-Schritt liess den gesperrten «Versand zum
    # Lieferanten» aufs ALTE Ziel zeigen (und webshop→supplier legte ihn gar nicht erst an).
    db.flush()
    owner.sync(db)
    log_audit(db, "article_process_steps", "update", str(payload), user.id, object_id=owner.object_id)
    db.commit()
    db.refresh(step)
    return _to_response(db, step)


def _delete(db: Session, owner: _Owner, step_id: int, user: UserProfile) -> dict:
    owner.ensure_editable()
    step = _get_step(db, owner, step_id)
    if step.locked:
        raise HTTPException(400, detail="Pflicht-Bewegung zu einer Beschaffung – nicht löschbar")
    step.is_active = False
    log_audit(db, "article_process_steps", "is_active", "false", user.id,
              object_id=owner.object_id, old_value="true")
    owner.sync(db)
    db.commit()
    return {"deleted": True}


# ─── Routen: Artikel-Prozess ─────────────────────────────────────────────────────

@router.get("/articles/{object_id}/steps", response_model=list[ArticleProcessStepResponse])
async def list_article_steps(object_id: int, db: Session = Depends(get_db), _: UserProfile = Depends(require_employee)):
    return [_to_response(db, s) for s in _active_steps(db, _article_owner(db, object_id))]


@router.post("/articles/{object_id}/steps", response_model=ArticleProcessStepResponse, status_code=201)
async def create_article_step(object_id: int, data: ArticleProcessStepCreate, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _create(db, _article_owner(db, object_id), data, user)


@router.patch("/articles/{object_id}/steps/reorder", response_model=list[ArticleProcessStepResponse])
async def reorder_article_steps(object_id: int, data: StepReorder, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _reorder(db, _article_owner(db, object_id), data, user)


@router.patch("/articles/{object_id}/steps/{step_id}", response_model=ArticleProcessStepResponse)
async def update_article_step(object_id: int, step_id: int, data: ArticleProcessStepUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _update(db, _article_owner(db, object_id), step_id, data, user)


@router.delete("/articles/{object_id}/steps/{step_id}")
async def delete_article_step(object_id: int, step_id: int, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _delete(db, _article_owner(db, object_id), step_id, user)


# ─── Routen: Auftrags-Prozess (CUSTOM) ───────────────────────────────────────────

@router.get("/orders/{object_id}/steps", response_model=list[ArticleProcessStepResponse])
async def list_order_steps(object_id: int, db: Session = Depends(get_db), _: UserProfile = Depends(require_employee)):
    return [_to_response(db, s) for s in _active_steps(db, _order_owner(db, object_id))]


@router.post("/orders/{object_id}/steps", response_model=ArticleProcessStepResponse, status_code=201)
async def create_order_step(object_id: int, data: ArticleProcessStepCreate, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _create(db, _order_owner(db, object_id), data, user)


@router.patch("/orders/{object_id}/steps/reorder", response_model=list[ArticleProcessStepResponse])
async def reorder_order_steps(object_id: int, data: StepReorder, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _reorder(db, _order_owner(db, object_id), data, user)


@router.patch("/orders/{object_id}/steps/{step_id}", response_model=ArticleProcessStepResponse)
async def update_order_step(object_id: int, step_id: int, data: ArticleProcessStepUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _update(db, _order_owner(db, object_id), step_id, data, user)


@router.delete("/orders/{object_id}/steps/{step_id}")
async def delete_order_step(object_id: int, step_id: int, db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    return _delete(db, _order_owner(db, object_id), step_id, user)
