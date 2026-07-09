"""Schemas Logistik/Versand (ADR 005) – «Versand wird abgeleitet, nicht bestellt».

Der Bewegungs-Schritt kennt Quelle und Ziel; die Klassifikation leitet daraus die
**Transportklasse** ab (intern | extern | unbekannt) und – bei extern – die Richtung
(outbound | inbound). Das ``ShipmentEmbed`` fährt im Bewegungs-Embed des Auftrags mit;
das Frontend zeigt daraus die Versand-Box (Tarife, günstigster vorgewählt, Label).
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# Transport-Modus (deklariert am Schritt, je Auftrag am Shipment übersteuerbar):
#   auto    → abgeleitet: Ziel extern → Versand, sonst nichts (Default)
#   carrier → immer Versand (auch wenn die Ableitung «intern» sagt)
#   self    → Selbsttransport (bringen/abholen) – protokolliert, kein Carrier
#   none    → nie ein Versand (z. B. rein organisatorische Bewegung)
ALLOWED_TRANSPORT_MODES = ("auto", "carrier", "self", "none")


class ShipmentRate(BaseModel):
    """Ein Angebot aus dem Rate-Shopping (Snapshot, unveränderlich)."""

    rate_id: str
    carrier: str
    service: Optional[str] = None
    amount: float
    currency: str = "CHF"
    days: Optional[int] = None          # geschätzte Laufzeit (Tage)
    cheapest: bool = False              # Empfehlung (Default-Auswahl)
    fastest: bool = False               # Hinweis «Schnellster»


class ShipmentEmbed(BaseModel):
    """Eingebetteter Versand-Stand eines Bewegungs-Schritts (im Auftrag)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    exists: bool = False                 # gibt es schon eine Shipment-Fachzeile?
    # Live-Ableitung: intern | extern | unknown (+ Richtung bei extern)
    transport_class: str = "unknown"
    direction: str = "outbound"          # outbound | inbound
    transport_mode: str = "auto"         # effektiver Modus (Shipment-Override ≻ Schritt)
    status: str = "draft"                # draft | quoted | purchased | done | cancelled
    provider: str = "manual"             # shippo | manual | self
    provider_ready: bool = False         # Aggregator konfiguriert (Rate-Shopping möglich)?

    from_label: Optional[str] = None     # Anzeige: Absender (kompakt)
    to_label: Optional[str] = None       # Anzeige: Empfänger (kompakt)
    parcels: list[dict] = []             # [{weight_kg, length_cm, width_cm, height_cm}]
    hazmat: bool = False                 # Gefahrgut an Bord (Warnung/Spezialversand)

    rates: list[ShipmentRate] = []
    chosen_rate_id: Optional[str] = None
    carrier: Optional[str] = None
    service: Optional[str] = None
    label_url: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    cost_amount: Optional[Decimal] = None
    cost_currency: Optional[str] = None
    note: Optional[str] = None


class ShipmentQuoteRequest(BaseModel):
    """Tarife laden (Rate-Shopping) für den Versand eines Bewegungs-Schritts."""

    step_id: Optional[int] = None


class ShipmentBuyRequest(BaseModel):
    """Gewähltes Angebot kaufen → Label + Tracking."""

    rate_id: str
    step_id: Optional[int] = None


class ShipmentUpdate(BaseModel):
    """Transport-Modus übersteuern bzw. manuelle Versanddaten erfassen (manual/self)."""

    step_id: Optional[int] = None
    transport_mode: Optional[str] = None
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    cost_amount: Optional[float] = None
    cost_currency: Optional[str] = None
    note: Optional[str] = None

    @field_validator("transport_mode")
    @classmethod
    def _mode_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in ALLOWED_TRANSPORT_MODES:
            raise ValueError(f"Transport-Modus muss eine von {', '.join(ALLOWED_TRANSPORT_MODES)} sein")
        return v

    @field_validator("cost_currency")
    @classmethod
    def _cur_ok(cls, v: Optional[str]) -> Optional[str]:
        return v.upper()[:3] if v else None
