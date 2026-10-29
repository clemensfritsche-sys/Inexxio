"""►►► **Postfach – Gmail ist der Speicher, das ERP der Verlauf** (CRM Schritt 3). ◄◄◄

Gefahren über den echten Dienst (``services/mailbox``) gegen echtes PostgreSQL – ohne
Netz: ``ingest`` bekommt, was Gmail liefern würde, und ``send`` wird dort ersetzt, wo es
Google anriefe. Jede Prüfung nennt die Regel, die sie hält.
"""

import base64
import random

import pytest
from fastapi import HTTPException

from app.models import Mailbox, Message, UserProfile
from app.services import people
from app.schemas.communication import MessageIn
from app.services import communication as comm
from app.services import mailbox as mb
from app.services import objects
from tests.runner import session
from tests.factories import new_person

COMPANY = "info.test@example.com"
#: Das Postfach einer (gedachten) eigenen Gesellschaft – die Form ``c<Objektnummer>``.
CH = "c999999990"


def _person(db, role="user", email=None):
    return new_person(db, role, email=email)


def _gmail(frm, to="", cc="", subject="Hallo", body="Text", labels=("INBOX",), **head):
    gid = f"g{random.randint(1, 10**12)}"
    headers = [{"name": "From", "value": frm}, {"name": "To", "value": to},
               {"name": "Cc", "value": cc}, {"name": "Subject", "value": subject},
               {"name": "Message-ID", "value": head.pop("rfc", f"<{gid}@mail>")}]
    headers += [{"name": k.replace("_", "-"), "value": v} for k, v in head.items()]
    data = base64.urlsafe_b64encode(body.encode()).decode()
    return {"id": gid, "threadId": gid, "labelIds": list(labels), "internalDate": "1760000000000",
            "payload": {"mimeType": "text/plain", "headers": headers, "body": {"data": data}}}


@pytest.fixture()
def world(db, monkeypatch):
    monkeypatch.setattr(mb, "company_address", lambda _db, _key: COMPANY)
    monkeypatch.setattr(mb, "_company_addresses", lambda _db: {COMPANY})
    staff = _person(db, "employee")
    box = Mailbox(channel=CH, address=COMPANY, owner_object_id=staff.object_id, token="x")
    db.add(box)
    db.flush()
    yield db, staff, box


def _one(db, gid):
    m = db.query(Message).filter(Message.gmail_id == gid).one()
    return comm.load(db, [m.id])[0]


def test_an_unknown_sender_becomes_a_contact_and_the_mail_is_open(world):
    """Absender unbekannt → Person angelegt (ohne Anmeldekonto); die eigene Adresse ist
    der Kanal, keine Beteiligte; von aussen = an uns = offen."""
    db, staff, box = world
    raw = _gmail('"Lea Muster" <Lea@Kunde.CH>', to=COMPANY)
    assert mb.ingest(db, box, raw)
    lea = db.query(UserProfile).filter(UserProfile.email == "lea@kunde.ch").one()
    assert (lea.first_name, lea.last_name, lea.role) == ("Lea", "Muster", "user")
    assert lea.firebase_uid == "mail:lea@kunde.ch" and lea.object_id
    out = _one(db, raw["id"])
    assert out.sender.object_id == lea.object_id and out.to == [] and out.open


def test_what_we_send_from_gmail_is_ours_and_captures_the_recipient(world):
    db, staff, box = world
    raw = _gmail(f"Inexxio <{COMPANY}>", to="Neu Kunde <neu@kunde.ch>", labels=("SENT",))
    assert mb.ingest(db, box, raw)
    out = _one(db, raw["id"])
    assert out.sender.object_id == staff.object_id and out.ours and not out.open
    assert [p.name for p in out.to] == ["Neu Kunde"]


