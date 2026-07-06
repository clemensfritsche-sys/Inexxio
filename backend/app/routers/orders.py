from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, OrderLine, UserProfile
from ..schemas.disposal import ScrapUpdate
from ..schemas.document import DocumentUpdate
from ..schemas.inspection import InspectionUpdate
from ..schemas.movement import MovementUpdate
from ..schemas.order import (
    OrderCoverStock, OrderCreate, OrderDeviationCreate, OrderLineCreate, OrderLinePins,
    OrderResponse, OrderSummary, OrderUpdate,
)
from ..schemas.purchase_order import PurchaseOrderUpdate
from ..schemas.resource import ResourceUpdate
from ..schemas.sale import SaleUpdate
from ..services import deactivation, deviation, order_lines as order_lines_svc, process, recovery, refund as refund_svc, sale as sale_svc, subject, supply
from ..services.admin import log_audit
from ..services.document import record_document
from ..services.inspection import record_inspection
from ..services.lifecycle import ensure_mutable, ensure_version
from ..services.movement import record_movement
from ..services.scrap import record_scrap
from ..services.objects import next_object_id
from ..services.orders import release_order, to_order_response, to_order_summaries, visible_orders
from ..services.purchase import apply_update_bulk as apply_purchase_update_bulk, instantiate_for_order as instantiate_purchase
from ..services.reservation import free_qty, reserved_for
from ..services.resource import record_resource

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


def _assert_not_paused(db: Session, order: Order) -> None:
    """Ein durch eine offene Abweichung **pausierter** Auftrag darf nicht weiterverarbeitet
    werden – erst die Abweichung klären. (Die Abweichung selbst pausiert nicht und läuft.)"""
    if process._is_paused_by_deviation(db, order):
        raise HTTPException(
            409,
            detail="Auftrag pausiert: erst die offene Abweichung abschliessen, dann den Prozess fortsetzen.",
        )


def _validate_article(db: Session, article_id: int | None) -> None:
    """Im Auftrag dürfen nur freigegebene Artikel referenziert werden."""
    if article_id is None:
        return
    art = db.query(Article).filter(Article.id == article_id, Article.is_active == True).first()
    if not art:
        raise HTTPException(400, detail="Artikel nicht gefunden")
    if art.status != "released":
        raise HTTPException(400, detail="Nur freigegebene Artikel können in einem Auftrag referenziert werden")


def _assert_quantity_serialization(db: Session, article_id: int | None, quantity) -> None:
    """Einzelteil-Artikel (``serialization='unit'``) dürfen nur GANZE Stück tragen – 2.5
    Schrauben gibt es nicht (jede Instanz ist ein Stück). Chargen (``batch``) dürfen
    Bruchmengen tragen (2.5 kg, 0.75 m²). Die Prüfung braucht den Artikel, darum hier im
    Router statt im Schema."""
    from ..services.quantity import is_whole
    if article_id is None or quantity is None:
        return
    art = db.query(Article).filter(Article.id == article_id).first()
    if art and art.serialization == "unit" and not is_whole(quantity):
        raise HTTPException(
            400,
            detail=f"«{art.name}» wird als Einzelteil geführt – die Menge muss eine ganze Zahl sein "
                   "(Bruchmengen nur bei Chargen-Artikeln, z. B. kg/m²/l).")


