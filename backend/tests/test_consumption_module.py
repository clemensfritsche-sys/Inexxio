"""**Der Wächter des Verbrauchsmoduls** – der Zwilling des Aussonderns.

Geprüft wird über die **echten** Dienstpfade (``process.release`` / ``confirm_step``)
gegen echtes PostgreSQL, nie über nachgestellte Zustände. Jede Regel steht hier gegen
ihre **Bug-Form**: ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu
unterscheiden.
"""

import pytest

from tests.runner import session
from tests.scenarios import World, free_stock


def _w() -> World:
    try:
        return World(session())
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}).")


def _assembly(w: World, *, parts: int = 2, after=None):
    """Der Normalfall: ein Produkt (Neu) und ``parts`` Komponenten (Lager)."""
    part, numbers = free_stock(w, serialization="unit", quantity=parts)
    template = [w.consume(part.object_id)] + list(after or [])
    product = w.article(serialization="unit", template=template)
    order = w.release(lines=[
        {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
         "units": []},
        {"article_object_id": part.object_id, "quantity": parts, "origin": "lager",
         "units": [{"number": n, "from_order": None} for n in numbers]},
    ])
    return part, numbers, product, order


# ---------------------------------------------------------------------------
# §2.2 – terminal je Zeile, ohne die Kettenregel zu verletzen
# ---------------------------------------------------------------------------

def test_the_module_is_no_exit_so_something_may_stand_behind_it():
    """►►► **Die Kettenregel bleibt unangetastet.** ◄◄◄

    ``Module.terminal`` beantwortet genau eine Frage: *verlassen ALLE ankommenden Stücke
    den Auftrag hier?* Beim Verbrauch lautet die Antwort **nein** – die Komponenten
    gehen, das Produkt läuft weiter. Also ist er kein Ausgang, und hinter ihm darf sehr
    wohl ein Modul stehen.

    Wäre er terminal (die naheliegende, falsche Abkürzung), wiese ``chain.assert_closes``
    ein Modul dahinter ab – und damit wäre die Montage genau um den Schritt beschnitten,
    der auf sie folgt: die Endprüfung.
    """
    from app.domain import chain, modules

    assert modules.get("verbrauch").terminal is False
    # Ein Modul HINTER dem Verbrauch ist erlaubt …
    chain.assert_closes([
        {"module_type": "verbrauch", "status_before": "im_prozess",
         "status_after": "im_prozess"},
        {"module_type": "datenerfassung", "status_before": "im_prozess",
         "status_after": "im_prozess"},
    ])
    # … hinter einem echten Ausgang nicht. Die Regel selbst ist unverändert scharf.
    with pytest.raises(Exception):
        chain.assert_closes([
            {"module_type": "aussondern", "status_before": "im_prozess",
             "status_after": "verschrottet"},
            {"module_type": "datenerfassung", "status_before": "im_prozess",
             "status_after": "im_prozess"},
        ])


def test_the_named_articles_leave_and_the_product_walks_on():
    """**Zwei Gruppen mit gleichem Ziel** – genannte Artikel hinaus, Rest weiter.

    Und das Modul steht **nicht** am Schluss: dahinter liegt eine Datenerfassung, die das
    Produkt noch durchläuft. Genau daran zeigt sich, dass die Teilung je Stück wirkt und
    nicht je Modul.
    """
    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=2, after=[w.capture()])
        w.run_all(order, values=World.GOOD)
        made = [n for n in w.numbers(order) if n not in numbers]

        assert [w.unit_status(n) for n in numbers] == ["verbaut", "verbaut"]
        assert len(made) == 1 and w.unit_status(made[0]) == "freigegeben", (
            "Das Produkt hat den Auftrag nicht regulär über das Ende-Objekt verlassen."
        )
        assert w.status(order) == "abgeschlossen"
        assert w.problems(order) == []
    finally:
        w.db.rollback()
        w.db.close()


