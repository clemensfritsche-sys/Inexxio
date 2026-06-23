from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# requested → confirmed → invoiced → paid  (+ cancelled) – Spiegel der Beschaffung.
ALLOWED_STATUS = ("requested", "confirmed", "invoiced", "paid", "cancelled")


class SaleUpdate(BaseModel):
    """Statusübergänge & Feldeingaben des Verkaufsschritts (kaufmännisch).

    EIN Verkaufsbetrag (netto); der Stückpreis wird berechnet (read-only)."""

    status: Optional[str] = None
    order_total: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    currency: Optional[str] = None
    customer_id: Optional[int] = None
    invoice_number: Optional[str] = None
    step_id: Optional[int] = None

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


class SaleEmbed(BaseModel):
    """Ausführungsstand des Verkaufsschritts – eingebettet in den Auftrag.

    OHNE eigene Objektnummer (läuft unter dem Auftrag). Stückpreis = Summe ÷ Menge.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    quantity: Optional[int] = None
    customer_id: Optional[int] = None
    order_total: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    currency: str = "CHF"
    invoice_number: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    invoiced_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None

    # Denormalisiert vom Service
    customer_name: Optional[str] = None
