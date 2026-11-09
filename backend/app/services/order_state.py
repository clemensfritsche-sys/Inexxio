"""**Der Zustand eines Auftrags – nur Ableitungen, kein Schreiben.**

Wo ein Stück steht, wer es hält, was an einem Modul zu tun ist, worauf ein Modul wartet,
welcher Zustand ein Auftrag hat: alles gelesen aus den Zugehörigkeiten (``order_units``)
und dem Ereignis-Log, nichts gespeichert. Geschrieben wird in ``services/process``
(Laufzeit) und ``services/release`` (Freigabe).
"""

from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain import statuses as st
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderLine, OrderUnit, ProcessEvent,
    ProcessStep,
)
from ..models.process_event import (
    KIND_START,
)
from . import (
    sampling,
)
from .instances import unit_numbers
from ..domain.errors import Invalid, NotFound

#: Wie viele Werte höchstens in eine ``IN``-Liste kommen.
_CHUNK = 1000


def _chunks(values: list[int]) -> Iterable[list[int]]:
    for i in range(0, len(values), _CHUNK):
        yield values[i:i + _CHUNK]


def _open_of(unit_ids: list[int]) -> tuple:
    """**Die offene Zugehörigkeit dieser Stücke** – die Bedingung, an EINER Stelle."""
    return (OrderUnit.instance_unit_id.in_(unit_ids), OrderUnit.released_at.is_(None))


def held_by(db: Session, unit_ids: list[int]) -> dict[int, OrderUnit]:
    """Je Stück die **offene Zugehörigkeit**, falls es gerade in einem Auftrag läuft.

    Eindeutig dank der Exklusivität (§3, partieller Unique-Index); zugleich die
    **Verbindung**, aus der eine Abweichung entsteht (§3.2).
    """
    if not unit_ids:
        return {}
    rows: dict[int, OrderUnit] = {}
    for part in _chunks(list(unit_ids)):
        for m in (
            db.query(OrderUnit).filter(*_open_of(part)).all()
        ):
            rows[m.instance_unit_id] = m
    return rows


def holders(db: Session, unit_ids: list[int]) -> dict[int, int]:
    """Je Stück die **Objektnummer des Auftrags**, in dem es gerade läuft.

    Zweite Form von ``held_by``, für die Anzeige (wohin der Klick führt).
    """
    out: dict[int, int] = {}
    for part in _chunks(list(unit_ids)):
        for uid, oid in (
            db.query(OrderUnit.instance_unit_id, Order.object_id)
            .join(Order, Order.id == OrderUnit.order_id)
            .filter(*_open_of(part))
            .all()
        ):
            out[int(uid)] = int(oid)
    return out


def _units_at(db: Session, order: Order, step_id: Optional[int],
              *, instance_id: Optional[int] = None):
    """Was steht an diesem Zustandspunkt — wahlweise nur die Stücke **einer** Instanz.

    Scan-Regel: ein Vorgang arbeitet nur an den Stücken der verifizierten Instanz.
    """
    q = (
        db.query(OrderUnit, InstanceUnit)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(
            OrderUnit.order_id == order.id,
            OrderUnit.released_at.is_(None),
            OrderUnit.current_step_id == step_id,
        )
    )
    if instance_id is not None:
        q = q.filter(InstanceUnit.instance_id == instance_id)
    return q.order_by(OrderUnit.id).all()


def units_before(db: Session, order: Order, step: ProcessStep) -> list[InstanceUnit]:
    """**Was steht vor diesem Modul?** — die eine öffentliche Antwort.

    Für Stückliste (``consumption.needs``: Zahl und Ort) und Arbeitsliste (Instanzen).
    """
    return [u for _, u in _units_at(db, order, step.id)]


