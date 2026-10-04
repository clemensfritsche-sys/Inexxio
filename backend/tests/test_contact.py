"""Wächter für das Anfrage-Formular der Website (``app/routers/contact.py``).

Gefahren wird der Endpunkt in einer **eigenen, leeren App** – nur mit diesem Router. Das
ist zugleich der Beweis für die Trennung vom ERP: läuft er so, braucht er weder Datenbank
noch Anmeldung noch ein anderes Modul.

Der Mailversand ist durch einen Briefkasten im Speicher ersetzt (``_smtp`` gepatcht);
geprüft wird, WAS verschickt würde – Empfänger, Betreff, Antwortadresse, Anhänge,
Bestätigung –, nicht ob ein fremder Server erreichbar ist.
"""
from __future__ import annotations

import json
import pathlib
import smtplib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import contact

JSON = {"Accept": "application/json"}
MSG = contact.MSG


class Mailbox:
    """Ersatz für ``smtplib.SMTP``: sammelt, was verschickt würde."""

    def __init__(self, fail: bool = False):
        self.sent = []
        self.logins = []
        self.fail = fail

    def __call__(self, settings):  # wird anstelle von contact._smtp gerufen
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.logins.append((user, password))

    def send_message(self, msg):
        if self.fail:
            raise smtplib.SMTPServerDisconnected("Verbindung weg")
        self.sent.append(msg)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(contact.router)
    contact.reset_rate_limit()
    return TestClient(app)


@pytest.fixture
def mailbox(monkeypatch):
    box = Mailbox()
    monkeypatch.setenv("INQUIRY_SMTP_HOST", "smtp.test")
    monkeypatch.setenv("INQUIRY_SMTP_USER", "website@test.ch")
    monkeypatch.setenv("INQUIRY_SMTP_PASSWORD", "geheim")
    monkeypatch.setattr(contact, "_smtp", box)
    return box


def short(**extra) -> dict:
    data = {
        "source": "/krantechnik/industriekrane", "t": "8000",
        "message": "Hubwerk bleibt stehen.", "name": "Anna Muster",
        "phone": "052 000 00 00", "email": "anna@muster.ch",
    }
    data.update(extra)
    return data


def main_form(**extra) -> dict:
    data = {
        "source": "/kontakt", "t": "45000", "message": "Jährliche Prüfung fällig.",
        "name": "Beat Beispiel", "company": "Beispiel AG",
        "phone": "+41 52 000 00 00", "email": "beat@beispiel.ch",
    }
    data.update(extra)
    return data


def attachments(msg):
    return [(p.get_filename(), p.get_content_type()) for p in msg.iter_attachments()]


# ------------------------------------------------------------------ Erfolg

def test_a_short_inquiry_reaches_us_and_the_customer_gets_a_copy(client, mailbox):
    res = client.post("/api/v1/contact", data=short(), headers=JSON)
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    internal, confirmation = mailbox.sent
    assert internal["Subject"] == "[Anfrage] Anna Muster"
    assert internal["To"] == contact.VOCAB["email"]
    assert "anna@muster.ch" in internal["Reply-To"]
    assert attachments(internal) == [("anfrage.json", "application/json")]
    assert "anna@muster.ch" in confirmation["To"]
    assert confirmation["Subject"] == contact.VOCAB["mail"]["confirmSubject"]
    body = confirmation.get_content()
    assert "Hubwerk bleibt stehen." in body and contact.VOCAB["phone"]["display"] in body
    assert mailbox.logins == [("website@test.ch", "geheim")]


def test_the_form_carries_photos_and_a_documented_record(client, mailbox):
    photos = [("photos", ("typenschild.jpg", b"\xff\xd8\xff" + b"0" * 2000, "image/jpeg")),
              ("photos", ("Schaden 1.HEIC", b"heic" * 100, "application/octet-stream"))]
    res = client.post("/api/v1/contact", data=main_form(), files=photos, headers=JSON)
    assert res.status_code == 200, res.text
    internal, confirmation = mailbox.sent
    assert internal["Subject"] == "[Anfrage] Beispiel AG"
    assert attachments(internal) == [
        ("typenschild.jpg", "image/jpeg"), ("Schaden_1.HEIC", "image/heic"), ("anfrage.json", "application/json"),
    ]
    record = json.loads(next(p for p in internal.iter_attachments() if p.get_filename() == "anfrage.json").get_content())
    assert record["schema"] == contact.SCHEMA
    assert record["message"] == "Jährliche Prüfung fällig."
    assert record["contact"] == {"name": "Beat Beispiel", "company": "Beispiel AG",
                                 "phone": "+41 52 000 00 00", "email": "beat@beispiel.ch"}
    assert not {"kind", "need", "urgency", "asset", "place"} & set(record)
    assert [p["filename"] for p in record["photos"]] == ["typenschild.jpg", "Schaden_1.HEIC"]
    # Die Bestätigung nennt immer den direkten Weg bei einem Stillstand: das Telefon.
    assert contact.VOCAB["mail"]["urgent"] in confirmation.get_content()


