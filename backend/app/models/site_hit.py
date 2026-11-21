"""**Die Website-Statistik** (``services/site_stats``) – ein Aufruf, ein Klick, eine Anfrage.

Gespeichert wird **keine IP-Adresse und nichts, was einen Menschen wiedererkennt**: der
Besuch ist eine Kennung aus Tagesschlüssel, Adresse und Browser (``visitor``), der Schlüssel
gilt einen Tag und wird danach gelöscht (``SiteSalt``) – morgen ist derselbe Mensch ein anderer
Besuch. Eine Anfrage trägt keine Kennung (sonst liesse sie sich mit dem Rest des Besuchs
verbinden), nur Einstieg und Quelle ihres Besuchs.

Technisch und ohne Datensatz – darum nicht im Log (``domain/log.EXEMPT``).
"""

from datetime import date
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, Index, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class SiteHit(Base, TimestampMixin):
    __tablename__ = "site_hits"
    __table_args__ = (Index("ix_site_hits_day_kind", "day", "kind"),
                      Index("ix_site_hits_day_visitor", "day", "visitor"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: Der Tag in Europe/Zurich.
    day: Mapped[date] = mapped_column(Date, nullable=False)
    #: view · leave · call · mail · route · form_view · form_start · form_step · lcp · cls ·
    #: inquiry · newsletter (``site_stats.KINDS``).
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Der Besuch dieses Tages (leer bei Anfrage und Newsletter).
    visitor: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    #: Die Seite (ohne Adress-Parameter).
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    lang: Mapped[str] = mapped_column(String(2), nullable=False)
    #: Einstieg in die Website (eine Ansicht von aussen) – nur dann stehen Quelle und Kampagne da.
    entry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ref_host: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    utm_source: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    #: Bei Klick, Anfrage, Newsletter: die Seite, auf der der Besuch begann.
    entry_path: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    #: mobile · tablet · desktop
    device: Mapped[str] = mapped_column(String(8), nullable=False)
    #: Lesezeit in Sekunden (leave) · Ladezeit in ms (lcp) · Verschiebung × 1000 (cls).
    value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    #: Die Nachricht einer Anfrage.
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class SiteSalt(Base, TimestampMixin):
    """Der Schlüssel eines Tages – zufällig, gelöscht, sobald der Tag vorbei ist (Takt)."""
    __tablename__ = "site_salts"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
