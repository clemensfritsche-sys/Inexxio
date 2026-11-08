from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Wann eine Zeile entstand und zuletzt geändert wurde – an jeder Tabelle."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class SoftDeleteMixin:
    """**Soft-Delete** – nur an Tabellen, deren Zeilen wirklich ausgeblendet werden
    (``is_active = false``). Wo nie gelöscht wird (append-only, Ableitungen, Belege), gibt es die
    Spalte nicht: eine Spalte, die immer ``true`` ist, wäre eine Prüfung, die nichts prüft."""
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
