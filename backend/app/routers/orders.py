from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Order, UserProfile
from ..schemas.order import OrderCreate, OrderResponse, OrderUpdate
from ..services.admin import log_audit
from ..services.objects import next_object_id
from ..services.purchase import instantiate_for_order

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])


def _get_active(db: Session, object_id: int) -> Order:
    order = (
        db.query(Order)
        .filter(Order.object_id == object_id, Order.is_active == True)
        .first()
    )
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    return order


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    orders = (
        db.query(Order)
        .filter(Order.is_active == True)
        .order_by(Order.object_id)
        .all()
    )
    return [OrderResponse.model_validate(o) for o in orders]


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    order = Order(
        object_id=next_object_id(db),
        status="draft",
        title=data.title,
        article_id=data.article_id,
        quantity=data.quantity,
        desired_delivery_date=data.desired_delivery_date,
    )
    db.add(order)
    db.flush()
    log_audit(db, "orders", None, "Auftrag angelegt",
              current_user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return OrderResponse.model_validate(order)


@router.get("/{object_id}", response_model=OrderResponse)
async def get_order(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return OrderResponse.model_validate(_get_active(db, object_id))


@router.patch("/{object_id}", response_model=OrderResponse)
async def update_order(
    object_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    order = _get_active(db, object_id)
    was_released = order.status == "released"

    for key, value in data.model_dump(exclude_unset=True).items():
        old_val = getattr(order, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "orders", key, new_str, current_user.id,
                      object_id=order.object_id, old_value=old_str)
        setattr(order, key, value)

    # Freigabe (draft → released) stösst den Artikel-Prozess an
    if order.status == "released" and not was_released:
        if not order.article_id or not order.quantity:
            raise HTTPException(400, detail="Zur Freigabe sind Artikel und Menge erforderlich")
        instantiate_for_order(db, order, current_user.id)

    db.commit()
    db.refresh(order)
    return OrderResponse.model_validate(order)
