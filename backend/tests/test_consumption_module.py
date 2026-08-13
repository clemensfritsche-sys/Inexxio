"""**Der Wächter des Verbrauchsmoduls** – Stückliste, Bindung, Nichtverfügbarkeit.

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


def _assembly(w: World, *, parts: int = 2, per_unit: int = 1, products: int = 1,
              after=None):
    """Der Normalfall: ein Produkt (Neu), die Komponenten liegen **frei am Lager**.

    Sie stehen ausdrücklich **nicht** im Bedarf: das Modul holt sie sich, wenn es dran
    ist (§2). Genau daran hängt die halbe Datei.
    """
    part, numbers = free_stock(w, serialization="unit", quantity=parts)
    template = [w.consume((part.object_id, per_unit))] + list(after or [])
    product = w.article(serialization="unit", template=template)
    order = w.release(lines=[
        {"article_object_id": product.object_id, "quantity": products, "origin": "neu",
         "units": []},
    ])
    return part, numbers, product, order


# ---------------------------------------------------------------------------
# §2 – gebunden wird beim ERREICHEN, nicht bei der Freigabe
# ---------------------------------------------------------------------------

def test_components_are_bound_when_the_module_is_reached():
    """►►► **Der zweite Eintrittspunkt.** ◄◄◄

    Bis hierher hing der Eintritt fest am **Start-Objekt**: ``release`` legte die
    Zugehörigkeiten an und schrieb den ``start``-Eintrag. Eine Komponente, die schon dort
    gebunden würde, wäre für jeden anderen Auftrag gesperrt, solange die Montage läuft –
    obwohl sie im Regal liegt.

    Geprüft wird beides, und zwar in der Reihenfolge, in der es passiert:

    1. **Nach der Freigabe ist die Komponente unberührt** – ``Freigegeben``, keine
       Auftragszeile, kein Log-Eintrag. Sie ist frei greifbar.
    2. **Nach dem Modul ist sie ``Verbaut``** und trägt genau den Weg aus §2:
       ``Freigegeben`` → (``start`` am Modul) → ``Im Prozess`` → (``step``) → ``Verbaut``.

    Die Bug-Form daneben: der ``start``-Eintrag der Komponente trägt die **Modul-id**.
    Trüge er ``NULL``, wäre er vom Eintritt am Start-Objekt nicht zu unterscheiden – und
    das Bild rechnete sie in die erste Kante ein, die sie nie passiert hat.
    """
    from app.models import OrderUnit, ProcessEvent

    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=1)
        step = w.steps(order)[0]

        assert w.unit_status(numbers[0]) == "freigegeben"
        unit = w.unit(numbers[0])
        assert w.db.query(OrderUnit).filter(
            OrderUnit.instance_unit_id == unit.id,
            OrderUnit.order_id == order.id).count() == 0, (
            "Die Komponente wurde schon bei der Freigabe gebunden."
        )

        w.run_all(order)
        assert w.unit_status(numbers[0]) == "verbaut"

        trail = (
            w.db.query(ProcessEvent)
            .filter(ProcessEvent.order_id == order.id,
                    ProcessEvent.instance_unit_id == unit.id)
            .order_by(ProcessEvent.id).all()
        )
        assert [(e.kind, e.status_before, e.status_after) for e in trail] == [
            ("start", "freigegeben", "im_prozess"),
            ("step", "im_prozess", "verbaut"),
        ]
        assert trail[0].step_id == step.id, (
            "Der Eintritt trägt kein Modul – er wäre vom Start-Objekt nicht zu "
            "unterscheiden."
        )
    finally:
        w.db.rollback()
        w.db.close()


def test_the_start_edge_does_not_carry_what_entered_at_a_module():
    """**Das Start-Objekt hat passiert, wer oben hereinkam.**

    Die Kehrseite des zweiten Eintrittspunkts, und sie sitzt im Bild: ``_tally.started``
    zählt die ``start``-Einträge. Zählte es auch die am Modul mit, trüge die erste Kante
    Material, das dort nie war – und die Bilanz entlang der Achse ginge nicht mehr auf.
    """
    from app.services import flow

    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=2, per_unit=2)
        w.run_all(order)

        tally = flow._tally(w.db, order.id)
        assert tally.started == 1, (
            "Die Komponenten sind in die erste Kante gerechnet worden."
        )
        assert w.problems(order) == [], w.problems(order)
    finally:
        w.db.rollback()
        w.db.close()


def test_a_line_nobody_walked_stays_a_hairline():
    """**Wer hier hinausging, ist nicht weitergelaufen** – die zweite Hälfte im Bild.

    ``passed`` zählt die ``step``-Einträge eines Moduls, und die schreibt auch, wer den
    Auftrag dort **verlässt**. Ohne Korrektur stünde die Bilanz hinter einem
    Verbrauchsmodul auf «Produkt + Komponenten»; nimmt danach eine Abweichung **alle**
    Produkte mit, bliebe eine **kräftige Linie, auf der niemand steht**.

    Das ist genau der Fehler, den die Invariantenprüfung nicht findet: sie meldet Stücke
    auf einer Haarlinie, nicht eine Haarlinie ohne Stücke. Er sähe also nach einem
    gelaufenen Weg aus, den niemand genommen hat.
    """
    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=2, per_unit=2,
                                            after=[w.capture()])
        build = w.steps(order)[0]
        w.run_step(order, build)
        made = [n for n in w.numbers(order) if n not in numbers]

        # Die Abweichung nimmt das Produkt mit – auf der Achse bleibt nichts.
        w.take(_article_of(w, made[0]), [made[0]], steps=[w.capture()],
               from_order=order.object_id, returns=False)

        g = w.graph(order)
        assert g.problems == [], g.problems
        bypass = [e for e in g.edges if e.frm.startswith("fork:") and e.kind == "axis"]
        assert bypass, "Ohne Abzweigepunkt prüft dieser Wächter nichts."
        assert all(not e.walked and not e.members for e in bypass), (
            "Der gerade Weg gilt als gegangen, obwohl ihn niemand genommen hat."
        )
    finally:
        w.db.rollback()
        w.db.close()


def _article_of(w: World, number: str):
    """Der Artikel, zu dem diese Stücknummer gehört."""
    from app.models import Article, Instance

    unit = w.unit(number)
    instance = w.db.query(Instance).filter(Instance.id == unit.instance_id).first()
    return w.db.query(Article).filter(Article.id == instance.article_id).first()


# ---------------------------------------------------------------------------
# §1 – die Menge gilt JE STÜCK, gerechnet beim Erreichen
# ---------------------------------------------------------------------------

def test_the_quantity_is_per_piece_and_counted_when_the_module_is_reached():
    """**«4× Schraube» heisst vier je Getriebe, nicht vier im Auftrag.**

    Und gerechnet wird beim **Erreichen**: die Zahl der Produkte steht beim Definieren
    nicht fest. Eine Vorlage, die eine Auftragsmenge nennt, ist bei der zweiten Menge
    falsch – und zwar stillschweigend.
    """
    from app.services import consumption

    w = _w()
    try:
        screw, numbers = free_stock(w, serialization="batch", quantity=20)
        product = w.article(serialization="unit",
                            template=[w.consume((screw.object_id, 4))])
        order = w.release(lines=[
            {"article_object_id": product.object_id, "quantity": 3, "origin": "neu",
             "units": []},
        ])
        step = w.steps(order)[0]
        need = consumption.needs(w.db, step, pieces=3)[0]
        assert (need.per_unit, need.required) == (4, 12)

        w.run_all(order)
        assert len([n for n in numbers if w.unit_status(n) == "verbaut"]) == 12
        assert len([n for n in numbers if w.unit_status(n) == "freigegeben"]) == 8
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# §3 – die Zuordnung steht im LOG, je Produkt-Stück
# ---------------------------------------------------------------------------

def test_every_product_piece_gets_its_own_parts_list():
    """►►► **Exakte Genealogie ohne ``into_instance_id``.** ◄◄◄

    Der Log gibt die Zuordnung nicht von selbst her – zwischen «diese zwölf Schrauben
    gingen in diesem Auftrag hinaus» und «diese vier gingen in dieses Getriebe» liegt
    genau eine Angabe. Sie steht im **Payload** des ``verbaut``-Eintrags (``into``), also
    dort, wo der Log ohnehin festhält, was ein Modul festgehalten hat.

    Das ist **kein Ersatzfeld**: ein ``into_instance_id`` an der Einzelinstanz wäre eine
    zweite Wahrheit, die bei der Demontage geleert würde – womit die Vergangenheit des
    Getriebes verschwände.

    Die Bug-Form daneben: über den Auftrag gelesen bekäme **jedes** Getriebe alle zwölf.
    """
    from app.services import genealogy

    w = _w()
    try:
        screw, numbers = free_stock(w, serialization="batch", quantity=12)
        product = w.article(serialization="unit",
                            template=[w.consume((screw.object_id, 4))])
        order = w.release(lines=[
            {"article_object_id": product.object_id, "quantity": 3, "origin": "neu",
             "units": []},
        ])
        w.run_all(order)
        made = [n for n in w.numbers(order) if n not in numbers]
        assert len(made) == 3

        lists = [
            {p["number"] for p in genealogy.parts_of(w.db, w.unit(n))} for n in made
        ]
        assert [len(s) for s in lists] == [4, 4, 4], (
            "Ein Getriebe hat nicht seine vier Schrauben – die Zuordnung ist grob."
        )
        assert set().union(*lists) == set(numbers)
        for a in range(3):
            for b in range(a + 1, 3):
                assert not lists[a] & lists[b], (
                    "Dieselbe Schraube steckt in zwei Getrieben."
                )

        # Die Gegenrichtung nennt genau EIN Erzeugnis, nicht alle drei.
        hosts = genealogy.built_into(w.db, w.unit(sorted(lists[0])[0]))
        assert len(hosts) == 1 and len(hosts[0]["products"]) == 1
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# §4 – Nichtverfügbarkeit ist kein Zustand
# ---------------------------------------------------------------------------

def test_a_shortage_is_not_a_state_it_is_an_unfinished_module():
    """►►► **Kein Pausenzustand.** ◄◄◄

    Reicht der Bestand nicht, passiert dreierlei – und nichts davon ist ein Zustand:

    * die **Freigabe geht** (der Bestand ist eine Frage der Laufzeit, keine der Freigabe),
    * das Modul **bewegt nichts** – auch das Produkt nicht, das ohne seine Teile nicht
      fertig ist,
    * die Meldung nennt **Artikel, Bedarf und Verfügbarkeit** im Klartext.

    Ein Auftrag mit einem eigenen «wartet auf Material»-Wert hätte einen Zustand mehr,
    den jemand wieder verlassen müsste. Das Modul ist schlicht nicht fertig.
    """
    from fastapi import HTTPException

    from app.services import consumption

    w = _w()
    try:
        screw, numbers = free_stock(w, serialization="unit", quantity=1)
        product = w.article(serialization="unit",
                            template=[w.consume((screw.object_id, 3))])
        order = w.release(lines=[
            {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
             "units": []},
        ])
        step = w.steps(order)[0]
        need = consumption.needs(w.db, step, pieces=1)[0]
        assert (need.required, need.available, need.missing) == (3, 1, 2)

        row = w.work(order, step)[0]
        with pytest.raises(HTTPException) as exc:
            w.confirm(order, step, instance=row["instance_object_id"])
        assert exc.value.status_code == 409
        detail = str(exc.value.detail)
        assert str(screw.object_id) in detail and "3" in detail and "1" in detail, (
            "Die Meldung nennt nicht, was fehlt – dann sucht der Mensch."
        )

        assert w.unit_status(numbers[0]) == "freigegeben", (
            "Es wurde halb verbaut und dann abgebrochen."
        )
        assert w.status(order) == "im_prozess"
        assert w.active_step(order) == step.id, (
            "Das Modul ist nicht mehr dran – es wäre stillschweigend übersprungen."
        )
    finally:
        w.db.rollback()
        w.db.close()


def test_another_instance_can_be_chosen():
    """**Kein automatisches Ausweichen** – aber ein Weg, es selbst zu sagen.

    ``sources`` sind die Instanzen, aus denen genommen werden soll: die Kisten, die der
    Lagerist gescannt hat. Es ist bewusst **keine Mengenangabe** – wie viel gebraucht
    wird, sagt die Stückliste, und ein zweiter Weg dorthin wäre ein zweiter Massstab.
    """
    from fastapi import HTTPException

    w = _w()
    try:
        screw = w.article(serialization="batch")
        first = w.stock(screw, 4)
        second = w.stock(screw, 4)
        # Eine Stücknummer ist «<Instanznummer>-<Suffix>» – die Kiste steht darin.
        instance_nr = int(second[0].split("-")[0])

        product = w.article(serialization="unit",
                            template=[w.consume((screw.object_id, 2))])
        order = w.release(lines=[
            {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
             "units": []},
        ])
        step = w.steps(order)[0]
        row = w.work(order, step)[0]
        w.confirm(order, step, instance=row["instance_object_id"],
                  sources=[instance_nr])

        assert [w.unit_status(n) for n in first] == ["freigegeben"] * 4, (
            "FIFO hat die ältere Kiste genommen, obwohl eine andere gewählt war."
        )
        assert len([n for n in second if w.unit_status(n) == "verbaut"]) == 2

        # Und die Wahl ist eine Aussage, keine Bitte: reicht die genannte Kiste nicht,
        # weicht nichts aus – der Rest des Lagers bleibt unangetastet.
        pair = w.article(serialization="batch",
                         template=[w.consume((screw.object_id, 2))])
        order2 = w.release(lines=[
            {"article_object_id": pair.object_id, "quantity": 2, "origin": "neu",
             "units": []},
        ])
        step2 = w.steps(order2)[0]
        rows = w.work(order2, step2)
        with pytest.raises(HTTPException) as exc:
            w.confirm(order2, step2, instance=rows[0]["instance_object_id"],
                      sources=[instance_nr])
        assert exc.value.status_code == 409
        assert [w.unit_status(n) for n in first] == ["freigegeben"] * 4, (
            "Es ist auf eine andere Kiste ausgewichen – das ist nie die Aufgabe des Moduls."
        )
    finally:
        w.db.rollback()
        w.db.close()


def test_only_free_pieces_are_taken():
    """**Genommen wird nur, was frei ist** – am Regelstart und ohne offene Zugehörigkeit.

    Das ist keine zusätzliche Regel, sondern dieselbe, aus der ``deviation_flags`` liest:
    wer auf ``Freigegeben`` steht, war regulär verfügbar. Zwei Folgen, beide gewollt: ein
    Verbrauch macht einen Auftrag **nie** stillschweigend zur Abweichung, und ein Stück,
    das gerade in einem anderen Auftrag läuft, kann nicht unter ihm weggezogen werden.
    """
    from fastapi import HTTPException

    w = _w()
    try:
        screw, numbers = free_stock(w, serialization="unit", quantity=2)
        # Ein Stück läuft in einem anderen Auftrag …
        busy = w.take(screw, [numbers[0]], steps=[w.capture()])
        assert w.unit_status(numbers[0]) == "im_prozess"

        product = w.article(serialization="unit",
                            template=[w.consume((screw.object_id, 2))])
        order = w.release(lines=[
            {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
             "units": []},
        ])
        step = w.steps(order)[0]
        row = w.work(order, step)[0]
        with pytest.raises(HTTPException) as exc:
            w.confirm(order, step, instance=row["instance_object_id"])
        assert exc.value.status_code == 409
        assert w.unit_status(numbers[0]) == "im_prozess", (
            "Das laufende Stück wurde dem anderen Auftrag entzogen."
        )
        assert w.is_deviation(order) is False
        assert w.status(busy) == "im_prozess"
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# §5 – was unverändert gilt
# ---------------------------------------------------------------------------

def test_the_module_is_no_exit_so_something_may_stand_behind_it():
    """►►► **Die Kettenregel bleibt unangetastet.** ◄◄◄

    ``Module.terminal`` beantwortet genau eine Frage: *verlassen ALLE ankommenden Stücke
    den Auftrag hier?* Beim Verbrauch lautet die Antwort **nein** – es kommt gar nichts
    an, was ginge: das Produkt läuft weiter, und die Komponenten treten hier ein. Also
    ist er kein Ausgang, und hinter ihm darf sehr wohl ein Modul stehen.

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


