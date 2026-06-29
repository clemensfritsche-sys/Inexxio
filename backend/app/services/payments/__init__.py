"""Factory für den Zahlungs-Provider.

Auswahl: ``company_settings.payments_provider`` (falls gesetzt) vor der Env
``PAYMENTS_PROVIDER`` (Default ``manual``). Unbekannt → ``manual`` (sicher).
"""

from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...models import CompanySettings
from .base import PaymentProvider
from .manual import ManualProvider
from .stripe_provider import StripeProvider

_PROVIDERS = {
    "manual": ManualProvider,
    "stripe": StripeProvider,
}


def provider_name(db: Session | None = None) -> str:
    """Aktiver Provider-Name: DB-Konfiguration vor Env, Default ``manual``."""
    name = ""
    if db is not None:
        s = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
        name = (s.payments_provider or "") if s else ""
    if not name:
        name = get_settings().payments_provider or "manual"
    return name if name in _PROVIDERS else "manual"


def get_provider(db: Session | None = None) -> PaymentProvider:
    return _PROVIDERS[provider_name(db)]()
