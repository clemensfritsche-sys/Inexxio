"""►►► **Das eine Datum am Auftrag** (Projektakte ``docs/konzept/aufgaben.md`` §5, Runde 2). ◄◄◄

Bug-Formen, gegen die jeder Wächter steht:

- ein Datum in der Vergangenheit, eine unbekannte Art, «bis» und «ab» zugleich
- das Datum lässt sich an einem abgeschlossenen Auftrag noch verschieben
- «ab» X erzeugt vorher schon eine Aufgabe · «bis» X reiht sich nicht nach X ein
- der Nachfolger einer Wiederholung verliert das Datum, das Wort oder den Abstand – oder sein
  Datum liegt in der Vergangenheit (dann entstünde er nie)
- ein verschobenes Datum lässt eine gesendete Offerte gültig
"""

from datetime import date, timedelta

import pytest

from app.core import clock
from app.domain import order_date
from app.domain.errors import Conflict, Invalid
from app.services import loop, orders, tasks
from tests.test_wiederkehr import _create, _draft, _units, db  # noqa: F401 (Fixture)
from tests.test_zahlung_ablauf import _run_capture

TODAY = clock.today()


def _day(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _plain(art, numbers, **date_):
    draft = {**_draft(art, numbers), "loop": None}
    if date_:
        draft["date"] = date_
    return draft


# ─── Die Regel (rein) ──────────────────────────────────────────────────────────────────

def test_one_date_until_or_from_never_in_the_past():
    assert order_date.problem(None, TODAY) is None
    assert order_date.clean({"kind": "until", "on": _day(3)}, TODAY) == (
        "until", TODAY + timedelta(days=3))
    assert order_date.clean(None, TODAY) == (None, None)
    for bad in ({"kind": "both", "on": _day(1)}, {"kind": "from", "on": "morgen"},
                {"kind": "from", "on": _day(-1)}):
        assert order_date.problem(bad, TODAY)
        with pytest.raises(ValueError):
            order_date.clean(bad, TODAY)


# ─── Am Auftrag ────────────────────────────────────────────────────────────────────────

def test_the_date_is_set_with_the_release_and_moved_while_in_process(db):
    art, numbers = _units(db)
    past = _plain(art, numbers, kind="until", on=_day(-1))
    assert any("Vergangenheit" in m for m in orders.validate_draft(db, past))
    order = _create(db, _plain(art, numbers, kind="until", on=_day(5)))
    assert (order.date_kind, order.date_on) == ("until", TODAY + timedelta(days=5))
    orders.set_date(db, order, {"kind": "from", "on": _day(2)})
    assert (order.date_kind, order.date_on) == ("from", TODAY + timedelta(days=2))
    with pytest.raises(Invalid):
        orders.set_date(db, order, {"kind": "from", "on": _day(-2)})
    orders.set_date(db, order, None)
    assert (order.date_kind, order.date_on) == (None, None)
    _run_capture(db, order)
    with pytest.raises(Conflict):
        orders.set_date(db, order, {"kind": "until", "on": _day(1)})


# ─── Die Aufgaben: das Arztpraxis-Modell ───────────────────────────────────────────────

def _step_task(db, order):
    found = [t for t in tasks.collect(db) if t.object_id == order.object_id
             and t.key.startswith("step:")]
    return found[0] if found else None


def test_from_hides_the_task_until_the_day_and_until_lines_it_up_at_the_day(db):
    art, numbers = _units(db)
    order = _create(db, _plain(art, numbers))
    plain = _step_task(db, order)
    assert plain is not None, "Ohne Datum: seit es zu tun ist."
    orders.set_date(db, order, {"kind": "from", "on": _day(3)})
    assert _step_task(db, order) is None, "«ab» in drei Tagen: vorher keine Aufgabe."
    orders.set_date(db, order, {"kind": "from", "on": _day(0)})
    assert _step_task(db, order).since == tasks._at(TODAY)
    orders.set_date(db, order, {"kind": "until", "on": _day(9)})
    task = _step_task(db, order)
    assert task is not None and task.since == tasks._at(TODAY + timedelta(days=9)), (
        "«bis» X: die Aufgabe gibt es, ihr Datum ist X.")


# ─── Die Wiederholung ──────────────────────────────────────────────────────────────────

def test_the_successor_keeps_word_and_distance_and_never_lies_in_the_past(db):
    first = date(2027, 1, 10)
    order = type("O", (), {"date_kind": "until", "date_on": TODAY + timedelta(days=4),
                           "object_id": 0, "created_at": clock.utcnow()})()
    assert loop._next_date(db, order, first) == {"kind": "until",
                                                 "on": first + timedelta(days=4)}
    late = TODAY - timedelta(days=30)
    assert loop._next_date(db, order, late)["on"] == TODAY, (
        "Wartete der Nachfolger, gilt heute – sonst wiese ihn die Freigabe ab.")
    order.date_on = None
    assert loop._next_date(db, order, first) is None


def test_a_successor_is_created_with_the_date(db):
    art, numbers = _units(db)
    draft = _draft(art, numbers, first=_day(0))
    draft["date"] = {"kind": "from", "on": _day(2)}
    order = _create(db, draft)
    _run_capture(db, order)
    new = loop.create_next(db, order)
    assert new is not None
    assert (new.date_kind, new.date_on) == ("from", TODAY + timedelta(days=2))
