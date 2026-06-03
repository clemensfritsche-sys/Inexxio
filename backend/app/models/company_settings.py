"""
Single-row table for all company settings (Firmeneinstellungen).
Sensitive fields (IBAN, UID, MWST) stored encrypted via pgcrypto.
"""
from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CompanySettings(Base):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Identification
    company_name: Mapped[str] = mapped_column(String(255), default="Inexxio AG")
    legal_form: Mapped[str] = mapped_column(String(50), default="AG")
    street: Mapped[str] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="Schweiz")

    # Legal numbers (stored encrypted)
    uid_number: Mapped[str] = mapped_column(String(50), nullable=True)
    vat_number: Mapped[str] = mapped_column(String(50), nullable=True)
    commercial_register_nr: Mapped[str] = mapped_column(String(50), nullable=True)
    commercial_register_canton: Mapped[str] = mapped_column(String(50), nullable=True)
    share_capital: Mapped[float] = mapped_column(Numeric(14, 2), nullable=True)

    # Banking (stored encrypted)
    iban: Mapped[str] = mapped_column(String(34), nullable=True)
    qr_iban: Mapped[str] = mapped_column(String(34), nullable=True)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=True)
    bic_swift: Mapped[str] = mapped_column(String(20), nullable=True)

    # Contact
    email: Mapped[str] = mapped_column(String(255), default="info@inexxio.com")
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    website: Mapped[str] = mapped_column(String(255), default="https://inexxio.com")
    logo_path: Mapped[str] = mapped_column(Text, nullable=True)

    # VAT settings
    vat_method: Mapped[str] = mapped_column(String(50), default="effektiv")
    vat_period: Mapped[str] = mapped_column(String(20), default="quartal")
    default_payment_term_days: Mapped[int] = mapped_column(Integer, default=30)
    default_skonto_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=2.0)
    default_skonto_days: Mapped[int] = mapped_column(Integer, default=10)

    # EU VAT toggles (prepared, not yet active)
    oss_active: Mapped[bool] = mapped_column(Boolean, default=False)
    oss_registration_nr: Mapped[str] = mapped_column(String(50), nullable=True)
    vies_active: Mapped[bool] = mapped_column(Boolean, default=False)
