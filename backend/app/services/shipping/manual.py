"""Manueller Versand-Fallback: kein Aggregator konfiguriert.

Der Versand-Beleg existiert trotzdem (Klassifikation/Adressen/Pakete), aber Tarife/
Label kommen nicht automatisch – das Personal erfasst Carrier, Tracking-Nummer und
Kosten von Hand (``PATCH …/shipment``). So funktioniert der Prozess vollständig ohne
externen Dienst und rüstet sich selbst auf, sobald ``SHIPPO_API_KEY`` gesetzt wird.
"""

from fastapi import HTTPException

from .base import ShippingProvider


class ManualShipping(ShippingProvider):
    name = "manual"
    supports_rates = False

    def rates(self, address_from: dict, address_to: dict, parcels: list[dict]) -> dict:
        # kein Rate-Shopping – manuelle Erfassung
        return {"provider_shipment_id": None, "rates": [], "messages": []}

    def buy(self, shipment: dict, provider_rate_id: str) -> dict:
        raise HTTPException(
            503,
            detail="Kein Versand-Anbieter konfiguriert – Carrier/Tracking bitte manuell erfassen "
                   "(oder SHIPPO_API_KEY hinterlegen).",
        )
