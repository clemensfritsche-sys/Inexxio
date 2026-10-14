from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Instance(Base, TimestampMixin):
    """Gruppe von Einzelinstanzen – ein Ordner, kein Bestandsposten.

    Die Instanz existiert aus genau einem Grund: **zigtausend Schrauben sollen keine
    zigtausend Objektnummern bekommen.** Sie fasst Einzelinstanzen zusammen und trägt
    dafür eine eigene 9-stellige Objektnummer (etikettier-/QR-fähig). Mehr tut sie nicht.

    **Sie trägt KEINE Menge.** Die Menge ist die Anzahl ihrer Einzelinstanzen und wird
    ausgerechnet, nie gespeichert (``services/instances.quantity``). Eine gespeicherte
    Menge wäre eine zweite Wahrheit neben den Zeilen, die sie zählt – und genau diese
    Fehlerklasse («Zeilen zählen statt Mengen summieren», und umgekehrt) hat das
    Vorgängermodell wieder und wieder produziert. Was es nicht gibt, kann nicht driften.

    ``kind`` sagt nur, wie die Gruppe entstanden ist:
        einzeln → eine Einzelinstanz je Stück (Seriennummern-Fall)
        batch   → viele Einzelinstanzen unter einer Nummer (Schüttgut, Charge)
    Es ist ein Etikett für die Anzeige, keine Regel: im Prozess wird ausschliesslich mit
    Einzelinstanzen gearbeitet, nie mit der Instanz und nie mit dem Artikel.

    **Einen Status trägt sie nicht.** Er wird abgeleitet (``services/instances.status_of``),
    genau wie die Menge: eine Gruppe ist im Prozess, solange eines ihrer Stücke es ist.
    Die frühere Spalte stand auf ``new`` und wurde nie geschrieben – ein Feld, das niemand
    setzt, ist kein Zustand, sondern eine Behauptung, die irgendwann falsch wird.
    """

    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Jede Instanz hat eine Objektnummer – anders als die Einzelinstanz, deren Nummer
    # von dieser hier abgeleitet wird (``<object_id>-<suffix>``).
    object_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)

    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # einzeln | batch

    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


KINDS = ("einzeln", "batch")
