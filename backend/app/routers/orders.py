"""Auftrag – Feed, Anlage, Detail.

Es gibt **keinen** Entwurfs-Endpunkt: ein Auftragsentwurf lebt im Browser, bis er
speicherbar ist. Erst ``POST`` legt ihn an, und erst dabei entsteht die Objektnummer.
``/validate`` sagt der Oberfläche vorher, ob es reichen würde – ohne etwas anzulegen.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Order, UserProfile
from ..schemas.order import OrderCreate, OrderResponse, OrderSummary, OrderValidation
from ..services import orders as orders_svc
from ..services.admin import log_audit

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])


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


@router.post("/validate", response_model=OrderValidation)
def validate_order(
    data: OrderCreate,
    _: UserProfile = Depends(require_employee),
):
    """Wäre dieser Entwurf speicherbar? Legt **nichts** an, zieht **keine** Nummer.

    Dieselbe Regel wie die Anlage (``services/orders.validate_draft``) – die Oberfläche
    formuliert sie nicht nach, sie fragt sie ab.
    """
    missing = orders_svc.validate_draft(data.model_dump())
    return OrderValidation(saveable=not missing, missing=missing)


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    order = orders_svc.create_order(db, data.model_dump())
    log_audit(db, user.id, "orders", order.id, "create", None, str(order.object_id))
    db.commit()
    db.refresh(order)
    return order


@router.get("/{object_id}", response_model=OrderResponse)
def get_order(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return orders_svc.get(db, object_id)
