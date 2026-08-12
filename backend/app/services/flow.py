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
**Kantenzustand**       ``walked`` — kräftig, wenn **mindestens eine
                        Einzelinstanz diese Kante genommen hat**. Sonst
                        Haarlinie. Kein dritter Wert.
======================  ====================================================

## Der Kantenzustand ist eine Aussage über die KANTE, nicht über den Punkt

Der Hauptstrang ist keine durchgehende Linie, sondern eine Folge von Kanten – und jede
beantwortet ihre eigene Frage. «Hier sind Stücke angekommen» gilt für die Kante **zum**
Abzweigepunkt; ob danach noch jemand geradeaus weiterging, ist eine andere Frage. Nimmt
eine Abweichung alle Stücke mit, hat den geraden Weg **niemand** genommen, und er ist
darum dünn – auch wenn unmittelbar davor sehr wohl Material stand.

Gerechnet wird das als **Bilanz entlang der Achse**: sie beginnt mit dem, was am Punkt
angekommen ist, jeder Abzweigepunkt zieht seine Ausgescherten ab, jeder Rückführpunkt
addiert seine Rückkehrer. Es gibt kein ``if`` je Kantenart und keinen Sonderfall für
«Abweichung nimmt alles»: die Zahl ist entweder grösser als null oder eben nicht.

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

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from . import process
from ..domain import modules, statuses as st
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


#: **Je Nachbar ein eigenes Paar.** Zwei Abweichungen am selben Zustandspunkt teilten
#: sich früher einen Abzweige- und einen Rückführpunkt – und damit musste die erste
#: Rückführung an der zweiten Abweichung *vorbei*, quer über die Fläche. Mit einem
#: eigenen Paar je Nachbar liegt jeder Rückweg unmittelbar unter seinem Hinweg; die
#: Kreuzung ist damit nicht vermieden, sondern **unmöglich** (§8.1a‴).
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
    #: **Die Zuordnung selbst**: die ``order_units``-Zeilen, die auf dieser Kante stehen.
    #: Sie verlässt die Antwort nicht – aber die Zahlen an der Pille (``units``) und die
    #: Liste im Aufklappen (``units_on``) kommen **beide** von hier. Zwei Abfragen für
    #: dieselbe Frage waren genau der Widerspruch «1 Stk, aber zwei Nummern im Dropdown».
    members: list[int] = field(default_factory=list)
    units: list[Placed] = field(default_factory=list)


