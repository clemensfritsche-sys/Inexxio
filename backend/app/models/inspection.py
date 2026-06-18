from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Inspection(Base, TimestampMixin):
    """Ausführung des Schritts «Datenerfassung» – unter dem Auftrag.

    KEINE eigene Objektnummer. Stichproben-Prüfumfang (% der Menge) aus der
    Prozessdefinition; der Prüfer erfasst die geprüfte Anzahl, erfasst die in der
    Maske definierten Werte (``values``) und das Ergebnis (passed/failed). Die
    Datenerfassung dient nicht nur der Qualitätskontrolle, sondern beliebiger
    Werterfassung; nur bewertbare Felder (Soll-Ist/Gut-Schlecht) erzeugen ein
    Pass/Fail. Ist eine Stichprobe ungenügend, wird auf 100 % hochgestuft
    (``escalated``). Das Ergebnis wird auf die Instanzen (qc_status) übertragen.
    """

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Welcher Prozessschritt-Definition (Routing): erlaubt mehrere gleichartige
    # Schritte hintereinander. NULL = Altdaten (einziger Schritt seines Typs).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    result: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending|passed|failed
    checked_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    inspector_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Erfasste Werte der Maske (Altformat, einzelne Erfassung): {field_key: value}
    values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Stichproben je Instanz: [{instance_id, slot, values:{field_key: value}}]
    samples: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # Auf 100 %-Prüfung hochgestuft (eine Stichprobe war ungenügend)
    escalated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False)
