"""Factory für den Versand-Provider (analog ``services/payments``).

Auswahl: **automatisch ``easypost``, sobald ``EASYPOST_API_KEY`` gesetzt ist** – sonst
``manual`` (Carrier/Tracking von Hand, kein externer Call). So aktiviert sich das
Rate-Shopping von selbst, wenn der Schlüssel im Secret Manager liegt; ohne Key ist
der Versand-Prozess trotzdem vollständig nutzbar (nie kaputt).
"""

from ...core.config import get_settings
from .base import ShippingProvider
from .easypost import EasyPostShipping
from .manual import ManualShipping

_PROVIDERS = {
    "manual": ManualShipping,
    "easypost": EasyPostShipping,
}


def provider_name() -> str:
    settings = get_settings()
    return "easypost" if settings.easypost_api_key else "manual"


def get_provider() -> ShippingProvider:
    return _PROVIDERS[provider_name()]()
