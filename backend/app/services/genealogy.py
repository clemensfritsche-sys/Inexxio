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

**Und sie ist exakt, weil sie AUFGESCHRIEBEN wird.** Der ``verbaut``-Eintrag einer
Komponente trägt im Payload, **worin** sie verbaut wurde (``into``, gesetzt von
``services/consumption``). Das ist keine gespeicherte Kante Stück→Stück und kein Feld am
Datensatz: der Log hält fest, was passiert ist, und was passiert ist, war «dieses Stück
ging in jenes». Eine Spalte ``into_instance_id`` wäre die zweite Wahrheit daneben – und
sie würde bei einer Demontage rückwirkend geleert, womit die Vergangenheit des Getriebes
verschwände.

**Altbestand wird tolerant gelesen.** Einträge ohne ``into`` stammen aus der Zeit, als das
Modul seine Komponenten noch als Auftragszeilen bekam; für sie gilt weiterhin die gröbere
Aussage auf Auftragsebene («in diesem Auftrag verbaut»). Darum steht der Auftrag immer
dabei – bei einer exakten Zuordnung als Herkunft, bei einer alten als die Genauigkeit,
die es gibt.
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


def _consumed_in(db: Session, order_ids: set[int]) -> dict[int, list[tuple[int, Optional[int]]]]:
    """Je Auftrag die Stücke, die ihn als ``Verbaut`` verlassen haben – **und worin**.

    ``into`` ist die Nummer des Produkt-Stücks aus dem Log; ``None`` heisst «nicht
    aufgeschrieben» (Altbestand) und bedeutet dann die gröbere Aussage «in diesem
    Auftrag verbaut».
    """
    if not order_ids:
        return {}
    out: dict[int, list[tuple[int, Optional[int]]]] = {}
    for oid, uid, into in db.execute(
        select(
            ProcessEvent.order_id,
            ProcessEvent.instance_unit_id,
            ProcessEvent.payload["into"].astext,
        )
        .where(
            ProcessEvent.order_id.in_(order_ids),
            ProcessEvent.status_after == st.VERBAUT,
        )
        .distinct()
    ).all():
        out.setdefault(int(oid), []).append(
            (int(uid), int(into) if into is not None else None))
    return out


def _parts_in(consumed: dict[int, list[tuple[int, Optional[int]]]],
              order_id: int, unit_id: int) -> list[int]:
    """Die Teile **dieses** Stücks aus diesem Auftrag.

    Zwei Fälle, eine Regel: ein Eintrag mit ``into`` gehört genau dem genannten Stück;
    ein Eintrag ohne (Altbestand) gehört dem Auftrag, also jedem Erzeugnis darin. Ein
    Stück ist dabei nie sein eigenes Bauteil – hat es denselben Auftrag ebenfalls als
    «Verbaut» verlassen, war es dort Komponente und nicht Produkt.
    """
    return [
        uid for uid, into in consumed.get(order_id, ())
        if uid != unit_id and into in (None, unit_id)
    ]


def parts_counts(db: Session, unit_ids: list[int]) -> dict[int, int]:
    """**Wie viele Teile stecken in diesem Stück?** — für eine ganze Seite auf einmal.

    Zwei Abfragen, unabhängig von der Zahl der Stücke: die Liste der Nummern will nur
    wissen, **ob** es etwas aufzuklappen gibt. Ein Zähler je Zeile wäre bei einer
    5000er-Charge fünftausend Abfragen.
    """
    orders = _orders_of(db, unit_ids)
    consumed = _consumed_in(db, {o for s in orders.values() for o in s})
    return {
        uid: sum(len(_parts_in(consumed, oid, uid)) for oid in orders.get(uid, ()))
        for uid in unit_ids
    }


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
        for uid in sorted(_parts_in(consumed, oid, unit.id))
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

    Steht die Zuordnung im Log (``into``), ist es **genau ein** Stück. Fehlt sie
    (Altbestand), bleibt die alte, gröbere Antwort: was denselben Auftrag
    **weiterlaufend** verlassen hat – bei mehreren Erzeugnissen stehen sie alle da,
    statt dass eines geraten wird.
    """
    out: list[dict] = []
    for oid, into in sorted(_left_as_built(db, unit.id).items()):
        products = [into] if into is not None else _products_of(db, oid, exclude=unit.id)
        facts = _describe(db, products)
        out.append({
            "order_object_id": _order_numbers(db, {oid}).get(oid),
            "products": [facts[u] for u in products if u in facts],
        })
    return out


def _left_as_built(db: Session, unit_id: int) -> dict[int, Optional[int]]:
    """Die Aufträge, die dieses Stück als ``Verbaut`` verlassen hat — **und worin**."""
    return {
        int(oid): int(into) if into is not None else None
        for oid, into in db.execute(
            select(ProcessEvent.order_id, ProcessEvent.payload["into"].astext)
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
