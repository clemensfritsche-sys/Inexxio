import enum
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin, utcnow


class ObjectType(str, enum.Enum):
    ITEM = "item"
    AUFTRAG = "auftrag"
    OBJEKT = "objekt"
    COMPANY = "company"
    CONTACT = "contact"
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    USER = "user"
    # Legacy (DB data preserved, no new entries)
    BOM = "bom"
    WORK_PLAN = "work_plan"
    PRODUCTION_ORDER = "production_order"
    PURCHASE_ORDER = "purchase_order"
    SALES_ORDER = "sales_order"
    SERIALIZATION = "serialization"
    COMPLAINT = "complaint"
    MAINTENANCE_ORDER = "maintenance_order"
    AUDIT = "audit"
    CAPA = "capa"
    RISK = "risk"
    DOCUMENT = "document"


object_id_seq = Sequence("object_id_seq", start=100000001, increment=1)


class UniversalObject(Base, TimestampMixin):
    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(
        BigInteger,
        object_id_seq,
        server_default=object_id_seq.next_value(),
        primary_key=True,
    )
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
