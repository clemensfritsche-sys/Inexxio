"""**Die Vormerkung: ein bestimmtes Stück, gebunden ab der Freigabe** (Testnotiz #721).

Die Regel in einem Satz: *eine Zeile der Stückliste kann statt «irgendein Rahmen» sagen
«dieser Rahmen» – und dann gehört er dem Auftrag ab seiner Freigabe.*

**Kein neuer Bindungs-Mechanismus.** Gebunden wird über denselben Eintritt wie sonst
(``process._enter_at_step``): das Stück ist ``Im Prozess`` an seinem Modul, exklusiv über
den partiellen Unique-Index. Neu ist nur der **Zeitpunkt** – und daraus folgt der einzige
Zustand, den es vorher nicht gab: *Material, das dem Auftrag gehört und noch nicht
verbaut ist.* Diese Datei prüft ihn in jeder Lage, in die er geraten kann.

Gefahren wird über die **echten** Dienstpfade gegen echtes PostgreSQL; jede Regel steht
gegen ihre **Bug-Form**.
"""

import pytest
from fastapi import HTTPException

from tests.runner import session
from tests.scenarios import World, free_stock


def _w() -> World:
    try:
        return World(session())
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}).")


def _instance_of(w: World, number: str) -> int:
    """Die Objektnummer der Instanz hinter einer Einzelinstanz-Nummer."""
    from app.models import Instance

    unit = w.unit(number)
    return w.db.query(Instance).filter(Instance.id == unit.instance_id).one().object_id


def _pin(article_object_id: int, number: str, *, quantity: int = 1) -> dict:
    """Ein Verbrauchsmodul mit **vorgemerkter** Einzelinstanz."""
    return {
        "module_type": "verbrauch",
        "config": {"lines": [{"article": article_object_id, "quantity": quantity,
                              "unit": number}]},
    }


def _assembly(w: World, *, parts: int = 1, products: int = 1, which: int = 0,
              after=None):
    """Ein Erzeugungsauftrag, der ein bestimmtes Stück vormerkt.

    **Die Vorlage nennt den Artikel, der Auftrag das Stück** (§9.6a): das Modul steht
    ungepinnt im Erzeugungsprozess, und der Entwurf schickt die Vormerkung mit. Genau so
    kommt sie in der Oberfläche zustande.
    """
    part, numbers = free_stock(w, serialization="unit", quantity=parts)
    product = w.article(
        serialization="unit",
        template=[w.consume((part.object_id, 1))] + list(after or []),
    )
    order = w.release(
        lines=[{"article_object_id": product.object_id, "quantity": products,
                "origin": "neu", "units": []}],
        steps=[_pin(part.object_id, numbers[which])],
    )
    return part, numbers, product, order


# ---------------------------------------------------------------------------
# Der Normalfall – gebunden ab der Freigabe
# ---------------------------------------------------------------------------

def test_a_pinned_piece_is_bound_from_the_release():
    """►►► **Der ganze Zweck.** ◄◄◄ Ab der Freigabe gehört das Stück diesem Auftrag.

    Vorher lag es frei, und jeder andere Auftrag konnte es greifen – dann wäre die
    Vormerkung eine Absichtserklärung gewesen. Geprüft wird beides: der Zustand des
    Stücks **und** die Zugehörigkeit; ohne die zweite wäre es ein Waisenkind, das
    niemand mehr freigeben könnte.

    Die **Bug-Form** daneben: eine Vormerkung, die erst beim Erreichen bindet, lässt das
    Stück hier auf ``Freigegeben`` und ohne Zeile stehen.
    """
    from app.models import OrderUnit

    w = _w()
    try:
        part, numbers, _, order = _assembly(w)
        step = w.steps(order)[0]

        assert w.unit_status(numbers[0]) == "im_prozess", (
            "Das vorgemerkte Stück liegt weiter frei – dann kann es jeder wegnehmen."
        )
        unit = w.unit(numbers[0])
        row = (
            w.db.query(OrderUnit)
            .filter(OrderUnit.instance_unit_id == unit.id,
                    OrderUnit.released_at.is_(None))
            .one()
        )
        assert row.order_id == order.id, "Es gehört dem falschen Auftrag."
        assert row.current_step_id == step.id, (
            "Es steht nicht an seinem Modul – dann wüsste niemand, wo es gebraucht wird."
        )
    finally:
        w.db.close()


