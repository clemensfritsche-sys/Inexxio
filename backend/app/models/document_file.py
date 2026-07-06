from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class DocumentFile(Base, TimestampMixin):
    """Ein **hochgeladenes Fremd-Dokument** (Beleg/Anleitung/Rechnung/…) – abgegrenzt vom
    Prozessschritt-``Document`` (Inexxio-eigene, verfasste Textdokumente).

    Der Nutzer lädt eine Datei (PDF/Bild) hoch oder fotografiert sie; die KI extrahiert
    Titel, Typ, Zusammenfassung und den Volltext (für spätere semantische Suche/RAG,
    aktuell «Objekt-bekannt → Text laden»). Die Zuordnung zu ERP-Objekten ist **n:m**
    (``DocumentLink``) – eine Rechnung gehört zu Lieferant **und** mehreren Artikeln.

    Das Dokument trägt – wie jedes ERP-Objekt – eine **eigene universelle Objektnummer**
    (``object_id``, Typ ``document``); zitierbar, etikettierbar, KI-referenzierbar. Die
    Bytes liegen über ``services/storage.py`` in GCS (oder als Fallback in ``document_blobs``);
    hier steht nur der ``storage_key`` + ``storage_backend`` (``gcs`` | ``db``)."""

    __tablename__ = "document_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    # Von der KI vergeben (bzw. vom Nutzer bestätigt/überschrieben).
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # invoice | delivery_note | manual | datasheet | certificate | contract | receipt | other
    doc_type: Mapped[str] = mapped_column(String(30), default="other", nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Volltext (Text-Layer bzw. KI-Transkript) – Basis für den späteren KI-Abruf.
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Strukturierte Extraktion je Typ (z. B. Rechnung: Betrag/Datum/Positionen) – optional.
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Datei / Ablage
    mime: Mapped[str] = mapped_column(String(100), default="application/pdf", nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(10), default="db", nullable=False)
    # Content-Hash (Dubletten-Erkennung: dieselbe Rechnung/dasselbe Manual nicht doppelt).
    sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    # Herkunft/Provenienz
    source: Mapped[str] = mapped_column(String(10), default="upload", nullable=False)   # upload | scan
    ai_model: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    ai_prompt_version: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # created_at / updated_at / is_active kommen aus TimestampMixin.
