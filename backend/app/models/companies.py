import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin


class CompanyType(str, enum.Enum):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    BOTH = "both"


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("objects.id"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    uid: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    vat_id: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    vat_validated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    country_code: Mapped[str] = mapped_column(String(3), default="CH", nullable=False)
    iban: Mapped[Optional[str]] = mapped_column(String(34), nullable=True)
    payment_term_days: Mapped[int] = mapped_column(BigInteger, default=30, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("objects.id"), primary_key=True
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
