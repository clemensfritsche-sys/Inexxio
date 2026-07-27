from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import (
    Article, Instance, Order, PurchaseOrder, UserProfile,
)
from ..schemas.article import (
    ArticleCreate, ArticleNameSuggestion, ArticleResponse, ArticleUpdate,
)
from ..schemas.deactivation import (
    DeactivateRequest, DeactivationImpact, ImpactArticle, ImpactOrder,
)
from ..schemas.instance import InstanceResponse
from ..services import deactivation, metrics
from ..services.admin import log_audit
from ..services.lifecycle import ensure_mutable, ensure_version
from ..services.locations import location_labels, physical_location_labels
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


def _validate_supplier(db: Session, supplier_id: int | None) -> None:
    """Der Beschaffungs-Default-Lieferant muss ein aktiver Lieferant sein (wie am Schritt)."""
    if supplier_id is None:
        return
    u = db.query(UserProfile).filter(
        UserProfile.id == supplier_id, UserProfile.is_active == True).first()
    if not u or u.role != "supplier":
        raise HTTPException(400, detail="Gewählter Benutzer ist kein aktiver Lieferant")


def _supplier_refs(db: Session, supplier_pks: set[int]) -> dict[int, tuple[str, int | None]]:
    """{UserProfile.id → (Anzeigename, Objektnummer)} für die Beschaffungs-Denormalisierung
    (batch, kein N+1 im Feed). ``display_name`` ist eine **@property** (keine Spalte) – daher die
    vollen Objekte laden und den Namen in Python bilden, NICHT in der Query selektieren
    (sonst ArgumentError „got <property object>")."""
    ids = {pk for pk in supplier_pks if pk}
    if not ids:
        return {}
    rows = db.query(UserProfile).filter(UserProfile.id.in_(ids)).all()
    return {u.id: (u.display_name, u.object_id) for u in rows}


def _price_ranges(db: Session, article_ids: list[int]) -> dict[int, tuple]:
    """Stückpreis (Bestellsumme ÷ Menge) je Artikel über akzeptierte Bestellungen –
    als ``(median, kleinster, grösster)``. Der Median braucht die Einzelwerte, darum
    wird hier nicht mehr in SQL aggregiert; die Zeilenzahl je Artikel ist klein."""
    if not article_ids:
        return {}
    rows = (
        db.query(PurchaseOrder.article_id, PurchaseOrder.order_total, PurchaseOrder.quantity)
        .filter(
            PurchaseOrder.article_id.in_(article_ids),
            PurchaseOrder.is_active == True,
            PurchaseOrder.order_total.isnot(None),
            PurchaseOrder.quantity > 0,
            PurchaseOrder.status.in_(_PRICED_STATUS),
        )
        .all()
    )
    per_article: dict[int, list] = {}
    for aid, total, qty in rows:
        per_article.setdefault(aid, []).append(total / qty)
    return {aid: metrics.spread(vals) for aid, vals in per_article.items()}


def _lead_time_ranges(db: Session, article_ids: list[int]) -> dict[int, tuple]:
    """Durchlaufzeit in Tagen (Freigabe → Abschluss) je Artikel über erledigte
    Aufträge – als ``(median, kürzeste, längste)``. Klein genug für Python."""
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
    per_article: dict[int, list] = {}
    for aid, released_at, completed_at in rows:
        days = (completed_at - released_at).total_seconds() / 86400.0
        if days >= 0:
            per_article.setdefault(aid, []).append(days)
    return {aid: metrics.spread(vals) for aid, vals in per_article.items()}


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
                 computed_weight=None, replaces_id: int | None = None,
                 supplier_ref: tuple | None = None) -> ArticleResponse:
    resp = ArticleResponse.model_validate(article)
    if price_range:
        resp.unit_cost_median, resp.unit_cost_low, resp.unit_cost_high = price_range
    elif article.landed_unit_cost is not None:
        # Ohne Bestellhistorie ist der letzte Einstandspreis der einzige Datenpunkt –
        # dann sind Median und Spanne derselbe Wert.
        resp.unit_cost_median = article.landed_unit_cost
        resp.unit_cost_low = article.landed_unit_cost
        resp.unit_cost_high = article.landed_unit_cost
    if lead_range:
        resp.lead_time_days_median, resp.lead_time_days_low, resp.lead_time_days_high = lead_range
    resp.computed_weight_kg = computed_weight
    resp.replaces_id = replaces_id
    # Beschaffungs-Default: Lieferantenname/Objektnummer denormalisieren (Anzeige/klickbar).
    if supplier_ref:
        resp.default_supplier_name, resp.default_supplier_object_id = supplier_ref
    return resp


