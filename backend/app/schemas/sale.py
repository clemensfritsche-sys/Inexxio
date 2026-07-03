from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# requested → confirmed → invoiced → paid  (+ cancelled) – Spiegel der Beschaffung.
ALLOWED_STATUS = ("requested", "confirmed", "invoiced", "paid", "cancelled")
# Zahlungsart, die Personal manuell wählen kann – kein Kartenterminal nötig, der übliche
# B2B-Weg ist Rechnung/QR-Rechnung. 'stripe' setzt das System selbst (Shop-Zahlung);
# 'terminal' (Stripe Terminal / Kartenleser vor Ort) ist als Wert vorgesehen (Phase 2+),
# aber hier bewusst noch nicht wählbar.
ALLOWED_PAYMENT_METHODS = ("invoice", "cash", "twint", "other")


class SaleUpdate(BaseModel):
    """Statusübergänge & Feldeingaben des Verkaufsschritts (kaufmännisch).

    EIN Verkaufsbetrag (netto); der Stückpreis wird berechnet (read-only)."""

    status: Optional[str] = None
    order_total: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    currency: Optional[str] = None
    customer_id: Optional[int] = None
    invoice_number: Optional[str] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
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

    # FIX: ``currency`` war ein freier String – "EURO" wäre erst an der DB-Spalte
    # (VARCHAR(3)) mit einem 500er gescheitert; ``vat_rate`` hatte keine Grenzen
    # (negativ/1000 % → falscher Brutto in «Meine Bestellungen»). Früh validieren.
    @field_validator("currency")
    @classmethod
    def _currency_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError("Währung muss ein 3-Buchstaben-Code sein (z. B. CHF)")
        return v

    @field_validator("vat_rate")
    @classmethod
    def _vat_rate_ok(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        if v < 0 or v > 100:
            raise ValueError("MWST-Satz muss zwischen 0 und 100 liegen")
        return v

    @field_validator("payment_method")
    @classmethod
    def _payment_method_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_PAYMENT_METHODS:
            raise ValueError(f"Zahlungsart muss eine von {', '.join(ALLOWED_PAYMENT_METHODS)} sein")
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
    # Verkauf vs. Gutschrift (Retoure): 'sale' | 'credit'. Bei 'credit' ist der Betrag eine
    # Gutschrift/Erstattung (Umsatz-/MWST-Umkehr); ``credit_note_number`` = unveränderlicher
    # Gutschrift-Beleg, ``refunded_at``/``stripe_refund_id`` = erfolgte Rückerstattung.
    kind: str = "sale"
    credit_note_number: Optional[str] = None
    original_sale_id: Optional[int] = None
    refunded_at: Optional[datetime] = None
    stripe_refund_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    invoiced_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    # Herkunft ('shop' = Kasse/Stripe, 'direct' = Personal im ERP) + Zahlungsart des
    # manuellen Zahlungseingangs (Rechnung/Bar/Twint/Sonstiges; 'stripe' = Shop-Zahlung).
    mode: Optional[str] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    # Artikel dieser Position (bei einem Mehrpositionen-Auftrag je Schritt unterschiedlich).
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None

    # Denormalisiert vom Service
    customer_name: Optional[str] = None