def step_work(db: Session, order: Order, step: ProcessStep) -> list[dict[str, Any]]:
    """**Was ist an diesem Modul zu tun — je Instanz?**

    Die Arbeitsliste: eine Zeile je Instanz, die davorsteht (ein Vorgang ist eine Instanz, §3):

    ``waiting``   wie viele Stücke dieser Instanz hier stehen
    ``sample``    wie viele davon **gezogen** sind (die übrigen laufen ohne Erfassung durch)
    ``held``      hat die letzte Erfassung **nicht bestanden**? Dann rückt hier nichts vor
    ``rest``      die ungeprüften Stücke **dieser** Instanz an **diesem** Modul

    ``rest`` (§4.1) umfasst nur die Stücke, die hier im Prozess stehen, nicht die übrige
    Charge. ``held`` ist die **letzte** Erfassung: ein neues Urteil zählt.
    """
    waiting = _units_at(db, order, step.id)
    if not waiting:
        return []
    units = [u for _, u in waiting]
    # **Gezogen** kommt aus dem Log, **erfasst** aus den Werten – zwei Fragen.
    drawn = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
    holds = held_units(db, order, step, [u.id for u in units])
    numbers = unit_numbers(db, units)

    instances = {
        i.id: i
        for i in db.query(Instance).filter(Instance.id.in_({u.instance_id for u in units})).all()
    }
    articles = {
        a.id: a.name
        for a in db.query(Article)
        .filter(Article.id.in_({i.article_id for i in instances.values()}))
        .all()
    } if instances else {}

    groups: dict[int, dict[str, Any]] = {}
    for unit in units:
        instance = instances[unit.instance_id]
        row = groups.setdefault(instance.id, {
            "instance_object_id": instance.object_id,
            "article_name": articles.get(instance.article_id),
            "waiting": 0, "sample": 0, "rest": 0, "held": False,
            "failed_numbers": [],
        })
        row["waiting"] += 1
        if unit.id in drawn:
            row["sample"] += 1
        else:
            row["rest"] += 1
        if unit.id in holds:
            row["held"] = True
            row["failed_numbers"].append(numbers[unit.id])
    return [groups[i] for i in sorted(groups)]


def _latest_captures(db: Session, order: Order, step: ProcessStep,
                     unit_ids: list[int]) -> dict[int, Any]:
    """Je Stück die **jüngste** Erfassung an diesem Modul. Ältere zählen nicht mehr."""
    from ..models import Capture

    out: dict[int, Any] = {}
    if not unit_ids:
        return out
    for part in _chunks(list(unit_ids)):
        for row in (
            db.query(Capture)
            .filter(
                Capture.order_id == order.id,
                Capture.step_id == step.id,
                Capture.instance_unit_id.in_(part),
            )
            .order_by(Capture.id)
            .all()
        ):
            out[row.instance_unit_id] = row   # die letzte gewinnt
    return out


def held_units(db: Session, order: Order, step: ProcessStep,
               unit_ids: list[int]) -> set[int]:
    """►►► **Welche Stücke hält dieses Modul fest?** ◄◄◄ — der **letzte Befund** zählt.

    Ein «nicht bestanden» hält an (§4.5). Der Halt ist eine **Auskunft**, keine Sperre –
    aufgehoben durch einen **neuen Befund** (erneutes Erfassen). Wer ``held`` anzeigt,
    zeigt es **neben** dem Weg nach vorn, nicht anstelle davon.
    """
    if not unit_ids:
        return set()
    latest = _latest_captures(db, order, step, unit_ids)
    return {u for u, cap in latest.items() if cap is not None and cap.result == "failed"}


def held_numbers(db: Session, order: Order, step: ProcessStep, *,
                 instance_object_id: int, group: str) -> list[str]:
    """Die Nummern **einer Gruppe dieser Instanz an diesem Modul** — erst auf Klick.

    Zwei Rollen, eine Frage – «welche Stücke, und wozu»:

    ``sample``   die **gezogenen**: für sie ist je ein Wertesatz zu erfassen (§9.3)
    ``failed``   die durchgefallenen – Vorauswahl für einen Abweichungsauftrag

    ``failed`` geht in einen gewöhnlichen Auftragsentwurf (§4.1). Die 100 %-Kontrolle ist
    ein Abweichungsauftrag mit der Stichprobe «alle». **Erst auf Klick**: die Zahlen in
    ``step_work`` genügen für die Vorschau.
    """
    instance = (
        db.query(Instance).filter(Instance.object_id == instance_object_id).first()
    )
    if instance is None:
        raise NotFound(f"Instanz {instance_object_id} gibt es nicht.")
    waiting = _units_at(db, order, step.id, instance_id=instance.id)
    units = [u for _, u in waiting]
    if group == "failed":
        latest = _latest_captures(db, order, step, [u.id for u in units])
        chosen = [u for u in units if (latest.get(u.id) is not None
                                       and latest[u.id].result == "failed")]
    elif group == "sample":
        drawn = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
        chosen = [u for u in units if u.id in drawn]
    else:
        raise Invalid(f"«{group}» ist keine Gruppe – erlaubt: sample, failed.")
    numbers = unit_numbers(db, chosen)
    return [numbers[u.id] for u in chosen]


