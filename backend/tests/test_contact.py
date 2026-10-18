"""Wächter für das Anfrage-Formular der Website (``app/routers/contact.py``).

►►► **Eine Anfrage ist eine Nachricht im ERP** (``services/inquiry``). ◄◄◄ Gefahren wird
der Endpunkt gegen echtes PostgreSQL – nur ohne Netz: die Gesellschaft ist fest gewählt,
und das Postfach, über das die Bestätigung hinausgeht, ist ein Ersatz, der festhält, was
hinausginge. ``commit`` wird zu ``flush``, damit jede Prüfung am Ende zurückrollt.
"""
from __future__ import annotations

import io
import random
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.domain import communication as dc
from app.models import Message, MessageParty, UserProfile
from app.routers import contact
from app.services import communication as comm
from app.services import inquiry as svc
from app.services import mailbox as mb
from tests.runner import session

JSON = {"Accept": "application/json"}
MSG = contact.MSG
FIRM = 999_999_991
CHANNEL = f"c{FIRM}"


@pytest.fixture
def world(monkeypatch):
    db = session()
    db.commit = db.flush            # zurückrollbar bleiben
    staff = UserProfile(firebase_uid=f"uid-s{random.randint(1, 10**9)}", role="employee",
                        email=f"staff{random.randint(1, 10**9)}@inexxio.test",
                        object_id=random.randint(900_000_000, 999_999_999))
    db.add(staff)
    db.flush()
    sent: list[int] = []
    box = SimpleNamespace(owner_object_id=staff.object_id, problem=None, address="info@example.ch")
    monkeypatch.setattr(svc, "company_for", lambda _db, _country: SimpleNamespace(object_id=FIRM))
    monkeypatch.setattr(mb, "ready", lambda: True)
    monkeypatch.setattr(mb, "active", lambda _db, ch: box if ch == CHANNEL else None)
    monkeypatch.setattr(mb, "send", lambda _db, m: sent.append(m.id) or True)
    app = FastAPI()
    app.include_router(contact.router)
    app.dependency_overrides[get_db] = lambda: db
    contact.reset_rate_limit()
    yield SimpleNamespace(db=db, client=TestClient(app), sent=sent, box=box, staff=staff)
    db.rollback()
    db.close()


def form(**extra) -> dict:
    data = {"source": "/krantechnik/krane-nach-mass", "t": "8000",
            "message": "Hubwerk bleibt stehen.", "name": "Anna Muster",
            "company": "Muster AG", "phone": "052 000 00 00",
            "email": f"anna{random.randint(1, 10**9)}@muster.ch"}
    data.update(extra)
    return data


def png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def inquiries(db, email: str) -> list[Message]:
    person = db.query(UserProfile).filter(UserProfile.email == email.lower()).first()
    if person is None:
        return []
    return db.query(Message).filter(Message.sender_object_id == person.object_id).all()


# ------------------------------------------------------------------ Ins ERP

def test_an_inquiry_is_an_open_message_from_a_new_person(world):
    """Die Person wird angelegt (mit Telefon), die Anfrage steht offen im Postfach der
    Gesellschaft, die die Website diesem Besucher zeigt."""
    data = form(email="Neu.Kunde@Muster.CH")
    res = world.client.post("/api/v1/contact", data=data, headers=JSON)
    assert res.status_code == 200, res.text
    person = world.db.query(UserProfile).filter(UserProfile.email == "neu.kunde@muster.ch").one()
    assert (person.first_name, person.last_name, person.phone) == ("Anna", "Muster", "052 000 00 00")
    (msg,) = inquiries(world.db, data["email"])
    assert msg.channel == CHANNEL and msg.subject == svc.SUBJECT
    assert "Hubwerk bleibt stehen." in msg.body and "Firma: Muster AG" in msg.body
    assert "Seite: /krantechnik/krane-nach-mass" in msg.body
    out = comm.load(world.db, [msg.id])[0]
    assert out.open and not out.ours


