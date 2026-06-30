"""Stripe-Provider – **Vollintegration** (eingebettete Kasse + Adaptive Pricing + Stripe Tax).

- ``create_checkout``: erstellt eine Stripe **Checkout Session** im Modus ``ui_mode='embedded'``
  (kein Redirect – die Kasse wird auf unserer Seite eingebettet, ``client_secret``). KEINE
  Währung gesetzt → **Adaptive Pricing** zeigt die Lokalwährung; ``automatic_tax`` →
  **Stripe Tax**. Modus ``payment`` (Einmalkauf) oder ``subscription`` (Abo). Mehrere
  Warenkorb-Positionen ⇒ mehrere ``line_items`` in EINER Session. Die Lieferadresse wird
  aus dem **Profil** auf den Stripe-Customer gespiegelt (Vorbefüllung, keine Doppeleingabe).
- ``handle_webhook``: signaturgeprüft; erzeugt/finalisiert bei bestätigter Zahlung die
  Aufträge des Intents (Defer-Modell) und friert den real bezahlten Betrag/Währung/Steuer
  je Position als Snapshot ein (Stripe = Quelle der Wahrheit).
- ``create_portal_session``: Stripe **Customer Portal** (Abo/Zahlungsmittel selbst verwalten).

Hart geschützt: ohne ``STRIPE_SECRET_KEY`` ist der Provider nie aktiv (sauberer 503, kein Crash).
"""

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...models import CheckoutIntent, Order, UserProfile
from .. import sales as sales_svc
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


def _profile_shipping(u: UserProfile) -> dict | None:
    """Lieferadresse aus dem Profil als Stripe-``shipping``-Objekt (oder None, wenn
    unvollständig). So füllt Stripe die Kasse vor – der Kunde tippt nichts erneut (#4)."""
    line1 = u.ship_address_line1 or u.address_line1
    city = u.ship_city or u.city
    postal = u.ship_postal_code or u.postal_code
    country = (u.ship_country or u.country or "CH")
    if not (line1 and city and postal and country):
        return None
    name = u.ship_name or _full_name(u) or u.email
    address = {
        "line1": line1,
        "line2": u.ship_address_line2 or u.address_line2 or None,
        "city": city,
        "postal_code": postal,
        "state": u.ship_state_region or u.state_region or None,
        "country": (country or "CH")[:2].upper(),
    }
    return {"name": name, "address": address}


def _ensure_customer(db: Session, stripe, user: UserProfile) -> str:
    """Den Stripe-Customer zum UserProfile holen/anlegen (idempotent, gecached) und die
    Lieferadresse aus dem Profil spiegeln (Vorbefüllung der Kasse)."""
    shipping = _profile_shipping(user)
    if user.stripe_customer_id:
        if shipping:
            try:
                stripe.Customer.modify(user.stripe_customer_id, shipping=shipping)
            except Exception:
                pass
        return user.stripe_customer_id
    cust = stripe.Customer.create(
        email=user.email,
        name=_full_name(user),
        shipping=shipping or None,
        metadata={"user_id": user.id, "object_id": user.object_id or ""},
    )
    user.stripe_customer_id = cust.id
    db.commit()
    return cust.id


