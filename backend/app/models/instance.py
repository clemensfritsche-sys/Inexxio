from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Instance(Base, TimestampMixin):
    """Bestandsobjekt – entsteht bei der **Auftragsfreigabe**.

    Aus der Artikel-Einstellung ``serialization`` abgeleitet:
        unit  → je Stück eine eigene Instanz (quantity = 1, eigene Nummer)
        batch → eine Charge-Instanz mit quantity = Bestellmenge

    Trägt eine eigene 9-stellige Objektnummer (etikettier-/QR-fähig) und ist die
    Grundlage des Bestands. Entsteht unter einem Auftrag (``order_id``).
    """

    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)

    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    kind: Mapped[str] = mapped_column(String(10), default="unit", nullable=False)   # unit | batch
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    serial_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # Qualitätsstatus: pending (Eingangskontrolle offen) | passed | failed
    qc_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Standort – eine Instanz hat IMMER einen Standort (ab Freigabe: Lieferant bzw. Wareneingang).
    # Der Standort ist stets ein Datensatzobjekt mit Nummer:
    #   lagerplatz → StorageLocation | user → UserProfile | instance → andere Instanz
    location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