def _validate_pins(db: Session, order: Order, object_ids: list[int]) -> list[Instance]:
    """Zu fixierende (gepinnte) Instanzen prüfen: Artikel des Auftrags, am Lager verfügbar
    und nicht bereits **fest reserviert** von einem anderen Auftrag. Die Festlegung im
    Entwurf ist nur eine **Vormerkung** – sie sperrt die Instanz NICHT; **scharf
    reserviert** wird erst bei der Freigabe. Mehrere Entwürfe dürfen dieselbe Instanz
    vormerken; wer zuerst freigibt, reserviert, der zweite scheitert dann an der Prüfung."""
    # Fixiertes Subjekt (keine Stock-Checks, jeder Verbleib): eine **Abweichung** (Unter-Auftrag)
    # ODER eine **verkaufte** Instanz – letztere macht den Auftrag zur **Retoure/Erstattung**
    # (siehe ``_set_chosen_instances``). Beide sind bereits «in der Hand»/verkauft und werden
    # nicht reserviert.
    devi = subject.is_deviation(order)
    insts: list[Instance] = []
    for oid in object_ids:
        i = db.query(Instance).filter(Instance.object_id == oid, Instance.is_active == True).first()
        if not i:
            raise HTTPException(400, detail=f"Instanz {oid} nicht gefunden")
        if order.article_id and i.article_id != order.article_id:
            raise HTTPException(400, detail="Es sind nur Instanzen desselben Artikels wählbar")
        if devi or i.disposition == "sold":
            insts.append(i)           # fixiertes Subjekt (Abweichung/Retoure) – ohne Stock-Checks
            continue
        if not (i.quality == "passed" and i.disposition == "in_stock"):
            raise HTTPException(400, detail=f"Instanz {oid} ist nicht am Lager verfügbar")
        if free_qty(i) + reserved_for(i, order.id) < i.quantity:
            raise HTTPException(409, detail=f"Instanz {oid} ist bereits für einen anderen Auftrag reserviert")
        insts.append(i)
    return insts


def _clear_return_marker(order: Order) -> None:
    """Retoure-Markierung wieder aufheben (wenn die Auswahl auf Lager-Instanzen zurückgeht)."""
    if order.reason == "return":
        order.reason = None
        order.parent_order_id = None


def _set_chosen_instances(db: Session, order: Order, object_ids: list[int]) -> None:
    """Die **fixierten** (gepinnten) Subjekt-Instanzen eines Entwurfs neu setzen: bisherige
    lösen, neue prüfen und **vormerken** (``subject_of_order_id``). KEINE feste Reservierung –
    die wird erst bei der Freigabe scharf.

    **Verkaufte Instanzen** in der Auswahl machen den Auftrag zur **Retoure/Erstattung**
    (`reason='return'` + `parent_order_id`=Original-Verkauf, abgeleitet) – ganz normal über
    dieselbe «Instanz wählen»-Auswahl, ohne eigene Sonder-Karte. Lager- und verkaufte Instanzen
    lassen sich nicht mischen (Verkauf vs. Erstattung sind gegensätzliche Geldrichtungen)."""
    for prev in (
        db.query(Instance)
        .filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
        .all()
    ):
        prev.subject_of_order_id = None
    if not object_ids:
        _clear_return_marker(order)
        return
    insts = _validate_pins(db, order, object_ids)
    sold = [i for i in insts if i.disposition == "sold"]
    if sold and len(sold) != len(insts):
        raise HTTPException(
            400, detail="Bitte entweder verkaufte Instanzen (Retoure/Erstattung) ODER Lager-Instanzen "
                        "wählen – nicht gemischt")
    if sold:
        # Retoure: Original-Verkauf ableiten (Grundlage der Gutschrift) + Auftrag markieren.
        parent = refund_svc.original_sale_order(db, sold)
        order.reason = "return"
        order.parent_order_id = parent.object_id
        art_ids = {i.article_id for i in sold}
        if len(art_ids) == 1:
            order.article_id = next(iter(art_ids))
            order.quantity = len(sold)
    else:
        _clear_return_marker(order)
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


