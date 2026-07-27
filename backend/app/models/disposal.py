from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Disposal(Base, TimestampMixin):
    """Ausführung von «Verschrotten» ODER «Sperren» – unter dem Auftrag (keine eigene Nummer).

    Beide Schritte steuern eine vorhandene Instanz aus dem verwendbaren Bestand aus und
    teilen sich darum diese Marker-Zeile; ``mode`` sagt, welcher der beiden es war:

    * ``scrap`` – **endgültig**: ``instances.disposition = 'scrapped'``, standortlos.
    * ``block`` – **vorübergehend**: ``instances.quality = 'blocked'``, Standort bleibt.
      Die Sperre ist an der Instanz wieder aufhebbar (defekte Maschine nach der Wartung).

    Welche Instanzen betroffen sind, steht direkt auf den Instanzen; dieser Datensatz hält
    nur fest, DASS der Schritt ausgeführt wurde (Wer/Wann/Notiz).
    """

    __tablename__ = "disposals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Routing: an welche Prozessschritt-Definition gebunden (mehrere möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # 'scrap' (endgültig) | 'block' (vorübergehend, aufhebbar)
    mode: Mapped[str] = mapped_column(String(10), default="scrap", nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scrapped_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
