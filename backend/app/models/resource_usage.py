from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ResourceUsage(Base, TimestampMixin):
    """Ausführung des Prozessschritts «Ressource» – läuft unter dem Auftrag.

    KEINE eigene Objektnummer (analog Bewegung/Datenerfassung): markiert den
    Abschluss des Schritts und protokolliert, welche Instanzen **verbraucht**
    (FIFO nach Freigabe, in die Produkt-Instanz eingebaut) bzw. als
    **Betriebsmittel** genutzt wurden. Der eigentliche Lagerabgang ist der
    Standortwechsel der verbrauchten Instanzen in die Produkt-Instanz
    (``instances.location_type='instance'``).
    """

    __tablename__ = "resource_usages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    used_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Protokoll: {"consume": [{article_id, picks:[{instance_id, quantity, into_instance_id, split_from?}]}],
    #             "tools":   [{article_id, instance_ids:[...]}]}
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
