from typing import Optional

from sqlalchemy import BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..domain.statuses import INITIAL_UNIT_STATUS
from .base import TimestampMixin


class InstanceUnit(Base, TimestampMixin):
    """Einzelinstanz – das **einzige Arbeitsobjekt** des Systems.

    Im Prozess wird ausschliesslich mit Einzelinstanzen gearbeitet: nie mit einer Instanz,
    nie mit einem Artikel. Jede Ansicht auf höherer Ebene (Instanz, Artikel, Bestand) ist
    nur eine Filterung oder Summierung von Einzelinstanzen – nie eine eigene Datenquelle.

    **Es gibt keine Mengen-Spalte.** Eine Einzelinstanz ist genau ein Stück; das ist ihre
    Definition, keine Einstellung. Was nicht gespeichert ist, kann nicht auf 0.5 oder 3
    stehen und damit der Definition widersprechen.

    **Nummer = ``<Objektnummer der Instanz>-<suffix>``.** Die Einzelinstanz zieht bewusst
    KEINE Nummer aus ``object_id_seq``: eine 1000er-Charge würde sonst 1000 Nummern des
    gemeinsamen Kreises verbrauchen, und genau dafür existiert die Instanz-Ebene. Der
    Suffix zählt innerhalb seiner Instanz ab 1 und wird an genau EINER Stelle vergeben:
    ``services/instances.create_instances``, im selben Zug wie die Instanz. Ein
    Nachträglich-Hinzufügen gibt es nicht mehr (Testnotiz #678) – damit gibt es auch
    keinen zweiten Ort, an dem eine Nummer entsteht.

    **Vergeben bleibt vergeben.** Eine Einzelinstanz wird nie gelöscht und nie
    deaktiviert (#679): ihre Nummer ist eine Identität, keine Position. Was einmal
    existiert hat, taucht in der Historie auf, und ein Verweis darauf darf nicht ins
    Leere zeigen.

    ``status`` ist der **eigene, individuelle** Zustand dieses einen Stücks – zwei
    Einzelinstanzen derselben Instanz dürfen verschieden stehen. Die Werte stammen aus
    der **geschlossenen Liste** (``domain/statuses``); wer sie ändert, tut das über
    ``services/process`` – dort und nur dort entsteht im selben Atemzug der Eintrag im
    Ereignis-Log. Ein zweiter Schreibweg wäre eine zweite Wahrheit.

    Ein frisch angelegtes Stück ist ``freigegeben``: es ist einsatzbereit und in keinem
    Auftrag – genau das heisst das Wort.
    """

    __tablename__ = "instance_units"
    __table_args__ = (
        UniqueConstraint("instance_id", "suffix", name="uq_instance_units_instance_suffix"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    # Laufende Nummer innerhalb der Instanz, beginnend bei 1.
    suffix: Mapped[int] = mapped_column(Integer, nullable=False)

    # Noch ohne Bedeutung: das Feld steht, die Logik folgt (siehe Klassen-Docstring).
    status: Mapped[str] = mapped_column(
        String(30), default=INITIAL_UNIT_STATUS, nullable=False,
    )

    #: **Wo dieses Stück liegt** – die Objektnummer seines Halters (``services/places``).
    #:
    #: Der Ort hängt am **Stück** und nicht an der Instanz: zwei Schrauben derselben
    #: Charge dürfen an zwei Orten liegen. Genau das konnte das Vorgängersystem nicht –
    #: es führte eine Standort→Menge-Map an der Instanz plus einen denormalisierten
    #: Skalar daneben, mit einem Umschalter dazwischen. Im Einzelinstanz-Modell fällt das
    #: ersatzlos weg: ein Stück, ein Ort.
    #:
    #: **Kein Typfeld daneben.** Objektnummern sind systemweit eindeutig, der Typ ist
    #: daraus ableitbar (``objects.resolve_object_type``). Halter ist alles, was eine
    #: Nummer hat: eine **Instanz** (Regal, Behälter, Palette), ein **Benutzer** oder ein
    #: **Unternehmen**. Ein *Stück* kann es hier nicht sein – es zieht bewusst keine
    #: Objektnummer; dafür steht ``place_unit_id`` daneben.
    #:
    #: **``NULL`` ist ein regulärer Zustand**, kein fehlender Wert: ein frisch erzeugtes
    #: Stück liegt nirgends, bis ein Modul es irgendwohin bringt.
    place_object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True,
    )

    #: **Der Träger** – das *Stück*, in dem dieses Stück steckt (``services/places``).
    #:
    #: Die zweite Art, einen Halter zu nennen, und sie ist nötig, weil eine Einzelinstanz
    #: keine Objektnummer trägt: eine verbaute Schraube liegt nicht «in Instanz
    #: 100000123» (das wären 600 Getriebe), sondern **in diesem einen** Getriebe.
    #:
    #: **Zwei Spalten, zwei Arten von Halter – nicht zwei Antworten auf eine Frage.** Die
    #: Genauigkeit des Ortes ist die Genauigkeit seiner Quelle: **gescannt** wird ein
    #: Etikett, und ein Etikett hat die Instanz (``place_object_id``); beim **Verbauen**
    #: kennt das Modul das Stück genau (``consumption.plan``), und diese Genauigkeit
    #: wegzuwerfen wäre eine erfundene Unschärfe. Ein ``CHECK`` erzwingt, dass höchstens
    #: eines von beiden gesetzt ist (Migration 112).
    #:
    #: **Nicht die Genealogie.** Der Log sagt, *worin* ein Stück verbaut wurde
    #: (``payload.into``) – unveränderlich, überlebt die Demontage. Diese Spalte sagt,
    #: *wo es jetzt liegt*, und wird beim Ausbau geräumt. Dass die beiden auseinander
    #: laufen können, ist der Beweis, dass es zwei Fragen sind (PROCESS_CORE §9.6).
    place_unit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True,
    )
