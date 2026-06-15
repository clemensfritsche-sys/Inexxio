from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import Article, Order, PurchaseOrder, UserProfile
from ..schemas.purchase_order import PurchaseOrderResponse, PurchaseOrderUpdate
from ..services import purchase

router = APIRouter(prefix="/api/v1/erp/purchase-orders", tags=["purchase-orders"])

_STAFF_ROLES = ("admin", "employee")


def _supplier_name(u: UserProfile | None) -> str | None:
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def _to_response(db: Session, po: PurchaseOrder) -> PurchaseOrderResponse:
    """Antwort mit denormalisierten Artikel-/Lieferant-Infos (für die Lieferant-Ansicht)."""
    resp = PurchaseOrderResponse.model_validate(po)
    art = db.query(Article).filter(Article.id == po.article_id).first()
    if art:
        resp.article_name = art.name
        resp.article_object_id = art.object_id
        resp.article_size = art.size
        resp.article_unit = art.unit
        resp.article_weight_kg = art.weight_kg
    if po.supplier_id:
        resp.supplier_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == po.supplier_id).first()
        )
    order = db.query(Order).filter(Order.id == po.order_id).first()
    if order:
        resp.order_object_id = order.object_id
    return resp


def _visible(db: Session, user: UserProfile) -> Query:
    """Sichtbarkeit: Mitarbeiter/Admin alle, Lieferant nur eigene, sonst keine."""
    q = db.query(PurchaseOrder).filter(PurchaseOrder.is_active == True)
    if user.role in _STAFF_ROLES:
        return q
    if user.role == "supplier":
        return q.filter(PurchaseOrder.supplier_id == user.id)
    return q.filter(false())


def _get_visible(db: Session, object_id: int, user: UserProfile) -> PurchaseOrder:
    po = _visible(db, user).filter(PurchaseOrder.object_id == object_id).first()
    if not po:
        raise HTTPException(404, detail="Bestellung nicht gefunden")
    return po


@router.get("", response_model=list[PurchaseOrderResponse])
async def list_purchase_orders(
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    pos = _visible(db, user).order_by(PurchaseOrder.object_id).all()
    return [_to_response(db, po) for po in pos]


@router.get("/{object_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    object_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return _to_response(db, _get_visible(db, object_id, user))


@router.patch("/{object_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    object_id: int,
    data: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    po = _get_visible(db, object_id, user)
    return _to_response(db, purchase.apply_update(db, po, data, user))
