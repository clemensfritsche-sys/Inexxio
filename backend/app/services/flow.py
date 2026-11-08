"""Der **Prozess-Graph** — Knoten, Kanten, Positionen. Abgeleitet aus dem Ereignis-Log.

Der Server liefert das Bild als **Graph** aus dem **Log** (nicht aus dem heutigen Zustand);
das Frontend layoutet und zeichnet nur. Die Begriffe sind abschliessend:

======================  ====================================================
**Knoten**              Prozessobjekte: ``start`` · ``module`` · ``end``,
                        dazu ``fork`` (Abzweigepunkt) und ``join``
                        (Rückführpunkt).
**Kante**               Verbindung zwischen genau zwei Knoten.
**Position**            Wo ein Stück steht — **immer eine Kante**, nie ein
                        Knoten und nie ein diffuser Zwischenraum.
**Kantenzustand**       ``walked`` — kräftig, wenn **mindestens eine
                        Einzelinstanz diese Kante genommen hat**. Sonst
                        Haarlinie. Kein dritter Wert.
======================  ====================================================

## Der Kantenzustand ist eine Aussage über die KANTE, nicht über den Punkt

Nimmt eine Abweichung alle Stücke mit, ist der gerade Weg danach dünn, auch wenn davor
Material stand. Gerechnet als **Bilanz entlang der Achse**: Ankunft, minus Ausgescherte je
Abzweigepunkt, plus Rückkehrer je Rückführpunkt – ohne Sonderfall.

## Warum fork und join eigene Knoten sind

Ein **Zustandspunkt** heisst «vor Modul X» (PROCESS_CORE.md §12.4); dorthin kehrt ein
ausgeschertes Stück zurück. Als **zwei** Knoten trennt das Bild, wer blieb und wer
zurückkam::

        │
    ● fork@X ──────────────▶  Abweichungsauftrag
        │  (wer blieb)                │
    ● join@X ◀────────────────────────┘
        │  (wer zurückkam)
    [ Modul X ]

Fachlich bleibt es **ein** Zustandspunkt (``order_units.current_step_id``).

## Warum der Log und nicht der Zustand

Alle Zähler sind **Zeilenzahlen im Log** und wachsen nur: eine einmal kräftige Kante wird
nie wieder schwach.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from . import order_state
from ..domain import modules
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

#: Ein Knoten in einem **anderen** Auftrag; steht er nicht im Bild, fehlt die Kante.
def order_ref(object_id: int) -> str:
    return f"order:{object_id}"


#: **Je Nachbar ein eigenes Paar** Abzweige-/Rückführpunkt: jeder Rückweg liegt unter
#: seinem Hinweg, Kreuzungen sind unmöglich (§8.1a‴).
def fork_id(at: Optional[int], target: int) -> str:
    return f"fork:{at if at is not None else 'end'}:{target}"


def join_id(at: Optional[int], target: int) -> str:
    return f"join:{at if at is not None else 'end'}:{target}"


def module_id(step_id: int) -> str:
    return f"module:{step_id}"


@dataclass
class Node:
    id: str
    kind: str
    #: Bei ``module`` die eigene ``step_id``; bei ``fork``/``join`` das Modul, **vor** dem
    #: der Punkt liegt. Name und Farbe stehen in ``steps``, nicht am Knoten.
    at: Optional[int] = None


@dataclass
class Placed:
    """Stücke an **einer** Position – gezählt, nicht aufgezählt.

    ``at_step_id``/``active`` sind der Schlüssel, mit dem die Oberfläche die einzelnen
    Nummern nachlädt (``GET …/units``).
    """

    status: str
    count: int
    active: bool
    at_step_id: Optional[int] = None


@dataclass
class Edge:
    id: str
    frm: str
    #: ``None`` bei der Kante hinter dem Ende (dort stehen die angekommenen Stücke).
    to: Optional[str]
    kind: str = EDGE_AXIS
    walked: bool = False
    #: **Die Zuordnung selbst**: die ``order_units``-Zeilen, die auf dieser Kante stehen.
    #: Zahlen an der Pille (``units``) und Liste im Aufklappen (``units_on``) kommen
    #: **beide** von hier.
    members: list[int] = field(default_factory=list)
    units: list[Placed] = field(default_factory=list)


@dataclass
class Neighbour:
    """Ein Auftrag, der an diesem hier hängt — **aus dem Graph, nicht daneben gezählt**.

    Ein Nachbar existiert genau dann, wenn es seine Kante gibt.
    """

    object_id: int
    #: Wie viele Einzelinstanzen sind zu ihm hinausgegangen (über alle Zustandspunkte).
    unit_count: int


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    #: Die Nachbarn in der Reihenfolge, in der sie im Bild stehen (chronologisch).
    neighbours: list[Neighbour] = field(default_factory=list)
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
    #: Je Modul: wie viele Stücke sind **dort** eingetreten (``process._enter_at_step``) –
    #: sie haben die Kante davor nie gesehen.
    entered: dict[int, int] = field(default_factory=dict)
    #: Je Zustandspunkt und Ziel-Auftrag: wie viele Stücke sind ausgeschert.
    out: dict[tuple[Optional[int], int], int] = field(default_factory=dict)
    #: Je Zustandspunkt und Herkunfts-Auftrag: wie viele Stücke sind zurückgekehrt.
    back: dict[tuple[Optional[int], int], int] = field(default_factory=dict)


def _tally(db: Session, order_id: int) -> _Tally:
    """**Eine** Abfrage über den Log dieses Auftrags, gruppiert.

    Gezählt werden **Einzelinstanzen**, nicht Log-Zeilen (ein Stück kann eine Stelle
    mehrfach verlassen); jeder Term bleibt monoton.
    """
    rows = db.execute(
        select(
            ProcessEvent.kind,
            ProcessEvent.step_id,
            ProcessEvent.payload["to_order"].astext,
            ProcessEvent.payload["from_order"].astext,
            func.count(distinct(ProcessEvent.instance_unit_id)),
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
            # Ein Eintritt an einem Modul (``process._enter_at_step``) zählt an seinem
            # Modul, nicht am Start-Objekt.
            if at is None:
                t.started += n
            else:
                t.entered[at] = t.entered.get(at, 0) + n
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
class _Row:
    """Eine Zugehörigkeit dieses Auftrags — **eine Zeile, eine Position**.

    Vier sich ausschliessende Fälle, und sie decken alles ab:

    ==========================  =============================================
    aktiv, Punkt gesetzt        steht hier (geblieben **oder** zurückgekehrt)
    geschlossen, Punkt gesetzt  ausgeschert – gerade in einem anderen Auftrag
    geschlossen, Punkt ``NULL`` **hinaus** – über das Ende oder über ein Modul,
                                das Stücke hinausführt (``left_at`` sagt, welches)
    aktiv, Punkt ``NULL``       gibt es nicht (wer das Ende passiert, wird frei)
    ==========================  =============================================
    """

    membership_id: int
    at: Optional[int]
    status: str
    active: bool
    #: Nur für Ausgescherte: die Objektnummer des Auftrags, **durch den** es ging.
    through: Optional[int] = None
    #: Ist dieses Stück an diesem Punkt schon einmal zurückgekehrt?
    returned: bool = False
    #: Kommt es (noch) zurück? Über die ganze Kette gelesen (§3.5).
    coming_back: bool = False
    #: Nur für Hinausgegangene: das **Modul**, an dem sie den Auftrag verlassen haben
    #: (Aussondern, Verbrauch). ``None`` heisst: über das Ende-Objekt.
    left_at: Optional[int] = None


def _returned_here(db: Session, order_id: int) -> set[tuple[int, Optional[int]]]:
    """``{(Stück, Zustandspunkt)}`` – wo ein Stück in diesen Auftrag **zurückgekehrt** ist.

    Der Punkt gehört dazu: ein Stück, das an Punkt P zurückkam und längst bei P′ steht,
    ist dort ein ganz gewöhnliches Stück.
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

    Nicht der Auftrag, in dem es gerade steckt (bei A → B → C zeigt A auf B).
    """
    rows = db.execute(
        select(ProcessEvent.instance_unit_id, ProcessEvent.payload["to_order"].astext)
        .where(ProcessEvent.order_id == order_id, ProcessEvent.kind == KIND_HANDOVER)
        .order_by(ProcessEvent.instance_unit_id, ProcessEvent.id)
    ).all()
    # Die letzte Zeile je Stück gewinnt: ein Stück kann denselben Auftrag mehrfach
    # verlassen haben, und gemeint ist, wo es **jetzt** hinausgegangen ist.
    return {int(uid): int(to) for uid, to in rows if to is not None}


def _exit_points(db: Session, order_id: int) -> dict[int, int]:
    """Je Stück das **Modul, an dem es diesen Auftrag verlassen hat** — aus dem Log.

    Es gibt genau zwei Arten, einen Auftrag zu verlassen, und der Log unterscheidet sie
    von selbst: über das **Ende-Objekt** (letzter Eintrag ``end``) oder über ein
    **Modul**, das ein Stück hinausführt (letzter Eintrag ``step``).

    ►► **Ein Stück, das noch läuft, verlässt nichts.** ◄◄ Ein wartendes Stück hat ebenfalls
    ``step`` zuletzt; unterschieden wird an der Zugehörigkeit (geschlossen = ``released_at``).
    So gilt der Ausgang auch für den Verbrauch mitten im Ablauf.
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
    gone = (
        select(OrderUnit.instance_unit_id)
        .where(OrderUnit.order_id == order_id, OrderUnit.released_at.isnot(None))
        .scalar_subquery()
    )
    rows = db.execute(
        select(ProcessEvent.instance_unit_id, ProcessEvent.step_id)
        .join(last, ProcessEvent.id == last.c.last_id)
        .where(
            ProcessEvent.kind == KIND_STEP,
            ProcessEvent.step_id.isnot(None),
            ProcessEvent.instance_unit_id.in_(gone),
        )
    ).all()
    return {int(u): int(s) for u, s in rows}