@dataclass
class Neighbour:
    """Ein Auftrag, der an diesem hier hängt — **aus dem Graph, nicht daneben gezählt**.

    Welche Nachbarn es gibt, stand einmal an zwei Stellen: die Spalten kamen aus einer
    eigenen Log-Abfrage, die Linien aus den Kanten dieses Graphs. Zwei Ableitungen
    derselben Sache laufen auseinander – und dann steht im Bild ein Abzweigepunkt, dessen
    Nachbar fehlt (kein Block, keine Linie, nur der Punkt). Jetzt ist es **dieselbe**
    Liste: ein Nachbar existiert genau dann, wenn es seine Kante gibt.
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
    #: Je Zustandspunkt und Ziel-Auftrag: wie viele Stücke sind ausgeschert.
    out: dict[tuple[Optional[int], int], int] = field(default_factory=dict)
    #: Je Zustandspunkt und Herkunfts-Auftrag: wie viele Stücke sind zurückgekehrt.
    back: dict[tuple[Optional[int], int], int] = field(default_factory=dict)


def _tally(db: Session, order_id: int) -> _Tally:
    """**Eine** Abfrage über den Log dieses Auftrags, gruppiert.

    Gezählt werden **Einzelinstanzen**, nicht Log-Zeilen: ein Stück kann dieselbe Stelle
    mehrfach verlassen (Abweichung der Abweichung), und die Bilanz entlang der Achse
    («angekommen − ausgeschert + zurückgekehrt») ginge dann nicht mehr auf. Jeder Term
    bleibt dabei monoton – ein Stück, das eine Stelle einmal passiert hat, hat sie
    passiert.
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
class _Row:
    """Eine Zugehörigkeit dieses Auftrags — **eine Zeile, eine Position**.

    Vier sich ausschliessende Fälle, und sie decken alles ab:

    ==========================  =============================================
    aktiv, Punkt gesetzt        steht hier (geblieben **oder** zurückgekehrt)
    geschlossen, Punkt gesetzt  ausgeschert – gerade in einem anderen Auftrag
    geschlossen, Punkt ``NULL`` angekommen, hinter dem Ende
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


def _rows(db: Session, order: Order) -> list[_Row]:
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
    # **Kommt es zurück?** – dieselbe Ableitung, die auch das Modul sperrt. Die Kette
    # zählt (§3.5); zweimal gelaufen wären es zwei Antworten auf eine Frage.
    coming = process.returning_home(db, order)

    out: list[_Row] = []
    for mid, at, active, status, unit_id in raw:
        at = int(at) if at is not None else None
        out.append(_Row(
            membership_id=int(mid), at=at, status=status, active=bool(active),
            through=through.get(int(unit_id)),
            returned=(int(unit_id), at) in came_back,
            coming_back=int(unit_id) in coming,
        ))
    return out


# ---------------------------------------------------------------------------
# Der Aufbau
# ---------------------------------------------------------------------------

@dataclass
class Planned:
    """Eine Abzweigung, die es **noch nicht gibt** – der Entwurf daneben.

    Ein Auftragsentwurf lebt im Browser (§6.1): er hat keine Zeile, keine Objektnummer
    und schreibt nichts in den Log. Trotzdem will man **vor** der Freigabe sehen, woher
    seine Stücke kommen und ob sie zurückgehen — und zwar in demselben Bild, das nach der
    Freigabe entsteht, nicht in einer Skizze daneben.

    Darum nimmt der Graph den Plan als Eingabe entgegen, statt dass ihn jemand nachbaut:
    dieselbe Auffaltung, dieselben Knoten-Kennungen, dieselben Kanten. Der einzige
    Unterschied ist der, der wahr ist — **nichts ist gegangen**, also bleibt jede Kante
    des Plans eine Haarlinie und trägt keine Stücke (Regel Nr. 1).
    """

    #: Zustandspunkt, an dem die Stücke stehen (``order_units.current_step_id``).
    at: Optional[int]
    #: Objektnummer des Entwurfs. Er hat noch keine – die Oberfläche setzt eine Marke.
    target: int
    #: Kommt das Material zurück? Nur dann gibt es einen Rückführpunkt.
    returns: bool


def build(db: Session, order: Order, steps: Optional[list[ProcessStep]] = None,
          *, planned: Optional[list[Planned]] = None) -> Graph:
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
    rows = _rows(db, order)
    plan = planned or []
    g = Graph()

    known = {s.id for s in steps}
    forks = {at for (at, _) in tally.out}
    # Ein Rückführpunkt entsteht, wenn dort je etwas zurückkam **oder** noch etwas
    # unterwegs ist. Beides ist «hier mündet etwas ein» – einmal rückblickend, einmal
    # angekündigt.
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
        # **Die Bilanz.** Sie beginnt mit dem, was an diesem Punkt angekommen ist — vor dem
        # ersten Modul über das Start-Objekt, sonst über das Modul davor — und wird in
        # ``_branches`` an jeder Teilung fortgeschrieben. Die Kante **vor** dem Modul trägt
        # damit, was nach allen Abzweigungen und Rückführungen übrig ist.
        flow = tally.started if index == 0 else tally.passed.get(steps[index - 1].id, 0)
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

    # ►► **Ein terminales Modul IST der Ausgang** (``domain/modules.Module.terminal``). ◄◄
    #
    # Dieselbe Eigenschaft, aus der ``domain/chain`` seinen Freigabe-Fehler zieht und der
    # Editor sein «dahinter geht nichts mehr»: hinter ihm gibt es kein Ende-Objekt, weil
    # dort nie ein Stück ankommt (``process.confirm_step`` überspringt ``_finish``).
    #
    # Ein Ende-Objekt trotzdem zu zeichnen war nicht bloss unschön, sondern nachweislich
    # falsch: die ausgesonderten Stücke landeten auf der Kante **hinter** dem Ende, und
    # die galt als nicht gegangen (es gab ja kein ``end``-Ereignis). Genau das hat der
    # Wächter unten gemeldet – zu Recht, und die Ursache war die Zeichnung, nicht er.
    exit_at = steps[-1] if steps and modules.get(steps[-1].module_type).terminal else None
    arrived = _pick(rows, lambda r: not r.active and r.at is None)
    if exit_at is not None:
        g.edges.append(_edge(
            "edge:exit:done", module_id(exit_at.id), None, EDGE_AXIS,
            tally.passed.get(exit_at.id, 0) > 0, arrived,
        ))
    else:
        g.nodes.append(Node(id=NODE_END, kind=NODE_END))
        _link(g, prev, NODE_END, tally.ended > 0, [])
        # Hinter dem Ende gibt es keinen Knoten mehr – angekommene Stücke stehen trotzdem
        # irgendwo, und «irgendwo» ist die Kante, die aus dem Ende herausführt.
        g.edges.append(_edge(
            "edge:end:done", NODE_END, None, EDGE_AXIS, tally.ended > 0, arrived,
        ))

    g.neighbours = _merged(g.neighbours)
    _verify(g, rows)
    _verify_history(db, order, g)
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
# Der Zähler an der Pille und die Liste im Dropdown lasen früher aus zwei verschiedenen
# Quellen: die Pille aus dem Graph, das Dropdown aus einer gröberen Abfrage
# «alle Stücke an Schritt X». Bei einer Teilung stimmte darum die Zahl, aber die Liste
# zeigte beide Gruppen – zweimal dieselbe. Jetzt beantwortet **ein** Prädikat je Kante
# beide Fragen: ``build`` zählt, was es zurückgibt, ``units_on`` listet es auf.

def _targets_at(at: Optional[int], tally: _Tally, pending: set,
                plan: list["Planned"]) -> list[int]:
    """Die Nachbarn an diesem Zustandspunkt — **chronologisch**.

    Die Objektnummer wächst mit der Zeit, also ist «aufsteigend» dasselbe wie «die
    zuerst abgezweigte zuerst». Das ist die Reihenfolge, in der sie im Bild
    untereinander stehen: deterministisch, gleiche Daten ⇒ gleiches Bild.
    """
    return sorted({t for (p, t) in tally.out if p == at}
                  | {s for (p, s) in tally.back if p == at}
                  | {s for (p, s) in pending if p == at}
                  | {p.target for p in plan if p.at == at})


def _branches(g: Graph, prev: str, at: Optional[int], tally: _Tally,
              rows: list["_Row"], pending: set, plan: list["Planned"],
              flow: int) -> tuple[str, int]:
    """Die Abzweigungen an einem Zustandspunkt — **je Nachbar ein eigenes Paar**.

    ``… → fork₁ → join₁ → fork₂ → join₂ → Modul`` statt eines gemeinsamen Paares für
    alle. Der Unterschied ist nicht kosmetisch: mit **einem** Rückführpunkt für alle
    liegt er unter dem letzten Nachbarn, und der Rückweg des ersten muss an allen
    folgenden vorbei – quer über die Fläche, mitten durch deren Hinwege. Mit einem
    eigenen Paar liegt jeder Rückweg unmittelbar unter seinem Hinweg.

    Das ist die Standardform eines **Raupengraphen** (eine Achse mit Anhängseln): sind
    die Ansatzpunkte verschieden, ist die Zeichnung **planar** – Kreuzungen sind dann
    nicht vermieden, sondern unmöglich. Genau das stellt diese Auffaltung her, denn ein
    Stück kehrt immer an den Punkt zurück, an dem es ausgeschert ist (§12.4): ohne sie
    fallen alle Anhängsel eines Punktes auf dieselbe Stelle.

    **Wer geblieben ist, steht auf dem Bypass der ersten noch offenen Abzweigung** –
    einer, nicht mehreren: eine Position ist eine Kante. Ist nichts mehr draussen,
    trägt ihn die Kante vor dem Modul (Befund 2.1).

    **Die Bilanz wandert mit** (``flow``): sie kommt mit dem herein, was am Punkt
    angekommen ist, verliert an jedem Abzweigepunkt seine Ausgescherten und gewinnt an
    jedem Rückführpunkt seine Rückkehrer. Der Bypass zwischen beiden trägt genau das,
    was **an diesem Nachbarn vorbeigelaufen** ist – nimmt er alles mit, ist es null, und
    die Linie ist dünn. Genau das ist die Regel «die Volllinie zeigt den Weg der
    Einzelinstanz», ohne eine einzige Fallunterscheidung.
    """
    stayed = _pick(rows, lambda r: _here_at(r, at, returned=False))
    targets = _targets_at(at, tally, pending, plan)
    # **Der Plan ist keine Vergangenheit.** Eine geplante Abzweigung bekommt ihren
    # Rückführpunkt aus dem Plan, nicht aus dem Log – und dort steht sonst nichts.
    plans = {p.target: p for p in plan if p.at == at}
    holds = next((t for t in targets if (at, t) in pending), None)

    for t in targets:
        fid = fork_id(at, t)
        g.nodes.append(Node(id=fid, kind=NODE_FORK, at=at))
        # Die Ankunftskante trägt niemanden: wer hier ist, ist am Abzweigepunkt
        # vorbei – entweder hinaus oder auf dem Bypass daneben.
        prev = _link(g, prev, fid, flow > 0, [])
        left = tally.out.get((at, t), 0)
        g.edges.append(_edge(
            f"out:{at}:{t}", fid, order_ref(t), EDGE_OUT, left > 0,
            _pick(rows, lambda r, tt=t: _away_at(r, at, tt)),
        ))
        g.neighbours.append(Neighbour(object_id=t, unit_count=left))
        # Ab hier ist die Achse um die Ausgescherten leichter. Nicht negativ: ein Stück
        # kann eine Stelle mehrfach verlassen haben (es kam zwischendurch zurück), und
        # «weniger als niemand» gibt es nicht.
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

    **Ein** Konstruktor für jede Kante des Graphs. Zahlen und Mitglieder können damit
    nicht auseinanderlaufen: die einen sind aus den anderen gerechnet.
    """
    return Edge(id=eid, frm=frm, to=to, kind=kind, walked=walked,
                members=[r.membership_id for r in members], units=_counted(members))


