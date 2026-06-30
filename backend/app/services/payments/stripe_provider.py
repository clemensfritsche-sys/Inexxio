"""Stripe-Provider – **Vollintegration** (hosted Checkout + Adaptive Pricing + Stripe Tax).

- ``create_checkout``: erstellt eine Stripe **Checkout Session** (Redirect). KEINE Währung
  gesetzt → **Adaptive Pricing** zeigt dem Kunden seine Lokalwährung; ``automatic_tax`` →
  **Stripe Tax** berechnet die MWST länderabhängig. Modus ``payment`` (Einmalkauf) oder
  ``subscription`` (Abo). Preise inline als ``price_data`` (CHF-Basis, ``tax_behavior``).
- ``handle_webhook``: signaturgeprüft (``STRIPE_WEBHOOK_SECRET``); spiegelt Zahlung/Abo-Status
  und friert den **real bezahlten** Betrag/Währung/Steuer als Snapshot ein (Stripe = Quelle
  der Wahrheit). Defer-Modell: der Auftrag wird erst bei bestätigter Zahlung freigegeben.
- ``create_portal_session``: Stripe **Customer Portal** (Abo/Zahlungsmittel selbst verwalten).

Hart geschützt: ohne ``STRIPE_SECRET_KEY`` ist der Provider nie aktiv (sauberer 503, kein Crash).
"""

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...models import Article, Order, Sale, UserProfile
from .. import pricing, sale as sale_svc
from ..events import emit
from .base import PaymentProvider


def _stripe():
    """Das Stripe-SDK mit gesetztem Key – oder sauberer 503, wenn nicht konfiguriert."""
    key = get_settings().stripe_secret_key
    if not key:
        raise HTTPException(
            503, detail="Stripe ist nicht konfiguriert (STRIPE_SECRET_KEY fehlt).")
    import stripe
    stripe.api_key = key
    return stripe


def _ship_countries() -> list[str]:
    raw = get_settings().shop_ship_countries or "CH"
    return [c.strip().upper() for c in raw.split(",") if c.strip()]


def _full_name(u: UserProfile) -> str | None:
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or None


