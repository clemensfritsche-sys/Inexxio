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
from ..models import Article, ArticleProcessStep, Order, OrderLine, UserProfile
from ..schemas.article_process_step import (
    ArticleProcessStepCreate,
    ArticleProcessStepResponse,
    ArticleProcessStepUpdate,
    ResourceLineView,
    StepReorder,
    normalize_capture_fields,
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
        # Mehrpositionen-Auftrag (``order_lines`` statt Einzel-``article_id``): «Verkauf»
        # (je Position, ``order_line_id``) und «Bewegung» (wirkt artikel-unabhängig auf
        # «alle Instanzen des Auftrags») sind bereits per-Position-fest. Beschaffung/
        # Ressource/Datenerfassung/Verschrotten SKALIEREN heute mit ``order.quantity``
        # (bei Mehrpositionen NULL) bzw. brauchen einen einzelnen Artikel – für sie fehlt
        # (noch) die Mehrpositionen-Auflösung, daher hier bewusst eingeschränkt statt
        # einer falschen Zahl/Fehlermeldung.
        self.pooled = kind == "order" and record.article_id is None

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
        if self.pooled:
            # Ein Mehrpositionen-Auftrag verwaltet Verkauf (je Position) und die EINE
            # gemeinsame Bewegung (eine Sendung) selbst, bei der Anlage – Beschaffung ist
            # hier nicht möglich (kein Wareneingang nötig). Liesse man die generische
            # Pflicht-Bewegungs-Synchronisation laufen, würde sie **pro** ``sale``-Schritt
            # eine eigene «Versand zum Kunden»-Bewegung nachziehen (die Regel kennt keine
            # Positionen) – aus einer Sendung würden N. Für Mehrpositionen-Aufträge daher
            # bewusst kein Auto-Sync.
            return
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
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def _resource_line_views(db: Session, raw_lines: list | None) -> list[ResourceLineView]:
    out: list[ResourceLineView] = []
    for line in raw_lines or []:
        art = db.query(Article).filter(Article.id == line["article_id"]).first()
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
    # Kompatibilität erzwingen: nur kontext-zulässige Schritttypen (kein „gemischter"
    # Prozess). Herstellung (Artikel) ≠ Bestands-Operation (Auftrag).
    if data.step_type not in owner.allowed_step_types:
        detail = ("Im Artikel-Prozess (Herstellung) sind nur Beschaffung, Ressource, "
                  "Datenerfassung und Bewegung zulässig – kein Verkauf."
                  if owner.kind == "article" else
                  "Im Auftrags-Ablauf (Bestand) sind nur Verkauf, Bewegung und "
                  "Datenerfassung zulässig – keine Beschaffung/Ressource.")
        raise HTTPException(400, detail=detail)
    if owner.pooled and data.step_type not in ("sale", "movement"):
        raise HTTPException(
            400, detail="Ein Mehrpositionen-Auftrag unterstützt aktuell nur Verkauf und Bewegung")
    order_line_id = None
    if owner.kind == "order" and data.step_type == "sale" and data.order_line_id is not None:
        line = db.query(OrderLine).filter(
            OrderLine.id == data.order_line_id, OrderLine.order_id == owner.order_id,
            OrderLine.is_active == True).first()
        if not line:
            raise HTTPException(400, detail="Position gehört nicht zu diesem Auftrag")
        order_line_id = line.id
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
    keeps_target = data.step_type == "movement"
    resource_raw = [l.model_dump() for l in (data.resource_lines or [])] if is_resource else None
    if is_resource:
        _validate_resource_lines(db, resource_raw)
    step = ArticleProcessStep(
        **owner.new_step_kwargs(),
        position=position,
        step_type=data.step_type,
        order_line_id=order_line_id,
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
    for key, value in payload.items():
        setattr(step, key, value)
    if step.mode == "supplier":
        step.webshop_url = None
    elif step.mode == "webshop":
        step.supplier_id = None
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
