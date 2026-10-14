"""►►► **Postfach – Gmail ist der Speicher, das ERP der Verlauf** (CRM Schritt 3). ◄◄◄

Gefahren über den echten Dienst (``services/mailbox``) gegen echtes PostgreSQL – ohne
Netz: ``ingest`` bekommt, was Gmail liefern würde, und ``send`` wird dort ersetzt, wo es
Google anriefe. Jede Prüfung nennt die Regel, die sie hält.
"""

import base64
import random

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.models import Mailbox, Message, UserProfile
from app.schemas.communication import MessageIn
from app.services import communication as comm
from app.services import mailbox as mb
from tests.runner import session

COMPANY = "info.test@example.com"
#: Das Postfach einer (gedachten) eigenen Gesellschaft – die Form ``c<Objektnummer>``.
CH = "c999999990"


def _person(db, role="user", email=None) -> UserProfile:
    oid = random.randint(900_000_000, 999_999_999)
    u = UserProfile(firebase_uid=f"uid-{oid}", email=email or f"p{oid}@x.ch", role=role,
                    object_id=oid, first_name="P", last_name=str(oid))
    db.add(u)
    db.flush()
    return u


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
def world(monkeypatch):
    db = session()
    monkeypatch.setattr(mb, "company_address", lambda _db, _key: COMPANY)
    monkeypatch.setattr(mb, "_company_addresses", lambda _db: {COMPANY})
    staff = _person(db, "employee")
    box = Mailbox(channel=CH, address=COMPANY, owner_object_id=staff.object_id, token="x")
    db.add(box)
    db.flush()
    yield db, staff, box
    db.rollback()
    db.close()


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


def test_a_reply_in_gmail_answers_the_message_it_references(world):
    db, staff, box = world
    first = _gmail("x@kunde.ch", to=COMPANY, rfc="<a1@kunde>")
    mb.ingest(db, box, first)
    assert _one(db, first["id"]).open
    answer = _gmail(COMPANY, to="x@kunde.ch", labels=("SENT",), rfc="<b2@inexxio>",
                    in_reply_to="<a1@kunde>", references="<a1@kunde>")
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


def test_the_state_cannot_be_forged(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_secret", "geheim")
    state = mb._sign({"c": CH, "u": 1, "exp": 9e12})
    assert mb._unsign(state)["c"] == CH
    with pytest.raises(ValueError):
        mb._unsign(state[:-1] + ("0" if state[-1] != "0" else "1"))


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


def test_every_own_company_has_its_own_mailbox_and_the_old_info_moves_to_the_operator():
    """Ein Postfach je eigener Gesellschaft (``c<Objektnummer>``) – seine Adresse ist ihre
    Kontakt-E-Mail; das alte ``info`` wird beim Start das des Betreibers."""
    from app.domain import communication as dc
    assert dc.channel(dc.company(100000001)).kind == "email"
    assert dc.is_mail("c100000001") and dc.company_of("c100000001") == 100000001
    assert not dc.is_mail("phone") and dc.owner_of("c100000001") is None
    with pytest.raises(ValueError):
        dc.channel("info")
    sql = " ".join(dc.info_repair_sql())
    assert "is_own" in sql and "is_operator DESC" in sql and "channel = 'info'" in sql


def test_an_answer_in_gmail_closes_only_the_mail_it_answers(world):
    """``In-Reply-To`` nennt genau eine Mail – die übrigen im Faden (``References``)
    bleiben offen, und die Nachfrage eines Kunden erledigt seine erste Frage nicht. Jede
    muss für sich beantwortet oder als erledigt markiert werden."""
    db, staff, box = world
    first = _gmail("z@kunde.ch", to=COMPANY, rfc="<f1@kunde>")
    second = _gmail("z@kunde.ch", to=COMPANY, rfc="<f2@kunde>", in_reply_to="<f1@kunde>")
    mb.ingest(db, box, first)
    mb.ingest(db, box, second)
    answer = _gmail(COMPANY, to="z@kunde.ch", labels=("SENT",), rfc="<f3@inexxio>",
                    in_reply_to="<f2@kunde>", references="<f1@kunde> <f2@kunde>")
    mb.ingest(db, box, answer)
    assert _one(db, first["id"]).open and not _one(db, second["id"]).open
    assert _one(db, answer["id"]).reply_to == _one(db, second["id"]).id


def test_last_comma_first_is_turned_around():
    """«Fritsche, Clemens» ist «Nachname, Vorname» – gedreht, ohne Komma."""
    assert mb.split_name('"Fritsche, Clemens"') == ("Clemens", "Fritsche")
    assert mb.split_name("Lea  Maria Muster") == ("Lea", "Maria Muster")
    assert mb.split_name("  ") is None


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
        oid = random.randint(900_000_000, 999_999_999)
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
        # Lag beides schon vor der Kopplung auseinander, zieht der Start es nach.
        from sqlalchemy import text
        from app.domain.communication import contact_repair_sql
        firm.email = "vorher@anders.ch"
        db.flush()
        for stmt in contact_repair_sql():
            db.execute(text(stmt))
        db.refresh(firm)
        assert firm.email == f"neu{oid}@firma.ch"
        mb.disconnect(db, key, admin)
        assert firm.email == "" and mb.active(db, key) is None
    finally:
        db.rollback()
        db.close()