def _single(db: Session, article: Article) -> ArticleResponse:
    """Vollständige Response eines einzelnen Artikels (inkl. Spannen + Vorgänger)."""
    return _to_response(
        article,
        _price_ranges(db, [article.id]).get(article.id),
        _lead_time_ranges(db, [article.id]).get(article.id),
        computed_weights(db, [article.id]).get(article.id),
        _predecessors(db, [article.object_id]).get(article.object_id),
        _supplier_refs(db, {article.default_supplier_id}).get(article.default_supplier_id),
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
    sup_refs = _supplier_refs(db, {a.default_supplier_id for a in articles})
    return [_to_response(a, ranges.get(a.id), leads.get(a.id), cweights.get(a.id),
                         preds.get(a.object_id), sup_refs.get(a.default_supplier_id)) for a in articles]


@router.post("", response_model=ArticleResponse, status_code=201)
async def create_article(
    data: ArticleCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    # Beschaffungs-Default konsistent halten: nur das zum Modus passende Quellfeld speichern.
    _validate_supplier(db, data.default_supplier_id)
    proc_mode = data.procurement_mode or "supplier"
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
        reorder_target=data.reorder_target,
        fixed_location_lat=data.fixed_location_lat,
        fixed_location_lng=data.fixed_location_lng,
        fixed_location_street=data.fixed_location_street,
        fixed_location_zip=data.fixed_location_zip,
        fixed_location_city=data.fixed_location_city,
        fixed_location_country=data.fixed_location_country,
        procurement_mode=proc_mode,
        default_supplier_id=data.default_supplier_id if proc_mode == "supplier" else None,
        default_webshop_url=data.default_webshop_url if proc_mode == "webshop" else None,
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


@router.get("/name-suggestions", response_model=list[ArticleNameSuggestion])
async def name_suggestions(
    q: str = "",
    limit: int = 8,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Intelligente Namensvorschläge (bereits verwendete/ähnliche Namen) beim Anlegen –
    freie Namensgebung, aber Dubletten werden vermieden. Ohne KI (lexikalisch, `services/
    article_names.py`). Muss VOR `/{object_id}` stehen (sonst würde die Zahl-Route greifen)."""
    from ..services import article_names
    return article_names.suggest(db, q, limit)


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
    # Logistik-Parameter (Meldebestand/Zielbestand, E) sind KEINE eingefrorene Spezifikation,
    # sondern operative Steuergrössen – auch am freigegebenen Artikel tunebar (analog zur
    # lebenden Verkaufs-Ebene). Vom Freeze-Check ausnehmen.
    _LIVE = {"safety_stock", "reorder_target"}
    ensure_mutable(article.status, {k: v for k, v in payload.items() if k not in _LIVE}, "Artikel")
    if "default_supplier_id" in payload:
        _validate_supplier(db, payload["default_supplier_id"])
    going_inactive = payload.get("status") == "inactive" and article.status != "inactive"
    # Inaktiv ist **endgültig**: ein deaktivierter Artikel kann NICHT reaktiviert werden
    # (die Identität ist abgeschlossen – Neustart = neuer Artikel/Nachfolger via «Ersetzen»).
    if payload.get("status") == "released" and article.status == "inactive":
        raise HTTPException(
            409,
            detail="Inaktive Artikel können nicht reaktiviert werden – bitte einen neuen Artikel anlegen (oder «Ersetzen»).",
        )
    # Freigabe nur mit hinterlegtem Prozess: Ohne Prozessschritt gäbe es nichts, was der
    # Artikel „kann" – die Freigabe friert Spezifikation UND Prozess gemeinsam ein.
    releasing = payload.get("status") == "released" and article.status == "draft"
    if releasing and not article_steps(db, article.id):
        raise HTTPException(
            400,
            detail="Ohne Prozessschritt kann der Artikel nicht freigegeben werden – bitte zuerst im Reiter «Prozess» einen Ablauf hinterlegen.",
        )
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
    # Beschaffungs-Default konsistent halten: nur das zum Modus passende Quellfeld behalten
    # (analog zum Beschaffungs-Prozessschritt), wenn Modus/Quelle angefasst wurde.
    if {"procurement_mode", "default_supplier_id", "default_webshop_url"} & set(payload):
        if article.procurement_mode == "supplier":
            article.default_webshop_url = None
        elif article.procurement_mode == "webshop":
            article.default_supplier_id = None
    # Freigabe-Gate: Fehlt einem Prozessschritt seine benötigte Konfiguration, ist keine Freigabe
    # möglich. Jeder Beschaffungs-Schritt braucht eine auflösbare Bezugsquelle – am Schritt selbst
    # (Lieferant/Webshop) ODER als Artikel-Default –, sonst könnte keine Bestellung entstehen.
    if releasing:
        from ..services.purchase import has_source
        if any(s.step_type == "purchase" and not has_source(s, article)
               for s in article_steps(db, article.id)):
            raise HTTPException(
                400,
                detail="Beschaffung unvollständig: Bitte für jeden Beschaffungs-Schritt eine Bezugsquelle "
                       "(Lieferant bzw. Webshop-Link) hinterlegen – am Schritt oder als Artikel-Standard "
                       "unter «Spezifikation → Beschaffung» –, bevor der Artikel freigegeben wird.")
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
    # Standort-Labels **batch** auflösen (statt einem Query je Instanz, N+1).
    loc_keys = [(r.location_type, r.location_id) for r in rows]
    loc_labels = location_labels(db, loc_keys)
    phys_labels = physical_location_labels(db, [k for k in loc_keys if k[0] == "instance"])
    out: list[InstanceResponse] = []
    for r in rows:
        resp = InstanceResponse.model_validate(r)
        resp.order_object_id = order_map.get(r.order_id)
        resp.article_name = article.name
        resp.location_label = loc_labels.get((r.location_type, r.location_id))
        if r.location_type == "instance":
            resp.physical_location_label = phys_labels.get((r.location_type, r.location_id))
        out.append(resp)
    return out
