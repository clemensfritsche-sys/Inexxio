from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class FeedbackNote(Base, TimestampMixin):
    """Eine in der Oberfläche **angeheftete Testnotiz** («das hier stört mich»).

    Bewusst **KEINE Objektnummer**: eine Testnotiz ist ein Meta-Artefakt *über* dem
    System – kein Geschäftsobjekt. Sie gehört damit weder in den 9-stelligen
    Nummernkreis noch in den ERP-Feed (gleiche Einordnung wie ``AiAction``,
    ``Attachment``, ``AuditLog``).

    Der Wert steckt nicht im Kommentar, sondern im **automatisch mitgeschnittenen
    Kontext**: Route, geöffneter Datensatz, Anker am geklickten Element und Umgebung.
    Damit findet die Weiterverarbeitung (Entwicklung/KI) die betroffene Stelle im Code,
    ohne dass der Melder etwas dokumentieren muss.

    * ``anchor``  – WO: ``{label, tag, selector, html, rx, ry}``. ``label`` ist der
      sichtbare Text des Elements («Freigeben») und in einer deutschsprachigen UI der
      beste greppbare Anker; ``rx``/``ry`` sind relative Koordinaten im Element (0–1),
      damit der Pin beim nächsten Besuch wieder an derselben Stelle sitzt.
    * ``context`` – WOMIT: ``{viewport, ua, role, version, errors}``. ``errors`` sind die
      letzten Laufzeitfehler der Sitzung (Ringpuffer im Client) – genau der Teil, den
      man von Hand nie sauber dokumentiert.
    """

    __tablename__ = "feedback_notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # offen → erledigt | verworfen (Ampel: open = gelb, done = grün, dismissed = rot/grau)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    route: Mapped[str] = mapped_column(String(500), default="", nullable=False, index=True)
    # Objektnummer des zum Zeitpunkt der Notiz geöffneten Datensatzes (falls erkennbar).
    # Bewusst ``target_object_id`` wie bei ``AiAction``: ``object_id`` ist im System die
    # EIGENE Nummer eines Datensatzes – und die hat eine Notiz gerade nicht.
    target_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    anchor: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Rückkopplung: was daraus wurde (Commit/PR bzw. Ablehnungsgrund) – der Pin zeigt es
    # beim nächsten Testlauf an derselben Stelle an.
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    # created_at / updated_at / is_active kommen aus TimestampMixin.
