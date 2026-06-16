from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# requested → quoted → approved | rejected → confirmed → received
ALLOWED_STATUS = ("requested", "quoted", "approved", "rejected", "confirmed", "received")


class PurchaseOrderUpdate(BaseModel):
    """Statusübergänge & Feldeingaben einer Bestellung.

    Die Offerte besteht aus EINER Bestellsumme (netto); der Stückpreis wird
    berechnet (read-only). Wer welche Felder/Übergänge setzen darf, validiert
    ``services/purchase.py`` rollenabhängig (Lieferant vs. Mitarbeiter,
    supplier- vs. webshop-Modus).
    """

    status: Optional[str] = None
    order_total: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    payment_terms_days: Optional[int] = None
    tracking_number: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_STATUS:
            raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
        return v

    @field_validator("order_total")
    @classmethod
    def _money_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Betrag darf nicht negativ sein")
        return v

    @field_validator("lead_time_days", "payment_terms_days")
    @classmethod
    def _days_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Anzahl Tage darf nicht negativ sein")
        return v

    @field_validator("tracking_number")
    @classmethod
    def _trim(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip() or None


class PurchaseEmbed(BaseModel):
    """Ausführungsstand des Beschaffungsschritts – eingebettet in den Auftrag.

    Bewusst OHNE eigene Objektnummer: die Bestellung läuft unter der
    Auftragsnummer und ist kein eigenständiges Objekt.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: str
    supplier_id: Optional[int]
    status: str

    order_total: Optional[Decimal]
    unit_price: Optional[Decimal]      # = order_total / Menge (berechnet)
    lead_time_days: Optional[int]
    payment_terms_days: Optional[int]
    tracking_number: Optional[str]
    landed_unit_cost: Optional[Decimal]
    webshop_url: Optional[str]

    created_at: datetime
    updated_at: datetime

    # Denormalisiert vom Router
    supplier_name: Optional[str] = None
    # Artikel-Stammdaten-Keys, die der Lieferant sehen darf
    shared_fields: list[str] = []