def test_pinned_material_is_not_a_subject():
    """**Es gehört dem Auftrag, es ist aber nicht sein Gegenstand.**

    Daraus folgt dreierlei, und alle drei prüft dieser Wächter:

    * es steht **nicht in der Arbeitsliste** – sonst böte die Oberfläche an, es zu
      scannen, und ``confirm_step`` teilte ihm seinerseits Komponenten zu;
    * es kommt **nicht in die Stichprobe** – eine Messung, die einem Erzeugnis gilt,
      wäre an einer Schraube sinnlos, und die Bezugsgrösse wäre um sie zu gross;
    * es zählt **nicht** beim Auftragszustand – es kommt nirgends an und ist auch nicht
      unterwegs.
    """
    from app.services import sampling

    w = _w()
    try:
        part, numbers, product, order = _assembly(
            w, products=2, after=[w.capture()],
        )
        consume, capture = w.steps(order)

        work = w.work(order, consume)
        assert [row["instance_object_id"] for row in work], "Es steht gar nichts an."
        assert all(row["instance_object_id"] != part.object_id for row in work), (
            "Das Material steht in der Arbeitsliste – dann soll es jemand scannen."
        )
        assert sum(row["waiting"] for row in work) == 2, (
            "Die Arbeitsliste zählt das Material mit."
        )

        pool = {u.id for u in sampling._population(w.db, order)}
        assert w.unit(numbers[0]).id not in pool, (
            "Das Material ist in der Grundgesamtheit der Ziehung."
        )
        assert len(pool) == 2

        assert w.status(order) == "im_prozess"
    finally:
        w.db.close()


def test_the_pinned_piece_is_the_one_that_gets_built_in():
    """**Genommen wird das genannte Stück** – nicht das erstbeste aus dem Lager.

    Wer eine bestimmte Einzelinstanz nennt, meint sie. Ein stiller Ersatz wäre genau das
    Gegenteil dessen, wofür die Vormerkung da ist – und niemand sähe es.
    """
    w = _w()
    try:
        # Zwei Stücke im Lager, vorgemerkt ist das **zweite**: nähme FIFO seinen Lauf,
        # ginge das erste hinein, und der Test bliebe zufällig grün.
        part, numbers, _, order = _assembly(w, parts=2, which=1)
        w.run_all(order)

        assert w.unit_status(numbers[1]) == "verbaut", (
            "Nicht das vorgemerkte Stück wurde verbaut."
        )
        assert w.unit_status(numbers[0]) == "freigegeben", (
            "Ein anderes Stück wurde mitgenommen."
        )
        assert w.status(order) == "abgeschlossen"
    finally:
        w.db.close()


def test_a_pin_covers_one_piece_the_rest_comes_from_stock():
    """Eine Vormerkung ist **ein** Stück – über die übrigen sagt sie nichts.

    Bei drei Erzeugnissen werden drei Rahmen gebraucht; genannt ist einer. Die anderen
    kommen wie immer aus dem freien Bestand. Alles andere wäre eine Regel, die aus «dieser
    eine» «nur dieser eine» macht – und der Auftrag stünde ohne Grund still.
    """
    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=3, products=3, which=2)
        w.run_all(order)
        assert [w.unit_status(n) for n in numbers] == ["verbaut"] * 3
        assert w.status(order) == "abgeschlossen"
    finally:
        w.db.close()


