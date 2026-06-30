"""Zahlungs-Bridge – ein Interface, hinter dem **stripe** (Vollintegration) und
**manual** (überbrückbarer Test-Provider) liegen. So bleibt der Checkout provider-agnostisch.

- ``create_checkout`` erzeugt die Zahl-URL (Stripe Checkout Session bzw. interne Test-Seite).
- ``handle_webhook`` verarbeitet die Rückmeldung (Stripe-Webhook signaturgeprüft, manual via
  Simulations-Payload) und setzt den Verkaufs-Status (mit Snapshot/Auftragsfreigabe).
- ``create_portal_session`` (optional) liefert einen Self-Service-Link (Stripe Customer Portal).
"""

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from ...models import CheckoutIntent, UserProfile


class PaymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_checkout(self, db: Session, intent: CheckoutIntent,
                        customer: UserProfile) -> dict:
        """Zahlungs-Session für einen Warenkorb-Intent erzeugen. Liefert ein Dict mit
        ``session_id``/``client_secret`` (Stripe, eingebettete Kasse) bzw. ``payment_url``
        (Redirect, manueller Fallback)."""

    @abstractmethod
    def handle_webhook(self, db: Session, raw: bytes, sig: str | None,
                       payload: dict | None) -> CheckoutIntent | None:
        """Provider-Ereignis verarbeiten (Zahlung/Abo). Liefert den betroffenen
        ``CheckoutIntent`` (oder None, wenn das Ereignis nichts betrifft)."""

    def create_portal_session(self, db: Session, user: UserProfile, return_url: str) -> str | None:
        """Self-Service-Portal (Abo/Zahlungsmittel verwalten). Default: nicht unterstützt."""
        return None

    def cancel_subscription(self, db: Session, order) -> bool:
        """Ein Abo (Auftrag) **on-site** kündigen. Default (manual): nur lokal beenden.
        Stripe-Provider kündigt zuerst beim Provider und spiegelt erst danach – so bleibt der
        lokale Status NIE fälschlich «aktiv», wenn die Kündigung beim Provider scheitert."""
        from ..events import emit
        order.recurrence_active = False
        emit(db, "subscription.cancelled", object_type="order", object_id=order.object_id)
        db.commit()
        return True
