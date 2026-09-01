"""**Material am richtigen Ort** — der Ort wird zur Voraussetzung, und nur dort.

Bis hierher war ``instance_units.place_*`` ein Zeiger, den **keine Regel liest**. Sobald
ein Modul Material an einem bestimmten Ort *braucht*, wird er zur Voraussetzung. Diese
Datei prüft die sechs Sätze, aus denen das besteht — jeder gegen seine **Bug-Form**:

1. Wo das Material liegen muss, ist **abgeleitet**: dort, wo das Produkt liegt.
2. «Am Ort» heisst **in der Kette**, nicht «identische Nummer».
3. **Wo nichts steht, wird nichts verlangt** – ohne Ort am Produkt ändert sich nichts.
4. Nichtverfügbarkeit bleibt **kein Zustand**: eine Spalte weiter in ``StepNeed``.
5. **Wer zur Historie zählt, verliert seinen Ort** – ausser er bekommt einen neuen.
6. Ein **verbautes** Stück liegt in seinem **Träger**, und die Kette läuft weiter.

Gefahren wird über die **echten** Dienstpfade gegen echtes PostgreSQL: die
interessanten Fehler entstehen zwischen den Schritten, nicht in einem nachgestellten
Zustand.
"""

import os
import pathlib
import re

import pytest

from tests.runner import session
from tests.scenarios import World, free_stock

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _w() -> World:
    return World(session())


def _before(w: World, order, step):
    from app.services import process as proc
    return proc.units_before(w.db, order, step)


def _need(w: World, order, step):
    """Die eine Stücklisten-Zeile dieses Moduls, gegen die Wirklichkeit gehalten."""
    from app.services import consumption
    return consumption.needs(w.db, step, products=_before(w, order, step))[0]


def _assembly(w: World, *, per_unit: int = 2, products: int = 1, stock: int = 10,
              before_move=None):
    """Ein Montage-Auftrag: Produkt mit Stückliste, dazu freier Komponenten-Bestand.

    ``before_move`` schiebt vor dem Verbrauch ein Bewegen-Modul ein – so bekommt das
    Produkt einen Ort, ohne dass ihn jemand von Hand setzt.
    """
    screw, numbers = free_stock(w, serialization="batch", quantity=stock)
    template = [] if before_move is None else [World.move(before_move)]
    template.append(World.consume((screw.object_id, per_unit)))
    product = w.article(serialization="unit", template=template)
    order = w.release(lines=[{
        "article_object_id": product.object_id, "quantity": products,
        "origin": "neu", "units": [],
    }])
    return screw, numbers, product, order


# ---------------------------------------------------------------------------
# 1 · Der verlangte Ort ist abgeleitet – und ohne Ort am Produkt gibt es keinen
# ---------------------------------------------------------------------------

def test_without_a_place_at_the_product_nothing_is_demanded():
    """**Wo nichts steht, wird nichts verlangt.**

    Das ist die Regel, an der diese ganze Änderung rückwärtsverträglich hängt: ein
    frisch erzeugtes Stück liegt nirgends (§9.8), und ein Modul, das dann trotzdem einen
    Ort verlangte, hielte **jeden** bestehenden Montage-Ablauf an.
    """
    w = _w()
    try:
        _screw, _numbers, _product, order = _assembly(w)
        step = w.steps(order)[0]
        need = _need(w, order, step)

        assert need.place is None, (
            "Ohne Ort am Produkt gibt es keinen verlangten Ort – sonst sperrte das Modul "
            "auf einen Ort, den niemand genannt hat."
        )
        assert need.here == need.available, "Ohne Anforderung ist «hier» gleich «frei»."
        w.run_all(order)   # und es läuft durch, wie eh und je
    finally:
        w.db.rollback()
        w.db.close()


def test_scattered_products_demand_no_place():
    """Liegen die Produkt-Stücke an **verschiedenen** Orten, gibt es keine Anforderung.

    Eine erfundene wäre schlimmer als keine: sie sperrte das Modul auf einen Ort, den
    nur ein Teil der Stücke teilt.
    """
    from app.services import places

    w = _w()
    try:
        bench, shelf = w.holder(name="Werkbank"), w.holder(name="Regal")
        _screw, _numbers, _product, order = _assembly(w, products=2)
        step = w.steps(order)[0]
        products = _before(w, order, step)
        assert len(products) == 2
        places.place(w.db, units=[products[0]], target=bench.object_id)
        places.place(w.db, units=[products[1]], target=shelf.object_id)
        w.db.flush()

        assert _need(w, order, step).place is None, (
            "Zwei Orte sind keine Antwort auf «wo wird gearbeitet» – dann wird nichts "
            "verlangt, statt einen der beiden zu erfinden."
        )
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# 2 · Am falschen Ort — dieselbe Aussage wie «zu wenig», eine Spalte weiter
# ---------------------------------------------------------------------------