def test_the_confirmation_is_in_the_history_but_answers_nothing(world):
    """Die Bestätigung geht über das Postfach hinaus und steht im Verlauf – unter EIGENEM
    Betreff: die Anfrage bleibt offen, bis ein Mensch antwortet (sonst wäre das 2-h-Ziel
    ausgehebelt)."""
    data = form()
    assert world.client.post("/api/v1/contact", data=data, headers=JSON).status_code == 200
    (inq,) = inquiries(world.db, data["email"])
    conf = world.db.query(Message).join(MessageParty, MessageParty.message_id == Message.id).filter(
        MessageParty.person_object_id == inq.sender_object_id, Message.id != inq.id).one()
    assert world.sent == [conf.id]
    assert conf.sender_object_id == world.staff.object_id and conf.channel == CHANNEL
    assert conf.subject == contact.VOCAB["mail"]["confirmSubject"]
    assert "Hubwerk bleibt stehen." in conf.body
    # In der Vorlage des Hauses: Überschrift = Betreff, OHNE Namen unterschrieben (geschrieben
    # hat sie niemand), und der allgemeine Weg, wenn es eilt.
    assert f">{conf.subject}</h1>" in conf.html
    assert world.staff.display_name not in conf.html
    assert contact.VOCAB["mail"]["urgent"] in conf.html
    assert dc.topic(conf.subject) != dc.topic(inq.subject)
    assert comm.load(world.db, [inq.id])[0].open


def test_a_known_email_is_the_same_person(world):
    first = form()
    world.client.post("/api/v1/contact", data=first, headers=JSON)
    again = form(email=first["email"].upper(), name="Anna M.")
    assert world.client.post("/api/v1/contact", data=again, headers=JSON).status_code == 200
    assert world.db.query(UserProfile).filter(UserProfile.email == first["email"]).count() == 1
    assert len(inquiries(world.db, first["email"])) == 2


def test_without_a_connected_mailbox_there_is_no_confirmation_but_the_inquiry_stands(world, monkeypatch):
    monkeypatch.setattr(mb, "active", lambda _db, _ch: None)
    data = form()
    assert world.client.post("/api/v1/contact", data=data, headers=JSON).status_code == 200
    assert world.sent == [] and len(inquiries(world.db, data["email"])) == 1


def test_a_failing_confirmation_does_not_fail_the_inquiry(world, monkeypatch):
    """Geht die Bestätigung nicht hinaus, bleibt sie als «muss noch hinaus» stehen – der
    nächste Abgleich holt sie nach; die Anfrage ist längst gespeichert."""
    monkeypatch.setattr(mb, "send", lambda _db, _m: False)
    data = form()
    assert world.client.post("/api/v1/contact", data=data, headers=JSON).status_code == 200
    (inq,) = inquiries(world.db, data["email"])
    conf = world.db.query(Message).filter(Message.channel == CHANNEL, Message.id > inq.id,
                                          Message.sender_object_id == world.staff.object_id).one()
    assert conf.outgoing


def test_photos_are_stored_and_linked(world):
    files = [("photos", ("typenschild.png", png(), "image/png"))]
    data = form()
    res = world.client.post("/api/v1/contact", data=data, files=files, headers=JSON)
    assert res.status_code == 200, res.text
    (msg,) = inquiries(world.db, data["email"])
    (att,) = msg.attachments
    assert att["name"] == "typenschild.png" and att["url"].startswith("/api/v1/attachments/")


# ------------------------------------------------------------------ Prüfen

def test_the_email_is_required_and_the_phone_is_not(world):
    res = world.client.post("/api/v1/contact", data=form(email="", phone=""), headers=JSON)
    assert res.status_code == 422
    assert res.json()["fields"] == {"email": MSG["contact"]}
    assert world.client.post("/api/v1/contact", data=form(phone=""), headers=JSON).status_code == 200


def test_missing_fields_come_back_with_the_websites_own_words(world):
    res = world.client.post("/api/v1/contact", data=form(message="", name="", email=""), headers=JSON)
    assert res.status_code == 422
    assert res.json()["fields"] == {"message": MSG["message"], "name": MSG["name"],
                                    "email": MSG["contact"]}


