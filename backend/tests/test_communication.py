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


def _send(db, actor, sender=None, **kw):
    """Geschrieben wird im eigenen Namen – eine Nachricht «von Lea» schreibt also Lea."""
    if sender is not None and sender != actor.object_id:
        actor = db.query(UserProfile).filter(UserProfile.object_id == sender).one()
    kw.setdefault("subject", "Betreff")     # eine E-Mail braucht einen (``_assert_mail``)
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
          reply_to=m.id)
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
    _send(db, actor, channel="intern", sender=staff, body="", reply_to=m.id)
    assert not _one(db, m.id).open


def test_history_is_every_message_a_person_takes_part_in(world):
    """Regel 2: Absender, An, Cc, Bcc und Betrifft – und die Firma ist ihre Personen."""
    db, actor, staff = world
    firm = random.randint(900_000_000, 999_999_999)
    lea, marco = _person(db, company=firm), _person(db, company=firm)
    a = _send(db, actor, channel="c999999990", sender=lea, body="a")
    b = _send(db, actor, channel="c999999990", sender=staff, to=[marco], cc=[lea], body="b")
    c = _send(db, actor, channel="c999999990", sender=staff, to=[marco], bcc=[lea], body="c")
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
        _send(db, actor, channel="c999999990", to=[1], body="x")


def test_there_is_no_kind_switch():
    """Keine Fallunterscheidung nach einer Art: die Unterschiede stehen im Kanal-Katalog
    (``outside``/``live``) und in den Angaben."""
    for path in ("app/services/communication.py", "app/domain/communication.py"):
        src = (BACKEND / path).read_text()
        assert "kind ==" not in src and "kind==" not in src, path


def test_one_writes_only_in_ones_own_name(world):
    """Ein mitgesendeter Absender wird verworfen – der Absender ist, wer angemeldet ist.
    Über das persönliche Postfach eines anderen schreibt niemand."""
    db, actor, staff = world
    lea, sara = _person(db), _person(db, "employee")
    m = svc.create(db, MessageIn(channel="intern", sender=lea, body="x"), actor)
    assert m.sender_object_id == staff
    with pytest.raises(HTTPException) as e:
        _send(db, actor, channel=f"u{sara}", to=[lea], body="x")
    assert e.value.status_code == 403


def test_an_answer_closes_only_what_it_answers(world):
    """«Antwort auf» nennt genau eine Nachricht – die zweite offene bleibt offen, bis auch
    sie beantwortet oder als erledigt markiert ist. Zweimal antworten ist erlaubt."""
    db, actor, staff = world
    lea = _person(db)
    first = _send(db, actor, channel="c999999990", sender=lea, body="Frage 1")
    second = _send(db, actor, channel="c999999990", sender=lea, body="Frage 2")
    _send(db, actor, channel="c999999990", to=[lea], body="Zu 2", reply_to=second.id)
    assert _one(db, first.id).open and not _one(db, second.id).open
    again = _send(db, actor, channel="c999999990", to=[lea], body="Nachtrag", reply_to=second.id)
    assert _one(db, again.id).reply_to == second.id
    with pytest.raises(Exception):
        MessageIn(channel="intern", body="", reply_to=[first.id, second.id])


def test_an_answer_reaches_whom_it_answers(world):
    """Eine Antwort erreicht den Absender der beantworteten Nachricht – sonst 400 mit
    Satz. «Erledigt ohne Antwort» und die eigene Erinnerung sind an niemanden gebunden;
    die Frage einer Kollegin beantworte ich ihr."""
    db, actor, staff = world
    lea, sara = _person(db), _person(db, "employee")
    ask = _send(db, actor, channel="c999999990", sender=lea, body="Frage")
    with pytest.raises(HTTPException) as e:
        _send(db, actor, channel="intern", to=[sara], body="Kannst du?", reply_to=ask.id)
    assert e.value.status_code == 400 and str(lea) in e.value.detail
    marco = _person(db)
    _send(db, actor, channel="c999999990", to=[marco], cc=[lea], body="Antwort",
          reply_to=ask.id)
    _send(db, actor, channel="intern", body="", reply_to=ask.id)
    me = _send(db, actor, channel="intern", to=[staff], body="zurückrufen")
    _send(db, actor, channel="intern", body="erledigt", reply_to=me.id)
    q = _send(db, actor, channel="intern", sender=sara, to=[staff], body="Lager?")
    with pytest.raises(HTTPException):
        _send(db, actor, channel="intern", to=[lea], body="x", reply_to=q.id)
    _send(db, actor, channel="intern", to=[sara], body="leer", reply_to=q.id)
    assert not _one(db, q.id).open


