"""►►► **Ein verbundenes Postfach** (CRM Schritt 3, ``services/mailbox``). ◄◄◄

Je Kanal höchstens ein aktives: ``info`` (das Postfach des Unternehmens – seine Adresse
ist die Kontakt-E-Mail des Betreibers) oder ``u<Objektnummer>`` (das persönliche eines
Mitarbeiters). Gmail ist das Postfach; hier steht nur der Schlüssel dorthin und der Stand
des Abgleichs.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Mailbox(Base, TimestampMixin):
    __tablename__ = "mailboxes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Die Adresse, die Google beim Verbinden genannt hat – klein geschrieben.
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Wer verbunden hat (Objektnummer). Beim persönlichen Postfach der Besitzer; beim
    #: Unternehmen der Absender einer Mail, die direkt in Gmail geschrieben wurde.
    owner_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: Der Refresh-Token, **verschlüsselt** (``services/mailbox._seal``).
    token: Mapped[str] = mapped_column(Text, nullable=False)
    #: Bis wohin abgeglichen ist (Gmail ``historyId``).
    history_id: Mapped[Optional[str]] = mapped_column(String(32))
    #: Warum der Abgleich nicht geht (z. B. «Verbindung abgelaufen») – leer = in Ordnung.
    problem: Mapped[Optional[str]] = mapped_column(Text)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("uq_mailboxes_channel", "channel", unique=True,
              postgresql_where=text("is_active")),
    )