def _ensure_customer(db: Session, stripe, user: UserProfile) -> str:
    """Den Stripe-Customer zum UserProfile holen/anlegen (idempotent, gecached)."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    cust = stripe.Customer.create(
        email=user.email,
        name=_full_name(user),
        metadata={"user_id": user.id, "object_id": user.object_id or ""},
    )
    user.stripe_customer_id = cust.id
    db.commit()
    return cust.id


class StripeProvider(PaymentProvider):
    name = "stripe"

    # ─── Checkout ────────────────────────────────────────────────────────────────
    def create_checkout(self, db: Session, order: Order, sale: Sale) -> str:
        stripe = _stripe()
        settings = get_settings()
        article = db.query(Article).filter(Article.id == sale.article_id).first()
        user = db.query(UserProfile).filter(UserProfile.id == sale.customer_id).first()
        if not article or not user:
            raise HTTPException(400, detail="Artikel/Kunde für den Checkout fehlt")
        price = pricing.resolve_primary_price(db, article)
        if not price:
            raise HTTPException(400, detail="Kein Preis hinterlegt")

        customer_id = _ensure_customer(db, stripe, user)
        unit_amount = int((Decimal(price.amount_chf) * 100).quantize(Decimal("1")))
        tax_behavior = "inclusive" if settings.prices_tax_inclusive else "exclusive"
        is_sub = bool(order.recurrence_active)

        price_data = {
            "currency": "chf",                  # Basis – Adaptive Pricing rechnet lokal um
            "unit_amount": unit_amount,
            "tax_behavior": tax_behavior,
            "product_data": {
                "name": article.name,
                "tax_code": settings.stripe_default_tax_code,
                "metadata": {"article_object_id": article.object_id or ""},
            },
        }
        if is_sub:
            price_data["recurring"] = {"interval": "year" if price.interval == "year" else "month"}

        base = settings.frontend_base_url.rstrip("/")
        meta = {"order_object_id": str(order.object_id)}
        params = {
            "mode": "subscription" if is_sub else "payment",
            "customer": customer_id,
            "line_items": [{"price_data": price_data, "quantity": order.quantity or 1}],
            # Stripe Tax nur, wenn im Dashboard eingerichtet (sonst schlägt die Session fehl).
            "automatic_tax": {"enabled": bool(settings.stripe_tax_enabled)},
            "billing_address_collection": "auto",
            "shipping_address_collection": {"allowed_countries": _ship_countries()},
            "customer_update": {"address": "auto", "name": "auto", "shipping": "auto"},
            "metadata": meta,
            "success_url": f"{base}/shop/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{base}/shop/product?id={article.object_id}",
            # KEINE currency → Adaptive Pricing wählt die Lokalwährung des Kunden.
        }
        if is_sub:
            params["subscription_data"] = {"metadata": meta}
        else:
            params["payment_intent_data"] = {"metadata": meta}

        session = stripe.checkout.Session.create(**params)
        order.stripe_checkout_session_id = session.id
        db.commit()
        return session.url

    # ─── Webhook ─────────────────────────────────────────────────────────────────
    def handle_webhook(self, db: Session, raw: bytes, sig: str | None,
                       payload: dict | None) -> Sale | None:
        stripe = _stripe()
        secret = get_settings().stripe_webhook_secret
        if secret:
            try:
                event = stripe.Webhook.construct_event(raw, sig, secret)
            except Exception as e:  # ungültige Signatur → 400 (Stripe wiederholt nicht endlos)
                raise HTTPException(400, detail=f"Ungültige Webhook-Signatur: {e}")
        else:
            # Ohne Secret (noch nicht konfiguriert): unverifiziert parsen + warnen.
            print("WARNING: STRIPE_WEBHOOK_SECRET fehlt – Webhook unverifiziert verarbeitet.", flush=True)
            event = payload or json.loads(raw or b"{}")

        etype = event["type"] if isinstance(event, dict) else event.type
        obj = (event["data"]["object"] if isinstance(event, dict) else event.data.object)

        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            return self._on_completed(db, stripe, obj)
        if etype in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            return self._on_failed(db, obj)
        if etype == "customer.subscription.deleted":
            return self._on_subscription_ended(db, obj)
        if etype == "invoice.paid":
            # Wiederkehrende Verrechnung läuft in Stripe (Quelle der Wahrheit) – wir spiegeln
            # nur. Folge-Fulfillment je Zyklus ist eine dokumentierte Erweiterung.
            emit(db, "stripe.invoice_paid", object_type="organization", object_id=None,
                 payload={"subscription": _get(obj, "subscription")})
            db.commit()
            return None
        return None

    # ─── Event-Handler ───────────────────────────────────────────────────────────
    def _resolve_sale(self, db: Session, session) -> tuple[Order, Sale] | tuple[None, None]:
        oid = (_get(session, "metadata") or {}).get("order_object_id")
        if not oid:
            return None, None
        order = db.query(Order).filter(Order.object_id == int(oid)).first()
        if not order:
            return None, None
        sale = db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).first()
        return order, sale

    def _on_completed(self, db: Session, stripe, session) -> Sale | None:
        status = _get(session, "payment_status")
        if status not in ("paid", "no_payment_required", None):
            return None   # asynchrone Methode noch offen → async_payment_succeeded abwarten
        order, sale = self._resolve_sale(db, session)
        if not order or not sale:
            return None
        snap = self._snapshot(stripe, session)
        sub = _get(session, "subscription")
        if sub:
            order.stripe_subscription_id = sub
        return sale_svc.finalize_paid(db, sale, stripe=snap)

    def _on_failed(self, db: Session, session) -> Sale | None:
        order, sale = self._resolve_sale(db, session)
        if sale:
            return sale_svc.mark_cancelled(db, sale)
        return None

    def _on_subscription_ended(self, db: Session, sub) -> Sale | None:
        sub_id = _get(sub, "id")
        order = db.query(Order).filter(Order.stripe_subscription_id == sub_id).first()
        if order and order.recurrence_active:
            order.recurrence_active = False
            emit(db, "subscription.cancelled", object_type="order", object_id=order.object_id)
            db.commit()
        return None

    def _snapshot(self, stripe, session) -> dict:
        """Real bezahlten Betrag/Währung/Steuer aus der Session lesen (Settlement = CHF;
        Adaptive-Pricing-Lokalwährung via ``presentment_details``)."""
        total = Decimal(str(_get(session, "amount_total") or 0)) / 100
        td = _get(session, "total_details") or {}
        tax = Decimal(str((td.get("amount_tax") if isinstance(td, dict) else _get(td, "amount_tax")) or 0)) / 100
        net = total - tax
        cur = (_get(session, "currency") or "chf").upper()
        pres = _get(session, "presentment_details") or {}
        presentment = {}
        if pres:
            presentment = {
                "currency": (_dig(pres, "presentment_currency") or "").upper() or None,
                "total": _money(_dig(pres, "presentment_amount")),
            }
        return {
            "settlement": {"currency": cur, "total": _q(total), "tax": _q(tax)},
            "presentment": presentment,
            "payment_intent": _get(session, "payment_intent"),
            "subscription": _get(session, "subscription"),
            "mode": _get(session, "mode"),
            "tax_rate": str((tax / net * 100).quantize(Decimal("0.01"))) if net > 0 else "0",
        }

    # ─── Customer Portal ─────────────────────────────────────────────────────────
    def create_portal_session(self, db: Session, user: UserProfile, return_url: str) -> str | None:
        stripe = _stripe()
        if not user.stripe_customer_id:
            raise HTTPException(404, detail="Kein Stripe-Kunde – noch kein Kauf getätigt")
        ps = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id, return_url=return_url)
        return ps.url


# ─── Helfer (tolerant ggü. dict ODER Stripe-Objekt) ──────────────────────────────

def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _dig(obj, key):
    return _get(obj, key)


def _money(v) -> str | None:
    if v is None:
        return None
    return str((Decimal(str(v)) / 100).quantize(Decimal("0.01")))


def _q(v: Decimal) -> str:
    return str(v.quantize(Decimal("0.01")))
