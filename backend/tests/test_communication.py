"""►►► **Kommunikation – drei Regeln, eine Logik** (CRM Schritt 2). ◄◄◄

Gefahren über den echten Dienst (``services/communication``) gegen echtes PostgreSQL.
Jede Prüfung nennt die Regel, die sie hält; keine prüft eine Art («Anruf», «Notiz») –
eine Art gibt es nicht, nur Angaben.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models import UserProfile
from app.schemas.communication import MessageIn
from app.services import communication as svc
from tests.runner import BACKEND


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
def world(db):
    staff = _person(db, "employee")
    actor = db.query(UserProfile).filter(UserProfile.object_id == staff).one()
    yield db, actor, staff


def test_a_message_from_outside_is_open_until_someone_answers(world):
    """Regel 3: von aussen = an uns; offen, bis eine spätere Nachricht von uns mit
    demselben Betreff sie erreicht – egal von welchem Mitarbeiter und auf welchem Kanal
    (Mail per Anruf beantwortet)."""
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="c999999990", sender=lea, body="Wann kommt der Techniker?")
    assert _one(db, m.id).open
    other = _person(db, "employee")
    _send(db, actor, channel="phone", sender=other, to=[lea], body="Donnerstag.",
          subject="Re: Betreff")
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
                subject="Fällig",
                at=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert not _one(db, note.id).open
    assert _one(db, ask.id).open
    assert _one(db, later.id).planned and not _one(db, later.id).open
    assert _one(db, due.id).open


def test_done_without_answer_is_a_silent_note_with_the_subject(world):
    """«Erledigt ohne Antwort» ist eine stille interne Nachricht mit dem Betreff, die den
    Absender betrifft – ohne Text und ohne Betreff sagt eine Nachricht nichts (400)."""
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="c999999990", sender=lea, subject="Danke", body="Danke!")
    with pytest.raises(HTTPException):
        _send(db, actor, channel="intern", sender=staff, subject=None, body="")
    _send(db, actor, channel="intern", sender=staff, subject="Danke", about=[lea], body="")
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
    """Ein mitgesendeter Absender wird verworfen – der Absender ist, wer angemeldet ist."""
    db, actor, staff = world
    lea = _person(db)
    m = svc.create(db, MessageIn(channel="intern", sender=lea, subject="X", body="x"), actor)
    assert m.sender_object_id == staff


def test_there_are_no_personal_mailboxes(world):
    """►►► **Im Kommunikationstool ist jeder Benutzer gleich** – auch ein Mitarbeiter kann
    Kunde sein. Ein Postfach gibt es nur je eigener Gesellschaft, verbinden darf es ein
    Admin; ein persönliches (``u<Nummer>``) ist kein Kanal mehr, und ohne Gesellschaft
    gibt es nichts zu verbinden. ◄◄◄"""
    from app.domain import communication as dc
    from app.services import mailbox
    db, actor, staff = world
    lea, sara = _person(db), _person(db, "employee")
    assert not hasattr(dc, "personal") and not hasattr(dc, "owner_of")
    with pytest.raises(ValueError):
        dc.channel(f"u{sara}")
    with pytest.raises(HTTPException) as e:
        _send(db, actor, channel=f"u{staff}", to=[lea], body="x")
    assert e.value.status_code == 400
    admin = db.query(UserProfile).filter(UserProfile.object_id == _person(db, "admin")).one()
    assert mailbox.may_connect(admin, "c100000001")
    assert not mailbox.may_connect(actor, "c100000001")
    assert not mailbox.may_connect(admin, f"u{admin.object_id}")
    assert mailbox.status(db, admin) == [] and mailbox.status(db, actor) == []
    assert not any(c.key.startswith("u") for c in svc.channels(db))


def test_an_answer_closes_every_open_message_of_its_subject(world):
    """►►► **Das Anliegen ist der Betreff.** ◄◄◄ Eine Antwort erledigt alle offenen
    Nachrichten mit demselben Betreff (ohne «Re:»/«AW:», ohne Gross/Klein) – ein anderer
    Betreff bleibt offen, und eine Nachfrage NACH der Antwort wartet wieder."""
    db, actor, staff = world
    lea = _person(db)
    first = _send(db, actor, channel="c999999990", sender=lea, subject="Seilwinde", body="1")
    second = _send(db, actor, channel="c999999990", sender=lea, subject="RE: seilwinde",
                   body="2")
    other = _send(db, actor, channel="c999999990", sender=lea, subject="Offerte", body="3")
    _send(db, actor, channel="c999999990", to=[lea], subject="Re: Seilwinde", body="Ok")
    assert not _one(db, first.id).open and not _one(db, second.id).open
    assert _one(db, other.id).open
    again = _send(db, actor, channel="c999999990", sender=lea, subject="AW: Seilwinde",
                  body="Und?")
    assert _one(db, again.id).open


def test_an_answer_must_reach_the_sender_and_the_asker_does_not_answer_himself(world):
    """Erledigt ist, was der Absender bekommt: eine Mail an jemand anderen erledigt Leas
    Frage nicht. Die Frage an eine Kollegin wartet auf SIE – schreibe ich selbst noch
    einmal, bleibt sie offen; die Erinnerung an mich erledige ich selbst."""
    db, actor, staff = world
    lea, marco, sara = _person(db), _person(db), _person(db, "employee")
    ask = _send(db, actor, channel="c999999990", sender=lea, subject="Frage", body="?")
    _send(db, actor, channel="c999999990", to=[marco], subject="Frage", body="x")
    assert _one(db, ask.id).open
    _send(db, actor, channel="c999999990", to=[marco], cc=[lea], subject="Re: Frage", body="y")
    assert not _one(db, ask.id).open
    q = _send(db, actor, channel="intern", to=[sara], subject="Lager", body="Wie viel?")
    _send(db, actor, channel="intern", to=[sara], subject="Lager", body="Nachtrag")
    assert _one(db, q.id).open
    _send(db, actor, channel="intern", sender=sara, to=[staff], subject="Re: Lager", body="3")
    assert not _one(db, q.id).open
    me = _send(db, actor, channel="intern", to=[staff], subject="Rückruf", body="anrufen")
    _send(db, actor, channel="intern", subject="Rückruf", body="")
    assert not _one(db, me.id).open


def test_a_planned_answer_answers_nothing_yet(world):
    db, actor, staff = world
    lea = _person(db)
    m = _send(db, actor, channel="c999999990", sender=lea, body="?")
    _send(db, actor, channel="c999999990", to=[lea], body="Später",
          at=datetime.now(timezone.utc) + timedelta(hours=1))
    assert _one(db, m.id).open


def test_reply_all_and_the_fixed_subject(world):
    """``reply_all`` belegt «Antworten» vor: Absender, An, Cc (ohne Bcc); der Betreff einer
    Antwort ist fest – «Re: » davor wie Gmail, nie ein zweites. Die Firma reist mit der
    Person (Kopf «Muster AG · Lea»), die Adresse nur für den Hover."""
    from app.models import CompanySettings
    db, actor, staff = world
    firm = random.randint(900_000_000, 999_999_999)
    db.add(CompanySettings(object_id=firm, company_name="Muster", legal_form="AG"))
    db.flush()
    lea, marco, eva = _person(db, company=firm), _person(db), _person(db)
    m = _one(db, _send(db, actor, channel="c999999990", sender=lea, to=[staff], cc=[marco],
                       bcc=[eva], subject="AW: Seilwinde", body="x").id)
    assert [p.object_id for p in m.reply_all] == [lea, staff, marco]
    assert m.topic == "Seilwinde" and m.reply_subject == "Re: Seilwinde"
    assert m.sender.company == "Muster AG" and m.sender.email == f"p{lea}@x.ch"


def test_the_subject_without_prefixes_is_the_topic():
    from app.domain import communication as dc
    assert dc.topic("Re: AW: Fwd:  Seilwinde  Kran") == dc.topic("seilwinde kran")
    assert dc.title("WG: Offerte") == "Offerte" and dc.reply_subject("Re: X") == "Re: X"
    assert dc.reply_subject(None) == ""


def test_every_message_has_a_subject(world):
    """►►► **Eine Regel für alles: jede Nachricht hat einen Betreff** – E-Mail, Anruf,
    Notiz, interne Nachricht (400 mit Satz). Er ist das Anliegen; ohne ihn liesse sich
    nicht sagen, was eine Nachricht erledigt. Die eine Ausnahme ist das «erledigt ohne
    Antwort» einer Nachricht aus dem Altbestand, die selbst keinen Betreff trägt. ◄◄◄
    Eine E-Mail braucht dazu einen Empfänger im «An»."""
    db, actor, staff = world
    lea = _person(db)
    with pytest.raises(HTTPException) as e:
        _send(db, actor, channel="c999999990", cc=[lea], body="x")
    assert "«An»" in e.value.detail
    for channel, kw in (("c999999990", {"to": [lea]}), ("phone", {"to": [lea]}),
                        ("intern", {"about": [lea]}), ("intern", {"to": [staff]})):
        with pytest.raises(HTTPException) as e:
            _send(db, actor, channel=channel, subject="  ", body="x", **kw)
        assert "Betreff" in e.value.detail, channel
    _send(db, actor, channel="intern", about=[lea], subject=None, body="")
    _send(db, actor, channel="phone", to=[lea], subject="Rückruf", body="erreicht")


def test_an_internal_message_goes_only_to_staff(world):
    """**Intern heisst intern**: an eine interne Nachricht gehen nur Mitarbeiter – ein
    Kunde im «An» bekäme sie nie, und sie wartete für immer. Wen sie betrifft, steht im
    «Betrifft»; der Satz nennt, wer falsch steht. Die Suche bietet dafür nur Mitarbeiter
    an (dieselbe Regel, früher gesagt)."""
    from app.services import people
    db, actor, staff = world
    lea, sara = _person(db), _person(db, "employee")
    for role in ("to", "cc", "bcc"):
        with pytest.raises(HTTPException) as e:
            _send(db, actor, channel="intern", body="x", **{role: [lea]})
        assert str(lea) in e.value.detail and "Betrifft" in e.value.detail, role
    _send(db, actor, channel="intern", to=[sara], about=[lea], body="Lager?")
    hits = people.search(db, str(lea)[:6], limit=50, staff=True)
    assert lea not in {u.object_id for u in hits}
    hits = people.search(db, str(sara), limit=50, staff=True)
    assert [u.object_id for u in hits] == [sara]


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
    # Rufe ich sie zum selben Betreff zurück, ist ihre Mail erledigt.
    mail = _send(db, actor, channel="c999999990", sender=lea, body="Frage")
    _send(db, actor, channel="phone", to=[lea], body="zurückgerufen")
    assert not _one(db, mail.id).open


def test_an_internal_question_is_not_the_answer_to_the_customer(world):
    """Wer von aussen schreibt, bekommt seine Antwort von aussen (Mail oder Anruf). Eine
    interne Rückfrage mit demselben Betreff, die ihn betrifft, lässt ihn weiter warten;
    «Erledigt ohne Antwort» (intern, ohne Text) erledigt ihn."""
    db, actor, staff = world
    lea, sara = _person(db), _person(db, "employee")
    m = _send(db, actor, channel="c999999990", sender=lea, subject="Kran", body="Wann?")
    _send(db, actor, channel="intern", to=[sara], about=[lea], subject="Re: Kran",
          body="Kannst du hinfahren?")
    assert _one(db, m.id).open
    _send(db, actor, channel="phone", to=[lea], subject="Re: Kran", body="Donnerstag")
    assert not _one(db, m.id).open
    n = _send(db, actor, channel="c999999990", sender=lea, subject="Danke", body="Danke!")
    _send(db, actor, channel="intern", about=[lea], subject="Re: Danke", body="")
    assert not _one(db, n.id).open


def test_the_feed_mark_counts_what_the_history_shows_without_building_it(world, monkeypatch):
    """►►► **Das Zeichen im Feed zählt dieselbe Regel wie der Verlauf – ohne ihn zu
    bauen** (Cleanup B-50). ◄◄◄ ``open_counts`` liess den ganzen Bestand durch ``load``
    laufen: jede Nachricht samt Text, gebauter Mail und Signatur-Erkennung zu einer vollen
    ``MessageOut``, nur um zwei Wahrheitswerte abzulesen – gemessen 1.9 s bei 10'000
    Nachrichten, bei jedem Feed-Aufruf. Gezählt wird jetzt über ``_state``, dieselbe eine
    Regel, die auch ``_out`` liest.

    Bug-Formen: (a) ``open_counts`` baut wieder Antworten (``_out``); (b) es liest die
    gebaute Mail (``messages.html``); (c) die Zahlen weichen vom Verlauf ab."""
    from sqlalchemy import event
    from app.core.database import engine
    db, actor, staff = world
    lea, max_, sara = _person(db), _person(db), _person(db, "employee")
    now = datetime.now(timezone.utc)
    ids = [m.id for m in (
        _send(db, actor, channel="c999999990", sender=lea, subject="Kran", body="Wann?",
              at=now - timedelta(hours=3)),                                    # überfällig
        _send(db, actor, channel="c999999990", sender=lea, subject="Lager", body="Wo?"),
        _send(db, actor, channel="c999999990", sender=max_, subject="Offerte", body="?"),
        _send(db, actor, channel="c999999990", sender=staff, to=[max_],
              subject="Re: Offerte", body="Anbei."),                          # beantwortet
        _send(db, actor, channel="intern", sender=staff, to=[sara], about=[lea],
              subject="Re: Kran", body="Kannst du hinfahren?"),               # Frage intern
        _send(db, actor, channel="intern", sender=staff, about=[max_], subject="Notiz",
              body="nur vormittags"),                                          # nie offen
        _send(db, actor, channel="intern", sender=staff, to=[staff], subject="Zurückrufen",
              body="morgen", at=now + timedelta(days=1)),                      # geplant
        _send(db, actor, channel="phone", sender=lea, to=[staff], subject="Anruf",
              body="ok"),                                                      # Gespräch
    )]
    expected: dict[int, list[int]] = {}
    for m in svc.load(db, ids):
        if m.open:
            for oid in {p.object_id for p in (m.sender, *m.to, *m.cc, *m.bcc, *m.about)}:
                row = expected.setdefault(oid, [0, 0])
                row[0] += 1
                row[1] += int(m.overdue)

    def built(*_a, **_k):
        raise AssertionError("open_counts baut wieder volle Antworten (a).")
    monkeypatch.setattr(svc, "_out", built)
    read: list[str] = []

    def watch(_c, _cur, stmt, *_a, **_k):
        read.append(stmt)
    event.listen(engine, "before_cursor_execute", watch)
    try:
        got = {c.object_id: [c.open, c.overdue] for c in svc.open_counts(db)
               if c.object_id in (lea, max_, sara, staff)}
    finally:
        event.remove(engine, "before_cursor_execute", watch)
    assert not [q for q in read if "messages.html" in q], "Die gebaute Mail wird geladen (b)."
    assert got == expected, f"Feed {got} ≠ Verlauf {expected} (c)."
    assert expected[lea] == [3, 1] and sara in expected and max_ not in expected
