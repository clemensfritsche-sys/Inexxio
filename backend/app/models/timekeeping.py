"""Zeiterfassung – gespeichert wird nur, was ein Mensch eingibt (Migration 154).

* ``time_contracts`` – der Vertrag ab einem Stichtag (Wochenstunden, Arbeitstage, Ferien,
  Gesellschaft). Eintritt = erster, Austritt = 0 h. **Append-only.**
* ``time_entries`` – EINE Tabelle für Stempel, Absenzen, Buchungen und Rücknahmen. Eine
  Änderung ist ein neuer Eintrag mit ``replaces_id``. **Append-only** (DB-Trigger).
* ``holidays`` – die bestätigten Feiertage einer Gesellschaft (Stammdaten, Soft-Delete).

Stundenkonto, Ferienguthaben, Hinweise und Aufgaben sind **Ableitungen**
(``services/timekeeping``) – keine Spalte speichert eine Summe.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, \
    SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class TimeContract(Base, TimestampMixin):
    __tablename__ = "time_contracts"
    __table_args__ = (
        Index("uq_time_contracts_person_from", "person_object_id", "valid_from", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    #: Wochenstunden in Minuten – 0 = Austritt.
    weekly_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Arbeitstage als Bitmaske (Bit 0 = Mo … Bit 6 = So).
    workdays: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vacation_weeks: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    #: Die Gesellschaft (Objektnummer) – sie bestimmt Feiertage und Nachweis-Regeln.
    company_object_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)


class TimeEntry(Base, TimestampMixin):
    __tablename__ = "time_entries"
    __table_args__ = (
        Index("ix_time_entries_person_day", "person_object_id", "day"),
        # Ein Eintrag wird höchstens EINMAL ersetzt – zwei gleichzeitige Korrekturen
        # derselben Zeile können sich nicht verzweigen.
        Index("uq_time_entries_replaces", "replaces_id", unique=True,
              postgresql_where=text("replaces_id IS NOT NULL")),
        # Derselbe Wisch (Netz wackelt, zweimal gesendet) schreibt nur einmal.
        Index("uq_time_entries_key", "idem_key", unique=True,
              postgresql_where=text("idem_key IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    #: Der Tag, dem der Eintrag gehört (Stempel: Tag des Zeitpunkts in Europe/Zurich;
    #: Absenz: erster Tag; Buchung: Datum).
    day: Mapped[date] = mapped_column(Date, nullable=False)
    #: Stempel: der Zeitpunkt (UTC).
    at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    #: Absenz: der letzte Tag.
    until: Mapped[Optional[date]] = mapped_column(Date)
    art: Mapped[Optional[str]] = mapped_column(String(20))
    #: Absenz: Minuten je Tag (``NULL`` = ganzer Tag = Tagessoll); Buchung: Stundenkonto ±.
    minutes: Mapped[Optional[int]] = mapped_column(Integer)
    #: Buchung: Ferien ± in Minuten.
    vacation_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(Text)
    proof_url: Mapped[Optional[str]] = mapped_column(String(200))
    source: Mapped[Optional[str]] = mapped_column(String(10))
    replaces_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("time_entries.id", ondelete="RESTRICT"))
    idem_key: Mapped[Optional[str]] = mapped_column(String(64))
    #: Wer erfasst hat (``user_profiles.id``) – «durch Anna Roth».
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)


class Holiday(Base, TimestampMixin):
    __tablename__ = "holidays"
    __table_args__ = (
        Index("uq_holidays_company_day", "company_object_id", "day", unique=True,
              postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)