def _order_number(db: Session, order_id: int) -> Optional[int]:
    """Die Objektnummer eines Auftrags – für Meldungen, die ihn nennen."""
    return db.query(Order.object_id).filter(Order.id == order_id).scalar()


def steps_of(db: Session, order: Order) -> list[ProcessStep]:
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id)
        .order_by(ProcessStep.position)
        .all()
    )


def lines_of(db: Session, order: Order) -> list[OrderLine]:
    return (
        db.query(OrderLine)
        .filter(OrderLine.order_id == order.id)
        .order_by(OrderLine.position)
        .all()
    )


def units_page(db: Session, order: Order, *, membership_ids: list[int],
               limit: int, offset: int) -> tuple[list[tuple[OrderUnit, InstanceUnit]], int]:
    """Die einzelnen Stücke einer Position – auf Abruf und in Seiten.

    **Welche** Stücke, entscheidet die Zuordnung im Prozessbild (``flow.units_on``); sie
    kommen als Zeilen-ids herein.
    """
    if not membership_ids:
        return [], 0
    q = (
        db.query(OrderUnit, InstanceUnit)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(OrderUnit.order_id == order.id, OrderUnit.id.in_(membership_ids))
    )
    total = q.count()
    return q.order_by(OrderUnit.id).limit(limit).offset(offset).all(), total


# ---------------------------------------------------------------------------
# Der Auftragsstatus — ABGELEITET, an genau einer Stelle
# ---------------------------------------------------------------------------
#
# Drei Zustände, keiner gesetzt: abgeleitet aus seinen Einzelinstanzen. «Freigegeben» ist
# eine Aktion, kein Zustand.
#
#   Im Prozess      es ist noch etwas unterwegs
#   Abgeschlossen   mindestens ein Stück hat das Ziel erreicht
#   Abgebrochen     nichts kann das Ziel mehr erreichen
#
# Zwei Formen derselben Regel, nebeneinander im selben Modul: ``order_status`` für einen
# geladenen Auftrag, ``order_statuses`` für den Feed (EINE Abfrage, kein N+1).

def _derive(arrived: int, alive: int, lent: int) -> str:
    """Die Regel selbst — aus drei Zahlen. Alles andere zählt nur.

    **«Abgeschlossen» = den definierten Weg zu Ende gegangen**, auch über einen Ausgang
    (§4.6). **Was noch unterwegs ist, gewinnt.** ``lent`` = einer Abweichung geliehen und
    **kommt zurück** (§3.2); gekappte Verbindungen zählen nicht.
    """
    if alive or lent:
        return st.IM_PROZESS
    if arrived:
        return st.ABGESCHLOSSEN
    # Nichts angekommen und nichts mehr unterwegs: das Ziel ist unerreichbar.
    return st.ABGEBROCHEN


def order_status(db: Session, order: Order) -> str:
    """Der Zustand **eines** Auftrags."""
    return order_statuses(db, [order.id]).get(order.id, st.IM_PROZESS)


def _loans_toward(db: Session, order_ids: list[int]) -> list[tuple[int, int, list[int]]]:
    """►►► **Die Rückführungs-Kette – gelesen an genau einer Stelle** (§3.5). ◄◄◄

    Je laufender Ausleihe, deren Stück aus einem der gefragten Aufträge stammt:
    ``(Stück, Auftrag, in dem es jetzt steckt, [Aufträge, in die es zurückkehrt])`` – die
    Liste von unten nach oben. Leiht A an B und B weiter an C, kehrt das Stück aus C nach
    B **und** nach A zurück, nur eine Stufe tiefer. Gefolgt wird ``return_to_order_id``,
    der Eigenschaft der **Verbindung**; eine gekappte Ausleihe endet die Kette, und das ist
    die Aussage «kommt nie zurück».

    Nur Stücke, die einen der Aufträge **verlassen** haben (geschlossen, mit Zustandspunkt).
    Leser: ``waiting_counts`` und ``returning_home``.
    """
    if not order_ids:
        return []
    left = (
        select(OrderUnit.instance_unit_id)
        .where(OrderUnit.order_id.in_(order_ids), OrderUnit.released_at.isnot(None),
               OrderUnit.current_step_id.isnot(None))
    )
    loans = db.query(OrderUnit.instance_unit_id, OrderUnit.order_id,
                     OrderUnit.return_to_order_id).filter(
        OrderUnit.released_at.is_(None), OrderUnit.return_to_order_id.isnot(None),
        OrderUnit.instance_unit_id.in_(left)).all()
    if not loans:
        return []
    upward: dict[tuple[int, int], int] = {
        (int(o), int(u)): int(r)
        for u, o, r in db.query(OrderUnit.instance_unit_id, OrderUnit.order_id,
                                OrderUnit.return_to_order_id).filter(
            OrderUnit.instance_unit_id.in_({u for u, _, _ in loans}),
            OrderUnit.return_to_order_id.isnot(None)).all()
    }
    out: list[tuple[int, int, list[int]]] = []
    for unit, holder, target in loans:
        homes: list[int] = []
        oid: Optional[int] = int(target)
        while oid is not None and oid not in homes:
            homes.append(oid)
            oid = upward.get((oid, int(unit)))
        out.append((int(unit), int(holder), homes))
    return out