def test_the_picture_puts_the_consumed_pieces_at_their_module():
    """**Wer hier hinausging, steht hier** – nicht auf der Kante hinter dem Ende.

    Das ist die dritte Wirkung, die beim Aussondern schon einmal gefehlt hat: die Stücke
    landeten hinter dem Ende, und die Invariantenprüfung meldete zu Recht «dort stehen
    Einzelinstanzen, aber die Kante gilt als nicht gegangen».

    Beim Verbrauch wäre derselbe Fehler schlimmer, weil er **unauffällig** ist: das
    Ende-Objekt existiert ja, die Kante gilt als gegangen (das Produkt ging dort hinaus) –
    die verbauten Stücke stünden also stillschweigend an einer Stelle, die sie nie
    passiert haben.
    """
    from app.services import flow

    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=2)
        step_id = w.steps(order)[0].id
        w.run_all(order, values=World.GOOD)
        g = w.graph(order)

        assert g.problems == [], g.problems
        gone = next(e for e in g.edges if e.id == f"edge:exit:{step_id}")
        assert sum(p.count for p in gone.units) == 2 and gone.walked
        end = next(e for e in g.edges if e.id == "edge:end:done")
        assert sum(p.count for p in end.units) == 1, (
            "Am Ende steht mehr als das Produkt – Verbautes ist dort nie angekommen."
        )
        # Gegenprobe zur Bug-Form: läse das Bild «geschlossen und ohne Punkt» als
        # «angekommen», stünden alle drei am Ende.
        assert flow._exit_points(w.db, order.id), (
            "Ohne die Ableitung aus dem Log gäbe es die Ausgangs-Kante gar nicht."
        )
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# §6 – «Verbaut» ist nicht terminal
# ---------------------------------------------------------------------------

def test_built_in_is_reversible_scrapped_is_not():
    """**Demontage ist real** – das Greifen IST der Ausbau, wie beim Sperren.

    Und die Gegenprobe steht daneben: ``Verschrottet`` bleibt der einzige endgültige
    Zustand, samt Schutz in der Datenbank.
    """
    from app.domain import statuses as st

    assert st.is_terminal(st.VERBAUT) is False
    assert st.is_selectable(st.VERBAUT) is True
    assert st.stock_kind(st.VERBAUT) == st.HISTORY, (
        "Ein verbautes Stück liegt nicht im Regal – als Bestand geführt wäre es Material, "
        "das niemand greifen kann."
    )
    assert st.is_terminal(st.VERSCHROTTET) is True
    assert st.VERBAUT not in st.TERMINAL_UNIT_STATUSES

    w = _w()
    try:
        part, numbers, _, build = _assembly(w, parts=1)
        w.run_all(build, values=World.GOOD)
        assert w.unit_status(numbers[0]) == "verbaut"

        strip = w.take(part, [numbers[0]], steps=[w.capture()])
        assert w.is_deviation(strip), (
            "Ein Ausbau greift auf Material zu, das nicht frei verfügbar war – das ist "
            "genau die Definition einer Abweichung und muss ohne Zutun so ausgewiesen sein."
        )
        w.run_all(strip, values=World.GOOD)
        assert w.unit_status(numbers[0]) == "freigegeben"
    finally:
        w.db.rollback()
        w.db.close()


def test_the_parts_list_survives_the_removal():
    """►►► **Die Stückliste kommt aus dem LOG, nicht aus dem Zustand.** ◄◄◄

    Das ist die Bedingung, unter der «nicht terminal» ungefährlich ist. Läse die
    Ableitung ``InstanceUnit.status``, verschwände ein ausgebautes Teil **rückwirkend**
    aus der Vergangenheit des Produkts – und ein Nachweis, der sich nachträglich ändert,
    ist keiner (dieselbe Regel wie im Prozessbild, §8.1a).

    Die Bug-Form steht als Gegenprobe darunter: nach dem Ausbau trägt kein einziges Stück
    mehr den Zustand ``verbaut``.
    """
    from app.domain import statuses as st
    from app.services import genealogy

    w = _w()
    try:
        part, numbers, _, build = _assembly(w, parts=2)
        w.run_all(build, values=World.GOOD)
        made = [n for n in w.numbers(build) if n not in numbers][0]
        assert len(genealogy.parts_of(w.db, w.unit(made))) == 2

        strip = w.take(part, [numbers[0]], steps=[w.capture()])
        w.run_all(strip, values=World.GOOD)

        parts = genealogy.parts_of(w.db, w.unit(made))
        assert len(parts) == 2, "Die Stückliste hat ein ausgebautes Teil verloren."
        by_number = {p["number"]: p for p in parts}
        assert by_number[numbers[0]]["still_in"] is False
        assert by_number[numbers[1]]["still_in"] is True

        # Die Bug-Form, ausgeschrieben: über den heutigen Zustand gelesen wäre die Liste
        # jetzt um genau dieses Teil kürzer.
        still = [n for n in numbers if w.unit_status(n) == st.VERBAUT]
        assert still == [numbers[1]]
    finally:
        w.db.rollback()
        w.db.close()


