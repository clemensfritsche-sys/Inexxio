from typing import Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticleProcessStep(Base, TimestampMixin):
    """Definition eines Prozessschritts am Artikel (Reiter «Prozess»).

    Aktuell unterstützter Typ: ``purchase`` (Beschaffung / Purchase Order).
    Pro Schritt wird entweder ein Lieferant (User mit Rolle ``supplier``) ODER
    ein Webshop-Link hinterlegt. Kind-Objekt des Artikels – KEINE eigene
    Objektnummer (gehört zur Prozess-Definition, nicht zum Nummernkreis).

    Wird ein Auftrag freigegeben, instanziiert das System aus diesen Schritten
    den angestossenen Prozess (siehe ``services/purchase.py``).
    """

    __tablename__ = "article_process_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    step_type: Mapped[str] = mapped_column(String(30), default="purchase", nullable=False)

    # Konfiguration des purchase-Schritts
    mode: Mapped[str] = mapped_column(String(20), default="supplier", nullable=False)  # supplier | webshop
    supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    webshop_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Welche Artikel-Stammdaten der Lieferant sehen darf (Liste von Feld-Keys).
    # NULL ⇒ nur die Pflichtfelder. Pflichtfelder sind immer enthalten.
    shared_fields: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