def waiting_counts(db: Session, order_ids: list[int]) -> dict[int, int]:
    """Wie viele Stücke sind gerade **ausgeliehen und kommen zurück**? — je Auftrag.

    Über die ganze Kette (``_loans_toward``); eine gekappte Stufe beendet sie (§3.4).
    """
    wanted = set(order_ids)
    out: dict[int, int] = {}
    for _unit, _holder, homes in _loans_toward(db, list(wanted)):
        for oid in homes:
            if oid in wanted:
                out[oid] = out.get(oid, 0) + 1
    return out


def _away_points(db: Session, order: Order) -> dict[int, int]:
    """Je ausgeschertem Stück der Zustandspunkt, an dem es diesen Auftrag verlassen hat.

    Es ist das ``current_step_id`` der geschlossenen Zeile (§3.3).
    """
    return {
        int(u): int(s)
        for u, s in db.query(OrderUnit.instance_unit_id, OrderUnit.current_step_id).filter(
            OrderUnit.order_id == order.id,
            OrderUnit.released_at.isnot(None),
            OrderUnit.current_step_id.isnot(None),
        ).all()
    }


def returning_home(db: Session, order: Order) -> dict[int, int]:
    """Welche ausgescherten Stücke kehren **hierher** zurück? — ``{Stück: Halter-Auftrag}``.

    Dieselbe Kette wie beim Auftragsstatus (``_loans_toward``), von diesem Auftrag aus
    gelesen. Zwei Fragen lesen sie: welches Modul **gesperrt** ist (``pending_returns``)
    und wo im Bild eine **Rückführungslinie** hingehört (``services/flow``).
    """
    return {unit: holder for unit, holder, homes in _loans_toward(db, [order.id])
            if order.id in homes}


def pending_returns(db: Session, order: Order) -> dict[int, list[int]]:
    """**Worauf wartet welches Modul?** — Modul-id → Objektnummern der Abweichungen.

    Solange ein ausgeschertes Stück **zurückkommt**, läuft das Modul dahinter nicht.
    **Gekappte Ausleihen sperren nichts** (§3.4). **Die Kette zählt** (§3.5); genannt wird
    der Auftrag, in dem das Stück **jetzt** steckt. Abgeleitet, kein Sperr-Flag.
    """
    coming = returning_home(db, order)
    if not coming:
        return {}
    at = _away_points(db, order)

    found: dict[int, set[int]] = {}
    for unit_id, holder_order_id in coming.items():
        step_id = at.get(unit_id)
        if step_id is None:
            continue
        found.setdefault(int(step_id), set()).add(holder_order_id)

    ids = {oid for group in found.values() for oid in group}
    numbers = {
        o.id: o.object_id
        for o in db.query(Order).filter(Order.id.in_(ids)).all()
    }
    return {
        step_id: sorted(numbers[oid] for oid in group if oid in numbers)
        for step_id, group in found.items()
    }