def test_a_component_names_what_it_was_built_into():
    """Die Gegenrichtung: **worin steckt dieses Stück?** – mit dem Auftrag dazu.

    Der Auftrag steht immer dabei, weil die Zuordnung über ihn läuft: bei mehreren
    Erzeugnissen in einem Auftrag ist er die genauere Aussage.
    """
    from app.services import genealogy

    w = _w()
    try:
        part, numbers, _, build = _assembly(w, parts=1)
        w.run_all(build, values=World.GOOD)
        made = [n for n in w.numbers(build) if n not in numbers][0]

        hosts = genealogy.built_into(w.db, w.unit(numbers[0]))
        assert len(hosts) == 1 and hosts[0]["order_object_id"] == build.object_id
        assert [p["number"] for p in hosts[0]["products"]] == [made]
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# Konfiguration – was die Freigabe abweist
# ---------------------------------------------------------------------------

def test_a_consumption_without_material_is_refused():
    """Ein Verbrauchsmodul, dessen Artikel im Auftrag fehlt, ist ein **stiller Durchgang**.

    Es sähe aus wie eine Montage und wäre keine – der Fehler kommt darum bei der
    Freigabe, also bevor eine Objektnummer vergeben ist.
    """
    from fastapi import HTTPException

    w = _w()
    try:
        other, _ = free_stock(w, serialization="unit", quantity=1)
        product = w.article(serialization="unit",
                            template=[w.consume(other.object_id)])
        with pytest.raises(HTTPException) as exc:
            w.release(lines=[{"article_object_id": product.object_id, "quantity": 1,
                              "origin": "neu", "units": []}])
        assert exc.value.status_code == 400
        assert str(other.object_id) in str(exc.value.detail), (
            "Die Meldung nennt den fehlenden Artikel nicht – dann sucht der Mensch."
        )
    finally:
        w.db.rollback()
        w.db.close()


def test_the_product_cannot_consume_itself():
    """Derselbe Artikel als ``Neu`` **und** als Verbrauch: das Produkt verliesse den
    Auftrag an seinem eigenen Montageschritt.

    Das ist die Kehrseite davon, dass die Konfiguration **Artikel** trifft und nicht
    Zeilen – die eine Stelle, an der diese Körnung zu grob ist, wird darum abgewiesen
    statt stillschweigend falsch gerechnet.
    """
    from fastapi import HTTPException

    w = _w()
    try:
        product = w.article(serialization="unit")
        product_steps = [w.consume(product.object_id)]
        art = w.article(serialization="unit", template=product_steps)
        with pytest.raises(HTTPException) as exc:
            w.release(lines=[{"article_object_id": art.object_id, "quantity": 1,
                              "origin": "neu", "units": []}])
        assert exc.value.status_code == 400
    finally:
        w.db.rollback()
        w.db.close()


def test_a_consumption_module_needs_at_least_one_article():
    """Ohne Artikel gäbe es nichts zu verbauen – der Fehler kommt beim **Anlegen**."""
    from fastapi import HTTPException

    from app.domain import modules

    with pytest.raises(HTTPException) as exc:
        modules.get("verbrauch").clean_config({"articles": []})
    assert exc.value.status_code == 400


def test_at_most_one_new_line_not_new_alone():
    """►►► **Die Regel heisst «höchstens EINE Neu-Zeile».** ◄◄◄

    Sie hiess einmal «Neu steht für sich allein» – und verbot damit ausgerechnet die
    Auftragsform, die eine Montage ist. Der ursprüngliche Grund (ein Auftrag hat **einen**
    Erzeugungsprozess) bleibt vollständig gewahrt: zwei Vorlagen sind weiterhin ein
    harter Fehler.
    """
    from fastapi import HTTPException

    w = _w()
    try:
        a1, n1 = free_stock(w, serialization="unit", quantity=1)
        a2 = w.article(serialization="unit")
        # Neu + Lager: erlaubt (die Montage).
        w.release(lines=[
            {"article_object_id": a2.object_id, "quantity": 1, "origin": "neu",
             "units": []},
            {"article_object_id": a1.object_id, "quantity": 1, "origin": "lager",
             "units": [{"number": n1[0], "from_order": None}]},
        ])
        # Zwei Neu-Zeilen: welche Vorlage gälte?
        a3 = w.article(serialization="unit")
        with pytest.raises(HTTPException) as exc:
            w.release(lines=[
                {"article_object_id": a2.object_id, "quantity": 1, "origin": "neu",
                 "units": []},
                {"article_object_id": a3.object_id, "quantity": 1, "origin": "neu",
                 "units": []},
            ])
        assert exc.value.status_code == 400
    finally:
        w.db.rollback()
        w.db.close()
