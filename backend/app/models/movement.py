from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Movement(Base, TimestampMixin):
    """Ausführung des Schritts «Bewegung» – unter dem Auftrag (keine eigene Nummer).

    Markiert den Abschluss des Bewegungsschritts (analog zur Eingangskontrolle).
    Die konkreten Zielstandorte werden direkt auf den Instanzen gespeichert
    (``instances.location_type`` / ``location_id``); dieser Datensatz hält nur
    fest, dass der Lagerist die Einlagerung bestätigt hat (Wer/Wann/Notiz).
    """

    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Routing: an welche Prozessschritt-Definition gebunden (mehrere möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    moved_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
