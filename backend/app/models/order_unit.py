from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class OrderUnit(Base, TimestampMixin):
    """Welche Einzelinstanz gehört zu welchem Auftrag – **und die Exklusivität**.

    Das ist die Definition aus PROCESS_CORE.md §2.1, materialisiert: bei der Freigabe
    entsteht je Stück eine Zeile, und danach kommt keine dazu und keine geht weg. Kein
    Nachschieben, kein Ersetzen zur Laufzeit.

    **Die Exklusivitätsregel steht als partieller Unique-Index in der Datenbank**
    (§3): ``released_at IS NULL`` heisst «aktiv», und ein Stück kann höchstens eine
    solche Zeile haben. Sie in der Anwendungslogik zu prüfen genügt nicht – zwei
    gleichzeitige Freigaben lesen beide «ist frei» und schreiben beide. Der Index ist
    die einzige Stelle, an der das nicht passieren kann.

    Der Unterschied, den §3 macht, steckt in genau dieser einen Spalte:

    ===================  ===============================================
    ``released_at`` NULL **aktiv** – exklusiv, das Stück ist im Prozess
    ``released_at`` Wert **referenziert** – Historie, beliebig oft
    ===================  ===============================================

    Frei wird ein Stück, sobald es das **Ende-Objekt** passiert hat – nicht erst, wenn
    der ganze Auftrag fertig ist. Der Auftrag ist fertig, wenn alle seine Stücke durch
    sind; das ist eine Folge, keine eigene Regel.

    ``current_step_id`` ist die Laufzeit-Projektion «wo steht dieses Stück» und gehört
    hierher, nicht an die Einzelinstanz: es ist eine Aussage über die Zugehörigkeit,
    nicht über das Stück selbst.

    **Damit gibt es zwei Gründe, warum eine Zeile geschlossen ist** – und der Unterschied
    steckt in ``current_step_id``:

    ==============================  =========================================
    ``current_step_id IS NULL``     **angekommen** – das Ende-Objekt passiert
    ``current_step_id IS NOT NULL`` **ausgeschert** – ein anderer Auftrag hat
                                    das Stück übernommen; hier steht, wohin es
                                    zurückkehrt
    ==============================  =========================================

    Das ist keine zweite Bedeutung, sondern dieselbe: ``current_step_id`` sagt immer «wo
    steht dieses Stück in diesem Auftrag», und beim Ausscheren steht es eben noch dort.
    Genau deshalb braucht die Rückkehr **kein eigenes Feld** – die Position ist schon da,
    und ihre Wahrheit steht im Ereignis-Log.

    ``return_to_order_id`` ist **die Verbindung zwischen zwei Aufträgen** (Abweichungs-
    auftrag §6): kehrt dieses Stück nach dem Durchlauf in den Auftrag zurück, aus dem es
    kam? Sie hängt an der **Verbindung**, nicht am Auftrag – dadurch funktionieren
    Schachtelung (ein Abweichungsauftrag hat seine eigene Abweichung) und Parallelität
    (mehrere Abweichungen gleichzeitig) ohne eine einzige zusätzliche Regel.

    ``NULL`` heisst «kehrt nirgends zurück» – entweder war das Stück frei (ein ganz
    gewöhnlicher Auftrag) oder die Rückführung wurde bei der Definition gekappt
    (Aussonderung). Der Quell-Auftrag läuft dann mit reduzierter Menge weiter; er wartet
    nicht. Auch **«wartet auf Rückführung» ist damit abgeleitet**, nicht gespeichert:
    es wartet, wer noch mindestens eine offene rückführende Verbindung hat. Kein Zähler,
    den jemand zu dekrementieren vergessen kann.
    """

    __tablename__ = "order_units"
    __table_args__ = (
        # Die eine Regel, an der einzigen Stelle, an der sie nicht umgangen werden kann.
        Index(
            "uq_order_units_active",
            "instance_unit_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    instance_unit_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    current_step_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    #: Die Verbindung: in welchen Auftrag kehrt dieses Stück zurück, wenn es hier durch
    #: ist. ``NULL`` = nirgendwohin (siehe Klassen-Docstring).
    return_to_order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, index=True, nullable=True,
    )
