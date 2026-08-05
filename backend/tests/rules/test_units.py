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


def test_parallel_only_means_at_the_same_time(db, kinds, world):
    """**Parallel ist nur, was gleichzeitig läuft** (Testnotiz #548).

    Zwei Abweichungen aus demselben Schritt sind eine Teilung in zwei Richtungen, solange
    beide offen sind. War die erste längst abgeschlossen, als die zweite entstand, ist das
    eine **Abfolge** – zwei Teilungen nacheinander. Vorher landeten beide in EINER Teilung,
    und der Bypass rechnete auch die zurückgegebene Menge ab: Mengen und Nummern passten
    nicht mehr zusammen."""
    from app.models import ArticleProcessStep
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc
    from app.services.orders import to_order_response

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    first = _make_deviation(db, main, inst, user, 2)
    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == first.id).first())
    insp_svc.record_inspection(db, first, InspectionUpdate(
        samples=[InspectionSample(instance_id=inst.object_id, slot=i + 1, values={"_ok": True})
                 for i in range(2)], step_id=step.id), user)
    db.commit()
    db.refresh(first)
    assert first.status == "completed"
    second = _make_deviation(db, main, inst, user, 1)

    resp = to_order_response(db, main)
    splits = [n for n in resp.flow_nodes if n.kind == "split"]
    assert len(splits) == 2, (
        f"Erst die eine, dann die andere – zwei Teilungen, nicht eine parallele: "
        f"{[n.branch_object_ids for n in splits]}")
    assert [n.branch_object_ids for n in splits] == [[first.object_id], [second.object_id]]

    # Und überall passen Menge und Nummern zusammen.
    for n in splits:
        for l in (n.bypass.lots if n.bypass else []):
            assert len(l.units) == int(l.quantity), (
                f"Bypass: {l.quantity} Stk, aber {len(l.units)} Nummern")
    for e in resp.flow_edges:
        for l in e.lots:
            assert len(l.units) == int(l.quantity), (
                f"Kante: {l.quantity} Stk, aber {len(l.units)} Nummern")


def test_a_piece_changes_its_state_it_does_not_vanish(db, kinds, world):
    """**Testnotiz #549** – ein verschrottetes Stück bleibt sichtbar, es wird nur rot.

    Es aus der Karte zu streichen hiess, dass ein Teil aus dem Nichts verschwindet: das
    Instanz-Detail zeigte plötzlich ``-2, -3, -4`` und niemand konnte sagen, wo ``-1``
    geblieben war. Dieselbe Regel, die für die Menge längst gilt (#481) – nur eine Ebene
    genauer. Für alles Rechnende zählt es trotzdem nicht mehr mit."""
    from app.services import units

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    dev = _make_deviation(db, main, inst, user, 1, steps=("scrap",))
    db.refresh(inst)
    doomed = units.numbers(inst, holder=dev.id)[0]
    _scrap(db, dev, inst, user, 1)
    db.refresh(inst)

    shown = {u.number: u for u in units.rows(inst, include_gone=True)}
    assert doomed in shown, (
        f"Das verschrottete Stück ist aus der Liste gefallen: {sorted(shown)}")
    assert shown[doomed].disposition == "scrapped", (
        "Es steht da – aber mit seinem eigenen Endzustand, nicht mit dem der Instanz.")
    assert doomed not in {u.number for u in units.rows(inst)}, (
        "Wer rechnet, sieht es NICHT: die Menge ist gesunken.")
    assert units.count(inst) == 3 and units.count(inst, include_gone=True) == 4
    assert units.verify(inst) == [], "Nummern und Mengen dürfen nie auseinanderlaufen."


