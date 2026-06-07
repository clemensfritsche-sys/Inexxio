import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import utcnow


class ObjektStatus(str, enum.Enum):
    VERFUEGBAR = "VERFUEGBAR"
    VERBAUT = "VERBAUT"
    GESPERRT = "GESPERRT"
    AUSGEMUSTERT = "AUSGEMUSTERT"


class ObjektTyp(str, enum.Enum):
    SERIAL = "serial"
    BATCH = "batch"


class Objekt(Base):
    __tablename__ = "objekte"

    id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("objects.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    auftrag_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("auftraege.id", ondelete="SET NULL"), nullable=True
    )
    typ: Mapped[str] = mapped_column(String(10), nullable=False)
    batch_menge: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    batch_verbleibend: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ObjektStatus.VERFUEGBAR, nullable=False, index=True
    )
    lagerort: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    gueltig_bis: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    schritt_protokoll: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    item: Mapped["Item"] = relationship("Item", back_populates="objekte")
    auftrag: Mapped[Optional["Auftrag"]] = relationship("Auftrag", back_populates="objekte")
