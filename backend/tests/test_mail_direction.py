"""►►► **Die Richtung einer Nachricht ist eine Tatsache der Nachricht** – nicht der Rolle
ihres Absenders (``messages.inbound``). ◄◄◄

Dazu, was daran hängt: wer eine automatische Mail schreibt (die Gesellschaft), woran eine
Mail sich selbst wiedererkennt (ihre Kennung, vergeben bevor sie geht) und was eine Antwort
ist (nur, was auch draussen ankam). Jede Prüfung nennt ihre Bug-Form.
"""

import base64
import email
from types import SimpleNamespace

from app.domain import communication as dc
from app.models import Message, UserProfile
from app.schemas.communication import MessageIn
from app.services import communication as comm
from app.services import mailbox as mb
from tests import test_mailbox
from tests.test_mailbox import CH, COMPANY, _gmail, _one, _person

world = test_mailbox.world     # dieselbe Bühne: Postfach, Mitarbeiter, eigene Adresse


def _row(db, raw) -> Message:
    return db.query(Message).filter(Message.gmail_id == raw["id"]).one()


def test_a_colleague_writing_from_a_private_address_writes_to_us(world):
    """Bug-Form: ein Mitarbeiter schreibt von seiner privaten Adresse an das Postfach – die
    Mail stand als «von uns» da, war nie offen, und «Antworten» hatte niemanden im «An»."""
    db, staff, box = world
    raw = _gmail(f"{staff.display_name} <{staff.email}>", to=COMPANY, subject="Frage zum Kran")
    assert mb.ingest(db, box, raw)
    out = _one(db, raw["id"])
    assert out.sender.object_id == staff.object_id
    assert not out.ours and out.open, "kam von aussen – also an uns, also offen"
    assert staff.object_id in [p.object_id for p in out.reply_all]
    reply = comm.create(db, MessageIn(channel=CH, to=[staff.object_id],
                                      subject=out.reply_subject, body="Antwort"), staff)
    assert not reply.inbound
    assert comm.answered(db, [out.id]) == {out.id}, "die Antwort nach aussen erledigt sie"
    # Bug-Form: die Antwort an die private Adresse galt selbst als «offen» (ein Mitarbeiter
    # im «An» = eine Bitte an uns) – und stand in «zu tun».
    mine = comm.load(db, [reply.id])[0]
    assert mine.ours and not mine.open
    assert not any(c.object_id == staff.object_id and c.open for c in comm.open_counts(db))


def test_what_a_colleague_writes_in_the_erp_is_ours(world):
    """Die Gegenprobe: im ERP geschrieben, über das Postfach hinaus – von uns, nie offen."""
    db, staff, _box = world
    lea = _person(db)
    msg = comm.create(db, MessageIn(channel=CH, to=[lea.object_id], subject="Offerte",
                                    body="Anbei"), staff)
    out = comm.load(db, [msg.id])[0]
    assert out.ours and not out.open and not msg.inbound


def test_a_reply_that_never_went_out_answers_nothing(world):
    """Bug-Form: eine Antwort, die noch wartete oder an der Gmail aufgab, galt als Antwort –
    die Anfrage verschwand aus «offen», der Kunde bekam nie etwas."""
    db, staff, box = world
    lea = _person(db)
    raw = _gmail(f"Lea <{lea.email}>", to=COMPANY, subject="Liefertermin?")
    assert mb.ingest(db, box, raw)
    asked = _row(db, raw)
    reply = comm.create(db, MessageIn(channel=CH, to=[lea.object_id],
                                      subject="Re: Liefertermin?", body="Freitag"), staff)
    reply.outgoing = True
    db.flush()
    assert comm.answered(db, [asked.id]) == set(), "wartet noch – erreicht niemanden"
    mb._give_up(db, reply, "Gmail hat sie abgewiesen (400).")
    db.flush()
    assert not reply.outgoing
    assert comm.answered(db, [asked.id]) == set(), "aufgegeben – erreicht niemanden"


def test_every_mail_gets_its_own_id_before_it_goes(world):
    """Bug-Form: die Kennung war die Nummer der Zeile – nach einem Neuaufbau der Datenbank
    fand Gmail eine alte Mail mit derselben Nummer, und die neue galt als gesendet."""
    db, staff, box = world
    lea = _person(db)
    a, b = (comm.create(db, MessageIn(channel=CH, to=[lea.object_id], subject=s, body="x"),
                        staff) for s in ("A", "B"))
    a.outgoing = b.outgoing = True
    db.flush()
    assert a.rfc_id != b.rfc_id and dc.ours(a.rfc_id) and dc.ours(b.rfc_id)
    # Der Abgleich findet sie im Ordner «Gesendet» – und erkennt sie wieder (nie doppelt).
    seen = _gmail(f"Inexxio <{COMPANY}>", to=lea.email, labels=("SENT",), rfc=a.rfc_id)
    assert not mb.ingest(db, box, seen)


def test_a_request_to_a_bare_address_never_creates_a_person(world, monkeypatch):
    """Bug-Form: die Bitte um Bestätigung einer Newsletter-Anmeldung von der Website kam beim
    nächsten Abgleich aus «Gesendet» herein – und ihr Empfänger wurde eine Person."""
    db, _staff, box = world
    sent: dict = {}
    monkeypatch.setattr(mb, "_access", lambda _mb: "tok")
    monkeypatch.setattr(mb, "_post", lambda _t, body, _w: (sent.update(body), ({"id": "g"}, ""))[1])
    mail = SimpleNamespace(text="Bitte bestätigen", html="<p>Bitte bestätigen</p>")
    assert mb.send_direct(db, CH, "neu@kunde.ch", "Bitte bestätigen", mail)
    rfc = email.message_from_bytes(base64.urlsafe_b64decode(sent["raw"]))["Message-ID"]
    assert dc.ours(rfc)
    raw = _gmail(f"Inexxio <{COMPANY}>", to="neu@kunde.ch", labels=("SENT",), rfc=rfc)
    assert not mb.ingest(db, box, raw)
    assert db.query(UserProfile).filter(UserProfile.email == "neu@kunde.ch").count() == 0


def test_a_mail_sent_from_gmail_is_written_by_the_company(world):
    """Bug-Form: was jemand direkt in Gmail schrieb, stand im Verlauf als Mail des Admins,
    der das Postfach verband. Wer es tippte, weiss das ERP nicht – es schrieb die
    Gesellschaft."""
    db, staff, box = world
    raw = _gmail(f"Inexxio <{COMPANY}>", to="kunde@example.org", labels=("SENT",))
    assert mb.ingest(db, box, raw)
    msg = _row(db, raw)
    assert msg.sender_object_id == dc.company_of(box.channel) != staff.object_id
    assert not msg.inbound


def test_a_mail_without_a_subject_can_be_answered(world):
    """Bug-Form: eine Mail ohne Betreff liess sich nicht beantworten – der Betreff der
    Antwort war leer, der Knopf blieb bei «Betreff fehlt», und sie blieb für immer offen."""
    db, staff, box = world
    lea = _person(db)
    raw = _gmail(f"Lea <{lea.email}>", to=COMPANY, subject="")
    assert mb.ingest(db, box, raw)
    out = _one(db, raw["id"])
    assert out.subject == dc.NO_SUBJECT and out.reply_subject == f"Re: {dc.NO_SUBJECT}"
    comm.create(db, MessageIn(channel=CH, to=[lea.object_id], subject=out.reply_subject,
                              body="Gerne"), staff)
    assert comm.answered(db, [out.id]) == {out.id}
