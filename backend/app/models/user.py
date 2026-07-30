from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    # Wie sich die Person zuletzt angemeldet hat (aus dem Firebase-ID-Token:
    # google.com | password | emailLink | custom = Passkey). Rein deskriptiv – die
    # Support-Frage «wie kommt der überhaupt rein?» war sonst nicht beantwortbar.
    last_sign_in_provider: Mapped[Optional[str]] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)

    # Personal identity
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(50))

    # Contact address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    state_region: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="CH")

    # Unified shipping address
    ship_name: Mapped[Optional[str]] = mapped_column(String(255))
    ship_company: Mapped[Optional[str]] = mapped_column(String(255))
    ship_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    ship_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    ship_city: Mapped[Optional[str]] = mapped_column(String(100))
    ship_postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    ship_state_region: Mapped[Optional[str]] = mapped_column(String(100))
    ship_country: Mapped[Optional[str]] = mapped_column(String(100))

    # Invoice / billing address
    invoice_company: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_first_name: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_last_name: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_city: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    invoice_country: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_email: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_same_as_shipping: Mapped[bool] = mapped_column(Boolean, default=False)

    # Personal extras
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Business / company info (for B2B users)
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    uid_number: Mapped[Optional[str]] = mapped_column(String(20))
    vat_number: Mapped[Optional[str]] = mapped_column(String(20))
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    trade_register_nr: Mapped[Optional[str]] = mapped_column(String(50))
    trade_register_canton: Mapped[Optional[str]] = mapped_column(String(50))
    company_website: Mapped[Optional[str]] = mapped_column(String(255))
    company_billing_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Supplier bank details
    bank_account_holder: Mapped[Optional[str]] = mapped_column(String(255))
    bank_iban: Mapped[Optional[str]] = mapped_column(String(50))
    bank_bic: Mapped[Optional[str]] = mapped_column(String(20))
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Employee info
    department: Mapped[Optional[str]] = mapped_column(String(100))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))
    employment_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weekly_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Preferences & notifications
    language: Mapped[str] = mapped_column(String(10), default="de")
    notification_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_inapp: Mapped[bool] = mapped_column(Boolean, default=True)
    newsletter_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stripe: gemappter Stripe-Customer (für Checkout, Abos, Customer Portal).
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    # Auth / compliance
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_version: Mapped[Optional[str]] = mapped_column(String(20))

    @property
    def display_name(self) -> str:
        """Anzeigename – EINE Regel für alle Anzeigen und ALLE Rollen (Lieferant/Kunde/Prüfer):
        **«Vorname Nachname» → Firma → E-Mail** (Notiz #291). Es wird immer der **Name der
        Person** im Datensatz gezeigt, nicht der Firmenname – der ist nur Rückfall, wenn keine
        Person hinterlegt ist. (Der Versand-Empfängername bleibt firmen-first – eigene Regel in
        ``stripe_provider._full_name`` – denn das Paket geht an die Firma.)"""
        name = " ".join(p for p in [self.first_name, self.last_name] if p).strip()
        return name or self.company_name or self.email
