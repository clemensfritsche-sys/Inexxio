import enum
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin


class AuftragStatus(str, enum.Enum):
    OFFEN = "OFFEN"
    IN_ARBEIT = "IN_ARBEIT"
    ABGESCHLOSSEN = "ABGESCHLOSSEN"
    ABGEBROCHEN = "ABGEBROCHEN"


class IntervallTyp(str, enum.Enum):
    ZEITBASIERT = "zeitbasiert"
    NUTZUNGSBASIERT = "nutzungsbasiert"
    EREIGNISBASIERT = "ereignisbasiert"


class Auftrag(Base, TimestampMixin):
    __tablename__ = "auftraege"

    id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("objects.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    menge: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("1"))
    datum_faellig: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=AuftragStatus.OFFEN, nullable=False, index=True
    )
    notiz: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wiederkehrend: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    intervall_typ: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    intervall_wert: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    naechste_faelligkeit: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    item: Mapped["Item"] = relationship("Item", back_populates="auftraege")
    objekte: Mapped[list["Objekt"]] = relationship("Objekt", back_populates="auftrag")
