from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import (
    Article, Instance, Order, PurchaseOrder, UserProfile,
)
from ..schemas.article import ArticleCreate, ArticleResponse, ArticleUpdate
from ..schemas.deactivation import (
    DeactivateRequest, DeactivationImpact, ImpactArticle, ImpactOrder,
)
from ..schemas.instance import InstanceResponse
from ..services import deactivation
from ..services.admin import log_audit
from ..services.lifecycle import ensure_mutable, ensure_version
from ..services.locations import location_label, physical_location_label
from ..services.processes import article_steps
from ..services.objects import next_object_id
from ..services.weight import computed_weights

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


def _lead_time_ranges(db: Session, article_ids: list[int]) -> dict[int, tuple]:
    """Min/Max Durchlaufzeit in Tagen (Freigabe → Abschluss) je Artikel über
    erledigte Aufträge. Klein genug, um in Python aggregiert zu werden."""
    if not article_ids:
        return {}
    rows = (
        db.query(Order.article_id, Order.released_at, Order.completed_at)
        .filter(
            Order.article_id.in_(article_ids),
            Order.is_active == True,
            Order.released_at.isnot(None),
            Order.completed_at.isnot(None),
        )
        .all()
    )
    out: dict[int, tuple] = {}
    for aid, released_at, completed_at in rows:
        days = (completed_at - released_at).total_seconds() / 86400.0
        if days < 0:
            continue
        lo, hi = out.get(aid, (None, None))
        out[aid] = (days if lo is None else min(lo, days),
                    days if hi is None else max(hi, days))
    return out


def _predecessors(db: Session, object_ids: list[int]) -> dict[int, int]:
    """{Nachfolger-Objektnummer → Vorgänger-Objektnummer} (für ``replaces_id``)."""
    if not object_ids:
        return {}
    rows = (
        db.query(Article.replaced_by_id, Article.object_id)
        .filter(Article.replaced_by_id.in_(object_ids))
        .all()
    )
    return {succ: pred for succ, pred in rows if succ is not None}


def _to_response(article: Article, price_range: tuple | None,
                 lead_range: tuple | None = None,
                 computed_weight=None, replaces_id: int | None = None) -> ArticleResponse:
    resp = ArticleResponse.model_validate(article)
    if price_range:
        low, high = price_range
        resp.unit_cost_low = low
        resp.unit_cost_high = high
    elif article.landed_unit_cost is not None:
        resp.unit_cost_low = article.landed_unit_cost
        resp.unit_cost_high = article.landed_unit_cost
    if lead_range:
        resp.lead_time_days_low, resp.lead_time_days_high = lead_range
    resp.computed_weight_kg = computed_weight
    resp.replaces_id = replaces_id
    return resp


def _single(db: Session, article: Article) -> ArticleResponse:
    """Vollständige Response eines einzelnen Artikels (inkl. Spannen + Vorgänger)."""
    return _to_response(
        article,
        _price_ranges(db, [article.id]).get(article.id),
        _lead_time_ranges(db, [article.id]).get(article.id),
        computed_weights(db, [article.id]).get(article.id),
        _predecessors(db, [article.object_id]).get(article.object_id),
    )


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
    leads = _lead_time_ranges(db, [a.id for a in articles])
    cweights = computed_weights(db, [a.id for a in articles])
    preds = _predecessors(db, [a.object_id for a in articles if a.object_id])
    return [_to_response(a, ranges.get(a.id), leads.get(a.id), cweights.get(a.id),
                         preds.get(a.object_id)) for a in articles]