def _link(g: Graph, frm: str, to: str, walked: bool, members: list) -> str:
    g.edges.append(_edge(f"edge:{frm}:{to}", frm, to, EDGE_AXIS, walked, members))
    return to


def _verify(g: Graph, rows: list["_Row"]) -> None:
    """Die Invarianten. Verletzt heisst **sichtbar kaputt**, nicht still falsch.

    Ein Bild, das eine Einzelinstanz verliert oder doppelt zeigt, ist schlimmer als
    keines: es sieht vollständig aus. Darum wird hier gezählt, und was nicht aufgeht,
    steht in ``problems`` – die Oberfläche sagt es dann, statt es zu zeichnen.
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
        # **Wo etwas steht, ist etwas gewesen.** Eine Haarlinie mit Stücken darauf wäre
        # ein Widerspruch in sich – und genau der Fehler, den die Bilanz entlang der
        # Achse machen könnte, wenn sie an einer Stelle zu viel abzöge.
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


def _verify_history(db: Session, order: Order, g: Graph) -> None:
    """**Sagt der Log dasselbe wie das Stück?** — die Invariante über den ABGLEICH.

    Die übrigen Invarianten prüfen die **Zeichnung**: steht jedes Stück an genau einer
    Stelle, gibt es jeden Knoten. Das ist richtig und war doch nicht genug – ein
    überschriebener Endzustand ist kein Zeichenfehler, und darum konnte keine von ihnen
    ihn melden.

    **Und im Log allein steht er auch nicht.** Das war der lehrreiche Teil: der Schreiber,
    der wirklich Schaden anrichtet, geht am Log **vorbei** – ein ``UPDATE`` aus einem
    Reparaturskript, einer Migration, einem Sicherheitsnetz beim Start. Er hinterlässt
    keinen Eintrag, den man zählen könnte. Eine Invariante, die nur den Log liest, sieht
    eine tadellose Geschichte und ein falsches Ding.

    Gefragt wird darum nach dem **Widerspruch zwischen beiden**: der Log sagt, dieses
    Stück hat einen Endzustand erreicht – die Zeile sagt etwas anderes. Weil ein
    Endzustand endgültig ist, gibt es dafür keine harmlose Lesart; jeder Treffer ist ein
    Schreiber ausserhalb der einen Schreibstelle. Das deckt auch den Fall ab, den es gab:
    eine Alt-Reparatur im Startvorgang, die jedes ausgesonderte Stück wieder auf
    ``freigegeben`` setzte.

    Kein zweiter Zustand, keine zweite Buchführung – nur die beiden vorhandenen Quellen
    gegeneinander. Eine Zeichnung, die eine unmögliche Geschichte hübsch darstellt, ist
    schlimmer als eine, die sagt, dass sie nicht stimmt.
    """
    terminal = list(st.TERMINAL_UNIT_STATUSES)
    if not terminal:
        return
    reached = (
        select(ProcessEvent.instance_unit_id)
        .where(
            ProcessEvent.instance_unit_id == InstanceUnit.id,
            ProcessEvent.status_after.in_(terminal),
        )
        .exists()
    )
    drifted = db.execute(
        select(func.count(distinct(InstanceUnit.id)))
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .where(
            OrderUnit.order_id == order.id,
            InstanceUnit.status.not_in(terminal),
            reached,
        )
    ).scalar() or 0
    if drifted:
        g.problems.append(
            f"{drifted}× hat ein Stück laut Log einen Endzustand erreicht, steht aber "
            "nicht mehr darauf. Ein Endzustand ist endgültig – hier hat jemand an der "
            "einen Schreibstelle vorbeigeschrieben."
        )


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

    Bei Menge 5000 will niemand 5000 Zeilen sehen; die Frage an dieser Stelle lautet «wie
    viele stehen wo». Wer die Nummern braucht, klappt auf – und bekommt dann genau diese
    Mitglieder, nicht das Ergebnis einer zweiten, gröberen Abfrage.
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

    Der Graph wird dafür gebaut und die Kante aufgeschlagen. Das ist Absicht: eine
    zweite, schnellere Abfrage («alle Stücke an Schritt X») wäre genau die zweite
    Quelle, aus der der Widerspruch entstand – die Pille zählte die Teilung, die Liste
    kannte sie nicht und zeigte beide Gruppen. Es passiert nur beim Aufklappen.
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
