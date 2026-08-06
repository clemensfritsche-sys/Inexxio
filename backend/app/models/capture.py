from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Capture(Base, TimestampMixin):
    """Datenerfassung an **einer Einzelinstanz**.

    Erfasst wird immer am Stück, nie an der Instanz und nie am Artikel – das ist die
    Einzelinstanz-Regel, hier als Fremdschlüssel. Eine Auswertung «wie steht die Charge
    da?» ist eine Summierung über die Einzelinstanzen, keine eigene Zeile.

    **Was erfasst wird, sagt der Artikel** (``articles.capture_fields``): dieselbe
    Feld-Beschreibung wie bisher (Soll-Ist mit Toleranz, Gut/Schlecht, Text, Foto,
    Unterschrift). ``values`` ist die Antwort darauf, geschlüsselt nach ``key``.

    ``result`` ist die Bewertung der **bewertbaren** Felder zum Zeitpunkt der Erfassung
    (``services/capture.evaluate``). ``NULL`` heisst «nichts Bewertbares dabei» – eine
    reine Text-/Foto-Erfassung hat kein Urteil, und ein erfundenes «bestanden» wäre eine
    Aussage, die niemand getroffen hat.

    **Eine Erfassung hat keine Folgen.** Sie sperrt nichts, stuft nichts hoch und löst
    keinen Folgeauftrag aus: das war Prozesslogik und ist entfallen. Sie hält fest, was
    gemessen wurde – was daraus folgt, entscheidet die neue Prozesslogik.
    """

    __tablename__ = "captures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instance_unit_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # passed | failed | NULL

    captured_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


RESULTS = ("passed", "failed")
