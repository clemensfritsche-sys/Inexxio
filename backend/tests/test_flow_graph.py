"""**Die Invarianten des Prozessbildes** – als ausführbare Regel, nicht als Prosa.

Das Bild hat sich über viele Runden Fall für Fall verschoben: eine Linie fehlte, ein
Stück stand an der falschen Stelle, eine Abzweigung verschwand. Jeder Fall wurde einzeln
nachgebessert, und beim nächsten brach etwas anderes. Das ist das Muster, das eine
Regel-Tabelle beendet: nicht jeden Fall prüfen, sondern die **Eigenschaften**, aus denen
alle Fälle folgen.

Acht Invarianten, und sie sind der ganze Vertrag:

=================================================  ===============================
Jede Einzelinstanz hat **genau eine** Position     ``test_every_unit_has_…``
Die Summe der Positionen = Stückzahl des Auftrags  ``test_every_unit_has_…``
Zähler und Aufklappen fragen **dieselbe** Position ``test_the_count_and_the_list_…``
Jede Kante hat **genau einen** Zustand             strukturell (``bool``)
Eine kräftige Kante wird **nie wieder** schwach    ``test_a_walked_edge_…``
Jeder Pfad stammt aus dem **einen** Generator      ``test_every_line_comes_…``
Keine zwei Kanten teilen sich einen **Kanal**      ``test_no_two_branches_…``
Keine Kante überlagert einen **Knoten-Container**  ``test_a_line_docks_at_a_port_…``
=================================================  ===============================

Wird eine verletzt, ist das ein **sauberer Fehler** – im Bild eine rote Notiz statt
einer stillen Fehldarstellung (``Graph.problems``), hier ein roter Test.

**Warum gegen echtes PostgreSQL.** Die Ableitung lebt von JSONB-Payloads
(``payload->>'to_order'``) und vom partiellen Unique-Index auf ``order_units``. Gegen
SQLite geprüft wäre eine andere Wahrheit geprüft als die, die läuft.
"""

import os
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"


def _read(path: pathlib.Path) -> str:
    assert path.exists(), f"Erwartete Datei fehlt: {path}"
    return path.read_text(encoding="utf-8")


def _code(src: str) -> str:
    """Nur der Code. Eine **Begründung**, warum etwas weg ist, darf den Namen nennen."""
    return "\n".join(
        line for line in src.split("\n")
        if not line.lstrip().startswith(("*", "//", "/*"))
    )


# ---------------------------------------------------------------------------
# Der Vertrag: das Backend weiss, das Frontend zeichnet
# ---------------------------------------------------------------------------

def test_the_backend_is_master_and_the_frontend_only_draws():
    """**Prozesslogik gehört auf den Server.** Die Oberfläche layoutet und zeichnet.

    Vorher baute sie die Knotenfolge selbst zusammen und leitete aus den *aktuellen*
    Stück-Gruppen ab, wie weit die Linie kräftig läuft. Das war eine zweite Ableitung
    neben dem Server – und welche von beiden stimmt, sah man erst am Bildschirm.
    """
    cols = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")

    for name in ("flowNodes", "walkedEdges", "statePointId", "branchPoints"):
        assert name not in cols and name not in diagram, (
            f"«{name}» ist zurück – das Frontend leitet den Graph wieder selbst ab."
        )
    # Die Kante bringt ihren Zustand mit; niemand rechnet ihn nach.
    assert "walked={e.walked}" in diagram, "Die Kante trägt ihren Zustand nicht selbst."
    assert "rel.flow" in cols, "Der Nachbar zeichnet nicht seinen eigenen Graph."
    # Die Mitte bekommt ihren Graph vom Aufrufer – am laufenden Auftrag ist das der des
    # Servers. Wer ihn dort nicht durchreicht, zeichnet wieder etwas Eigenes.
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "graph: order.flow" in detail, "Die Mitte zeichnet nicht den Graph des Servers."


def test_every_line_comes_from_the_one_generator():
    """**Ein Pfad-Generator, ein Eckenradius, zwei Stärken.**

    Wird irgendwo eine Linie ausserhalb von ``polyPath``/``Stroke`` gezeichnet, ist es
    falsch gebaut: dann kann sich eine Stelle anders entscheiden, und genau daraus
    entstanden die Abweichungen zwischen Achse, Ausscherung und Rückführung.
    """
    flow = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    cols = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")

    assert flow.count("export function polyPath(") == 1
    assert flow.count("export const BEND") == 1, "Der Eckenradius steht nicht an einer Stelle."
    assert (diagram + cols).count("<path") == 1, (
        "Es gibt mehr als eine Stelle, die eine Prozesslinie zeichnet."
    )
    # Und der Generator glättet das Zittern selbst – kein Korrekturversatz am Aufruf.
    assert "function straighten(" in flow, (
        "Ein zu kurzes Zwischenstück wird nicht begradigt – dann wackelt jede Linie, "
        "deren Anker zufällig fast auf einer Höhe liegen."
    )
    # **Kein Korrekturversatz an einer gemessenen Koordinate.** Ein «+ 4» hinter einem
    # Anker ist kein Layout, sondern ein Pflaster über einer Geometrie, die nicht
    # aufgeht – und das nächste Pflaster liegt dann woanders. Benannte Masse (``LEAD``,
    # ``BEND``, ``metrics.gap``) sind erlaubt: die stehen an einer Stelle.
    for name, src in (("process-columns", cols), ("process-diagram", diagram)):
        stray = re.search(r"\.(cx|cy|top|bottom|left|right)\s*[+-]\s*\d", src)
        assert not stray, (
            f"{name} korrigiert eine gemessene Koordinate mit einer nackten Zahl "
            f"(«{stray.group(0)}») – ein Versatz an der Aufrufstelle ist der Anfang "
            f"einer zweiten Geometrie."
        )


