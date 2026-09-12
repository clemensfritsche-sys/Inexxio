"""**Ein abgeschlossenes Modul zeigt lückenlos, was in ihm passiert ist.**

> Feste Regel für **alle** Module, heute und künftig (Testnotiz #717).

Und darum steht sie an genau **einer** Stelle: ``services/record.py`` liest den
Ereignis-Log, und den schreibt jedes Modul über dieselbe eine Schreibstelle
(``process._pass``). Ein Protokoll je Modultyp wäre dieselbe Ansicht n-mal – und die
(n+1)-te fehlte beim nächsten Typ. Genau die Sorte Lücke, die man erst bemerkt, wenn
jemand einen Nachweis braucht.

Geprüft wird über die **echten** Dienstpfade gegen echtes PostgreSQL; jede Regel steht
gegen ihre **Bug-Form**.
"""

import ast
import pathlib

import pytest

from tests.runner import session
from tests.scenarios import World, free_stock

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _w() -> World:
    try:
        return World(session())
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}).")


def _record(w: World, order, step, **kw):
    from app.services import record

    return record.step_record(w.db, order, step, **kw)


# ---------------------------------------------------------------------------
# Die Regel ist ZENTRAL – nicht je Modultyp
# ---------------------------------------------------------------------------

def test_the_record_is_derived_at_exactly_one_place():
    """**Zentral bauen, nicht pro Modultyp** – ein neuer Typ erbt es ohne eine Zeile.

    Geprüft wird die **Form**: die Ableitung existiert einmal, sie liest den Log (nicht
    den heutigen Zustand), und kein Modul- oder Modultyp-File baut sich ein eigenes
    Protokoll. Ein zweites wäre nicht falsch, es wäre nur unvollständig – und das fällt
    erst auf, wenn es zählt.
    """
    src = (BACKEND / "app" / "services" / "record.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "step_record" in names, "Die eine Ableitung fehlt."

    # **Gelesen wird der LOG.** Aus dem heutigen Zustand liesse sich nicht ableiten, was
    # gemessen wurde – nur, was daraus geworden ist.
    assert "ProcessEvent" in src and "KIND_CAPTURE" in src and "KIND_STEP" in src, (
        "Das Protokoll liest nicht mehr den Ereignis-Log – dann ist es eine zweite "
        "Wahrheit statt einer Ansicht."
    )

    # **Kein zweites Protokoll.** Weder in den Modulen noch in den Erfassungstypen.
    for folder in ("modules", "capture_types"):
        for path in (BACKEND / "app" / "domain" / folder).glob("*.py"):
            body = path.read_text(encoding="utf-8")
            assert "step_record" not in body and "def record(" not in body, (
                f"{path.name} baut sich ein eigenes Protokoll – dann gibt es die Regel "
                f"n-mal, und beim nächsten Modultyp fehlt sie."
            )


# ---------------------------------------------------------------------------
# Vollständig – jede Angabe, je Einzelinstanz
# ---------------------------------------------------------------------------

def test_a_finished_module_shows_every_value_per_piece():
    """**Lückenlos** heisst: jedes gezogene Stück, jeder Punkt, mit seiner **Frage**.

    Ein Nachweis, der nur den Schlüssel nennt (``t1: 42``), ist keiner – man liest ihn
    nur mit der Definition daneben. Und er nennt, **wer** wann bestätigt hat und **wie**
    (Kamera ↔ Tastatur): ohne den Vermerk wäre die Tastatur hinterher nicht von der
    Kamera zu unterscheiden (§4.4).
    """
    w = _w()
    try:
        points = [
            {"label": "Länge", "type": "measure", "target": 10, "tolerance": 1,
             "unit": "mm"},
            {"label": "Sauber?", "type": "bool"},
        ]
        art = w.article(serialization="unit", template=[w.capture(points=points)])
        order = w.produce(art, 2)
        step = w.steps(order)[0]
        # Die Schlüssel kommen aus der **Definition** – sie selbst zu bilden wäre ein
        # zweiter Massstab neben ``capture_types.clean_points``.
        keys = [p["key"] for p in (step.config or {}).get("points") or []]
        w.run_step(order, step, values={keys[0]: 10, keys[1]: True})

        entries, total = _record(w, order, step)
        assert total == 2, f"Zwei Stücke, zwei Vorgänge – gezählt wurden {total}."
        assert {e.number for e in entries} == set(w.numbers(order))

        for e in entries:
            assert [v.label for v in e.values] == ["Länge", "Sauber?"], (
                "Die Werte stehen ohne ihre Frage da – dann liest man sie nur mit der "
                "Definition in der Hand."
            )
            assert [v.value for v in e.values] == [10, True]
            assert [v.ok for v in e.values] == [True, True]
            assert e.verification == "scan", "Wie bestätigt wurde, steht nicht im Protokoll."
            assert e.result == "passed"
            assert e.status_after, "Der Zustand nach dem Vorgang fehlt."
            assert e.at is not None
    finally:
        w.db.close()


def test_a_repetition_is_a_second_entry_not_an_overwrite():
    """**Ein Eintrag ist ein VORGANG, kein Stück** – der Log ist append-only.

    Nach einem «nicht bestanden» wird erneut erfasst; **beides ist passiert**. Wer je
    Stück zusammenfasst, überschreibt damit die Vergangenheit – und ausgerechnet der
    interessante Teil (die durchgefallene Messung) verschwindet.

    **Die Bug-Form daneben:** ein Protokoll, das nach Stück gruppiert, meldete hier
    genau einen Eintrag mit dem Urteil «bestanden».
    """
    w = _w()
    try:
        art = w.article(serialization="batch", template=[w.capture()])
        order = w.produce(art, 1)
        step = w.steps(order)[0]
        instance = w.instances(order)[0]

        w.confirm(order, step, instance=instance, values=w.BAD)
        w.confirm(order, step, instance=instance, values=w.GOOD)

        entries, total = _record(w, order, step)
        assert total == 2, (
            f"Erfasst wurde zweimal, im Protokoll stehen {total} Vorgänge – die "
            f"Wiederholung hat die Vergangenheit überschrieben."
        )
        assert [e.result for e in entries] == ["failed", "passed"], (
            "Die durchgefallene Messung fehlt oder steht in der falschen Reihenfolge."
        )

        # Der erste Vorgang rückte NICHTS vor – genau das heisst «nicht bestanden».
        assert entries[0].status_after is None, (
            "Der durchgefallene Vorgang behauptet einen Nachher-Zustand."
        )
        assert entries[1].status_after, "Der bestandene Vorgang rückte nicht vor."
    finally:
        w.db.close()


def test_what_ran_through_without_capture_is_visible():
    """Der **ungezogene Rest** läuft ohne Erfassung durch – sichtbar, nicht stillschweigend.

    Er hat keinen ``capture``-Eintrag; ihn deshalb wegzulassen hiesse, ein Stück aus dem
    Nachweis zu entfernen, das sehr wohl durch das Modul gegangen ist (§9.3).
    """
    w = _w()
    try:
        # Eine **Charge**: ein Scan, vier Stücke, zwei davon gezogen. Genau der Fall, für
        # den «je Instanz ein Vorgang, je Stück ein Wertesatz» gebaut ist (§9.5).
        art = w.article(serialization="batch",
                        template=[w.capture(sample={"percent": 50})])
        order = w.produce(art, 4)
        step = w.steps(order)[0]
        w.run_step(order, step)

        entries, total = _record(w, order, step)
        assert total == 4, f"Vier Stücke gingen hindurch, protokolliert sind {total}."
        drawn = [e for e in entries if e.sampled]
        rest = [e for e in entries if not e.sampled]
        assert len(drawn) == 2 and len(rest) == 2, (
            f"Die Ziehung ist im Protokoll nicht ablesbar ({len(drawn)} gezogen, "
            f"{len(rest)} durchgelaufen)."
        )
        assert all(not e.values for e in rest), (
            "Ein nicht gezogenes Stück trägt Werte – die hat niemand erhoben."
        )
        assert all(e.status_after for e in rest), (
            "Der ungezogene Rest ist nicht vorgerückt – dann lief er nicht durch."
        )
    finally:
        w.db.close()


# ---------------------------------------------------------------------------
# JEDES Modul erbt es – auch eines ohne Erfassungspunkte
# ---------------------------------------------------------------------------

def test_a_module_without_capture_points_has_a_record_too():
    """**Aussondern** erfasst nichts – und hat trotzdem ein Protokoll.

    Der Scan IST dort die Bestätigung; erfasst wird kein Wert. Ein Protokoll, das an den
    Erfassungspunkten hinge, wäre hier leer – dabei ist «wer hat wann was verschrottet»
    der Nachweis, auf den es bei einem Ausgang am meisten ankommt.
    """
    w = _w()
    try:
        art = w.article(serialization="unit",
                        template=[w.dispose("scrap", "Sichtprüfung")])
        order = w.produce(art, 2)
        step = w.steps(order)[0]
        w.run_step(order, step)

        entries, total = _record(w, order, step)
        assert total == 2, f"Zwei Stücke ausgesondert, protokolliert sind {total}."
        assert all(e.values == [] for e in entries)
        assert {e.status_after for e in entries} == {"verschrottet"}, (
            "Der Nachher-Zustand fehlt – dann sagt das Protokoll nicht, was geschah."
        )
        assert all(e.verification == "scan" for e in entries)
    finally:
        w.db.close()


def test_the_consumption_record_says_into_which_piece():
    """**Verbrauch**: dieselbe Ansicht, und sie nennt das Ziel.

    Wohin eine Komponente ging, steht im Payload des Übergangs (``into``) – das ist die
    Genealogie, und sie ist damit ohne ein zusätzliches Feld im Protokoll ablesbar. Das
    ist zugleich der Beleg, dass die Regel wirklich zentral sitzt: das Verbrauchsmodul
    hat für sein Protokoll keine Zeile geschrieben.
    """
    w = _w()
    try:
        part, numbers = free_stock(w, serialization="unit", quantity=2)
        product = w.article(serialization="unit",
                            template=[w.consume((part.object_id, 1))])
        order = w.release(lines=[{
            "article_object_id": product.object_id, "quantity": 2, "origin": "neu",
            "units": [],
        }])
        step = w.steps(order)[0]
        w.run_step(order, step)

        entries, _ = _record(w, order, step)
        built = [e for e in entries if e.into]
        assert len(built) == 2, (
            f"{len(built)} von 2 Komponenten nennen das Stück, in das sie gingen – ohne "
            f"das ist die Stückliste im Nachhinein nicht mehr lesbar."
        )
        assert {e.number for e in built} == set(numbers)
        # Die Erzeugnisse sind die Stücke des Auftrags **ohne** die Komponenten – die
        # sind mit dem Verbrauch ebenfalls seine geworden.
        products = set(w.numbers(order)) - set(numbers)
        assert {e.into for e in built} == products, (
            "Die Ziel-Nummern stimmen nicht mit den Erzeugnissen überein."
        )
    finally:
        w.db.close()


# ---------------------------------------------------------------------------
# Nie alles auf einmal
# ---------------------------------------------------------------------------

def test_the_record_is_paged_and_says_how_many_there_are():
    """Bei einer 6000er-Charge sind es tausende Vorgänge.

    Gekappt wird, aber nicht verschwiegen: die Gesamtzahl steht daneben. Ein stiller
    Deckel läse sich wie Vollständigkeit – und das ist bei einem **Nachweis** die
    gefährlichste Form einer Lücke.
    """
    w = _w()
    try:
        art = w.article(serialization="unit", template=[w.capture()])
        order = w.produce(art, 5)
        step = w.steps(order)[0]
        w.run_step(order, step)

        page, total = _record(w, order, step, limit=2)
        assert total == 5 and len(page) == 2, (
            f"Die Seitenzählung stimmt nicht ({len(page)} von {total})."
        )
        rest, again = _record(w, order, step, limit=2, offset=2)
        assert again == 5 and len(rest) == 2
        assert {e.number for e in page}.isdisjoint({e.number for e in rest}), (
            "Zwei Seiten zeigen dieselben Vorgänge."
        )
    finally:
        w.db.close()


# ---------------------------------------------------------------------------
# Testnotiz #726 – ein Zustand, der sich nicht ändert, ist keine Aussage
# ---------------------------------------------------------------------------

def test_a_pass_through_module_shows_no_state_but_an_exit_does():
    """**Der Nachher-Zustand steht da, wenn er ein ANDERER ist – sonst nicht.**

    Ein Durchläufer (Datenerfassung, Bewegen) führt ``Im Prozess`` → ``Im Prozess``: in
    jeder Zeile des Protokolls stand dasselbe Wort, und was in jeder Zeile gleich lautet,
    ist keine Information. Bei einem **Ausgang** ist es umgekehrt – dort ist der Zustand
    genau das, was der Vorgang bewirkt hat.

    Beides ist **eine** Regel, nicht zwei: ``status_after`` trägt die Änderung. Damit
    fällt der Fall «nicht bestanden» (nichts rückte vor) ohne Zutun in dieselbe Antwort.
    """
    w = _w()
    try:
        # (a) Durchläufer – kein Zustand im Protokoll.
        art = w.article(serialization="unit", template=[w.capture()])
        order = w.produce(art, 2)
        step = w.steps(order)[0]
        w.run_step(order, step)
        entries, _total = _record(w, order, step)
        assert entries, "Ohne Einträge prüft der Wächter nichts."
        assert all(e.status_before == e.status_after for e in entries), (
            "Die Datenerfassung verändert den Zustand – dann ist die Prämisse dieses "
            "Wächters falsch."
        )
        # **Beide Werte stehen da.** Die Anzeige bildet die Differenz; nur den einen zu
        # liefern hiesse, «vorgerückt» und «nichts geändert» wären dasselbe.
        assert all(e.status_after for e in entries), (
            "Der Nachher-Zustand fehlt – dann ist im Protokoll nicht mehr ablesbar, ob "
            "der Vorgang durchging."
        )

        # (b) Ausgang – dort ist der Zustand die Aussage und bleibt.
        art2 = w.article(serialization="unit",
                         template=[w.dispose("scrap", "Sichtprüfung")])
        order2 = w.produce(art2, 1)
        step2 = w.steps(order2)[0]
        w.run_step(order2, step2)
        entries2, _t2 = _record(w, order2, step2)
        assert {e.status_after for e in entries2} == {"verschrottet"}, (
            "Beim Aussondern ist der Zustand die Aussage – er darf nicht mitentfallen."
        )
        assert all(e.status_before != e.status_after for e in entries2), (
            "Ein Ausgang ändert den Zustand – sonst wäre er keiner."
        )
    finally:
        w.db.close()
