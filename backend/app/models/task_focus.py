"""►►► **Wer woran ist** (Projektakte «Aufgaben» `docs/konzept/aufgaben.md` §6, §8). ◄◄◄

**Eine Zeile je Person**, die je etwas zugeteilt bekam. ``task_key`` leer = frei; ``since`` =
seit wann so (daraus «wer am längsten frei ist»). Eine Aufgabe hat höchstens eine Person
(``task_key`` eindeutig, wo nicht leer) – eine Doppelvergabe ist unmöglich, nicht verboten.
``handed_key`` = die zuletzt abgegebene Aufgabe; sie kommt erst nach einer anderen wieder.

Die Aufgabe selbst ist nicht gespeichert – sie ist eine Ableitung (``services/tasks.collect``).
Geschrieben nur von ``services/tasks``; das Log schreibt die Datenbank selbst.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin, utcnow


class TaskFocus(Base, TimestampMixin):
    __tablename__ = "task_focus"
    __table_args__ = (Index("uq_task_focus_task", "task_key", unique=True,
                            postgresql_where=text("task_key IS NOT NULL")),)

    person_object_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                            nullable=False)
    handed_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
