from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
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
    # Verkaufsmenge als Dezimalzahl (NUMERIC(14,3)) – ganze Stück ODER Bruchmenge (kg/m²/…).
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    # Routing: an welche Prozessschritt-Definition gebunden (mehrere möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # ── Verkauf vs. Gutschrift (Spiegelbild) ────────────────────────────────────────
    # 'sale' = normaler Verkauf (Geld herein, Bestand raus). 'credit' = **Gutschrift**: das
    # Spiegelbild in einer Retoure (Unter-Auftrag ``reason='return'``) – Umsatz-/MWST-Umkehr,
    # Geld zurück (Stripe-Refund gegen den Original-PaymentIntent bzw. manuell). ``order_total``
    # bleibt der **Betrag (Magnitude, netto)**; die Richtung sagt ``kind`` (kein Vorzeichen im
    # Betrag → der ``_money_non_negative``-Validator bleibt gültig, Anzeige „Gutschrift: CHF X").
    kind: Mapped[str] = mapped_column(String(8), default="sale", server_default="sale", nullable=False)
    original_sale_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    credit_note_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)  # unveränderlich, 10-J-Archiv
    stripe_refund_id: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Kunde (UserProfile mit Rolle «customer»). Objektnummer als Standort beim Versand.
    customer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # **Fakturierende Gesellschaft** (Seller of Record, ADR 006) – die Objektnummer der
    # Gesellschaft, die diesen Verkauf ausstellt. Abgeleitet aus der Rechnungsadresse des
    # Kunden (``sites.company_for_country``) und – wie Preis/Währung/Steuer – bei der
    # Zahlung **eingefroren** (Snapshot), damit der Beleg unveränderlich die richtige
    # Rechtsperson trägt. NULL bei Alt-/Nicht-Verkaufsbelegen → Fallback Betreiber.
    seller_company_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="requested", nullable=False)

    # Herkunft (rein informativ, wie ``PurchaseOrder.mode`` bei der Beschaffung): 'shop' –
    # Kunde hat selbst über die Kasse bezahlt (Stripe) | 'direct' – Personal hat den Verkauf
    # im ERP erfasst (Telefon/Messe/B2B-Rechnung). KEIN Modus-Flag am Prozessschritt (der ist
    # für beide Wege identisch) – nur eine Herkunfts-Notiz je Beleg.
    mode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Zahlungsart des manuellen Zahlungseingangs («Zahlung erfassen»): 'invoice' (Rechnung/
    # QR-Rechnung, der übliche B2B-Weg ohne Kartenterminal) | 'cash' | 'twint' | 'other'.
    # 'stripe' setzt das System selbst (Shop-Zahlung); 'terminal' (Stripe Terminal / Karten-
    # leser vor Ort) ist als Wert bewusst vorgesehen, aber noch nicht auswählbar (Phase 2+).
    payment_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    # Kaufmännisch: EIN Verkaufsbetrag (netto, exkl. MWST). Stückpreis = Summe ÷ Menge.
    order_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))   # z. B. 8.10 (CH Standard)
    currency: Mapped[str] = mapped_column(String(3), default="CHF", nullable=False)

    # ── Preis-Snapshot beim Kauf (Katalog ist mutabel, Transaktion unveränderlich) ──
    # Der Shop friert Preis/Währung/Steuerklasse zum Kaufzeitpunkt auf den Beleg ein:
    # ``order_total`` ist der Netto-Betrag in ``currency``, ``base_amount_chf`` die
    # Netto-Basis in CHF, ``fx_date`` das Kursdatum, ``tax_class`` die Steuerklasse des
    # Preises. Spätere Katalog-Änderungen berühren den Beleg nie.
    base_amount_chf: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    fx_date: Mapped[Optional[date]] = mapped_column(Date)
    tax_class: Mapped[Optional[str]] = mapped_column(String(16))

    # Stripe-Beleg: PaymentIntent + voller Snapshot von Stripe. **Settlement = die Währung
    # der Stripe-Session**: mit Adaptive Pricing (keine feste Session-Währung) ist das die
    # LOKALWÄHRUNG des Kunden, nicht zwingend CHF – alle Folge-Rechnungen (Teil-Erstattung
    # ``frac`` × ``line_gross``) rechnen konsistent in DIESER gespeicherten Währung.
    # {"settlement":{"currency","total","tax"},"presentment":{"currency","total"},
    #  "payment_intent","mode","tax_rate"} – Stripe ist die Quelle der Wahrheit.
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    stripe_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Belege/Abwicklung (TODO Phase 2: PDF-Erzeugung, Stripe, Gmail).
    invoice_number: Mapped[Optional[str]] = mapped_column(String(60))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    invoiced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
