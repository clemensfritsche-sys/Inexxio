import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin, utcnow


class SerialMode(str, enum.Enum):
    UNIT = "unit"
    BATCH = "batch"


class PurchaseType(str, enum.Enum):
    ONE_TIME = "one_time"
    SUBSCRIPTION = "subscription"
    BOTH = "both"


class Item(Base, TimestampMixin):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("objects.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), default="Stk", nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    is_equipment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    serial_mode: Mapped[str] = mapped_column(
        String(20), default=SerialMode.UNIT, nullable=False
    )
    replaced_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True
    )
    replaces_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True
    )
    is_sales_product: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shop_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    purchase_type: Mapped[str] = mapped_column(
        String(20), default=PurchaseType.ONE_TIME, nullable=False
    )
    list_price_chf: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    hs_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    min_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 3), nullable=True)
    reorder_point: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 3), nullable=True)
    max_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 3), nullable=True)
    preferred_supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), default=Decimal("0"), nullable=False
    )
