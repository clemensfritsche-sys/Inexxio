from sqlalchemy import BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
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
    Suffix ist **kumulierend** – einmal vergeben, nie wieder verwendet. Er wird beim
    Anlegen als ``MAX(suffix)+1`` unter Zeilensperre auf der Instanz ermittelt
    (``services/instances.add_units`` – die einzige Schreibstelle). Ein gespeicherter
    Zähler wäre eine zweite Wahrheit neben den Zeilen; da nur soft gelöscht wird
    (``is_active=false``), bleibt jede vergebene Nummer in ``MAX`` sichtbar und kommt
    nicht zurück.

    ``status`` ist der **eigene, individuelle** Zustand dieses einen Stücks – zwei
    Einzelinstanzen derselben Instanz dürfen verschieden stehen. Werte und Übergänge
    kommen mit der neuen Prozesslogik; heute trägt das Feld noch keine Logik.
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
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)