def test_without_javascript_success_redirects_and_errors_are_a_readable_page(world):
    res = world.client.post("/api/v1/contact", data=form(t=""), follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/kontakt/danke"
    res = world.client.post("/api/v1/contact", data=form(name=""))
    assert res.status_code == 422 and res.headers["content-type"].startswith("text/html")
    assert MSG["name"] in res.text and "Zurück-Taste" in res.text


def test_only_images_within_count_and_size(world):
    """Nur Bilder: ein PDF, eine falsche Endung, eine Datei, die sich als Bild ausgibt und
    keines ist, zu viele, zu gross – jedes kommt mit dem Satz der Website zurück, und
    gespeichert ist nichts."""
    data = form()
    pdf = [("photos", ("skizze.pdf", b"%PDF-1.4 " + b"0" * 500, "application/pdf"))]
    res = world.client.post("/api/v1/contact", data=data, files=pdf, headers=JSON)
    assert res.json()["fields"]["photos"] == MSG["photosType"].replace("{name}", "skizze.pdf")
    fake = [("photos", ("foto.jpg", b"kein bild", "image/jpeg"))]
    res = world.client.post("/api/v1/contact", data=data, files=fake, headers=JSON)
    assert res.status_code == 422 and "photos" in res.json()["fields"]
    many = [("photos", (f"f{i}.png", png(), "image/png")) for i in range(contact.PHOTOS["max"] + 1)]
    res = world.client.post("/api/v1/contact", data=data, files=many, headers=JSON)
    assert res.status_code == 422 and "photos" in res.json()["fields"]
    big = [("photos", ("gross.jpg", b"0" * (contact.PHOTOS["maxTotalBytes"] + 1), "image/jpeg"))]
    res = world.client.post("/api/v1/contact", data=data, files=big, headers=JSON)
    assert res.status_code in (413, 422)
    assert inquiries(world.db, data["email"]) == []
    assert contact.PHOTOS["extensions"] == [".jpg", ".jpeg", ".png", ".webp"]


def test_overlong_text_is_refused_with_the_limit(world):
    res = world.client.post("/api/v1/contact", data=form(message="x" * (contact.LIMITS["message"] + 1)), headers=JSON)
    assert res.status_code == 422 and str(contact.LIMITS["message"]) in res.json()["fields"]["message"]


# ------------------------------------------------------------------ Spam erzeugt nichts

def test_spam_creates_neither_a_person_nor_a_message(world):
    """Honigtopf (tut, als ginge es), zu schnell, zu oft – keine Person, keine Nachricht."""
    hp = form(hp="http://spam.example")
    res = world.client.post("/api/v1/contact", data=hp, headers=JSON)
    assert res.status_code == 200 and res.json()["ok"] is True
    fast = form(t="900")
    res = world.client.post("/api/v1/contact", data=fast, headers=JSON)
    assert res.status_code == 400 and res.json()["message"] == MSG["tooFast"]
    for data in (hp, fast):
        assert world.db.query(UserProfile).filter(UserProfile.email == data["email"]).count() == 0


def test_more_than_the_limit_per_hour_from_one_address_is_refused(world):
    headers = {**JSON, "X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
    for _ in range(contact.RATE_LIMIT):
        assert world.client.post("/api/v1/contact", data=form(), headers=headers).status_code == 200
    over = form()
    res = world.client.post("/api/v1/contact", data=over, headers=headers)
    assert res.status_code == 429 and contact.VOCAB["phone"]["display"] in res.json()["message"]
    assert inquiries(world.db, over["email"]) == []
    other = {**JSON, "X-Forwarded-For": "198.51.100.1"}
    assert world.client.post("/api/v1/contact", data=form(), headers=other).status_code == 200


# ------------------------------------------------------------------ Nie ein stilles «Danke»

def test_if_the_erp_cannot_store_it_the_page_shows_phone_and_mail(world, monkeypatch, capsys):
    def broken(_db, _inq, _country):
        raise RuntimeError("Datenbank weg")
    monkeypatch.setattr(svc, "record", broken)
    res = world.client.post("/api/v1/contact", data=form(), headers=JSON)
    assert res.status_code == 503 and res.json()["ok"] is False
    res = world.client.post("/api/v1/contact", data=form())      # ohne JS: HTML
    assert res.status_code == 503
    assert "tel:" + contact.VOCAB["phone"]["e164"] in res.text
    assert "mailto:" + contact.VOCAB["email"] in res.text
    log = capsys.readouterr().out
    assert "INQUIRY_UNSENT" in log and "Hubwerk bleibt stehen." in log


# ------------------------------------------------------------------ Vokabular

def _texts(value):
    """Jede Zeichenkette im Vokabular – die Struktur selbst (Listen in Listen) zählt nicht."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _texts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _texts(v)


def test_the_vocabulary_is_complete_and_consistent():
    """Jedes Feld, das die Website beschriftet, prüft der Server – und umgekehrt."""
    labelled = {name for name, _ in contact.VOCAB["labels"]}
    assert labelled == set(contact.FIELDS)
    for key in ("message", "name", "contact", "phone", "email",
                "photosCount", "photosType", "photosSize", "tooFast", "tooLong"):
        assert contact.MSG.get(key), key
    marked = [t for t in _texts(contact.VOCAB) if "[[" in t or "{{" in t]
    assert marked == []