def test_a_sketch_as_pdf_is_attached(client, mailbox):
    """Skizzen dürfen als PDF kommen (Auftrag 11.1) – sie landen als Anhang bei uns."""
    sketch = [("photos", ("skizze.pdf", b"%PDF-1.4 " + b"0" * 500, "application/pdf"))]
    res = client.post("/api/v1/contact", data=main_form(), files=sketch, headers=JSON)
    assert res.status_code == 200, res.text
    internal = mailbox.sent[0]
    assert ("skizze.pdf", "application/pdf") in attachments(internal)
    assert internal["Subject"] == "[Anfrage] Beispiel AG"


def test_without_javascript_success_redirects_to_the_thank_you_page(client, mailbox):
    res = client.post("/api/v1/contact", data=short(t=""), follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/kontakt/danke"
    assert len(mailbox.sent) == 2


def test_no_confirmation_without_an_email_address(client, mailbox):
    res = client.post("/api/v1/contact", data=short(email=""), headers=JSON)
    assert res.status_code == 200
    assert len(mailbox.sent) == 1


# ------------------------------------------------------------------ Prüfen

def test_missing_fields_come_back_with_the_websites_own_words(client, mailbox):
    res = client.post("/api/v1/contact", data=short(message="", name="", phone="", email=""), headers=JSON)
    assert res.status_code == 422
    fields = res.json()["fields"]
    assert fields == {"message": MSG["message"], "name": MSG["name"], "phone": MSG["contact"]}
    assert mailbox.sent == []


def test_old_choice_fields_are_ignored_not_believed(client, mailbox):
    """Bereich, Anliegen und Dringlichkeit gibt es nicht mehr (04.10.2026) – eine alte Seite,
    die sie noch schickt, kommt trotzdem an; gelesen wird nur, was das Formular heute fragt."""
    res = client.post("/api/v1/contact", data=short(kind="kran", need="pruefung", urgency="dringend", place="9546"), headers=JSON)
    assert res.status_code == 200, res.text
    record = json.loads(next(p for p in mailbox.sent[0].iter_attachments()).get_content())
    assert not {"kind", "need", "urgency", "place"} & set(record)


def test_without_javascript_errors_come_back_as_a_readable_page(client, mailbox):
    res = client.post("/api/v1/contact", data=short(name=""))
    assert res.status_code == 422
    assert res.headers["content-type"].startswith("text/html")
    assert MSG["name"] in res.text and "Zurück-Taste" in res.text


def test_photos_are_limited_by_count_type_and_size(client, mailbox):
    many = [("photos", (f"f{i}.jpg", b"x", "image/jpeg")) for i in range(contact.PHOTOS["max"] + 1)]
    res = client.post("/api/v1/contact", data=main_form(), files=many, headers=JSON)
    assert res.status_code == 422 and "photos" in res.json()["fields"]
    wrong = [("photos", ("lebenslauf.docx", b"PK", "application/octet-stream"))]
    res = client.post("/api/v1/contact", data=main_form(), files=wrong, headers=JSON)
    assert res.json()["fields"]["photos"] == MSG["photosType"].replace("{name}", "lebenslauf.docx")
    big = [("photos", ("gross.jpg", b"0" * (contact.PHOTOS["maxTotalBytes"] + 1), "image/jpeg"))]
    res = client.post("/api/v1/contact", data=main_form(), files=big, headers=JSON)
    assert res.status_code in (413, 422)
    assert mailbox.sent == []


def test_text_is_cleaned_before_it_reaches_a_mail_header(client, mailbox):
    res = client.post("/api/v1/contact", data=short(name="Anna\r\nBcc:\x00 x@y.z"), headers=JSON)
    assert res.status_code == 200, res.text
    subject = mailbox.sent[0]["Subject"]
    assert "\n" not in subject and "\x00" not in subject
    assert subject == "[Anfrage] Anna Bcc: x@y.z"


def test_overlong_text_is_refused_with_the_limit(client, mailbox):
    res = client.post("/api/v1/contact", data=short(message="x" * (contact.LIMITS["message"] + 1)), headers=JSON)
    assert res.status_code == 422
    assert str(contact.LIMITS["message"]) in res.json()["fields"]["message"]


# ------------------------------------------------------------------ Schutz

def test_the_honeypot_pretends_success_and_sends_nothing(client, mailbox):
    res = client.post("/api/v1/contact", data=short(hp="http://spam.example"), headers=JSON)
    assert res.status_code == 200 and res.json()["ok"] is True
    assert mailbox.sent == []


def test_a_form_filled_faster_than_a_human_can_type_is_refused(client, mailbox):
    res = client.post("/api/v1/contact", data=short(t="900"), headers=JSON)
    assert res.status_code == 400
    assert res.json()["message"] == MSG["tooFast"]
    assert mailbox.sent == []


def test_more_than_the_limit_per_hour_from_one_address_is_refused(client, mailbox, monkeypatch):
    monkeypatch.setenv("INQUIRY_RATE_LIMIT", "2")
    headers = {**JSON, "X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
    assert client.post("/api/v1/contact", data=short(), headers=headers).status_code == 200
    assert client.post("/api/v1/contact", data=short(), headers=headers).status_code == 200
    res = client.post("/api/v1/contact", data=short(), headers=headers)
    assert res.status_code == 429
    assert contact.VOCAB["phone"]["display"] in res.json()["message"]
    other = {**JSON, "X-Forwarded-For": "198.51.100.1"}
    assert client.post("/api/v1/contact", data=short(), headers=other).status_code == 200


# ------------------------------------------------------------------ Keine Anfrage geht still verloren

def test_without_a_mail_server_the_form_falls_back_instead_of_pretending(client, monkeypatch, capsys):
    monkeypatch.delenv("INQUIRY_SMTP_HOST", raising=False)
    res = client.post("/api/v1/contact", data=short(), headers=JSON)
    assert res.status_code == 503 and res.json()["ok"] is False
    log = capsys.readouterr().out
    assert "INQUIRY_UNSENT" in log and "Hubwerk bleibt stehen." in log


def test_a_failing_mail_server_shows_phone_and_a_prefilled_mailto(client, monkeypatch, capsys):
    monkeypatch.setenv("INQUIRY_SMTP_HOST", "smtp.test")
    monkeypatch.setattr(contact, "_smtp", Mailbox(fail=True))
    res = client.post("/api/v1/contact", data=short())  # ohne JS: HTML
    assert res.status_code == 503
    assert "tel:" + contact.VOCAB["phone"]["e164"] in res.text
    assert "mailto:" + contact.VOCAB["email"] in res.text
    assert "%5BAnfrage%5D" in res.text  # derselbe Betreff wie die E-Mail, im Link
    assert "INQUIRY_UNSENT" in capsys.readouterr().out


def test_a_failed_confirmation_does_not_fail_the_inquiry(client, monkeypatch):
    class HalfBox(Mailbox):
        def send_message(self, msg):
            if self.sent:
                raise smtplib.SMTPRecipientsRefused({})
            self.sent.append(msg)

    box = HalfBox()
    monkeypatch.setenv("INQUIRY_SMTP_HOST", "smtp.test")
    monkeypatch.setattr(contact, "_smtp", box)
    res = client.post("/api/v1/contact", data=short(), headers=JSON)
    assert res.status_code == 200 and len(box.sent) == 1


# ------------------------------------------------------------------ Trennung und Vokabular

def test_the_endpoint_imports_nothing_from_the_erp():
    source = pathlib.Path(contact.__file__).read_text("utf-8")
    for forbidden in ("from ..models", "from ..services", "from ..core", "from app.", "import app."):
        assert forbidden not in source, forbidden


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
    # Kein unaufgelöster Wert ({{…}}) in einer E-Mail – gefragt wird jeder TEXT,
    # nicht das JSON: dort steht «[[» schon in jeder Liste von Paaren.
    marked = [t for t in _texts(contact.VOCAB) if "[[" in t or "{{" in t]
    assert marked == []
