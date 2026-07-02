from typing import Optional

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ReturnReceipt(Base, TimestampMixin):
    """Ausführung des Schritts «Rücknahme» – das **Spiegelbild des Verschrottens**.

    Nimmt verkaufte Instanzen einer Retoure (Unter-Auftrag ``reason='return'``) physisch
    zurück ins Lager: die Instanzen-Menge wird wiederhergestellt (Spiegel von ``consume_qty``
    beim Verkauf), ``disposition`` wechselt ``sold`` → ``in_stock`` (bzw. ``pending``, wenn
    erst geprüft werden soll), der Standort wird gesetzt. Läuft – wie Verschrotten/Bewegung –
    unter dem Auftrag (**keine eigene Objektnummer**); welche Instanzen betroffen sind, steht
    direkt auf den Instanzen. Dieser Datensatz markiert nur den Abschluss (Wer/Wann/Notiz).
    """

    __tablename__ = "return_receipts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Routing: an welche Prozessschritt-Definition gebunden (mehrere möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    received_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Zielstandort der zurückgenommenen Ware (Vorgabe; je Instanz gesetzt).
    location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # lagerplatz|user|instance
    location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Zur Prüfung zurückgenommen? → Instanzen starten wieder als ``pending`` (Datenerfassung
    # entscheidet danach: wieder freigeben oder verschrotten), sonst direkt ``in_stock``.
    to_inspection: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
