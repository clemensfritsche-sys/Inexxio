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
from ..services import people
from ..services.admin import log_audit

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


def _order_owner_for(order: Order) -> _Owner:
    """Owner für einen bereits geladenen Auftrag – gebraucht bei der **Anlage**, wo der
    Auftrag noch keine Objektnummer hat (die kommt erst mit der Freigabe, Notiz #386).
    Damit legt die Anlage ihre Schritte über denselben EINEN Weg an wie der Editor."""
    return _Owner("order", order)


# ─── Gemeinsame Helfer ───────────────────────────────────────────────────────────

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
    resp.supplier_name = people.name_by_id(db, step.supplier_id)
    if step.supplier_id:
        sup = db.query(UserProfile).filter(UserProfile.id == step.supplier_id).first()
        resp.supplier_object_id = sup.object_id if sup else None
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


# ─── Welche Felder ein Schritt-Typ trägt ─────────────────────────────────────────
# Je Typ EINE Funktion: sie prüft, was zu prüfen ist, und liefert genau die Spalten,
# die dieser Typ füllt. Alles andere bleibt leer (Modell-Default) – ein Beschaffungs-
# Schritt hat kein ``sample_percent``, ein Dokument keinen Lieferanten.
#
# Vorher stand dieselbe Aussage als ~14 einzelne ``x if is_document else None`` im
# Konstruktor, dazu drei Flag-Variablen davor. Die Frage «welche Felder hat ein
# Dokument-Schritt?» liess sich nur durch Absuchen aller Zeilen beantworten, und ein
# neuer Typ hiess: überall eine Bedingung ergänzen. Jetzt ist es ein Eintrag.

def _purchase_fields(db: Session, d) -> dict:
    _validate_supplier(db, d.supplier_id)
    return {
        # Die Quelle ist entweder ein Lieferant ODER ein Webshop – nie beides.
        "supplier_id": d.supplier_id if d.mode == "supplier" else None,
        "webshop_url": d.webshop_url if d.mode == "webshop" else None,
        "shared_fields": d.shared_fields,
    }


def _inspection_fields(db: Session, d) -> dict:
    return {"sample_percent": d.sample_percent,
            "capture_fields": normalize_capture_fields(d.capture_fields)}


def _movement_fields(db: Session, d) -> dict:
    return {"target_location_type": d.target_location_type,
            "target_location_id": d.target_location_id}


def _resource_fields(db: Session, d) -> dict:
    raw = [l.model_dump() for l in (d.resource_lines or [])]
    _validate_resource_lines(db, raw)
    return {"resource_lines": raw}


def _document_fields(db: Session, d) -> dict:
    _validate_doc_signers(db, d.doc_signers)
    return {
        "doc_signers": normalize_doc_signers(d.doc_signers),
        "sign_sequential": bool(d.sign_sequential),
        "doc_audience": d.doc_audience,
        "doc_audience_roles": d.doc_audience_roles or None,
        "doc_audience_person_ids": ([int(x) for x in d.doc_audience_person_ids]
                                    if d.doc_audience_person_ids else None),
        "doc_visibility": d.doc_visibility or "internal",
    }


_FIELDS_BY_TYPE = {
    "purchase": _purchase_fields,
    "inspection": _inspection_fields,
    "movement": _movement_fields,
    "resource": _resource_fields,
    "document": _document_fields,
}


# ─── CRUD (owner-agnostisch) ─────────────────────────────────────────────────────

def _next_position(db: Session, owner: _Owner, wanted: int | None) -> int:
    """Position des neuen Schritts: die gewünschte oder ans Ende."""
    if wanted is not None:
        return wanted
    max_pos = (
        db.query(func.max(ArticleProcessStep.position))
        .filter(owner.filter(), ArticleProcessStep.is_active == True).scalar()
    )
    return (max_pos or 0) + 1


def _create(db: Session, owner: _Owner, data: ArticleProcessStepCreate, user: UserProfile) -> ArticleProcessStepResponse:
    owner.ensure_editable()
    # Jedes Modul ist universell einsetzbar (Testnotiz #246) – die Liste ist für Artikel
    # und Auftrag dieselbe; die Prüfung bleibt als Schutz gegen unbekannte Typen.
    if data.step_type not in owner.allowed_step_types:
        raise HTTPException(400, detail=f"Unbekannter Schritt-Typ «{data.step_type}»")
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
    # Prüfen + die Felder DIESES Typs holen; alles andere bleibt leer (Modell-Default).
    fields = _FIELDS_BY_TYPE.get(data.step_type, lambda _db, _d: {})(db, data)
    step = ArticleProcessStep(
        **owner.new_step_kwargs(),
        position=_next_position(db, owner, data.position),
        step_type=data.step_type,
        mode=data.mode,
        **fields,
    )
    db.add(step)
    db.flush()
    log_audit(db, "article_process_steps", None, f"Prozessschritt '{data.step_type}' hinzugefügt",
              user.id, object_id=owner.object_id)
    db.commit()
    db.refresh(step)
    return _to_response(db, step)


def _reorder(db: Session, owner: _Owner, data: StepReorder, user: UserProfile) -> list[ArticleProcessStepResponse]:
    owner.ensure_editable()
    # ALLE aktiven Schritte sind frei sortierbar – auch die gesäten Begleit-Bewegungen
    # (Wareneingang/Versand). Früher waren sie ``locked`` und wurden hier ausgeklammert.
    free = (
        db.query(ArticleProcessStep)
        .filter(owner.filter(), ArticleProcessStep.is_active == True)
        .all()
    )
    by_id = {s.id: s for s in free}
    if set(data.ordered_ids) != set(by_id):
        raise HTTPException(400, detail="Reihenfolge passt nicht zu den vorhandenen Schritten")
    for i, sid in enumerate(data.ordered_ids):
        by_id[sid].position = i * 2
    db.flush()
    log_audit(db, "article_process_steps", "reorder", str(data.ordered_ids), user.id,
              object_id=owner.object_id)
    db.commit()
    return [_to_response(db, s) for s in _active_steps(db, owner)]


def _update(db: Session, owner: _Owner, step_id: int, data: ArticleProcessStepUpdate, user: UserProfile) -> ArticleProcessStepResponse:
    owner.ensure_editable()
    step = _get_step(db, owner, step_id)
    payload = data.model_dump(exclude_unset=True)
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
    db.flush()
    log_audit(db, "article_process_steps", "update", str(payload), user.id, object_id=owner.object_id)
    db.commit()
    db.refresh(step)
    return _to_response(db, step)


def _delete(db: Session, owner: _Owner, step_id: int, user: UserProfile) -> dict:
    owner.ensure_editable()
    step = _get_step(db, owner, step_id)
    # JEDER Schritt ist löschbar. Das System legt von sich aus KEINEN Prozessschritt an –
    # physisch nötige Transporte entstehen zur Laufzeit als Bereitstellungs-Unter-Auftrag
    # (``services/provisioning.py``), nicht als Modul im geplanten Ablauf.
    step.is_active = False
    log_audit(db, "article_process_steps", "is_active", "false", user.id,
              object_id=owner.object_id, old_value="true")
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