def _pin_line_instances(db: Session, order: Order, article_id: int, quantity: int,
                        object_ids: list[int]) -> None:
    """Fixierte Instanzen EINER Position eines Mehrpositionen-Auftrags vormerken – wie
    ``_set_chosen_instances`` für den Einzel-Artikel-Auftrag, nur gegen die Menge/den
    Artikel DIESER Position statt des ganzen Auftrags geprüft (mehrere Artikel können
    unter demselben Sammel-Auftrag je eigene Fixierungen tragen). Löst zuerst die
    bisherige Fixierung dieser Position (idempotent, wie beim Einzel-Artikel-Auftrag)."""
    for prev in db.query(Instance).filter(
        Instance.subject_of_order_id == order.id, Instance.article_id == article_id,
        Instance.is_active == True,
    ).all():
        prev.subject_of_order_id = None
    if not object_ids:
        return
    insts: list[Instance] = []
    for oid in object_ids:
        i = db.query(Instance).filter(Instance.object_id == oid, Instance.is_active == True).first()
        if not i:
            raise HTTPException(400, detail=f"Instanz {oid} nicht gefunden")
        if i.article_id != article_id:
            raise HTTPException(400, detail="Es sind nur Instanzen desselben Artikels wie die Position wählbar")
        if not (i.quality == "passed" and i.disposition == "in_stock"):
            raise HTTPException(400, detail=f"Instanz {oid} ist nicht am Lager verfügbar")
        if free_qty(i) + reserved_for(i, order.id) < i.quantity:
            raise HTTPException(409, detail=f"Instanz {oid} ist bereits für einen anderen Auftrag reserviert")
        insts.append(i)
    pinned_qty = sum(i.quantity for i in insts)
    if pinned_qty > quantity:
        raise HTTPException(
            400, detail=f"Es sind mehr Instanzen fixiert ({pinned_qty}) als die Positionsmenge ({quantity})")
    for i in insts:
        i.subject_of_order_id = order.id


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
    # definiert wird – nicht aus der Anlage. Weitere Artikel lassen sich jederzeit über
    # POST .../lines ergänzen (Mehrpositionen – siehe unten).
    _validate_article(db, data.article_id)             # nur freigegebene Artikel
    _assert_quantity_serialization(db, data.article_id, data.quantity)  # unit → ganze Zahl
    order.article_id = data.article_id
    order.quantity = data.quantity
    db.add(order)
    db.flush()
    log_audit(db, "orders", None, "Auftrag angelegt",
              current_user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/lines", response_model=OrderResponse, status_code=201)
async def add_order_line(
    object_id: int,
    data: OrderLineCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Eine weitere Position zu einem **Entwurf** hinzufügen – jederzeit möglich, auch
    nachdem der Auftrag schon gespeichert wurde (nicht nur bei der Anlage). Macht den
    Auftrag (falls noch nicht) zu einem **Mehrpositionen**-Auftrag: «Herstellen» scheidet
    dann aus (``subject.subject_kind`` erzwingt ``stock``); Ablauf/Ziel-Karten bleiben
    sonst unverändert (nur «Aus Lager»/«Instanz wählen», jetzt über mehrere Artikel)."""
    order = _get_staff_order(db, object_id)
    if order.status != "draft":
        raise HTTPException(400, detail="Weitere Positionen sind nur im Entwurf möglich")
    _validate_article(db, data.article_id)
    _assert_quantity_serialization(db, data.article_id, data.quantity)  # unit → ganze Zahl
    existing_lines = order_lines_svc.lines_for(db, order)
    # FIX: Doppelte Positionen desselben Artikels zerlegen die gesamte Mehrpositionen-Logik,
    # die je Auftrag nach ``article_id`` schlüsselt: die FIFO-Allokation zählte die Instanzen
    # der ersten Position bei der zweiten als «gepinnt» mit (Unter-Reservierung), und
    # Beschaffung/Verkauf legen je Artikel nur EINE Fachzeile an – die zweite Position wäre
    # still weder bestellt noch verrechnet worden. Menge stattdessen an der Position anpassen.
    existing_article_ids = {l.article_id for l in existing_lines} | (
        {order.article_id} if order.article_id else set())
    if data.article_id in existing_article_ids:
        raise HTTPException(
            400, detail="Dieser Artikel ist bereits eine Position – bitte dort die Menge anpassen")

    # Die Abo-Mischungsregel betrifft nur den VERKAUF (Stripe: ein Checkout ist entweder
    # Einmalkauf oder Abo) – sie gehört daher ans Hinzufügen des Sales-Prozessschritts
    # (``article_process.py: _create``), NICHT hierher: eine weitere Position anzulegen,
    # die z. B. nur bewegt oder geprüft werden soll, hat mit Verkaufspreisen nichts zu tun
    # und darf nicht blockiert werden. Existiert für diesen Auftrag aber BEREITS ein
    # Verkaufsschritt, würde die neue Position ihn sonst nachträglich unbemerkt kaputt
    # machen – dagegen sichert dieser Check gezielt ab.
    if process.has_step(db, order, "sale"):
        sale_svc.assert_sale_compatible(db, existing_article_ids | {data.article_id})

    if order.article_id is not None:
        # Erste zusätzliche Position: den bisherigen Einzel-Artikel-Anker in eine
        # gewöhnliche Position umwandeln (die Instanzen-/Reservierungs-Historie bleibt
        # unangetastet – nur die Bedarfs-Darstellung wechselt).
        db.add(OrderLine(order_id=order.id, article_id=order.article_id,
                         quantity=order.quantity, position=0))
        order.article_id = None
        order.quantity = None
        db.flush()
        existing_lines = order_lines_svc.lines_for(db, order)
    next_pos = (max((l.position for l in existing_lines), default=-1)) + 1
    line = OrderLine(order_id=order.id, article_id=data.article_id, quantity=data.quantity, position=next_pos)
    db.add(line)
    db.flush()
    new_art = db.query(Article).filter(Article.id == data.article_id).first()
    log_audit(db, "orders", None,
              f"Position hinzugefügt ({data.quantity}× Artikel {new_art.object_id if new_art else data.article_id})",
              current_user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.delete("/{object_id}/lines/{line_id}", response_model=OrderResponse)
async def remove_order_line(
    object_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Eine Position eines Mehrpositionen-Auftrags entfernen (nur im Entwurf)."""
    order = _get_staff_order(db, object_id)
    if order.status != "draft":
        raise HTTPException(400, detail="Positionen lassen sich nur im Entwurf entfernen")
    line = db.query(OrderLine).filter(
        OrderLine.id == line_id, OrderLine.order_id == order.id, OrderLine.is_active == True).first()
    if not line:
        raise HTTPException(404, detail="Position nicht gefunden")
    remaining = order_lines_svc.lines_for(db, order)
    if len(remaining) <= 1:
        raise HTTPException(400, detail="Die letzte Position kann nicht entfernt werden – bitte den Auftrag abbrechen")
    for inst in db.query(Instance).filter(
        Instance.subject_of_order_id == order.id, Instance.article_id == line.article_id,
        Instance.is_active == True,
    ).all():
        inst.subject_of_order_id = None
    line.is_active = False
    db.flush()
    # Bleibt nur noch EINE Position, wird der Auftrag wieder ein gewöhnlicher Einzel-Artikel-
    # Auftrag (symmetrisch zur ersten Zusatz-Position, die den Anker in eine Position umwandelt):
    # ``article_id``/``quantity`` zurück an den Auftrag, die verbleibende Position auflösen. So
    # aktualisieren sich die Ziel-Karten korrekt (Herstellen wieder möglich, kein `stock`-Zwang).
    left = order_lines_svc.lines_for(db, order)
    if len(left) == 1:
        anchor = left[0]
        order.article_id = anchor.article_id
        order.quantity = anchor.quantity
        anchor.is_active = False   # gepinnte Instanzen bleiben (subject_of_order_id = order.id)
    log_audit(db, "orders", None, "Position entfernt", current_user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/lines/{line_id}", response_model=OrderResponse)
async def set_order_line_pins(
    object_id: int,
    line_id: int,
    data: OrderLinePins,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Fixierte Instanzen EINER Position setzen (statt FIFO) – «Instanz wählen» je Artikel
    eines Mehrpositionen-Auftrags, analog ``instance_object_ids`` am Einzel-Artikel-Auftrag."""
    order = _get_staff_order(db, object_id)
    if order.status != "draft":
        raise HTTPException(400, detail="Instanzen lassen sich nur im Entwurf fixieren")
    line = db.query(OrderLine).filter(
        OrderLine.id == line_id, OrderLine.order_id == order.id, OrderLine.is_active == True).first()
    if not line:
        raise HTTPException(404, detail="Position nicht gefunden")
    _pin_line_instances(db, order, line.article_id, line.quantity, data.instance_object_ids)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


def _ensure_step_facts(db: Session, order: Order, user: UserProfile) -> None:
    """Selbstheilung beim Lesen: fehlende **Beschaffungs-/Verkaufsbelege** eines freigegebenen
    Auftrags idempotent nachziehen, damit die Prozessschritt-Details IMMER erscheinen (kein
    leeres Panel, falls ein Beleg aus irgendeinem Grund nicht bei der Freigabe entstand).
    Nur Personal; nur purchase/sale (diese werden bei der Freigabe instanziiert – die übrigen
    Fachzeilen entstehen erst bei der Ausführung und fehlen legitim)."""
    if order.status != "released" or user.role not in ("admin", "employee"):
        return
    created = instantiate_purchase(db, order, user.id)
    created += sale_svc.instantiate_for_order(db, order, user.id)
    if created:
        db.commit()


@router.get("/{object_id}", response_model=OrderResponse)
async def get_order(
    object_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    order = visible_orders(db, user).filter(Order.object_id == object_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    _ensure_step_facts(db, order, user)   # fehlende Beschaffungs-/Verkaufsbelege nachziehen
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
    if ("article_id" in payload or "quantity" in payload) and order.article_id is None \
            and order_lines_svc.lines_for(db, order):
        # Ein Mehrpositionen-Auftrag hat seinen Bedarf auf ``order_lines`` – Artikel/Menge
        # nachträglich am Auftrag selbst zu setzen würde ihn inkonsistent (verwaiste
        # Positionen) auf einen Einzel-Artikel-Auftrag umbiegen.
        raise HTTPException(
            400, detail="Bei einem Mehrpositionen-Auftrag sind Artikel/Menge nicht direkt editierbar")
    if "article_id" in payload:
        _validate_article(db, payload["article_id"])
    if "quantity" in payload:
        _assert_quantity_serialization(db, payload.get("article_id", order.article_id), payload["quantity"])
    # Kein Reaktivieren von Aufträgen: die Physis ist weitergewandert → neuer Auftrag.
    if payload.get("status") == "released" and order.status == "inactive":
        raise HTTPException(409, detail="Auftrag kann nicht reaktiviert werden – bitte neuen Auftrag anlegen")
    # FIX: Status-Zustandsmaschine – vorher fiel jeder nicht explizit geprüfte Wechsel in die
    # generische setattr-Schleife: ein Entwurf liess sich direkt auf «completed» setzen (ohne
    # Schritte/completed_at) und ein abgeschlossener/inaktiver Auftrag auf «draft» zurückholen
    # (und danach erneut freigeben – Umgehung von «kein Reaktivieren»). Erlaubte manuelle
    # Wechsel sind NUR draft→released (Freigabe) und draft/released→inactive (unten geregelt);
    # «completed» leitet ausschliesslich das System ab (recompute_completion).
    new_status = payload.get("status")
    if new_status and new_status != order.status:
        if new_status == "completed":
            raise HTTPException(400, detail="«Abgeschlossen» wird vom System abgeleitet, wenn alle Schritte erledigt sind")
        if order.status in ("completed", "inactive"):
            raise HTTPException(409, detail="Ein abgeschlossener/inaktiver Auftrag ist endgültig – bitte neuen Auftrag anlegen")
        if order.status == "released" and new_status == "draft":
            raise HTTPException(409, detail="Ein freigegebener Auftrag kann nicht in den Entwurf zurück – bitte «Abbrechen» verwenden")

    # Freigabe (draft → released) läuft AUSSCHLIESSLICH über ``release_order`` – dieser Pfad setzt
    # den Status selbst. Den Status hier NICHT vorab über die generische Schleife setzen: sonst ist
    # der Auftrag beim Aufruf bereits „released", ``release_order`` kehrt wegen „nicht mehr draft"
    # sofort zurück und es entsteht KEIN Subjekt – keine Instanzen, keine Objektnummern (stiller
    # Blindgänger). Der Statuswechsel wird nach erfolgreicher Freigabe protokolliert.
    wants_release = payload.get("status") == "released" and not was_released
    if wants_release:
        payload.pop("status")

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
    if wants_release:
        is_multiline = order.article_id is None and bool(order_lines_svc.lines_for(db, order))
        # Eine Abweichung ODER Retoure (Unter-Auftrag) hat ihr Subjekt bereits über fixierte
        # Instanzen (nicht über order_lines) – erbt bei einem Mehrpositionen-Eltern-Auftrag
        # dessen article_id=NULL, OHNE selbst eine Mehrpositionen-Struktur zu sein. Sie braucht
        # daher WEDER article_id/quantity NOCH order_lines zur Freigabe.
        if not is_multiline and not subject.is_fixed_subject(order) and (not order.article_id or not order.quantity):
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
        # Einheitliche Freigabe (setzt draft → released selbst): Subjekt herstellen (Fehlmenge ist
        # KEIN Fehler – der Schritt wird «blockiert» und über «Nachschub anlegen» gedeckt),
        # Beschaffung/Verkauf instanziieren, Komponenten reservieren, Abbruch-Folgeauftrag wirksam
        # machen.
        release_order(db, order, current_user.id)
        log_audit(db, "orders", "status", "released", current_user.id,
                  object_id=order.object_id, old_value="draft")

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
    if order.article_id is None and order_lines_svc.lines_for(db, order):
        raise HTTPException(400, detail="Ein Mehrpositionen-Auftrag kann (noch) nicht ersetzt werden")
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


@router.post("/{object_id}/revoke", response_model=OrderResponse)
async def revoke_followup(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """«Abbruch zurücknehmen / Folgeauftrag verwerfen»: einen noch im **Entwurf** befindlichen
    Folgeauftrag (Abbruch/Abweichung) zurücknehmen. Das Original läuft danach **unverändert**
    weiter (kein Vollzug, Reservierungen blieben erhalten). ``object_id`` = der Folgeauftrag.
    Liefert den wieder laufenden Eltern-Auftrag zurück."""
    followup = _get_staff_order(db, object_id)
    parent = deviation.revoke(db, followup, current_user.id)
    db.commit()
    target = parent or followup
    db.refresh(target)
    return to_order_response(db, target)


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
    if not data.instance_object_ids:
        # **Auftragsebene** (alle Instanzen): nur an einem LAUFENDEN Auftrag – ist der Prozess
        # abgeschlossen, gibt es nichts mehr am Auftrag selbst abzuweichen.
        if parent.status != "released":
            raise HTTPException(400, detail="Auf Auftragsebene lässt sich eine Abweichung nur an einem laufenden Auftrag melden")
    elif parent.status not in ("released", "completed"):
        # **Instanz-Ebene**: auch nach Abschluss möglich (z. B. spätere Reklamation eines Teils).
        raise HTTPException(400, detail="Abweichungen lassen sich nur an einem laufenden/abgeschlossenen Auftrag eröffnen")
    devi = deviation.create_deviation(db, parent, data.instance_object_ids, current_user.id)
    db.commit()
    db.refresh(devi)
    return to_order_response(db, devi)


@router.post("/{object_id}/supply", response_model=OrderResponse)
async def create_supply(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """«Nachschub anlegen»: für jeden ungedeckten Bedarf (blockierter Schritt) dieses Auftrags
    einen **Nachschub-Unter-Auftrag** anlegen + freigeben, der die Fehlmenge produziert/beschafft
    (rekursiv über die Stückliste). Bei Abschluss wird der Nachschub an diesen Auftrag gepinnt
    und der blockierte Schritt von selbst wieder aktiv. Idempotent. Liefert den Auftrag zurück."""
    order = _get_staff_order(db, object_id)
    if order.status != "released":
        raise HTTPException(400, detail="Nachschub kann nur für einen freigegebenen Auftrag angelegt werden")
    supply.ensure_supply(db, order, current_user.id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/cover-stock", response_model=OrderResponse)
async def cover_stock(
    object_id: int,
    data: OrderCoverStock,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """«Aus Lager decken» / «Andere Instanz wählen»: die offene Subjekt-Fehlmenge eines
    blockierten Schritts aus **vorhandenem** Lagerbestand decken – FIFO (ohne Auswahl) oder
    gezielt gewählte Instanzen. Alternative zu «Nachschub anlegen» (produzieren), wenn der
    Bestand bereits am Lager liegt. Liefert den Auftrag zurück."""
    order = _get_staff_order(db, object_id)
    if order.status != "released":
        raise HTTPException(400, detail="Nur ein freigegebener Auftrag lässt sich aus Lager decken")
    recovery.cover_from_stock(db, order, current_user.id, data.instance_object_ids)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/purchase", response_model=OrderResponse)
async def update_order_purchase(
    object_id: int,
    data: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Beschaffungsschritt des Auftrags bearbeiten (rollenabhängig, läuft unter der
    Auftragsnummer – keine eigene Bestellnummer).

    EIN Schritt, auch bei mehreren Artikeln (Mehrpositionen-Auftrag): ``facts_for_step``
    liefert dann mehrere Bestellungen (eine je Artikel), ein reiner Statuswechsel gilt für
    alle gemeinsam (eine Sendung) – siehe ``purchase.apply_update_bulk``."""
    order = visible_orders(db, user).filter(Order.object_id == object_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    _assert_not_paused(db, order)
    step = process.resolve_exec_step(db, order, "purchase", data.step_id)
    pos = process.facts_for_step(db, order, step)
    apply_purchase_update_bulk(db, pos, data, user)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/sale", response_model=OrderResponse)
async def update_order_sale(
    object_id: int,
    data: SaleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Verkauf» (kaufmännisch): Bestätigung → Rechnung → Zahlung.

    EIN Schritt, auch bei mehreren Artikeln (Mehrpositionen-Auftrag): ``facts_for_step``
    liefert dann mehrere Belege (einen je Artikel), die Aktualisierung (Kunde/Status/
    Zahlungsart) gilt für alle gemeinsam (eine Sendung, eine Zahlung) – siehe
    ``sale.apply_update_bulk``."""
    order = _get_staff_order(db, object_id)
    _assert_not_paused(db, order)
    step = process.resolve_exec_step(db, order, "sale", data.step_id)
    sales = process.facts_for_step(db, order, step)
    sale_svc.apply_update_bulk(db, sales, data, current_user)
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
    _assert_not_paused(db, order)
    record_inspection(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/document", response_model=OrderResponse)
async def update_order_document(
    object_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Dokument»: Inhalt verfassen (save) bzw. ausstellen (issue)."""
    order = _get_staff_order(db, object_id)
    _assert_not_paused(db, order)
    record_document(db, order, data, current_user.id)
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
    _assert_not_paused(db, order)
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
    _assert_not_paused(db, order)
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
    _assert_not_paused(db, order)
    record_scrap(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)
