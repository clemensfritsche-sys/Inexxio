import enum
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, Sequence, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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

    # ── Unified Objekt+Prozess fields (object_type='objekt') ──────────────────
    stamm_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("objects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    obj_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="ENTWURF")
    menge: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    einheit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    lagerort: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notiz: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schritt_protokoll: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    parent_instanz_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("objects.id", ondelete="SET NULL"), nullable=True
    )
    parent_schritt_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
