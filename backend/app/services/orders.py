"""Hilfen rund um den Auftrag: Response-Aufbau (mit eingebettetem Prozess) und
rollenabhängige Sichtbarkeit (Lieferant sieht nur seine Aufträge)."""

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from ..models import Article, ArticleProcessStep, Order, PurchaseOrder, UserProfile
from ..schemas.order import OrderResponse
from ..schemas.purchase_order import PurchaseEmbed
from .article_fields import normalize_shared_fields

_STAFF_ROLES = ("admin", "employee")


def _purchase_shared_fields(db: Session, article_id: int) -> list[str]:
    """Vom purchase-Schritt des Artikels freigegebene Stammdaten (Pflicht inkl.)."""
    step = (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article_id,
            ArticleProcessStep.step_type == "purchase",
            ArticleProcessStep.is_active == True,
        )
        .order_by(ArticleProcessStep.position)
        .first()
    )
    return normalize_shared_fields(step.shared_fields if step else None)


def _supplier_name(u: UserProfile | None) -> str | None:
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def to_order_response(db: Session, order: Order) -> OrderResponse:
    """OrderResponse inkl. denormalisiertem Artikel und eingebettetem Beschaffungsschritt."""
    resp = OrderResponse.model_validate(order)
    if order.article_id:
        art = db.query(Article).filter(Article.id == order.article_id).first()
        if art:
            resp.article_name = art.name
            resp.article_object_id = art.object_id
            resp.article_size = art.size
            resp.article_unit = art.unit
            resp.article_weight_kg = art.weight_kg
            resp.article_serialization = art.serialization
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .first()
    )
    if po:
        emb = PurchaseEmbed.model_validate(po)
        if po.supplier_id:
            emb.supplier_name = _supplier_name(
                db.query(UserProfile).filter(UserProfile.id == po.supplier_id).first()
            )
        if order.article_id:
            emb.shared_fields = _purchase_shared_fields(db, order.article_id)
        resp.purchase = emb
    return resp


def visible_orders(db: Session, user: UserProfile) -> Query:
    """Mitarbeiter/Admin sehen alle Aufträge, Lieferanten nur ihre, sonst keine."""
    q = db.query(Order).filter(Order.is_active == True)
    if user.role in _STAFF_ROLES:
        return q
    if user.role == "supplier":
        sub = (
            db.query(PurchaseOrder.order_id)
            .filter(PurchaseOrder.supplier_id == user.id, PurchaseOrder.is_active == True)
        )
        return q.filter(Order.id.in_(sub))
    return q.filter(false())
