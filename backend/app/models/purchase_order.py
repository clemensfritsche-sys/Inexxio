from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class PurchaseOrder(Base, TimestampMixin):
    """Ausführung des Prozessschritts «Beschaffung» – läuft unter dem Auftrag.

    KEINE eigene Objektnummer: die Bestellung ist kein eigenständiges Objekt,
    sondern der Ausführungsstand eines Auftrags-Prozessschritts. Referenziert
    wird sie über die Auftragsnummer (``order_id``).

    Status-Ablauf:
        requested  → Angefragt    (angelegt, wartet auf Offerte des Lieferanten)
        quoted     → Offeriert    (Stückpreis/Transport/Lieferzeit erfasst)
        approved   → Freigegeben  (wir akzeptieren die Offerte)
        rejected   → Abgelehnt    (wir lehnen ab)
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

    # Offerte
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    transport_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    transport_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    other_costs: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    payment_terms_days: Mapped[Optional[int]] = mapped_column(Integer)
    desired_delivery_date: Mapped[Optional[date]] = mapped_column(Date)

    # Abwicklung
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100))
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500))

    # Vom System berechneter Einstandspreis netto/Stück
    landed_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
