"""Factory für den Versand-Provider (analog ``services/payments``).

Mehrere Aggregatoren stehen hinter EINEM Interface und lassen sich per Konfiguration
wählen (``shipping_provider``): **sendcloud** (europäisch, native Schweiz-Herkunft –
Swiss Post/DPD/DHL, self-serve, Test-Labels gratis), **shippo** (US-zentriert, bleibt als
Fallback/Alternative) oder **manual** (Carrier/Tracking von Hand – ohne Keys nie kaputt).

Auswahl (``provider_name``):
  • ``shipping_provider='auto'`` (Default): bevorzugt **sendcloud** (beide Keys gesetzt),
    dann **shippo** (Key gesetzt), sonst **manual**.
  • Expliziter Wert ('sendcloud'|'shippo'|'manual'): wird genommen, sofern konfiguriert –
    sonst fällt es auf die Auto-Reihenfolge zurück (nie kaputt).

So laufen beide Adapter im Code parallel; der aktive wird durch die vorhandenen Secrets
bzw. den expliziten Schalter bestimmt.
"""

from ...core.config import get_settings
from .base import ShippingProvider
from .manual import ManualShipping
from .sendcloud import SendcloudShipping
from .shippo import ShippoShipping

_PROVIDERS = {
    "manual": ManualShipping,
    "shippo": ShippoShipping,
    "sendcloud": SendcloudShipping,
}


def _configured(settings, name: str) -> bool:
    """Ist der genannte Provider einsatzbereit (Keys vorhanden)?"""
    if name == "sendcloud":
        return bool(settings.sendcloud_public_key and settings.sendcloud_secret_key)
    if name == "shippo":
        return bool(settings.shippo_api_key)
    return name == "manual"


def provider_name() -> str:
    settings = get_settings()
    pref = (settings.shipping_provider or "auto").strip().lower()
    if pref in _PROVIDERS and pref != "auto" and _configured(settings, pref):
        return pref
    # Auto-Reihenfolge: Sendcloud ≻ Shippo ≻ manual.
    if _configured(settings, "sendcloud"):
        return "sendcloud"
    if _configured(settings, "shippo"):
        return "shippo"
    return "manual"


def get_provider() -> ShippingProvider:
    return _PROVIDERS[provider_name()]()
