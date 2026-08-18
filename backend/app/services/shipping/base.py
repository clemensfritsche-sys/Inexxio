"""Versand-Bridge (ADR 005) – ein Interface, hinter dem der Carrier-Aggregator
(**shippo**: Rate-Shopping über viele Carrier + Label-Kauf, Self-Serve wie Stripe)
und **manual** (Carrier/Tracking von Hand – ohne Key nie kaputt) liegen.

- ``rates`` liefert Angebote (Preis/Laufzeit je Carrier-Service) für Adressen + Paket,
  zusammen mit der Provider-Shipment-Referenz (für den anschliessenden Kauf).
- ``buy`` kauft das gewählte Angebot → Label-PDF + Tracking-Nummer.

Bewusst schlank: Tracking-Webhooks/Pickup-Orders sind dokumentierte Erweiterungen.
"""

from abc import ABC, abstractmethod


class ShippingProvider(ABC):
    name: str = "base"
    supports_rates: bool = False   # kann dieser Provider Tarife laden/Label kaufen?

    @abstractmethod
    def rates(self, address_from: dict, address_to: dict, parcels: list[dict]) -> dict:
        """Angebote laden. Rückgabe: {"provider_shipment_id": str|None, "rates": [
        {rate_id, carrier, service, amount, currency, days, provider_rate_id}],
        "messages": [str]} – amount als float, unsortiert (Sortierung macht der
        Aufrufer). ``messages`` erklärt eine leere Tarifliste (z. B. »Herkunftsland
        nicht unterstützt«) und wird dem Nutzer gezeigt. Wirft HTTPException bei
        echten Provider-/Netzwerkfehlern (HTTP ≥ 400)."""

    @abstractmethod
    def buy(self, shipment: dict, provider_rate_id: str) -> dict:
        """Das gewählte Angebot kaufen → Label + Tracking.

        ``shipment`` trägt den Kontext, den manche Anbieter erst beim Kauf brauchen:
        {"provider_shipment_id", "address_from", "address_to", "parcels"}. Shippo kauft
        allein gegen die Rate-Objektnummer (ignoriert den Rest); Sendcloud legt hier das
        Paket (Adresse + Gewicht + Methode) an. Rückgabe: {label_url, tracking_number,
        tracking_url, provider_shipment_id}. Wirft HTTPException bei Provider-Fehlern."""