def _left_with(db: Session, order_id: int) -> dict[int, str]:
    """**Mit welchem Zustand hat ein Stück diesen Auftrag verlassen?** — aus dem Log.

    Der letzte Eintrag dieses Stücks in **diesem** Auftrag sagt es.
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
    rows = db.execute(
        select(ProcessEvent.instance_unit_id, ProcessEvent.status_after)
        .join(last, ProcessEvent.id == last.c.last_id)
    ).all()
    return {int(u): s for u, s in rows}


def _rows(db: Session, order: Order, left_at: dict[int, int]) -> list[_Row]:
    """Alle Zugehörigkeiten dieses Auftrags, angereichert — **eine** Abfrage plus Log."""
    raw = db.execute(
        select(
            OrderUnit.id,
            OrderUnit.current_step_id,
            OrderUnit.released_at.is_(None).label("active"),
            InstanceUnit.status,
            OrderUnit.instance_unit_id,
        )
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .where(OrderUnit.order_id == order.id)
        .order_by(OrderUnit.id)
    ).all()
    came_back = _returned_here(db, order.id)
    through = _left_through(db, order.id)
    # **Kommt es zurück?** – dieselbe Ableitung, die das Modul sperrt (Kette, §3.5).
    coming = order_state.returning_home(db, order)
    left_with = _left_with(db, order.id)

    out: list[_Row] = []
    for mid, at, active, status, unit_id in raw:
        at = int(at) if at is not None else None
        # ►►► **Die Achse erzählt diesen Auftrag, die Abzweigung den Nachbarn.** ◄◄◄
        # Abzweigung (geschlossen mit Punkt): der HEUTIGE Zustand (§8.1a). Achse
        # (geschlossen ohne Punkt): der Zustand, mit dem es DIESEN Auftrag verliess –
        # sonst schriebe ein fremder Auftrag rückwirkend in dieses Bild.
        if not bool(active) and at is None:
            status = left_with.get(int(unit_id), status)
        out.append(_Row(
            membership_id=int(mid), at=at, status=status, active=bool(active),
            through=through.get(int(unit_id)),
            returned=(int(unit_id), at) in came_back,
            coming_back=int(unit_id) in coming,
            # Nur wer draussen ist, ist hinausgegangen.
            left_at=(left_at.get(int(unit_id))
                     if not bool(active) and at is None else None),
        ))
    return out


# ---------------------------------------------------------------------------
# Der Aufbau
# ---------------------------------------------------------------------------

@dataclass
class Planned:
    """Eine Abzweigung, die es **noch nicht gibt** – der Entwurf daneben.

    Ein Entwurf lebt im Browser (§6.1); der Graph nimmt ihn als Eingabe und zeichnet ihn im
    selben Bild – als Haarlinien ohne Stücke (**nichts ist gegangen**).
    """

    #: Zustandspunkt, an dem die Stücke stehen (``order_units.current_step_id``).
    at: Optional[int]
    #: Objektnummer des Entwurfs. Er hat noch keine – die Oberfläche setzt eine Marke.
    target: int
    #: Kommt das Material zurück? Nur dann gibt es einen Rückführpunkt.
    returns: bool


def build(db: Session, order: Order, *, planned: Optional[list[Planned]] = None) -> Graph:
    """Der Graph dieses Auftrags: Knoten, Kanten, Positionen.

    Die Knotenfolge ist die Schrittliste, aufgefaltet um die Punkte, an denen etwas
    passiert ist: ``fork``, wo je ein Stück ausscherte; ``join``, wo je eines zurückkam
    **oder** noch unterwegs ist. Was einmal passiert ist, bleibt im Bild.
    """
    steps = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id)
        .order_by(ProcessStep.position, ProcessStep.id)
        .all()
    )
    tally = _tally(db, order.id)
    # ►► **Wer hier hinausging, ist nicht weitergelaufen.** ◄◄ ``passed`` zählt auch, wer
    # den Auftrag am Modul verlässt (z. B. verbrauchte Komponenten).
    left_at = _exit_points(db, order.id)
    # ``onward`` = weitergelaufen; ``tally.passed`` bleibt roh, gegen ihn prüft
    # ``_verify_walked`` die Linienstärke.
    onward = dict(tally.passed)
    for at in left_at.values():
        if at in onward:
            onward[at] = max(0, onward[at] - 1)
    rows = _rows(db, order, left_at)
    plan = planned or []
    g = Graph()

    known = {s.id for s in steps}
    forks = {at for (at, _) in tally.out}
    # Ein Rückführpunkt entsteht, wenn dort je etwas zurückkam **oder** noch unterwegs ist.
    pending = {(r.at, r.through) for r in rows
               if not r.active and r.at is not None and r.through and r.coming_back}
    joins = ({at for (at, _) in tally.back} | {at for (at, _) in pending}
             | {p.at for p in plan if p.returns})
    forks |= {p.at for p in plan}
    for at in sorted(
        (x for x in (forks | joins) if x not in known),
        key=lambda x: (x is None, x),
    ):
        where = f"Modul {at}" if at is not None else "einem Punkt hinter dem Ende"
        g.problems.append(
            f"Abzweigung an {where}, das nicht (mehr) zum Ablauf gehört – "
            "das Bild kann sie nicht verorten."
        )

    g.nodes.append(Node(id=NODE_START, kind=NODE_START))
    prev = NODE_START

    for index, step in enumerate(steps):
        at = step.id
        # **Die Bilanz**: was hier ankam, fortgeschrieben in ``_branches`` an jeder Teilung.
        flow = tally.started if index == 0 else onward.get(steps[index - 1].id, 0)
        open_here = any(point == at for point, _ in pending)

        prev, flow = _branches(g, prev, at, tally, rows, pending, plan, flow)

        g.nodes.append(Node(id=module_id(at), kind=NODE_MODULE, at=at))
        # Die letzte Kante vor dem Modul: alle, die hier warten – ausser denen, die der
        # noch offene Bypass daneben schon trägt.
        prev = _link(g, prev, module_id(at), flow > 0, _pick(
            rows,
            (lambda r: _here_at(r, at, returned=True)) if open_here
            else (lambda r: _here_at(r, at)),
        ))

        # ►► **Wer hier hinausgegangen ist, steht hier** – nicht am Ende. ◄◄ Eine Kante
        # ohne Ziel, **aus dem Log** (Ausgang wie Verbrauch), nicht aus dem Modultyp.
        gone = _pick(rows, lambda r: r.left_at == at)
        if gone:
            g.edges.append(_edge(
                f"edge:exit:{at}", module_id(at), None, EDGE_AXIS, True, gone,
            ))

    # ►► **Hinter einem Ausgang gibt es kein Ende-Objekt** (``modules.Module.terminal``). ◄◄
    # Dort kommt nie ein Stück an (``process.confirm_step`` überspringt ``_finish``).
    if not (steps and modules.get(steps[-1].module_type).terminal):
        g.nodes.append(Node(id=NODE_END, kind=NODE_END))
        _link(g, prev, NODE_END, tally.ended > 0, [])
        # Angekommene Stücke stehen auf der Kante aus dem Ende heraus.
        g.edges.append(_edge(
            "edge:end:done", NODE_END, None, EDGE_AXIS, tally.ended > 0,
            # **Angekommen ist, wer über das Ende ging** – ein verbautes Stück steht an
            # seinem Modul (``left_at``).
            _pick(rows, lambda r: not r.active and r.at is None and r.left_at is None),
        ))

    g.neighbours = _merged(g.neighbours)
    _verify(g, rows)
    _verify_walked(g, tally)
    return g


def _merged(found: list[Neighbour]) -> list[Neighbour]:
    """Ein Nachbar, der an zwei Punkten ansetzt, ist **ein** Nachbar.

    Die Reihenfolge ist die des ersten Auftretens – dieselbe, in der er im Bild steht.
    """
    out: dict[int, Neighbour] = {}
    for n in found:
        seen = out.get(n.object_id)
        if seen is None:
            out[n.object_id] = Neighbour(object_id=n.object_id, unit_count=n.unit_count)
        else:
            seen.unit_count += n.unit_count
    return list(out.values())


# ---------------------------------------------------------------------------
# Die Zuordnung — **eine** Stelle, an der ein Stück auf eine Kante kommt
# ---------------------------------------------------------------------------
#
# Zähler an der Pille und Liste im Dropdown fragen **ein** Prädikat je Kante: ``build``
# zählt, ``units_on`` listet auf.

def _targets_at(at: Optional[int], tally: _Tally, pending: set,
                plan: list["Planned"]) -> list[int]:
    """Die Nachbarn an diesem Zustandspunkt — **chronologisch**.

    Aufsteigende Objektnummer = die zuerst abgezweigte zuerst; deterministisch.
    """
    return sorted({t for (p, t) in tally.out if p == at}
                  | {s for (p, s) in tally.back if p == at}
                  | {s for (p, s) in pending if p == at}
                  | {p.target for p in plan if p.at == at})


def _branches(g: Graph, prev: str, at: Optional[int], tally: _Tally,
              rows: list["_Row"], pending: set, plan: list["Planned"],
              flow: int) -> tuple[str, int]:
    """Die Abzweigungen an einem Zustandspunkt — **je Nachbar ein eigenes Paar**.

    ``… → fork₁ → join₁ → fork₂ → join₂ → Modul``: jeder Rückweg liegt unter seinem Hinweg,
    die Zeichnung ist planar (**Raupengraph**, §12.4).

    **Wer geblieben ist, steht auf dem Bypass der ersten noch offenen Abzweigung**; ist
    nichts mehr draussen, auf der Kante vor dem Modul.

    **Die Bilanz wandert mit** (``flow``): minus Ausgescherte, plus Rückkehrer; der Bypass
    trägt, was **an diesem Nachbarn vorbeigelaufen** ist.
    """
    stayed = _pick(rows, lambda r: _here_at(r, at, returned=False))
    targets = _targets_at(at, tally, pending, plan)
    # Eine geplante Abzweigung bekommt ihren Rückführpunkt aus dem Plan, nicht aus dem Log.
    plans = {p.target: p for p in plan if p.at == at}
    holds = next((t for t in targets if (at, t) in pending), None)

    for t in targets:
        fid = fork_id(at, t)
        g.nodes.append(Node(id=fid, kind=NODE_FORK, at=at))
        # Die Ankunftskante trägt niemanden: wer hier ist, ist hinaus oder auf dem Bypass.
        prev = _link(g, prev, fid, flow > 0, [])
        left = tally.out.get((at, t), 0)
        g.edges.append(_edge(
            f"out:{at}:{t}", fid, order_ref(t), EDGE_OUT, left > 0,
            _pick(rows, lambda r, tt=t: _away_at(r, at, tt)),
        ))
        g.neighbours.append(Neighbour(object_id=t, unit_count=left))
        # Ab hier ist die Achse um die Ausgescherten leichter; nie negativ (ein Stück kann
        # eine Stelle mehrfach verlassen haben).
        flow = max(0, flow - left)
        returning = (at, t) in tally.back or (at, t) in pending
        if t in plans:
            returning = plans[t].returns
        if not returning:
            continue  # **gekappte Ausleihe**: es gibt keinen Rückweg, also keinen Punkt
        jid = join_id(at, t)
        g.nodes.append(Node(id=jid, kind=NODE_JOIN, at=at))
        prev = _link(g, prev, jid, flow > 0, stayed if t == holds else [])
        came = tally.back.get((at, t), 0)
        g.edges.append(_edge(
            f"back:{at}:{t}", order_ref(t), jid, EDGE_BACK, came > 0, [],
        ))
        flow += came
    return prev, flow


def _pick(rows: list["_Row"], where) -> list["_Row"]:
    """Die Zeilen, die auf einer Kante stehen — **das** ist die Zuordnung."""
    return [r for r in rows if where(r)]


def _edge(eid: str, frm: str, to: Optional[str], kind: str, walked: bool,
          members: list) -> Edge:
    """Eine Kante mit ihren Mitgliedern – und den Zahlen, die daraus folgen.

    **Ein** Konstruktor für jede Kante; die Zahlen sind aus den Mitgliedern gerechnet.
    """
    return Edge(id=eid, frm=frm, to=to, kind=kind, walked=walked,
                members=[r.membership_id for r in members], units=_counted(members))


def _link(g: Graph, frm: str, to: str, walked: bool, members: list) -> str:
    g.edges.append(_edge(f"edge:{frm}:{to}", frm, to, EDGE_AXIS, walked, members))
    return to


def _verify_walked(g: Graph, tally: _Tally) -> None:
    """►►► **Die Linienstärke gegen den LOG, nicht gegen die Rechnung.** ◄◄◄

    **Wer ein Modul passiert hat, ist die Kante davor gegangen** – ausser er trat dort ein
    (``process._enter_at_step``). Eine bewusst zweite Herleitung neben der Bilanz; sie trägt
    auch im abgeschlossenen Auftrag, wo keine Kante mehr Mitglieder hat.
    """
    for e in g.edges:
        if e.kind != EDGE_AXIS or not e.to or not e.to.startswith(f"{NODE_MODULE}:"):
            continue
        at = int(e.to.split(":")[1])
        from_axis = tally.passed.get(at, 0) - tally.entered.get(at, 0)
        if from_axis > 0 and not e.walked:
            g.problems.append(
                f"Kante {e.id}: {from_axis} Einzelinstanz(en) haben das Modul passiert, "
                "die Linie dorthin gilt trotzdem als nicht gegangen."
            )


def _verify(g: Graph, rows: list["_Row"]) -> None:
    """Die Invarianten. Verletzt heisst **sichtbar kaputt**, nicht still falsch.

    Was nicht aufgeht, steht in ``problems``; die Oberfläche sagt es, statt es zu zeichnen.
    """
    placed: list[int] = [m for e in g.edges for m in e.members]
    if len(placed) != len(set(placed)):
        g.problems.append("Eine Einzelinstanz steht an zwei Stellen im Bild.")
    if len(set(placed)) != len(rows):
        g.problems.append(
            f"{len(set(placed))} von {len(rows)} Einzelinstanzen haben eine Position im "
            "Bild – jede muss genau eine haben."
        )
    for e in g.edges:
        if sum(p.count for p in e.units) != len(e.members):
            g.problems.append(f"Kante {e.id}: Zahl und Mitglieder stimmen nicht überein.")
        # **Wo etwas steht, ist etwas gewesen** – keine Haarlinie mit Stücken darauf.
        if e.members and not e.walked:
            g.problems.append(
                f"Kante {e.id}: dort stehen Einzelinstanzen, aber sie gilt als nicht gegangen."
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


def _away_at(r: _Row, at: Optional[int], target: int) -> bool:
    """Ausgeschert an Punkt ``at``, hinaus durch Auftrag ``target``."""
    return not r.active and r.at == at and r.through == target


def _here_at(r: _Row, at: Optional[int], returned: Optional[bool] = None) -> bool:
    """Steht an Punkt ``at`` – wahlweise nur die Zurückgekehrten bzw. nur die Gebliebenen."""
    if not (r.active and r.at == at):
        return False
    return returned is None or r.returned is returned


def _counted(members: list[_Row]) -> list[Placed]:
    """Die Zahlen an der Pille – **abgeleitet aus den Mitgliedern**, nicht daneben gezählt.

    Wer die Nummern braucht, klappt auf und bekommt genau diese Mitglieder.
    """
    counts: dict[tuple[str, bool, Optional[int]], int] = {}
    for r in members:
        key = (r.status, r.active, r.at)
        counts[key] = counts.get(key, 0) + 1
    return [
        Placed(status=status, count=n, active=active, at_step_id=at)
        for (status, active, at), n in sorted(counts.items())
    ]


def units_on(db: Session, order: Order, edge_id: str) -> list[int]:
    """Die ``order_units``-Zeilen dieser Kante — **nachgeschlagen**, nicht neu hergeleitet.

    Der Graph wird dafür gebaut und die Kante aufgeschlagen – bewusst keine zweite Abfrage.
    """
    g = build(db, order)
    for e in g.edges:
        if e.id == edge_id:
            return list(e.members)
    return []


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
