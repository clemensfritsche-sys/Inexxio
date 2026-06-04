from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin, utcnow


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    firebase_uid: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    department: Mapped[Optional[str]] = mapped_column(String(100))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(10), default="de")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Zurich")
    weekly_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    notification_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_inapp: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
