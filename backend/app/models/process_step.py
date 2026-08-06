from typing import Any, Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin

#: Die Modultypen. Heute genau einer: ein **Testmodul**, bewusst ohne Fachlogik – es
#: prüft den Vorher-Status, setzt den Nachher-Status, loggt, und rückt das Stück vor.
#: Das erste echte Modul wird die Datenerfassung sein.
TESTMODUL = "testmodul"
MODULE_TYPES = (TESTMODUL,)


class ProcessStep(Base, TimestampMixin):
    """Ebene 1 – die **Prozessdefinition** (PROCESS_CORE.md §10.1).

    **Eine geordnete Liste, kein allgemeiner Graph.** Ein Auftrag hat einen Anfang, ein
    Ende und dazwischen eine Folge; ``position`` ist die Kante. Verzweigungen entstehen
    nicht innerhalb der Definition, sondern als eigener Auftrag daneben – ein
    Kantenmodell böte eine Freiheit an, die es fachlich nicht gibt, und jede Auswertung
    müsste danach mit Zyklen und toten Ästen rechnen.

    **Start und Ende sind keine Zeilen.** Es gibt genau einen von jedem, ihre Position
    ist implizit, und ihre Übergänge gehören zum System (``domain/statuses``), nicht zur
    Modellierung.

    ``status_before``/``status_after`` sind **Pflicht** – ein Modul ohne definierten
    Übergang ist nicht anlegbar. Beide Werte stammen aus der geschlossenen Liste; der
    Wächter sitzt in ``domain/statuses.assert_known``.

    **Eingefroren nach der Freigabe.** Weil der Auftrag erst mit der Freigabe entsteht,
    entstehen auch diese Zeilen erst dort – und danach gibt es keinen Schreibpfad mehr
    auf sie. Das ist keine bewachte Regel, sondern eine fehlende Tür.
    """

    __tablename__ = "process_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    module_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status_before: Mapped[str] = mapped_column(String(30), nullable=False)
    status_after: Mapped[str] = mapped_column(String(30), nullable=False)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
