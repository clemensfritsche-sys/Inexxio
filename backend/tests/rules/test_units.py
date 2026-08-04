"""**Jedes Stück hat eine eigene Nummer** – die Regel, ausgeführt.

Eine Charge war eine Menge unter EINER Nummer; welches der vier Stück gerade in einer
Abweichung steckte, liess sich nicht sagen. Jetzt trägt jedes Stück ``<objektnr>-<n>``,
gespeichert als Läufe in der Instanz (keine neuen Datensätze).

Geprüft wird das, was am Bildschirm steht – die Nummern in der Aufteilung, im Auftrags-
Embed und auf den Kanten des Flusses – und dass Nummern und Mengen nie auseinanderlaufen
(``units.verify``, dieselbe Rolle wie ``ledger.verify_instance``).
"""

from decimal import Decimal

import pytest

from .conftest import _make_deviation, _make_order, _scrap  # noqa: F401


@pytest.fixture(scope="module")
def kinds(db):
    """Ein Chargen- und ein Einzelteil-Artikel – der Unterschied zeigt sich an den Nummern."""
    from app.models import Article, ArticleProcessStep
    from app.services.objects import next_object_id

    out = {}
    for key, ser, unit in (("batch", "batch", "pcs"), ("unit", "unit", "pcs"),
                           ("kg", "batch", "kg")):
        art = Article(object_id=next_object_id(db), name=f"Stück {key}", unit=unit,
                      serialization=ser, status="released")
        db.add(art)
        db.flush()
        db.add(ArticleProcessStep(article_id=art.id, step_type="inspection", position=0,
                                  sample_percent=100))
        out[key] = art
    db.commit()
    return out


def test_a_batch_numbers_every_piece(db, kinds, world):
    """Charge über 4 → ``-1`` bis ``-4``, alle unter EINER Instanz."""
    from app.models import Instance
    from app.services import units

    user, _ = world
    order, inst = _make_order(db, kinds["batch"], user, 4)
    assert units.count(inst) == 4
    assert units.numbers(inst) == [f"{inst.object_id}-{n}" for n in (1, 2, 3, 4)]
    assert db.query(Instance).filter(Instance.order_id == order.id).count() == 1, (
        "Die Nummern sind KEINE neuen Datensätze – sie wohnen in der Instanz.")


def test_a_single_piece_keeps_its_plain_number(db, kinds, world):
    """Ein Einzelteil ist schon eindeutig – ``-1`` wäre Lärm und stünde auf keinem Etikett."""
    from app.services import units

    user, _ = world
    _, inst = _make_order(db, kinds["unit"], user, 1)
    assert units.numbers(inst) == [str(inst.object_id)]


def test_kilograms_get_no_running_numbers(db, kinds, world):
    """2.5 kg sind EIN Stück mit 2.5 – ein halbes Stück gibt es nicht."""
    from app.services import units

    user, _ = world
    _, inst = _make_order(db, kinds["kg"], user, Decimal("2.5"))
    assert units.count(inst) == 1
    assert units.of(inst)[0].quantity == Decimal("2.5")
    assert units.numbers(inst) == [str(inst.object_id)]


def test_a_deviation_takes_named_pieces_and_the_parent_keeps_the_rest(db, kinds, world):
    """Wer 1 von 4 nimmt, nimmt **ein bestimmtes** Stück – und der Rest bleibt beim Eltern."""
    from app.services import units

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    dev = _make_deviation(db, main, inst, user, 1, steps=("scrap",))
    db.refresh(inst)

    mine = units.numbers(inst, holder=dev.id)
    theirs = units.numbers(inst, holder=main.id) or units.numbers(inst, holder=None)
    assert len(mine) == 1, f"Genau ein Stück, nicht eine Menge ohne Namen: {mine}"
    assert len(theirs) == 3, theirs
    assert not (set(mine) & set(theirs)), (
        f"Ein Stück gehört genau einem Auftrag – nie beiden: {mine} ∩ {theirs}")
    assert units.verify(inst) == [], "Nummern und Mengen dürfen nie auseinanderlaufen."


def test_a_scrapped_number_is_never_handed_out_again(db, kinds, world):
    """Eine Nummer ist eine Identität: ist das Stück weg, bleibt seine Nummer weg."""
    from app.services import units

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    dev = _make_deviation(db, main, inst, user, 1, steps=("scrap",))
    db.refresh(inst)
    doomed = set(units.numbers(inst, holder=dev.id))
    _scrap(db, dev, inst, user, 1)
    db.refresh(inst)

    left = set(units.numbers(inst))
    assert not (doomed & left), f"Verschrottete Nummer wieder da: {doomed & left}"
    assert len(left) == 3, left
    assert units.verify(inst) == []
    # Und die übrigen behalten ihre Nummern – es wird NICHT neu durchgezählt.
    assert left <= {f"{inst.object_id}-{n}" for n in (1, 2, 3, 4)}


def test_the_numbers_reach_the_surface(db, kinds, world):
    """Aufteilung, Auftrags-Embed und Fluss-Kante nennen die Stücke beim Namen."""
    from app.services import shares
    from app.services.orders import to_order_response

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    dev = _make_deviation(db, main, inst, user, 1, steps=("scrap",))
    db.refresh(inst)

    rows = shares.shares_for(db, [inst])[inst.id]
    assert any(r.units and r.unit_count == 1 for r in rows), (
        f"Die Auswahl muss zeigen, WELCHES Stück eine Zeile meint: {rows}")
    assert sum(r.unit_count for r in rows) == 4, rows

    resp = to_order_response(db, dev)
    assert resp.instances and resp.instances[0].units, (
        "Der Auftrag zeigt die Nummern der Stücke, die er hält.")
    assert resp.instances[0].unit_count == 1
    on_edges = {u for e in resp.flow_edges for l in e.lots for u in l.units}
    assert on_edges == set(resp.instances[0].units), (
        f"Die Kante trägt dieselben Nummern wie das Embed: {on_edges}")