def test_a_named_share_hands_over_its_own_pieces(db, kinds, world):
    """**Testnotiz #553** – die Stücke folgen dem genannten Anteil, nicht dem freien Topf.

    Kette Hauptauftrag → Abweichung → Abweichung: die zweite nimmt der ERSTEN etwas weg.
    Vorher griff die Vormerkung in den freien Topf – der aber gehört dem Erzeuger; beim
    anschliessenden Geradeziehen der Mengen tauschten Hauptauftrag und Enkel-Abweichung
    ihre Stücke, «aus dem Nichts»."""
    from app.services import units

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    d1 = _make_deviation(db, main, inst, user, 2)
    db.refresh(inst)
    before_main = set(units.numbers(inst, holder=main.id)) | set(units.numbers(inst, holder=None))
    before_d1 = set(units.numbers(inst, holder=d1.id))
    assert len(before_d1) == 2 and len(before_main) == 2

    d2 = _make_deviation(db, d1, inst, user, 1)     # genannter Anteil: der von D1
    db.refresh(inst)
    after_main = set(units.numbers(inst, holder=main.id)) | set(units.numbers(inst, holder=None))
    after_d1 = set(units.numbers(inst, holder=d1.id))
    after_d2 = set(units.numbers(inst, holder=d2.id))

    assert after_main == before_main, (
        f"Der Hauptauftrag war nicht gemeint und behält seine Stücke: "
        f"{sorted(before_main)} → {sorted(after_main)}")
    assert after_d2 <= before_d1, (
        f"Genommen wird beim GENANNTEN Anteil {sorted(before_d1)}, nicht irgendwo: "
        f"{sorted(after_d2)}")
    assert after_d1 | after_d2 == before_d1, (
        "Was die erste Abweichung hielt, teilen sich jetzt beide – nichts kommt dazu.")
    assert units.verify(inst) == []


def test_a_lot_never_names_pieces_it_did_not_carry(db, kinds, world):
    """**Testnotizen #559–#562** – zwei Fehler, ein Bild: Menge und Nummern gehören zusammen.

    (1) Eine **Weitergabe nach unten ist keine Rückgabe**: ein Abzweig, der 2 Stück übernimmt,
    davon 1 an seine eigene Abweichung weiterreicht und 1 zurückgibt, meldete «2 zurück» –
    gezählt wurde jede lebende Abgabe, nicht nur die echten Rückgaben.

    (2) Und die zurückgegebenen Stücke sind die der **Buchung**, nicht die, die einmal
    hineingingen – sonst nennt eine Menge von 1 beide Nummern."""
    from app.models import ArticleProcessStep
    from app.schemas.movement import MovementTarget, MovementUpdate
    from app.services import ledger, movement as mv_svc, sites
    from app.services.orders import to_order_response

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    branch = _make_deviation(db, main, inst, user, 2, steps=("movement",))
    inner = _make_deviation(db, branch, inst, user, 1, steps=("scrap",))
    _scrap(db, inner, inst, user, 1)
    db.commit()

    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == branch.id).first())
    company = sites.operator(db)
    mv_svc.record_movement(db, branch, MovementUpdate(targets=[MovementTarget(
        instance_id=inst.object_id, location_type="company",
        location_id=company.object_id)], step_id=step.id), user.id)
    db.commit()

    back = ledger.departed_of(db, branch.id)
    assert sum(b.quantity for b in back.values()) == 1, (
        f"Weitergereicht ist nicht zurückgegeben (#559): {dict(back)}")

    resp = to_order_response(db, main)
    lots = [l for n in resp.flow_nodes if n.kind == "split"
            for d in (resp.deviations or []) if d.object_id in n.branch_object_ids
            for l in (d.flow_back or [])]
    for l in lots:
        assert len(l.units) == int(l.quantity), (
            f"Rückgabe: {l.quantity} Stk, aber {len(l.units)} Nummern")
    # Und auf der ganzen Achse: Menge und Nummern sind dieselbe Aussage (#560/#561/#562).
    for e in resp.flow_edges:
        for l in e.lots:
            assert len(l.units) == int(l.quantity), (
                f"Kante: {l.quantity} Stk, aber {len(l.units)} Nummern – "
                f"der geladene JSONB-Wert darf nie an Ort und Stelle verändert werden.")