def test_a_user_with_our_address_is_never_the_sender_and_never_created(world):
    """Die Frage des Nutzers: trägt ein Benutzer dieselbe Adresse wie das Unternehmen,
    zählt sie trotzdem als «wir» – der Absender ist der Mitarbeiter hinter dem Postfach."""
    db, staff, box = world
    twin = _person(db, "user", email=COMPANY)
    raw = _gmail(COMPANY, to="a@b.ch", labels=("SENT",))
    mb.ingest(db, box, raw)
    assert _one(db, raw["id"]).sender.object_id == staff.object_id != twin.object_id
    assert "bereits" in mb._store(db, "u1", staff, COMPANY, "t", "1")


def test_a_reply_in_gmail_answers_the_message_of_its_subject(world):
    """Wer direkt in Gmail antwortet, erledigt die Nachricht im ERP – über den Betreff."""
    db, staff, box = world
    first = _gmail("x@kunde.ch", to=COMPANY, subject="Seilwinde", rfc="<a1@kunde>")
    mb.ingest(db, box, first)
    assert _one(db, first["id"]).open
    answer = _gmail(COMPANY, to="x@kunde.ch", subject="Re: Seilwinde", labels=("SENT",),
                    rfc="<b2@inexxio>")
    mb.ingest(db, box, answer)
    assert not _one(db, first["id"]).open


def test_the_same_mail_in_two_mailboxes_is_one_message(world):
    db, staff, box = world
    raw = _gmail("y@kunde.ch", to=COMPANY, rfc="<same@kunde>")
    assert mb.ingest(db, box, raw)
    again = dict(raw, id="other")
    assert not mb.ingest(db, box, again)


def test_bulk_mail_creates_no_contact(world):
    db, _, box = world
    for raw in (_gmail("news@shop.ch", list_unsubscribe="<mailto:u@shop.ch>"),
                _gmail("noreply@bank.ch"),
                _gmail("promo@shop.ch", labels=("INBOX", "CATEGORY_PROMOTIONS"))):
        assert not mb.ingest(db, box, raw)
    assert db.query(UserProfile).filter(UserProfile.email.like("%shop.ch")).count() == 0


def test_the_quoted_history_is_cut():
    text = ("Gerne, Donnerstag passt.\n\nAm Mo., 13. Okt. 2026 um 10:00 Uhr schrieb Lea "
            "<lea@kunde.ch>:\n> Wann kommt der Techniker?\n")
    assert mb._strip_quote(text) == "Gerne, Donnerstag passt."


def test_a_forged_state_connects_nothing(db):
    """Der ``state`` der Rückkehr von Google ist signiert (``core/signed``) – gefälscht oder
    für einen anderen Zweck ausgestellt, verbindet er nichts."""
    from app.core import signed
    state = signed.sign({"c": CH, "a": 1}, mb.STATE_PURPOSE, 600)
    forged = state[:-1] + ("0" if state[-1] != "0" else "1")
    assert "ungültig" in mb.callback(db, "code", forged)
    other = signed.sign({"c": CH, "a": 1}, "unsubscribe")
    assert "ungültig" in mb.callback(db, "code", other)


def test_an_outward_mail_goes_out_through_its_mailbox(world, monkeypatch):
    """Mit Anbindung: ohne verbundenes Postfach keine Mail nach aussen (400); mit ihm
    wird sie gesendet – und bis dahin steht sie als «muss hinaus» da."""
    db, staff, box = world
    lea = _person(db)
    sent = []
    monkeypatch.setattr(mb, "ready", lambda: True)
    monkeypatch.setattr(mb, "send", lambda _db, m: sent.append(m.id) or False)
    m = comm.create(db, MessageIn(channel=CH, sender=staff.object_id, to=[lea.object_id],
                                  subject="Offerte", body="Offerte"), staff)
    assert sent == [m.id] and comm.load(db, [m.id])[0].pending
    box.is_active = False
    db.flush()
    with pytest.raises(HTTPException):
        comm.create(db, MessageIn(channel=CH, sender=staff.object_id,
                                  to=[lea.object_id], subject="x", body="x"), staff)
    with pytest.raises(HTTPException):          # ein persönliches nur mit seinem Besitzer
        comm.create(db, MessageIn(channel=f"u{lea.object_id}", sender=staff.object_id,
                                  to=[lea.object_id], subject="x", body="x"), staff)


