"""**Die Invarianten als Wächter** – über den gesamten Bestand, bei jeder Änderung.

Sie sind das eigentliche Netz: ein Szenariotest prüft, woran jemand gedacht hat, eine
Invariante prüft, was **wahr sein muss**. Sie laufen darum hier mit und nicht nur auf
Zuruf (``scripts/invariant_report.py``).

**Der Bestand wird dafür hergestellt**, nicht vorausgesetzt: eine Invariantenprüfung über
eine leere Datenbank ist grün und sagt nichts. Gefahren wird ein kleiner, echter
Ausschnitt der Matrix – Erzeugung, Abweichung, dreistufige Kette, Aussonderung – und
danach geprüft, **ohne** zu committen.
"""

import pytest

from tests.runner import session
from tests.scenarios import World


def _db():
    try:
        return session()
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regeln wirklich laufen.")


def _world(db) -> World:
    """Ein Bestand, der jede Invariante etwas zu prüfen gibt."""
    w = World(db)
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])

    # 1 · Erzeugung, ganz durchgelaufen
    fertig = w.produce(art, 2)
    w.run_all(fertig)

    # 2 · laufender Auftrag mit offener, rückführender Abweichung
    laufend = w.produce(art, 2)
    n = w.numbers(laufend)
    w.take(art, n[:1], from_order=laufend.object_id, steps=[w.capture()])

    # 3 · dreistufige Kette
    a = w.produce(art, 1)
    na = w.numbers(a)
    b = w.take(art, na, from_order=a.object_id, steps=[w.capture()])
    w.take(art, na, from_order=b.object_id, steps=[w.capture()])

    # 4 · Aussonderung (Ausgang) und Sperre
    weg = w.article(serialization="batch", template=[w.dispose("scrap")])
    w.run_all(w.produce(weg, 2))
    ruht = w.article(serialization="batch", template=[w.dispose("block", "Klärung")])
    w.run_all(w.produce(ruht, 1))
    db.flush()
    return w


def test_the_invariants_hold_over_the_whole_dataset():
    """►►► **Was wahr sein muss, ist wahr — über ALLES, nicht über ein Szenario.** ◄◄◄

    Jede verletzte Invariante nennt den betroffenen Datensatz. Eine Meldung ohne ihn wäre
    eine Behauptung, mit der niemand etwas anfangen kann.
    """
    from app.services import invariants

    db = _db()
    try:
        _world(db)
        findings = invariants.run(db)
        bad = [f for f in findings if not f.ok]
        assert not bad, "\n".join(
            f"{f.check.key} — {f.check.title}\n"
            + f"  Regel: {f.check.rule}\n"
            + "\n".join(f"  ❌ {v}" for v in f.violations)
            for f in bad
        )
        assert len(findings) >= 15, (
            "Die Invariantenliste ist geschrumpft – eine Prüfung, die still verschwindet, "
            "ist von einer bestandenen nicht zu unterscheiden."
        )
    finally:
        db.rollback()
        db.close()


def test_every_invariant_would_actually_notice_something():
    """**Ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu unterscheiden.**

    Geprüft wird die Fehlerform selbst: ein zweiter offener Eintrag für dasselbe Stück
    (Bruch von G2) und ein Log-Eintrag aus einem Endzustand heraus (Bruch von G4). Beide
    müssen gemeldet werden – täte es keiner, wäre das grüne Ergebnis oben wertlos.
    """
    from app.models import InstanceUnit, OrderUnit, ProcessEvent
    from app.services import invariants

    db = _db()
    try:
        w = _world(db)
        art = w.article(serialization="batch")
        order = w.produce(art, 1)
        unit = w.unit(w.numbers(order)[0])

        # Bug-Form 1: eine zweite offene Zugehörigkeit. Sie lässt sich **nur** herstellen,
        # indem der partielle Unique-Index kurz weicht – und genau das ist der Beweis,
        # dass er trägt (der erste Anlauf scheiterte an ihm, wie er soll). Das ``DROP``
        # ist transaktional; der Rollback am Ende bringt ihn zurück.
        from sqlalchemy import text

        db.execute(text("DROP INDEX uq_order_units_active"))
        db.add(OrderUnit(order_id=order.id, instance_unit_id=unit.id,
                         current_step_id=w.steps(order)[0].id))
        # Bug-Form 2: ein Wechsel aus einem Endzustand heraus.
        db.add(ProcessEvent(order_id=order.id, instance_unit_id=unit.id, kind="step",
                            status_before="verschrottet", status_after="freigegeben"))
        # Bug-Form 3: ein Zustand, den der Katalog nicht kennt.
        db.add(InstanceUnit(instance_id=unit.instance_id, suffix=99, status="phantasie"))
        db.flush()

        keys = {f.check.key for f in invariants.run(db) if not f.ok}
        assert "I01" in keys, "Zwei offene Zugehörigkeiten blieben unbemerkt (G2)."
        assert "I04" in keys, "Ein Wechsel aus dem Endzustand blieb unbemerkt (G4)."
        assert "I06" in keys, "Ein unbekannter Zustand blieb unbemerkt (§1.1)."
    finally:
        db.rollback()
        db.close()


def test_the_campaign_runs_on_every_push():
    """**Matrix und Invarianten laufen in der CI mit — sonst sind sie Dekoration.**

    Sie brauchen echtes PostgreSQL. Läuft die CI ohne, überspringen sie sich lautlos, und
    ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu unterscheiden. Geprüft
    wird darum die Reihenfolge (erst Schema, dann Tests) **und** dass die beiden Dateien
    überhaupt noch da sind – eine Prüfung, die still verschwindet, sieht aus wie eine
    bestandene.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    wf = (root / ".github" / "workflows" / "deploy-dev.yml").read_text(encoding="utf-8")
    quality = wf.split("jobs:")[1].split("deploy-backend:")[0]
    assert quality.index("alembic upgrade head") < quality.index("pytest"), (
        "Das Schema wird erst nach den Tests gebaut – dann laufen Matrix und Invarianten "
        "gegen keine Datenbank und überspringen sich selbst."
    )
    assert "DATABASE_URL" in quality[: quality.index("pytest")]
    for name in ("matrix.py", "scenarios.py", "runner.py", "test_scenarios.py"):
        assert (pathlib.Path(__file__).parent / name).exists(), (
            f"tests/{name} fehlt – die Szenariomatrix ist damit weg, und niemand merkt es."
        )
