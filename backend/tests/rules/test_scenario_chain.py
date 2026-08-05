"""**Das Szenario-Netz: die Kette, die beim Testen wirklich gefahren wird.**

Auftrag → Abweichung → Abweichung → Verschrottung → Klärung. Genau diese Abfolge hat die
letzten drei Testrunden getragen (Notizen #505, #520, #522/#523) – und jedes Mal fiel der
Fehler erst am Bildschirm auf, Tage nach der Änderung, die ihn verursacht hatte.

Darum läuft sie ab jetzt bei **jedem Push** durch die echten Dienste. Geprüft wird nicht
eine Innensicht, sondern das, was am Bildschirm steht: Fehlmenge, Pause, wer gefragt wird,
was auf den Kanten liegt und was das Journal sagt. Bricht eine Station, sagt der Text,
welche Aussage nicht mehr stimmt.
"""

from decimal import Decimal

import pytest

from .conftest import _make_deviation, _make_order, _scrap  # noqa: F401


@pytest.fixture(scope="module")
def chain(db, world):
    """Die Kette einmal aufbauen; die Stationen prüfen darauf auf."""
    user, art = world
    main, inst = _make_order(db, art, user, 4)
    dev = _make_deviation(db, main, inst, user, 4)              # nimmt alle 4
    sub = _make_deviation(db, dev, inst, user, 1, steps=("scrap",))   # nimmt 1 davon
    _scrap(db, sub, inst, user, 1)                              # und verschrottet es
    return dict(user=user, main=main, dev=dev, sub=sub, inst=inst)


def test_station_1_die_ausleihe_ist_die_unterdeckung(db, chain):
    """Der Hauptauftrag hat alles verliehen – ihm fehlt alles, aber er wird nicht gefragt."""
    from app.services import process, supply

    main, dev = chain["main"], chain["dev"]
    assert process.subject_shortfalls(db, main), (
        "Was eine laufende Abweichung hält, hat der Eltern nicht – das IST die Ausleihe.")
    covering = [o.object_id for o in supply.covering_sub_orders(db, main)]
    assert dev.object_id in covering, (
        "Es läuft jemand daran: der Eltern WARTET, er wird nicht um eine Entscheidung "
        "gebeten (sonst stünde eine tote Frage im Fluss).")


def test_station_2_die_abweichung_arbeitet_weiter(db, chain):
    """Die Abweichung hat 1 von 4 verloren – und läuft mit 3 weiter (#522/#523)."""
    from app.services import process

    dev = chain["dev"]
    assert not process.subject_shortfalls(db, dev), (
        "Ein festes Subjekt schuldet nichts: es hat weniger zu tun, nicht zu wenig.")
    assert not process.is_paused(db, dev), (
        "Und darum ruht sein Prozess auch nicht – der Schritt bleibt bedienbar.")
    states = {s["step_type"]: s["state"] for s in process.build_order_steps(db, dev)}
    assert states.get("inspection") in ("active", "done"), states


def test_station_3_die_untere_abweichung_ist_fertig(db, chain):
    """Sie hat verschrottet – ihr Auftrag ist damit abgeschlossen, nicht offen."""
    db.refresh(chain["sub"])
    assert chain["sub"].status == "completed", chain["sub"].status


def test_station_4_das_journal_bleibt_ausgeglichen(db, chain):
    """Die Buchhaltung muss stimmen – sonst ist jede Anzeige darüber Zufall."""
    from app.services import ledger

    inst = chain["inst"]
    db.refresh(inst)
    assert ledger.verify_instance(db, inst) == [], (
        "Journal und Projektion dürfen nie auseinanderlaufen.")
    lots = ledger.lots(db, inst)
    assert sum(lots.values()) == Decimal(4), (
        f"Die Menge verschwindet nicht – sie wechselt den Topf: {lots}")
    assert any(b.disposition == "scrapped" and v == 1 for b, v in lots.items()), lots