@router.post("", response_model=ArticleResponse, status_code=201)
async def create_article(
    data: ArticleCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = Article(
        object_id=next_object_id(db, "article"),
        status="draft",
        name=data.name,
        unit=data.unit,
        serialization=data.serialization,
        size=data.size,
        weight_kg=data.weight_kg,
        material=data.material,
        cad_url=data.cad_url,
        surface=data.surface,
        min_order_qty=data.min_order_qty,
        safety_stock=data.safety_stock,
    )
    db.add(article)
    db.flush()
    # Der Artikel trägt seinen (einen) Prozess inline – Schritte werden im Reiter
    # «Prozess» ergänzt und mit dem Artikel freigegeben. Kein separates Prozess-Objekt.
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
    return _single(db, article)


@router.patch("/{object_id}", response_model=ArticleResponse)
async def update_article(
    object_id: int,
    data: ArticleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = _get_active(db, object_id)
    payload = data.model_dump(exclude_unset=True)
    ensure_version(article, payload.pop("expected_updated_at", None))
    ensure_mutable(article.status, payload, "Artikel")
    going_inactive = payload.get("status") == "inactive" and article.status != "inactive"
    reactivating = payload.get("status") == "released" and article.status == "inactive"
    # Freigabe nur mit hinterlegtem Prozess: Ohne Prozessschritt gäbe es nichts, was der
    # Artikel „kann" – die Freigabe friert Spezifikation UND Prozess gemeinsam ein.
    releasing = payload.get("status") == "released" and article.status == "draft"
    if releasing and not article_steps(db, article.id):
        raise HTTPException(
            400,
            detail="Ohne Prozessschritt kann der Artikel nicht freigegeben werden – bitte zuerst im Reiter «Prozess» einen Ablauf hinterlegen.",
        )
    # Stammdaten-Freigabe ist **entkoppelt** von den Prozessen: Sie friert die
    # Spezifikation ein (Identität). Ob der Artikel produzierbar/bestellbar ist,
    # entscheidet sich am Auftrag (dort muss zusätzlich ein **freigegebener Prozess**
    # vorliegen – siehe routers/orders.py). So ist die Stammdaten-Freigabe eine
    # klare Vorbedingung, bevor ein Prozess gestartet werden kann.
    # Reaktivieren nur, wenn nicht ersetzt und keine Komponente inaktiv ist
    if reactivating:
        blk = deactivation.article_reactivation_blocker(db, article)
        if blk:
            raise HTTPException(409, detail=f"Reaktivieren nicht möglich: {blk}")
    for key, value in payload.items():
        if key == "status" and going_inactive:
            continue   # via deactivate_article (inkl. Kaskade) unten
        old_val = getattr(article, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "articles", key, new_str, current_user.id,
                      object_id=article.object_id, old_value=old_str)
        setattr(article, key, value)
    # Inaktivieren kaskadiert (consume-Eltern) – laufende Aufträge laufen aus (Default).
    if going_inactive:
        deactivation.deactivate_article(db, article, current_user.id, "phase_out")
    db.commit()
    db.refresh(article)
    return _single(db, article)


@router.get("/{object_id}/deactivation-impact", response_model=DeactivationImpact)
async def deactivation_impact(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Wirkungsanalyse vor Inaktiv/Ersetzen: mitbetroffene Artikel, laufende
    Aufträge, Lagerbestand."""
    article = _get_active(db, object_id)
    imp = deactivation.article_impact(db, article)
    return DeactivationImpact(
        articles=[ImpactArticle(object_id=a.object_id, name=a.name) for a in imp["articles"]],
        orders=[ImpactOrder(object_id=o.object_id) for o in imp["orders"]],
        stock=imp["stock"],
    )


@router.post("/{object_id}/deactivate", response_model=ArticleResponse)
async def deactivate_article_endpoint(
    object_id: int,
    data: DeactivateRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article = _get_active(db, object_id)
    if article.status == "inactive":
        raise HTTPException(400, detail="Artikel ist bereits inaktiv")
    deactivation.deactivate_article(db, article, current_user.id, data.orders_mode)
    db.commit()
    db.refresh(article)
    return _single(db, article)


@router.post("/{object_id}/replace", response_model=ArticleResponse)
async def replace_article_endpoint(
    object_id: int,
    data: DeactivateRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ersetzen: Duplikat als Entwurf anlegen, verknüpfen, Original inaktiv setzen.
    Liefert den **neuen** Artikel zurück (zum Anpassen)."""
    article = _get_active(db, object_id)
    if article.status == "inactive":
        raise HTTPException(400, detail="Artikel ist bereits inaktiv")
    new = deactivation.duplicate_article(db, article, current_user.id)
    log_audit(db, "articles", "replaced_by_id", str(new.object_id), current_user.id,
              object_id=article.object_id)
    article.replaced_by_id = new.object_id
    deactivation.deactivate_article(db, article, current_user.id, data.orders_mode)
    db.commit()
    db.refresh(new)
    return _single(db, new)


@router.get("/{object_id}/instances", response_model=list[InstanceResponse])
async def list_article_instances(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Bestand des Artikels: alle Bestands-Instanzen (Reiter «Bestand»)."""
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
        resp.location_label = location_label(db, r.location_type, r.location_id)
        if r.location_type == "instance":
            resp.physical_location_label = physical_location_label(db, r.location_type, r.location_id)
        out.append(resp)
    return out