def test_a_message_names_whom_an_answer_must_reach(world):
    """``answer_to`` sagt der Oberfläche, wen «An» vorbelegt und sperrt; die Firma reist
    mit der Person (Kopf «Muster AG · Lea»), die Adresse nur für den Hover."""
    from app.models import CompanySettings
    db, actor, staff = world
    firm = random.randint(900_000_000, 999_999_999)
    db.add(CompanySettings(object_id=firm, company_name="Muster", legal_form="AG"))
    db.flush()
    lea = _person(db, company=firm)
    m = _one(db, _send(db, actor, channel="c999999990", sender=lea, body="x").id)
    assert [p.object_id for p in m.answer_to] == [lea]
    assert m.sender.company == "Muster AG" and m.sender.email == f"p{lea}@x.ch"
    mine = _one(db, _send(db, actor, channel="c999999990", to=[lea], body="y").id)
    assert {p.object_id for p in mine.answer_to} == {staff, lea}


def test_an_email_needs_a_recipient_and_a_subject(world):
    """Eine E-Mail von uns ohne «An» oder ohne Betreff geht nicht hinaus (400 mit Satz) –
    ohne «An» hätte sie keinen Adressaten, ohne Betreff steht beim Empfänger eine leere
    Zeile. Eine Notiz braucht beides nicht."""
    db, actor, staff = world
    lea = _person(db)
    with pytest.raises(HTTPException) as e:
        _send(db, actor, channel="c999999990", cc=[lea], body="x")
    assert "«An»" in e.value.detail
    with pytest.raises(HTTPException) as e:
        _send(db, actor, channel="c999999990", to=[lea], subject="  ", body="x")
    assert "Betreff" in e.value.detail
    _send(db, actor, channel="intern", about=[lea], subject=None, body="Notiz")


def test_an_incoming_call_has_the_caller_as_sender(world):
    """«Wurde angerufen»: der Kontakt ist der Absender, ich der Empfänger – nur bei einem
    Anruf und nur mit genau einem Anrufer. Wer es erfasst hat, steht in ``created_by``."""
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="phone", to=[lea], body="Will Offerte", incoming=True)
    out = _one(db, m.id)
    assert out.sender.object_id == lea and [p.object_id for p in out.to] == [staff]
    assert m.created_by == actor.id and not out.open
    with pytest.raises(HTTPException):
        _send(db, actor, channel="intern", to=[lea], body="x", incoming=True)
    with pytest.raises(HTTPException):
        _send(db, actor, channel="phone", to=[lea, staff], body="x", incoming=True)
    # Ruft sie zurück und «antwortet» damit auf ihre Mail, ist sie als Anruferin erreicht.
    mail = _send(db, actor, channel="c999999990", sender=lea, body="Frage")
    _send(db, actor, channel="phone", to=[lea], body="zurückgerufen", incoming=True,
          reply_to=mail.id)


def test_the_feed_mark_sits_where_the_matter_is(world):
    """Eine Notiz an mich über Unisto zählt bei Unisto, nicht bei mir; die Mail eines
    Kunden bei ihm; die interne Frage ohne «Betrifft» bei der gefragten Kollegin."""
    db, actor, staff = world
    lea, unisto, sara = _person(db), _person(db), _person(db, "employee")
    _send(db, actor, channel="intern", to=[staff], about=[unisto], body="nachfassen")
    _send(db, actor, channel="c999999990", sender=lea, body="Frage")
    _send(db, actor, channel="intern", to=[sara], body="Lager?")
    rows = {c.object_id: c.open for c in svc.open_counts(db)}
    assert rows.get(unisto) == 1 and rows.get(lea) == 1 and rows.get(sara) == 1
    assert staff not in rows
