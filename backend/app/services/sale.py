"""Geschäftslogik für den Prozessschritt «Verkauf» – das Spiegelbild der Beschaffung.

Rein kaufmännisch (der physische Versand läuft über die Bewegung, Ziel = Kunde):
    requested → confirmed → invoiced → paid   (+ cancelled)

- ``instantiate_for_order``: bei Auftragsfreigabe je sale-Schritt einen Verkauf anlegen.
- ``apply_update``: Feldeingaben + Statusübergänge.
"""

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Order, Sale, UserProfile
from ..models.base import utcnow
from . import process
from .admin import log_audit
from .events import emit

_STAFF_ROLES = ("admin", "employee")
# Erlaubte Übergänge: Zielstatus → zulässige Ausgangsstatus
_FROM = {
    "confirmed": {"requested"},
    "invoiced": {"confirmed"},
    "paid": {"invoiced"},
    "cancelled": {"requested", "confirmed", "invoiced"},
}
_EDITABLE = ("order_total", "vat_rate", "currency", "customer_id", "invoice_number")


def unit_price(sale: Sale) -> Optional[Decimal]:
    """Verkaufs-Stückpreis netto = Verkaufsbetrag ÷ Menge."""
    if sale.order_total is None or not sale.quantity:
        return None
    return (sale.order_total / sale.quantity).quantize(Decimal("0.0001"))


def instantiate_for_order(db: Session, order: Order, actor_id: int) -> list[Sale]:
    """Bei Auftragsfreigabe je Verkaufs-Schritt des Prozesses einen Verkauf anlegen."""
    if not order.article_id or not order.quantity:
        return []
    steps = [d for d in process.order_step_defs(db, order) if d.step_type == "sale"]
    if not steps:
        return []
    existing = db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).all()
    has_step = {s.step_id for s in existing if s.step_id is not None}
    legacy = any(s.step_id is None for s in existing)
    created: list[Sale] = []
    for step in steps:
        if step.id in has_step or (legacy and len(steps) == 1):
            continue
        sale = Sale(order_id=order.id, article_id=order.article_id,
                    quantity=order.quantity, step_id=step.id, status="requested")
        db.add(sale)
        db.flush()
        log_audit(db, "sales", None, "Verkauf angefragt", actor_id, object_id=order.object_id)
        created.append(sale)
    # TODO(E-Mail/Beleg): Auftragsbestätigung/Rechnung erzeugen (Gmail API/PDF, Phase 2)
    return created


def _apply_transition(db: Session, sale: Sale, order: Order, target: str, user: UserProfile) -> None:
    if target not in _FROM:
        raise HTTPException(400, detail="Unbekannter Zielstatus")
    if sale.status not in _FROM[target]:
        raise HTTPException(400, detail=f"Übergang {sale.status} → {target} ist nicht erlaubt")
    if target in ("confirmed", "invoiced"):
        if sale.order_total is None:
            raise HTTPException(400, detail="Verkaufsbetrag ist erforderlich")
        # Ein Verkauf ohne Kunde ist fachlich nicht zulässig – der Kunde ist NIE optional,
        # sobald der Verkauf bestätigt/fortgeschrieben wird (spätestens zur Bestätigung).
        if sale.customer_id is None:
            raise HTTPException(400, detail="Kunde ist erforderlich")
    now = utcnow()
    if target == "confirmed":
        sale.confirmed_at = now
    elif target == "invoiced":
        sale.invoiced_at = now
    elif target == "paid":
        sale.paid_at = now
    old = sale.status
    sale.status = target
    log_audit(db, "sales", "status", target, user.id, object_id=order.object_id, old_value=old)
    emit(db, f"sale.{target}", object_type="order", object_id=order.object_id, actor_id=user.id)
    # Auftrag ggf. automatisch abschliessen (alle Schritte erledigt) – setzt Subjekte auf «sold».
    process.recompute_completion(db, order)


def mark_paid(db: Session, sale: Sale) -> Sale:
    """Zahlungseingang (vom Zahlungs-Provider) – den Beleg-Fluss durchlaufen und den
    Verkauf auf ``paid`` setzen. Idempotent: ein bereits bezahlter Verkauf bleibt so.

    Im Shop-Fluss überspringt die Zahlung die manuellen Zwischenschritte (Bestätigung/
    Rechnung); deren Zeitstempel werden zur Beleg-Vollständigkeit nachgezogen."""
    if sale.status == "paid":
        return sale
    now = utcnow()
    if sale.confirmed_at is None:
        sale.confirmed_at = now
    if sale.invoiced_at is None:
        sale.invoiced_at = now
    sale.paid_at = now
    sale.status = "paid"
    order = db.query(Order).filter(Order.id == sale.order_id).first()
    oid = order.object_id if order else None
    log_audit(db, "sales", "status", "paid", None, object_id=oid)
    emit(db, "sale.paid", object_type="order", object_id=oid)
    if order:
        process.recompute_completion(db, order)   # ggf. Auftrag abschliessen (Versand erfolgt)
    db.commit()
    db.refresh(sale)
    return sale


def mark_cancelled(db: Session, sale: Sale) -> Sale:
    """Zahlung abgebrochen/storniert: Verkauf ``cancelled`` und den (unbezahlten)
    Auftrag auflösen – Reservierungen freigeben, Auftrag inaktiv (kein herrenloser
    Bestand). Idempotent."""
    if sale.status in ("paid", "cancelled"):
        return sale
    sale.status = "cancelled"
    order = db.query(Order).filter(Order.id == sale.order_id).first()
    oid = order.object_id if order else None
    log_audit(db, "sales", "status", "cancelled", None, object_id=oid)
    emit(db, "sale.cancelled", object_type="order", object_id=oid)
    if order and order.status in ("draft", "released"):
        from .deactivation import cancel_order_effects
        if order.status == "released":
            cancel_order_effects(db, order, None)
        order.status = "inactive"
    db.commit()
    db.refresh(sale)
    return sale


def apply_update(db: Session, sale: Sale, data, user: UserProfile) -> Sale:
    if user.role not in _STAFF_ROLES:
        raise HTTPException(403, detail="Keine Berechtigung für diesen Verkauf")
    order = db.query(Order).filter(Order.id == sale.order_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    payload = data.model_dump(exclude_unset=True)
    payload.pop("step_id", None)
    target = payload.pop("status", None)
    if sale.status in ("paid", "cancelled") and (payload or target):
        raise HTTPException(400, detail="Abgeschlossener Verkauf ist gesperrt")
    for key in _EDITABLE:
        if key in payload:
            setattr(sale, key, payload[key])
    if target and target != sale.status:
        _apply_transition(db, sale, order, target, user)
    db.commit()
    db.refresh(sale)
    return sale
