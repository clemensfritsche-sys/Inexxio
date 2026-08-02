from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class InstanceOrderLink(Base, TimestampMixin):
    """Unveränderlicher Verweis: **Auftrag X hat Instanz Y verarbeitet** (als Subjekt).

    Die Auftrags-Historie einer Instanz darf NICHT von veränderlichen Zeigern abhängen
    (``subject_of_order_id`` wandert bei Wieder-Bindung/Abbruch, ``reserved_for_order_id``
    wird bei Abschluss gelöst). Hier wird jede Verarbeitung **einmal dauerhaft** festgehalten
    (bei der Freigabe geschrieben) – so bleibt „welche Aufträge haben diese Instanz
    angefasst" immer vollständig und korrekt (eine Quelle der Wahrheit für die Historie).
    """

    __tablename__ = "instance_order_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instance_object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)  # DB-id des Auftrags
    # **Wie viel dieser Instanz der Auftrag übernommen hat** – der Materialfluss (Notiz #413).
    #
    # Ohne sie ist die Menge nur so lange bekannt, wie der Auftrag läuft: bei Abschluss wird
    # die Reservierung gelöst, und «wie viel ging da eigentlich rein?» wäre nicht mehr
    # beantwortbar. Genau das braucht der Fluss aber, um an der Kante «2 × 100000590» zu
    # zeigen – und später die Geschichte einer Instanz über alle Aufträge hinweg.
    #
    # ``NULL`` = Altbestand vor Migration 097; dort fällt die Anzeige auf die abgeleitete
    # Menge zurück (tolerant lesen, streng schreiben).
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)
