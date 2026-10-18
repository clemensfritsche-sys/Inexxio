"""►►► **Ein Brief – jeder Absender** (``services/mail_layout``) und «erledigt = gelesen». ◄◄◄

Jede Mail des ERP trägt dieselbe Vorlage: Überschrift = Betreff, unterschrieben vom
Menschen im Namen der Gesellschaft (deren Telefon und E-Mail, keine Funktion), eine
automatische Mail ohne Namen. Und was im ERP erledigt ist, wird in Gmail gelesen –
genau einmal. Jede Prüfung nennt die Regel und ist gegen ihre Bug-Form gegengeprüft.
"""

import random
import time
from types import SimpleNamespace

from app.models import Mailbox, Message
from app.schemas.communication import MessageIn
from app.services import communication as comm
from app.services import mail_layout as layout
from app.services import mailbox as mb
from tests.runner import session
from tests.test_mailbox import CH, COMPANY, _gmail, _person

FIRM = layout.Firm(name="INEXXIO AG", address=["Waldweg 1", "9546 Tuttwil"],
                   phone="052 378 22 47", email="info@inexxio.com")


def test_the_headline_is_the_subject_without_re():
    html = layout.html("Re: Traglast Hallenkran", "Guten Tag", FIRM, "Monika Fritsche")
    assert ">Traglast Hallenkran</h1>" in html
    assert layout.text("AW: Traglast", "x", FIRM, None).startswith("Traglast\n")


def test_a_person_signs_in_the_name_of_the_company():
    """Name des Menschen, darunter die Gesellschaft mit IHRER Nummer und IHRER Adresse."""
    text = layout.text("Offerte", "Hallo", FIRM, "Clemens Fritsche")
    sign = text.split("Freundliche Grüsse\n", 1)[1].split("\n")[:3]
    assert sign == ["Clemens Fritsche", "INEXXIO AG", "052 378 22 47 · info@inexxio.com"]
    assert layout.sender_name("Clemens Fritsche") == "Clemens Fritsche · INEXXIO"
    assert layout.sender_name(None) == "INEXXIO"


def test_an_automatic_mail_carries_no_name():
    """Geschrieben hat sie niemand – also unterschreibt niemand (``created_by`` leer)."""
    staff = SimpleNamespace(role="employee", display_name="Clemens Fritsche")
    assert mb.signer_of(staff, SimpleNamespace(created_by=None)) is None
    assert mb.signer_of(staff, SimpleNamespace(created_by=7)) == "Clemens Fritsche"
    assert mb.signer_of(SimpleNamespace(role="user", display_name="Kunde"),
                        SimpleNamespace(created_by=7)) is None


def test_a_typed_closing_is_not_doubled():
    body = "Ja, 5 t reichen.\n\nFreundliche Grüsse\nMonika"
    assert layout.html("x", body, FIRM, "Monika Fritsche").count("Freundliche Grüsse") == 1


def test_the_footer_is_two_quiet_lines_without_an_explanation():
    html = layout.html("x", "y", FIRM, None)
    foot = html.split("border-top:1px solid", 1)[1]
    assert "INEXXIO AG" in foot and "Waldweg 1" in foot and "052 378 22 47" in foot
    assert "betrifft Ihr Konto" not in html and "symbol" not in html


def test_the_mail_that_goes_out_is_the_layout(monkeypatch):
    """Was hinausgeht, ist die Vorlage – als Text UND als HTML, «Von» mit Mensch und Marke."""
    db = session()
    try:
        monkeypatch.setattr(mb, "company", lambda _db, _ch: None)
        staff = _person(db, "employee")
        lea = _person(db)
        box = Mailbox(channel=CH, address=COMPANY, owner_object_id=staff.object_id, token="x")
        db.add(box)
        msg = comm.write(db, Message(sender_object_id=staff.object_id, channel=CH,
                                     subject="Re: Seilwinde", body="Passt.", created_by=staff.id),
                         {"to": [lea.object_id], "cc": [], "bcc": [], "about": []})
        mime = mb._mime(db, box, msg, None)
        assert mime["From"].startswith(f"{staff.display_name} · INEXXIO")
        html = mime.get_body(("html",)).get_content()
        assert ">Seilwinde</h1>" in html and staff.display_name in html
        assert "Passt." in mime.get_body(("plain",)).get_content()
    finally:
        db.rollback()
        db.close()


def test_what_is_done_in_the_erp_is_read_in_gmail_once(monkeypatch):
    """Beantwortet → «UNREAD» weg, genau einmal; Offenes bleibt ungelesen."""
    db = session()
    calls: list[list[str]] = []
    try:
        monkeypatch.setattr(mb, "company_address", lambda _db, _key: COMPANY)
        monkeypatch.setattr(mb, "_company_addresses", lambda _db: {COMPANY})
        monkeypatch.setattr(mb, "_access", lambda _mb: "token")
        monkeypatch.setattr(mb.httpx, "post", lambda url, **kw: calls.append(kw["json"]["ids"])
                            or SimpleNamespace(status_code=204))
        staff = _person(db, "employee")
        box = Mailbox(channel=CH, address=COMPANY, owner_object_id=staff.object_id, token="x")
        db.add(box)
        db.flush()
        tag = random.randint(1, 10**9)
        done = _gmail("x@kunde.ch", to=COMPANY, subject=f"Seil {tag}", rfc=f"<a{tag}@k>")
        still = _gmail("y@kunde.ch", to=COMPANY, subject=f"Kran {tag}", rfc=f"<c{tag}@k>")
        answer = _gmail(COMPANY, to="x@kunde.ch", subject=f"Re: Seil {tag}",
                        labels=("SENT",), rfc=f"<b{tag}@i>")
        now = int(time.time() * 1000)
        for i, raw in enumerate((done, still, answer)):
            raw["internalDate"] = str(now - 60_000 + i * 1000)     # heute, nicht 2025
        for raw in (done, still, answer):
            mb.ingest(db, box, raw)
        mb._mark_read(db, box)
        assert calls == [[done["id"]]]
        mb._mark_read(db, box)
        assert len(calls) == 1          # genau einmal
    finally:
        db.rollback()
        db.close()


def test_the_mailbox_may_mark_mails_read():
    """Ohne ``gmail.modify`` liesse sich «UNREAD» nicht entfernen."""
    assert "gmail.modify" in mb.SCOPES and "gmail.readonly" not in mb.SCOPES


def test_an_internal_message_still_needs_no_mailbox():
    """Die Vorlage gilt für Mails – eine interne Nachricht geht nirgends hinaus."""
    db = session()
    try:
        staff = _person(db, "employee")
        other = _person(db, "employee")
        m = comm.create(db, MessageIn(channel="intern", to=[other.object_id], subject="Frage",
                                      body="Kannst du?"), staff)
        assert not m.outgoing and m.html is None
    finally:
        db.rollback()
        db.close()
