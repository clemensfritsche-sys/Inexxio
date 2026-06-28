from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import utcnow


class ObjectRef(Base):
    """Zentrale Registry der universellen Objektnummern (Typ-Auflösung).

    Jede vergebene 9-stellige Objektnummer wird hier mit ihrem **Objekttyp**
    registriert. Damit lässt sich eine gescannte/referenzierte Nummer in **O(1)**
    auflösen (statt jede Fachtabelle abzusuchen) – die Grundlage, um Quer-
    Referenzen (Standort, Ersetzen, Abweichung) künftig typsicher/integritäts-
    geschützt zu führen. Bewusst schlank: nur Nummer → Typ; die Fachtabellen
    bleiben die Quelle der Wahrheit für Inhalte/``is_active``.
    """

    __tablename__ = "objects"

    object_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    object_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
