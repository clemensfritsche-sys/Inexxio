"""Manueller Zahlungs-Provider – **kein externer Call** (Fallback für Tests ohne Stripe-Keys).

``create_checkout`` liefert eine interne Seite ``/shop/pay?token=…``; dort simuliert der Kunde
Erfolg/Abbruch. ``handle_webhook`` (ausgelöst von ``POST /shop/payments/simulate``) erzeugt/
finalisiert die Aufträge des Intents bzw. löst ihn auf. Der ``token`` ist die Intent-id.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...models import CheckoutIntent, UserProfile
from .. import selling as selling_svc
from .base import PaymentProvider


def _resolve_intent(db: Session, token: str) -> CheckoutIntent:
    try:
        iid = int(token)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="Ungültiges Zahlungs-Token")
    intent = db.query(CheckoutIntent).filter(
        CheckoutIntent.id == iid, CheckoutIntent.is_active == True).first()
    if not intent:
        raise HTTPException(404, detail="Checkout zum Zahlungs-Token nicht gefunden")
    return intent


class ManualProvider(PaymentProvider):
    name = "manual"

    def create_checkout(self, db: Session, intent: CheckoutIntent,
                        customer: UserProfile) -> dict:
        base = get_settings().frontend_base_url.rstrip("/")
        return {"provider": self.name, "session_id": None, "client_secret": None,
                "payment_url": f"{base}/shop/pay?token={intent.id}"}

    def handle_webhook(self, db: Session, raw: bytes, sig: str | None,
                       payload: dict | None) -> CheckoutIntent | None:
        payload = payload or {}
        token = payload.get("sale_token")
        result = (payload.get("result") or "").lower()
        intent = _resolve_intent(db, str(token))
        if result in ("paid", "success", "succeeded"):
            selling_svc.fulfill_intent(db, intent)        # netto/Steuer aus eigener Pipeline (CHF)
            return intent
        if result in ("cancelled", "canceled", "failed"):
            selling_svc.cancel_intent(db, intent)
            return intent
        raise HTTPException(400, detail="Unbekanntes Zahlungs-Ergebnis (paid|cancelled)")
