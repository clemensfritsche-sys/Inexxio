"""
Append-only audit log – every field change is recorded here.
Never update or delete rows. Used for compliance and traceability.
"""
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=True)
    changed_at_utc: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class Signature(Base):
    __tablename__ = "signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    context: Mapped[str] = mapped_column(String(100), nullable=False)
    signer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=False)
    signed_at_utc: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    signature_png_path: Mapped[str] = mapped_column(Text, nullable=False)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=True)
    uploaded_at_utc: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    link: Mapped[str] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at_utc: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