def test_material_elsewhere_is_reported_and_refused():
    """**Der Kern.** Bestand ist da, liegt aber woanders: gemeldet *und* abgewiesen.

    Zwei Formen derselben Regel – ``needs`` als Auskunft, ``plan`` als Riegel. Ein
    milderer Riegel wäre eine Zeile, die «0 hier» meldet, und ein Modul, das trotzdem
    verbaut.
    """
    from fastapi import HTTPException
    from app.models import InstanceUnit
    from app.services import places

    w = _w()
    try:
        bench, shelf = w.holder(name="Werkbank 5"), w.holder(name="Regal A")
        _screw, numbers, _product, order = _assembly(w, per_unit=2, stock=10)
        step = w.steps(order)[0]
        products = _before(w, order, step)
        places.place(w.db, units=products, target=bench.object_id)
        w.put(numbers, shelf.object_id)

        need = _need(w, order, step)
        assert need.place == (places.OBJECT, bench.object_id)
        assert (need.required, need.available, need.here) == (2, 10, 0), (
            "Die Zeile nennt beides: es ist genug da, es liegt nur nicht hier."
        )
        assert need.misplaced == 2
        assert need.sources[0].place == (places.OBJECT, shelf.object_id), (
            "Und sie nennt, WO es liegt – eine Zahl ohne den Ort verschweigt die Ursache."
        )

        row = w.work(order, step)[0]
        with pytest.raises(HTTPException) as exc:
            w.confirm(order, step, instance=row["instance_object_id"])
        assert exc.value.status_code == 409
        assert "Werkbank 5" in str(exc.value.detail), (
            "Der Grund gehört in die Meldung: «0 verfügbar» ist wahr und nutzlos, wenn "
            "zehn im Regal liegen und nur der Ort nicht stimmt."
        )

        # **Und es hat sich nichts bewegt** – die Prüfung steht vor dem Schreiben (§4).
        assert not w.db.query(InstanceUnit).filter(
            InstanceUnit.status == "verbaut").count()
    finally:
        w.db.rollback()
        w.db.close()


def test_at_the_place_means_inside_the_chain():
    """Die Schraube in der Kiste, die auf Werkbank 5 steht, **ist** auf Werkbank 5.

    «Identische Nummer» wäre die naive Lesart und in der Praxis fast immer falsch:
    Material steht in Behältern, und der Behälter steht am Arbeitsplatz.
    """
    from app.models import Instance, InstanceUnit
    from app.services import places

    w = _w()
    try:
        bench, box = w.holder(name="Werkbank 5"), w.holder(name="Kiste 7")
        # Die Kiste steht auf der Werkbank.
        box_unit = w.db.query(InstanceUnit).join(
            Instance, Instance.id == InstanceUnit.instance_id,
        ).filter(Instance.object_id == box.object_id).one()
        places.place(w.db, units=[box_unit], target=bench.object_id)

        _screw, numbers, _product, order = _assembly(w, per_unit=2, stock=4)
        step = w.steps(order)[0]
        places.place(w.db, units=_before(w, order, step), target=bench.object_id)
        w.put(numbers, box.object_id)          # das Material liegt IN der Kiste

        need = _need(w, order, step)
        assert need.here == 4, (
            "Was in einem Behälter am Arbeitsplatz liegt, ist am Arbeitsplatz – sonst "
            "verlangte das Modul, jede Kiste auszuleeren."
        )
        w.run_step(order, step)                # und es lässt sich verbauen
        assert len([n for n in numbers if w.unit_status(n) == "verbaut"]) == 2
    finally:
        w.db.rollback()
        w.db.close()


