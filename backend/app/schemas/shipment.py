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

# Sendungsart (Phase 0 Fracht): parcel (Paket → Aggregator/Rate-Shopping) | freight
# (Stückgut/Palette → manuell/Spediteur). Abgeleitet aus der Last, am Beleg übersteuerbar.
ALLOWED_SHIPMENT_KINDS = ("parcel", "freight")
# Incoterms 2020 (international, Fracht) – die gängigsten.
ALLOWED_INCOTERMS = ("EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FOB", "CFR", "CIF")


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

    kind: str = "parcel"                 # parcel (Paket) | freight (Stückgut/Palette, Phase 0)
    incoterm: Optional[str] = None       # Fracht/international (EXW, FCA, DAP, DDP …)
    pickup_date: Optional[str] = None    # Wunsch-Abholtermin (ISO YYYY-MM-DD), Fracht

    from_label: Optional[str] = None     # Anzeige: Absender (kompakt)
    to_label: Optional[str] = None       # Anzeige: Empfänger (kompakt)
    parcels: list[dict] = []             # [{weight_kg, length_cm, width_cm, height_cm}]
    load: Optional[dict] = None          # Fracht-Last {pallets, loading_meters, volume_m3, …}
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
    # Phase-0-Fracht: Sendungsart übersteuern + Fracht-Last/Incoterm/Abholtermin verfeinern.
    kind: Optional[str] = None
    load: Optional[dict] = None
    incoterm: Optional[str] = None
    pickup_date: Optional[str] = None

    @field_validator("transport_mode")
    @classmethod
    def _mode_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in ALLOWED_TRANSPORT_MODES:
            raise ValueError(f"Transport-Modus muss eine von {', '.join(ALLOWED_TRANSPORT_MODES)} sein")
        return v

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in ALLOWED_SHIPMENT_KINDS:
            raise ValueError(f"Sendungsart muss eine von {', '.join(ALLOWED_SHIPMENT_KINDS)} sein")
        return v

    @field_validator("incoterm")
    @classmethod
    def _incoterm_ok(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip().upper()
        if v not in ALLOWED_INCOTERMS:
            raise ValueError(f"Incoterm muss eine von {', '.join(ALLOWED_INCOTERMS)} sein")
        return v

    @field_validator("cost_currency")
    @classmethod
    def _cur_ok(cls, v: Optional[str]) -> Optional[str]:
        return v.upper()[:3] if v else None
