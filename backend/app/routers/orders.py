from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, Process, PurchaseOrder, Sale, UserProfile
from ..models.base import utcnow
from ..schemas.inspection import InspectionUpdate
from ..schemas.movement import MovementUpdate
from ..schemas.order import OrderCreate, OrderResponse, OrderSummary, OrderUpdate
from ..schemas.purchase_order import PurchaseOrderUpdate
from ..schemas.resource import ResourceUpdate
from ..schemas.sale import SaleUpdate
from ..services import deactivation, processes as processes_svc, sale as sale_svc, subject
from ..services.admin import log_audit
from ..services.events import emit
from ..services.inspection import record_inspection
from ..services.lifecycle import ensure_mutable, ensure_version
from ..services.movement import record_movement
from ..services.objects import next_object_id
from ..services.orders import to_order_response, to_order_summaries, visible_orders
from ..services.purchase import apply_update as apply_purchase_update, instantiate_for_order
from ..services.resource import record_resource, reserve_resources

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])


def _get_staff_order(db: Session, object_id: int) -> Order:
    order = (
        db.query(Order)
        .filter(Order.object_id == object_id, Order.is_active == True)
        .first()
    )
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    return order


def _validate_article(db: Session, article_id: int | None) -> None:
    """Im Auftrag dürfen nur freigegebene Artikel referenziert werden."""
    if article_id is None:
        return
    art = db.query(Article).filter(Article.id == article_id, Article.is_active == True).first()
    if not art:
        raise HTTPException(400, detail="Artikel nicht gefunden")
    if art.status != "released":
        raise HTTPException(400, detail="Nur freigegebene Artikel können in einem Auftrag referenziert werden")


def _resolve_subject(db: Session, article_id, quantity, process_id, subject_instance_id):
    """Subjekt + Prozess eines Auftrags auflösen/validieren.

    Quelle ``instance`` (Prozess wirkt auf eine konkrete Instanz): der Artikel wird
    aus der Instanz abgeleitet, Menge = 1. Sonst zählt der gewählte (oder Default-)
    Prozess des Artikels. Liefert (article_id, quantity, process_id) – der Prozess
    wird auf den Default («Entstehung») aufgelöst, falls keiner gewählt wurde."""
    proc = processes_svc.get_process(db, process_id) if process_id else None
    source = proc.source if proc else "produce"
    if source == "instance":
        if not subject_instance_id:
            raise HTTPException(400, detail="Für diesen Prozess ist eine Instanz als Subjekt erforderlich")
        inst = db.query(Instance).filter(
            Instance.object_id == subject_instance_id, Instance.is_active == True).first()
        if not inst:
            raise HTTPException(400, detail="Subjekt-Instanz nicht gefunden")
        return inst.article_id, 1, process_id
    _validate_article(db, article_id)
    if proc and proc.article_id and proc.article_id != article_id and not proc.is_standard:
        raise HTTPException(400, detail="Der gewählte Prozess gehört nicht zu diesem Artikel")
    # Kein Prozess gewählt → Default-«Entstehung» des Artikels persistieren (Feed/Konsistenz).
    resolved = process_id
    if resolved is None and article_id:
        dp = processes_svc.default_process(db, article_id)
        resolved = dp.id if dp else None
    return article_id, quantity, resolved


