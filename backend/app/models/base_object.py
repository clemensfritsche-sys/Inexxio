"""
Universal object model – every ERP entity gets a 9-digit sequential ID from this table.
Range: 100_000_001 – 999_999_999. Never reused, never deleted (soft-delete only).
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Sequence, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ObjectType(str, enum.Enum):
    item = "item"
    bom = "bom"
    work_plan = "work_plan"
    production_order = "production_order"
    purchase_order = "purchase_order"
    sales_order = "sales_order"
    serialization = "serialization"
    complaint = "complaint"
    scrapping_record = "scrapping_record"
    maintenance_order = "maintenance_order"
    audit = "audit"
    capa = "capa"
    risk = "risk"
    document = "document"
    invoice = "invoice"
    credit_note = "credit_note"
    company = "company"
    contact = "contact"
    user = "user"
    contract = "contract"
    subscription = "subscription"


object_id_seq = Sequence("object_id_seq", start=100_000_001, increment=1)


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(
        BigInteger,
        object_id_seq,
        server_default=object_id_seq.next_value(),
        primary_key=True,
    )
    object_type: Mapped[ObjectType] = mapped_column(Enum(ObjectType), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=True)
    updated_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
