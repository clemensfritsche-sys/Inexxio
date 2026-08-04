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


def test_station_6_der_hauptauftrag_wird_genau_einmal_gefragt(db, chain):
    """Nach dem Abschluss der Abweichung: EINE Entscheidung, oben, wo die Menge geschuldet
    wird – nicht auf jeder Ebene der Kette."""
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
    short = process.subject_shortfalls(db, main)
    assert short and sum(short.values()) == Decimal(1), (
        f"Jetzt fehlt dem Hauptauftrag genau das verschrottete Stück: {dict(short)}")
    assert not supply.covering_sub_orders(db, main), (
        "Niemand arbeitet mehr daran – JETZT ist die Frage fällig (und nur hier).")
