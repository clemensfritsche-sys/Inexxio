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


def test_the_suffix_has_no_exception(db, kinds, world):
    """**Eine Regel für alles**: auch ein Einzelteil trägt ``-1``.

    Eine Sonderregel «bei genau einem Stück ohne Zusatz» wäre eine zweite Schreibweise für
    dieselbe Sache, und jede Ansicht müsste sie kennen. Ein Format, überall gleich."""
    from app.services import units

    user, _ = world
    _, inst = _make_order(db, kinds["unit"], user, 1)
    assert units.numbers(inst) == [f"{inst.object_id}-1"]


def test_kilograms_get_no_running_numbers(db, kinds, world):
    """2.5 kg sind EIN Stück mit 2.5 – ein halbes Stück gibt es nicht."""
    from app.services import units

    user, _ = world
    _, inst = _make_order(db, kinds["kg"], user, Decimal("2.5"))
    assert units.count(inst) == 1
    assert units.of(inst)[0].quantity == Decimal("2.5")
    assert units.numbers(inst) == [f"{inst.object_id}-1"], "auch hier kein Sonderfall"


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
    # **Drei Angaben, immer** (Testnotizen #531/#532): Nummer · Menge · Zustand.
    for r in rows:
        for u in r.units:
            assert u.number and u.quantity > 0 and u.quality and u.disposition, u

    resp = to_order_response(db, dev)
    assert resp.instances and resp.instances[0].units, (
        "Der Auftrag zeigt die Nummern der Stücke, die er hält.")
    assert resp.instances[0].unit_count == 1
    on_edges = {u.number for e in resp.flow_edges for l in e.lots for u in l.units}
    assert on_edges == {u.number for u in resp.instances[0].units}, (
        f"Die Kante trägt dieselben Nummern wie das Embed: {on_edges}")


def test_a_lot_always_names_its_pieces(db, kinds, world):
    """**Eine Instanzanzeige ist überall dieselbe** (Testnotizen #536/#537/#539/#540).

    Über einem Split liegt das Material noch **ganz** beim Auftrag – es zweigt ja erst
    darunter ab. Vorher standen dort zwei Pillen: «3 Stk» (gehalten, mit Nummern) und
    «1 Stk» (abgegeben, OHNE Nummern). Zwei Zeilen für eine Sache, und eine davon konnte
    ihre Stücke nicht benennen.

    Jetzt gilt eine Regel: was an dieser Stelle noch auf der Achse liegt, liegt hier noch –
    und die Nummern kommen von dem, der die Menge jetzt hält (der Auftrag selbst oder der
    Abzweig, in den sie ging)."""
    from app.services.orders import to_order_response

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    dev = _make_deviation(db, main, inst, user, 1, steps=("scrap",))
    db.refresh(inst)

    resp = to_order_response(db, main)
    above = next(e for e in resp.flow_edges if e.reached)
    assert len(above.lots) == 1, (
        f"Über dem Split ist es EINE Menge in EINEM Zustand, nicht zwei Pillen: "
        f"{[(l.quantity, len(l.units)) for l in above.lots]}")
    lot = above.lots[0]
    assert lot.quantity == 4, f"Alle vier waren hier, bevor eines abzweigte: {lot.quantity}"
    assert [u.number for u in lot.units] == [f"{inst.object_id}-{n}" for n in (1, 2, 3, 4)], (
        f"…und die Kante benennt sie alle, aufsteigend: {[u.number for u in lot.units]}")

    # Jede Materialzeile, die lebendes Material trägt, kennt ihre Stücke – überall.
    for e in resp.flow_edges:
        for l in e.lots:
            if l.disposition not in ("scrapped", "sold", "consumed"):
                assert l.units, f"Zeile ohne Nummern: {l}"
    for d in (resp.deviations or []):
        for l in (d.flow_in or []):
            assert l.units, f"Der Abzweig-Teaser nennt seine Stücke nicht: {l}"
    assert dev.object_id


def test_the_past_keeps_its_numbers(db, kinds, world):
    """**Ein Abschluss ändert die Vergangenheit nicht** (Testnotizen #543/#544).

    Die Nummern wurden aus dem HEUTIGEN Halter abgeleitet. Gab ein Abzweig beim Abschluss
    seine Stücke zurück, hielt er nichts mehr – und die Vergangenheit zeigte plötzlich ALLE
    Nummern statt der richtigen. Eine abgeleitete Antwort kann keine Vergangenheit sein;
    sie steht jetzt in der **Buchung** (ADR 007)."""
    from app.models import ArticleProcessStep
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc
    from app.services.orders import to_order_response

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    dev = _make_deviation(db, main, inst, user, 1)          # inspection-Schritt
    db.refresh(inst)
    mine = [u.number for u in to_order_response(db, dev).flow_edges[0].lots[0].units]
    assert len(mine) == 1, mine

    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == dev.id,
                    ArticleProcessStep.step_type == "inspection").first())
    insp_svc.record_inspection(db, dev, InspectionUpdate(
        samples=[InspectionSample(instance_id=inst.object_id, slot=1, values={"_ok": True})],
        step_id=step.id), user)
    db.commit()
    db.refresh(dev)
    db.refresh(inst)
    assert dev.status == "completed"

    after = to_order_response(db, dev)
    for e in after.flow_edges:
        for l in e.lots:
            assert [u.number for u in l.units] == mine, (
                f"Der Abschluss hat die Vergangenheit umgeschrieben: {[u.number for u in l.units]}")
    parent = to_order_response(db, main)
    bypass = [n.bypass for n in parent.flow_nodes if n.bypass and n.bypass.lots]
    for edge in bypass:
        for l in edge.lots:
            assert len(l.units) == int(l.quantity), (
                f"Menge und Nummern müssen zusammenpassen: {l.quantity} vs "
                f"{[u.number for u in l.units]}")
            assert not (set(u.number for u in l.units) & set(mine)), (
                "Was durch den Abzweig ging, kam nicht am Bypass vorbei.")
