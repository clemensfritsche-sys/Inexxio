"""Stripe-Provider – **vollständiges Gerüst** hinter demselben Interface.

Hart geschützt: ohne ``STRIPE_SECRET_KEY`` ist der Provider **nie aktiv** und stürzt
NICHT ab – jede Operation liefert einen sauberen Konfigurations-Fehler (HTTP 503), kein
Crash. Mit Key sind die TODOs zu füllen (Checkout Session + Webhook).

Bewusst NICHT umgesetzt (Schlankheit): echte Live-Charge, Stripe Tax, Abo-Verwaltung
über die Stripe-API. Das Gerüst zeigt nur die Anbindungspunkte.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...models import Order, Sale
from .. import sale as sale_svc
from .base import PaymentProvider


class StripeProvider(PaymentProvider):
    name = "stripe"

    def _require_key(self) -> str:
        key = get_settings().stripe_secret_key
        if not key:
            # «niemals aktiv ohne Key» – sauberer Fehler statt Absturz.
            raise HTTPException(
                503,
                detail="Stripe ist nicht konfiguriert (STRIPE_SECRET_KEY fehlt). "
                       "Bitte PAYMENTS_PROVIDER=manual verwenden oder den Schlüssel hinterlegen.",
            )
        return key

    def create_checkout(self, db: Session, order: Order, sale: Sale) -> str:
        key = self._require_key()
        # TODO(Stripe): Checkout Session anlegen und die Hosted-Checkout-URL zurückgeben.
        #   import stripe; stripe.api_key = key
        #   session = stripe.checkout.Session.create(
        #       mode="payment" if sale ... else "subscription",
        #       line_items=[{"price_data": {... aus dem Snapshot ...}, "quantity": sale.quantity}],
        #       success_url=f"{frontend}/shop/pay/{order.object_id}?status=success",
        #       cancel_url=f"{frontend}/shop/pay/{order.object_id}?status=cancel",
        #       client_reference_id=str(order.object_id),
        #       metadata={"order_object_id": order.object_id})
        #   return session.url
        raise HTTPException(501, detail="Stripe-Checkout ist noch nicht implementiert (Gerüst).")

    def handle_event(self, db: Session, payload: dict) -> Sale | None:
        self._require_key()
        # TODO(Stripe): Webhook-Signatur prüfen (STRIPE_WEBHOOK_SECRET) und das Event
        #   auswerten:
        #   event = stripe.Webhook.construct_event(raw_body, sig_header, webhook_secret)
        #   if event.type == "checkout.session.completed":
        #       oid = int(event.data.object.metadata["order_object_id"])
        #       order = ...; sale = ...; return sale_svc.mark_paid(db, sale)
        #   if event.type in ("checkout.session.expired", ...):
        #       return sale_svc.mark_cancelled(db, sale)
        _ = sale_svc  # Anbindungspunkt (wie manual): mark_paid/mark_cancelled
        raise HTTPException(501, detail="Stripe-Webhook ist noch nicht implementiert (Gerüst).")
