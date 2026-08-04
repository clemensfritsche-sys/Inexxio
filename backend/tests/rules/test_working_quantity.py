"""**Wie viel bearbeitet dieser Auftrag?** – die zweite Regel neben der Unterdeckung.

Sie hängt an derselben Unterscheidung wie ADR 008: ein **regulärer** Auftrag bearbeitet
seine **Zusage** (gespeichert, sie schrumpft nicht, nur weil ein Stück gerade in Klärung
ist), ein Auftrag mit **festem Subjekt** seine **Arbeitsmenge** (abgeleitet – was ihm von
seinen Instanzen noch gehört).

Der Befund, der diese Zeile ausgelöst hat: eine Abweichung, die auf 4 Stück eröffnet wurde
und eines an ihre eigene Abweichung verloren hat, verlangte weiter Komponenten für 4 – 8
statt 6 Schrauben. Der Überschuss war für jeden anderen Auftrag gesperrt und erzeugte dort
eine Fehlmenge, die es nicht gab. Keine Anzeigefrage.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from .conftest import _make_deviation, _make_order, _scrap  # noqa: F401


@pytest.fixture(scope="module")
def with_components(db, world):
    """Ein Bauteil am Lager – damit ein Ressourcen-Schritt überhaupt etwas reservieren kann."""
    from app.models import Article
    from app.services.objects import next_object_id

    user, art = world
    comp = Article(object_id=next_object_id(db), name="Schraube", unit="pcs",
                   serialization="batch", status="released")
    db.add(comp)
    db.flush()
    _, inst = _make_order(db, comp, user, 100)
    inst.quality, inst.disposition = "passed", "in_stock"
    inst.released_at = datetime.now(timezone.utc)
    db.commit()
    return comp


def test_a_fixed_subject_works_with_what_it_still_holds(db, world, with_components):
    """Verliert eine Abweichung ein Stück, sinkt ihr Materialbedarf mit."""
    from app.models import ArticleProcessStep
    from app.services import process
    from app.services.order_lines import declared_quantity, effective_quantity

    user, art = world
    comp = with_components
    lines = [{"article_id": comp.id, "quantity": 2, "mode": "consume"}]
    main, inst = _make_order(db, art, user, 4)
    dev = _make_deviation(db, main, inst, user, 4, steps=("resource",),
                          step_kwargs={"resource_lines": lines})

    assert effective_quantity(db, dev) == Decimal(4), "Frisch hält sie alle vier."
    assert process._component_needs(db, dev) == {comp.id: Decimal(8)}

    sub = _make_deviation(db, dev, inst, user, 1, steps=("scrap",))
    _scrap(db, sub, inst, user, 1)
    db.refresh(dev)

    assert declared_quantity(db, dev) == Decimal(4), (
        "Die Eröffnungsmenge bleibt – sie ist eine Aussage über die Anlage, keine über den "
        "Bestand, und gilt auch nach dem Abschluss noch.")
    assert effective_quantity(db, dev) == Decimal(3), (
        "Sie hält noch drei Stück – auf so viel arbeitet sie, nicht auf ihre Eröffnungsmenge.")
    assert process._component_needs(db, dev) == {comp.id: Decimal(6)}, (
        "8 statt 6 Schrauben waren für JEDEN anderen Auftrag gesperrt und erzeugten dort "
        "eine Fehlmenge, die es nicht gab.")


def test_a_regular_order_keeps_its_promise(db, world, with_components):
    """Beim regulären Auftrag bleibt die Zusage stehen – auch während einer Ausleihe.

    Sonst würde er seine Komponenten in dem Moment freigeben, in dem ein Stück in Klärung
    geht, und müsste sie neu anfordern, sobald die Ausleihe zurückkommt."""
    from app.services.order_lines import declared_quantity, effective_quantity

    user, art = world
    main, inst = _make_order(db, art, user, 4)
    _make_deviation(db, main, inst, user, 1)          # nimmt ihm eines weg, läuft weiter
    db.refresh(main)
    assert effective_quantity(db, main) == Decimal(4) == declared_quantity(db, main)
