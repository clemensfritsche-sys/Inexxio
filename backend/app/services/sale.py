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


def _release_on_payment(db: Session, order: Order, actor_id: int | None) -> None:
    """Auftrag bei bestätigter Zahlung freigeben (Defer-Modell: erst zahlen, dann erfüllen).

    make → erzeugt jetzt die Instanzen; stock → war bereits bei der Bestellung reserviert
    (dann ist der Auftrag schon ``released`` und dies ist ein No-op). Idempotent."""
    if order.status != "draft":
        return
    from .events import emit as _emit
    from .resource import reserve_resources
    from .subject import materialize_subject
    order.status = "released"
    if order.released_at is None:
        order.released_at = utcnow()
    materialize_subject(db, order, actor_id)
    reserve_resources(db, order, actor_id)
    _emit(db, "order.released", object_type="order", object_id=order.object_id,
          payload={"article_id": order.article_id, "quantity": order.quantity, "via": "payment"},
          actor_id=actor_id)


def _apply_stripe_snapshot(sale: Sale, snap: dict) -> None:
    """Real bezahlten Betrag/Währung/Steuer (Stripe) auf den Beleg einfrieren."""
    settlement = snap.get("settlement") or {}
    cur = (settlement.get("currency") or sale.currency or "CHF").upper()
    total = Decimal(str(settlement.get("total") or 0))      # brutto (inkl. Steuer)
    tax = Decimal(str(settlement.get("tax") or 0))
    net = total - tax
    sale.currency = cur
    sale.order_total = net.quantize(Decimal("0.01"))        # netto im Settlement (CHF)
    if net > 0:
        sale.vat_rate = (tax / net * Decimal("100")).quantize(Decimal("0.01"))
    sale.stripe_payment_intent_id = snap.get("payment_intent")
    sale.stripe_snapshot = snap


def finalize_paid(db: Session, sale: Sale, stripe: dict | None = None,
                  release_order: bool = True) -> Sale:
    """Zahlungseingang verarbeiten: Auftrag freigeben (falls noch Entwurf), Snapshot
    einfrieren und den Verkauf auf ``paid`` setzen. Idempotent (Webhooks treffen mehrfach).

    ``stripe`` (optional): real bezahlte Beträge von Stripe (sonst gilt die eigene CHF-Pipeline,
    deren Snapshot bei der Bestellung gesetzt wurde).
    ``release_order=False``: Zahlung verbuchen, aber den Verkaufsauftrag NICHT freigeben
    (Make-to-Order: die Freigabe erfolgt erst, wenn die verknüpfte Produktion fertig ist)."""
    if sale.status == "paid":
        return sale
    order = db.query(Order).filter(Order.id == sale.order_id).first()
    actor_id = sale.customer_id
    if order:
        if release_order:
            _release_on_payment(db, order, actor_id)
        if stripe and stripe.get("subscription") and not order.stripe_subscription_id:
            order.stripe_subscription_id = stripe["subscription"]
    if stripe:
        _apply_stripe_snapshot(sale, stripe)
    now = utcnow()
    if sale.confirmed_at is None:
        sale.confirmed_at = now
    if sale.invoiced_at is None:
        sale.invoiced_at = now
    sale.paid_at = now
    sale.status = "paid"
    oid = order.object_id if order else None
    log_audit(db, "sales", "status", "paid", None, object_id=oid)
    emit(db, "sale.paid", object_type="order", object_id=oid)
    if order:
        process.recompute_completion(db, order)   # ggf. Auftrag abschliessen (Versand erfolgt)
    db.commit()
    db.refresh(sale)
    return sale


def mark_paid(db: Session, sale: Sale) -> Sale:
    """Kompatibilität: Zahlungseingang ohne externen Snapshot (eigene CHF-Pipeline)."""
    return finalize_paid(db, sale, stripe=None)


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
