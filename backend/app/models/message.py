"""►►► **Die Nachricht** – das einzige Objekt der Kommunikation (CRM Schritt 2). ◄◄◄

Keine Objektnummer (eine technische Id genügt – man druckt kein Etikett für eine Mail),
kein Status, kein Typ. Was sie ist, sagen ihre Angaben; ob sie offen ist, ist eine
**Ableitung** (``services/communication``). Nach dem Speichern wird nichts mehr geändert
– die Geschichte bleibt, wie sie war; weg kommt eine Nachricht nur per Soft-Delete.

* ``message_parties`` – An · Cc · Bcc · Betrifft, je Person eine Zeile.

Was zusammengehört, sagt der **Betreff** (``domain.topic``) – ein «Antwort auf» gibt es
nicht. Die frühere Tabelle ``message_replies`` hat kein Modell mehr; sie steht bis zum
Folge-Deploy (``docs/backlog.md``) und wird nur noch von der Übernahme gelesen
(``domain.topic_repair_sql``).
"""

from datetime import datetime
from typing import Optional

from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
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

    # ── Postfach (CRM Schritt 3, ``services/mailbox``) ─────────────────────────────
    #: Die Mail selbst bleibt in Gmail; hier steht nur, wie man sie dort wiederfindet.
    gmail_id: Mapped[Optional[str]] = mapped_column(String(64))
    thread_id: Mapped[Optional[str]] = mapped_column(String(64))
    #: Der ``Message-ID``-Kopf – weltweit eindeutig, also die Dublettensperre über alle
    #: Postfächer (dieselbe Mail an info@ **und** in Cc an einen Mitarbeiter ist EINE).
    rfc_id: Mapped[Optional[str]] = mapped_column(String(255))
    #: **Muss noch hinaus** – gesetzt beim Anlegen einer Mail an aussen, gelöscht beim
    #: Versand. Eine geplante Mail wartet hier, bis ihr Zeitpunkt da ist.
    outgoing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                           server_default="false")
    #: Anhänge: nur Name und Grösse – die Datei bleibt in Gmail.
    attachments: Mapped[Optional[list[Any]]] = mapped_column(JSONB)
    #: **Die Mail, wie sie hinausging** (``services/mail_layout``) – ein Beleg behält, was
    #: auf ihm stand. Leer = sie wird beim Versand aus Text und Absender gebaut.
    html: Mapped[Optional[str]] = mapped_column(Text)
    #: **In Gmail als gelesen markiert** – erledigt im ERP heisst gelesen im Postfach,
    #: und zwar genau einmal (``mailbox._mark_read``).
    read_marked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                              server_default="false")

    __table_args__ = (
        Index("uq_messages_rfc_id", "rfc_id", unique=True,
              postgresql_where=text("rfc_id IS NOT NULL")),
        Index("uq_messages_gmail", "channel", "gmail_id", unique=True,
              postgresql_where=text("gmail_id IS NOT NULL")),
    )


class MessageParty(Base):
    __tablename__ = "message_parties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id"), nullable=False, index=True)
    person_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    #: ``to`` · ``cc`` · ``bcc`` · ``about``.
    role: Mapped[str] = mapped_column(String(5), nullable=False)