def test_moving_the_material_makes_the_module_ready():
    """**Der ganze Weg** – und es entsteht dabei kein einziger Wartezustand.

    Solange der Transportauftrag läuft, ist das Stück ``Im Prozess`` mit offener
    Zugehörigkeit – der Verbrauch nimmt nur, was frei ist, kann es also gar nicht
    greifen. Danach ist es frei **und** liegt richtig. Keine Sperre, keine Verknüpfung,
    keine Wartelogik: die bestehende Exklusivität tut es.
    """
    from app.services import places

    w = _w()
    try:
        bench, shelf = w.holder(name="Werkbank 5"), w.holder(name="Regal A")
        screw, numbers, _product, order = _assembly(w, per_unit=2, stock=4)
        step = w.steps(order)[0]
        places.place(w.db, units=_before(w, order, step), target=bench.object_id)
        w.put(numbers, shelf.object_id)
        assert _need(w, order, step).here == 0

        # **Ein ganz gewöhnlicher Auftrag** mit einem Bewegen-Modul – kein Sondertyp.
        haul = w.take(screw, numbers[:2], steps=[World.move(bench.object_id)])
        assert _need(w, order, step).available == 2, (
            "Während der Transport läuft, sind die Stücke gebunden – das ist die "
            "Sperre, und sie war schon da."
        )
        w.run_all(haul)

        need = _need(w, order, step)
        assert (need.available, need.here) == (4, 2), (
            "Nach dem Transport sind sie wieder frei und liegen am Arbeitsplatz."
        )
        w.run_step(order, step)
        assert [w.unit_status(n) for n in numbers[:2]] == ["verbaut", "verbaut"]
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# 3 · Der Ort eines Stücks, das den Kreislauf verlässt
# ---------------------------------------------------------------------------

def test_a_consumed_piece_lies_in_its_carrier():
    """**Der Nachweis, wo etwas verbaut wurde** – als Ort, nicht als leeres Feld.

    Der Träger ist ein **Stück**, nicht seine Instanz: «in 100000123» wären bei einer
    Charge 600 Getriebe, also eine Gruppe und kein Ort. Und weil das Stück auf den
    Träger zeigt und nicht auf dessen Anschrift, **wandert die Schraube mit**, sobald das
    Getriebe bewegt wird – genau wie eine Schraube in einer Kiste.
    """
    from app.services import instances as inst_svc, places

    w = _w()
    try:
        bench = w.holder(name="Werkbank 5")
        _screw, numbers, _product, order = _assembly(w, per_unit=2, stock=4)
        step = w.steps(order)[0]
        products = _before(w, order, step)
        places.place(w.db, units=products, target=bench.object_id)
        w.put(numbers, bench.object_id)
        w.run_step(order, step)

        built = [n for n in numbers if w.unit_status(n) == "verbaut"]
        assert len(built) == 2
        for number in built:
            unit = inst_svc.find_unit(w.db, number)
            assert unit.place_unit_id == products[0].id, (
                "Ein verbautes Stück liegt in seinem Träger – das ist der Nachweis, wo "
                "es hingegangen ist."
            )
            assert unit.place_object_id is None, (
                "Der Ort ist EINE Aussage: der alte Halter gilt nicht mehr."
            )

        # **Die Kette läuft über den Träger weiter** – bis zur Anschrift.
        chain = places.chain(w.db, places.place_of(inst_svc.find_unit(w.db, built[0])))
        assert [s.kind for s in chain][:2] == ["unit", "instance"]
        from app.services import process as proc
        assert chain[0].number == proc.unit_numbers(w.db, products)[products[0].id], (
            "Die erste Station ist das Träger-STÜCK, benannt mit seiner Nummer – nicht "
            "seine Instanz: die wären bei einer Charge sechshundert Getriebe."
        )
        assert chain[1].object_id == bench.object_id
    finally:
        w.db.rollback()
        w.db.close()


def test_history_loses_its_place_but_blocked_keeps_it():
    """**Wer zur Historie zählt, verliert seinen Ort** – und wer im Regal liegt, nicht.

    Die Regel hängt am **Status** (``Status.stock`` heisst wörtlich «liegt im Regal»),
    nicht am Modul. Damit erbt sie jedes künftige Modul, und **Gesperrt** fällt ohne
    Sonderregel richtig heraus: es ist physisch noch da.
    """
    from app.services import instances as inst_svc

    w = _w()
    try:
        shelf = w.holder(name="Regal A")
        for mode, expect_place in (("scrap", False), ("block", True)):
            article, numbers = free_stock(w, serialization="unit", quantity=1)
            w.put(numbers, shelf.object_id)
            order = w.take(article, numbers, steps=[World.dispose(mode)])
            w.run_all(order)

            unit = inst_svc.find_unit(w.db, numbers[0])
            assert (unit.place_object_id is not None) is expect_place, (
                f"«{mode}»: ein verschrottetes Stück liegt nirgends, ein gesperrtes "
                f"liegt weiterhin im Regal."
            )
            assert unit.place_unit_id is None
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# 4 · Die Bauart – eine Schreibstelle, ein Kettenlauf
# ---------------------------------------------------------------------------

