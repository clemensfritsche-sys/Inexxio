from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .objects import UniversalObject

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin


class ProzessSchritt(Base, TimestampMixin):
    __tablename__ = "prozess_schritte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), nullable=True, index=True
    )
    objekt_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("objects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False)

    ressourcen: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    daten_felder: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    ergebnis_optionen: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    aktion: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    onshape_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    dokument_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    item: Mapped[Optional["Item"]] = relationship("Item", back_populates="prozess_schritte")
    objekt: Mapped[Optional["UniversalObject"]] = relationship(
        "UniversalObject", foreign_keys=[objekt_id]
    )