def test_every_own_company_has_its_own_mailbox():
    """Ein Postfach je eigener Gesellschaft (``c<Objektnummer>``) – seine Adresse ist ihre
    Kontakt-E-Mail; einen Kanal ``info`` gibt es nicht."""
    from app.domain import communication as dc
    assert dc.channel(dc.company(100000001)).kind == "email"
    assert dc.is_mail("c100000001") and dc.company_of("c100000001") == 100000001
    assert not dc.is_mail("phone") and not dc.is_mail("u100000001")
    with pytest.raises(ValueError):
        dc.channel("info")


def test_one_answer_in_gmail_closes_every_mail_of_its_subject(world):
    """Zwei Mails desselben Kunden zum selben Betreff – eine Antwort erledigt beide; eine
    Mail mit anderem Betreff bleibt offen."""
    db, staff, box = world
    first = _gmail("z@kunde.ch", to=COMPANY, subject="Kran 3", rfc="<f1@kunde>")
    second = _gmail("z@kunde.ch", to=COMPANY, subject="AW: Kran 3", rfc="<f2@kunde>")
    other = _gmail("z@kunde.ch", to=COMPANY, subject="Offerte", rfc="<f9@kunde>")
    for raw in (first, second, other):
        mb.ingest(db, box, raw)
    mb.ingest(db, box, _gmail(COMPANY, to="z@kunde.ch", subject="Re: Kran 3",
                              labels=("SENT",), rfc="<f3@inexxio>"))
    assert not _one(db, first["id"]).open and not _one(db, second["id"]).open
    assert _one(db, other["id"]).open


def test_a_reply_goes_out_in_the_thread_of_its_subject(world):
    """Der Faden einer ausgehenden Mail ist die jüngste frühere Mail mit demselben
    Anliegen und einem der Empfänger – wie Gmail über den Betreff."""
    db, staff, box = world
    first = _gmail("t@kunde.ch", to=COMPANY, subject="Kran 3", rfc="<t1@kunde>")
    mb.ingest(db, box, first)
    lea = db.query(UserProfile).filter(UserProfile.email == "t@kunde.ch").one()
    msg = comm.create(db, MessageIn(channel=CH, to=[lea.object_id], subject="Re: Kran 3",
                                    body="Ok"), staff)
    parent = mb._parent(db, msg)
    assert parent is not None and parent.rfc_id == "<t1@kunde>"
    mime = mb._mime(db, box, msg, parent)
    assert mime["Subject"] == "Re: Kran 3" and mime["In-Reply-To"] == "<t1@kunde>"


def test_last_comma_first_is_turned_around():
    """«Fritsche, Clemens» ist «Nachname, Vorname» – gedreht, ohne Komma."""
    assert people.split_name('"Fritsche, Clemens"') == ("Clemens", "Fritsche")
    assert people.split_name("Lea  Maria Muster") == ("Lea", "Maria Muster")
    assert people.split_name("  ") is None


def test_the_signature_folds_and_greeting_and_name_stay():
    from app.domain.communication import split_signature
    text = ("Hallo\n\n\n\nDanke für die Offerte.\n\nFreundliche Grüsse\n\nClemens Fritsche"
            "\n\n\nInexxio AG\n\nStrasse 1\n\nwww.inexxio.com <http://www.inexxio.com>")
    body, sig = split_signature(text, "Clemens Fritsche")
    assert body == "Hallo\n\nDanke für die Offerte.\n\nFreundliche Grüsse\n\nClemens Fritsche"
    assert sig == "Inexxio AG\nStrasse 1\nwww.inexxio.com <http://www.inexxio.com>"
    assert split_signature("Kurz.\n--\nCF\nTel 1") == ("Kurz.", "CF\nTel 1")
    # Nichts erkannt → der Text bleibt, wie er ist; lieber zu viel zeigen als verschlucken.
    assert split_signature("Danke.\nBeste Grüsse\nMax") == ("Danke.\nBeste Grüsse\nMax", None)


