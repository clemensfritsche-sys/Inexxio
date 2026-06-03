import enum
from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SerialMode(str, enum.Enum):
    unit = "unit"
    batch = "batch"


class PurchaseType(str, enum.Enum):
    one_time = "one_time"
    subscription = "subscription"
    both = "both"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    size: Mapped[str] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="Stk", nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    is_equipment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    serial_mode: Mapped[SerialMode] = mapped_column(Enum(SerialMode), default=SerialMode.unit, nullable=False)

    # Replacement chain (immutability rule)
    replaced_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=True)
    replaces_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=True)

    # Shop fields
    is_sales_product: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shop_description: Mapped[str] = mapped_column(Text, nullable=True)
    purchase_type: Mapped[PurchaseType] = mapped_column(Enum(PurchaseType), default=PurchaseType.one_time, nullable=True)
    list_price_chf: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    hs_code: Mapped[str] = mapped_column(String(20), nullable=True)

    # Stock
    min_stock: Mapped[float] = mapped_column(Numeric(12, 3), nullable=True)
    reorder_point: Mapped[float] = mapped_column(Numeric(12, 3), nullable=True)
    max_stock: Mapped[float] = mapped_column(Numeric(12, 3), nullable=True)
    preferred_supplier_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=True)

    # Approval
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=True)
    approved_at = mapped_column(nullable=True)