def test_the_parts_leave_and_the_product_walks_on():
    """Die Komponenten gehen hinaus, das Produkt läuft weiter – und zwar **durch** ein
    Modul dahinter. Genau daran zeigt sich, dass der Verbrauch kein Ausgang ist.
    """
    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=2, per_unit=2,
                                            after=[w.capture()])
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
        part, numbers, _, order = _assembly(w, parts=2, per_unit=2)
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
        part, numbers, _, build = _assembly(w, parts=2, per_unit=2)
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
    """Die Gegenrichtung: **worin steckt dieses Stück?** – mit dem Auftrag dazu."""
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
# Konfiguration – was das Anlegen und die Freigabe abweisen
# ---------------------------------------------------------------------------

def test_the_product_cannot_consume_itself():
    """Derselbe Artikel als ``Neu`` **und** in der Stückliste: der Auftrag zöge Stücke
    desselben Artikels aus dem Lager, während er ihn gerade herstellt.

    Das ist die Kehrseite davon, dass die Konfiguration **Artikel** trifft und nicht
    Zeilen – die eine Stelle, an der diese Körnung zu grob ist, wird darum abgewiesen
    statt stillschweigend falsch gerechnet.
    """
    from fastapi import HTTPException

    w = _w()
    try:
        from app.models import ArticleProcessStep
        from app.services import article_process as tpl

        art = w.article(serialization="unit")
        # Die Vorlage nennt **sich selbst**: derselbe Artikel wird erzeugt und verbaut.
        w.db.query(ArticleProcessStep).filter_by(article_id=art.id).delete()
        tpl.create_steps(w.db, art, [w.consume((art.object_id, 1))])
        w.db.flush()
        with pytest.raises(HTTPException) as exc:
            w.release(lines=[{"article_object_id": art.object_id, "quantity": 1,
                              "origin": "neu", "units": []}])
        assert exc.value.status_code == 400
        assert str(art.object_id) in str(exc.value.detail)
    finally:
        w.db.rollback()
        w.db.close()


def test_a_consumption_module_needs_at_least_one_line():
    """Ohne Zeile gäbe es nichts zu verbauen – der Fehler kommt beim **Anlegen**."""
    from fastapi import HTTPException

    from app.domain import modules

    with pytest.raises(HTTPException) as exc:
        modules.get("verbrauch").clean_config({"lines": []})
    assert exc.value.status_code == 400

    # Und eine Zeile ohne Menge ist keine: «4× Schraube» ist die Aussage, «Schraube» nicht.
    with pytest.raises(HTTPException):
        modules.get("verbrauch").clean_config({"lines": [{"article": 100000001}]})
    # Zweimal derselbe Artikel wäre eine Menge, die man addieren muss – und zwei Stellen,
    # an denen sie auseinanderlaufen kann.
    with pytest.raises(HTTPException):
        modules.get("verbrauch").clean_config({"lines": [
            {"article": 100000001, "quantity": 1},
            {"article": 100000001, "quantity": 2},
        ]})


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