# ---------------------------------------------------------------------------
# Die Freigabe scheitert – mit einem Satz, und ohne Spuren
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", ["weg", "fremder_artikel", "schon_vergeben", "im_bedarf"])
def test_a_pin_that_cannot_be_kept_stops_the_release(case: str):
    """**Der Fehler kommt bei der Freigabe** – nicht in drei Wochen mitten in der Montage.

    Und er kostet **keine Objektnummer**: jede Prüfung liegt vor der ersten (§6.3). Ein
    halb angelegter Auftrag wäre die Sackgasse, die es hier nicht geben darf.

    Vier Lagen, ein Verhalten:

    ==================  ==========================================================
    ``weg``             die genannte Nummer gibt es nicht
    ``fremder_artikel`` sie gehört zu einem anderen Artikel als die Zeile
    ``schon_vergeben``  ein anderer Auftrag hält das Stück bereits
    ``im_bedarf``       dieselbe Nummer steht zugleich im Bedarf dieses Auftrags
    ==================  ==========================================================
    """
    from app.models import Order

    w = _w()
    try:
        part, numbers = free_stock(w, serialization="unit", quantity=1)
        other, other_numbers = free_stock(w, serialization="unit", quantity=1)

        if case == "weg":
            line = _pin(part.object_id, "999999999-9")
        elif case == "fremder_artikel":
            line = _pin(part.object_id, other_numbers[0])
        elif case == "schon_vergeben":
            w.take(part, [numbers[0]], steps=[w.capture()])
            line = _pin(part.object_id, numbers[0])
        else:
            line = _pin(part.object_id, numbers[0])

        product = w.article(serialization="unit",
                            template=[w.consume((part.object_id, 1))])
        lines = [{"article_object_id": product.object_id, "quantity": 1,
                  "origin": "neu", "units": []}]
        if case == "im_bedarf":
            lines.append({"article_object_id": part.object_id, "quantity": 1,
                          "origin": "lager", "returns": True,
                          "units": [{"number": numbers[0], "from_order": None}]})

        # **Nur die Freigabe zurückdrehen**, nicht den Aufbau: sonst misst der Test
        # den Rollback seiner eigenen Vorbereitung.
        before = w.db.query(Order).count()
        sp = w.db.begin_nested()
        with pytest.raises(HTTPException) as err:
            w.release(lines=lines, steps=[line])
        assert err.value.status_code in (400, 404, 409), err.value.detail
        sp.rollback()

        assert w.db.query(Order).count() == before, (
            "Die gescheiterte Freigabe hat einen Auftrag hinterlassen."
        )
    finally:
        w.db.close()


def test_a_pin_is_matched_by_article_not_by_position():
    """**Die Vorlage sagt WAS, der Auftrag sagt WELCHES** (``_apply_pins``).

    Ein Erzeugungsauftrag fährt die Vorlage des Artikels – der Entwurf schickt darum gar
    keine passende Modul-Liste mit, nur die Vormerkung. Zugeordnet wird sie über den
    **Artikel**; «das dritte Modul» zeigte beim nächsten Umsortieren auf etwas anderes.

    Zwei Lagen, die es sagen statt zu raten: der Prozess verbraucht diesen Artikel gar
    nicht, oder er verbraucht ihn an zwei Modulen.
    """
    w = _w()
    try:
        part, numbers = free_stock(w, serialization="unit", quantity=2)
        andere, _ = free_stock(w, serialization="unit", quantity=1)

        # (a) Der Prozess verbraucht diesen Artikel gar nicht.
        product = w.article(serialization="unit",
                            template=[w.consume((andere.object_id, 1))])
        with pytest.raises(HTTPException) as err:
            w.release(
                lines=[{"article_object_id": product.object_id, "quantity": 1,
                        "origin": "neu", "units": []}],
                steps=[_pin(part.object_id, numbers[0])],
            )
        assert err.value.status_code == 400
        assert "verbraucht ihn gar nicht" in err.value.detail, err.value.detail
        w.db.rollback()

        # (b) Zwei Module verbrauchen denselben Artikel – nicht entscheidbar.
        zwei = w.article(
            serialization="unit",
            template=[w.consume((part.object_id, 1)), w.consume((part.object_id, 1))],
        )
        with pytest.raises(HTTPException) as err:
            w.release(
                lines=[{"article_object_id": zwei.object_id, "quantity": 1,
                        "origin": "neu", "units": []}],
                steps=[_pin(part.object_id, numbers[0])],
            )
        assert err.value.status_code == 400
        assert "mehreren Modulen" in err.value.detail, err.value.detail
    finally:
        w.db.close()