def test_the_graph_is_derived_from_the_log():
    """**Was passiert ist, ist passiert.** Der Graph liest den Log, nicht den Zustand.

    Das ist der Grund, warum die Abzweigung verschwand, sobald das Stück zurück und
    weitergezogen war: sie wurde aus «wo stehen aktive Stücke» gebaut. Zeilen im Log
    können nur wachsen – daraus folgt die Monotonie der Kanten von selbst.
    """
    svc = _read(BACKEND / "app" / "services" / "flow.py")
    tally = svc.split("def _tally(")[1].split("\ndef ")[0]
    assert "ProcessEvent" in tally and "OrderUnit" not in tally, (
        "Die Zähler, aus denen die Linienstärke folgt, lesen den Zustand statt den Log."
    )
    for kind in ("KIND_START", "KIND_STEP", "KIND_END", "KIND_HANDOVER", "KIND_RETURN"):
        assert kind in tally, f"«{kind}» wird nicht gezählt – ein Ereignis fehlt im Bild."


# ---------------------------------------------------------------------------
# Die Invarianten am laufenden Prozess
# ---------------------------------------------------------------------------

def _db():
    """Eine Sitzung gegen echtes PostgreSQL – oder ein Skip **mit Grund**.

    Ein Wächter, der stillschweigend nicht läuft, ist von einem kaputten nicht zu
    unterscheiden; darum nennt der Skip die fehlende Bedingung.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    try:
        from app.core.database import Base, SessionLocal, engine
        import app.main as main
        Base.metadata.create_all(engine)
        main._ensure_columns()
        return SessionLocal()
    except Exception as exc:  # pragma: no cover - reine Umgebungsfrage
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Invarianten wirklich laufen.")


def _confirm(db, order, step, values=None):
    """Ein Modul bestätigen — **ein Vorgang je wartender Instanz** (Scan-Regel §3).

    Der Scan verifiziert die Instanz, nicht die Einzelinstanz; ein Bestätigen gilt darum
    für die Stücke genau einer Instanz. Diese Tests wollen «das Modul läuft durch», also
    gehen sie der Reihe nach durch alles, was davorsteht.
    """
    from app.services import process as proc

    moved = 0
    for work in proc.step_work(db, order, step):
        moved += proc.confirm_step(
            db, order=order, step_id=step.id, values=values or {"ok": True},
            instance_object_id=work["instance_object_id"], verification="scan",
            actor_id=None,
        )["moved"]
    return moved


def _scenario(db):
    """Der gemeldete Fall: 2 Stück, 1 Modul, eine Abweichung nimmt 1 und gibt es zurück."""
    from app.models import Article, InstanceUnit, OrderUnit, ProcessStep
    from app.services import article_process as tpl, objects as obj, process as proc

    art = Article(object_id=obj.next_object_id(db), name="Prüfstück", unit="stk",
                  serialization="unit", status="released")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, [{"module_type": "datenerfassung",
                                "config": {"points": [{"label": "OK", "type": "bool"}]}}])
    db.flush()

    parent = proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": 2, "origin": "neu",
                "units": []}],
        steps=[], actor_id=None,
    )
    db.flush()
    rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
    numbers = proc.unit_numbers(
        db, db.query(InstanceUnit).filter(
            InstanceUnit.id.in_([r.instance_unit_id for r in rows])).all())
    first = numbers[rows[0].instance_unit_id]

    child = proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": 1, "origin": "lager",
                "units": [{"number": first, "from_order": parent.object_id}],
                "returns": True}],
        steps=[{"module_type": "datenerfassung",
                "config": {"points": [{"label": "OK", "type": "bool"}]}}],
        actor_id=None,
    )
    db.flush()
    step = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one()
    return parent, child, step


def test_every_unit_has_exactly_one_position():
    """**Jede Einzelinstanz steht genau einmal im Bild – und die Summe stimmt.**

    Ein Bild, das ein Stück verliert oder doppelt zeigt, ist schlimmer als keines: es
    sieht vollständig aus. Geprüft wird über den ganzen Lebenslauf, weil sich die
    Zuordnung bei jedem Übergang ändert.
    """
    from app.models import OrderUnit, ProcessStep
    from app.services import flow, process as proc

    db = _db()
    try:
        parent, child, _ = _scenario(db)
        total = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).count()
        assert total == 2

        def placed():
            g = flow.build(db, parent)
            assert not g.problems, f"Der Graph meldet Invarianten-Verstösse: {g.problems}"
            return sum(p.count for e in g.edges for p in e.units)

        assert placed() == total, "Nach der Ausscherung fehlt oder doppelt ein Stück."
        cstep = db.query(ProcessStep).filter(ProcessStep.order_id == child.id).one()
        _confirm(db, child, cstep)
        db.flush()
        assert placed() == total, "Nach der Rückkehr fehlt oder doppelt ein Stück."

        pstep = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one()
        _confirm(db, parent, pstep)
        db.flush()
        assert placed() == total, "Nach dem Abschluss fehlt oder doppelt ein Stück."
    finally:
        db.rollback()
        db.close()


def test_a_returned_piece_stands_after_the_join():
    """**Der Bypass trägt nur, solange die Teilung offen ist** (Befund 2.1).

    Zwei Zustände, eine Regel:

    * **Solange etwas draussen ist**, sind «geblieben» und «zurückgekehrt» zwei Orte:
      das gebliebene Stück steht auf dem Bypass ``fork → join``, das zurückgekehrte
      dahinter. Solange Abzweige- und Rückführpunkt **ein** Knoten waren, standen beide
      an derselben Stelle und man sah dem Bild die Runde nicht an.
    * **Ist alles zurück**, ist die Unterscheidung Geschichte und keine Position mehr:
      beide warten an derselben Stelle auf dasselbe Modul. Zwei Pillen dafür behaupteten
      zwei Orte – und darum standen im Aufklappen beide Nummern unter «1 Stk».

    Die Reihenfolge fork → join → Modul gilt in beiden Zuständen: sie ist die Aussage
    über das, was **passiert ist**, nicht darüber, wo gerade jemand steht.
    """
    from app.models import ProcessStep
    from app.services import flow, process as proc

    db = _db()
    try:
        parent, child, step = _scenario(db)
        fork = flow.fork_id(step.id, child.object_id)
        join = flow.join_id(step.id, child.object_id)
        module = flow.module_id(step.id)

        def picture():
            g = flow.build(db, parent)
            ids = [n.id for n in g.nodes]
            assert ids.index(fork) < ids.index(join) < ids.index(module), (
                f"Die Punkte stehen in der falschen Reihenfolge: {ids}"
            )
            return {(e.frm, e.to): sum(p.count for p in e.units) for e in g.edges}

        on = picture()
        assert on[(fork, join)] == 1, (
            "Das gebliebene Stück steht nicht auf dem Bypass, solange draussen noch "
            "etwas unterwegs ist."
        )
        assert on[(join, module)] == 0, (
            "Vor dem Modul steht schon jemand, obwohl die Teilung noch offen ist."
        )

        cstep = db.query(ProcessStep).filter(ProcessStep.order_id == child.id).one()
        _confirm(db, child, cstep)
        db.flush()

        on = picture()
        assert on[(fork, join)] == 0, (
            "Der Bypass trägt noch etwas, obwohl nichts mehr draussen ist – dann steht "
            "dasselbe Stück im Bild zweimal an zwei Orten."
        )
        assert on[(join, module)] == 2, (
            "Nach der Rückkehr stehen nicht beide Stücke vor dem Modul."
        )
    finally:
        db.rollback()
        db.close()


def test_a_walked_edge_never_becomes_weak_again():
    """**Was passiert ist, bleibt passiert** – über den ganzen Lebenslauf gemessen.

    Zugleich der Nachweis für den schwersten der gemeldeten Fehler: nachdem die
    Abweichung abgeschlossen war, verschwanden Hin- und Rückweg aus dem Bild. Eine
    einmal gezeichnete Kante darf weder verschwinden noch verblassen.
    """
    from app.models import ProcessStep
    from app.services import flow, process as proc

    db = _db()
    try:
        parent, child, _ = _scenario(db)
        seen: set[str] = set()

        def snapshot(stage: str):
            g = flow.build(db, parent)
            walked = {e.id for e in g.edges if e.walked}
            gone = seen - walked
            assert not gone, f"{stage}: Kanten sind wieder schwach geworden: {sorted(gone)}"
            missing = seen - {e.id for e in g.edges}
            assert not missing, f"{stage}: Kanten sind verschwunden: {sorted(missing)}"
            seen.update(walked)

        snapshot("nach dem Ausscheren")
        cstep = db.query(ProcessStep).filter(ProcessStep.order_id == child.id).one()
        _confirm(db, child, cstep)
        db.flush()
        snapshot("nach der Rückkehr")

        pstep = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one()
        _confirm(db, parent, pstep)
        db.flush()
        snapshot("nach dem Abschluss")

        g = flow.build(db, parent)
        assert any(e.kind == "out" and e.walked for e in g.edges), (
            "Die Ausscherung ist aus dem Bild verschwunden, sobald das Stück zurück war."
        )
        assert any(e.kind == "back" and e.walked for e in g.edges), (
            "Die Rückführung ist aus dem Bild verschwunden."
        )
    finally:
        db.rollback()
        db.close()


def test_the_strong_line_shows_the_way_a_piece_actually_took():
    """**Der Hauptstrang ist eine Folge von Kanten, nicht eine Linie** (Befund 1).

    Nimmt eine Abweichung **alle** Stücke mit, hat den geraden Weg zwischen Abzweige-
    und Rückführpunkt niemand genommen – er ist dünn. Die Kante **zum** Abzweigepunkt ist
    kräftig (dort ist Material angekommen), und das ist kein Widerspruch, sondern der
    Unterschied zwischen zwei Kanten.

    Vorher trug jede Kante an einem Punkt denselben Zustand («hier ist etwas
    angekommen»); der gerade Weg war damit **immer** kräftig, sobald überhaupt jemand
    dort war. Gerechnet wird jetzt als Bilanz entlang der Achse – ohne Fallunterscheidung
    für «Abweichung nimmt alles».

    Die Gegenprobe steckt mit im selben Test: bei **zwei** Nachbarn am selben Punkt ist
    der Bypass des ersten kräftig (das zweite Stück lief daran vorbei) und der des
    zweiten dünn.
    """
    from app.models import InstanceUnit, OrderUnit, ProcessStep
    from app.services import article_process as tpl, flow, objects as obj, process as proc

    db = _db()
    try:
        art = _article(db, tpl, obj)
        parent = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": 2, "origin": "neu",
                    "units": []}],
            steps=[], actor_id=None,
        )
        db.flush()
        rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
        names = proc.unit_numbers(
            db, db.query(InstanceUnit).filter(
                InstanceUnit.id.in_([r.instance_unit_id for r in rows])).all())
        numbers = [names[r.instance_unit_id] for r in rows]
        at = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one().id

        both = _deviate(db, proc, art, parent, numbers)
        db.flush()
        g = flow.build(db, parent)
        edges = {e.id: e for e in g.edges}
        bypass = edges[f"edge:fork:{at}:{both.object_id}:join:{at}:{both.object_id}"]
        assert not bypass.walked, (
            "Der gerade Weg ist kräftig, obwohl jede Einzelinstanz die Abweichung "
            "genommen hat – die Volllinie zeigt damit einen Weg, den niemand ging."
        )
        assert edges[f"edge:start:fork:{at}:{both.object_id}"].walked, (
            "Die Kante ZUM Abzweigepunkt muss kräftig bleiben – dort ist Material "
            "angekommen."
        )

        # Gegenprobe: zwei Nachbarn, je ein Stück. Am ersten läuft das zweite vorbei.
        db.rollback()
        art = _article(db, tpl, obj)
        parent = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": 2, "origin": "neu",
                    "units": []}],
            steps=[], actor_id=None,
        )
        db.flush()
        rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
        names = proc.unit_numbers(
            db, db.query(InstanceUnit).filter(
                InstanceUnit.id.in_([r.instance_unit_id for r in rows])).all())
        numbers = [names[r.instance_unit_id] for r in rows]
        at = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one().id
        first = _deviate(db, proc, art, parent, numbers[:1])
        second = _deviate(db, proc, art, parent, numbers[1:])
        db.flush()
        edges = {e.id: e for e in flow.build(db, parent).edges}
        assert edges[f"edge:fork:{at}:{first.object_id}:join:{at}:{first.object_id}"].walked, (
            "Am ersten Nachbarn ist das zweite Stück vorbeigelaufen – dort ist die Linie "
            "kräftig."
        )
        assert not edges[
            f"edge:fork:{at}:{second.object_id}:join:{at}:{second.object_id}"].walked, (
            "Am zweiten Nachbarn ist niemand mehr vorbeigelaufen – dort ist sie dünn."
        )
    finally:
        db.rollback()
        db.close()


def test_a_neighbour_exists_exactly_when_its_branch_does():
    """**Spalte und Linie kommen aus EINER Liste** (Befund 2).

    Die Nachbarn daneben stammten aus einer eigenen Log-Abfrage, die Abzweigungen aus dem
    Graph. Zwei Ableitungen derselben Sache – und wo sie auseinanderliefen, stand im Bild
    ein Abzweigepunkt ohne seinen Nachbarn: kein Block, keine Linie, nur der Punkt.

    Geprüft wird die Gleichheit selbst, nicht ein Symptom: **jeder** Auftrag, auf den eine
    Kante zeigt, steht in ``graph.neighbours`` – und umgekehrt. Eine gekappte Abweichung
    (ohne Rückweg) ist dabei der Fall, der es am ehesten auseinanderreisst, denn sie hat
    nur eine der beiden Kanten.
    """
    from app.models import InstanceUnit, OrderUnit
    from app.services import article_process as tpl, flow, objects as obj, process as proc

    db = _db()
    try:
        art = _article(db, tpl, obj)
        parent = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": 3, "origin": "neu",
                    "units": []}],
            steps=[], actor_id=None,
        )
        db.flush()
        rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
        names = proc.unit_numbers(
            db, db.query(InstanceUnit).filter(
                InstanceUnit.id.in_([r.instance_unit_id for r in rows])).all())
        numbers = [names[r.instance_unit_id] for r in rows]

        cut = _deviate(db, proc, art, parent, numbers[:1], returns=False)
        back = _deviate(db, proc, art, parent, numbers[1:2])
        db.flush()

        g = flow.build(db, parent)
        listed = {n.object_id for n in g.neighbours}
        referenced = {
            int(end[len("order:"):])
            for e in g.edges
            for end in (e.frm, e.to or "")
            if end.startswith("order:")
        }
        assert listed == referenced, (
            "Nachbar-Liste und Kanten des Graphs nennen verschiedene Aufträge – "
            f"Liste {sorted(listed)}, Kanten {sorted(referenced)}."
        )
        assert cut.object_id in listed, (
            "Die gekappte Abweichung fehlt in der Liste – ihr Abzweigepunkt stünde im "
            "Bild ohne Nachbarn."
        )
        assert back.object_id in listed
        assert [n.object_id for n in g.neighbours] == sorted(listed), (
            "Die Reihenfolge ist nicht chronologisch – gleiche Daten müssen dasselbe "
            "Bild ergeben."
        )
    finally:
        db.rollback()
        db.close()


def _article(db, tpl, obj):
    from app.models import Article
    art = Article(object_id=obj.next_object_id(db), name="Prüfstück", unit="stk",
                  serialization="unit", status="released")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, [{"module_type": "datenerfassung",
                                "config": {"points": [{"label": "OK", "type": "bool"}]}}])
    db.flush()
    return art


def _deviate(db, proc, art, parent, numbers, *, returns=True):
    return proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": len(numbers),
                "origin": "lager", "returns": returns,
                "units": [{"number": n, "from_order": parent.object_id} for n in numbers]}],
        steps=[{"module_type": "datenerfassung",
                "config": {"points": [{"label": "OK", "type": "bool"}]}}],
        actor_id=None,
    )


def test_branches_at_one_point_get_their_own_pair_and_never_overlap():
    """**Kreuzungsfreiheit entsteht aus dem Graph, nicht aus geschickterem Zeichnen.**

    Das Bild ist ein **Raupengraph**: eine Achse mit Anhängseln. Ein solcher Graph ist
    genau dann planar zeichenbar, wenn die Ansatz-Intervalle der Anhängsel einander
    nicht überschneiden. Ein Stück kehrt immer an den Punkt zurück, an dem es
    ausgeschert ist (§12.4) – also ist jedes Intervall ``[fork, join]`` **eines**
    Punktes, und zwei Punkte liegen nie ineinander.

    Blieb es bei **einem** Paar je Zustandspunkt, fielen alle Anhängsel eines Punktes
    auf dasselbe Intervall: der Rückweg des ersten musste an allen folgenden vorbei,
    quer durch deren Hinwege. Mit einem eigenen Paar je Nachbar sind die Intervalle
    disjunkt – und damit ist eine Kreuzung nicht vermieden, sondern **unmöglich**.

    Geprüft wird genau das: paarweise Disjunktheit über den echten Knotenverlauf.
    """
    from app.models import ProcessStep
    from app.services import article_process as tpl, flow, objects as obj, process as proc
    from app.models import Article, InstanceUnit, OrderUnit

    db = _db()
    try:
        art = Article(object_id=obj.next_object_id(db), name="Blech", unit="stk",
                      serialization="unit", status="released")
        db.add(art)
        db.flush()
        point = {"points": [{"label": "OK", "type": "bool"}]}
        tpl.create_steps(db, art, [{"module_type": "datenerfassung", "config": point}])
        db.flush()
        parent = proc.release(db, steps=[], actor_id=None,
                              lines=[{"article_object_id": art.object_id, "quantity": 4,
                                      "origin": "neu", "units": []}])
        db.flush()
        step = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one()
        rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
        nums = proc.unit_numbers(db, [db.get(InstanceUnit, r.instance_unit_id) for r in rows])

        # Drei Abweichungen am **selben** Punkt – der gemeldete Fall.
        kids = [
            proc.release(db, lines=[{
                "article_object_id": art.object_id, "quantity": 1, "origin": "lager",
                "units": [{"number": nums[r.instance_unit_id],
                           "from_order": parent.object_id}],
                "returns": i != 1,          # einer davon gekappt
            }], steps=[{"module_type": "datenerfassung", "config": point}], actor_id=None)
            for i, r in enumerate(rows[:3])
        ]
        db.flush()

        g = flow.build(db, parent)
        assert not g.problems, g.problems
        order_of = {n.id: i for i, n in enumerate(g.nodes)}

        spans = []
        for kid in kids:
            ref = flow.order_ref(kid.object_id)
            ends = [order_of[e.frm] for e in g.edges if e.kind == "out" and e.to == ref]
            ends += [order_of[e.to] for e in g.edges if e.kind == "back" and e.frm == ref]
            assert ends, f"Abweichung {kid.object_id} hängt an keinem Punkt."
            spans.append((min(ends), max(ends), kid.object_id))

        for i, (a0, a1, a) in enumerate(spans):
            for (b0, b1, b) in spans[i + 1:]:
                assert a1 < b0 or b1 < a0, (
                    f"Die Abzweigungen {a} und {b} teilen sich Zeilen ({a0}–{a1} ↔ "
                    f"{b0}–{b1}) – dann muss eine Linie an der anderen vorbei, und "
                    f"genau daraus entsteht die Kreuzung."
                )
        # Und die Reihenfolge im Bild ist die chronologische – gleiche Daten, gleiches Bild.
        assert [s[2] for s in sorted(spans)] == sorted(k.object_id for k in kids), (
            "Die Abzweigungen stehen nicht in der Reihenfolge, in der sie entstanden."
        )
    finally:
        db.rollback()
        db.close()


def test_no_two_branches_share_a_channel():
    """**Mehrere Abzweigungen sind kein Sonderfall, sondern n statt 1.**

    Laufen zwei Abweichungen gleichzeitig, brauchen ihre senkrechten Stücke verschiedene
    Spuren – sonst liegen die Linien exakt übereinander, und aus zwei Wegen wird optisch
    einer. Das ist seit Jahrzehnten gelöst (ELK nennt die Spuren *tracks*): zwei
    Segmente, deren **Spannen sich überschneiden**, bekommen verschiedene Spuren; für
    Intervalle ist gierig nach Anfang sortiert optimal.

    Geprüft wird, dass die Zuteilung **an einer Stelle** entsteht und nirgends
    danebengerechnet wird. Eine zweite Zuteilung wäre wieder «meistens passt es».
    """
    flow = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    cols = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")

    assert flow.count("export function channels(") == 1, (
        "Die Kanalzuteilung steht nicht an genau einer Stelle."
    )
    assert "open[i].end < s.from" in flow, (
        "Die Spannen sind halboffen – zwei Abzweigungen, die sich eine Zeile teilen, "
        "bekämen denselben Kanal und lägen aufeinander."
    )
    assert "channelX(centre," in cols and flow.count("export function channelX(") == 1, (
        "Die x-Koordinate eines Kanals entsteht nicht aus der Zuteilung."
    )
    assert "channels(spans(left))" in cols and "channels(spans(right))" in cols, (
        "Nicht jede Seite bekommt ihre eigene Zuteilung."
    )
    # **Die Lücke folgt der Zuteilung, nicht umgekehrt.** Ein festes Mass wäre bei zwei
    # Abweichungen zu eng – und «zu eng» heisst hier: übereinander.
    assert "gutterFor(Math.max(" in cols and "gutter={gutter}" in cols, (
        "Die Spurlücke wächst nicht mit der Zahl der Kanäle."
    )
    # Und Nachbarn, deren Spannen sich überschneiden, stehen **untereinander**: im
    # selben Rasterfeld lägen sie sonst als zwei Rasterelemente aufeinander.
    assert "if (last && s.from <= last.to)" in cols, (
        "Überschneidende Nachbarn werden nicht zu einem Band zusammengefasst – im "
        "Raster stünden sie dann in derselben Zelle, also übereinander."
    )


def test_a_line_docks_at_a_port_and_the_layer_is_never_clipped():
    """**Ports und ein Linien-Layer** – die beiden Befunde 2.3 und 2.4 hatten eine Wurzel.

    Eine Linie endete «irgendwo am Knoten» und lief darum je nach Modulhöhe hinein; und
    sie wurde vom Rahmen beschnitten, wenn sie einen Pixel darüber hinausging. Beides
    ist dieselbe Frage: **wo hört eine Linie auf?**

    Die Antwort ist die der etablierten Werkzeuge (React Flow *Handles*, bpmn-js
    *docking points*, Miro-Ankerpunkte): sie hört an einem **Port** auf – einem Punkt
    auf dem Rand, der aus der Messung kommt. Sie kennt die Fläche eines Knotens gar
    nicht mehr. Und gezeichnet wird auf **einem** Layer über der ganzen Prozessfläche,
    den kein Geschwister-Container beschneidet.
    """
    flow = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    cols = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")

    assert flow.count("export function port(") == 1, "Der Andockpunkt entsteht nicht an einer Stelle."
    # Jedes Ende einer Linie ist ein Port – auch die Achse, damit es nur eine Regel gibt.
    assert "port(A, 'bottom'), port(B, 'top')" in diagram, (
        "Die Achse dockt nicht an Ports an."
    )
    for side in ("'center'", "'top'", "'bottom'"):
        assert f"port(there.a, {side})" in cols or f"port(here.a, {side})" in cols, (
            f"Die Querverbindung nutzt den Port {side} nicht."
        )
    # **Ein Layer, und er beschneidet nichts.** Ohne `overflow: visible` fehlte eine
    # Linie still, sobald sie einen Pixel über die gemessene Rahmenhöhe hinauslief.
    assert flow.count("<svg") == 1, "Es gibt mehr als einen Linien-Layer."
    assert "overflow: 'visible'" in flow, (
        "Der Linien-Layer beschneidet wieder – dann fehlt eine Linie, statt dass sie "
        "sichtbar zu weit läuft."
    )
    # Platz wird im **Layout** gemacht, nicht mit einem Versatz an der Linie.
    assert "paddingTop: TOP_LEAD, paddingBottom: BOTTOM_LEAD" in cols, (
        "Der Rahmen macht oben und unten keinen Platz für die ein- und ausmündenden "
        "Linien – dann läuft eine davon über den Rand."
    )
    # Und der Knoten nennt sich, damit «keine Linie überlagert einen Knoten» nachmessbar
    # ist statt behauptet.
    assert "data-flow-node={id}" in flow, "Ein Knoten ist im DOM nicht als solcher erkennbar."
    # **Ein Takt für das ganze Bild.** An jedem Prozesspunkt setzt ein Bogen an; liegen
    # zwei Punkte näher als zwei Radien, überlagern sich die Bögen und kreuzen sich.
    # Zwei Rhythmen – einer im Raster, einer in der Spalte – hiessen: in der einen
    # Ansicht stimmt es, in der anderen nicht.
    assert "export const FLOW_GAP = 2 * BEND;" in flow, (
        "Der senkrechte Takt ist keine Ableitung des Radius mehr. Zwischen einem "
        "Abzweigepunkt und SEINEM Rückführpunkt liegen zwei Waagrechte (hinaus bei "
        "`fork + BEND`, herein bei `join − BEND`); übrig bleibt `FLOW_GAP + POINT − "
        "2·BEND`. Beim früheren `2·BEND − 8` war das **ein** Pixel – im Bild eine "
        "einzige Linie (gemessen: 1,6 px Abstand über 172 px gemeinsame Länge)."
    )
    assert "export const POINT = 9;" in flow and "width: POINT, height: POINT" in diagram, (
        "Die Punktgrösse steht nicht mehr an der einen Stelle, aus der der Takt sie "
        "liest – dann rechnet der Takt mit einer Zahl, die die Komponente nicht hat."
    )
    assert "rowGap: FLOW_GAP" in cols and "gap: FLOW_GAP" in diagram, (
        "Raster und Spalte laufen in verschiedenen Takten – dann überlagert es in genau "
        "einer der beiden Ansichten. Genau so ist es aufgetreten: in der Mitte stimmte "
        "es, in der Nachbarspalte lagen die beiden Waagrechten aufeinander."
    )


def test_the_draft_shows_the_source_order_exactly_as_it_will_be():
    """**Die Vorschau ist dasselbe Bild, nur früher** (Auftrag §2).

    Ein Entwurf, der einem laufenden Auftrag ein Stück abnimmt, zeigt ihn schon vor der
    Freigabe in der linken Spur – mit dem Abzweigepunkt, der entstünde, und (falls
    zurückgeführt wird) dem Rückführpunkt. Das ist **keine zweite Darstellung**: sie kommt
    aus derselben Ableitung (``flow.build`` mit ``planned``) und wird mit denselben
    Bauteilen gezeichnet.

    Geprüft wird die Gleichheit selbst — Vorschau vor der Freigabe gegen den echten Graph
    danach, bis auf die Objektnummer (die es vorher nicht gibt) und ``walked`` (vorher ist
    nichts gegangen). Läuft eine der beiden Seiten weg, bricht genau das.
    """
    from app.routers import orders as router
    from app.schemas.order import DRAFT_OBJECT_ID
    from app.services import article_process as tpl, flow, objects as obj, process as proc
    from app.models import InstanceUnit, OrderUnit

    db = _db()
    try:
        for returns in (True, False):
            art = _article(db, tpl, obj)
            parent = proc.release(
                db,
                lines=[{"article_object_id": art.object_id, "quantity": 2,
                        "origin": "neu", "units": []}],
                steps=[], actor_id=None,
            )
            db.flush()
            rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
            numbers = proc.unit_numbers(
                db, db.query(InstanceUnit).filter(
                    InstanceUnit.id.in_([r.instance_unit_id for r in rows])).all())
            first = numbers[rows[0].instance_unit_id]

            draft = {
                "lines": [{"article_object_id": art.object_id, "quantity": 1,
                           "origin": "lager", "returns": returns,
                           "units": [{"number": first, "from_order": parent.object_id}]}],
                "steps": [{"module_type": "datenerfassung",
                           "config": {"points": [{"label": "OK", "type": "bool"}]}}],
            }
            preview = router._preview_parents(db, draft)
            assert len(preview) == 1, "Der Quell-Auftrag fehlt in der Vorschau."
            shown = preview[0]
            assert shown.object_id == parent.object_id
            assert shown.unit_count == 1, "Die Vorschau nennt die Stückzahl nicht."
            assert shown.returns is returns

            kinds = [n.kind for n in shown.flow.nodes]
            assert "fork" in kinds, "Die geplante Abzweigung fehlt im Bild."
            assert ("join" in kinds) is returns, (
                "Der Rückführpunkt richtet sich nicht nach der Entscheidung."
            )
            assert not [e for e in shown.flow.edges
                        if e.kind in ("out", "back") and e.walked], (
                "Etwas Geplantes ist kräftig – es ist aber noch nichts gegangen."
            )

            def shape(graph, target):
                def norm(x):
                    # Als **ganze Zahl** ersetzen: ein blosses `replace` träfe die 0 des
                    # Entwurfs auch mitten in jeder Objektnummer und in jeder Schritt-id.
                    return re.sub(rf"(?<!\d){target}(?!\d)", "<DRAFT>", x or "")
                return {
                    "nodes": [(norm(n.id), n.kind) for n in graph.nodes],
                    "edges": sorted((norm(e.id), norm(e.frm), norm(e.to), e.kind)
                                    for e in graph.edges),
                }

            before = shape(shown.flow, DRAFT_OBJECT_ID)
            child = proc.release(db, lines=draft["lines"], steps=draft["steps"], actor_id=None)
            db.flush()
            after = shape(
                type(shown.flow)(**flow.as_dict(flow.build(db, parent))), child.object_id)
            assert before == after, (
                "Vorschau und Wirklichkeit haben verschiedene Formen – dann ist die "
                "Vorschau eine zweite Darstellung und nicht dasselbe Bild."
            )
    finally:
        db.rollback()
        db.close()


def test_the_planned_return_is_the_line_itself():
    """**Ob zurückgeführt wird, sagt die Linie – nicht ein Knopfpaar** (Auftrag §5).

    Im laufenden Bild ist es längst so: eine gekappte Ausleihe hat schlicht keinen
    Rückweg, und das Fehlen ist die Aussage. Der Entwurf sagte es daneben, mit zwei
    Knöpfen an der Stückauswahl – also an einer anderen Stelle als seine Wirkung.

    Seit der Vorschau (§2) ist die Linie die **echte**: sie führt zum Quell-Auftrag, der
    daneben steht, und kommt aus dem Server. Der frühere Ersatz-Knoten unter dem Ende
    (``ReturnSwitch``) ist damit weg – zwei Rückweg-Linien für eine Entscheidung wären
    eine zu viel, und die zweite wäre die erfundene.

    Was bleibt, ist die Regel Wort für Wort: **ein Klick schaltet sie an und aus**, der
    Schalter bleibt, wenn die Linie geht (sonst wäre die Entscheidung einmalig), und es
    gibt keinen dritten Linientyp. *Wo* er steht – am Anfang der Linie, als letzte Zeile
    der Spalte –, prüft ``test_the_return_switch_sits_where_its_line_starts``.
    """
    diagram = _code(_read(FRONTEND / "components/erp/process-diagram.tsx"))
    cols = _read(FRONTEND / "components/erp/process-columns.tsx")
    lines = _read(FRONTEND / "components/erp/definition-lines.tsx")
    detail = _read(FRONTEND / "components/erp/order-detail.tsx")

    for gone in ("ReturnSwitch", "ReturnLink", "kind: 'back'", "edge:end:back"):
        assert gone not in diagram, (
            f"«{gone}» ist zurück – der Ersatz-Rückweg steht neben dem echten, und das "
            f"Bild zeigt dieselbe Entscheidung zweimal."
        )
    assert "onToggleReturn" in cols and "function ReturnRow(" in diagram, (
        "Es gibt keinen Schalter mehr – dann ist die Entscheidung im Entwurf nicht mehr "
        "zu treffen."
    )
    assert "onToggleReturn" in detail and "l.returns" in detail, (
        "Der Klick landet nicht mehr an der Definitionszeile, an der die Entscheidung hängt."
    )
    assert "ReturnBtn" not in lines and "onReturns" not in lines, (
        "Die Rückführung wird wieder neben der Stückauswahl entschieden – zwei Orte für "
        "dieselbe Aussage."
    )
    for banned in ("strokeDasharray", "dashed'"):
        assert banned not in diagram and banned not in cols, (
            f"«{banned}» im Prozessbild: es gibt zwei Stärken und sonst nichts – ob "
            f"zurückgeführt wird, sagt die Anwesenheit der Linie."
        )


def test_the_line_says_the_past_and_the_pill_says_the_present():
    """**Zwei Aussagen, zwei Träger** (Auftrag §1) – und beide stehen schon in den Daten.

    Eine ausgescherte Zeile hiess «In Abweichung», für immer. Bei einer **gekappten**
    Ausleihe blieb das stehen, auch wenn der Nachbar längst fertig war und das Stück
    nirgends mehr in einem Prozess stand: ein Satz in der Gegenwartsform über etwas
    Vergangenes.

    Aufgelöst wird das ohne neues Feld, denn der Graph trägt beides längst:

    * ``walked`` ist **Vergangenheit** – aus dem Log, monoton, verschwindet nie.
    * ``units[].status`` ist die **Gegenwart** des Stücks – ``im_prozess`` heisst «es
      arbeitet gerade woanders», alles andere heisst «es ist dort geblieben».

    Geprüft wird genau der gemeldete Ablauf: die Abzweigung bleibt kräftig, der Status
    darauf wechselt. Läuft eine der beiden Aussagen der anderen nach, bricht das hier.
    """
    from app.domain import statuses as st
    from app.models import InstanceUnit, OrderUnit, ProcessStep
    from app.services import article_process as tpl, flow, objects as obj, process as proc

    db = _db()
    try:
        art = _article(db, tpl, obj)
        parent = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": 2, "origin": "neu",
                    "units": []}],
            steps=[], actor_id=None,
        )
        db.flush()
        rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
        numbers = proc.unit_numbers(
            db, db.query(InstanceUnit).filter(
                InstanceUnit.id.in_([r.instance_unit_id for r in rows])).all())
        child = _deviate(db, proc, art, parent, [numbers[rows[0].instance_unit_id]],
                         returns=False)
        db.flush()

        def out_edge():
            return next(e for e in flow.build(db, parent).edges if e.kind == flow.EDGE_OUT)

        away = out_edge()
        assert away.walked, "Die Abzweigung ist nicht kräftig – da ist aber etwas gegangen."
        assert [(p.status, p.count) for p in away.units] == [(st.IM_PROZESS, 1)], (
            "Solange der Nachbar läuft, ist das Stück «im Prozess» – das ist die Gegenwart."
        )

        # Der Nachbar läuft durch. Das Stück kommt nicht zurück (gekappt).
        for s in (db.query(ProcessStep).filter(ProcessStep.order_id == child.id)
                  .order_by(ProcessStep.position).all()):
            _confirm(db, child, s,
                     values={p["key"]: True for p in (s.config or {}).get("points", [])})
        db.flush()

        done = out_edge()
        assert done.walked, (
            "Die Abzweigung ist schwach geworden – was passiert ist, bleibt passiert."
        )
        assert [p.status for p in done.units] == [st.FREIGEGEBEN], (
            "Das Stück gilt weiter als «im Prozess», obwohl es in keinem mehr steht – "
            "dann sagt die Pille die Vergangenheit in der Gegenwartsform."
        )
    finally:
        db.rollback()
        db.close()


def test_the_draft_is_named_the_same_on_both_sides():
    """Der Entwurf hat keine Objektnummer – aber **eine Adresse**, und die ist geteilt.

    Die Vorschau nennt ihn als Ziel ihrer Abzweigung (``order:<n>``); im Browser muss
    dieselbe Zahl die Mitte bezeichnen, sonst findet die Linie ihr Ende nicht und
    verschwindet **still**.
    """
    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    diagram = _read(FRONTEND / "components/erp/process-diagram.tsx")
    server = re.search(r"DRAFT_OBJECT_ID\s*=\s*(-?\d+)", schema)
    client = re.search(r"DRAFT_OBJECT_ID\s*=\s*(-?\d+)", diagram)
    assert server and client, "Eine der beiden Seiten kennt die Entwurfs-Adresse nicht."
    assert server.group(1) == client.group(1), (
        f"Server sagt {server.group(1)}, Browser sagt {client.group(1)} – die Linie zum "
        f"Entwurf endet damit im Nichts."
    )


def test_the_journey_is_a_tree_on_the_same_line():
    """**Herkunft und Verbleib hängen am Strang, nicht daneben** (Auftrag §6).

    Oben und unten stand eine Textzeile mit den Nachbar-Aufträgen, und **daneben** ein
    Container mit der Definition («3× Blech, neu erzeugt»). Zwei Anzeigen derselben
    Sache: jedes Stück kam entweder aus einem Auftrag (steht in ``journey_in``) oder ist
    hier entstanden (steht als ``neu``-Zeile) – gegen echtes PostgreSQL gemessen, über
    Erzeugung, Lagerzugriff, zwei Vorgänger und Abweichung.

    Geblieben ist **ein** Baum am selben Strang. Drei Eigenschaften tragen ihn:

    * **Eine Bedingung** dafür, ob es die Zeile gibt (``hasJourney``) – das Raster mit
      drei Spuren und die Spalte darin zählen sonst verschiedene Zeilen, und alles
      darunter sitzt eine daneben.
    * **Eine Liste** für Chips und Äste (``journeyKeys``) – sonst entsteht ein Ast ohne
      Chip oder ein Chip ohne Ast. Genau diese Klasse Fehler war Befund 2.
    * **Gruppiert, gekappt, nicht verschwiegen**: je Nachbar eine Verzweigung mit Anzahl,
      höchstens ``JOURNEY_LIMIT``, der Rest gezählt. Bei 5000 Stück sieht man dasselbe
      wie bei drei.
    """
    diagram = _read(FRONTEND / "components/erp/process-diagram.tsx")
    cols = _read(FRONTEND / "components/erp/process-columns.tsx")
    detail = _read(FRONTEND / "components/erp/order-detail.tsx")

    assert "export const hasJourney" in diagram, (
        "Die Bedingung für die Herkunfts-Zeile hat keinen Ort mehr."
    )
    assert diagram.count("journeyIn: hasJourney(") == 1 and "hasJourney(inStops" in cols, (
        "Raster und Spalte entscheiden wieder verschieden, ob es die Zeile gibt."
    )
    assert "export function journeyKeys" in diagram, "Die Ast-Schlüssel sind keine Liste mehr."
    # **Dieselben Variablen speisen beides**: die Äste (über `journeyKeys`) und die Chips
    # (über die Spalte). Sie stehen im selben Rahmen und werden dort einmal berechnet –
    # ein zweiter Rahmen mit eigener Rechnung war genau die Stelle, an der ein Ast ohne
    # Chip entstehen konnte.
    assert "journeyKeys(inStops, origins)" in cols, "Die Äste kommen nicht aus der Liste."
    assert "journeyIn={inStops} journeyOut={outStops} origins={origins}" in cols, (
        "Chips und Äste kommen nicht mehr aus denselben Variablen – dann gibt es Chips "
        "ohne Linie oder Linien ohne Chip."
    )
    assert cols.count("journeyKeys(") == 2, (
        "Die Ast-Schlüssel werden an mehr als einer Stelle gerechnet."
    )
    assert "slice(0, JOURNEY_LIMIT)" in diagram and "rest=" in diagram, (
        "Die Journey ist nicht mehr gekappt oder sagt es nicht – eine stumme Liste sähe "
        "aus wie alles."
    )
    assert "flexWrap: 'nowrap'" in diagram, (
        "Die Journey-Zeile bricht um – dann fällt ein Ast der oberen Reihe durch die "
        "untere (§4)."
    )
    assert "DefinitionSummary" not in detail, (
        "Der Definitions-Container ist zurück – er sagt ein zweites Mal, was am Baum steht."
    )


def test_the_count_and_the_list_ask_the_same_position():
    """**Zähler und Aufklappen fragen dieselbe Stelle** (Befund 2.1).

    Die Pille zählte aus dem Graph, das Dropdown holte «alle Stücke an Schritt X» – zwei
    Quellen, und an einem Punkt mit Teilung liefen sie auseinander: «1 Stk», und im
    Aufklappen zwei Nummern. Jetzt ist die Zuordnung **die Kante**: ``build`` zählt, was
    sie enthält, ``units_on`` schlägt genau dieselbe Liste nach.
    """
    svc = _read(BACKEND / "app" / "services" / "flow.py")
    assert "members: list[int]" in svc, "Die Kante trägt ihre Mitglieder nicht."
    assert "units=_counted(members)" in svc, (
        "Die Zahl an der Pille wird nicht aus den Mitgliedern gerechnet."
    )
    body = svc[svc.index("def units_on("):]
    body = body[:body.index("\ndef ")]
    assert "build(db, order)" in body and "OrderUnit" not in body, (
        "Das Aufklappen fragt wieder eigenständig ab – das ist die zweite Quelle."
    )
    proc = _read(BACKEND / "app" / "services" / "process.py")
    page = proc[proc.index("def units_page("):]
    page = page[:page.index("\ndef ")]
    assert "membership_ids" in page and "current_step_id" not in page, (
        "Die Seite sucht sich ihre Stücke selbst zusammen, statt die Zuordnung des "
        "Bildes zu übernehmen."
    )
    api = _read(FRONTEND / "lib" / "api.ts")
    assert "getOrderUnits(objectId: number, edge: string" in api, (
        "Die Oberfläche fragt nicht nach der Kante – dann kann sie eine andere Menge "
        "bekommen als die, die sie gezählt hat."
    )


def test_the_invariants_run_on_every_push():
    """Ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu unterscheiden.

    Die Invarianten oben brauchen eine Datenbank. Läuft die CI ohne, überspringt sie
    genau die Prüfungen, für die diese Datei da ist – lautlos.
    """
    wf = _read(ROOT / ".github" / "workflows" / "deploy-dev.yml")
    quality = wf.split("jobs:")[1].split("deploy-backend:")[0]
    schema = quality.index("alembic upgrade head")
    tests = quality.index("pytest")
    assert schema < tests, (
        "Das Schema wird erst nach den Tests gebaut – dann laufen die Invarianten des "
        "Prozessbildes gegen keine Datenbank und überspringen sich selbst."
    )
    assert "DATABASE_URL" in quality[:tests], (
        "Der Test-Schritt bekommt keine DATABASE_URL – die Invarianten überspringen sich."
    )
