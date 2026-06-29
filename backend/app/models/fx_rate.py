from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import utcnow


class FxRate(Base):
    """Unveränderliche Tageshistorie der Wechselkurse (1 CHF-Basis).

    Je (Tag, Währung) **ein** Eintrag (UNIQUE). Der Kurs wird einmal pro Tag von
    einer kostenlosen Quelle geholt und gespeichert; danach ist er für diesen Tag
    konstant (``services/fx.py``). Keine Objektnummer (rein technische Referenz)."""

    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("day", "currency", name="uq_fx_rates_day_currency"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_to_chf: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(40))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
