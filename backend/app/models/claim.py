from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Claim(Base, TimestampMixin):
    """Reklamation (RMA) — eigenständiger ERP-Datensatz mit eigener Objektnummer.

    Eine Reklamation bezieht sich auf genau eine serialisierte **Instanz** (nur
    rückverfolgbare Objekte sind reklamierbar). Artikel- und Auftrags-Bezug werden
    aus der Instanz abgeleitet und denormalisiert mitgeführt.

    Statuswerte (`status`):
        open      → Offen (neu, in Klärung)
        accepted  → Angenommen (Reklamation anerkannt, in Bearbeitung)
        rejected  → Abgelehnt (nicht anerkannt)
        closed    → Abgeschlossen (erledigt)

    `direction` unterscheidet, gegen wen/von wem sich die Reklamation richtet:
        internal  → interne Beanstandung (z. B. aus der Eingangskontrolle)
        supplier  → Reklamation an einen Lieferanten
        customer  → Reklamation eines Kunden

    `source` hält fest, wie die Reklamation entstand (manuell vs. automatisch aus
    einer fehlgeschlagenen Datenerfassung).
    """

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)

    # Bezugsobjekte – stets über die Objektnummer angesprochen (klickbar im Frontend).
    instance_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    article_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    order_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Beanstandung
    reason: Mapped[str] = mapped_column(String(30), default="defect", nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Lösung
    resolution: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Herkunft & Melder
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # manual | inspection
    reported_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
