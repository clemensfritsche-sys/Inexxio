from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin

class Order(Base, TimestampMixin):
    """Auftrag – ein ERP-Datensatz mit eigener Objektnummer.

    **Der Auftrag ist der Ort, an dem Prozesse ausgeführt werden** (PROCESS_CORE.md §8).
    Seine Struktur – die Schrittliste – hängt an ``process_steps``, seine Stücke an
    ``order_units``, seine Historie an ``process_events``.

    **Er existiert erst ab der Freigabe.** Ein Auftragsentwurf lebt ausschliesslich im
    Browser: keine Entwurfs-Zeile, keine vorreservierte Nummer, kein Autosave. Wer den
    Entwurf verwirft, lässt keine Spur. Entsprechend gibt es keinen Zustand «Entwurf» –
    ein gespeicherter Auftrag ist immer schon freigegeben.

    **Sein Status ist abgeleitet, nicht gespeichert** (``process.order_status``): er
    ergibt sich aus dem Zustand seiner Einzelinstanzen. Eine Spalte dafür wäre der zweite
    Ort, an dem er gesetzt wird – und der läuft beim ersten vergessenen Update von der
    Wahrheit weg. Genau das war der Fall: die Spalte stand auf ``released``, also zeigte
    der Kopf «Freigegeben» – ein Wort, das gar keinen Zustand beschreibt, sondern die
    Aktion, mit der der Auftrag entstanden ist.

    Der Endzustand ist keine Angabe des Auftrags: was das Ende-Objekt setzt, steht einmal
    in der Fachschicht (``statuses.DEFAULT_END_STATUS``, ``process._finish``).
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    #: Bei der Freigabe gesetzt: «Auftrag <Objektnummer>». Er entsteht im selben Zug wie
    #: die Objektnummer – vorher gibt es keine, nachher wäre er ein zweiter Schreibweg.
    name: Mapped[str] = mapped_column(String(120), nullable=False)
