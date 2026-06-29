from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, PurchaseOrder, Sale, UserProfile
from ..models.base import utcnow
from ..schemas.disposal import ScrapUpdate
from ..schemas.inspection import InspectionUpdate
from ..schemas.movement import MovementUpdate
from ..schemas.order import OrderCreate, OrderDeviationCreate, OrderResponse, OrderSummary, OrderUpdate
from ..schemas.purchase_order import PurchaseOrderUpdate
from ..schemas.resource import ResourceUpdate
from ..schemas.sale import SaleUpdate
from ..services import deactivation, deviation, process, sale as sale_svc, subject
from ..services.admin import log_audit
from ..services.events import emit
from ..services.inspection import record_inspection
from ..services.lifecycle import ensure_mutable, ensure_version
from ..services.movement import record_movement
from ..services.scrap import record_scrap
from ..services.objects import next_object_id
from ..services.orders import to_order_response, to_order_summaries, visible_orders
from ..services.purchase import apply_update as apply_purchase_update, instantiate_for_order
from ..services.reservation import free_qty, reserved_for
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


def _validate_pins(db: Session, order: Order, object_ids: list[int]) -> list[Instance]:
    """Zu fixierende (gepinnte) Instanzen prüfen: Artikel des Auftrags, am Lager verfügbar
    und nicht bereits **fest reserviert** von einem anderen Auftrag. Die Festlegung im
    Entwurf ist nur eine **Vormerkung** – sie sperrt die Instanz NICHT; **scharf
    reserviert** wird erst bei der Freigabe. Mehrere Entwürfe dürfen dieselbe Instanz
    vormerken; wer zuerst freigibt, reserviert, der zweite scheitert dann an der Prüfung."""
    # Abweichung (Unter-Auftrag) wirkt auf bereits «in der Hand» befindliche Instanzen –
    # diese dürfen jeden Verbleib haben (in Arbeit, am Lager, …) und sind nicht zu reservieren.
    devi = subject.is_deviation(order)
    insts: list[Instance] = []
    for oid in object_ids:
        i = db.query(Instance).filter(Instance.object_id == oid, Instance.is_active == True).first()
        if not i:
            raise HTTPException(400, detail=f"Instanz {oid} nicht gefunden")
        if order.article_id and i.article_id != order.article_id:
            raise HTTPException(400, detail="Es sind nur Instanzen desselben Artikels wählbar")
        if not devi and not (i.quality == "passed" and i.disposition == "in_stock"):
            raise HTTPException(400, detail=f"Instanz {oid} ist nicht am Lager verfügbar")
        if not devi and free_qty(i) + reserved_for(i, order.id) < i.quantity:
            raise HTTPException(409, detail=f"Instanz {oid} ist bereits für einen anderen Auftrag reserviert")
        insts.append(i)
    return insts


def _set_chosen_instances(db: Session, order: Order, object_ids: list[int]) -> None:
    """Die **fixierten** (gepinnten) Subjekt-Instanzen eines Entwurfs neu setzen: bisherige
    lösen, neue prüfen und **vormerken** (``subject_of_order_id``). KEINE feste Reservierung –
    die wird erst bei der Freigabe scharf. Artikel + Menge bleiben unverändert (Anker)."""
    for prev in (
        db.query(Instance)
        .filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
        .all()
    ):
        prev.subject_of_order_id = None
    if not object_ids:
        return
    insts = _validate_pins(db, order, object_ids)
    pinned_qty = sum(i.quantity for i in insts)
    if order.quantity and pinned_qty > order.quantity:
        raise HTTPException(
            400, detail=f"Es sind mehr Instanzen fixiert ({pinned_qty}) als die Auftragsmenge ({order.quantity})")
    for i in insts:
        i.subject_of_order_id = order.id              # nur vormerken (Reservierung bei Freigabe)


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
    order = Order(
        object_id=next_object_id(db, "order"),
        status="draft",
        desired_delivery_date=data.desired_delivery_date,
        recurrence_active=bool(data.recurrence_active),
        recurrence_interval_days=data.recurrence_interval_days,
        recurrence_lead_time_days=data.recurrence_lead_time_days or 0,
        recurrence_anchor=data.recurrence_anchor,
    )
    # Anker ist IMMER der Artikel + Menge. Was damit geschieht (Erzeugung vs. Operation
    # am Bestand, FIFO/fixiert) ergibt sich aus dem Ablauf, der danach im Entwurf
    # definiert wird – nicht aus der Anlage.
    _validate_article(db, data.article_id)             # nur freigegebene Artikel
    order.article_id = data.article_id
    order.quantity = data.quantity
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
    # Vorgewählte Subjekt-Instanzen (Mehrfachauswahl) gesondert – kein Modellfeld.
    new_instances = payload.pop("instance_object_ids", None)
    # Inhalte – inklusive der Wiederkehr-Einstellung – sind NUR im Entwurf änderbar.
    # Nach der Freigabe ist der Auftrag „scharf"; ein einmal freigegebener Auftrag
    # lässt sich nicht mehr nachträglich auf wiederkehrend umstellen (ensure_mutable
    # erlaubt dann nur noch status/is_active).
    ensure_mutable(order.status, payload, "Auftrag")
    if new_instances is not None:
        if order.status != "draft":
            raise HTTPException(409, detail="Instanzen lassen sich nur im Entwurf ändern")
        _set_chosen_instances(db, order, new_instances)
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

    # Freigabe (draft → released) stösst den Prozess an und stellt das Subjekt her.
    # Anker ist immer Artikel + Menge:
    #   produce – KEIN eigener Ablauf → der **Artikel-Prozess** läuft, neue Instanzen entstehen.
    #   stock   – eigener Ablauf → er läuft auf ``quantity`` Instanzen des Artikels
    #             (FIFO ab Lager, optional durch fixierte Instanzen ergänzt).
    if order.status == "released" and not was_released:
        if not order.article_id or not order.quantity:
            raise HTTPException(400, detail="Zur Freigabe sind Artikel und Menge erforderlich")
        if subject.subject_kind(db, order) == "produce":
            # Vorbedingung: der Artikel (Spezifikation + Prozess) muss freigegeben sein.
            art = db.query(Article).filter(Article.id == order.article_id).first()
            if not art or art.status != "released":
                raise HTTPException(
                    400,
                    detail="Der Artikel muss freigegeben sein, bevor der Prozess gestartet werden kann",
                )
        elif not process.order_step_infos(db, order):
            raise HTTPException(400, detail="Bitte zuerst mindestens einen Prozessschritt definieren")
        if order.released_at is None:
            order.released_at = utcnow()   # Start der Durchlaufzeit
        subject.materialize_subject(db, order, current_user.id)
        instantiate_for_order(db, order, current_user.id)        # Beschaffung
        sale_svc.instantiate_for_order(db, order, current_user.id)  # Verkauf
        # Zu verbrauchende Komponenten für diesen Auftrag reservieren (FIFO).
        reserve_resources(db, order, current_user.id)
        emit(db, "order.released", object_type="order", object_id=order.object_id,
             payload={"article_id": order.article_id, "quantity": order.quantity},
             actor_id=current_user.id)
        # War das ein Abbruch-Folgeauftrag? → mit seiner Freigabe das Original abbrechen
        # (die übernommenen Instanzen bleiben erhalten und gehören jetzt diesem Auftrag).
        if order.parent_order_id is not None:
            deviation.apply_abort_on_release(db, order, current_user.id)

    # Ein freigegebener Auftrag wird NICHT direkt inaktiv gesetzt – der Abbruch läuft über
    # «Abbrechen» (POST /abort), das einen Folgeauftrag erzwingt (keine herrenlosen Teile).
    if order.status == "inactive" and was_released:
        raise HTTPException(
            409, detail="Bitte «Abbrechen» verwenden – ein freigegebener Auftrag braucht einen Folgeauftrag")

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


