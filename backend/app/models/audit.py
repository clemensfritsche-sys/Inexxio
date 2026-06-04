from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin, utcnow


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)

    # Personal identity
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    phone_mobile: Mapped[Optional[str]] = mapped_column(String(50))

    # Contact address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    state_canton: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="CH")

    # Shipping B2C
    ship_b2c_first_name: Mapped[Optional[str]] = mapped_column(String(100))
    ship_b2c_last_name: Mapped[Optional[str]] = mapped_column(String(100))
    ship_b2c_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    ship_b2c_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    ship_b2c_city: Mapped[Optional[str]] = mapped_column(String(100))
    ship_b2c_postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    ship_b2c_country: Mapped[Optional[str]] = mapped_column(String(100))

    # Shipping B2B
    ship_b2b_company: Mapped[Optional[str]] = mapped_column(String(255))
    ship_b2b_contact: Mapped[Optional[str]] = mapped_column(String(255))
    ship_b2b_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    ship_b2b_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    ship_b2b_city: Mapped[Optional[str]] = mapped_column(String(100))
    ship_b2b_postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    ship_b2b_country: Mapped[Optional[str]] = mapped_column(String(100))

    # Invoice / billing address
    invoice_company: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_first_name: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_last_name: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_city: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    invoice_country: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_vat_id: Mapped[Optional[str]] = mapped_column(String(50))
    invoice_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Personal extras
    salutation: Mapped[Optional[str]] = mapped_column(String(20))  # Herr / Frau / Divers
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Business / company info (for B2B users)
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    company_legal_form: Mapped[Optional[str]] = mapped_column(String(50))
    uid_number: Mapped[Optional[str]] = mapped_column(String(20))
    vat_number: Mapped[Optional[str]] = mapped_column(String(20))
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    trade_register_nr: Mapped[Optional[str]] = mapped_column(String(50))
    trade_register_canton: Mapped[Optional[str]] = mapped_column(String(50))
    company_website: Mapped[Optional[str]] = mapped_column(String(255))
    company_billing_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Online shop / CRM
    is_business: Mapped[bool] = mapped_column(Boolean, default=False)
    customer_group: Mapped[Optional[str]] = mapped_column(String(50))
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    accepts_marketing: Mapped[bool] = mapped_column(Boolean, default=False)

    # Payment
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Employee info
    department: Mapped[Optional[str]] = mapped_column(String(100))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))
    employment_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weekly_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Preferences & notifications
    language: Mapped[str] = mapped_column(String(10), default="de")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Zurich")
    notification_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_inapp: Mapped[bool] = mapped_column(Boolean, default=True)
    newsletter_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)

    # Auth / compliance
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_version: Mapped[Optional[str]] = mapped_column(String(20))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[Optional[str]] = mapped_column(String(100))
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    changed_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
