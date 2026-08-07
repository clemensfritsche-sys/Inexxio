from typing import Any, Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin

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

    ``status_before``/``status_after`` sind **Pflicht**, werden aber nicht **gefragt**:
    der Übergang gehört zum Modultyp und steht in ``domain/modules`` (die Datenerfassung
    ist ein Durchläufer – sie misst, sie verändert den Zustand nicht). Zwei Auswahlen
    beim Anlegen hätten dem Anwender eine Entscheidung angeboten, deren einzige richtige
    Antwort schon feststand.

    ``config`` trägt, was der Modultyp braucht – bei der Datenerfassung die
    Erfassungspunkte. Geprüft wird sie beim Anlegen (``Module.clean_config``), nicht zur
    Laufzeit: ein Modul, das erst beim Ausführen auffliegt, steht schon im Prozess.

    **Die ``id`` IST die Identität des Moduls** (Testnotiz #687). Sie entsteht mit der
    Zeile, ändert sich nie und ist das Einzige, worauf der Ereignis-Log zeigt. Vorher
    diente der **Name** als Merkmal in der Anzeige – und ein Name ist eine Eingabe: er
    lässt sich ändern, doppelt vergeben oder leer lassen, und dann zeigt die Historie auf
    etwas, das es so nie gab. Wie ein Modul **heisst**, sagt sein Typ (``domain/modules``);
    **welches** es ist, sagt diese Zahl.

    **Eingefroren nach der Freigabe.** Weil der Auftrag erst mit der Freigabe entsteht,
    entstehen auch diese Zeilen erst dort – und danach gibt es keinen Schreibpfad mehr
    auf sie. Das ist keine bewachte Regel, sondern eine fehlende Tür.
    """

    __tablename__ = "process_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    module_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status_before: Mapped[str] = mapped_column(String(30), nullable=False)
    status_after: Mapped[str] = mapped_column(String(30), nullable=False)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Herkunftsstempel der **Kopie** (PROCESS_CORE.md §6.4, Auftragspunkt §6): stammt diese
    # Zeile aus dem Erzeugungsprozess eines Artikels, steht hier dessen id und der
    # ``process_version``-Stand von damals. Beide ``None`` = im Auftrag von Hand modelliert.
    # Ein **Verweis** auf die Vorlage statt einer Kopie hiesse, dass eine spätere
    # Artikeländerung laufende Aufträge rückwirkend umschreibt – genau das darf nicht sein.
    source_article_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