def order_statuses(db: Session, order_ids: list[int]) -> dict[int, str]:
    """Der Zustand **vieler** Aufträge – für den Feed, ohne N+1.

    «Unterwegs» heisst: die Zugehörigkeit ist offen. «Abgebrochen» entsteht, wenn eine
    Abweichung **alle** Stücke nimmt und die Rückführung gekappt ist (Matrix S57 · S58 · S59).

    «Angekommen» heisst: die Zugehörigkeit ist geschlossen **und** das Stück steht vor
    keinem Modul mehr (auch Ausscheren schliesst die Zeile).
    """
    if not order_ids:
        return {}
    rows = (
        db.query(
            OrderUnit.order_id,
            func.count(OrderUnit.id).filter(
                OrderUnit.released_at.isnot(None), OrderUnit.current_step_id.is_(None)
            ).label("arrived"),
            func.count(OrderUnit.id).filter(OrderUnit.released_at.is_(None)).label("alive"),
        )
        .filter(OrderUnit.order_id.in_(order_ids))
        .group_by(OrderUnit.order_id)
        .all()
    )
    lent = waiting_counts(db, order_ids)
    found = {
        int(oid): _derive(int(a), int(al), lent.get(int(oid), 0))
        for oid, a, al in rows
    }
    # Ohne Zugehörigkeit (kann es nicht geben) ist ein Auftrag kein «Im Prozess».
    return {oid: found.get(oid, st.ABGEBROCHEN) for oid in order_ids}


def deviation_flags(db: Session, order_ids: list[int]) -> dict[int, bool]:
    """Welche dieser Aufträge sind **Abweichungen**? — die Frage aus §2.

    **Ein Auftrag ist eine Abweichung, wenn sein Start vom Regelstart abwich.** Regulär
    beginnt, was **ruht** (``statuses.REGULAR_STARTS``: *Freigegeben* bei uns, *Verkauft* bei
    der Partei). Alles andere ist ein Zugriff auf Material, das gerade nicht zur Verfügung
    stand – einem Auftrag entzogen, gesperrt, verbaut – und genau das ist
    dokumentationspflichtig. Eine Retoure ist keine Abweichung: sie ist eine Eigentumsfrage
    und steht in ihrer Zahlung («geht an uns»).

    Die Regel nennt keinen Status (ein künftiger Zustand ist automatisch eine Abweichung).
    **Kein Feld**, kein Auftragstyp: «Abweichung» ist eine Auskunft.
    """
    if not order_ids:
        return {oid: False for oid in order_ids}
    hits = {
        int(oid)
        for (oid,) in db.query(ProcessEvent.order_id)
        .filter(
            ProcessEvent.order_id.in_(order_ids),
            ProcessEvent.kind == KIND_START,
            ProcessEvent.status_before.notin_(st.REGULAR_STARTS),
        )
        .distinct()
        .all()
    }
    return {oid: oid in hits for oid in order_ids}


def active_step_id(db: Session, order: Order) -> Optional[int]:
    """Welches Modul ist **jetzt** dran? Das erste, vor dem noch ein Stück steht.

    Abgeleitet, nicht gespeichert.
    """
    waiting = {
        int(sid) for (sid,) in db.query(OrderUnit.current_step_id).filter(
            OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
            OrderUnit.current_step_id.isnot(None)).distinct().all()
    }
    if not waiting:
        return None
    for step in steps_of(db, order):
        if step.id in waiting:
            return step.id
    return None


def events_page(db: Session, order: Order, *, limit: int) -> tuple[list[ProcessEvent], int]:
    """Die Historie – die **neuesten** ``limit`` Einträge und wie viele es insgesamt sind.

    Der Deckel wird ausgewiesen: die Zahl daneben sagt, dass es mehr gibt.
    """
    total = (
        db.query(func.count(ProcessEvent.id))
        .filter(ProcessEvent.order_id == order.id)
        .scalar() or 0
    )
    rows = (
        db.query(ProcessEvent)
        .filter(ProcessEvent.order_id == order.id)
        .order_by(ProcessEvent.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows)), int(total)


def started_at(db: Session, order: Order, unit_ids: list[int]) -> dict[int, datetime]:
    """**Wann hat dieses Stück das Start-Objekt passiert?** — je Stück, aus dem Log.

    Keine Spalte daneben: die Wahrheit ist der Log (§7.2). Gemeint ist der Eintritt in
    **diesen** Auftrag.
    """
    if not unit_ids:
        return {}
    out: dict[int, datetime] = {}
    for part in _chunks(list(unit_ids)):
        for uid, at in (
            db.query(ProcessEvent.instance_unit_id, func.min(ProcessEvent.created_at))
            .filter(
                ProcessEvent.order_id == order.id,
                ProcessEvent.kind == KIND_START,
                ProcessEvent.instance_unit_id.in_(part),
            )
            .group_by(ProcessEvent.instance_unit_id)
            .all()
        ):
            out[int(uid)] = at
    return out