def test_a_cut_return_ends_the_chain(db, kinds, world):
    """**Testnotiz #563** – «die Rückführung kappen»: der Halter endet an dieser Stelle.

    Nimmt ein Unter-Auftrag ALLES und steht fest, dass nichts zurückkommt, wartet der
    Verleiher nicht bis zum Ende des Abzweigs – er ist im selben Moment abgebrochen,
    fortgeführt in diesem Auftrag. Und weil ein gekappter Auftrag niemanden deckt, greift
    dieselbe Regel eine Ebene höher: ein Unter-Unter-Auftrag kappt die ganze Kette."""
    from app.services import process

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 2)
    branch = _make_deviation(db, main, inst, user, 2)
    db.refresh(main)
    assert main.status == "released" and process.subject_shortfalls(db, main), (
        "Ohne Kappen wartet er – die Menge kann ja zurückkommen (#556).")

    inner = _make_deviation(db, branch, inst, user, 2, cut=True)
    db.refresh(branch)
    db.refresh(main)
    assert branch.status == "inactive" and branch.abort_into_id == inner.object_id, (
        f"Der Abzweig endet hier: {branch.status}/{branch.abort_into_id}")
    assert main.status == "inactive", (
        "Und der Hauptauftrag ebenso – die Kaskade ist dieselbe Regel, keine zweite "
        f"(ist {main.status}).")


def test_a_finished_order_still_names_its_pieces(db, kinds, world):
    """**Testnotizen #567–#570** – die Nummern überleben den Abschluss.

    Ein abgeschlossener Auftrag löst seine Reservierung; die Karte kennt ihn danach nicht
    mehr. Wurden die Nummern seiner Achse aus dieser Karte abgeleitet, stand dort plötzlich
    eine Menge **ohne eine einzige Nummer** («1 Stk × 100000651» statt «…-1») – und bei einem
    teilweise zurückgegebenen Auftrag eine halbe Liste, was schlimmer ist, weil sie
    vollständig aussieht.

    Die Regel ist dieselbe wie für die Vergangenheit einer Kante (#543/#544), nur konsequent
    zu Ende geführt: **die Nummern gehören in die Buchung** – auch die der Entstehung und die
    der Freigabe. Geprüft wird die Aussage, die ein Mensch am Bildschirm liest: *jede
    Materialzeile nennt so viele Stücke, wie sie Menge trägt.*"""
    from app.models import ArticleProcessStep
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc
    from app.services.orders import to_order_response

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    branch = _make_deviation(db, main, inst, user, 1, cut=True)
    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == branch.id,
                    ArticleProcessStep.step_type == "inspection").first())
    insp_svc.record_inspection(db, branch, InspectionUpdate(
        samples=[InspectionSample(instance_id=inst.object_id, slot=1, values={"_ok": True})],
        step_id=step.id), user)
    db.commit()
    db.refresh(branch)
    assert branch.status == "completed", branch.status

    for order, tag in ((main, "Hauptauftrag"), (branch, "gekappter Abzweig")):
        resp = to_order_response(db, order)
        for edge in resp.flow_edges:
            for lot in edge.lots:
                assert lot.unit_count == int(lot.quantity), (
                    f"{tag}: «{lot.quantity} Stk» nennt {lot.unit_count} Nummern "
                    f"({[u.number for u in lot.units]}) – beides muss zusammenpassen.")
    # Und zwar GENAU die, die er hielt – nicht irgendwelche.
    got = [u.number for e in to_order_response(db, branch).flow_edges
           for l in e.lots for u in l.units]
    assert got and set(got) == {f"{inst.object_id}-1"}, (
        f"Der gekappte Abzweig hielt …-1, zeigt aber {got}")


