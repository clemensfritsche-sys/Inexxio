from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class PurchaseOrder(Base, TimestampMixin):
    """Ausführung des Prozessschritts «Beschaffung» – läuft unter dem Auftrag.

    KEINE eigene Objektnummer: die Bestellung ist kein eigenständiges Objekt,
    sondern der Ausführungsstand eines Auftrags-Prozessschritts. Referenziert
    wird sie über die Auftragsnummer (``order_id``).

    Verantwortlichkeiten (Modus 'supplier'): Lieferant offeriert, Besteller
    bestellt/lehnt ab und bestätigt den Wareneingang. Im Modus 'webshop' gibt es
    keinen externen Lieferanten – der Mitarbeiter erfasst die Summe und bestellt.

    Status-Ablauf (verschlankt):
        requested  → Angefragt    (angelegt; Lieferant offeriert / Webshop: Summe erfassen)
        quoted     → Offeriert    (Lieferant hat Bestellsumme/Lieferzeit erfasst)  – nur supplier
        ordered    → Bestellt     (Besteller bestellt; Tracking optional)
        received   → Wareneingang (Ware ist eingetroffen → Schritt erledigt)
        rejected   → Abgelehnt    (Besteller lehnt die Offerte ab)               – nur supplier
    """

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Bestellmenge als Dezimalzahl (NUMERIC(14,3)) – ganze Stück ODER Bruchmenge (kg/m²/…).
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    # Routing: an welche Prozessschritt-Definition gebunden (mehrere möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # Bezugsquelle (aus dem Prozessschritt kopiert)
    mode: Mapped[str] = mapped_column(String(20), default="supplier", nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    webshop_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False)

    # Offerte: EINE Bestellsumme (netto, exkl. MWST). Der Stückpreis wird daraus
    # berechnet (nicht gespeichert). Einstandspreis netto/Stück = order_total/Menge.
    order_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    payment_terms_days: Mapped[Optional[int]] = mapped_column(Integer)

    # Abwicklung
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100))
    ordered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Vom System berechneter Einstandspreis netto/Stück (bei «Bestellt»)
    landed_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
