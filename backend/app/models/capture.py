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

    **Was erfasst wird, sagt das Modul** (``process_steps.config``): die Erfassungspunkte,
    die beim Modellieren festgelegt wurden (Text · Ja/Nein · Bild · Signatur ·
    Soll-Ist-Vergleich). ``values`` ist die Antwort darauf, geschlüsselt nach ``key``.

    ``order_id``/``step_id`` sind **Pflicht**: eine Erfassung entsteht ausschliesslich,
    wenn ein Stück vor einem Modul steht und jemand bestätigt. Eine Erfassung ohne
    Prozess wäre ein Wert ohne Anlass – und genau die gab es vorher, als die Maske am
    Artikel hing und man an jedem Stück jederzeit erfassen konnte.

    ``result`` ist die Bewertung der **bewertbaren** Felder zum Zeitpunkt der Erfassung
    (``services/capture.evaluate``). ``NULL`` heisst «nichts Bewertbares dabei» – eine
    reine Text-/Foto-Erfassung hat kein Urteil, und ein erfundenes «bestanden» wäre eine
    Aussage, die niemand getroffen hat.

    **Eine Erfassung hat heute keine Folgen.** Sie sperrt nichts, stuft nichts hoch und
    löst keinen Folgeauftrag aus. Was aus einem «nicht bestanden» folgt, ist bewusst noch
    nicht entschieden (PROCESS_CORE.md §12.5); bis dahin ist ``result`` eine Aussage über
    die **Messung**, kein Ereignis im Prozess. Ein erfundener Abzweig wäre schlimmer als
    keiner.
    """

    __tablename__ = "captures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instance_unit_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    step_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # passed | failed | NULL

    captured_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


RESULTS = ("passed", "failed")
