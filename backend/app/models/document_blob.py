from typing import Optional

from sqlalchemy import BigInteger, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class DocumentBlob(Base, TimestampMixin):
    """DB-Fallback für die Dokument-Bytes, wenn KEIN GCS-Bucket konfiguriert ist.

    So läuft das Beleg-Modul auch in der Sandbox/lokal ohne Bucket/IAM sofort. Ist
    ``settings.gcs_bucket`` gesetzt, liegen die Bytes in GCS und diese Tabelle bleibt
    leer (``services/storage.py`` entscheidet je Upload; der ``storage_backend`` steht
    am ``DocumentFile``). Anders als ``attachments`` wird hier NICHT normalisiert/
    re-kodiert – ein PDF muss unverändert bleiben."""

    __tablename__ = "document_blobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    storage_key: Mapped[str] = mapped_column(String(400), unique=True, index=True, nullable=False)
    mime: Mapped[str] = mapped_column(String(100), default="application/octet-stream", nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # created_at / updated_at / is_active kommen aus TimestampMixin.