class StripeProvider(PaymentProvider):
    name = "stripe"

    # ─── Checkout ────────────────────────────────────────────────────────────────
    def create_checkout(self, db: Session, intent: CheckoutIntent,
                        customer: UserProfile) -> dict:
        stripe = _stripe()
        settings = get_settings()
        lines = list(intent.lines or [])
        if not lines:
            raise HTTPException(400, detail="Warenkorb ist leer")
        customer_id = _ensure_customer(db, stripe, customer)
        tax_behavior = "inclusive" if settings.prices_tax_inclusive else "exclusive"
        is_sub = any(l.get("kind") == "subscription" for l in lines)

        line_items = [self._line_item(line, tax_behavior) for line in lines]
        base = settings.frontend_base_url.rstrip("/")
        meta = {"intent_id": str(intent.id)}
        params = {
            "ui_mode": "embedded",
            "mode": "subscription" if is_sub else "payment",
            "customer": customer_id,
            "line_items": line_items,
            # Stripe Tax nur, wenn im Dashboard eingerichtet (sonst schlägt die Session fehl).
            "automatic_tax": {"enabled": bool(settings.stripe_tax_enabled)},
            "billing_address_collection": "auto",
            "shipping_address_collection": {"allowed_countries": _ship_countries()},
            "customer_update": {"address": "auto", "name": "auto", "shipping": "auto"},
            "metadata": meta,
            # Eingebettete Kasse nutzt return_url (kein success_url/cancel_url).
            "return_url": f"{base}/shop/success?session_id={{CHECKOUT_SESSION_ID}}",
            # KEINE currency → Adaptive Pricing wählt die Lokalwährung des Kunden.
        }
        if is_sub:
            params["subscription_data"] = {"metadata": meta}
        else:
            params["payment_intent_data"] = {"metadata": meta}

        session = stripe.checkout.Session.create(**params)
        intent.stripe_session_id = session.id
        db.commit()
        return {"provider": self.name, "session_id": session.id,
                "client_secret": session.client_secret, "payment_url": None}

    def _line_item(self, line: dict, tax_behavior: str) -> dict:
        qty = int(line.get("quantity") or 1)
        base = Decimal(str(line.get("base_amount_chf") or 0))
        unit = (base / qty) if qty else base
        price_data = {
            "currency": "chf",                  # Basis – Adaptive Pricing rechnet lokal um
            "unit_amount": int((unit * 100).quantize(Decimal("1"))),
            "tax_behavior": tax_behavior,
            "product_data": {
                "name": line.get("article_name") or "Produkt",
                "tax_code": get_settings().stripe_default_tax_code,
                "metadata": {"article_object_id": line.get("article_object_id") or ""},
            },
        }
        if line.get("kind") == "subscription":
            price_data["recurring"] = {
                "interval": "year" if line.get("interval") == "year" else "month"}
        return {"price_data": price_data, "quantity": qty}

    # ─── Webhook ─────────────────────────────────────────────────────────────────
    def handle_webhook(self, db: Session, raw: bytes, sig: str | None,
                       payload: dict | None) -> CheckoutIntent | None:
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
            return self._on_invoice_paid(db, obj)
        return None

    # ─── Event-Handler ───────────────────────────────────────────────────────────
    def _resolve_intent(self, db: Session, session) -> CheckoutIntent | None:
        iid = (_get(session, "metadata") or {}).get("intent_id")
        if iid:
            it = db.query(CheckoutIntent).filter(CheckoutIntent.id == int(iid)).first()
            if it:
                return it
        sid = _get(session, "id")
        return db.query(CheckoutIntent).filter(
            CheckoutIntent.stripe_session_id == sid).first() if sid else None

    def _on_completed(self, db: Session, stripe, session) -> CheckoutIntent | None:
        status = _get(session, "payment_status")
        if status not in ("paid", "no_payment_required", None):
            return None   # asynchrone Methode noch offen → async_payment_succeeded abwarten
        intent = self._resolve_intent(db, session)
        if not intent:
            return None
        snap = self._snapshot(stripe, session)
        sales_svc.fulfill_intent(db, intent, snapshot=snap)
        return intent

    def _on_failed(self, db: Session, session) -> CheckoutIntent | None:
        intent = self._resolve_intent(db, session)
        if intent:
            sales_svc.cancel_intent(db, intent)
        return intent

    def _on_subscription_ended(self, db: Session, sub) -> CheckoutIntent | None:
        sub_id = _get(sub, "id")
        order = db.query(Order).filter(Order.stripe_subscription_id == sub_id).first()
        if order and order.recurrence_active:
            order.recurrence_active = False
            emit(db, "subscription.cancelled", object_type="order", object_id=order.object_id)
            db.commit()
        return None

    def _on_invoice_paid(self, db: Session, invoice) -> CheckoutIntent | None:
        """Wiederkehrende Verrechnung läuft in Stripe (Quelle der Wahrheit) – wir spiegeln.
        Beim **Produktabo** wäre hier das Folge-Fulfillment je Zyklus zu erzeugen; beim
        **Nutzungsabo** (Zugang/Miete) ist nichts zu liefern. Das eigentliche Erzeugen des
        Folgeauftrags ist die dokumentierte nächste Erweiterung (TODO-Hook unten)."""
        sub_id = _get(invoice, "subscription")
        order = (db.query(Order).filter(Order.stripe_subscription_id == sub_id).first()
                 if sub_id else None)
        kind = order.recurrence_kind if order else None
        emit(db, "stripe.invoice_paid", object_type="order",
             object_id=order.object_id if order else None,
             payload={"subscription": sub_id, "recurrence_kind": kind})
        # TODO(Erweiterung): kind == 'product' → Folge-Fulfillment-Auftrag je Zyklus erzeugen.
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
