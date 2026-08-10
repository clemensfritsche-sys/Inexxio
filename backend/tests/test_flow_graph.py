"""**Die Invarianten des Prozessbildes** – als ausführbare Regel, nicht als Prosa.

Das Bild hat sich über viele Runden Fall für Fall verschoben: eine Linie fehlte, ein
Stück stand an der falschen Stelle, eine Abzweigung verschwand. Jeder Fall wurde einzeln
nachgebessert, und beim nächsten brach etwas anderes. Das ist das Muster, das eine
Regel-Tabelle beendet: nicht jeden Fall prüfen, sondern die **Eigenschaften**, aus denen
alle Fälle folgen.

Fünf Invarianten, und sie sind der ganze Vertrag:

=================================================  ===========================
Jede Einzelinstanz hat **genau eine** Position     ``test_every_unit_has_…``
Die Summe der Positionen = Stückzahl des Auftrags  ``test_every_unit_has_…``
Jede Kante hat **genau einen** Zustand             strukturell (``bool``)
Eine kräftige Kante wird **nie wieder** schwach    ``test_a_walked_edge_…``
Jeder Pfad stammt aus dem **einen** Generator      ``test_every_line_comes_…``
=================================================  ===========================

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
    assert "order.flow" in cols, "Die Mitte zeichnet nicht den Graph des Servers."
    assert "rel.flow" in cols, "Der Nachbar zeichnet nicht seinen eigenen Graph."


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
        proc.confirm_step(db, order=child, step_id=cstep.id, values={"ok": True},
                          actor_id=None)
        db.flush()
        assert placed() == total, "Nach der Rückkehr fehlt oder doppelt ein Stück."

        pstep = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one()
        proc.confirm_step(db, order=parent, step_id=pstep.id, values={"ok": True},
                          actor_id=None)
        db.flush()
        assert placed() == total, "Nach dem Abschluss fehlt oder doppelt ein Stück."
    finally:
        db.rollback()
        db.close()


def test_a_returned_piece_stands_after_the_join():
    """**Wer zurückkam, steht hinter dem Rückführpunkt – nicht vor der Abzweigung.**

    Solange Abzweige- und Rückführpunkt **ein** Knoten waren, standen das gebliebene und
    das zurückgekehrte Stück an derselben Stelle: man sah dem Bild die Runde nicht an.
    """
    from app.models import ProcessStep
    from app.services import flow, process as proc

    db = _db()
    try:
        parent, child, step = _scenario(db)
        cstep = db.query(ProcessStep).filter(ProcessStep.order_id == child.id).one()
        proc.confirm_step(db, order=child, step_id=cstep.id, values={"ok": True},
                          actor_id=None)
        db.flush()

        g = flow.build(db, parent)
        fork, join, module = flow.fork_id(step.id), flow.join_id(step.id), flow.module_id(step.id)
        ids = [n.id for n in g.nodes]
        assert ids.index(fork) < ids.index(join) < ids.index(module), (
            f"Die Punkte stehen in der falschen Reihenfolge: {ids}"
        )
        on = {(e.frm, e.to): sum(p.count for p in e.units) for e in g.edges}
        assert on[(fork, join)] == 1, "Das gebliebene Stück steht nicht auf dem Bypass."
        assert on[(join, module)] == 1, (
            "Das zurückgekehrte Stück steht nicht hinter dem Rückführpunkt."
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
        proc.confirm_step(db, order=child, step_id=cstep.id, values={"ok": True},
                          actor_id=None)
        db.flush()
        snapshot("nach der Rückkehr")

        pstep = db.query(ProcessStep).filter(ProcessStep.order_id == parent.id).one()
        proc.confirm_step(db, order=parent, step_id=pstep.id, values={"ok": True},
                          actor_id=None)
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
