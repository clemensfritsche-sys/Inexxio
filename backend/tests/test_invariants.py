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


def test_a_record_goes_out_of_service_on_exactly_one_axis():
    """►►► **Zwei Achsen, die beide «aktiv» heissen — und nur EINE darf gemeint sein.** ◄◄◄

    Das war die Ursache des Befunds 🟠-1: ``is_active`` ist der **Soft-Delete** des
    Datensatzes, ``status`` der **fachliche** Zustand. Geprüft wurde die erste, gemeint war
    die zweite – und weil die erste im ganzen Prozessbereich **nie** gesetzt wird, konnte
    die Prüfung gar nichts abweisen.

    Der dauerhafte Schutz ist keine Umbenennung, sondern das **Wegnehmen der zweiten
    Achse, wo sie keine Bedeutung hat**:

    * Am **Artikel** ist ``is_active`` nicht mehr von aussen setzbar (kein Feld in
      ``ArticleUpdate``) – es gibt genau einen Weg ausser Betrieb, und das ist ``status``.
    * An der **Einzelinstanz** wird ``is_active`` nirgends gesetzt: sie wird nie gelöscht
      und nie deaktiviert (``models/instance_unit``). Ihre Filter sind Gurt neben dem
      Hosenträger, keine lebende Regel – und dieser Wächter hält das fest.
    * Die eine Frage «darf dieser Artikel Neues erzeugen?» heisst nach der **Regel**
      (``articles.may_create``), nicht nach einem Zustand. Ein Name wie
      ``is_article_active`` hätte dieselbe Falle eine Ebene weiter aufgestellt.
    """
    import pathlib
    import re

    app = pathlib.Path(__file__).resolve().parents[1] / "app"

    from app.schemas.article import ArticleUpdate

    assert "is_active" not in ArticleUpdate.model_fields, (
        "``ArticleUpdate`` nimmt wieder ``is_active`` entgegen – damit gibt es zwei Wege, "
        "einen Artikel ausser Betrieb zu nehmen, und die Prozesslogik liest den falschen."
    )

    # Nichts im Prozessbereich deaktiviert eine Einzelinstanz oder eine Instanz.
    hits: list[str] = []
    for path in sorted(app.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*(\w+)\.is_active\s*=\s*False", src, re.M):
            if m.group(1) in ("unit", "instance", "article", "order"):
                hits.append(f"{path.relative_to(app)}: {m.group(0).strip()}")
    assert not hits, (
        "Etwas deaktiviert einen Prozess-Datensatz über den Soft-Delete statt über den "
        "fachlichen Zustand:\n  " + "\n  ".join(hits)
    )

    # Und die Regel steht an genau einer Stelle.
    proc = (app / "services" / "process.py").read_text(encoding="utf-8")
    assert "articles_svc.may_create" in proc, (
        "Die Freigabe fragt nicht mehr, ob der Artikel Neues erzeugen darf."
    )
    body = proc[proc.index("def resolve_lines"):]
    body = body[: body.index("\ndef _assert_single_new")]
    # Die Freigabe **fragt** die Regel, sie formuliert sie nicht nach. Ein eigener
    # Vergleich auf ``article.status`` wäre der zweite Massstab.
    assert "article.status" not in body, (
        "Die Freigabe vergleicht den Artikel-Status selbst, statt ``may_create`` zu "
        "fragen – zwei Massstäbe für dieselbe Regel."
    )
    # Der verbliebene ``is_active``-Vergleich ist der **Soft-Delete** («gibt es nicht»),
    # nicht der fachliche Zustand – daran hängt die Meldung 404, nicht 400.
    assert 'detail=f"Zeile {position}: Artikel {object_id} gibt es nicht.",' in body
    # Und sie greift **nur** für «Neu»: Lager muss abwickelbar bleiben.
    assert "if origin == NEU:" in body and "may_create" in body.split("if origin == NEU:")[1][:200], (
        "``may_create`` greift nicht (mehr) ausschliesslich für die Herkunft «Neu» – "
        "damit wäre der Restbestand eines ausgelaufenen Artikels unerreichbar."
    )


def test_the_article_status_has_exactly_one_vocabulary():
    """►►► **Ein Zustand, ein Wort — auch im Standardwert der Spalte.** ◄◄◄

    Der zweite Fund derselben Klasse wie oben, nur eine Ebene tiefer: der Artikel-Status
    gab es in **zwei Sprachen**. Migration ``107`` hat die Daten und den *Server*-Default
    auf die deutsche Liste gezogen — der *ORM*-Default blieb auf ``"released"`` stehen.
    Und der ORM-Default **gewinnt**: jede Zeile, die ohne ausdrücklichen Status entsteht,
    hätte das alte Wort zurückgebracht.

    **Warum es niemand gemerkt hat:** es gab schlicht keinen Leser. ``services/articles``
    setzt den Status ausdrücklich, und sonst fragte niemand danach. Erst ``may_create``
    muss die Frage «ist dieser Artikel freigegeben?» wirklich beantworten — und beantwortete
    sie für jede so entstandene Zeile mit **nein**.

    Geprüft wird darum die **Quelle des Standardwerts**, nicht sein heutiger Wert: ein
    Literal ist genau die Form, die beim nächsten Umbenennen stehen bleibt.
    """
    import pathlib
    import re

    from app.domain import statuses as st
    from app.models import Article

    column = Article.__table__.c.status
    default = column.default.arg if column.default is not None else None
    assert default in st.ARTICLE_STATUSES, (
        f"Der Standardwert der Spalte ({default!r}) steht nicht in der Statusliste "
        f"{st.ARTICLE_STATUSES} – ein Artikel entstünde in einem Zustand, den das System "
        f"nicht kennt."
    )
    assert str(column.server_default.arg) == default, (
        "ORM- und Server-Default sagen Verschiedenes. Der ORM-Default gewinnt, der "
        "Server-Default ist die Wahrheit für alles, was an SQLAlchemy vorbeischreibt – "
        "sie dürfen nicht auseinanderlaufen."
    )

    # Und **kein** Modul spricht die alte **Artikel**-Status-Sprache. Gesucht wird
    # ausdrücklich nach dem Subjekt: ``draft`` ist als *Auftrags*-Zustand weiterhin ein
    # gültiges Wort, und ein Wächter, der beides in einen Topf wirft, meldet Falsches und
    # wird dafür stillgelegt.
    #
    # Die frühere Ausnahmeliste (die abgeschalteten Bereiche sprachen die alte Sprache
    # noch) ist mit ihnen entfallen – der Wächter gilt jetzt ohne Ausnahme.
    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(
        r"""\b(?:article|art|Article)\.status\s*(?:=|==|!=)\s*["'](released|inactive|draft)["']"""
    )
    hits: list[str] = []
    for path in sorted(app.rglob("*.py")):
        rel = str(path.relative_to(app))
        for m in pattern.finditer(path.read_text(encoding="utf-8")):
            hits.append(f"{rel}: {m.group(0)}")
    assert not hits, (
        "Ein aktives Modul spricht wieder die alte Artikel-Status-Sprache:\n  "
        + "\n  ".join(hits)
    )