def test_a_pin_belongs_to_the_order_not_to_the_template():
    """**Eine Vorlage kennt keine bestimmten Stücke** (``Module.template_problem``).

    Der Erzeugungsprozess eines Artikels läuft für jeden künftigen Auftrag erneut. Ein
    dort genanntes Stück ist nach dem ersten verbaut, und jeder weitere müsste den
    Eintrag ignorieren – dann ist er keine Angabe, sondern eine Notiz.
    """
    w = _w()
    try:
        part, numbers = free_stock(w, serialization="unit", quantity=1)
        with pytest.raises(HTTPException) as err:
            w.article(serialization="unit", template=[_pin(part.object_id, numbers[0])])
        assert err.value.status_code == 400
        assert "nur im Auftrag" in err.value.detail, err.value.detail
    finally:
        w.db.close()


@pytest.mark.parametrize("case", ["menge", "doppelt"])
def test_a_pin_is_exactly_one_piece(case: str):
    """Eine genannte Einzelinstanz **ist** ein Stück.

    «4× dieses eine» gibt es nicht, und zweimal dasselbe Stück auch nicht – ein Stück
    kann nur an einer Stelle verbaut werden.
    """
    from app.domain import modules

    w = _w()
    try:
        part, numbers = free_stock(w, serialization="unit", quantity=1)
        module = modules.get("verbrauch")
        if case == "menge":
            config = {"lines": [{"article": part.object_id, "quantity": 4,
                                 "unit": numbers[0]}]}
        else:
            config = {"lines": [
                {"article": part.object_id, "quantity": 1, "unit": numbers[0]},
                {"article": part.object_id + 1, "quantity": 1, "unit": numbers[0]},
            ]}
        with pytest.raises(HTTPException) as err:
            module.clean_config(config)
        assert err.value.status_code == 400, err.value.detail
    finally:
        w.db.close()


# ---------------------------------------------------------------------------
# Abweichungen auf das vorgemerkte Stück
# ---------------------------------------------------------------------------

def test_a_deviation_may_take_the_pinned_piece_and_give_it_back():
    """**Vorgemerkt heisst nicht unantastbar.**

    Ein vorgemerktes Stück ist ``Im Prozess`` – also greift es ein anderer Auftrag als
    ganz gewöhnliche **Abweichung**. Genau so soll es sein: das System kennt einen Weg,
    ein Stück zu holen, und die Vormerkung erfindet keinen zweiten.

    Kehrt es zurück, steht es wieder an **seinem** Modul und wird verbaut. Die Position
    braucht dafür kein eigenes Feld – sie steht in ``order_units.current_step_id``.
    """
    w = _w()
    try:
        part, numbers, _, order = _assembly(w)
        step = w.steps(order)[0]

        dev = w.take(part, [numbers[0]], from_order=order.object_id,
                     steps=[w.capture()], returns=True)
        assert w.is_deviation(dev), "Der Zugriff gilt nicht als Abweichung."
        assert w.waits(order), "Der Montage-Auftrag wartet nicht auf sein Material."

        w.run_all(dev)
        assert w.unit_status(numbers[0]) == "im_prozess"

        from app.models import OrderUnit
        unit = w.unit(numbers[0])
        back = (
            w.db.query(OrderUnit)
            .filter(OrderUnit.instance_unit_id == unit.id,
                    OrderUnit.released_at.is_(None))
            .one()
        )
        assert back.order_id == order.id and back.current_step_id == step.id, (
            "Das Stück kehrt nicht an seine Stelle zurück."
        )

        w.run_all(order)
        assert w.unit_status(numbers[0]) == "verbaut"
        assert w.status(order) == "abgeschlossen"
    finally:
        w.db.close()


def test_a_cut_deviation_leaves_the_module_short_and_says_so():
    """Nimmt jemand das vorgemerkte Stück **endgültig**, fehlt es – sichtbar.

    Kein Deadlock, kein stiller Ersatz: das Modul meldet die Fehlmenge und **nennt die
    Nummer**, die vorgemerkt war. Was daraus folgt, entscheidet ein Mensch – und der
    gewöhnliche Weg dafür (eine andere Instanz wählen) funktioniert weiter.
    """
    w = _w()
    try:
        part, numbers, _, order = _assembly(w, parts=2)
        step = w.steps(order)[0]

        dev = w.take(part, [numbers[0]], from_order=order.object_id,
                     steps=[w.dispose("scrap", "Bruch")], returns=False)
        w.run_all(dev)
        assert w.unit_status(numbers[0]) == "verschrottet"

        need = w.needs(order, step)[0]
        assert need["pinned"] == numbers[0]
        assert need["pinned_here"] is False, (
            "Die Zeile behauptet, das vorgemerkte Stück stünde noch hier."
        )

        with pytest.raises(HTTPException) as err:
            w.run_step(order, step)
        assert numbers[0] in err.value.detail, (
            "Der Fehler nennt die vorgemerkte Nummer nicht – dann sucht der Mensch."
        )

        # **Der Ausweg ist der gewöhnliche**: eine andere Instanz wählen.
        w.run_step(order, step, sources=[_instance_of(w, numbers[1])])
        assert w.unit_status(numbers[1]) == "verbaut"
        assert w.status(order) == "abgeschlossen"
    finally:
        w.db.close()


