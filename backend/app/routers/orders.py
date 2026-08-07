"""Auftrag – Feed, Freigabe, Detail, Schritt bestätigen.

Es gibt **keinen** Entwurfs-Endpunkt: ein Auftragsentwurf lebt im Browser, bis er
freigebbar ist. Erst ``POST`` legt ihn an – und dieser eine Aufruf ist zugleich die
Freigabe. ``/validate`` sagt der Oberfläche vorher, ob es reichen würde, ohne etwas
anzulegen und ohne eine Nummer zu ziehen.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..domain import statuses as st
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderUnit, UserProfile,
)
from ..schemas.order import (
    ArticleOption, OrderCreate, OrderLineResponse, OrderResponse, OrderSummary,
    OrderUnitPage, OrderUnitResponse, OrderValidation, ProcessEventResponse,
    ProcessStepResponse, UnitGroup, UnitOption,
)
from ..schemas.process import (
    CaptureTypeInfo, ModuleCatalog, ModuleTypeInfo, StepConfirm,
)
from ..domain import capture_types, modules
from ..services import article_process as tpl_svc
from ..services import orders as orders_svc
from ..services import process as process_svc
from ..services.admin import log_audit
from ..services.instances import unit_number

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])

#: Wie viele Log-Einträge das Detail mitliefert. Bei 5000 Stück hat der Log 10 000
#: Einträge; alle mitzuschicken machte die Antwort megabytegross, ohne dass jemand sie
#: liest. Die Gesamtzahl steht daneben (``event_count``) – gekappt, aber nicht verschwiegen.
EVENT_LIMIT = 200


# ---------------------------------------------------------------------------
# Antwort zusammensetzen
# ---------------------------------------------------------------------------

def _to_response(db: Session, order: Order) -> OrderResponse:
    steps = process_svc.steps_of(db, order)
    lines = process_svc.lines_of(db, order)
    articles = {
        a.id: a
        for a in db.query(Article).filter(Article.id.in_([ln.article_id for ln in lines])).all()
    } if lines else {}
    events, event_count = process_svc.events_page(db, order, limit=EVENT_LIMIT)
    numbers = _event_numbers(db, events)
    actors = _actor_names(db, {e.actor_id for e in events if e.actor_id})

    return OrderResponse(
        id=order.id,
        object_id=order.object_id,
        status=order.status,
        end_status=order.end_status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        is_active=order.is_active,
        lines=[
            OrderLineResponse(
                id=ln.id,
                position=ln.position,
                quantity=ln.quantity,
                origin=ln.origin,
                article_object_id=articles[ln.article_id].object_id if ln.article_id in articles else None,
                article_name=articles[ln.article_id].name if ln.article_id in articles else None,
            )
            for ln in lines
        ],
        steps=[ProcessStepResponse.model_validate(s) for s in steps],
        unit_groups=[UnitGroup(**g) for g in process_svc.unit_groups(db, order)],
        events=[
            ProcessEventResponse(
                id=e.id,
                kind=e.kind,
                step_id=e.step_id,
                unit_number=numbers.get(e.instance_unit_id, str(e.instance_unit_id)),
                status_before=e.status_before,
                status_after=e.status_after,
                actor=actors.get(e.actor_id),
                created_at=e.created_at,
            )
            for e in events
        ],
        event_count=event_count,
        active_step_id=process_svc.active_step_id(db, order),
    )


def _event_numbers(db: Session, events) -> dict[int, str]:
    """Nummern nur für die Stücke, die in den gezeigten Einträgen vorkommen."""
    ids = {e.instance_unit_id for e in events}
    if not ids:
        return {}
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(ids)).all()
    return process_svc.unit_numbers(db, units)


def _actor_names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {
        u.id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.id.in_(ids)).all()
    }


# ---------------------------------------------------------------------------
# Endpunkte
# ---------------------------------------------------------------------------

@router.get("", response_model=list[OrderSummary])
def list_orders(
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return (
        db.query(Order)
        .order_by(Order.object_id.desc())
        .limit(limit).offset(offset).all()
    )


@router.get("/article-options", response_model=list[ArticleOption])
def article_options(
    limit: int = Query(300, le=1000),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Welche Artikel kann ich in eine Definitionszeile nehmen?

    ``template_steps`` fährt mit, damit die Oberfläche «Neu» sperren **und begründen**
    kann. Sie in zwei Aufrufen zu holen hiesse, die Zeile erst leer und dann korrigiert
    zu zeigen.
    """
    rows = (
        db.query(Article)
        .filter(Article.is_active.is_(True), Article.object_id.isnot(None))
        .order_by(Article.object_id.desc())
        .limit(limit)
        .all()
    )
    counts = tpl_svc.step_counts(db, [a.id for a in rows])
    return [
        ArticleOption(
            object_id=a.object_id,
            name=a.name,
            serialization=a.serialization,
            unit=a.unit,
            template_steps=counts.get(a.id, 0),
        )
        for a in rows
    ]


