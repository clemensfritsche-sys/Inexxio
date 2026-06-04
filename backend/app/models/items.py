import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin, utcnow


class ItemStatus(str, enum.Enum):
    ENTWURF = "ENTWURF"
    IN_FREIGABE = "IN_FREIGABE"
    FREIGEGEBEN = "FREIGEGEBEN"
    ERSETZT = "ERSETZT"
    UNGUELTIG = "UNGUELTIG"


class ItemUnit(str, enum.Enum):
    STK = "Stk"
    MM = "mm"
    G = "g"
    MM2 = "mm²"


class VatRate(str, enum.Enum):
    STANDARD = "8.1"
    REDUCED = "2.6"
    ACCOMMODATION = "3.8"
    ZERO = "0.0"


class Item(Base, TimestampMixin):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("objects.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    name_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("item_names.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(10), default="Stk", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ItemStatus.ENTWURF, nullable=False, index=True
    )
    batch_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    order_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    onshape_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    weight_g: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    dim_1_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    dim_2_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    dim_3_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    surface_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("item_surfaces.id", ondelete="SET NULL"), nullable=True
    )
    purchase_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    purchase_currency: Mapped[str] = mapped_column(String(3), default="CHF", nullable=False)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stock_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), default=Decimal("0"), nullable=False
    )
    stock_reserved: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), default=Decimal("0"), nullable=False
    )
    replaced_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True
    )
    replaces_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True
    )
    is_sales_product: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sales_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    sales_currency: Mapped[str] = mapped_column(String(3), default="CHF", nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("item_categories.id", ondelete="SET NULL"), nullable=True
    )
    vat_rate: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    shop_description_long: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seo_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hs_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    name_ref = relationship("ItemName", foreign_keys=[name_id])
    surface = relationship("ItemSurface", foreign_keys=[surface_id])
    category = relationship("ItemCategory", foreign_keys=[category_id])
    signatures: Mapped[list["ItemSignature"]] = relationship(
        "ItemSignature", back_populates="item", cascade="all, delete-orphan"
    )


class ItemSignature(Base):
    __tablename__ = "item_signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signed_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    item: Mapped["Item"] = relationship("Item", back_populates="signatures")
    signer = relationship("UserProfile", foreign_keys=[signed_by])
