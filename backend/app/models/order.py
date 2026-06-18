from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Order(Base, TimestampMixin):
    """Auftrag — interner Bedarf, der einen Artikel-Prozess auslöst.

    Beispiel: «5× Artikel 1003». Wird der Auftrag freigegeben (status=released)
    und besitzt der Artikel einen ``purchase``-Prozessschritt, instanziiert das
    System die zugehörige Bestellung (Purchase Order).

    Statuswerte (`status`): draft → Entwurf | released → Freigegeben | inactive → Inaktiv
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))

    # Bedarf: welcher Artikel in welcher Menge (löst den Prozess aus)
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    desired_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Prozess-Eckdaten für die Durchlaufzeit (Freigabe → Abschluss).
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
