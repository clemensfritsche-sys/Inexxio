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


def test_the_article_status_has_exactly_one_source():
    """►►► **Der Artikel-Zustand ist ABGELEITET — es gibt keine zweite Angabe.** ◄◄◄

    «Ausser Betrieb» ist keine eigene Aussage, sondern die Folge des Ersetzens (Testnotiz
    #773): ``Freigegeben``, solange dieser Artikel die neueste Fassung ist, ``Inaktiv``,
    sobald ein Nachfolger ihn abgelöst hat. Genau **eine** Angabe trägt das –
    ``replaced_by_id``.

    **Die Bug-Form, gegen die dieser Wächter steht**, ist die Rückkehr der Spalte: eine
    ``status``-Spalte am Modell wäre wieder die zweite Wahrheit, sie würde von zwei
    Stellen gesetzt (dem Ersetzen und einem Knopf) und von ``may_create`` gelesen. Genau
    daraus entstand der Artikel, der «inaktiv» hiess, ohne dass ihn jemand abgelöst hatte
    – und der nur über denselben Knopf wieder zurückkam, den es nicht mehr gibt.

    *Der Vorgänger dieses Wächters prüfte den **Standardwert** der Spalte gegen die
    Statusliste (ORM- und Server-Default waren einmal auseinandergelaufen). Diese Frage
    stellt sich nicht mehr: ohne Spalte gibt es keinen Default, der veralten könnte.*
    """
    import pathlib
    import re

    from app.domain import statuses as st
    from app.models import Article

    assert "status" not in Article.__table__.c, (
        "``articles.status`` ist wieder eine Spalte – damit gibt es die zweite Aussage "
        "über dieselbe Sache zurück. Der Zustand gehört als Projektion an "
        "``replaced_by_id`` (``Article.status``)."
    )
    assert isinstance(getattr(Article, "status", None), property), (
        "``Article.status`` ist keine Ableitung mehr – ohne sie beantwortet jede Ansicht "
        "die Frage «ausser Betrieb?» selbst, und beim nächsten Leser anders."
    )

    class _Fake:
        replaced_by_id = None

    assert Article.status.fget(_Fake()) == st.FREIGEGEBEN
    _Fake.replaced_by_id = 100000001
    assert Article.status.fget(_Fake()) == st.INAKTIV

    # Und **kein** Modul spricht die alte **Artikel**-Status-Sprache. Gesucht wird
    # ausdrücklich nach dem Subjekt: ``draft`` ist als *Auftrags*-Zustand weiterhin ein
    # gültiges Wort, und ein Wächter, der beides in einen Topf wirft, meldet Falsches und
    # wird dafür stillgelegt.
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


def test_out_of_service_is_written_at_exactly_one_place():
    """►►► **Ausser Betrieb geht ein Artikel auf genau EINEM Weg: durch Ersetzen.** ◄◄◄

    Es gibt keinen Schalter, kein Feld und keinen Endpunkt dafür. Der Wächter liest den
    Quelltext, weil genau das die Form ist, in der ein zweiter Weg zurückkommt: eine
    Zuweisung an ``status`` irgendwo, ein ``status``-Feld in ``ArticleUpdate``, ein
    ``PATCH``, der ihn durchreicht.

    Bug-Form: mit dem alten Knopf meldet er ``ArticleUpdate`` **und** die Zuweisung in
    ``apply_replacement`` – gegengeprüft.
    """
    import pathlib
    import re

    from app.schemas.article import ArticleUpdate

    assert "status" not in ArticleUpdate.model_fields, (
        "``ArticleUpdate`` nimmt wieder einen Status entgegen – damit gibt es den zweiten "
        "Weg zurück, ausser Betrieb zu nehmen."
    )

    # **Gesucht wird in den Dateien, die den Artikel besitzen** – und nach der *Form*
    # einer Zuweisung, nicht nach einem Variablennamen. Der Vorgänger fragte nach
    # ``*article*.status =`` und liess damit ausgerechnet die Zeile durch, um die es geht:
    # sie heisst ``predecessor.status = …`` (gemessen, gegengeprüft, nachgeschärft).
    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    owners = ("services/articles.py", "routers/articles.py", "services/bom.py",
              "models/article.py")
    setter = re.compile(r"^\s*\w+\.status\s*=\s*[^=]", re.M)
    hits = [
        f"{rel}: {m.group(0).strip()}"
        for rel in owners
        for m in setter.finditer((app / rel).read_text(encoding="utf-8"))
    ]
    assert not hits, (
        "Der Artikel-Zustand wird wieder geschrieben – er ist abgeleitet:\n  "
        + "\n  ".join(hits)
    )
