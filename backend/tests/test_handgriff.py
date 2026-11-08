"""►►► **Der Handgriff und sein Probelauf** (Projektakte, Phase 5 §6). ◄◄◄

Ein Handgriff ruft die **echte Route** auf – als die Person, mit ihren Rechten. Der Probelauf
geht ganz durch und hinterlässt nichts; was nach aussen ginge, braucht die Hand.

Bug-Formen, gegen die diese Wächter stehen: (a) der Probelauf hinterlässt Zeilen oder Log;
(b) er geht nach aussen; (c) eine Person kann über einen Handgriff mehr als mit einem Klick;
(d) ein Handgriff ist eine Handlung, die es nicht gibt; (e) gespeichert wird nur halb.
"""

import socket

import pytest
from sqlalchemy import func

from app.core import outside
from app.models import Log, Message
from app.services import handgriff
from tests import factories
from tests.runner import session


@pytest.fixture
def people():
    """Personal und Admin, **festgeschrieben** – ein Handgriff läuft in eigener Sitzung."""
    db = session()
    staff = factories.new_person(db, "employee")
    boss = factories.new_person(db, "admin")
    db.commit()
    yield db, staff, boss
    db.close()


def _counts(db) -> tuple[int, int]:
    db.expire_all()
    return (db.query(func.count(Log.id)).scalar(), db.query(func.count(Message.id)).scalar())


def _note(about: int, text: str = "Kran 3 quietscht") -> dict:
    return {"channel": "note", "about": [about], "subject": "Kran 3", "body": text}


def test_the_probe_runs_through_and_leaves_nothing(people, monkeypatch):
    db, staff, _boss = people
    before = _counts(db)

    def no_network(*_a, **_k):
        raise AssertionError("(b) Der Probelauf ging nach aussen.")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    out = handgriff.call(staff.id, "POST", "/api/v1/erp/messages", _note(staff.object_id),
                         probe=True)
    assert out.ok, out.detail
    assert _counts(db) == before, "(a) Der Probelauf hat etwas hinterlassen."


def test_executing_saves_the_route_and_its_mark_together(people):
    db, staff, _boss = people
    marks = []

    def done(s, data):
        marks.append(handgriff.result_of(data))
        from app.services import log
        log.event(s, "test.done", staff.object_id, {"message": data["id"]})
    out = handgriff.call(staff.id, "POST", "/api/v1/erp/messages",
                         _note(staff.object_id, "gespeichert"), probe=False, done=done)
    assert out.ok, out.detail
    db.expire_all()
    msg = db.query(Message).filter(Message.id == out.data["id"]).one()
    assert msg.body == "gespeichert"
    assert db.query(Log).filter(Log.event == "test.done",
                                Log.payload["message"].as_integer() == msg.id).count() == 1


def test_a_failing_mark_saves_nothing(people):
    """(e) Scheitert ``done``, ist auch die Handlung nicht gespeichert – ganz oder gar nicht."""
    db, staff, _boss = people
    before = _counts(db)

    def done(_s, _data):
        raise RuntimeError("kaputt")
    with pytest.raises(RuntimeError):
        handgriff.call(staff.id, "POST", "/api/v1/erp/messages", _note(staff.object_id),
                       probe=False, done=done)
    assert _counts(db) == before


def test_a_handgriff_has_exactly_the_rights_of_its_person(people):
    """(c) Was die Mitarbeiterin per Klick nicht darf, darf sie per Handgriff nicht."""
    _db, staff, boss = people
    path = f"/api/v1/erp/records/{staff.object_id}"         # Angaben einer Person: nur Admin
    change = {"phone": "+41 52 000 00 00"}
    assert handgriff.call(staff.id, "PATCH", path, change, probe=True).status == 403
    assert handgriff.call(boss.id, "PATCH", path, change, probe=True).ok


def test_only_actions_of_the_erp_are_handgriffe(people):
    """(d) Lesen, öffentliche Türen und der Assistent selbst sind keine Handgriffe."""
    _db, staff, _boss = people
    keys = {o.key for o in handgriff.operations()}
    assert "POST /api/v1/erp/messages" in keys
    assert not any(k.startswith("GET ") for k in keys)
    assert "POST /api/v1/contact" not in keys
    assert not any("/assistant" in k for k in keys)
    out = handgriff.call(staff.id, "GET", "/api/v1/erp/records", None, probe=True)
    assert out.status == 400


def test_whatever_goes_outside_needs_the_hand_in_a_probe():
    """(b) Gegenprobe der Tür: im Probelauf weist ``outside.now`` ab, sonst nicht."""
    outside.now("die KI")
    with outside.probe(), pytest.raises(outside.NeedsHand):
        outside.now("die KI")
    from app.services import ai
    with outside.probe(), pytest.raises(outside.NeedsHand):
        ai._client()


def test_every_route_says_in_a_sentence_what_it_does():
    """Aus diesen Sätzen kennt die KI die Handlungen – eine Route ohne Satz ist für sie
    stumm (§6.4)."""
    from fastapi.routing import APIRoute, iter_route_contexts

    from app.main import app
    silent = [c.path for c in iter_route_contexts(app.routes)
              if isinstance(c.route, APIRoute) and not (c.route.endpoint.__doc__ or "").strip()]
    assert silent == []


def test_no_route_saves_in_the_middle():
    """§6.1: gespeichert wird am Ende der Anfrage (``get_db``), nie in einer Route."""
    import pathlib
    import re
    routers = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
    found = [f"{p.name}:{i}" for p in sorted(routers.glob("*.py"))
             for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
             if re.search(r"\.commit\(\)", line)]
    assert found == []


def test_a_request_that_fails_after_writing_leaves_nothing(people):
    """§6.1: eine Route, die schreibt und danach scheitert, hinterlässt nichts – ganz oder gar
    nicht."""
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.core.actor import act
    from app.core.database import DB
    from app.services import log
    db, staff, _boss = people
    app = FastAPI()

    @app.post("/x")
    def write_then_fail(s=DB):
        """Schreibt ein Ereignis und scheitert dann."""
        act(s, "person", staff.object_id, "ui")
        log.event(s, "test.half", staff.object_id, {})
        s.flush()
        raise HTTPException(409, detail="halb")
    before = _counts(db)
    assert TestClient(app).post("/x").status_code == 409
    assert _counts(db) == before