# ---------------------------------------------------------------------------
# Die Sackgasse, die es nicht geben darf
# ---------------------------------------------------------------------------

def test_unused_material_leaves_when_the_order_is_over():
    """►►► **Was eintritt und nicht verbraucht wird, tritt wieder aus.** ◄◄◄

    Der gefährlichste Fall: eine Abweichung nimmt dem Montage-Auftrag **alle** Subjekte
    und kappt die Rückführung. Er ist damit abgebrochen und tut nie wieder etwas – das
    vorgemerkte Material bliebe für immer ``Im Prozess`` an einem toten Auftrag, und
    niemand könnte es je wieder greifen.

    Der Austritt hängt an **denselben zwei Zahlen** wie der Auftragszustand: kein Subjekt
    mehr unterwegs, keines mehr auf dem Rückweg. Eine zweite Regel gibt es nicht.

    Die **Bug-Form** daneben: ohne den Austritt steht das Stück auf ``Im Prozess`` und
    lässt sich in keinem neuen Auftrag mehr verwenden.
    """
    w = _w()
    try:
        part, numbers, product, order = _assembly(w)
        product_numbers = w.numbers(order)
        # Genau die Subjekte, ohne das Material.
        subjects = [n for n in product_numbers if n not in numbers]
        assert subjects, "Der Auftrag hat gar kein Subjekt."

        dev = w.take(product, subjects, from_order=order.object_id,
                     steps=[w.dispose("scrap", "Totalschaden")], returns=False)
        w.run_all(dev)

        assert w.status(order) == "abgebrochen", (
            "Der Auftrag zählt sein Material als Subjekt – dann läuft er ewig weiter."
        )
        assert w.unit_status(numbers[0]) == "freigegeben", (
            "Das vorgemerkte Stück hängt an einem toten Auftrag fest."
        )

        # Und es ist wirklich wieder greifbar – die Probe aufs Exempel.
        again = w.take(part, [numbers[0]], steps=[w.capture()])
        assert not w.is_deviation(again), (
            "Es gilt weiter als gebunden – dann war der Austritt nur die halbe Miete."
        )
    finally:
        w.db.close()


def test_waiting_material_is_not_drawn_on_the_axis():
    """**Das Bild zeigt den Weg der Subjekte** – wartendes Material steht nicht darin.

    Ein vorgemerktes Stück tritt an *seinem* Modul ein; die Kante davor ist es nie
    gegangen. Es dort zu zeichnen wäre entweder ein Widerspruch (Stücke auf einer
    Haarlinie) oder eine Lüge (die kräftige Linie liefe bis zu einem Modul, das noch kein
    Erzeugnis erreicht hat).

    **Die Bug-Form daneben ist gemessen, nicht ausgedacht:** ohne die Bedingung meldet
    die Invariantenprüfung unmittelbar nach der Freigabe «Kante …: dort stehen
    Einzelinstanzen, aber sie gilt als nicht gegangen».

    Sichtbar wird das Material in dem Moment, in dem es etwas getan hat – verbaut, auf
    der Ausgangskante seines Moduls.
    """
    from app.services import flow

    w = _w()
    try:
        part, numbers = free_stock(w, serialization="unit", quantity=1)
        product = w.article(
            serialization="unit",
            template=[w.capture(), w.consume((part.object_id, 1))],
        )
        order = w.release(
            lines=[{"article_object_id": product.object_id, "quantity": 1,
                    "origin": "neu", "units": []}],
            steps=[_pin(part.object_id, numbers[0])],
        )

        assert flow.build(w.db, order).problems == [], (
            "Das Bild widerspricht sich, solange die Vormerkung wartet."
        )
        w.run_step(order, w.steps(order)[0])
        assert flow.build(w.db, order).problems == []

        w.run_all(order)
        graph = flow.build(w.db, order)
        assert graph.problems == []
        # Jetzt steht es im Bild – auf der Ausgangskante seines Moduls.
        exits = [e for e in graph.edges if e.id.startswith("edge:exit:")]
        assert exits and sum(len(e.members) for e in exits) == 1, (
            "Das verbaute Stück steht nicht auf der Ausgangskante seines Moduls."
        )
    finally:
        w.db.close()


