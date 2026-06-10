from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import utcnow


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
