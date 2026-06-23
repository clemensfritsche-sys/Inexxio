"""Wiederkehrende Vorgänge (Compliance/Termine + Abos) – Feed-Typ «Wiederkehrend».

Erzeugen automatisch normale Aufträge (gleiche Prozess-Engine). ``POST /run`` löst
die Erzeugung fälliger Vorgänge manuell aus (zusätzlich läuft sie beim App-Start)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Process, RecurringOrder, UserProfile
from ..schemas.recurring_order import (
    RecurringOrderCreate, RecurringOrderResponse, RecurringOrderUpdate,
)
from ..services import recurring as recurring_svc
from ..services.admin import log_audit
from ..services.objects import next_object_id

router = APIRouter(prefix="/api/v1/erp/recurring-orders", tags=["recurring-orders"])


def _to_response(db: Session, rec: RecurringOrder) -> RecurringOrderResponse:
    resp = RecurringOrderResponse.model_validate(rec)
    if rec.process_id:
        p = db.query(Process).filter(Process.id == rec.process_id).first()
        resp.process_name = p.name if p else None
    if rec.article_id:
        a = db.query(Article).filter(Article.id == rec.article_id).first()
        resp.article_name = a.name if a else None
    resp.due_now = recurring_svc.due_now(rec, date.today())
    return resp


@router.get("", response_model=list[RecurringOrderResponse])
async def list_recurring(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    rows = (
        db.query(RecurringOrder)
        .filter(RecurringOrder.is_active == True)
        .order_by(RecurringOrder.object_id.desc())
        .all()
    )
    return [_to_response(db, r) for r in rows]


@router.post("", response_model=RecurringOrderResponse, status_code=201)
async def create_recurring(
    data: RecurringOrderCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    if not data.interval_days and not data.valid_until:
        raise HTTPException(400, detail="Entweder ein Intervall (Abo) oder ein Ablaufdatum (Compliance) angeben")
    rec = RecurringOrder(
        object_id=next_object_id(db, "recurring_order"),
        name=data.name, status="draft",
        process_id=data.process_id, article_id=data.article_id,
        quantity=data.quantity, subject_instance_id=data.subject_instance_id,
        interval_days=data.interval_days, lead_time_days=data.lead_time_days,
        validity_days=data.validity_days, next_due_at=data.next_due_at,
        valid_until=data.valid_until,
    )
    db.add(rec)
    db.flush()
    log_audit(db, "recurring_orders", None, f"Wiederkehrender Vorgang '{data.name}' angelegt",
              current_user.id, object_id=rec.object_id)
    db.commit()
    db.refresh(rec)
    return _to_response(db, rec)


def _get(db: Session, object_id: int) -> RecurringOrder:
    rec = (
        db.query(RecurringOrder)
        .filter(RecurringOrder.object_id == object_id, RecurringOrder.is_active == True)
        .first()
    )
    if not rec:
        raise HTTPException(404, detail="Wiederkehrender Vorgang nicht gefunden")
    return rec


@router.post("/run")
async def run_due(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Fällige Vorgänge jetzt zu Aufträgen machen (manueller Trigger)."""
    created = recurring_svc.spawn_due(db)
    return {"created": [o.object_id for o in created]}


@router.get("/{object_id}", response_model=RecurringOrderResponse)
async def get_recurring(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _to_response(db, _get(db, object_id))


@router.patch("/{object_id}", response_model=RecurringOrderResponse)
async def update_recurring(
    object_id: int,
    data: RecurringOrderUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    rec = _get(db, object_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        old = getattr(rec, key, None)
        if str(old) != str(value):
            log_audit(db, "recurring_orders", key, str(value), current_user.id,
                      object_id=rec.object_id, old_value=str(old))
        setattr(rec, key, value)
    db.commit()
    db.refresh(rec)
    return _to_response(db, rec)


@router.delete("/{object_id}")
async def delete_recurring(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    rec = _get(db, object_id)
    rec.is_active = False
    log_audit(db, "recurring_orders", "is_active", "false", current_user.id,
              object_id=rec.object_id, old_value="true")
    db.commit()
    return {"deleted": True}
