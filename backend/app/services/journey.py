"""Die **Journey einer Einzelinstanz** – woher sie kam, wohin sie ging.

Ein Stück ist immer in **genau einem** Auftrag aktiv; hier wird die Aufteilung in Aufträge
wieder zusammengesetzt.

**Abgeleitet, nicht gepflegt** (keine Zeiger-Spalten): Quelle ist der **Ereignis-Log**
(``process.*``, Sicht ``process_log``, PROCESS_CORE.md §10.3); seine ``id`` ist die
Zeitachse::

    Vorgänger  = der Auftrag des letzten Ereignisses VOR dem ersten Ereignis
                 dieses Stücks in diesem Auftrag
    Nachfolger = der Auftrag des ersten Ereignisses NACH dem letzten

**Gruppiert, nicht aufgezählt**: je **Nachbar-Auftrag** die Anzahl Stücke (§8.3).
Zwei Abfragen je Auftrag (``DISTINCT ON`` über den Index ``(instance_unit_id, id)``).
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, aliased

from ..domain import statuses as st
from ..models import Order, OrderUnit, ProcessEvent
from ..models.process_event import KIND_START


def _walked_the_process(order_id: int):
    """Die Stücke, die diesen Auftrag **von vorne** durchlaufen — sein Subjekt.

    Zwei Eintrittspunkte (PROCESS_CORE.md §9.6): am **Start-Objekt** das Subjekt, an einem
    **Modul** Material zum Verbrauch – beide als ``start``, unterschieden an der Modul-``id``.
    Verbautes Material macht seinen Herkunftsauftrag nicht zum Vorgänger. Dieselbe Bedingung
    wie ``flow._tally`` (``step_id IS NULL``).
    """
    return (
        select(ProcessEvent.instance_unit_id)
        .where(
            ProcessEvent.order_id == order_id,
            ProcessEvent.kind == KIND_START,
            ProcessEvent.step_id.is_(None),
        )
        .scalar_subquery()
    )


def _span(order_id: int):
    """Je Stück: sein erstes und letztes Ereignis **in diesem Auftrag**.

    Die Klammer, ausserhalb derer der Nachbar liegt; nur über das **Subjekt**
    (``_walked_the_process``).
    """
    return (
        select(
            ProcessEvent.instance_unit_id.label("unit_id"),
            func.min(ProcessEvent.id).label("first_id"),
            func.max(ProcessEvent.id).label("last_id"),
        )
        .where(
            ProcessEvent.order_id == order_id,
            ProcessEvent.instance_unit_id.in_(_walked_the_process(order_id)),
        )
        .group_by(ProcessEvent.instance_unit_id)
        .subquery()
    )


def _neighbour_counts(db: Session, order_id: int, *, before: bool) -> list[tuple[int, int]]:
    """``[(Auftrag-id, Anzahl Stücke), …]`` – der direkte Nachbar je Stück, gezählt.

    ``DISTINCT ON (unit)`` mit passender Sortierung liefert je Stück genau **ein**
    Ereignis: das letzte davor bzw. das erste danach. Ein Stück ohne Nachbarn fällt heraus.
    """
    span = _span(order_id)
    ev = ProcessEvent
    cond = (ev.id < span.c.first_id) if before else (ev.id > span.c.last_id)
    order_by = (ev.instance_unit_id, ev.id.desc() if before else ev.id.asc())

    nearest = (
        select(ev.instance_unit_id, ev.order_id)
        .join(span, span.c.unit_id == ev.instance_unit_id)
        .where(cond, ev.order_id != order_id)
        .ext(distinct_on(ev.instance_unit_id))
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

    Ein Nachbar erscheint erst mit seiner Freigabe (§6.1). Kein Vorgänger: hier entstanden;
    kein Nachfolger: (noch) zu Ende – je eine leere Liste.
    """
    return (_resolve(db, _neighbour_counts(db, order.id, before=True)),
            _resolve(db, _neighbour_counts(db, order.id, before=False)))


# ---------------------------------------------------------------------------
# Die Struktur: übergeordneter Auftrag ↔ Abweichungsauftrag
# ---------------------------------------------------------------------------
#
# Die **Struktur** (wer hat wem ein Stück mitten im Ablauf abgenommen) misst vom
# **Auftragswechsel** aus, nicht von der Spanne: eine Abweichung, die ihr Stück zurückgibt,
# liegt innerhalb der Spanne ihres Eltern-Auftrags.


def _adjacent(before: bool):
    """Das unmittelbar benachbarte Ereignis desselben Stücks — als Unterabfrage.

    Ein Sprung an die Nachbar-Zeile über den Index ``(instance_unit_id, id)``.
    """
    ev = aliased(ProcessEvent)
    q = select(ev.order_id).where(ev.instance_unit_id == ProcessEvent.instance_unit_id)
    q = q.where(ev.id < ProcessEvent.id) if before else q.where(ev.id > ProcessEvent.id)
    return q.order_by(ev.id.desc() if before else ev.id).limit(1).scalar_subquery()


class Related:
    """Ein Nachbar-Auftrag **und die Zustandspunkte, an denen er ansetzt**.

    Ein **Zustandspunkt** ist «vor Modul X» (``order_units.current_step_id``, ``None`` =
    nach dem Ende). Eine **Liste**, weil derselbe Abweichungsauftrag Stücke an mehreren
    Stellen abgenommen haben kann.
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

    Der Punkt steht im Anker-Ereignis (``step_id`` = wo das Stück stand, als es wechselte).
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

    Die Zustandspunkte werden **zusammengefasst**: hier ist der Start der Punkt.
    """
    out: list[Related] = []
    for rel in _counts_from(db, order_id=order.id, kind=KIND_START,
                            status_before=st.IM_PROZESS, before=True):
        merged = Related(rel.order_id)
        merged.points = [(None, rel.unit_count)]
        out.append(merged)
    return out


# «Welche Aufträge haben mir Stücke abgenommen» beantwortet allein der Graph
# (``flow.Graph.neighbours``).


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

    Nach aussen ist ein Auftrag seine Objektnummer; einer, den es nicht mehr gibt, fällt weg.
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
