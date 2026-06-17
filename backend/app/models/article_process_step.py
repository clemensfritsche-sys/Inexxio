from typing import Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticleProcessStep(Base, TimestampMixin):
    """Definition eines Prozessschritts am Artikel (Reiter «Prozess»).

    Unterstützte Typen (``step_type``): ``purchase`` (Beschaffung),
    ``serialization`` (Serialisierung), ``inspection`` (Eingangskontrolle),
    ``movement`` (Bewegung). Die Reihenfolge bestimmt ``position`` (pro Artikel
    frei sortierbar); welche Schritte vorhanden sind, ist pro Artikel optional.
    Kind-Objekt des Artikels – KEINE eigene Objektnummer.

    Wird ein Auftrag freigegeben, instanziiert das System aus diesen Schritten
    den Prozess (siehe ``services/process.py``).
    """

    __tablename__ = "article_process_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    step_type: Mapped[str] = mapped_column(String(30), default="purchase", nullable=False)

    # Konfiguration «purchase»
    mode: Mapped[str] = mapped_column(String(20), default="supplier", nullable=False)  # supplier | webshop
    supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    webshop_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Welche Artikel-Stammdaten der Lieferant sehen darf (Pflichtfelder immer).
    shared_fields: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Konfiguration «inspection» (Datenerfassung): Stichproben-Prüfumfang in % der
    # Menge + Erfassungsfelder (Soll-Ist mit Toleranz, Gut/Schlecht, Text).
    sample_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capture_fields: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Konfiguration «movement» (Bewegung): optionales Vorgabe-Ziel. Beides NULL =
    # der Lagerist entscheidet beim Ausführen frei je Instanz.
    target_location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    target_location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

