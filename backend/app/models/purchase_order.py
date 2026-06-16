from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class PurchaseOrder(Base, TimestampMixin):
    """Ausführung des Prozessschritts «Beschaffung» – läuft unter dem Auftrag.

    KEINE eigene Objektnummer: die Bestellung ist kein eigenständiges Objekt,
    sondern der Ausführungsstand eines Auftrags-Prozessschritts. Referenziert
    wird sie über die Auftragsnummer (``order_id``).

    Verantwortlichkeiten (Modus 'supplier'): Offerte/Bestätigung = Lieferant,
    Freigabe/Ablehnung/Wareneingang = Besteller. Im Modus 'webshop' führt der
    Mitarbeiter alle Schritte.

    Status-Ablauf:
        requested  → Angefragt    (angelegt, wartet auf Offerte des Lieferanten)
        quoted     → Offeriert    (Bestellsumme/Lieferzeit erfasst)
        approved   → Freigegeben  (Besteller akzeptiert die Offerte)
        rejected   → Abgelehnt    (Besteller lehnt ab)
        confirmed  → Bestätigt    (Lieferant bestätigt, ggf. Tracking)
        received   → Wareneingang (Ware ist eingetroffen → Schritt erledigt)
    """

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Bezugsquelle (aus dem Prozessschritt kopiert)
    mode: Mapped[str] = mapped_column(String(20), default="supplier", nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    webshop_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False)

    # Offerte: der Lieferant erfasst EINE Bestellsumme (netto, exkl. MWST).
    # Der Preis pro Stück (unit_price) wird daraus automatisch berechnet.
    order_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))  # = order_total / quantity (read-only)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    payment_terms_days: Mapped[Optional[int]] = mapped_column(Integer)
    desired_delivery_date: Mapped[Optional[date]] = mapped_column(Date)

    # Abwicklung
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100))

    # Vom System berechneter Einstandspreis netto/Stück
    landed_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
