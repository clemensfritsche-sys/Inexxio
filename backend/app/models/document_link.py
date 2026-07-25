from typing import Optional

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class DocumentLink(Base, TimestampMixin):
    """n:m-Verknüpfung zwischen einem hochgeladenen ``DocumentFile`` und einem ERP-Objekt.

    Ein Dokument gehört selten zu genau EINEM Objekt: eine Rechnung betrifft den
    Lieferanten UND mehrere Artikel UND einen Auftrag. Darum keine 1:1-Spalte, sondern
    eine Verknüpfungszeile je Bezug. ``object_id`` ist die universelle Objektnummer des
    Ziels (Artikel/Auftrag/Instanz/Benutzer/Unternehmen), ``object_type`` ein
    Snapshot für Filter/Anzeige. Ein Dokument hat IMMER mindestens eine Verknüpfung
    (Freigabe-Gate im Service) – es darf nicht objektlos existieren."""

    __tablename__ = "document_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)   # -> document_files.id
    object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)     # Ziel-Objektnummer
    object_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Semantik der Beziehung (z. B. about | invoice_for | manual_for | delivery_for).
    relation: Mapped[str] = mapped_column(String(30), default="about", nullable=False)
    # Das «Haupt»-Objekt, dem das Dokument primär zugeordnet ist (für Audit/Anzeige).
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # created_at / updated_at / is_active kommen aus TimestampMixin.
