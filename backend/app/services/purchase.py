"""Geschäftslogik für das Prozessschritt-Modul «Purchase Order».

- ``instantiate_for_order``: erzeugt bei Auftragsfreigabe die Bestellung aus dem
  ``purchase``-Prozessschritt des Artikels.
- ``compute_landed_unit_cost``: Einstandspreis netto/Stück.
- ``apply_update``: rollenabhängige Feldeingaben + Statusübergänge.
"""

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, ArticleProcessStep, Order, PurchaseOrder, UserProfile
from .admin import log_audit

# Erlaubte Statusübergänge: Zielstatus → zulässige Ausgangsstatus
_FROM = {
    "quoted": {"requested"},
    "approved": {"quoted"},
    "rejected": {"quoted"},
    "confirmed": {"approved"},
    "received": {"confirmed"},
}

_STAFF_ROLES = ("admin", "employee")
_SUPPLIER_OFFER_FIELDS = {
    "unit_price", "transport_cost", "transport_included",
    "other_costs", "lead_time_days", "payment_terms_days",
}
_SUPPLIER_CONFIRM_FIELDS = {"tracking_number", "lead_time_days"}
_STAFF_FIELDS = _SUPPLIER_OFFER_FIELDS | {
    "desired_delivery_date", "tracking_number", "rejection_reason",
}


def _is_staff(user: UserProfile) -> bool:
    return user.role in _STAFF_ROLES


def _is_owner_supplier(po: PurchaseOrder, user: UserProfile) -> bool:
    return user.role == "supplier" and po.supplier_id == user.id


def compute_landed_unit_cost(po: PurchaseOrder) -> Optional[Decimal]:
    """Einstandspreis netto/Stück = (Stückpreis × Menge + Transport + Sonstiges) ÷ Menge."""
    if po.unit_price is None or not po.quantity:
        return None
    transport = Decimal(0) if po.transport_included else (po.transport_cost or Decimal(0))
    other = po.other_costs or Decimal(0)
    total = po.unit_price * po.quantity + transport + other
    return (total / po.quantity).quantize(Decimal("0.0001"))


def instantiate_for_order(db: Session, order: Order, actor_id: int) -> list[PurchaseOrder]:
    """Bei Auftragsfreigabe die Bestellung aus dem purchase-Prozessschritt anlegen.

    Idempotent: existiert bereits eine Bestellung zum Auftrag, wird nichts erzeugt.
    Hat der Artikel keinen purchase-Schritt, passiert nichts.
    """
    if not order.article_id or not order.quantity:
        return []
    existing = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .first()
    )
    if existing:
        return [existing]
    step = (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == order.article_id,
            ArticleProcessStep.step_type == "purchase",
            ArticleProcessStep.is_active == True,
        )
        .order_by(ArticleProcessStep.position)
        .first()
    )
    if not step:
        return []
    po = PurchaseOrder(
        order_id=order.id,
        article_id=order.article_id,
        quantity=order.quantity,
        mode=step.mode,
        supplier_id=step.supplier_id,
        webshop_url=step.webshop_url,
        desired_delivery_date=order.desired_delivery_date,
        status="requested",
    )
    db.add(po)
    db.flush()
    log_audit(db, "purchase_orders", None, "Bestellung angefragt",
              actor_id, object_id=order.object_id)
    # TODO(E-Mail): Lieferant über neue Bestellanfrage benachrichtigen (Gmail API, Phase 2)
    return [po]


def _order_steps_done(db: Session, order: Order) -> bool:
    """True, wenn alle Prozessschritte des Auftrags erledigt sind.

    Aktuell existiert nur der Schritt «purchase» (erledigt = Wareneingang).
    Künftige Schritt-Typen hier ergänzen – ein unbekannter Typ gilt als offen.
    """
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == order.article_id,
                ArticleProcessStep.is_active == True)
        .all()
    )
    if not steps:
        return False
    for st in steps:
        if st.step_type == "purchase":
            po = (
                db.query(PurchaseOrder)
                .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
                .first()
            )
            if not po or po.status != "received":
                return False
        else:
            return False
    return True


def maybe_complete_order(db: Session, order: Order) -> None:
    """Auftrag automatisch abschliessen, wenn alle Prozessschritte erledigt sind."""
    if order.status != "completed" and _order_steps_done(db, order):
        order.status = "completed"


def _editable_fields(po: PurchaseOrder, user: UserProfile) -> set[str]:
    if _is_staff(user):
        return set(_STAFF_FIELDS)
    if _is_owner_supplier(po, user):
        fields: set[str] = set()
        if po.status in ("requested", "quoted"):
            fields |= _SUPPLIER_OFFER_FIELDS
        if po.status in ("approved", "confirmed"):
            fields |= _SUPPLIER_CONFIRM_FIELDS
        return fields
    return set()


def _transition_allowed(po: PurchaseOrder, target: str, user: UserProfile) -> bool:
    if _is_staff(user):
        return True
    if _is_owner_supplier(po, user):
        return target in ("quoted", "confirmed") and po.mode == "supplier"
    return False


def _apply_transition(db: Session, po: PurchaseOrder, order: Order, target: str, user: UserProfile) -> None:
    if target not in _FROM:
        raise HTTPException(400, detail="Unbekannter Zielstatus")
    if po.status not in _FROM[target]:
        raise HTTPException(400, detail=f"Übergang {po.status} → {target} ist nicht erlaubt")
    if not _transition_allowed(po, target, user):
        raise HTTPException(403, detail="Keine Berechtigung für diesen Schritt")
    if target == "quoted" and po.unit_price is None:
        raise HTTPException(400, detail="Stückpreis ist für die Offerte erforderlich")
    if target == "approved":
        lc = compute_landed_unit_cost(po)
        po.landed_unit_cost = lc
        if lc is not None:
            art = db.query(Article).filter(Article.id == po.article_id).first()
            if art:
                art.landed_unit_cost = lc
    old = po.status
    po.status = target
    log_audit(db, "purchase_orders", "status", target, user.id,
              object_id=order.object_id, old_value=old)
    # Auftrag automatisch abschliessen, wenn damit alle Schritte erledigt sind
    maybe_complete_order(db, order)
    # TODO(E-Mail): Statuswechsel an Lieferant/uns melden (Gmail API, Phase 2)


def apply_update(db: Session, po: PurchaseOrder, data, user: UserProfile) -> PurchaseOrder:
    """Felder setzen (rollen-/statusabhängig) und optional einen Statusübergang ausführen."""
    if not (_is_staff(user) or _is_owner_supplier(po, user)):
        raise HTTPException(403, detail="Keine Berechtigung für diese Bestellung")
    order = db.query(Order).filter(Order.id == po.order_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")

    payload = data.model_dump(exclude_unset=True)
    target = payload.pop("status", None)

    editable = _editable_fields(po, user)
    for key, value in payload.items():
        if key not in editable:
            raise HTTPException(403, detail=f"Feld '{key}' darf in diesem Status nicht geändert werden")
        setattr(po, key, value)

    if target and target != po.status:
        _apply_transition(db, po, order, target, user)

    db.commit()
    db.refresh(po)
    return po