def test_the_contact_email_of_an_own_company_is_its_mailbox(monkeypatch):
    """Gesetzt allein durch Verbinden, geleert allein durch Trennen – und die normale
    Pflege schreibt sie nicht (ein zweiter Weg wäre die Adresse, die nie hinausgeht)."""
    from app.models import CompanySettings
    from app.services import sites
    db = session()
    monkeypatch.setattr(db, "commit", db.flush)
    monkeypatch.setattr(mb, "_open", lambda _t: None)
    try:
        oid = objects.next_object_id(db, "organization")
        firm = CompanySettings(company_name=f"T{oid}", legal_form="AG", is_own=True,
                               email="alt@firma.ch", country="CH", object_id=oid)
        db.add(firm)
        admin = _person(db, "admin")
        db.flush()
        key = f"c{oid}"
        assert mb._store(db, key, admin, f"neu{oid}@firma.ch", "t", "1") == ""
        assert firm.email == f"neu{oid}@firma.ch"
        sites._apply_entity_fields(firm, {"email": "x@y.ch"}, db, None)
        assert firm.email == f"neu{oid}@firma.ch"
        mb.disconnect(db, key, admin)
        assert firm.email == "" and mb.active(db, key) is None
    finally:
        db.rollback()
        db.close()


def test_a_sent_mail_stays_sent_when_the_follow_up_read_fails(world, monkeypatch):
    """Ist die Mail bei Gmail draussen, darf nichts danach den Versand ungeschehen machen:
    scheitert der Abruf der ``Message-ID``, bleibt sie trotzdem «gesendet» – sonst schickte
    der nächste Abgleich sie ein zweites Mal."""
    import httpx
    db, staff, box = world
    lea = _person(db)
    msg = comm.create(db, MessageIn(channel=CH, to=[lea.object_id], subject="Offerte",
                                    body="Offerte"), staff)
    msg.outgoing = True

    class Sent:
        status_code, text = 200, ""
        def json(self):
            return {"id": "g-sent", "threadId": "t-sent"}

    def down(*_a, **_k):
        raise httpx.ConnectError("weg")
    monkeypatch.setattr(mb, "_access", lambda _mb: "tok")
    monkeypatch.setattr(mb.httpx, "post", lambda *_a, **_k: Sent())
    monkeypatch.setattr(mb, "_get", down)
    assert mb.send(db, msg)
    assert (msg.outgoing, msg.gmail_id, msg.rfc_id) == (False, "g-sent", None)


def test_two_syncs_never_send_the_same_mail_twice(monkeypatch):
    """Zwei offene ERP-Tabs gleichen gleichzeitig ab. Eine Mail, die der eine gerade
    sendet (gesperrt), überspringt der andere – und jede gesendete Mail steht sofort fest,
    auch wenn eine andere im selben Lauf scheitert."""
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.models import MessageParty
    a, b = session(), session()
    staff = _person(a, "employee")
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    mails = [Message(sender_object_id=staff.object_id, channel=CH, subject=f"Test {i}",
                     body="x", at=old, outgoing=True) for i in range(2)]
    box = Mailbox(channel=CH, address=f"two{staff.object_id}@x.ch",
                  owner_object_id=staff.object_id, token="x")
    a.add_all([*mails, box])
    a.commit()
    ids = [m.id for m in mails]
    sent: list[int] = []
    broken = [ids[0]]                    # scheitert genau beim ersten Versuch

    def fake(_db, m, _tokens=None):
        if m.id in broken:
            broken.remove(m.id)
            raise RuntimeError("kaputt")
        sent.append(m.id)
        m.outgoing = False
        return True
    monkeypatch.setattr(mb, "send", fake)
    try:
        a.execute(text("SET lock_timeout = '2s'"))     # ohne SKIP LOCKED: Fehler statt Hängen
        b.query(Message).filter(Message.id == ids[1]).with_for_update().one()
        mb.send_due(a)                                   # ids[0] scheitert, ids[1] gesperrt
        assert sent == []
        b.rollback()
        mb.send_due(a)
        assert sent == [ids[0], ids[1]] or sent == [ids[1], ids[0]]
        mb.send_due(a)                                   # beide stehen fest: nichts doppelt
        assert sorted(sent) == sorted(ids)
        assert not any(o for (o,) in b.query(Message.outgoing).filter(Message.id.in_(ids)))
    finally:
        b.rollback()
        a.rollback()
        a.query(MessageParty).filter(MessageParty.message_id.in_(ids)).delete()
        a.query(Message).filter(Message.id.in_(ids)).delete()
        a.query(Mailbox).filter(Mailbox.id == box.id).delete()
        a.query(UserProfile).filter(UserProfile.id == staff.id).delete()
        a.commit()
        a.close()
        b.close()