def test_only_places_writes_a_place():
    """**Genau ein Modul schreibt den Ort.** Quelltext-Wächter.

    Der Ort ist ein dummes Feld mit genau einer Regel (keine Zyklen) – und die steht in
    ``places``. Ein zweiter Schreiber umginge sie, und der Fehler zeigte sich erst,
    wenn eine Bestandsansicht im Kreis läuft.
    """
    guilty: list[str] = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        if path.name == "places.py":
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if re.search(r"\.place_(object|unit)_id\s*=", line):
                guilty.append(f"{path.relative_to(BACKEND)}: {line.strip()}")
    assert not guilty, (
        "Nur ``services/places`` darf einen Ort schreiben (``place`` · ``place_in`` · "
        "``forget``). Gefunden: " + " | ".join(guilty)
    )


def test_the_chain_is_resolved_per_holder_not_per_piece():
    """Sechzig Stücke in einem Regal sind **eine** Kette, nicht sechzig.

    Gemessen statt behauptet: die Zahl der Abfragen darf nicht mit der Zahl der Stücke
    wachsen. Genau daran hing die Ortsanzeige des Vorgängersystems.
    """
    from sqlalchemy import event
    from app.core.database import engine
    from app.services import places

    w = _w()
    try:
        shelf = w.holder(name="Regal A")
        article, numbers = free_stock(w, serialization="batch", quantity=60)
        w.put(numbers, shelf.object_id)
        units = [__import__("app.services.instances", fromlist=["x"]).find_unit(w.db, n)
                 for n in numbers]

        seen = {"n": 0}

        def tally(*_a, **_k):
            seen["n"] += 1

        event.listen(engine, "before_cursor_execute", tally)
        try:
            places.for_units(w.db, units)
        finally:
            event.remove(engine, "before_cursor_execute", tally)

        assert seen["n"] <= 15, (
            f"Je Stück aufgelöst wären es Hunderte; gemessen: {seen['n']}."
        )
    finally:
        w.db.rollback()
        w.db.close()


def test_a_carrier_cycle_is_refused():
    """Ein Stück kann nicht in sich selbst liegen – und nicht in dem, was in ihm liegt.

    Verglichen werden **Orte**, nicht Beschriftungen: ein Träger und seine Instanz tragen
    dieselbe Objektnummer, und ein Vergleich über sie hielte ein Stück für sein eigenes
    Regal.
    """
    from fastapi import HTTPException
    from app.services import instances as inst_svc, places

    w = _w()
    try:
        article, numbers = free_stock(w, serialization="batch", quantity=2)
        a, b = (inst_svc.find_unit(w.db, n) for n in numbers)
        places.place_in(w.db, units=[a], carrier=b)
        w.db.flush()
        with pytest.raises(HTTPException) as exc:
            places.place_in(w.db, units=[b], carrier=a)
        assert exc.value.status_code == 400
        assert "Kreis" in str(exc.value.detail)
    finally:
        w.db.rollback()
        w.db.close()


def test_a_place_is_one_statement():
    """Höchstens **eines** von beiden – erzwungen von der Datenbank, nicht von der App.

    Eine Anwendungsregel liesse sich umgehen; die Tabelle nicht. Ohne den Riegel könnte
    ein Stück gleichzeitig im Regal und in einem Getriebe liegen, und welche Angabe gilt,
    entschiede die Lesestelle.
    """
    from sqlalchemy.exc import IntegrityError
    from app.services import instances as inst_svc

    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("Der CHECK lebt in PostgreSQL – ohne echte Datenbank ist er nicht da.")

    w = _w()
    try:
        _article, numbers = free_stock(w, serialization="batch", quantity=2)
        unit = inst_svc.find_unit(w.db, numbers[0])
        other = inst_svc.find_unit(w.db, numbers[1])
        unit.place_object_id = 100_000_001
        unit.place_unit_id = other.id
        with pytest.raises(IntegrityError):
            w.db.flush()
    finally:
        w.db.rollback()
        w.db.close()
