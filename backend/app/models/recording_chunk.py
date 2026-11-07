"""**Ein Stück einer Aufnahme** (Phase 4 · Sprache, ``docs/konzept/phase4-bauplan.md``).

Der Browser schickt alle 30 s ein Stück; ein **Abschnitt** (5 Minuten) ist eine eigene,
vollständige Datei aus seinen Stücken in Reihenfolge. Die Bytes liegen im Bucket
(``recordings/<Aufnahme>/<Abschnitt>-<Stück>``, ``services/attachments``), ohne Bucket hier in
``data``. Technisch und kurzlebig: gelöscht nach der Abschrift, spätestens nach einem Tag
(``services/recordings``) – darum nicht im Log (``domain/log.EXEMPT``).
"""

from typing import Optional

from sqlalchemy import BigInteger, Integer, LargeBinary, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class RecordingChunk(Base, TimestampMixin):
    __tablename__ = "recording_chunks"
    __table_args__ = (UniqueConstraint("recording", "segment", "seq",
                                       name="uq_recording_chunks_piece"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: Die Aufnahme – Log-Id ihres ``recording.start``.
    recording: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    #: Der Abschnitt (ab 0; je 5 Minuten eine eigene, vollständige Datei).
    segment: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Das Stück im Abschnitt (ab 0; je 30 s).
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Die Bytes – nur, wenn kein Bucket sie hält (``attachments.put_object``).
    data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
