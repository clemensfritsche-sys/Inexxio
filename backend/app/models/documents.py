import enum
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    OBSOLETE = "obsolete"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("objects.id"), primary_key=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.DRAFT, nullable=False
    )
    replaces_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("documents.id"), nullable=True
    )
    applicable_from: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)


class Signature(Base):
    __tablename__ = "signatures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    context: Mapped[str] = mapped_column(String(100), nullable=False)
    signer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    signed_at_utc: Mapped[str] = mapped_column(String(50), nullable=False)
    signature_png_path: Mapped[Optional[str]] = mapped_column(String(500))


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_at_utc: Mapped[str] = mapped_column(String(50), nullable=False)
