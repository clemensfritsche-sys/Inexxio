"""►►► **Die Nachricht** – das einzige Objekt der Kommunikation (CRM Schritt 2). ◄◄◄

Keine Objektnummer (eine technische Id genügt – man druckt kein Etikett für eine Mail),
kein Status, kein Typ. Was sie ist, sagen ihre Angaben; ob sie offen ist, ist eine
**Ableitung** (``services/communication``). Nach dem Speichern wird nichts mehr geändert
– die Geschichte bleibt, wie sie war; weg kommt eine Nachricht nur per Soft-Delete.

* ``message_parties`` – An · Cc · Bcc · Betrifft, je Person eine Zeile.
* ``message_replies`` – «Antwort auf» als **Liste**: eine Antwort darf mehrere offene
  Nachrichten zugleich beantworten, und sie wird angehängt, nie in die alte geschrieben.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin, utcnow


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: Wer schreibt (Objektnummer der Person). Bei einer E-Mail von uns der Mitarbeiter,
    #: der sie über den Kanal schickt.
    sender_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    #: Schlüssel im Katalog (``domain/communication.CHANNELS``).
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    #: Der Zeitpunkt der Nachricht – darf in der Zukunft liegen (Erinnerung, später senden).
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                         default=utcnow, index=True)
    #: Wer sie erfasst hat (``user_profiles.id``) – nicht zwingend der Absender.
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)


class MessageParty(Base):
    __tablename__ = "message_parties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id"), nullable=False, index=True)
    person_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    #: ``to`` · ``cc`` · ``bcc`` · ``about``.
    role: Mapped[str] = mapped_column(String(5), nullable=False)


class MessageReply(Base):
    __tablename__ = "message_replies"

    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id"), primary_key=True)
    reply_to_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id"), primary_key=True, index=True)
