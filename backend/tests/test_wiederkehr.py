"""►►► **Wiederkehrende Aufträge – die Schlaufe** (SYSTEM_LOGIC §5.10, W1–W9). ◄◄◄

Projektakte ``docs/konzept/wiederkehr.md``. Geprüft wird Verhalten: was entsteht, was wartet,
was nie mehr geht, und dass nichts doppelt entsteht.
"""

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.core import clock
from app.domain import loop as dl
from app.domain import statuses as st
from tests.runner import session
from tests.scenes import voucher as scene
from tests.scenes.voucher import do as _do, house as _house
from tests.test_zahlung_ablauf import _run_capture

CAPTURE = [{"module_type": "datenerfassung",
            "config": {"points": [{"label": "OK", "type": "bool"}]}}]


@pytest.fixture
def db():
    s = session()
    _house(s)
    try:
        yield s
    finally:
        s.rollback()


def _units(db, quantity=1):
    """``quantity`` freie Stücke eines neuen Artikels (Erzeugung durchlaufen)."""
    from app.models import Instance, InstanceUnit
    from app.services import instances
    art = scene.article(db, capture=False, steps=CAPTURE)
    order, _ = scene.release(db, art, quantity=quantity)
    _run_capture(db, order)
    rows = (db.query(InstanceUnit, Instance).join(Instance, Instance.id == InstanceUnit.instance_id)
            .filter(Instance.article_id == art.id).order_by(InstanceUnit.id).all())
    assert {u.status for u, _ in rows} == {st.FREIGEGEBEN}
    return art, [instances.unit_number(i, u) for u, i in rows]


def _draft(art, numbers, *, take=dl.SAME, steps=CAPTURE, **loop):
    return {
        "lines": [{"article_object_id": art.object_id, "quantity": len(numbers),
                   "origin": "lager", "returns": True,
                   "units": [{"number": n, "from_order": None} for n in numbers]}],
        "steps": steps,
        "loop": {"every": "month", "first": clock.today().isoformat(), "takes": [take], **loop},
    }


def _create(db, draft):
    from app.services import orders
    order = orders.create_order(db, draft, actor_id=None)
    db.flush()
    return order


def _order(db, object_id):
    from app.models import Order
    return db.query(Order).filter(Order.object_id == object_id).first()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DER KALENDER (rein, ohne Datenbank)
# ═══════════════════════════════════════════════════════════════════════════════

def test_month_end_takes_the_last_day_and_returns_to_the_anchor():
    """Wie ein Dauerauftrag: der 31. im Februar ist der 28. (29.), im März wieder der 31."""
    assert dl.after(date(2027, 1, 31), "month", 31) == date(2027, 2, 28)
    assert dl.after(date(2027, 2, 28), "month", 31) == date(2027, 3, 31)
    assert dl.after(date(2028, 1, 31), "month", 31) == date(2028, 2, 29)
    assert dl.after(date(2026, 11, 14), "year", 14) == date(2027, 11, 14)
    assert dl.after(date(2026, 12, 15), "quarter", 15) == date(2027, 3, 15)
    assert dl.after(date(2026, 12, 30), "week", 30) == date(2027, 1, 6)


def test_count_and_until_end_the_chain():
    base = {"every": "year", "next": "2027-11-14", "anchor": 14, "until": None, "left": 1}
    assert dl.go_on(base)
    nxt = dl.follow(base)
    assert nxt["next"] == "2028-11-14" and nxt["left"] == 0 and not dl.go_on(nxt)
    assert not dl.go_on({**base, "left": None, "until": "2027-01-01"})


# ═══════════════════════════════════════════════════════════════════════════════
# ►► IM ENTWURF (W1)
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_loop_is_checked_in_the_draft_and_frozen_with_the_release(db):
    from app.services import loop, orders
    art, numbers = _units(db)
    bad = _draft(art, numbers, take=None)
    assert any("gleiche Einzelinstanzen oder FIFO" in m for m in orders.validate_draft(db, bad))
    past = _draft(art, numbers, first=(clock.today() - timedelta(days=1)).isoformat())
    assert any("Vergangenheit" in m for m in orders.validate_draft(db, past))
    both = _draft(art, numbers, until="2030-01-01", count=3)
    assert any("nicht beides" in m for m in orders.validate_draft(db, both))
    good = _draft(art, numbers, first=(clock.today() + timedelta(days=1)).isoformat())
    assert orders.validate_draft(db, good) == []
    order = _create(db, good)
    frozen = loop.settings(db, order)
    assert frozen["every"] == "month" and frozen["lines"] == [{"take": "same", "units": numbers}]
    assert loop.view(db, order)["state"] == loop.RUN


