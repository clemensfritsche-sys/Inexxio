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
from sqlalchemy.orm import Session, aliased

from ..domain import statuses as st
from ..models import Order, OrderUnit, ProcessEvent
from ..models.process_event import KIND_HANDOVER, KIND_START


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


# ---------------------------------------------------------------------------
# Die Struktur: übergeordneter Auftrag ↔ Abweichungsauftrag
# ---------------------------------------------------------------------------
#
# Die Journey oben beantwortet «wo war das Stück davor/danach» – eine Frage an die
# **Zeitachse**. Hier geht es um die **Struktur**: welche Aufträge greifen ineinander,
# weil einer dem anderen ein Stück mitten im Ablauf abgenommen hat.
#
# Beides aus derselben Quelle, aber an einem anderen Anker: die Journey misst von der
# Auftrags-Spanne aus, die Struktur vom **Auftragswechsel** aus. Der Unterschied ist
# nicht Geschmack — eine Abweichung, die ihr Stück zurückgibt, liegt *innerhalb* der
# Spanne ihres Eltern-Auftrags, und die Spannen-Rechnung fände sie darum nie.


def _adjacent(before: bool):
    """Das unmittelbar benachbarte Ereignis desselben Stücks — als Unterabfrage.

    Ein Sprung an die Nachbar-Zeile über den Index ``(instance_unit_id, id)``; ohne ihn
    wäre es ein Sortieren über die ganze Geschichte des Stücks.
    """
    ev = aliased(ProcessEvent)
    q = select(ev.order_id).where(ev.instance_unit_id == ProcessEvent.instance_unit_id)
    q = q.where(ev.id < ProcessEvent.id) if before else q.where(ev.id > ProcessEvent.id)
    return q.order_by(ev.id.desc() if before else ev.id).limit(1).scalar_subquery()


class Related:
    """Ein Nachbar-Auftrag **und die Zustandspunkte, an denen er ansetzt**.

    Ein **Zustandspunkt** ist die Stelle auf der Prozesslinie, an der ein Stück wartet –
    zwischen zwei Objekten, nicht in einem. Seine Identität steht in den Daten:
    ``order_units.current_step_id`` heisst «steht **vor** diesem Modul» (``None`` = nach
    dem Ende). Ein Punkt ist also «vor Modul X»; das Modul **benennt** ihn, es besitzt
    ihn nicht.

    Darum eine **Liste**: derselbe Abweichungsauftrag kann Stücke an zwei verschiedenen
    Stellen abgenommen haben. Ein einzelner Wert (früher ``min(step_id)``) hätte sich für
    eine davon entschieden und die andere verschwiegen – und die Linie zeigte dann auf
    einen Punkt, an dem gar nichts passiert ist.
    """

    def __init__(self, order_id: int):
        self.order_id = order_id
        #: ``[(at_step_id, Anzahl Stücke), …]`` – je Zustandspunkt eine Zeile.
        self.points: list[tuple[Optional[int], int]] = []

    @property
    def unit_count(self) -> int:
        return sum(n for _, n in self.points)


def _counts_from(db: Session, *, order_id: int, kind: str, status_before: Optional[str],
                 before: bool) -> list[Related]:
    """Nachbarn zu einem Anker-Ereignis, **je Zustandspunkt gezählt**.

    Der Punkt steht im Anker-Ereignis (``step_id`` = wo das Stück stand, als es wechselte);
    es gibt nichts nachzuschlagen und nichts abzuleiten.
    """
    anchor = select(
        ProcessEvent.instance_unit_id.label("unit_id"),
        ProcessEvent.step_id.label("step_id"),
        _adjacent(before).label("oid"),
    ).where(ProcessEvent.order_id == order_id, ProcessEvent.kind == kind)
    if status_before is not None:
        anchor = anchor.where(ProcessEvent.status_before == status_before)
    sub = anchor.subquery()
    rows = db.execute(
        select(sub.c.oid, sub.c.step_id, func.count())
        .where(sub.c.oid.isnot(None), sub.c.oid != order_id)
        .group_by(sub.c.oid, sub.c.step_id)
    ).all()

    found: dict[int, Related] = {}
    for oid, step_id, n in rows:
        rel = found.setdefault(int(oid), Related(int(oid)))
        rel.points.append((int(step_id) if step_id is not None else None, int(n)))
    # Der Hauptstrom zuerst; bei Gleichstand die id – willkürlich, aber stabil.
    return sorted(found.values(), key=lambda r: (-r.unit_count, r.order_id))


def parents(db: Session, order: Order) -> list[Related]:
    """Aus welchen **laufenden** Aufträgen hat dieser Auftrag Stücke übernommen?

    Anker ist sein eigener Start-Eintrag mit ``status_before = im_prozess`` – dieselbe
    Bedingung, die den Auftrag zur Abweichung macht (§2). Daneben steht dann der
    Auftrag, aus dem das Stück kam.

    Die Zustandspunkte werden hier **zusammengefasst**: sie liegen im Ablauf des *anderen*
    Auftrags und haben in diesem hier keine Stelle. Von einem übergeordneten Auftrag kommen
    die Stücke am **Start** herein, und der Start ist der Punkt.
    """
    out: list[Related] = []
    for rel in _counts_from(db, order_id=order.id, kind=KIND_START,
                            status_before=st.IM_PROZESS, before=True):
        merged = Related(rel.order_id)
        merged.points = [(None, rel.unit_count)]
        out.append(merged)
    return out


def deviations(db: Session, order: Order) -> list[Related]:
    """Welche Aufträge haben diesem hier Stücke **mitten im Ablauf** abgenommen?

    Anker ist sein eigener ``handover``-Eintrag; daneben steht der Auftrag, der das
    Stück aufgenommen hat. Gekappte Abweichungen erscheinen dabei genauso wie
    rückführende – sie sind ja passiert, und dass sie nichts zurückgeben, ist ihre
    Eigenschaft, nicht ihr Fehlen.
    """
    return _counts_from(db, order_id=order.id, kind=KIND_HANDOVER,
                        status_before=None, before=False)


def returning_to(db: Session, order: Order, order_ids: list[int]) -> set[int]:
    """Welche dieser Aufträge geben ihre Stücke an ``order`` zurück? — die Verbindung."""
    if not order_ids:
        return set()
    return {
        int(oid)
        for (oid,) in db.query(OrderUnit.order_id)
        .filter(
            OrderUnit.order_id.in_(order_ids),
            OrderUnit.return_to_order_id == order.id,
        )
        .distinct()
        .all()
    }


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
