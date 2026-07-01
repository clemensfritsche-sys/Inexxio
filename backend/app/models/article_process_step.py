from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticleProcessStep(Base, TimestampMixin):
    """Definition eines Prozessschritts am Artikel (Reiter «Prozess»).

    Unterstützte Typen (``step_type``): ``purchase`` (Beschaffung),
    ``inspection`` (Datenerfassung), ``movement`` (Bewegung). Die Reihenfolge
    bestimmt ``position`` (pro Artikel frei sortierbar); welche Schritte
    vorhanden sind, ist pro Artikel optional. Die Bestands-Instanzen entstehen
    bereits bei der Auftragsfreigabe (kein eigener Serialisierungs-Schritt).
    Kind-Objekt des Artikels – KEINE eigene Objektnummer.

    Wird ein Auftrag freigegeben, instanziiert das System aus diesen Schritten
    den Prozess (siehe ``services/process.py``).
    """

    __tablename__ = "article_process_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Ein Schritt gehört ENTWEDER zum Prozess eines Artikels (``article_id``, das
    # «wie es entsteht») ODER zum individuellen Prozess eines Auftrags (``order_id``,
    # auf bereits vorhandene Instanzen). Genau eines der beiden ist gesetzt – es gibt
    # kein eigenständiges Prozess-Objekt mehr.
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    step_type: Mapped[str] = mapped_column(String(30), default="purchase", nullable=False)

    # Nur für einen ``sale``-Schritt an einem **Mehrpositionen**-Auftrag (``order_lines``):
    # bindet diesen Schritt an EINE Position (Artikel + Menge), damit die Fachzeile
    # (``Sale``) bei der Freigabe die richtige Menge/den richtigen Artikel bekommt statt
    # den (bei Mehrpositionen NULL) ``order.article_id``/``order.quantity``.
    order_line_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # Pflicht-Bewegung: vom System rund um eine Beschaffung erzeugt (Versand/Wareneingang).
    # Nicht löschbar/editierbar und automatisch positioniert (services/process_steps.py).
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

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

    # Konfiguration «resource» (Ressource): Liste der benötigten Ressourcen je
    # Operation – [{article_id, quantity, mode}], mode ∈ consume | tool.
    resource_lines: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