def test_an_order_releases_the_pieces_it_still_holds(db, kinds, world):
    """**Testnotizen #566/#572** – «hat es das Ziel erreicht, wird es freigegeben».

    Die Regel gilt für Auftrag und Unter-Auftrag gleich, und sie ist **eine Reihenfolge**,
    keine Fallunterscheidung: erst Geliehenes zurückgeben, dann freigeben, was übrig ist.

    Der Zustand gehört dabei zur **Menge**, nicht zur Instanz. Eine Charge kann geteilter
    Meinung sein: ein Stück durch den Prozess, drei noch in Arbeit – beides wahr, nur nicht
    über dieselbe Menge. Der Instanz-Skalar ist die **Projektion** darüber und sagt «am
    Lager», sobald ein Stück entnehmbar ist (Testnotiz #604) – sonst fände FIFO die Charge
    nicht. Dass nicht alles frei ist, trägt die **Menge**: ``inventory.ready_qty`` zählt
    Stücke und gibt kein einziges heraus, das noch im Prozess ist."""
    from app.models import ArticleProcessStep
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc, units

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)

    # (a) Gewöhnliche Abweichung: gibt zurück → hält nichts → gibt nichts frei (#332).
    plain = _make_deviation(db, main, inst, user, 1)
    _run_inspection(db, plain, inst, user, 1)
    db.refresh(inst)
    assert not [u for u in units.of(inst) if u.released], (
        "Ein zurückgegebenes Stück ist geklärt, nicht produziert – es bleibt im Prozess.")

    # (b) Gekappter Abzweig: behält sein Stück → gibt es frei, obwohl der Eltern läuft.
    cut = _make_deviation(db, main, inst, user, 1, cut=True)
    _run_inspection(db, cut, inst, user, 1)
    db.refresh(inst)
    freed = [u.number for u in units.of(inst) if u.released]
    assert len(freed) == 1, f"Genau sein Stück ist frei, nicht mehr und nicht weniger: {freed}"
    # **Der Datensatz sagt «am Lager», die MENGE sagt wie viel** (#604): sonst fände FIFO
    # die Charge nicht, obwohl ein entnehmbares Stück darin liegt.
    assert (inst.quality, inst.disposition) == ("passed", "in_stock"), (
        f"Ein entnehmbares Stück macht die Charge auffindbar (ist {inst.quality}/"
        f"{inst.disposition}).")
    from app.services import inventory
    assert inventory.ready_qty(inst) == Decimal(1), (
        "…aber entnehmbar ist genau EINES – die drei laufenden gehören ihren Aufträgen "
        f"(ist {inventory.ready_qty(inst)}).")
    assert not units.verify(inst), units.verify(inst)


def _run_inspection(db, order, inst, user, n):
    """Den Datenerfassungs-Schritt eines Auftrags durchlaufen – bis zum Abschluss."""
    from app.models import ArticleProcessStep
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc

    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == order.id,
                    ArticleProcessStep.step_type == "inspection").first())
    if step is None:                       # Erzeugungsauftrag → der Prozess des Artikels
        from app.services import process
        step = process.order_step_defs(db, order)[0]
    insp_svc.record_inspection(db, order, InspectionUpdate(
        samples=[InspectionSample(instance_id=inst.object_id, slot=i + 1,
                                  values={"_ok": True}) for i in range(n)],
        step_id=step.id), user)
    db.commit()
    db.refresh(order)


def test_a_released_piece_belongs_to_nobody(db, kinds, world):
    """**Testnotizen #573/#577** – freigegeben heisst frei.

    Der «unbeanspruchte Rest gehört dem Erzeuger» (``inventory.rest_owner``) gilt für das,
    was noch im Prozess ist. Als die Freigabe je Stück kam, fielen fertige Stücke ohne
    Halter unter dieselbe Regel und wurden dem Erzeuger erneut zugeschlagen – mit zwei
    sichtbaren Folgen: das Instanz-Detail zeigte sie als «Reserviert» (gelb) statt
    «Freigegeben» (grün), und auf den Kanten des Erzeugers tauchten längst fertige Nummern
    wieder auf und verdrängten die, die er wirklich hält.

    Und der **Hover** muss dasselbe sagen wie die Pille: er las den Instanz-Skalar, und der
    bleibt bei einer teilweise freigegebenen Charge bewusst «Im Prozess» (#574)."""
    from app.services import units

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    cut = _make_deviation(db, main, inst, user, 1, cut=True)
    _run_inspection(db, cut, inst, user, 1)
    db.refresh(inst)

    free = [u for u in units.of(inst) if u.released]
    assert len(free) == 1, f"Genau ein Stück ist durch: {[u.number for u in free]}"

    # (a) Es gehört niemandem mehr – sonst «Reserviert» statt «Freigegeben» (#573).
    row = next(r for r in units.rows(inst) if r.number == free[0].number)
    assert row.order_object_id is None, (
        f"Ein freigegebenes Stück trägt keinen Halter (ist {row.order_object_id}).")
    assert (row.quality, row.disposition) == ("passed", "in_stock"), (row.quality, row.disposition)

    # (b) Der Erzeuger zieht es nicht wieder an sich (#577).
    mine = [u.number for u in units.owned_by(inst, main.id, db)]
    assert free[0].number not in mine, (
        f"Der Erzeuger hält fertige Stücke nicht erneut: {mine}")
    assert len(mine) == 3, f"Er hält genau die drei, die noch laufen: {mine}"

    # (c) Der Hover nennt denselben Zustand wie die Pille (#574).
    hover = units.rows_for(inst, [free[0].index])
    assert (hover[0].quality, hover[0].disposition) == ("passed", "in_stock"), (
        f"Hover und Pille müssen dasselbe sagen (ist {hover[0].quality}/{hover[0].disposition}).")


