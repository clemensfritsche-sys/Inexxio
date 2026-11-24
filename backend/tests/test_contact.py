"""Wächter für das Anfrage-Formular der Website (``app/routers/contact.py``).

►►► **Eine Anfrage ist eine Nachricht im ERP** (``services/inquiry``). ◄◄◄ Gefahren wird
der Endpunkt gegen echtes PostgreSQL – nur ohne Netz: die Gesellschaft ist fest gewählt,
und das Postfach, über das die Bestätigung hinausgeht, ist ein Ersatz, der festhält, was
hinausginge. ``commit`` wird zu ``flush``, damit jede Prüfung am Ende zurückrollt.
"""
from __future__ import annotations

import inspect
import io
import random
import re
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.factories import quiet_outbox
from tests.support import after_save
from app.core.database import get_db
from app.domain import communication as dc
from app.models import Message, MessageParty, UserProfile
from app.schemas.communication import MessageIn
from app.routers import contact
from app.services import communication as comm
from app.services import inquiry as svc
from app.services import mailbox as mb
from app.services import people, visitor
from tests.test_mail_layout import pictures

JSON = {"Accept": "application/json"}
MSG = contact.MSG
FIRM = 999_999_991
CHANNEL = f"c{FIRM}"


@pytest.fixture
def world(db, monkeypatch):
    db.commit = db.flush            # zurückrollbar bleiben
    quiet_outbox(db)
    staff = UserProfile(firebase_uid=f"uid-s{random.randint(1, 10**9)}", role="employee",
                        email=f"staff{random.randint(1, 10**9)}@inexxio.test",
                        object_id=random.randint(900_000_000, 999_999_999))
    db.add(staff)
    db.flush()
    sent: list[int] = []
    box = SimpleNamespace(owner_object_id=staff.object_id, problem=None, address="info@example.ch",
                          picture="https://lh3.googleusercontent.com/a/konto")
    monkeypatch.setattr(svc.mail_layout, "firm_of", lambda _c, a, p="": svc.mail_layout.Firm(
        name="Inexxio AG", phone="+41 52 378 22 47", tel="+41523782247", email=a, picture=p))
    monkeypatch.setattr(svc, "company_for", lambda _db, _country: SimpleNamespace(object_id=FIRM))
    monkeypatch.setattr(mb, "ready", lambda: True)
    monkeypatch.setattr(mb, "active", lambda _db, ch: box if ch == CHANNEL else None)
    monkeypatch.setattr(mb, "send", lambda _db, m, *_: sent.append(m.id) or True)
    app = FastAPI()
    app.include_router(contact.router)
    app.dependency_overrides[get_db] = lambda: db
    visitor.reset()
    yield SimpleNamespace(db=db, client=TestClient(app), sent=sent, box=box, staff=staff)


def form(**extra) -> dict:
    data = {"source": "/krantechnik/krane-nach-mass", "t": "8000",
            "message": "Hubwerk bleibt stehen.", "name": "Anna Muster",
            "company": "Muster AG", "phone": "052 000 00 00",
            "email": f"anna{random.randint(1, 10**9)}@muster.ch"}
    data.update(extra)
    return data


