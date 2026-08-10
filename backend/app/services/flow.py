"""Der **Prozess-Graph** — Knoten, Kanten, Positionen. Abgeleitet aus dem Ereignis-Log.

Das Bild eines Auftrags entstand bisher im Browser: die Oberfläche baute die Knotenfolge
aus Schritten und Stück-Gruppen zusammen und leitete daraus ab, wie weit die Linie
kräftig läuft. Das ist **Prozesslogik im Frontend**, und sie war aus zwei Gründen falsch:

* Sie las den **aktuellen Zustand** («wo stehen aktive Stücke») statt den **Log** («was ist
  passiert»). Sobald ein Stück eine Stelle verliess, verschwand sie – mitsamt der
  Abzweigung, die dort einmal stattgefunden hatte.
* Sie war eine **zweite Wahrheit** neben dem Server. Zwei Ableitungen derselben Sache
  laufen auseinander; welche stimmt, sieht man erst am Bildschirm.

Darum liefert der Server das Bild als **Graph**, und das Frontend layoutet und zeichnet
ihn nur noch. Die Begriffe sind abschliessend – mehr gibt es nicht:

======================  ====================================================
**Knoten**              Prozessobjekte: ``start`` · ``module`` · ``end``,
                        dazu ``fork`` (Abzweigepunkt) und ``join``
                        (Rückführpunkt).
**Kante**               Verbindung zwischen genau zwei Knoten.
**Position**            Wo ein Stück steht — **immer eine Kante**, nie ein
                        Knoten und nie ein diffuser Zwischenraum.
**Kantenzustand**       ``walked`` — kräftig, wenn Material die Kante laut
                        Log erreicht hat. Sonst Haarlinie. Kein dritter Wert.
======================  ====================================================

## Warum fork und join eigene Knoten sind

Ein **Zustandspunkt** heisst «vor Modul X» (PROCESS_CORE.md §12.4) – und genau dorthin
kehrt ein ausgeschertes Stück zurück. Solange das *ein* Knoten war, standen das Stück,
das geblieben ist, und das Stück, das zurückkam, an derselben Stelle im Bild: man sah der
Zeichnung nicht an, dass eines von beiden gerade eine Runde gedreht hat.

Als **zwei** Knoten fällt die Frage weg, statt beantwortet zu werden::

        │
    ● fork@X ──────────────▶  Abweichungsauftrag
        │  (wer blieb)                │
    ● join@X ◀────────────────────────┘
        │  (wer zurückkam)
    [ Modul X ]

Beide Punkte heissen weiterhin «vor Modul X»; fachlich ist es **ein** Zustandspunkt, und
``order_units.current_step_id`` bleibt seine eine Identität. Die Teilung ist die
Darstellung dieser Identität in der Zeit: davor und danach.

## Warum der Log und nicht der Zustand

Ein Handover-Eintrag verschwindet nie. Eine Abzweigung, die einmal passiert ist, ist
passiert – auch wenn das Stück längst zurück und weitergezogen ist. Alle Zähler hier sind
darum **Zeilenzahlen im Log**: sie können nur wachsen. Daraus folgt die Invariante «eine
einmal kräftige Kante wird nie wieder schwach» **von selbst**, statt sie zu bewachen.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import process
from ..models import InstanceUnit, Order, OrderUnit, ProcessEvent, ProcessStep
from ..models.process_event import (
    KIND_END, KIND_HANDOVER, KIND_RETURN, KIND_START, KIND_STEP,
)

# --- Knotenarten ------------------------------------------------------------
#: Das Start-Objekt. Genau einer je Auftrag.
NODE_START = "start"
#: Ein Prozessschrittmodul.
NODE_MODULE = "module"
#: Das Ende-Objekt. Genau einer je Auftrag.
NODE_END = "end"
#: **Abzweigepunkt** – hier hat mindestens ein Stück den Auftrag verlassen.
NODE_FORK = "fork"
#: **Rückführpunkt** – hierher kehrt mindestens ein Stück zurück (oder ist zurück).
NODE_JOIN = "join"

# --- Kantenarten ------------------------------------------------------------
#: Die Hauptachse dieses Auftrags: von Knoten zu Knoten, senkrecht.
EDGE_AXIS = "axis"
#: Hinaus in einen anderen Auftrag (``to`` zeigt auf dessen **Start**).
EDGE_OUT = "out"
#: Zurück aus einem anderen Auftrag (``frm`` zeigt auf dessen **Ende**).
EDGE_BACK = "back"

#: Ein Knoten in einem **anderen** Auftrag. Das Frontend löst ihn auf die Spalte auf, in
#: der dieser Auftrag steht – steht er nicht im Bild, wird die Kante nicht gezeichnet.
#: Damit braucht keine Seite zu wissen, welche Nachbarn gerade sichtbar sind.
def order_ref(object_id: int) -> str:
    return f"order:{object_id}"


def fork_id(at: Optional[int]) -> str:
    return f"fork:{at if at is not None else 'end'}"


def join_id(at: Optional[int]) -> str:
    return f"join:{at if at is not None else 'end'}"


def module_id(step_id: int) -> str:
    return f"module:{step_id}"


@dataclass
class Node:
    id: str
    kind: str
    #: Bei ``module`` die eigene ``step_id``; bei ``fork``/``join`` das Modul, **vor** dem
    #: der Punkt liegt (er heisst danach, er gehört ihm nicht).
    #:
    #: **Der Knoten trägt keinen Namen und keine Farbe.** Was in einem Modul steht, sagt
    #: seine Zeile in ``steps`` – hier steht, *wo* es steht. Beides am Knoten wäre
    #: dieselbe Angabe an zwei Stellen, und die eine liefe irgendwann der anderen davon.
    at: Optional[int] = None


@dataclass
class Placed:
    """Stücke an **einer** Position – gezählt, nicht aufgezählt.

    ``at_step_id``/``active`` sind der Schlüssel, mit dem die Oberfläche die einzelnen
    Nummern nachlädt (``GET …/units``). Sie stehen hier, weil eine Position ohne ihn
    zwar hübsch aussieht, sich aber nicht aufklappen lässt.
    """

    status: str
    count: int
    active: bool
    at_step_id: Optional[int] = None


@dataclass
class Edge:
    id: str
    frm: str
    #: ``None`` bei der Kante hinter dem Ende: dort ist der Prozess zu Ende, es gibt
    #: keinen nächsten Knoten. Die angekommenen Stücke stehen trotzdem irgendwo – und
    #: «irgendwo» ist diese Kante.
    to: Optional[str]
    kind: str = EDGE_AXIS
    walked: bool = False
    units: list[Placed] = field(default_factory=list)


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    #: Verletzte Invarianten. Nicht leer heisst: das Bild ist **nicht** verlässlich, und
    #: die Oberfläche sagt das, statt eine falsche Zeichnung anzubieten.
    problems: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Der Log — die einzige Quelle für «was ist passiert»
# ---------------------------------------------------------------------------

@dataclass
class _Tally:
    """Was der Log über diesen Auftrag sagt, in Zahlen."""

    #: Wie viele Stücke haben das Start-Objekt passiert.
    started: int = 0
    #: Je Modul: wie viele Stücke haben es passiert.
    passed: dict[int, int] = field(default_factory=dict)
    #: Wie viele Stücke haben das Ende-Objekt passiert.
    ended: int = 0
    #: Je Zustandspunkt und Ziel-Auftrag: wie viele Stücke sind ausgeschert.
    out: dict[tuple[Optional[int], int], int] = field(default_factory=dict)
    #: Je Zustandspunkt und Herkunfts-Auftrag: wie viele Stücke sind zurückgekehrt.
    back: dict[tuple[Optional[int], int], int] = field(default_factory=dict)


def _tally(db: Session, order_id: int) -> _Tally:
    """**Eine** Abfrage über den Log dieses Auftrags, gruppiert.

    Gezählt werden Zeilen, nicht Stücke: ein Stück kann eine Stelle mehrfach verlassen
    (Abweichung der Abweichung). Für die Frage «ist hier je etwas passiert» genügt das,
    und es ist die Zahl, die nur wachsen kann.
    """
    rows = db.execute(
        select(
            ProcessEvent.kind,
            ProcessEvent.step_id,
            ProcessEvent.payload["to_order"].astext,
            ProcessEvent.payload["from_order"].astext,
            func.count(),
        )
        .where(ProcessEvent.order_id == order_id)
        .group_by(
            ProcessEvent.kind,
            ProcessEvent.step_id,
            ProcessEvent.payload["to_order"].astext,
            ProcessEvent.payload["from_order"].astext,
        )
    ).all()

    t = _Tally()
    for kind, step_id, to_order, from_order, n in rows:
        n = int(n)
        at = int(step_id) if step_id is not None else None
        if kind == KIND_START:
            t.started += n
        elif kind == KIND_STEP and at is not None:
            t.passed[at] = t.passed.get(at, 0) + n
        elif kind == KIND_END:
            t.ended += n
        elif kind == KIND_HANDOVER and to_order is not None:
            key = (at, int(to_order))
            t.out[key] = t.out.get(key, 0) + n
        elif kind == KIND_RETURN and from_order is not None:
            key = (at, int(from_order))
            t.back[key] = t.back.get(key, 0) + n
    return t


# ---------------------------------------------------------------------------
# Die Positionen — jede Zugehörigkeit steht auf genau einer Kante
# ---------------------------------------------------------------------------

@dataclass
class _Live:
    """Wo die Stücke **jetzt** stehen. Der Log sagt, was passiert ist; das hier, wo es steht."""

    #: ``(step_id, status) → Anzahl`` – anwesend und noch nicht zurückgekehrt.
    stayed: dict[tuple[Optional[int], str], int] = field(default_factory=dict)
    #: ``(step_id, status) → Anzahl`` – anwesend, aus einer Abweichung zurückgekehrt.
    returned: dict[tuple[Optional[int], str], int] = field(default_factory=dict)
    #: ``(step_id, Ziel-Objektnummer, status) → Anzahl`` – ausgeschert, gerade woanders.
    away: dict[tuple[Optional[int], int, str], int] = field(default_factory=dict)
    #: ``status → Anzahl`` – angekommen, hinter dem Ende.
    arrived: dict[str, int] = field(default_factory=dict)
    #: Zustandspunkte mit einer **offenen** Rückführung: ``(step_id, Objektnummer)``.
    pending: set[tuple[Optional[int], int]] = field(default_factory=set)
    total: int = 0


def _returned_here(db: Session, order_id: int) -> set[tuple[int, Optional[int]]]:
    """``{(Stück, Zustandspunkt)}`` – wo ein Stück in diesen Auftrag **zurückgekehrt** ist.

    Das ist der Unterschied zwischen «steht hier» und «steht hier **wieder**» – und der
    Grund, warum der Rückführpunkt ein eigener Knoten ist: ohne diese Menge stünden
    beide auf derselben Kante, und das Bild verschwiege die Runde.

    Der Punkt gehört dazu. Ein Stück, das an Punkt P zurückkam und längst bei P′ steht,
    ist dort ein ganz gewöhnliches Stück; ohne den Punkt hinge es für immer an einem
    Rückführpunkt, den es hinter sich hat.
    """
    return {
        (int(uid), int(sid) if sid is not None else None)
        for uid, sid in db.execute(
            select(ProcessEvent.instance_unit_id, ProcessEvent.step_id)
            .where(ProcessEvent.order_id == order_id, ProcessEvent.kind == KIND_RETURN)
            .distinct()
        ).all()
    }


def _left_through(db: Session, order_id: int) -> dict[int, int]:
    """Je ausgeschertem Stück die Objektnummer des Auftrags, **durch den** es ging.

    Nicht der Auftrag, in dem es gerade steckt: bei einer Kette A → B → C ist C weder
    ein Nachbar von A noch in dessen Bild – die Linie ginge ins Leere. Was A zeigt, ist
    sein eigener Handover, und der steht in seinem Log.
    """
    rows = db.execute(
        select(ProcessEvent.instance_unit_id, ProcessEvent.payload["to_order"].astext)
        .where(ProcessEvent.order_id == order_id, ProcessEvent.kind == KIND_HANDOVER)
        .order_by(ProcessEvent.instance_unit_id, ProcessEvent.id)
    ).all()
    # Die letzte Zeile je Stück gewinnt: ein Stück kann denselben Auftrag mehrfach
    # verlassen haben, und gemeint ist, wo es **jetzt** hinausgegangen ist.
    return {int(uid): int(to) for uid, to in rows if to is not None}


def _live(db: Session, order: Order) -> _Live:
    """Jede Zugehörigkeit dieses Auftrags, eingeordnet — **genau einmal**.

    Vier sich ausschliessende Fälle, und sie decken alles ab:

    ==========================  =============================================
    aktiv, Punkt gesetzt        steht hier (geblieben **oder** zurückgekehrt)
    geschlossen, Punkt gesetzt  ausgeschert – gerade in einem anderen Auftrag
    geschlossen, Punkt ``NULL`` angekommen, hinter dem Ende
    aktiv, Punkt ``NULL``       gibt es nicht (wer das Ende passiert, wird frei)
    ==========================  =============================================
    """
    rows = db.execute(
        select(
            OrderUnit.current_step_id,
            OrderUnit.released_at.is_(None).label("active"),
            InstanceUnit.status,
            OrderUnit.instance_unit_id,
        )
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .where(OrderUnit.order_id == order.id)
    ).all()

    came_back = _returned_here(db, order.id)
    through = _left_through(db, order.id)
    # **Kommt es zurück?** – dieselbe Ableitung, die auch das Modul sperrt. Die Kette
    # zählt (§3.5); zweimal gelaufen wären es zwei Antworten auf eine Frage.
    coming = process.returning_home(db, order)

    live = _Live(total=len(rows))
    for at, active, status, unit_id in rows:
        at = int(at) if at is not None else None
        unit_id = int(unit_id)
        if active:
            bucket = live.returned if (unit_id, at) in came_back else live.stayed
            bucket[(at, status)] = bucket.get((at, status), 0) + 1
        elif at is None:
            live.arrived[status] = live.arrived.get(status, 0) + 1
        else:
            target = through.get(unit_id)
            if target is None:
                continue
            key = (at, target, status)
            live.away[key] = live.away.get(key, 0) + 1
            if unit_id in coming:
                live.pending.add((at, target))
    return live


# ---------------------------------------------------------------------------
# Der Aufbau
# ---------------------------------------------------------------------------

def build(db: Session, order: Order, steps: Optional[list[ProcessStep]] = None) -> Graph:
    """Der Graph dieses Auftrags: Knoten, Kanten, Positionen.

    Die Knotenfolge ist die Schrittliste, aufgefaltet um die Punkte, an denen etwas
    passiert ist. Ein ``fork`` entsteht, wenn dort je ein Stück ausgeschert ist; ein
    ``join``, wenn dort je eines zurückkam **oder** noch eines unterwegs ist. Beides
    steht im Log bzw. an der Verbindung – geraten wird nichts, und weggenommen wird
    auch nichts mehr: was einmal passiert ist, bleibt im Bild.
    """
    if steps is None:
        steps = (
            db.query(ProcessStep)
            .filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position, ProcessStep.id)
            .all()
        )
    tally = _tally(db, order.id)
    live = _live(db, order)
    g = Graph()

    known = {s.id for s in steps}
    forks = {at for (at, _) in tally.out}
    joins = {at for (at, _) in tally.back} | {at for (at, _) in live.pending}
    for at in sorted(x for x in (forks | joins) if x is not None and x not in known):
        g.problems.append(
            f"Abzweigung an Modul {at}, das nicht (mehr) zum Ablauf gehört – "
            "das Bild kann sie nicht verorten."
        )

    g.nodes.append(Node(id=NODE_START, kind=NODE_START))
    prev = NODE_START

    for index, step in enumerate(steps):
        at = step.id
        # Wie viele Stücke sind je an diesem Punkt angekommen — der Punkt vor dem
        # ersten Modul über das Start-Objekt, jeder weitere über das Modul davor.
        arrived = tally.started if index == 0 else tally.passed.get(steps[index - 1].id, 0)
        reached = arrived > 0
        # Wer hier steht: **geblieben** (nie ausgeschert) und **zurückgekehrt**. Die
        # Trennung ist der ganze Zweck von fork und join – sie stehen auf verschiedenen
        # Kanten, obwohl sie an derselben Stelle warten.
        stayed = _at(live.stayed, at)

        if at in forks:
            g.nodes.append(Node(id=fork_id(at), kind=NODE_FORK, at=at))
            # Die Ankunftskante trägt niemanden: wer hier ist, ist am Abzweigepunkt
            # vorbei – entweder hinaus oder auf dem Bypass daneben.
            prev = _link(g, prev, fork_id(at), reached, [])
            for (point, target) in sorted(tally.out, key=_pointkey):
                if point != at:
                    continue
                g.edges.append(Edge(
                    id=f"out:{at}:{target}", frm=fork_id(at), to=order_ref(target),
                    kind=EDGE_OUT, walked=True, units=_away(live.away, at, target),
                ))

        if at in joins:
            g.nodes.append(Node(id=join_id(at), kind=NODE_JOIN, at=at))
            # Zwischen fork und join liegt der **Bypass** – der Weg derer, die geblieben
            # sind. Ohne fork davor ist es schlicht die Ankunftskante; in beiden Fällen
            # ist es die Kante, auf der sie stehen.
            prev = _link(g, prev, join_id(at), reached, stayed)
            stayed = []
            for (point, source) in sorted(set(tally.back) | live.pending, key=_pointkey):
                if point != at:
                    continue
                g.edges.append(Edge(
                    id=f"back:{at}:{source}", frm=order_ref(source), to=join_id(at),
                    kind=EDGE_BACK, walked=tally.back.get((at, source), 0) > 0,
                ))

        g.nodes.append(Node(id=module_id(at), kind=NODE_MODULE, at=at))
        # Die letzte Kante vor dem Modul: die Zurückgekehrten immer – und die
        # Gebliebenen dann, wenn es hier weder fork noch join gab.
        prev = _link(g, prev, module_id(at), reached, stayed + _at(live.returned, at))

    g.nodes.append(Node(id=NODE_END, kind=NODE_END))
    _link(g, prev, NODE_END, tally.ended > 0, [])
    # Hinter dem Ende gibt es keinen Knoten mehr – angekommene Stücke stehen trotzdem
    # irgendwo, und «irgendwo» ist die Kante, die aus dem Ende herausführt.
    g.edges.append(Edge(
        id="edge:end:done", frm=NODE_END, to=None, walked=tally.ended > 0,
        units=[Placed(status=s, count=n, active=False, at_step_id=None)
               for s, n in sorted(live.arrived.items())],
    ))

    _verify(g, live)
    return g


def _pointkey(key: tuple) -> tuple:
    """Sortierschlüssel für ``(Zustandspunkt, Auftrag)`` – ``None`` ist ein Punkt wie jeder
    andere und darf die Sortierung nicht sprengen."""
    return (key[0] is None, key[0] or 0, key[1])


def _link(g: Graph, frm: str, to: str, walked: bool, units: list[Placed]) -> str:
    g.edges.append(Edge(id=f"edge:{frm}:{to}", frm=frm, to=to, walked=walked, units=units))
    return to


def _at(bucket: dict[tuple[Optional[int], str], int], at: Optional[int]) -> list[Placed]:
    return [
        Placed(status=status, count=n, active=True, at_step_id=point)
        for (point, status), n in sorted(bucket.items(), key=lambda kv: kv[0][1])
        if point == at
    ]


def _away(bucket: dict[tuple[Optional[int], int, str], int],
          at: Optional[int], target: int) -> list[Placed]:
    return [
        Placed(status=status, count=n, active=False, at_step_id=point)
        for (point, to, status), n in sorted(bucket.items(), key=lambda kv: kv[0][2])
        if point == at and to == target
    ]


def _verify(g: Graph, live: _Live) -> None:
    """Die Invarianten. Verletzt heisst **sichtbar kaputt**, nicht still falsch.

    Ein Bild, das eine Einzelinstanz verliert oder doppelt zeigt, ist schlimmer als
    keines: es sieht vollständig aus. Darum wird hier gezählt, und was nicht aufgeht,
    steht in ``problems`` – die Oberfläche sagt es dann, statt es zu zeichnen.
    """
    placed = sum(p.count for e in g.edges for p in e.units)
    if placed != live.total:
        g.problems.append(
            f"{placed} von {live.total} Einzelinstanzen haben eine Position im Bild – "
            "jede muss genau eine haben."
        )
    ids = [n.id for n in g.nodes]
    if len(ids) != len(set(ids)):
        g.problems.append("Zwei Knoten teilen sich eine Kennung.")
    anchored = set(ids)
    for e in g.edges:
        if e.frm not in anchored and not e.frm.startswith("order:"):
            g.problems.append(f"Kante {e.id} beginnt an einem Knoten, den es nicht gibt.")
        if e.to is not None and e.to not in anchored and not e.to.startswith("order:"):
            g.problems.append(f"Kante {e.id} endet an einem Knoten, den es nicht gibt.")


def as_dict(g: Graph) -> dict[str, Any]:
    """Die Aussenform – flach, damit das Schema sie 1:1 übernehmen kann."""
    return {
        "nodes": [
            {"id": n.id, "kind": n.kind, "at": n.at}
            for n in g.nodes
        ],
        "edges": [
            {"id": e.id, "frm": e.frm, "to": e.to, "kind": e.kind, "walked": e.walked,
             "units": [
                 {"status": p.status, "count": p.count, "active": p.active,
                  "at_step_id": p.at_step_id}
                 for p in e.units
             ]}
            for e in g.edges
        ],
        "problems": g.problems,
    }