def test_marking_read_asks_once_not_once_per_mail(world, monkeypatch):
    """►►► **«Gelesen in Gmail» fragt EINMAL, was beantwortet ist** (Cleanup B-50). ◄◄◄
    Die Ableitung stand als Bedingung in der Auswahl (``if m.id in answered(…)``) und lief
    damit für **jede** Mail erneut über alle – quadratisch, alle 30 Sekunden je Postfach.

    Bug-Form: ``answered`` wird je Mail gefragt."""
    from datetime import datetime, timezone
    db, _staff, box = world
    raws = [_gmail("q@kunde.ch", to=COMPANY, subject=f"Frage {i}", rfc=f"<q{i}@kunde>")
            for i in range(4)]
    for raw in raws:
        mb.ingest(db, box, raw)
    db.query(Message).filter(Message.gmail_id.in_([r["id"] for r in raws])).update(
        {Message.at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.flush()
    calls = {"n": 0}
    real = comm.answered

    def counted(*a, **k):
        calls["n"] += 1
        return real(*a, **k)
    monkeypatch.setattr(comm, "answered", counted)
    monkeypatch.setattr(mb, "_access", lambda _box: None)
    mb._mark_read(db, box)
    assert calls["n"] == 1, f"answered wurde {calls['n']}-mal gefragt, für vier Mails."


# ------------------------------------------------------------------ Abgleich robust

class _Resp:
    def __init__(self, data, status=200):
        self.status_code, self._data, self.text = status, data, ""

    def json(self):
        return self._data


def test_a_broken_mail_does_not_hold_up_the_sync(world, monkeypatch):
    """Eine Mail, die sich nicht verarbeiten lässt, steht im Log und wird übersprungen; die
    übrigen kommen an, und der Stand rückt vor. Bug-Form: eine Ausnahme in einer Mail rollte
    das ganze Postfach zurück – jeder Lauf scheiterte an derselben Mail, für immer."""
    db, _staff, box = world
    raws = [_gmail(f"k{i}@kunde.ch", to=COMPANY, subject=f"Frage {i}") for i in range(3)]
    by_id = {r["id"]: r for r in raws}
    monkeypatch.setattr(mb, "_token", lambda _mb, _t=None: "tok")
    monkeypatch.setattr(mb, "_new_ids", lambda _t, _s: (list(by_id), "h-neu"))
    monkeypatch.setattr(mb, "_get", lambda _t, path, **_k: _Resp(by_id[path.split("/")[1]]))
    real = mb.ingest

    def flaky(db_, mb_, raw, ours=None):
        if raw["id"] == raws[1]["id"]:
            raise ValueError("kaputte Mail")
        return real(db_, mb_, raw, ours)
    monkeypatch.setattr(mb, "ingest", flaky)
    assert mb._sync_one(db, box, mb._ours(db)) == 2
    assert box.history_id == "h-neu"
    got = {g for (g,) in db.query(Message.gmail_id).filter(Message.gmail_id.in_(list(by_id)))}
    assert got == {raws[0]["id"], raws[2]["id"]}


def test_a_failed_fetch_keeps_the_position(world, monkeypatch):
    """Scheitert das Holen (Gmail antwortet nicht), bleibt der Stand stehen – der nächste Lauf
    holt die Mail nach, statt sie zu verlieren."""
    db, _staff, box = world
    box.history_id = "h-alt"
    monkeypatch.setattr(mb, "_token", lambda _mb, _t=None: "tok")
    monkeypatch.setattr(mb, "_new_ids", lambda _t, _s: (["g-x"], "h-neu"))
    monkeypatch.setattr(mb, "_get", lambda *_a, **_k: _Resp({}, 503))
    assert mb._sync_one(db, box, {}) == 0 and box.history_id == "h-alt"


def test_a_disconnected_mailbox_does_not_hold_up_sending(world, monkeypatch):
    """Mails an einem gestörten (oder getrennten) Postfach warten – ohne die übrigen
    aufzuhalten. Bug-Form: die ältesten 20 «fälligen» Mails eines toten Postfachs belegten
    jeden Lauf, und keine andere Mail ging je hinaus."""
    from datetime import datetime, timezone
    db, staff, box = world
    db.commit = db.flush
    box.problem = mb.EXPIRED
    other = Mailbox(channel="c999999989", address="ok@example.com",
                    owner_object_id=staff.object_id, token="x")
    db.add(other)
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    stuck = [Message(sender_object_id=staff.object_id, channel=CH, subject=f"S{i}", body="x",
                     at=old, outgoing=True) for i in range(25)]
    fine = Message(sender_object_id=staff.object_id, channel=other.channel, subject="ok",
                   body="x", at=datetime(2001, 1, 1, tzinfo=timezone.utc), outgoing=True)
    db.add_all([*stuck, fine])
    db.flush()
    tried: list[int] = []
    monkeypatch.setattr(mb, "send", lambda _db, m, _t=None: tried.append(m.id) or True)
    mb.send_due(db)
    assert fine.id in tried and not set(tried) & {m.id for m in stuck}


def test_a_mail_gmail_keeps_rejecting_gives_up_visibly(world, monkeypatch):
    """Weist Gmail eine Mail immer wieder ab, gibt der Versand nach ``MAX_ATTEMPTS`` auf, und
    der Grund steht als interne Nachricht unter ihrem Betreff im Verlauf. Bug-Form: sie blieb
    für immer «wartet auf Versand» und wurde alle 30 Sekunden erneut versucht."""
    db, staff, box = world
    lea = _person(db)
    msg = comm.create(db, MessageIn(channel=CH, to=[lea.object_id], subject="Offerte 7",
                                    body="Offerte"), staff)
    msg.outgoing = True
    monkeypatch.setattr(mb, "_token", lambda _mb, _t=None: "tok")
    monkeypatch.setattr(mb, "_post", lambda *_a: (None, "Gmail hat sie abgewiesen (400)."))
    for i in range(mb.MAX_ATTEMPTS):
        assert msg.outgoing, f"gibt zu früh auf ({i})"
        assert not mb.send(db, msg)
    assert not msg.outgoing
    note = db.query(Message).filter(Message.channel == "intern",
                                    Message.subject == "Offerte 7").one()
    assert "abgewiesen" in note.body
    assert lea.object_id in {p.object_id for p in comm.load(db, [note.id])[0].about}


def test_a_subject_is_one_line(world):
    """Ein Umbruch im Betreff bräche den Mail-Kopf – angelegt wird er einzeilig."""
    db, staff, _box = world
    lea = _person(db)
    m = comm.create(db, MessageIn(channel="intern", to=[staff.object_id], about=[lea.object_id],
                                  subject="Frage\r\nBcc: x@y.ch", body="x"), staff)
    assert m.subject == "Frage Bcc: x@y.ch"