def test_a_loop_needs_a_regular_order(db):
    """W4/W8: wer ein Stück einem laufenden Auftrag entnimmt (Abweichung), bekommt keine
    Schlaufe – und mit der Schlaufe kein verbotener Anlegeweg (keine Nummer verbrannt)."""
    from app.services import orders
    art, numbers = _units(db)
    running = _create(db, {**_draft(art, numbers), "loop": None})
    draft = _draft(art, numbers)
    draft["lines"][0]["units"][0]["from_order"] = running.object_id
    found = orders.validate_draft(db, draft)
    assert any("regulären Auftrag" in m and "ist in Auftrag" in m for m in found)
    with pytest.raises(HTTPException):
        orders.create_order(db, draft, actor_id=None)


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DER NACHFOLGER (W2, W3, W5)
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_successor_is_a_copy_and_never_comes_twice(db):
    from sqlalchemy.exc import IntegrityError
    from app.models import ProcessStep
    from app.services import log, loop
    art, numbers = _units(db)
    first = _create(db, _draft(art, numbers))
    # Solange das Stück im Auftrag steckt, wartet die Wiederholung (W5) – mit Grund.
    assert first in loop.due(db)
    reason, final = loop.problem(db, first)
    assert "ist in Auftrag" in reason and not final
    assert loop.view(db, first)["state"] == loop.WAIT
    assert any(oid == first.object_id for oid, _, _ in loop.todo_items(db))
    assert loop.create_next(db, first) is None
    _run_capture(db, first)
    second = loop.create_next(db, first)
    assert second is not None
    db.flush()
    # Eine 1:1-Kopie: dieselben Module, dieselben Stücke, dieselbe Schlaufe mit dem nächsten Termin.
    kinds = [s.module_type for s in db.query(ProcessStep).filter(
        ProcessStep.order_id == second.id).order_by(ProcessStep.position)]
    assert kinds == ["datenerfassung"]
    nxt = loop.settings(db, second)
    assert nxt["lines"] == [{"take": "same", "units": numbers}]
    assert nxt["next"] == dl.after(clock.today(), "month", clock.today().day).isoformat()
    assert loop.successor(db, first) == second.object_id
    assert loop.predecessor(db, second) == first.object_id
    view = loop.view(db, first)
    assert view["state"] == loop.CONTINUED and not view["may_end"]
    # Nie zwei: ein zweiter Lauf legt nichts an, und die Datenbank weist einen zweiten ab.
    assert loop.create_next(db, first) is None
    point = db.begin_nested()
    with pytest.raises(IntegrityError):
        log.event(db, loop.NEXT, 123456789, {"from": first.object_id})
    point.rollback()
    from app.services import order_state
    assert order_state.deviation_flags(db, [second.id])[second.id] is False


def test_fifo_takes_only_what_is_free_with_us(db):
    """«FIFO» nimmt in jeder Wiederholung neu – nur «Freigegeben», nie ein gesperrtes."""
    from app.services import loop
    art, numbers = _units(db, quantity=3)
    first = _create(db, _draft(art, numbers[:1], take=dl.FIFO))
    _run_capture(db, first)
    second = loop.create_next(db, first)
    assert second is not None
    from app.models import OrderUnit
    assert db.query(OrderUnit).filter(OrderUnit.order_id == second.id).count() == 1


def test_a_scrapped_unit_stops_the_loop_for_good_and_only_ending_helps(db):
    """W6/W7: verschrottet ⇒ «geht nicht mehr» (rot in «zu tun»); beendet wird am neuesten
    Auftrag der Kette, auch wenn er abgeschlossen ist – der Auftrag ändert sich nicht."""
    from app.models import InstanceUnit
    from app.services import instances, loop
    art, numbers = _units(db)
    first = _create(db, _draft(art, numbers))
    _run_capture(db, first)
    unit = instances.find_units(db, numbers)[numbers[0]]
    db.query(InstanceUnit).filter(InstanceUnit.id == unit.id).update(
        {"status": st.VERSCHROTTET})
    db.flush()
    reason, final = loop.problem(db, first)
    assert final and "Verschrottet" in reason
    assert loop.view(db, first)["state"] == loop.STUCK
    assert any(oid == first.object_id and red for oid, _, red in loop.todo_items(db))
    assert loop.create_next(db, first) is None
    loop.end(db, first)
    assert loop.view(db, first)["state"] == loop.ENDED_STATE
    assert first not in loop.due(db)
    with pytest.raises(HTTPException):
        loop.end(db, first)