def test_the_instance_state_is_a_projection_over_its_pieces(db, world, kinds):
    """**Der Zustand des Datensatzes wird ABGELEITET, nicht zugewiesen** (Testnotiz #604).

    Ein Datensatz trägt genau einen Zustand, eine Charge aber viele. Die Frage ist nicht,
    welcher stimmt, sondern welcher auf den Datensatz gehört – und die Rangfolge folgt dem,
    wonach man sucht: **≥ 1 Stück freigegeben → «am Lager»**, sonst «Im Prozess», sonst der
    Endzustand. Sonst fände FIFO eine Charge nicht, in der entnehmbare Stücke liegen.

    Dass nicht alles frei ist, trägt die **Menge** (``inventory.ready_qty``) – nicht der
    Skalar. Zwei Fragen, zwei Namen: «wem gehört nichts» (``free_qty``) und «was ist
    entnehmbar».

    Der gemeldete Hänger (#601/#602) folgt aus der Zuweisung: der Skalar wurde in genau dem
    Moment gesetzt, in dem das letzte lebende Stück freigegeben wurde. Schied danach ein
    Geschwister-Stück aus, kippte die Bedingung nachträglich – aber niemand rechnete sie
    neu, und die Instanz blieb für immer «Im Prozess», obwohl jedes Stück «Freigegeben»
    zeigte. Als Projektion kann das nicht mehr auseinanderlaufen."""
    from app.services import inventory, units

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 3)

    # Ein Abzweig nimmt 2 Stück, führt sie durch und behält sie (gekappt) → 2 frei.
    cut = _make_deviation(db, main, inst, user, 2, cut=True)
    _run_inspection(db, cut, inst, user, 2)
    db.refresh(inst)
    assert (inst.quality, inst.disposition) == ("passed", "in_stock"), (
        f"Ein entnehmbares Stück macht die Charge auffindbar (ist {inst.quality}/"
        f"{inst.disposition}) – sonst sucht FIFO daran vorbei.")
    assert inventory.ready_qty(inst) == Decimal(2), (
        f"…entnehmbar sind aber genau 2, nicht 3 ({inventory.ready_qty(inst)}).")

    # Jetzt scheidet das letzte laufende Stück aus – genau der gemeldete Hänger.
    gone = _make_deviation(db, main, inst, user, 1, steps=("scrap",), cut=True)
    _scrap(db, gone, inst, user, 1)
    db.refresh(inst)
    assert (inst.quality, inst.disposition) == ("passed", "in_stock"), (
        "Der Datensatz bleibt «am Lager» – vorher fiel er zurück auf «Im Prozess» und kam "
        f"nie wieder heraus (#601/#602; ist {inst.quality}/{inst.disposition}).")
    assert units.project(inst) == (inst.quality, inst.disposition), (
        "Skalar und Projektion sind dieselbe Aussage – sonst gibt es wieder zwei.")