@router.get("/module-catalog", response_model=ModuleCatalog)
def module_catalog(_: UserProfile = Depends(require_employee)):
    """Was sich modellieren lässt – Modultypen und Erfassungspunkt-Typen.

    Beides sind **geschlossene Listen** im Backend (``domain/modules``,
    ``domain/capture_types``). Die Oberfläche holt sie hier, statt sie nachzubauen: eine
    zweite Aufzählung liefe beim ersten neuen Typ auseinander, und der Fehler zeigte sich
    erst, wenn jemand ihn auswählt.
    """
    return ModuleCatalog(
        modules=[
            ModuleTypeInfo(key=m.key, label=m.label,
                           status_before=m.status_before, status_after=m.status_after)
            for m in modules.MODULES.values()
        ],
        capture_types=[CaptureTypeInfo(key=t.key, label=t.label) for t in capture_types.ALL],
    )


@router.get("/unit-options", response_model=list[UnitOption])
def unit_options(
    article: Optional[int] = Query(None, description="Objektnummer des Artikels"),
    limit: int = Query(300, le=1000),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Welche Einzelinstanzen kann ich in eine ``Lager``-Zeile nehmen?

    **FIFO**: älteste zuerst (aufsteigende Nummer). Das ist eine Vorauswahl-Reihenfolge,
    kein Zwang – die Oberfläche schlägt die ersten N vor und lässt jede davon abwählen.

    Gesperrte werden **mitgeliefert**, nicht weggefiltert: die Oberfläche soll den Grund
    zeigen können («aktiv in Auftrag …»), statt eine Zeile stumm verschwinden zu lassen.
    """
    q = (
        db.query(InstanceUnit, Instance, Article)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .outerjoin(Article, Article.id == Instance.article_id)
        .filter(InstanceUnit.is_active.is_(True), Instance.is_active.is_(True))
    )
    if article is not None:
        q = q.filter(Article.object_id == article)
    rows = q.order_by(InstanceUnit.id).limit(limit).all()
    blocked = {
        m.instance_unit_id: o.object_id
        for m, o in db.query(OrderUnit, Order)
        .join(Order, Order.id == OrderUnit.order_id)
        .filter(OrderUnit.released_at.is_(None))
        .all()
    }
    return [
        UnitOption(
            number=unit_number(instance, unit),
            status=unit.status,
            article_object_id=art.object_id if art else None,
            article_name=art.name if art else None,
            available=unit.id not in blocked and unit.status == st.START_BEFORE,
            blocked_by=blocked.get(unit.id),
        )
        for unit, instance, art in rows
    ]


@router.post("/validate", response_model=OrderValidation)
def validate_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Wäre dieser Entwurf freigebbar? Legt **nichts** an, zieht **keine** Nummer."""
    missing = orders_svc.validate_draft(db, data.model_dump())
    return OrderValidation(saveable=not missing, missing=missing)


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Anlegen **ist** Freigeben – ein Aufruf, eine Transaktion (§6.3)."""
    order = orders_svc.create_order(db, data.model_dump(), actor_id=user.id)
    log_audit(db, "orders", "release", str(order.object_id),
              user_id=user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return _to_response(db, order)


@router.get("/{object_id}", response_model=OrderResponse)
def get_order(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _to_response(db, orders_svc.get(db, object_id))


@router.get("/{object_id}/units", response_model=OrderUnitPage)
def list_units(
    object_id: int,
    step_id: Optional[int] = Query(None),
    active: bool = Query(True),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Die einzelnen Stücke einer Gruppe – erst wenn jemand aufklappt."""
    order = orders_svc.get(db, object_id)
    rows, total = process_svc.units_page(
        db, order, step_id=step_id, active=active, limit=limit, offset=offset,
    )
    numbers = process_svc.unit_numbers(db, [u for _, u in rows])
    return OrderUnitPage(
        units=[
            OrderUnitResponse(
                instance_unit_id=u.id,
                number=numbers[u.id],
                status=u.status,
                current_step_id=m.current_step_id,
                active=m.released_at is None,
            )
            for m, u in rows
        ],
        total=total,
    )


@router.post("/{object_id}/steps/{step_id}/confirm", response_model=OrderResponse)
def confirm_step(
    object_id: int,
    step_id: int,
    data: StepConfirm,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """«Bestätigen» – der **eine** Ausführungs-Endpunkt, für jedes Modul derselbe.

    Was im Rumpf steht, entscheidet der Modultyp: bei der Datenerfassung die erfassten
    Werte. Ein Endpunkt je Modul wäre ein zweiter Ausführungspfad – und damit eine
    zweite Stelle, an der ein Statuswechsel geschrieben wird.
    """
    order = orders_svc.get(db, object_id)
    moved = process_svc.confirm_step(
        db, order=order, step_id=step_id, values=data.values, actor_id=user.id)
    log_audit(db, "process_steps", "confirm", str(moved),
              user_id=user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return _to_response(db, order)
