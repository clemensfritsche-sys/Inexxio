from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class RecurringOrder(Base, TimestampMixin):
    """Wiederkehrender Vorgang – ein **Generator** für Aufträge (kein Parallel-Modell).

    Deckt zwei Welten mit DERSELBEN Logik ab:
    - **Compliance/Termine** (ISO 9001, Kalibrierung, Audits …): muss *vor* dem
      Ablauf erledigt sein. Anker ist ``valid_until``; der Erneuerungs-Auftrag wird
      **``lead_time_days`` früher** automatisch erzeugt (nie eine Lücke). Bei
      Abschluss rollt ``valid_until`` um ``validity_days`` vor.
    - **Abos/Subscriptions** (wiederkehrender Verkauf): fester Intervall
      (``interval_days``) ab ``next_due_at``.

    Erzeugt einen ganz normalen ``Order`` (Artikel/Instanz + Prozess) – dieser läuft
    durch die **gleiche** Prozess-Engine. Eigenständiges Objekt mit Objektnummer
    (Feed-Typ «Wiederkehrend»).
    """

    __tablename__ = "recurring_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="released", nullable=False)  # draft|released|inactive

    # Was wird erzeugt: Prozess + Subjekt (gespiegelt zum Auftrag).
    process_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    subject_instance_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Takt: entweder fester Intervall (Abo) ODER ablauf-verankert (Compliance).
    interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validity_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    next_due_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)   # nächster Soll-Termin
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)   # aktuelles Ablaufdatum (Compliance)

    last_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)   # zuletzt erzeugter Auftrag
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