def test_two_pins_in_one_module():
    """Rahmen **und** Motor – zwei Vormerkungen, ein Modul.

    Es ist kein Sonderfall, sondern der Normalfall einer Montage: die Stückliste hat
    mehrere Zeilen, und mehr als eine davon kann ein bestimmtes Stück nennen. Geprüft
    wird, dass nichts sich in die Quere kommt – beide binden, beide bleiben aus der
    Arbeitsliste heraus, beide werden verbaut.
    """
    w = _w()
    try:
        rahmen, rn = free_stock(w, serialization="unit", quantity=1)
        motor, mn = free_stock(w, serialization="unit", quantity=1)
        product = w.article(
            serialization="unit",
            template=[w.consume((rahmen.object_id, 1), (motor.object_id, 1))],
        )
        order = w.release(
            lines=[{"article_object_id": product.object_id, "quantity": 1,
                    "origin": "neu", "units": []}],
            steps=[{"module_type": "verbrauch", "config": {"lines": [
                {"article": rahmen.object_id, "quantity": 1, "unit": rn[0]},
                {"article": motor.object_id, "quantity": 1, "unit": mn[0]},
            ]}}],
        )
        assert [w.unit_status(n) for n in (rn[0], mn[0])] == ["im_prozess"] * 2
        assert sum(r["waiting"] for r in w.work(order, w.steps(order)[0])) == 1, (
            "Das Material zählt in der Arbeitsliste mit."
        )
        w.run_all(order)
        assert [w.unit_status(n) for n in (rn[0], mn[0])] == ["verbaut"] * 2
        assert w.status(order) == "abgeschlossen"
    finally:
        w.db.close()


def test_a_pin_survives_a_chain_of_deviations():
    """**Geschachtelt ist kein Fall** – die Kette ist der gewöhnliche Mechanismus (§12.3).

    Auftrag → Abweichung → Abweichung, alle drei auf dasselbe vorgemerkte Stück. Die
    Rückführung hängt an der **Verbindung**, nicht am Auftrag; darum braucht die
    Vormerkung dafür keine eigene Regel. Am Ende steht das Stück wieder an seinem Modul
    und wird verbaut.
    """
    w = _w()
    try:
        part, numbers, _, order = _assembly(w)
        first = w.take(part, [numbers[0]], from_order=order.object_id,
                       steps=[w.capture()], returns=True)
        second = w.take(part, [numbers[0]], from_order=first.object_id,
                        steps=[w.capture()], returns=True)
        assert w.is_deviation(second)
        assert w.waits(order), "Der Hauptauftrag wartet nicht über die Kette hinweg."

        w.run_all(second)
        w.run_all(first)
        w.run_all(order)
        assert w.unit_status(numbers[0]) == "verbaut"
        assert w.status(order) == "abgeschlossen"
    finally:
        w.db.close()


def test_material_does_not_make_a_lost_order_look_finished():
    """Ein Auftrag ohne Subjekte ist **abgebrochen**, nicht «abgeschlossen».

    Träte das Material als «angekommen» in die Zählung ein, sähe genau dieser Fall aus
    wie ein Erfolg: das Ziel ist unerreichbar, aber es stünde ein Häkchen daran.
    """
    w = _w()
    try:
        _, numbers, product, order = _assembly(w)
        subjects = [n for n in w.numbers(order) if n not in numbers]
        dev = w.take(product, subjects, from_order=order.object_id,
                     steps=[w.dispose("scrap", "Totalschaden")], returns=False)
        w.run_all(dev)
        assert w.status(order) == "abgebrochen"
    finally:
        w.db.close()
