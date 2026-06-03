from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin


class BOM(Base, TimestampMixin):
    __tablename__ = "boms"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("objects.id"), primary_key=True
    )
    parent_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lines: Mapped[list["BOMLine"]] = relationship(
        "BOMLine", back_populates="bom", cascade="all, delete-orphan"
    )


class BOMLine(Base):
    __tablename__ = "bom_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boms.id"), nullable=False, index=True
    )
    component_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="Stk", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    bom: Mapped["BOM"] = relationship("BOM", back_populates="lines")
