from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# requested → quoted → ordered → received  (+ rejected); webshop: requested → ordered → received
ALLOWED_STATUS = ("requested", "quoted", "ordered", "received", "rejected")


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
    # Aktueller Lagerort beim Wareneingang (Pflicht beim Übergang auf «received»)
    receiving_location_id: Optional[int] = None
    # Mehr-Operationen-Routing: welcher Beschaffungs-Schritt (mehrere gleichartige möglich).
    step_id: Optional[int] = None
    # Mehrpositionen-Auftrag: bei >1 Bestellung unter demselben Schritt legt dies fest,
    # WELCHE Position Betrag/Lieferzeit/Tracking betreffen (interne Artikel-Id).
    article_id: Optional[int] = None

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


class PurchaseHistoryEntry(BaseModel):
    """Audit-Eintrag eines Statuswechsels (für Hover-Anzeige im Stepper)."""

    status: str
    at: datetime
    by: Optional[str] = None


class PurchaseEmbed(BaseModel):
    """Ausführungsstand des Beschaffungsschritts – eingebettet in den Auftrag.

    Bewusst OHNE eigene Objektnummer: die Bestellung läuft unter der
    Auftragsnummer und ist kein eigenständiges Objekt. Der Stückpreis wird aus
    ``order_total ÷ Menge`` berechnet (nicht gespeichert).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: str
    supplier_id: Optional[int]
    status: str
    # Interne Artikel-Id + Menge DIESER Position – bei einem Mehrpositionen-Auftrag trägt
    # jede Bestellung einen ANDEREN Artikel (``order.article_id`` ist dann NULL). Die id
    # dient zugleich als Disambiguierung bei ``PATCH .../purchase`` (``article_id``).
    article_id: Optional[int] = None
    quantity: Optional[float] = None   # Bruchmenge möglich (kg/m²/…)

    order_total: Optional[Decimal]
    lead_time_days: Optional[int]
    payment_terms_days: Optional[int]
    tracking_number: Optional[str]
    ordered_at: Optional[datetime]
    landed_unit_cost: Optional[Decimal]
    webshop_url: Optional[str]
    receiving_location_id: Optional[int] = None

    created_at: datetime
    updated_at: datetime

    # Denormalisiert vom Router
    supplier_name: Optional[str] = None
    receiving_location_label: Optional[str] = None   # Lieferadresse/Wareneingang (Objektnr.)
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    # Stammdaten DIESER Position für die «Für Lieferant sichtbar»-Karte – bei einem
    # Mehrpositionen-Auftrag ist ``order.article_*`` NULL, die Werte müssen je Bestellung kommen.
    article_unit: Optional[str] = None
    article_size: Optional[str] = None
    article_weight_kg: Optional[Decimal] = None
    article_serialization: Optional[str] = None
    article_supplier_article_number: Optional[str] = None
    # Artikel-Stammdaten-Keys, die der Lieferant sehen darf
    shared_fields: list[str] = []
    # Audit-Verlauf der Statuswechsel (Wer/Wann)
    history: list[PurchaseHistoryEntry] = []
