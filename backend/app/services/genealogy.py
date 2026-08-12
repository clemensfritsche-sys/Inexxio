"""**Woraus besteht ein Stück – und worin steckt es?** Beides aus dem Log abgeleitet.

Es gibt hier **kein Feld, keine Tabelle und keine Beziehung**. Die Stückliste ist eine
Frage an den Ereignis-Log, und die Antwort lautet:

    Die Stückliste eines Stücks = alle Einzelinstanzen, die einen Auftrag, an dem dieses
    Stück beteiligt war, mit dem Zustand ``Verbaut`` verlassen haben.

**Warum aus dem Log und nicht aus dem heutigen Zustand.** Ein verbautes Stück ist
**aufhebbar** (``statuses.VERBAUT``): eine Demontage holt es zurück, und es steht danach
wieder auf ``Freigegeben``. Läse die Stückliste den Zustand, verschwände das Zahnrad damit
**rückwirkend** aus der Vergangenheit des Getriebes – und ein Nachweis, der sich
nachträglich ändert, ist keiner. Der Log ist append-only; was verbaut *war*, bleibt verbaut
gewesen. Ob es noch drinsteckt, ist eine **zweite** Frage, und die beantwortet der
heutige Zustand (``still_in``).

Das ist dieselbe Regel wie im Prozessbild (§8.1a): *eine Ansicht der Vergangenheit darf
keine bewegliche Grösse lesen.*

**Die Grenze, ehrlich benannt.** Die Zuordnung läuft über den **Auftrag**, nicht über eine
gespeicherte Kante Stück→Stück. Sie ist damit exakt, solange ein Auftrag **ein** Erzeugnis
weiterführt – der Normalfall («eine Maschine je Auftrag»). Werden in **einem** Auftrag zwei
Maschinen montiert, ist «welche Schraube in welcher» nicht mehr herleitbar; die Aussage
bleibt auf Auftragsebene wahr und nennt darum immer den Auftrag mit. Eine gespeicherte
Kante wäre die Alternative – und genau die soll es nicht geben, weil sie eine zweite
Wahrheit neben dem Log wäre.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain import statuses as st
from ..models import Article, Instance, InstanceUnit, Order, ProcessEvent


def _orders_of(db: Session, unit_ids: list[int]) -> dict[int, set[int]]:
    """Je Stück die Aufträge, an denen es beteiligt war — aus dem Log."""
    if not unit_ids:
        return {}
    out: dict[int, set[int]] = {}
    for uid, oid in db.execute(
        select(ProcessEvent.instance_unit_id, ProcessEvent.order_id)
        .where(ProcessEvent.instance_unit_id.in_(unit_ids))
        .distinct()
    ).all():
        out.setdefault(int(uid), set()).add(int(oid))
    return out


def _consumed_in(db: Session, order_ids: set[int]) -> dict[int, list[int]]:
    """Je Auftrag die Stücke, die ihn als ``Verbaut`` verlassen haben."""
    if not order_ids:
        return {}
    out: dict[int, list[int]] = {}
    for oid, uid in db.execute(
        select(ProcessEvent.order_id, ProcessEvent.instance_unit_id)
        .where(
            ProcessEvent.order_id.in_(order_ids),
            ProcessEvent.status_after == st.VERBAUT,
        )
        .distinct()
    ).all():
        out.setdefault(int(oid), []).append(int(uid))
    return out


def parts_counts(db: Session, unit_ids: list[int]) -> dict[int, int]:
    """**Wie viele Teile stecken in diesem Stück?** — für eine ganze Seite auf einmal.

    Zwei Abfragen, unabhängig von der Zahl der Stücke: die Liste der Nummern will nur
    wissen, **ob** es etwas aufzuklappen gibt. Ein Zähler je Zeile wäre bei einer
    5000er-Charge fünftausend Abfragen.
    """
    orders = _orders_of(db, unit_ids)
    consumed = _consumed_in(db, {o for s in orders.values() for o in s})
    out: dict[int, int] = {}
    for uid in unit_ids:
        n = 0
        for oid in orders.get(uid, ()):
            # Ein Stück ist nie sein eigenes Bauteil: hat es denselben Auftrag ebenfalls
            # als «Verbaut» verlassen, war es dort Komponente und nicht Produkt.
            n += len([u for u in consumed.get(oid, ()) if u != uid])
        out[uid] = n
    return out


def _describe(db: Session, unit_ids: list[int]) -> dict[int, dict]:
    """Nummer · Artikel · heutiger Zustand je Stück — eine Abfrage über drei Tabellen."""
    if not unit_ids:
        return {}
    rows = db.execute(
        select(
            InstanceUnit.id, InstanceUnit.suffix, InstanceUnit.status,
            Instance.object_id, Article.name, Article.object_id,
        )
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .join(Article, Article.id == Instance.article_id)
        .where(InstanceUnit.id.in_(unit_ids))
    ).all()
    return {
        int(uid): {
            "unit_id": int(uid),
            "number": f"{int(inst_nr)}-{int(suffix)}",
            "status": status,
            "article_name": name,
            "article_object_id": int(art_nr) if art_nr else None,
        }
        for uid, suffix, status, inst_nr, name, art_nr in rows
    }


def parts_of(db: Session, unit: InstanceUnit) -> list[dict]:
    """**Die Stückliste** – was in diesem Stück steckt, je Eintrag mit seinem Auftrag.

    ``still_in`` sagt, ob das Teil **heute noch** drin ist: der Log sagt «wurde verbaut»,
    der Zustand sagt «ist es noch». Ein ausgebautes Teil bleibt darum in der Liste und
    wird als ausgebaut gezeigt – die Vergangenheit wird nicht gelöscht, sie bekommt eine
    Fortsetzung.
    """
    orders = _orders_of(db, [unit.id]).get(unit.id, set())
    consumed = _consumed_in(db, orders)
    pairs = [
        (oid, uid)
        for oid in sorted(orders)
        for uid in sorted(consumed.get(oid, ()))
        if uid != unit.id
    ]
    facts = _describe(db, [uid for _, uid in pairs])
    numbers = _order_numbers(db, {oid for oid, _ in pairs})
    return [
        {**facts[uid], "order_object_id": numbers.get(oid),
         "still_in": facts[uid]["status"] == st.VERBAUT}
        for oid, uid in pairs if uid in facts
    ]


def built_into(db: Session, unit: InstanceUnit) -> list[dict]:
    """**Worin steckt dieses Stück?** – die Gegenrichtung der Stückliste.

    Genannt wird, was denselben Auftrag **weiterlaufend** verlassen hat: das Erzeugnis.
    Bei mehreren ist die Zuordnung nicht mehr eindeutig (siehe Modul-Docstring) – dann
    stehen sie alle da, statt dass eines geraten wird.
    """
    out: list[dict] = []
    for oid in sorted(_left_as_built(db, unit.id)):
        products = _products_of(db, oid, exclude=unit.id)
        facts = _describe(db, products)
        out.append({
            "order_object_id": _order_numbers(db, {oid}).get(oid),
            "products": [facts[u] for u in products if u in facts],
        })
    return out


def _left_as_built(db: Session, unit_id: int) -> set[int]:
    """Die Aufträge, die dieses Stück als ``Verbaut`` verlassen hat."""
    return {
        int(oid)
        for (oid,) in db.execute(
            select(ProcessEvent.order_id)
            .where(
                ProcessEvent.instance_unit_id == unit_id,
                ProcessEvent.status_after == st.VERBAUT,
            )
            .distinct()
        ).all()
    }


def _products_of(db: Session, order_id: int, *, exclude: int) -> list[int]:
    """Die Stücke, die diesen Auftrag **weiterlaufend** verlassen haben (das Erzeugnis).

    «Weiterlaufend» heisst: ihr letzter Eintrag ist das Ende-Objekt. Wer über ein Modul
    hinausging, ist Komponente oder Ausschuss und kein Produkt.
    """
    last = (
        select(
            ProcessEvent.instance_unit_id.label("unit"),
            func.max(ProcessEvent.id).label("last_id"),
        )
        .where(ProcessEvent.order_id == order_id)
        .group_by(ProcessEvent.instance_unit_id)
        .subquery()
    )
    return sorted(
        int(u)
        for (u,) in db.execute(
            select(ProcessEvent.instance_unit_id)
            .join(last, ProcessEvent.id == last.c.last_id)
            .where(ProcessEvent.kind == "end", ProcessEvent.instance_unit_id != exclude)
        ).all()
    )


def _order_numbers(db: Session, order_ids: set[int]) -> dict[int, Optional[int]]:
    if not order_ids:
        return {}
    return {
        int(o.id): int(o.object_id)
        for o in db.query(Order).filter(Order.id.in_(order_ids)).all()
    }
