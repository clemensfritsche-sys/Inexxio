from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Disposal(Base, TimestampMixin):
    """Ausführung des Schritts «Verschrotten» – unter dem Auftrag (keine eigene Nummer).

    Markiert den Abschluss des Verschrottungsschritts (analog zur Bewegung). Welche
    Instanzen verschrottet wurden, steht direkt auf den Instanzen
    (``instances.disposition = 'scrapped'``); dieser Datensatz hält nur fest, dass der
    Schritt ausgeführt wurde (Wer/Wann/Notiz/Grund).
    """

    __tablename__ = "disposals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Routing: an welche Prozessschritt-Definition gebunden (mehrere möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scrapped_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