def test_ein_ganz_ausgesteuertes_teil_ist_kein_drift(db, world):
    """**Die Menge verschwindet nicht, nur der Zustand ändert sich** (#481) – auch im Wächter.

    Eine ganz ausgesteuerte Instanz BEHÄLT ihre Menge; im Journal liegt sie danach
    vollständig im terminalen Topf. «Lebend 0 ≠ Projektion 1» ist deshalb kein Drift,
    sondern genau das erwartete Bild – die Projektion sagt es über ihre eigene
    ``disposition``. Der Wächter meldete es trotzdem, und zwar bei **jedem** Ausschuss
    (Systemprotokoll zu #598). Ein Wächter, der im Normalbetrieb anschlägt, ist von einem
    kaputten nicht zu unterscheiden."""
    from app.services import ledger

    user, art = world
    order, inst = _make_order(db, art, user, 1)
    dev = _make_deviation(db, order, inst, user, 1, steps=("scrap",))
    _scrap(db, dev, inst, user, 1)
    db.refresh(inst)

    assert inst.disposition == "scrapped" and inst.quantity == Decimal(1), (
        "Die Instanz behält ihre Menge – ihr Endzustand IST die «Wo»-Aussage (#481).")
    assert ledger.verify_instance(db, inst) == [], (
        "Journal und Projektion sagen dasselbe: alles im terminalen Topf. Das ist kein "
        "Widerspruch, den man melden müsste.")


def test_station_5_die_kante_zeigt_EINE_zeile_je_zustand(db, chain):
    """Der Fluss des Hauptauftrags: keine doppelte Zeile derselben Instanz (#520)."""
    from app.services.orders import to_order_response

    resp = to_order_response(db, chain["main"])
    for i, edge in enumerate(resp.flow_edges):
        seen = [(l.instance_object_id, l.quality, l.disposition) for l in edge.lots]
        assert len(seen) == len(set(seen)), (
            f"Kante {i}: dieselbe Instanz steht im selben Zustand mehrfach – "
            f"«3 Stk × X» + «1 Stk × X» statt «4 Stk × X» (#520): {edge.lots}")
        if not edge.reached:
            assert edge.lots == [], (
                f"Kante {i} ist noch nicht erreicht – sie darf nichts behaupten (#521).")


def test_station_6_der_hauptauftrag_entscheidet_sich_selbst(db, chain):
    """Nach dem Abschluss der Abweichung: die Entscheidung fällt **automatisch** (#556).

    Niemand hält die fehlende Menge mehr – sie ist verschrottet und kommt nicht zurück.
    Damit gibt es nichts zu entscheiden: das Soll des Hauptauftrags sinkt darauf, und er
    läuft mit weniger normal weiter. Vorher stand hier eine Frage, die nur eine sinnvolle
    Antwort hatte – und bis sie beantwortet war, ruhte der ganze Auftrag."""
    from app.models import ArticleProcessStep
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc, process, supply

    user, dev, main, inst = chain["user"], chain["dev"], chain["main"], chain["inst"]
    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == dev.id,
                    ArticleProcessStep.step_type == "inspection").first())
    insp_svc.record_inspection(db, dev, InspectionUpdate(
        samples=[InspectionSample(instance_id=inst.object_id, slot=n + 1,
                                  values={"_ok": True}) for n in range(3)],
        step_id=step.id), user)
    db.commit()
    db.refresh(dev)
    assert dev.status == "completed", "Die Abweichung ist mit ihrer Prüfung durch."
    db.refresh(main)
    assert not supply.covering_sub_orders(db, main), (
        "Niemand arbeitet mehr daran – die Menge kommt nicht zurück.")
    assert not process.subject_shortfalls(db, main), (
        "Und genau darum ist sie schon gekürzt – es gibt nichts mehr zu entscheiden (#556).")
    assert main.quantity == Decimal(3), (
        f"Das Soll ist auf das Gesicherte gesunken (4 → 3), ist {main.quantity}.")
    assert not process.is_paused(db, main), "Der Prozess läuft weiter."
