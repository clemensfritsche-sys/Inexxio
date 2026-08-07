from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, String, func
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
#: eine Abweichung erkennbar, ohne dass irgendwo ein Flag steht (§2 des Auftrags): ihr
#: Start-Eintrag trägt ``status_before = im_prozess`` statt ``freigegeben``.
KIND_HANDOVER = "handover"
KIND_RETURN = "return"

EVENT_KINDS = (KIND_START, KIND_STEP, KIND_END, KIND_HANDOVER, KIND_RETURN)


class ProcessEvent(Base):
    """Ebene 3 – der **Ereignis-Log**. Die Quelle der Wahrheit (PROCESS_CORE.md §10.3).

    **Append-only.** Es gibt hier keinen Update- und keinen Delete-Pfad, kein
    ``is_active``, keinen ``updated_at`` – deshalb erbt diese Klasse als einzige
    **nicht** von ``TimestampMixin``: ein ``updated_at`` wäre das Versprechen, dass
    sich eine Zeile ändern kann. Eine Korrektur ist ein **neuer Eintrag**, nie eine
    Änderung des alten.

    Die Reihenfolge ist die ``id`` – sie ist die Zeitachse. ``created_at`` sagt, *wann*
    es war; *in welcher Reihenfolge* sagt die ``id``, weil zwei Einträge dieselbe
    Sekunde tragen können.

    **Eigene Tabelle, nicht der bestehende ``events``-Strom.** Der ist ein
    Beobachtungs-Outbox für KI und Analytik mit freier Payload; hier geht es um die
    Buchführung, aus der sich der Zustand ableiten lässt. Beides in denselben Zeilen zu
    führen hiesse, eine «nice to have»-Spur und eine verbindliche Historie zu mischen –
    und die schwächere Garantie gewinnt immer.
    """

    __tablename__ = "process_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    #: ``NULL`` bei Start und Ende – die sind keine Schritt-Zeilen.
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    instance_unit_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status_before: Mapped[str] = mapped_column(String(30), nullable=False)
    status_after: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
