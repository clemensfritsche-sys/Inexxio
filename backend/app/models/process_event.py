from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

#: An welchem Objekt ist das passiert. Start und Ende tragen keine ``step_id`` – sie
#: sind keine Zeilen in ``process_steps`` (§10.1), also braucht die Historie ein Wort
#: dafür statt eines Fremdschlüssels ins Leere.
KIND_START = "start"
KIND_STEP = "step"
KIND_END = "end"

#: Der **Auftragswechsel** (Abweichungsauftrag §3.2/§3.3). Er passiert an keinem
#: Prozessobjekt – das Stück verlässt einen Auftrag mitten im Ablauf und tritt in einen
#: anderen ein. Beide Seiten schreiben, denn ein Ereignis gehört immer zu genau **einem**
#: Auftrag (``order_id``), und beide Historien müssen vollständig sein: sonst führe in
#: einer davon die Spur ins Nichts.
#:
#:   ``handover``  «das Stück hat diesen Auftrag verlassen» (``payload.to_order``)
#:   ``return``    «das Stück ist zurückgekehrt»            (``payload.from_order``)
#:
#: Der **Eintritt** braucht kein eigenes Wort: das ist ``start`` – und genau daran ist
#: eine Abweichung erkennbar, ohne dass irgendwo ein Flag steht: ihr Start-Eintrag trägt
#: einen anderen Vorher-Zustand als ``freigegeben`` (``process.deviation_flags``).
KIND_HANDOVER = "handover"
KIND_RETURN = "return"

#: **Die gezogene Stichprobe** (§2 des Datenerfassungs-Auftrags). Eine Zeile je gezogenem
#: Stück, geschrieben in dem Moment, in dem die Stücke am Modul **ankommen** – vorher
#: steht die Menge nicht fest, nachher wäre die Ziehung beeinflussbar.
#:
#: Sie steht hier und nicht in einem Feld am Modul, weil sie genau das braucht, was
#: dieser Log leistet: **eingefroren und nachvollziehbar**. Eine Stichprobe, die sich
#: nachträglich ändern lässt, ist keine – und ihr Wert liegt nicht im Algorithmus,
#: sondern darin, dass hinterher dasteht, wer gezogen wurde, wann und durch wen.
#:
#: Der Status ändert sich dabei nicht: gezogen zu sein ist keine Zustandsänderung des
#: Stücks, sondern eine Aussage darüber, was mit ihm geschehen wird.
KIND_SAMPLE = "sample"

#: **Es wurde erfasst** – mit ``payload.capture_id`` und ``payload.result``.
#:
#: Eigene Art, weil Erfassen und Passieren zwei Dinge sind: was **nicht bestanden** hat,
#: rückt nicht vor (§4) und hinterliesse sonst überhaupt keine Spur in der Historie –
#: die Messung stünde allein in ``captures``, und die Geschichte des Stücks bräche an
#: der interessantesten Stelle ab.
KIND_CAPTURE = "capture"


class ProcessEvent(Base):
    """Ebene 3 – der **Ereignis-Log**. Die Quelle der Wahrheit (PROCESS_CORE.md §10.3).

    **Append-only – durchgesetzt in der Datenbank** (``domain/process_log``: ein Trigger
    weist jedes ``UPDATE`` und ``DELETE`` ab). Es gibt kein ``is_active`` und kein
    ``updated_at`` – darum erbt diese Klasse **nicht** von ``TimestampMixin``. Eine
    Korrektur ist ein **neuer Eintrag**, nie eine Änderung des alten. Jeder Verweis
    (Auftrag, Modul, Stück, Person) ist ein Fremdschlüssel.

    Die Reihenfolge ist die ``id`` – sie ist die Zeitachse. ``created_at`` sagt, *wann*
    es war; *in welcher Reihenfolge* sagt die ``id``, weil zwei Einträge dieselbe
    Sekunde tragen können.
    """

    __tablename__ = "process_events"
    __table_args__ = (
        # Die Geschichte eines Stücks (Journey, Bild) und «was ist an diesem Modul
        # passiert» (Stichprobe, Protokoll) – je eine Frage, je ein Index.
        Index("ix_process_events_unit_timeline", "instance_unit_id", "id"),
        Index("ix_process_events_order_step_kind", "order_id", "step_id", "kind"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="RESTRICT"), index=True, nullable=False)
    #: ``NULL`` bei Start und Ende – die sind keine Schritt-Zeilen.
    step_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("process_steps.id", ondelete="RESTRICT"), nullable=True)
    instance_unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instance_units.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status_before: Mapped[str] = mapped_column(String(30), nullable=False)
    status_after: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("user_profiles.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
