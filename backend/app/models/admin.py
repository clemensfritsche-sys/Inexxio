from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class CompanySettings(Base):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    company_name: Mapped[str] = mapped_column(String(255), default="Inexxio AG")
    legal_form: Mapped[str] = mapped_column(String(50), default="AG")
    street: Mapped[Optional[str]] = mapped_column(String(255))
    street_nr: Mapped[Optional[str]] = mapped_column(String(20))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Schweiz")
    uid_number: Mapped[Optional[str]] = mapped_column(String(30))
    vat_number: Mapped[Optional[str]] = mapped_column(String(30))
    trade_register_nr: Mapped[Optional[str]] = mapped_column(String(50))
    trade_register_canton: Mapped[Optional[str]] = mapped_column(String(50))
    share_capital: Mapped[Optional[str]] = mapped_column(String(100))
    iban_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    qr_iban_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    bank: Mapped[Optional[str]] = mapped_column(String(255))
    bic_swift: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255), default="info@inexxio.com")
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    website: Mapped[str] = mapped_column(String(255), default="https://inexxio.com")
    vat_method: Mapped[str] = mapped_column(String(50), default="effektiv")
    vat_period: Mapped[str] = mapped_column(String(20), default="quartal")
    default_payment_days: Mapped[int] = mapped_column(Integer, default=30)
    default_skonto_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    default_skonto_days: Mapped[Optional[int]] = mapped_column(Integer)
    oss_active: Mapped[bool] = mapped_column(Boolean, default=False)
    oss_reg_number: Mapped[Optional[str]] = mapped_column(String(50))
    vies_active: Mapped[bool] = mapped_column(Boolean, default=False)
    logo_path: Mapped[Optional[str]] = mapped_column(String(500))

    # API Keys / Integrations
    stripe_publishable_key: Mapped[Optional[str]] = mapped_column(String(255))
    plausible_domain: Mapped[Optional[str]] = mapped_column(String(255))
    hcaptcha_site_key: Mapped[Optional[str]] = mapped_column(String(255))
