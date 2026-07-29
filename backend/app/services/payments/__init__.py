"""Factory für den Zahlungs-Provider.

Auswahl (Reihenfolge): ausdrückliche ``company_settings.payments_provider`` →
sonst **automatisch ``stripe``, sobald ``STRIPE_SECRET_KEY`` gesetzt ist** → sonst die Env
``PAYMENTS_PROVIDER`` (Default ``manual``). So aktiviert sich Stripe von selbst, sobald der
Schlüssel im Secret Manager liegt; ``manual`` bleibt der Fallback für Tests ohne Keys.
"""

from sqlalchemy.orm import Session

from ...core.config import get_settings
from .base import PaymentProvider
from .manual import ManualProvider
from .stripe_provider import StripeProvider

_PROVIDERS = {
    "manual": ManualProvider,
    "stripe": StripeProvider,
}


def provider_name(db: Session | None = None) -> str:
    settings = get_settings()
    has_key = bool(settings.stripe_secret_key)
    # 1) Ausdrückliche Konfiguration (Admin) hat Vorrang.
    explicit = ""
    if db is not None:
        from ..sites import find_primary
        s = find_primary(db)          # Provider-Wahl: Systemkonfiguration am Hauptsitz
        explicit = (s.payments_provider or "") if s else ""
    if explicit in _PROVIDERS:
        if explicit == "stripe" and not has_key:
            return "manual"                    # gewählt, aber ohne Key nicht aktivierbar
        return explicit
    # 2) Auto: Key vorhanden → stripe.
    if has_key:
        return "stripe"
    # 3) Fallback: Env-Default (manual).
    name = settings.payments_provider or "manual"
    return name if name in _PROVIDERS else "manual"


def get_provider(db: Session | None = None) -> PaymentProvider:
    return _PROVIDERS[provider_name(db)]()