def words(text: str) -> list[str]:
    import html as h
    import re
    return re.findall(r"\w+", h.unescape(re.sub(r"<[^>]+>", " ", text)))


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
    assert (person.first_name, person.last_name, person.phone) == ("Anna", "Muster", "+41 52 000 00 00")
    (msg,) = inquiries(world.db, data["email"])
    assert msg.channel == CHANNEL and msg.subject == "Anfrage"
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
    after_save(world.db)
    (inq,) = inquiries(world.db, data["email"])
    conf = world.db.query(Message).join(MessageParty, MessageParty.message_id == Message.id).filter(
        MessageParty.object_id == inq.sender_object_id, Message.id != inq.id).one()
    assert world.sent == [conf.id]
    # Geschrieben hat sie niemand – sie kommt von der Gesellschaft, nicht vom Admin, der
    # das Postfach verband.
    from app.domain import communication as dcom
    assert conf.sender_object_id == dcom.company_of(CHANNEL) and conf.channel == CHANNEL
    assert not conf.inbound and inq.inbound
    assert conf.subject == contact.VOCAB["mail"]["confirmSubject"]
    # Zwei Betreffs, zwei Anliegen: die Bestätigung erledigt die Anfrage nicht.
    from app.domain import communication as dcm
    assert dcm.topic(conf.subject) != dcm.topic(inq.subject)
    assert "Hubwerk bleibt stehen." not in conf.body, "kein Relais für fremden Text"
    # In der Vorlage des Hauses: Überschrift = Betreff, OHNE Namen unterschrieben (geschrieben
    # hat sie niemand), und der allgemeine Weg, wenn es eilt.
    assert f">{conf.subject}</h1>" in conf.html
    assert world.staff.display_name not in conf.html
    assert contact.VOCAB["mail"]["urgent"] in conf.html and "+41 52 378 22 47" in conf.html
    # Die Unterschrift trägt das Bild des Postfachs.
    assert [photo for photo, _ in pictures(conf.html)] == [world.box.picture]
    # ►►► Der Verlauf IST der Inhalt der Mail – Wort für Wort (die Anfrage-Bug-Form strich
    # «Danke für Ihre Nachricht» in der Mail und zeigte ihn im Verlauf).
    inner = conf.html.split("<!--inhalt-->")[1].split("<!--/inhalt-->")[0]
    assert words(inner) == words(conf.body)
    assert contact.VOCAB["mail"]["confirmIntro"] in conf.body
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
    monkeypatch.setattr(mb, "send", lambda _db, _m, *_: False)
    data = form()
    assert world.client.post("/api/v1/contact", data=data, headers=JSON).status_code == 200
    (inq,) = inquiries(world.db, data["email"])
    conf = world.db.query(Message).filter(Message.channel == CHANNEL, Message.id > inq.id,
                                          Message.inbound.is_(False)).one()
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
    assert res.json()["fields"] == {"email": MSG["emailMissing"]}
    assert world.client.post("/api/v1/contact", data=form(phone=""), headers=JSON).status_code == 200


def test_missing_fields_come_back_with_the_websites_own_words(world):
    res = world.client.post("/api/v1/contact", data=form(message="", name="", email=""), headers=JSON)
    assert res.status_code == 422
    assert res.json()["fields"] == {"message": MSG["message"], "name": MSG["name"],
                                    "email": MSG["emailMissing"]}


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
    res = world.client.post("/api/v1/contact", data=form(message="x" * (svc.LIMITS["message"] + 1)), headers=JSON)
    assert res.status_code == 422 and str(svc.LIMITS["message"]) in res.json()["fields"]["message"]


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


def test_a_forged_front_of_the_chain_does_not_reset_the_limit(world):
    """Die vorderen Einträge von ``X-Forwarded-For`` setzt der Absender selbst – wer sie bei
    jeder Sendung ändert, darf damit nicht die Grenze umgehen (Bug-Form: der erste Eintrag
    zählte)."""
    proxies = "203.0.113.7, 10.0.0.1, 10.0.0.2"
    for i in range(contact.RATE_LIMIT):
        h = {**JSON, "X-Forwarded-For": f"192.0.2.{i}, {proxies}"}
        assert world.client.post("/api/v1/contact", data=form(), headers=h).status_code == 200
    h = {**JSON, "X-Forwarded-For": f"192.0.2.99, {proxies}"}
    assert world.client.post("/api/v1/contact", data=form(), headers=h).status_code == 429


def test_the_global_limit_holds_whatever_the_sender_says(world, monkeypatch):
    monkeypatch.setattr(visitor, "GLOBAL_LIMIT", 3)
    for i in range(3):
        h = {**JSON, "X-Forwarded-For": f"198.51.100.{i}"}
        assert world.client.post("/api/v1/contact", data=form(), headers=h).status_code == 200
    h = {**JSON, "X-Forwarded-For": "198.51.100.77"}
    assert world.client.post("/api/v1/contact", data=form(), headers=h).status_code == 429


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
    assert labelled == set(svc.FIELDS)
    for key in ("message", "name", "emailMissing", "phone", "email",
                "photosCount", "photosType", "photosSize", "tooFast", "tooLong"):
        assert contact.MSG.get(key), key
    marked = [t for t in _texts(contact.VOCAB) if "[[" in t or "{{" in t]
    assert marked == []


# ------------------------------------------------------------------ Browser und Server: EINE Quelle



def test_the_mailto_way_out_carries_the_subject_of_the_erp_message(world, monkeypatch):
    """Der mailto-Ausweg landet im Postfach derselben Gesellschaft – unter demselben Betreff
    wie die Nachricht, die das Formular angelegt hätte; was jemand schrieb, steht nicht darin."""
    def broken(_db, _inq, _country):
        raise RuntimeError("Datenbank weg")
    monkeypatch.setattr(svc, "record", broken)
    data = form(message="Kran läuft beim Anfahren ruckartig. Seit gestern.")
    res = world.client.post("/api/v1/contact", data=data)
    assert res.status_code == 503
    assert "subject=Anfrage&amp;" in res.text
    assert quote("Kran läuft") not in res.text.split("body=")[0]


