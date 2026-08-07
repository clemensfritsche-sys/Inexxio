"""Die **Journey einer Einzelinstanz** – woher sie kam, wohin sie ging.

Im Prozess wird ausschliesslich mit Einzelinstanzen gearbeitet, und ein Stück ist immer
in **genau einem** Auftrag aktiv. Alles ist damit ein einziger langer Prozess, nur
aufgeteilt in Aufträge – und diese Aufteilung ist genau das, was hier wieder
zusammengesetzt wird.

**Abgeleitet, nicht gepflegt.** Es gibt keine Spalten ``vorheriger_auftrag`` /
``naechster_auftrag``, die bei jeder Freigabe mitgeschrieben werden müssten. Solche
Zeiger laufen irgendwann auseinander – und dann ist die Journey unbrauchbar für genau
das, was sie beweisen soll. Die Quelle ist stattdessen die, die es ohnehin gibt: der
**Ereignis-Log** (``process_events``, PROCESS_CORE.md §10.3). Er ist append-only, hält
je Statuswechsel fest, welches Stück in welchem Auftrag war, und seine ``id`` ist die
Zeitachse.

Daraus fällt die Nachbarschaft ohne weiteres Zutun heraus::

    Vorgänger  = der Auftrag des letzten Ereignisses VOR dem ersten Ereignis
                 dieses Stücks in diesem Auftrag
    Nachfolger = der Auftrag des ersten Ereignisses NACH dem letzten

Beides ist damit automatisch lückenlos: was nicht im Log steht, ist nicht passiert, und
was passiert ist, steht drin.

**Gruppiert, nicht aufgezählt.** Bei 5000 Stück will niemand 5000 Verweise sehen (und
das Layout überlebt sie auch nicht). Die Antwort ist darum eine Liste je **Nachbar-
Auftrag** mit der Anzahl Stücke: «3 Stück aus Auftrag 100000123». Dieselbe Entscheidung
wie bei den Stück-Gruppen im Prozessbild (§8.3).

**Performance.** Zwei Abfragen je Auftrag, unabhängig von der Stückzahl – kein N+1. Der
teure Teil ist «das letzte Ereignis vor X je Stück»; er läuft als ``DISTINCT ON`` über
den Index ``(instance_unit_id, id)``. Das ist ein **abgeleiteter Index**, kein zweiter
Datenbestand: er beschleunigt eine Frage, er beantwortet sie nicht.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Order, ProcessEvent


def _span(order_id: int):
    """Je Stück: sein erstes und letztes Ereignis **in diesem Auftrag**.

    Das ist die Klammer, ausserhalb derer der Nachbar liegt. Zwei Grenzen statt einer,
    weil ein Stück den Auftrag betritt und wieder verlässt – und beides zählt.
    """
    return (
        select(
            ProcessEvent.instance_unit_id.label("unit_id"),
            func.min(ProcessEvent.id).label("first_id"),
            func.max(ProcessEvent.id).label("last_id"),
        )
        .where(ProcessEvent.order_id == order_id)
        .group_by(ProcessEvent.instance_unit_id)
        .subquery()
    )


def _neighbour_counts(db: Session, order_id: int, *, before: bool) -> list[tuple[int, int]]:
    """``[(Auftrag-id, Anzahl Stücke), …]`` – der direkte Nachbar je Stück, gezählt.

    ``DISTINCT ON (unit)`` mit passender Sortierung liefert je Stück genau **ein**
    Ereignis: das letzte davor bzw. das erste danach. Ein Stück ohne Nachbarn fällt
    heraus – es hat keinen, und ein Platzhalter wäre erfunden.
    """
    span = _span(order_id)
    ev = ProcessEvent
    cond = (ev.id < span.c.first_id) if before else (ev.id > span.c.last_id)
    order_by = (ev.instance_unit_id, ev.id.desc() if before else ev.id.asc())

    nearest = (
        select(ev.instance_unit_id, ev.order_id)
        .join(span, span.c.unit_id == ev.instance_unit_id)
        .where(cond, ev.order_id != order_id)
        .distinct(ev.instance_unit_id)
        .order_by(*order_by)
        .subquery()
    )
    rows = db.execute(
        select(nearest.c.order_id, func.count())
        .group_by(nearest.c.order_id)
        .order_by(func.count().desc(), nearest.c.order_id)
    ).all()
    return [(int(oid), int(n)) for oid, n in rows]


def neighbours(db: Session, order: Order) -> tuple[list[dict], list[dict]]:
    """Die Nachbar-Aufträge dieses Auftrags: ``(vorher, nachher)``.

    Ein Nachbar erscheint erst, **wenn es ihn wirklich gibt** – also sobald er
    freigegeben ist, denn vorher existiert er nicht (es gibt keinen gespeicherten
    Entwurf, §6.1) und schreibt darum auch nichts in den Log. Es braucht dafür keine
    Zusatzbedingung: die Abwesenheit im Log **ist** die Abwesenheit des Auftrags.

    Kein Vorgänger heisst: die Stücke sind hier entstanden. Kein Nachfolger heisst:
    hier ist die Journey (noch) zu Ende. Beides wird als leere Liste gemeldet, nicht
    als Platzhalter.
    """
    return (_resolve(db, _neighbour_counts(db, order.id, before=True)),
            _resolve(db, _neighbour_counts(db, order.id, before=False)))


def _resolve(db: Session, counts: list[tuple[int, int]]) -> list[dict]:
    """Interne Auftrags-ids → Objektnummer und Name, in **einer** Abfrage.

    Die interne ``id`` verlässt die Antwort nicht: nach aussen ist ein Auftrag seine
    Objektnummer. Ein Auftrag, den es nicht mehr gibt, fällt weg statt als Zeile mit
    leerem Namen zu erscheinen.
    """
    if not counts:
        return []
    ids = [oid for oid, _ in counts]
    known = {
        o.id: o for o in db.query(Order).filter(Order.id.in_(ids)).all()
    }
    out = []
    for oid, n in counts:
        o: Optional[Order] = known.get(oid)
        if o is None:
            continue
        out.append({"object_id": o.object_id, "name": o.name, "unit_count": n})
    return out