def test_ending_happens_only_at_the_newest_order(db):
    from app.services import loop
    art, numbers = _units(db)
    first = _create(db, _draft(art, numbers))
    _run_capture(db, first)
    second = loop.create_next(db, first)
    with pytest.raises(HTTPException):
        loop.end(db, first)
    loop.end(db, second)
    assert loop.view(db, second)["state"] == loop.ENDED_STATE


def test_after_the_last_count_the_chain_ends_by_itself(db):
    from app.services import loop
    art, numbers = _units(db)
    first = _create(db, _draft(art, numbers, count=1))
    _run_capture(db, first)
    second = loop.create_next(db, first)
    assert second is not None and loop.settings(db, second)["left"] == 0
    _run_capture(db, second)
    assert loop.view(db, second)["state"] == loop.DONE
    assert second not in loop.due(db)


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DIE ZAHLUNG IN DER WIEDERHOLUNG (W9)
# ═══════════════════════════════════════════════════════════════════════════════

def _with_payment(db, art, numbers, *, priced=True):
    who = scene.party(db)
    cfg = {"direction": "in", "parties": [{"party": who.object_id, "ref": ""}],
           "ownership": "party", "payment_days": 30, "lead_days": 0, "incoterm": "EXW"}
    if priced:
        cfg["prices"] = [{"article": art.object_id, "price": "890.00"}]
    steps = [{"module_type": "beleg", "config": cfg}, *CAPTURE]
    return _draft(art, numbers, steps=steps), who


def _beleg(db, order):
    from app.models import ProcessStep
    from app.services import voucher as vs
    step = db.query(ProcessStep).filter(ProcessStep.order_id == order.id,
                                        ProcessStep.module_type == "beleg").first()
    return step, vs.of_step(db, step.id)


def test_a_promised_loop_offers_and_agrees_by_itself_quietly(db):
    """Dieselben Schritte (Offerte → Zusage), ausgeführt vom System, gestützt auf die Zusage zur
    Schlaufe – die Offerte entsteht als Dokument, eine Mail nicht. Die Offerte des ersten
    Auftrags nennt die Wiederholung."""
    from app.domain import voucher as vo
    from app.models import VoucherDocument
    from app.services import loop, voucher_docs
    art, numbers = _units(db)
    draft, who = _with_payment(db, art, numbers)
    first = _create(db, draft)
    step, row = _beleg(db, first)
    from app.services import voucher_head
    voucher_head.sync_lines(db, row, first, step)
    paper = voucher_docs.build(db, row=row, kind=vo.OFFER_DOC, party=who.object_id)
    assert any(k == "Wiederholung" and "monatlich" in v for k, v in paper.terms)
    _do(db, first, step, "ask")
    _do(db, first, step, "agree", party=who.object_id)
    _run_capture(db, first)
    second = loop.create_next(db, first)
    step2, row2 = _beleg(db, second)
    assert row2.stage == vo.AGREED
    docs = db.query(VoucherDocument).filter(VoucherDocument.voucher_id == row2.id).all()
    assert docs and all(d.message_id is None for d in docs), "Hinaus geht nichts von selbst."
    view = loop.view(db, second)
    assert view["agreed_from"] == first.object_id and view["agreed_on"]


def test_without_preset_prices_the_voucher_waits_at_the_offer(db):
    from app.domain import voucher as vo
    from app.services import loop
    art, numbers = _units(db)
    draft, who = _with_payment(db, art, numbers, priced=False)
    first = _create(db, draft)
    step, row = _beleg(db, first)
    from app.services import voucher_head
    lines = voucher_head.sync_lines(db, row, first, step)
    _do(db, first, step, "price", lines=[{"id": ln.id, "price": "500.00"} for ln in lines])
    _do(db, first, step, "ask")
    _do(db, first, step, "agree", party=who.object_id)
    _run_capture(db, first)
    second = loop.create_next(db, first)
    _, row2 = _beleg(db, second)
    assert row2.stage == vo.OFFER
    assert loop.view(db, second)["agreed_from"] is None


def test_every_state_of_a_loop_has_a_word_and_a_tone():
    """Jeder Zustand, den ``services/loop.view`` ableiten kann, hat Wort und Ampelton – sonst
    fiele die Karte beim ersten unbekannten Zustand mit einem KeyError aus."""
    from app.domain import loop as dl
    from app.services import loop as svc

    states = {svc.RUN, svc.WAIT, svc.STUCK, svc.ENDED_STATE, svc.DONE, svc.CONTINUED}
    assert states == set(dl.STATES)
    assert {tone for _, tone in dl.STATES.values()} <= {"pending", "done", "danger"}