def test_fifo_never_hands_out_a_piece_that_is_still_in_process(db, world, kinds):
    """Die Kehrseite von #604: der Datensatz sagt «am Lager», die **Menge** sagt wie viel.

    Ohne sie wäre die Projektion ein Rückschritt – FIFO fände die Charge und nähme Stücke,
    die noch mitten in einem anderen Auftrag stecken."""
    from app.models import ArticleProcessStep, Order
    from app.routers import orders as R
    from app.services import inventory

    user, _ = world
    main, inst = _make_order(db, kinds["batch"], user, 4)
    cut = _make_deviation(db, main, inst, user, 1, cut=True)
    _run_inspection(db, cut, inst, user, 1)
    db.refresh(inst)
    assert inventory.ready_qty(inst) == Decimal(1), inventory.ready_qty(inst)

    taker = Order(object_id=None, article_id=kinds["batch"].id, quantity=Decimal(3),
                  status="draft")
    db.add(taker)
    db.flush()
    db.add(ArticleProcessStep(order_id=taker.id, step_type="inspection", position=0,
                              sample_percent=100))
    db.flush()
    R._do_release(db, taker, user.id)
    db.commit()
    db.refresh(inst)

    held = [r for r in ((inst.units or {}).get("r") or [])
            if r.get("o") == taker.id and not r.get("s")]
    assert not held, (
        f"Kein Stück im Prozess darf per FIFO vergeben werden: {held}")


def test_an_order_only_takes_over_the_share_it_reserved(db, world, kinds):
    """**Übernommen wird, was reserviert wurde – nicht die ganze Instanz** (Testnotiz #615).

    Der FIFO-Zweig der Allokation liess das Mengen-Argument weg; die Buchung fiel auf
    ``inst.quantity`` zurück. Ein Auftrag über **1 Stück** nahm damit eine 4er-Charge
    komplett in seine Obhut, gab beim Abschluss nur seinen Anspruch (1) frei – und hielt
    die restlichen 3 für immer. Im Fluss stand die richtige Instanznummer mit der falschen
    Menge; im Bestand fehlten drei Stück, die niemand angefasst hatte.

    Der Fix ist ein fehlendes Argument – und dass es keinen Vorgabewert mehr gibt, damit
    aus «vergessen» kein stilles Falschbuchen werden kann."""
    from app.models import Article, ArticleProcessStep, Order
    from app.routers import orders as R
    from app.services import ledger
    from app.services.objects import next_object_id
    from app.services.reservation import reserved_for

    user, _ = world
    # **Ein eigener Artikel**: sonst deckt FIFO sich aus dem Bestand der Nachbar-Tests,
    # und der Test prüfte am Ende eine andere Instanz als die, die er aufgebaut hat.
    art = Article(object_id=next_object_id(db), name=f"Nur hier {next_object_id(db)}",
                  unit="pcs", serialization="batch", status="released")
    db.add(art)
    db.flush()
    db.add(ArticleProcessStep(article_id=art.id, step_type="inspection", position=0,
                              sample_percent=100))
    db.commit()
    main, inst = _make_order(db, art, user, 4)
    _run_inspection(db, main, inst, user, 4)          # 4 ans Lager
    db.refresh(inst)

    taker = Order(object_id=None, article_id=art.id, quantity=Decimal(1), status="draft")
    db.add(taker)
    db.flush()
    db.add(ArticleProcessStep(order_id=taker.id, step_type="inspection", position=0,
                              sample_percent=100))
    db.flush()
    R._do_release(db, taker, user.id)
    db.commit()
    db.refresh(inst)

    assert reserved_for(inst, taker.id) == Decimal(1), reserved_for(inst, taker.id)
    took = [m for m in ledger.moves_of(db, taker.id) if m.kind == "taken"]
    assert took and took[-1].quantity == Decimal(1), (
        f"Er übernimmt 1 Stück, nicht die ganze Charge: {[str(m.quantity) for m in took]}")

    _run_inspection(db, taker, inst, user, 1)
    db.refresh(inst)
    free = sum(v for b, v in ledger.lots(db, inst).items() if b.holder is None)
    assert free == Decimal(4), (
        f"Nach dem Abschluss sind alle 4 wieder frei – vorher hielt er 3 für immer ({free}).")
    assert ledger.verify_instance(db, inst) == [], ledger.verify_instance(db, inst)
