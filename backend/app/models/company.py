import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CompanyType(str, enum.Enum):
    customer = "customer"
    supplier = "supplier"
    both = "both"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_type: Mapped[CompanyType] = mapped_column(Enum(CompanyType), nullable=False, index=True)
    uid: Mapped[str] = mapped_column(String(50), nullable=True)
    vat_id: Mapped[str] = mapped_column(String(50), nullable=True)
    vat_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    address: Mapped[dict] = mapped_column(JSONB, nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="CH", nullable=False)
    iban: Mapped[str] = mapped_column(String(34), nullable=True)
    payment_term_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
