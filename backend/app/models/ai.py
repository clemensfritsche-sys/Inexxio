from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class AiAction(Base, TimestampMixin):
    """Ein von der KI **vorgeschlagener** Vorgang mit menschlichem Freigabe-Gate (ADR 004).

    «Vorschlagen ≠ Ausführen»: kritische Aktionen (z. B. Auftrag freigeben) legt die KI
    nur als Vorschlag an; erst die menschliche **Bestätigung** führt den echten,
    autorisierten Service-Pfad aus – exakt einmal (Idempotenz über ``status``).
    Keine eigene Objektnummer (läuft unter dem Zielobjekt), Attribution über
    ``proposed_by_ai_id`` (KI-Principal) + ``requested_by_id`` (delegierender Mensch).
    """

    __tablename__ = "ai_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)   # z. B. 'release_order'
    summary: Mapped[str] = mapped_column(String(500), nullable=False)      # menschenlesbar (Karte im Chat)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Parameter der Aktion
    # proposed → executed | rejected | failed
    status: Mapped[str] = mapped_column(String(20), default="proposed", nullable=False)

    proposed_by_ai_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # KI-UserProfile.id
    requested_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)    # Mensch (Delegation)
    decided_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)      # wer bestätigt/abgelehnt hat
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Ziel-/Ergebnisobjekt (universelle Objektnummer), z. B. der freigegebene Auftrag.
    target_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