@router.get("", response_model=list[OrderSummary])
async def list_orders(
    limit: int = Query(0, ge=0, le=1000, description="0 = keine Begrenzung; sonst Seitengröße"),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Schlanker Auftrags-Feed (ohne Prozess-Embeds). Das Detail kommt aus
    ``GET /orders/{id}``. Optional server-seitig paginierbar (limit/offset)."""
    q = visible_orders(db, user).order_by(Order.object_id.desc())
    if limit:
        q = q.offset(offset).limit(limit)
    return to_order_summaries(db, q.all())


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    article_id, quantity, process_id = _resolve_subject(
        db, data.article_id, data.quantity, data.process_id, data.subject_instance_id)
    order = Order(
        object_id=next_object_id(db, "order"),
        status="draft",
        article_id=article_id,
        quantity=quantity,
        desired_delivery_date=data.desired_delivery_date,
        process_id=process_id,
        subject_instance_id=data.subject_instance_id,
        recurrence_active=bool(data.recurrence_active),
        recurrence_interval_days=data.recurrence_interval_days,
        recurrence_lead_time_days=data.recurrence_lead_time_days or 0,
        recurrence_anchor=data.recurrence_anchor,
    )
    db.add(order)
    db.flush()
    log_audit(db, "orders", None, "Auftrag angelegt",
              current_user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.get("/{object_id}", response_model=OrderResponse)
async def get_order(
    object_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    order = visible_orders(db, user).filter(Order.object_id == object_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    return to_order_response(db, order)


@router.patch("/{object_id}", response_model=OrderResponse)
async def update_order(
    object_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    order = _get_staff_order(db, object_id)
    was_released = order.status == "released"

    payload = data.model_dump(exclude_unset=True)
    ensure_version(order, payload.pop("expected_updated_at", None))
    # Wiederkehr-Einstellung ändert nicht die Arbeit – auch nach Freigabe erlaubt.
    _RECURRENCE_KEYS = ("recurrence_active", "recurrence_interval_days",
                        "recurrence_lead_time_days", "recurrence_anchor")
    recurrence_payload = {k: payload.pop(k) for k in _RECURRENCE_KEYS if k in payload}
    ensure_mutable(order.status, payload, "Auftrag")
    for key, value in recurrence_payload.items():
        setattr(order, key, value)
    if "article_id" in payload:
        _validate_article(db, payload["article_id"])
    # Kein Reaktivieren von Aufträgen: die Physis ist weitergewandert → neuer Auftrag.
    if payload.get("status") == "released" and order.status == "inactive":
        raise HTTPException(409, detail="Auftrag kann nicht reaktiviert werden – bitte neuen Auftrag anlegen")

    for key, value in payload.items():
        old_val = getattr(order, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "orders", key, new_str, current_user.id,
                      object_id=order.object_id, old_value=old_str)
        setattr(order, key, value)

    # Freigabe (draft → released) stösst den gewählten Prozess an und stellt das
    # **Subjekt** her – je nach Prozess-Quelle: produce → neue Instanzen erzeugen,
    # stock → FIFO-Bestand wählen/reservieren, instance → die Instanz binden.
    if order.status == "released" and not was_released:
        if not order.article_id or not order.quantity:
            raise HTTPException(400, detail="Zur Freigabe sind Artikel und Menge erforderlich")
        if order.released_at is None:
            order.released_at = utcnow()   # Start der Durchlaufzeit
        subject.materialize_subject(db, order, current_user.id)
        instantiate_for_order(db, order, current_user.id)        # Beschaffung
        sale_svc.instantiate_for_order(db, order, current_user.id)  # Verkauf
        # Zu verbrauchende Komponenten für diesen Auftrag reservieren (FIFO),
        # damit sie kein anderer Auftrag mehr verbrauchen kann.
        reserve_resources(db, order, current_user.id)
        emit(db, "order.released", object_type="order", object_id=order.object_id,
             payload={"article_id": order.article_id, "quantity": order.quantity},
             actor_id=current_user.id)

    # Abbruch (released → inactive): Reservierungen freigeben + unfertige Instanzen deaktivieren.
    if order.status == "inactive" and was_released:
        deactivation.cancel_order_effects(db, order, current_user.id)

    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/replace", response_model=OrderResponse)
async def replace_order(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ersetzen: neuen Auftrag (Entwurf, gleicher Artikel/Menge) anlegen, verknüpfen,
    Original abbrechen. Liefert den **neuen** Auftrag zurück."""
    order = _get_staff_order(db, object_id)
    if order.status in ("inactive", "completed"):
        raise HTTPException(400, detail="Abgeschlossene/inaktive Aufträge können nicht ersetzt werden")
    new = deactivation.duplicate_order(db, order, current_user.id)
    log_audit(db, "orders", "replaced_by_id", str(new.object_id), current_user.id,
              object_id=order.object_id)
    order.replaced_by_id = new.object_id
    was_released = order.status == "released"
    order.status = "inactive"
    if was_released:
        deactivation.cancel_order_effects(db, order, current_user.id)
    db.commit()
    db.refresh(new)
    return to_order_response(db, new)


@router.patch("/{object_id}/purchase", response_model=OrderResponse)
async def update_order_purchase(
    object_id: int,
    data: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Beschaffungsschritt des Auftrags bearbeiten (rollenabhängig, läuft unter
    der Auftragsnummer – keine eigene Bestellnummer)."""
    order = visible_orders(db, user).filter(Order.object_id == object_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .first()
    )
    if not po:
        raise HTTPException(404, detail="Für diesen Auftrag existiert keine Bestellung")
    apply_purchase_update(db, po, data, user)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/sale", response_model=OrderResponse)
async def update_order_sale(
    object_id: int,
    data: SaleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Verkauf» (kaufmännisch): Bestätigung → Rechnung → Zahlung."""
    order = _get_staff_order(db, object_id)
    sale = (
        db.query(Sale)
        .filter(Sale.order_id == order.id, Sale.is_active == True)
        .first()
    )
    if not sale:
        raise HTTPException(404, detail="Für diesen Auftrag existiert kein Verkauf")
    sale_svc.apply_update(db, sale, data, current_user)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/inspection", response_model=OrderResponse)
async def update_order_inspection(
    object_id: int,
    data: InspectionUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Eingangskontrolle»: Stichprobenergebnis erfassen (passed/failed)."""
    order = _get_staff_order(db, object_id)
    record_inspection(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/movement", response_model=OrderResponse)
async def update_order_movement(
    object_id: int,
    data: MovementUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Bewegung»: Instanzen einlagern/umlagern (Zielstandort je Instanz)."""
    order = _get_staff_order(db, object_id)
    record_movement(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/resource", response_model=OrderResponse)
async def update_order_resource(
    object_id: int,
    data: ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Ressource»: Verbrauch (FIFO, Chargen-Teilentnahme) + Betriebsmittel."""
    order = _get_staff_order(db, object_id)
    record_resource(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)