def test_the_words_and_patterns_of_an_inquiry_stand_once():
    """Muster, Beschriftungen und der Name kommen aus dem Vokabular der Website – weder der
    Endpunkt noch die Nachricht im ERP schreiben sie ein zweites Mal (das Formular liest
    dasselbe Vokabular, ``website/src/scripts/form.ts``: ``vocab.patterns``)."""
    assert people.EMAIL.pattern == contact.VOCAB["patterns"]["email"]
    assert svc.PHONE_RE.pattern == contact.VOCAB["patterns"]["phone"]
    router = inspect.getsource(contact)
    assert not re.search(r're\.compile\(r"[^"]*(@|\\d\]\[)', router), "eigenes Muster im Endpunkt"
    assert "ehemals" not in router
    body = inspect.getsource(svc._body)
    for label in ("Firma", "Telefon", "Seite"):
        assert f'"{label}"' not in body, label


def test_an_answer_closes_only_the_inquiry_of_its_person(world):
    """Jede Anfrage heisst «Anfrage» – offen bleibt sie je Person. Bug-Form: eine Antwort an
    Anna erledigte auch die Anfrage von Beat (gleicher Betreff)."""
    a, b = form(), form(name="Beat Beispiel")
    for data in (a, b):
        assert world.client.post("/api/v1/contact", data=data, headers=JSON).status_code == 200
    (qa,), (qb,) = inquiries(world.db, a["email"]), inquiries(world.db, b["email"])
    reply = comm.create(world.db, MessageIn(channel=CHANNEL, to=[qa.sender_object_id],
                                            subject="Anfrage", body="Gern."), world.staff)
    reply.outgoing = False
    world.db.flush()
    assert comm.answered(world.db, [qa.id, qb.id]) == {qa.id}


def test_the_confirmation_carries_nothing_a_stranger_typed(world):
    """►►► **Die Eingangsbestätigung ist kein Spam-Relais.** ◄◄◄ Wer eine fremde Adresse
    eintippt, schickt über uns keinen Text, keine Firma und keinen Link an sie – und einen Namen
    nur, wenn er wie ein Name aussieht (``salutation_name``). Bug-Form: die Bestätigung kopierte
    die Angaben (und machte Adressen darin zu Links)."""
    data = form(message="Gewinn abholen: https://spam.example/x", name="Gewinn: spam.example/x",
                company="Klick Hier AG")
    assert world.client.post("/api/v1/contact", data=data, headers=JSON).status_code == 200
    (inq,) = inquiries(world.db, data["email"])
    conf = world.db.query(Message).join(MessageParty, MessageParty.message_id == Message.id).filter(
        MessageParty.object_id == inq.sender_object_id, Message.id != inq.id).one()
    for foreign in ("spam.example", "Gewinn", "Klick Hier", data["phone"]):
        assert foreign not in conf.body and foreign not in conf.html, foreign
    assert conf.body.startswith("Guten Tag\n"), "ohne Namen steht die Anrede allein"
    assert "spam.example" in inq.body, "die Anfrage selbst bleibt vollständig"


def test_a_real_name_is_greeted():
    """«Guten Tag Clemens Fritsche» – Vor- und Nachname, ohne Herr/Frau. Nur Buchstaben,
    Bindestrich, Apostroph; höchstens vier Wörter und 40 Zeichen, sonst keine Anrede mit Namen."""
    for ok in ("Clemens Fritsche", "Anne-Marie D'Amico", "Zoë Müller", "José da Silva Costa"):
        assert svc.salutation_name(ok) == ok, ok
    for bad in ("www.spam.ch", "Gewinn: 1000 CHF", "Max 2", "a b c d e", "x" * 41, "<b>Hi</b>", ""):
        assert svc.salutation_name(bad) == "", bad
    words = svc.words("de")["mail"]
    assert svc.lead(words, "de", "  Clemens   Fritsche ").startswith("Guten Tag Clemens Fritsche\n")
    assert svc.lead(words, "fr", "Clemens Fritsche").startswith("Bonjour Clemens Fritsche\n")


