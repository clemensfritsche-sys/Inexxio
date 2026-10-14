"""►►► **Kommunikation – drei Regeln, eine Logik** (CRM Schritt 2). ◄◄◄

Gefahren über den echten Dienst (``services/communication``) gegen echtes PostgreSQL.
Jede Prüfung nennt die Regel, die sie hält; keine prüft eine Art («Anruf», «Notiz») –
eine Art gibt es nicht, nur Angaben.
"""

import pathlib
import random
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models import UserProfile
from app.schemas.communication import MessageIn
from app.services import communication as svc
from tests.runner import BACKEND, session


def _person(db, role="user", company=None) -> int:
    oid = random.randint(900_000_000, 999_999_999)
    db.add(UserProfile(firebase_uid=f"uid-{oid}", email=f"p{oid}@x.ch", role=role,
                       object_id=oid, first_name="P", last_name=str(oid),
                       company_object_id=company))
    db.flush()
    return oid


def _send(db, actor, **kw):
    return svc.create(db, MessageIn(**kw), actor)


def _one(db, msg_id):
    return svc.load(db, [msg_id])[0]


@pytest.fixture()
def world():
    db = session()
    staff = _person(db, "employee")
    actor = db.query(UserProfile).filter(UserProfile.object_id == staff).one()
    yield db, actor, staff
    db.rollback()
    db.close()


def test_a_message_from_outside_is_open_until_someone_answers(world):
    """Regel 3: von aussen = an uns; offen, bis eine Nachricht sie in «Antwort auf» nennt –
    egal von welchem Mitarbeiter und auf welchem Kanal (Mail per Anruf beantwortet)."""
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="c999999990", sender=lea, body="Wann kommt der Techniker?")
    assert _one(db, m.id).open
    other = _person(db, "employee")
    _send(db, actor, channel="phone", sender=other, to=[lea], body="Donnerstag.",
          reply_to=[m.id])
    assert not _one(db, m.id).open


def test_overdue_after_two_hours(world):
    db, actor, _ = world
    lea = _person(db)
    old = _send(db, actor, channel="c999999990", sender=lea, body="x",
                at=datetime.now(timezone.utc) - timedelta(hours=3))
    new = _send(db, actor, channel="c999999990", sender=lea, body="y")
    assert _one(db, old.id).overdue and not _one(db, new.id).overdue


def test_what_we_write_outward_is_never_open(world):
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="c999999990", sender=staff, to=[lea], body="Offerte.")
    out = _one(db, m.id)
    assert out.ours and not out.open


def test_a_call_answers_itself(world):
    """Ein Gespräch wartet auf niemanden – auch wenn sie angerufen hat."""
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="phone", sender=lea, to=[staff], body="Termin ok.")
    assert not _one(db, m.id).open


def test_internal_note_question_and_reminder_are_one_thing(world):
    """Intern: ohne «An» eine Notiz (nie offen), mit Kollegin eine Frage (offen),
    an mich in der Zukunft eine Erinnerung (geplant, dann offen)."""
    db, actor, staff = world
    lea, sara = _person(db), _person(db, "employee")
    note = _send(db, actor, channel="intern", sender=staff, about=[lea], body="nur vormittags")
    ask = _send(db, actor, channel="intern", sender=staff, to=[sara], about=[lea], body="Lager?")
    later = _send(db, actor, channel="intern", sender=staff, to=[staff], about=[lea],
                  body="zurückrufen", at=datetime.now(timezone.utc) + timedelta(days=1))
    due = _send(db, actor, channel="intern", sender=staff, to=[staff], body="jetzt",
                at=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert not _one(db, note.id).open
    assert _one(db, ask.id).open
    assert _one(db, later.id).planned and not _one(db, later.id).open
    assert _one(db, due.id).open


def test_done_without_answer_is_a_silent_reply(world):
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="c999999990", sender=lea, body="Danke!")
    with pytest.raises(HTTPException):
        _send(db, actor, channel="intern", sender=staff, body="")
    _send(db, actor, channel="intern", sender=staff, body="", reply_to=[m.id])
    assert not _one(db, m.id).open


def test_history_is_every_message_a_person_takes_part_in(world):
    """Regel 2: Absender, An, Cc, Bcc und Betrifft – und die Firma ist ihre Personen."""
    db, actor, staff = world
    firm = random.randint(900_000_000, 999_999_999)
    lea, marco = _person(db, company=firm), _person(db, company=firm)
    a = _send(db, actor, channel="c999999990", sender=lea, body="a")
    b = _send(db, actor, channel="c999999990", sender=staff, to=[marco], cc=[lea], body="b")
    c = _send(db, actor, channel="c999999990", sender=staff, bcc=[lea], body="c")
    d = _send(db, actor, channel="intern", sender=staff, about=[lea], body="d")
    e = _send(db, actor, channel="intern", sender=staff, body="e")
    lea_ids = [m.id for m in svc.history(db, person=lea)]
    assert lea_ids == [a.id, b.id, c.id, d.id]
    firm_ids = {m.id for m in svc.history(db, company=firm)}
    assert firm_ids == {a.id, b.id, c.id, d.id} and e.id not in firm_ids


def test_the_feed_mark_counts_the_open_messages_of_the_history(world):
    db, actor, _ = world
    lea = _person(db)
    _send(db, actor, channel="c999999990", sender=lea, body="x",
          at=datetime.now(timezone.utc) - timedelta(hours=3))
    _send(db, actor, channel="c999999990", sender=lea, body="y")
    row = next(c for c in svc.open_counts(db) if c.object_id == lea)
    assert (row.open, row.overdue) == (2, 1)


def test_unknown_channel_and_person_are_refused(world):
    db, actor, staff = world
    with pytest.raises(HTTPException):
        _send(db, actor, channel="fax", sender=staff, body="x")
    with pytest.raises(HTTPException):
        _send(db, actor, channel="c999999990", sender=1, body="x")


def test_there_is_no_kind_switch():
    """Keine Fallunterscheidung nach einer Art: die Unterschiede stehen im Kanal-Katalog
    (``outside``/``live``) und in den Angaben."""
    for path in ("app/services/communication.py", "app/domain/communication.py"):
        src = (BACKEND / path).read_text()
        assert "kind ==" not in src and "kind==" not in src, path
