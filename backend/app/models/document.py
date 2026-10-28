"""►►► **Das Dokument – jede Datei, die ein Mensch freigegeben hat.** ◄◄◄

Ein Dokument ist **Datei + Art + Name + Referenz(en)** (``docs/dokumente.md``). Es
entsteht erst mit der Freigabe (``services/documents.file``) – vorher lebt der Entwurf im
Browser, ohne Zeile und ohne Nummer, wie ein neuer Artikel oder Auftrag. Danach sind Datei,
Art und Name fest. Was sich noch ändert, sind die Referenzen und die Unterschriften.

Der Zustand ist **abgeleitet** (``services/documents.status_of``): gelöscht · Unterschrift
abgelehnt · Unterschrift angefragt · freigegeben. Keine Spalte dafür.

Die Bytes liegen im **Korb** (``attachments``, ``services/attachments``) – dieselbe Ablage,
die heute schon jedes Bild trägt. ``file_id`` zeigt darauf; nach dem Löschen ist sie leer.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    #: Ein Wort, frei: «Lieferantenrechnung». Steht vorne im Titel «Art · Name».
    art: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Was es von anderen derselben Art unterscheidet: «Hydro AG RE-26-4471».
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Woher es kam (``domain/documents.SOURCES``) – nur Auskunft, keine Logik daran.
    source: Mapped[str] = mapped_column(String(12), nullable=False)
    #: Die Datei im Korb (``attachments.id``); leer, sobald das Dokument gelöscht ist.
    file_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Prüfsumme der Datei – dieselbe Datei zweimal ist dasselbe Dokument
    #: (partieller Unique-Index, solange nicht gelöscht).
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    #: Was gelesen wurde: der ganze Text und Stichworte auf Deutsch und Englisch (Suche).
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Was die KI abgelesen hat: Bezeichnung → Wert («Rechnungsnummer» → «RE-26-4471»). Ein
    #: Modul füllt daraus seine Felder vor; ob es passt, entscheidet der Code, nie die KI.
    facts: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    #: Wer freigegeben hat (``user_profiles.id``).
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    #: Gelöscht: der Datensatz bleibt (Art, Name, wer, wann, Grund), Datei und Text sind weg.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    delete_reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)


class DocumentRef(Base, TimestampMixin):
    """►►► **Die Referenz – die EINE Verbindung zwischen Dokument und Datensatz.** ◄◄◄

    ``object_id`` ist der Datensatz, an dem das Dokument erscheint. ``part`` nennt einen Teil
    ohne eigene Seite (``step:<id>`` ein Modul im Auftrag, ``time:<id>`` eine Absenz,
    ``unit:<Nummer>`` ein Stück). ``field`` ist gesetzt, wenn die Referenz ein **Pflichtfeld**
    ist (``voucher.original``, ``company.agb`` …): dann ändert sie nur ihr Datensatz, und
    leer wird sie nie. Entfernt wird mit ``is_active = false``."""

    __tablename__ = "document_refs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    part: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    field: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class DocumentSignature(Base, TimestampMixin):
    """Eine verlangte Unterschrift – nur anfügen. Unterschrieben oder abgelehnt ist endgültig;
    festgehalten werden Name, Zeitpunkt, die Prüfsumme des Textes und das Bild des Zugs."""

    __tablename__ = "document_signatures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    person_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    image: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class DocumentLink(Base, TimestampMixin):
    """Ein Link nach aussen – je Empfänger einer, **ohne Ablauf**. Ist das Dokument gelöscht,
    führt er auf denselben Hinweis wie jede überholte Belegseite."""

    __tablename__ = "document_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    person_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