def test_the_form_never_writes_into_an_existing_person(world):
    """Ein Telefon aus dem öffentlichen Formular übernimmt nur eine **neue** Person. Bug-Form:
    eine bestehende Person ohne Telefon bekam die Nummer, die ein Fremder eintippte."""
    known = UserProfile(firebase_uid=f"uid-k{random.randint(1, 10**9)}", role="user",
                        email=f"known{random.randint(1, 10**9)}@muster.ch",
                        object_id=random.randint(900_000_000, 999_999_999))
    world.db.add(known)
    world.db.flush()
    data = form(email=known.email, phone="052 111 22 33")
    assert world.client.post("/api/v1/contact", data=data, headers=JSON).status_code == 200
    world.db.refresh(known)
    assert known.phone is None
    fresh = form(phone="052 111 22 33")
    assert world.client.post("/api/v1/contact", data=fresh, headers=JSON).status_code == 200
    (inq,) = inquiries(world.db, fresh["email"])
    new = world.db.query(UserProfile).filter(UserProfile.object_id == inq.sender_object_id).one()
    assert new.phone == "+41 52 111 22 33"


# ------------------------------------------------------------------ In der Sprache der Seite

def test_a_french_page_gets_french_answers_and_its_own_thanks_page(world):
    """►►► **Der Server antwortet in der Sprache der Seite** (`?lang=`, WEBSITE_PLAN Entscheid 136). ◄◄◄
    Meldungen am Feld, die Seite ohne JavaScript und die Danke-Seite kommen aus den Wörtern dieser
    Sprache. Bug-Form: eine französische Seite bekam deutsche Fehler und landete auf /kontakt/danke."""
    fr = svc.words("fr")
    assert fr["messages"]["name"] != MSG["name"], "ohne Übersetzung prüft dieser Test nichts"
    res = world.client.post("/api/v1/contact?lang=fr", data=form(name=""), headers=JSON)
    assert res.status_code == 422 and res.json()["fields"] == {"name": fr["messages"]["name"]}
    assert res.json()["message"] == fr["server"]["check"]
    res = world.client.post("/api/v1/contact?lang=fr", data=form(name=""))
    assert '<html lang="fr">' in res.text and fr["server"]["back"] in res.text and "Zurück-Taste" not in res.text
    res = world.client.post("/api/v1/contact?lang=fr", data=form(t=""), follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == fr["pages"]["thanks"] != "/kontakt/danke"


def test_the_confirmation_speaks_the_language_of_the_page(world):
    """Die Eingangsbestätigung einer französischen Anfrage ist französisch – Betreff, Anrede, Text."""
    fr = svc.words("fr")["mail"]
    data = form()
    assert world.client.post("/api/v1/contact?lang=fr", data=data, headers=JSON).status_code == 200
    after_save(world.db)
    (inq,) = inquiries(world.db, data["email"])
    conf = world.db.query(Message).join(MessageParty, MessageParty.message_id == Message.id).filter(
        MessageParty.object_id == inq.sender_object_id, Message.id != inq.id).one()
    assert conf.subject == fr["confirmSubject"] != svc.VOCAB["mail"]["confirmSubject"]
    assert fr["confirmIntro"] in conf.body and "Guten Tag" not in conf.body


def test_an_unknown_language_is_german(world):
    res = world.client.post("/api/v1/contact?lang=xx", data=form(name=""), headers=JSON)
    assert res.json()["fields"] == {"name": MSG["name"]}


def test_the_person_keeps_the_language(world):
    """►►► **Die Sprache gehört zur Person.** ◄◄◄ Wer zum ersten Mal von der französischen Seite
    schreibt, ist ab dann französisch; eine bestehende Person ändert das öffentliche Formular nie
    (wie ihr Telefon) – das tut sie selbst im Konto oder das Personal im ERP. Die Sprachen der
    Person sind genau die der Website. Bug-Form: nur die erste Mail sprach Französisch."""
    from typing import get_args
    from app.schemas.admin import Language
    assert set(get_args(Language)) == set(svc.LANGS)
    data = form()
    assert world.client.post("/api/v1/contact?lang=fr", data=data, headers=JSON).status_code == 200
    person = world.db.query(UserProfile).filter(UserProfile.email == data["email"]).one()
    assert person.language == "fr"
    again = dict(data, message="Noch eine Frage, diesmal auf Deutsch.")
    assert world.client.post("/api/v1/contact?lang=de", data=again, headers=JSON).status_code == 200
    world.db.refresh(person)
    assert person.language == "fr", "das Formular schreibt nie in eine bestehende Person"
