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
    OrderCreate, OrderResponse, OrderSummary, OrderUnitResponse, OrderValidation,
    ProcessEventResponse, ProcessStepResponse, UnitOption,
)
from ..services import orders as orders_svc
from ..services import process as process_svc
from ..services.admin import log_audit
from ..services.instances import unit_number

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# Antwort zusammensetzen
# ---------------------------------------------------------------------------

def _to_response(db: Session, order: Order) -> OrderResponse:
    steps = process_svc.steps_of(db, order)
    rows = (
        db.query(OrderUnit, InstanceUnit)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(OrderUnit.order_id == order.id)
        .order_by(OrderUnit.id)
        .all()
    )
    numbers = process_svc.unit_numbers(db, [u for _, u in rows])
    events = process_svc.events_of(db, order)
    actors = _actor_names(db, {e.actor_id for e in events if e.actor_id})

    return OrderResponse(
        id=order.id,
        object_id=order.object_id,
        status=order.status,
        end_status=order.end_status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        is_active=order.is_active,
        steps=[ProcessStepResponse.model_validate(s) for s in steps],
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
        active_step_id=process_svc.active_step_id(db, order),
    )


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


@router.get("/unit-options", response_model=list[UnitOption])
def unit_options(
    limit: int = Query(300, le=1000),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Welche Einzelinstanzen kann ich in die Definition nehmen?

    Gesperrte werden **mitgeliefert**, nicht weggefiltert: die Oberfläche soll den Grund
    zeigen können («aktiv in Auftrag …»), statt eine Zeile stumm verschwinden zu lassen.
    """
    rows = (
        db.query(InstanceUnit, Instance, Article)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .outerjoin(Article, Article.id == Instance.article_id)
        .filter(InstanceUnit.is_active.is_(True), Instance.is_active.is_(True))
        .order_by(InstanceUnit.id.desc())
        .limit(limit)
        .all()
    )
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
            article_name=article.name if article else None,
            available=unit.id not in blocked and unit.status == st.START_BEFORE,
            blocked_by=blocked.get(unit.id),
        )
        for unit, instance, article in rows
    ]


@router.post("/validate", response_model=OrderValidation)
def validate_order(
    data: OrderCreate,
    _: UserProfile = Depends(require_employee),
):
    """Wäre dieser Entwurf freigebbar? Legt **nichts** an, zieht **keine** Nummer."""
    missing = orders_svc.validate_draft(data.model_dump())
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


@router.post("/{object_id}/steps/{step_id}/confirm", response_model=OrderResponse)
def confirm_step(
    object_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """«Schritt bestätigen» – der eine Ausführungs-Endpunkt des Testmoduls."""
    order = orders_svc.get(db, object_id)
    moved = process_svc.confirm_step(db, order=order, step_id=step_id, actor_id=user.id)
    log_audit(db, "process_steps", "confirm", str(moved),
              user_id=user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return _to_response(db, order)
