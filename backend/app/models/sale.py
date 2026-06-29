from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Sale(Base, TimestampMixin):
    """Ausführung des Prozessschritts «Verkauf» – das **Spiegelbild der Beschaffung**.

    Rein kaufmännisch (outbound): der physische Versand läuft – wie beim Einkauf der
    Wareneingang – über den/die **Bewegungs**-Schritt(e) (Ziel = Kunde, mit Tracking).
    KEINE eigene Objektnummer: läuft unter dem Auftrag (``order_id``).

    Status-Ablauf (Spiegel von requested→quoted→ordered→received):
        requested → Angefragt    (Warenkorb/Anfrage angelegt)
        confirmed → Bestätigt    (Auftragsbestätigung – Beleg)
        invoiced  → Verrechnet    (Rechnung – Beleg, 10-Jahres-Archiv)
        paid      → Bezahlt       (Zahlungseingang → Schritt erledigt)
        cancelled → Storniert     (abgebrochen)
    """

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Routing: an welche Prozessschritt-Definition gebunden (mehrere möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # Kunde (UserProfile mit Rolle «customer»). Objektnummer als Standort beim Versand.
    customer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False)

    # Kaufmännisch: EIN Verkaufsbetrag (netto, exkl. MWST). Stückpreis = Summe ÷ Menge.
    order_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))   # z. B. 8.10 (CH Standard)
    currency: Mapped[str] = mapped_column(String(3), default="CHF", nullable=False)

    # ── Preis-Snapshot beim Kauf (Katalog ist mutabel, Transaktion unveränderlich) ──
    # Der Shop friert Preis/Währung/FX-Kurs/Steuerklasse zum Kaufzeitpunkt auf den Beleg
    # ein: ``order_total`` ist der Netto-Betrag in ``currency``, ``base_amount_chf`` die
    # Netto-Basis in CHF, ``fx_rate``/``fx_date`` der angewandte Tageskurs, ``tax_class``
    # die Steuerklasse des Preises. Spätere Katalog-Änderungen berühren den Beleg nie.
    base_amount_chf: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    fx_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    fx_date: Mapped[Optional[date]] = mapped_column(Date)
    tax_class: Mapped[Optional[str]] = mapped_column(String(16))

    # Belege/Abwicklung (TODO Phase 2: PDF-Erzeugung, Stripe, Gmail).
    invoice_number: Mapped[Optional[str]] = mapped_column(String(60))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    invoiced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
