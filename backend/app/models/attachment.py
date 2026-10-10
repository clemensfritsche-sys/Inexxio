from typing import Optional

from sqlalchemy import BigInteger, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Attachment(Base, TimestampMixin):
    """Ein hochgeladenes Bild (Foto), in der DB abgelegt und über einen **unerratbaren
    Token** ausgeliefert – ohne eigene Cloud-Infrastruktur, sofort lauffähig (später auf
    GCS umstellbar, indem nur der Service dahinter wechselt).

    Verbraucher (Datenerfassung, Verkauf/Shop) speichern die **URL** (``/api/v1/attachments/
    {token}``) als String in ihren Feldern – kein Fremdschlüssel, self-contained. Bilder werden
    beim Upload normalisiert (EXIF-Rotation, max. Kantenlänge, JPEG) → beschränkte Grösse."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    mime: Mapped[str] = mapped_column(String(100), default="image/jpeg", nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # created_at / updated_at / is_active kommen aus TimestampMixin.
