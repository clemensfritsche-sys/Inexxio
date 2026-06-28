from sqlalchemy import BigInteger
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
