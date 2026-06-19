from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import utcnow


class Event(Base):
    """Domain-Event-Strom (transaktionaler Outbox) – append-only.

    Hält fachliche Ereignisse fest (z. B. ``order.released``, ``order.completed``,
    ``inspection.failed``), die im selben Transaktions-Commit wie die Zustands-
    änderung geschrieben werden – die Events sind also konsistent mit dem Zustand.

    Zweck: native KI-/Automatisierungs-Anbindung und Analytik. Externe Agenten
    konsumieren den Strom vorwärts über ``GET /api/v1/events?after_id=…`` (id ist
    monoton steigend → einfacher, lückenloser Cursor). Kein Soft-Delete/Update:
    Events sind unveränderlich.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Betroffenes Objekt (9-stellige Objektnummer), sofern eines existiert.
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    object_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