@router.post("/{object_id}/abort", response_model=OrderResponse)
async def abort_order(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Abbruch eines Auftrags. Ein **Entwurf** wird direkt inaktiv. Ein **freigegebener**
    Auftrag mit im Prozess befindlichen Instanzen erzwingt einen **Folgeauftrag**
    (Abweichung): dieser übernimmt die Instanzen; das Original wird erst inaktiv, wenn der
    Folgeauftrag freigegeben ist. Liefert den **Folgeauftrag** (bzw. das Original) zurück."""
    order = _get_staff_order(db, object_id)
    if order.status in ("inactive", "completed"):
        raise HTTPException(400, detail="Auftrag ist bereits abgeschlossen/inaktiv")
    if order.abort_into_id:
        raise HTTPException(409, detail="Für diesen Auftrag ist bereits ein Folgeauftrag offen")

    # Entwurf oder ein Auftrag ohne (noch aktive) im Prozess befindliche Instanzen → direkt
    # inaktiv. Verschrottete/terminale Teile zählen nicht als «zu retten».
    if order.status == "draft" or not subject.order_active_instances(db, order):
        was_released = order.status == "released"
        order.status = "inactive"
        if was_released:
            deactivation.cancel_order_effects(db, order, current_user.id)
        db.commit()
        db.refresh(order)
        return to_order_response(db, order)

    follow = deviation.create_abort_followup(db, order, current_user.id)
    db.commit()
    db.refresh(follow)
    return to_order_response(db, follow)


@router.post("/{object_id}/deviation", response_model=OrderResponse)
async def open_deviation(
    object_id: int,
    data: OrderDeviationCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """«Abweichung melden» zu einem Auftrag (Fehler/Reklamation/Nacharbeit – ein Konzept):
    legt einen **Unter-Auftrag** auf die betroffenen Instanzen an (Instanz-Ebene mit Auswahl,
    sonst Prozess-Ebene über alle Instanzen). Der Eltern-Auftrag pausiert, bis die Abweichung
    geklärt ist. Liefert die neue Abweichung zurück (man definiert dort die Auflösung)."""
    parent = _get_staff_order(db, object_id)
    if parent.status not in ("released", "completed"):
        raise HTTPException(400, detail="Abweichungen lassen sich nur an einem laufenden/abgeschlossenen Auftrag eröffnen")
    devi = deviation.create_deviation(db, parent, data.instance_object_ids, current_user.id)
    db.commit()
    db.refresh(devi)
    return to_order_response(db, devi)


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


@router.patch("/{object_id}/scrap", response_model=OrderResponse)
async def update_order_scrap(
    object_id: int,
    data: ScrapUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Verschrotten»: gewählte Instanzen ausschleusen (disposition='scrapped')."""
    order = _get_staff_order(db, object_id)
    record_scrap(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)
