from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Document(Base, TimestampMixin):
    """Ausführung des Prozessschritts «Dokument» – das **erzeugte, nummerierte Dokument**.

    Anders als die kaufmännischen Fachzeilen (PurchaseOrder/Sale/Movement, die OHNE eigene
    Nummer unter dem Auftrag laufen) IST das Dokument der Liefergegenstand des Auftrags und
    trägt deshalb – wie eine Instanz – eine **eigene 9-stellige Objektnummer** (ISO-9001-
    Nachvollziehbarkeit, klickbar/scanbar/verlinkbar).

    Der Inhalt (``content``) ist ein **eingefrorener Snapshot** der Schritt-Vorlage
    (``article_process_steps.document_content``), festgehalten bei der Auftragsfreigabe.
    Ab Erzeugung unveränderlich: eine Änderung erzeugt eine neue Version (``replaced_by_id``),
    das Original bleibt erhalten (rechtliche/QM-Aufbewahrung).

    ``content``-Struktur (bewusst schlank, „Word"-artige Textdokumente):
        {"title": str, "subtitle": str|None, "document_date": str|None,
         "sections": [{"heading": str, "body": str}]}
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Eigene Objektnummer – das Dokument ist ein eigenständiger, nachvollziehbarer ERP-Datensatz.
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)

    # Herkunft: unter welchem Auftrag entstanden, aus welcher Schritt-Definition, welche Vorlage.
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # Eingefrorener Inhalt (Snapshot der Vorlage bei Freigabe) + denormalisierter Titel (Feed).
    content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Versionierung: Ersetzen statt Ändern (Nachfolger-Objektnummer; Original bleibt erhalten).
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Zeitpunkt der Ausstellung (= Auftragsfreigabe, ab dann eingefroren). is_active kommt
    # aus dem TimestampMixin (Soft-Delete).
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
