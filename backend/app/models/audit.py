from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import utcnow


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
