from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..models import ArticleProcessStep, Article, Instance, Order, OrderLine, PurchaseOrder, UserProfile
from ..models.base import utcnow
from ..schemas.disposal import ScrapUpdate
from ..schemas.inspection import InspectionUpdate
from ..schemas.movement import MovementUpdate
from ..schemas.order import (
    OrderCreate, OrderDeviationCreate, OrderLineIn, OrderResponse, OrderSummary, OrderUpdate,
)
from ..schemas.purchase_order import PurchaseOrderUpdate
from ..schemas.resource import ResourceUpdate
from ..schemas.sale import SaleUpdate
from ..services import deactivation, deviation, order_lines as order_lines_svc, process, sale as sale_svc, subject, supply
from ..services.admin import log_audit
from ..services.events import emit
from ..services.inspection import record_inspection
from ..services.lifecycle import ensure_mutable, ensure_version
from ..services.movement import record_movement
from ..services.scrap import record_scrap
from ..services.objects import next_object_id
from ..services.orders import release_order, to_order_response, to_order_summaries, visible_orders
from ..services.purchase import apply_update as apply_purchase_update, instantiate_for_order as instantiate_purchase
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


def _pin_line_instances(db: Session, order: Order, article_id: int, quantity: int,
                        object_ids: list[int]) -> None:
    """Fixierte Instanzen EINER Position eines Mehrpositionen-Auftrags vormerken – wie
    ``_set_chosen_instances`` für den Einzel-Artikel-Auftrag, nur gegen die Menge/den
    Artikel DIESER Position statt des ganzen Auftrags geprüft (mehrere Artikel können
    unter demselben Sammel-Auftrag je eigene Fixierungen tragen)."""
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


def _create_single_order(db: Session, data: OrderCreate, current_user: UserProfile) -> Order:
    """Der gewöhnliche Einzel-Artikel-Auftrag (unverändert)."""
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
    return order


def _create_multiline_order(
    db: Session, lines: list[OrderLineIn], current_user: UserProfile
) -> tuple[Order, list[int]]:
    """**Mehrpositionen**-Anlage: «Herstellen/Beschaffen»-Zeilen werden je ein **eigener**
    Auftrag (eigene Fertigungs-Timeline, analog zum Shop-Warenkorb – „make-Positionen
    bleiben je ein eigener Auftrag"); «Aus dem Lager»/«Instanz wählen»-Zeilen bündeln sich
    zu EINEM Sammel-Auftrag (``order_lines``, eine Sendung). Liefert (**primärer** Auftrag
    – Sammel-Auftrag, sonst die erste Herstellung –, Objektnummern der übrigen)."""
    for line in lines:
        _validate_article(db, line.article_id)

    siblings: list[Order] = []
    for line in lines:
        if line.goal != "produce":
            continue
        o = Order(object_id=next_object_id(db, "order"), status="draft",
                  article_id=line.article_id, quantity=line.quantity)
        db.add(o)
        db.flush()
        log_audit(db, "orders", None,
                  "Auftrag angelegt (Mehrpositionen: Herstellen/Beschaffen)",
                  current_user.id, object_id=o.object_id)
        siblings.append(o)

    pooled_lines = [l for l in lines if l.goal == "stock"]
    pooled: Order | None = None
    if pooled_lines:
        pooled = Order(
            object_id=next_object_id(db, "order"), status="draft", article_id=None, quantity=None,
            title=f"Mehrpositionen ({len(pooled_lines)} Position(en))" if len(pooled_lines) > 1 else None,
        )
        db.add(pooled)
        db.flush()
        for i, line in enumerate(pooled_lines):
            ol = OrderLine(order_id=pooled.id, article_id=line.article_id,
                           quantity=line.quantity, position=i)
            db.add(ol)
            db.flush()
            if line.instance_object_ids:
                _pin_line_instances(db, pooled, line.article_id, line.quantity, line.instance_object_ids)
            # «Verkaufen an Kunden»: je Position sofort ein Verkaufs-Schritt (Personal
            # trägt Kunde/Preis später im Verkaufs-Panel ein – wie beim Einzel-Artikel-
            # Auftrag). Direkt konstruiert (nicht über den generischen Step-Editor), damit
            # KEIN Pflicht-Bewegungs-Sync ausgelöst wird (siehe ``_Owner.sync``).
            db.add(ArticleProcessStep(order_id=pooled.id, position=i, step_type="sale",
                                      order_line_id=ol.id))
        # EIN gemeinsamer Bewegungs-Schritt für alle Positionen (eine Sendung) – Ziel frei
        # wählbar beim Ausführen (Personal wählt den Kunden über den Verkauf, nicht hier fix).
        db.add(ArticleProcessStep(order_id=pooled.id, position=len(pooled_lines),
                                  step_type="movement"))
        db.flush()
        log_audit(db, "orders", None, f"Auftrag angelegt ({len(pooled_lines)} Position(en))",
                  current_user.id, object_id=pooled.object_id)

    primary = pooled or siblings[0]
    also_created = [o.object_id for o in (siblings + ([pooled] if pooled else [])) if o is not primary]
    return primary, also_created


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    if data.lines:
        order, also_created = _create_multiline_order(db, data.lines, current_user)
        db.commit()
        db.refresh(order)
        resp = to_order_response(db, order)
        resp.also_created = also_created
        return resp
    order = _create_single_order(db, data, current_user)
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
    # Kein Reaktivieren von Aufträgen: die Physis ist weitergewandert → neuer Auftrag.
    if payload.get("status") == "released" and order.status == "inactive":
        raise HTTPException(409, detail="Auftrag kann nicht reaktiviert werden – bitte neuen Auftrag anlegen")

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
        if not is_multiline and (not order.article_id or not order.quantity):
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
    _assert_not_paused(db, order)
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
    """Schritt «Verkauf» (kaufmännisch): Bestätigung → Rechnung → Zahlung.

    Bei einem Mehrpositionen-Auftrag trägt jede Position ihren EIGENEN Verkaufs-Schritt
    (Mehr-Operationen-Routing) – ``step_id`` wählt die richtige Position; ohne ``step_id``
    die gerade aktive (identisch zu movement/resource/inspection)."""
    order = _get_staff_order(db, object_id)
    _assert_not_paused(db, order)
    step = process.resolve_exec_step(db, order, "sale", data.step_id)
    sale = process.fact_for_step(db, order, step)
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
    _assert_not_paused(db, order)
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
