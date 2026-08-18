from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import utcnow

# Woher die Beobachtung stammt. Geschlossene Liste – wie bei der Modul-Bestätigung
# (`scan` ↔ `manual`) ist die HERKUNFT der Aussage Teil der Aussage.
SOURCE_SCAN = "scan"          # ein Mensch hat gescannt
SOURCE_TRACKING = "tracking"  # ein Dritter hat gemeldet (Sendungsverfolgung)
SOURCES = (SOURCE_SCAN, SOURCE_TRACKING)


class UnitPlace(Base):
    """**Wo ein Stück liegt** – eine Beobachtung, kein Zustand (PROCESS_CORE §15.1).

    Der aktuelle Ort einer Einzelinstanz ist die **letzte** Zeile hier; die Historie
    fällt geschenkt an, weil nichts überschrieben wird. Es gibt bewusst **keine**
    Ortsspalte an der Einzelinstanz – sie wäre die zweite Wahrheit, und genau daran ist
    der Vorgänger gescheitert (ADR 009 §2.2: eine Standort→Menge-Map plus ein
    denormalisierter Skalar daneben, mit einem Umschalter dazwischen).

    **Append-only.** Kein Update, kein Delete, kein ``is_active``, kein ``updated_at`` –
    darum erbt diese Klasse ``TimestampMixin`` NICHT. Eine Korrektur ist eine **neue**
    Zeile. Die Reihenfolge ist die ``id``, nicht der Zeitstempel: zwei Ablagen können
    dieselbe Sekunde tragen.

    **Bewusst NICHT im Ereignis-Log** (``process_events``, §11.3). Der hängt an
    ``order_id``/``step_id``; eine Ablage muss aber auch **ohne Auftrag** möglich sein –
    freier Bestand ist der Normalzustand eines Lagers, und genau dort war die Frage «wo
    ist es» bisher unbeantwortbar (`SYSTEM_INTENT` §5a). Diese Unabhängigkeit **ist** die
    Robustheit: der Ort funktioniert, wenn der Prozess stillsteht.

    **Ein Halter ist eine Objektnummer – mehr nicht** (§15.2). Daneben steht **kein**
    Typfeld: Objektnummern sind systemweit eindeutig, der Typ ist daraus ableitbar. Das
    spart die Validierung, die Typ-Labels und jede «unbekannter Typ»-Fallunterscheidung –
    im Vorgänger musste ein entfallener Wert ``'lagerplatz'`` tolerant zu ``None``
    aufgelöst werden, weil er sonst jede Ansicht zerlegt hätte.

    Halter ist damit alles, was eine Objektnummer hat: ein Regal, ein Behälter, eine
    Palette und der LKW sind **Instanzen**; Werk Nord und der Hauptsitz sind
    **Unternehmen**; ein Mitarbeiter, ein Kunde und DHL sind **Benutzer**. Es gibt keinen
    neuen Datensatztyp und keine Whitelist.

    **Diese Zeile ändert nie einen Status und nie eine Zugehörigkeit** (§15.6). Das ist
    die Robustheitsgarantie, konstruktiv statt geprüft: weil eine Ablage nichts anfasst
    ausser dem Ort, muss keine andere Regel im System von ihr wissen. Ein Stück darf
    gesperrt, verbaut, verschrottet oder in einer Abweichung sein – sein Ort ist trotzdem
    einfach der letzte Scan.
    """

    __tablename__ = "unit_places"
    __table_args__ = (
        # Die eine Leserichtung, die zählt: «wo ist dieses Stück» = die höchste id je
        # Einzelinstanz. Absteigend, damit der aktuelle Ort der erste Treffer ist.
        Index("ix_unit_places_unit_id_desc", "instance_unit_id", "id"),
        # Die Gegenrichtung: «was liegt hier». Dieselbe Tabelle, zweiter Index –
        # eine zweite Tabelle dafür wäre eine zweite Wahrheit (§15.9).
        Index("ix_unit_places_holder", "holder_object_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    instance_unit_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: Die Objektnummer des Halters. **Kein Typfeld daneben** (siehe Docstring).
    holder_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: Wer die Beobachtung gemacht hat. Bei ``tracking`` die Person, die den Vorgang
    #: angestossen hat – gemeldet hat ein Dritter, verantwortet wird es hier.
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    #: Woher die Aussage stammt (``SOURCES``). Ohne den Vermerk wäre eine gemeldete
    #: Ankunft von einem echten Scan nicht zu unterscheiden.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=SOURCE_SCAN)

    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False,
    )
