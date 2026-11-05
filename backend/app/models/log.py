"""►►► **Das Log – die eine, unveränderliche Wahrheit darüber, was geschehen ist.** ◄◄◄

Eine Tabelle für alles (``docs/konzept/lernende-firma.md`` §1): jede Änderung an jeder
Tabelle schreibt die **Datenbank selbst** hinein (Trigger ``log_row``, ``domain/log``), jedes
fachliche Ereignis die eine Funktion ``log_event`` – beide lesen den Handelnden aus der
Transaktion und scheitern ohne ihn. ``UPDATE`` und ``DELETE`` weist ein Trigger ab; einzige
Ausnahme ist die Schwärzung (``services/log.redact``), die sich selbst einträgt.

Die Ausdrucks-Indizes für den Prozess (``payload->>'unit'`` …) stehen nur in der Migration:
ein Modell kennt keine Ausdrücke, und der Schema-Wächter vergleicht Spalten.
"""

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Log(Base):
    __tablename__ = "log"
    __table_args__ = (
        Index("ix_log_object_at", "object_id", "at"),        # der Verlauf am Ding
        Index("ix_log_request", "request_id"),               # alles einer Handlung
        Index("ix_log_actor_at", "actor_id", "at"),          # was hat jemand getan
        Index("ix_log_event_at", "event", "at"),             # Ereignisse einer Art
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: ``now()`` der Datenbank – nie vom Aufrufer.
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                         nullable=False)
    #: ``person`` · ``ai`` (im Namen von ``actor_id``) · ``system`` · ``external``.
    actor_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    #: Objektnummer der handelnden Person (bei ``ai``: in wessen Namen).
    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    #: ``ui`` · ``capture`` · ``webhook`` · ``job`` · ``start`` · ``migration`` · ``link`` ·
    #: ``login`` · ``mcp`` · ``test`` (``domain/log.SOURCES``).
    source: Mapped[str] = mapped_column(String(12), nullable=False)
    request_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: Die Objektnummer des Dings, an dem es geschah (``domain/log.OBJECT``).
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    table_name: Mapped[Optional[str]] = mapped_column(String(64))
    row_key: Mapped[Optional[str]] = mapped_column(String(64))
    #: ``insert`` · ``update`` · ``delete`` (auch weich: ``is_active`` → false) · ``event``.
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    event: Mapped[Optional[str]] = mapped_column(String(64))
    #: Nur Geändertes: ``{"feld": [alt, neu]}``; bei ``insert``/``delete`` die Werte selbst.
    changes: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)


class LogSeal(Base):
    """Die Versiegelung: je abgeschlossenem Tag eine Prüfsumme über seine Einträge und die
    des Vortags – eine nachträgliche Änderung bricht die Kette (``services/log.verify``)."""

    __tablename__ = "log_seal"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    first_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    last_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    entries: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                server_default=func.now(), nullable=False)
