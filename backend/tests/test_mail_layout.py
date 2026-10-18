"""►►► **Ein Brief – jeder Absender** (``services/mail_layout``) und «erledigt = gelesen». ◄◄◄

Jede Mail des ERP trägt dieselbe Vorlage: Überschrift = Betreff, unterschrieben vom
Menschen im Namen der Gesellschaft (deren Telefon und E-Mail, keine Funktion, mit Bild),
eine automatische Mail vom Unternehmen. **Und was im Verlauf steht, ist was hinausging –
Wort für Wort.** Was im ERP erledigt ist, wird in Gmail gelesen – genau einmal. Jede
Prüfung nennt die Regel und ist gegen ihre Bug-Form gegengeprüft.
"""

import html as h
import random
import re
import time
from pathlib import Path
from types import SimpleNamespace

from app.models import Mailbox, Message
from app.schemas.communication import MessageIn
from app.services import communication as comm
from app.services import mail_layout as layout
from app.services import mailbox as mb
from tests.runner import session
from tests.test_mailbox import CH, COMPANY, _gmail, _person

FIRM = layout.Firm(name="INEXXIO AG", address=["Waldweg 1", "9546 Tuttwil"],
                   phone="+41 52 378 22 47", tel="+41523782247", email="info@inexxio.com",
                   picture="https://lh3.googleusercontent.com/a/konto")
MONIKA = layout.Signer(name="Monika Fritsche")


def words(text: str) -> list[str]:
    return re.findall(r"\w+", h.unescape(re.sub(r"<[^>]+>", " ", text)))


def inner(html: str) -> str:
    return html.split("<!--inhalt-->")[1].split("<!--/inhalt-->")[0]


def test_the_headline_is_the_subject_without_re():
    mail = layout.compose("Re: Traglast Hallenkran", "Guten Tag", FIRM, MONIKA)
    assert ">Traglast Hallenkran</h1>" in mail.html
    assert layout.text("AW: Traglast", "x", FIRM, None).startswith("Traglast\n")


def test_the_history_is_the_mail_word_for_word():
    """►►► Verlauf und Mail aus EINER Angabe – auch mit allen Bausteinen der Bestätigung.
    Bug-Form: «Danke für Ihre Nachricht» galt als Grussformel und fiel aus der Mail."""
    extra = layout.Extra(
        facts=layout.Facts("Ihre Angaben", [("Firma", "Muster AG"), ("Fotos", "2 Bilder")],
                           "Der Kran ruckelt."),
        steps=layout.Steps("So geht es weiter", [("Angekommen · 18.10.2026, 17:50", True),
                                                 ("Wir melden uns.", False)]),
        call="Eilt es? Dann rufen Sie uns direkt an:")
    lead = "Guten Tag Anna\n\nDanke für Ihre Nachricht.\n\nFällt Ihnen noch etwas ein?"
    mail = layout.compose("Ihre Anfrage", lead, FIRM, None, kicker="Anfrage erhalten", extra=extra)
    assert words(inner(mail.html)) == words(mail.body)
    assert "Danke für Ihre Nachricht" in mail.body and "Danke für Ihre Nachricht" in mail.html
    assert mail.body in mail.text          # die Textfassung trägt denselben Inhalt
    assert "+41 52 378 22 47" in mail.body and 'href="tel:+41523782247"' in mail.html


def test_a_reply_goes_out_as_it_stands_in_the_history(monkeypatch):
    """Was hinausgeht, ist die Vorlage – als Text UND als HTML, und ``body`` ist ihr Inhalt."""
    db = session()
    try:
        monkeypatch.setattr(mb, "company", lambda _db, _ch: None)
        staff = _person(db, "employee")
        lea = _person(db)
        box = Mailbox(channel=CH, address=COMPANY, owner_object_id=staff.object_id, token="x")
        db.add(box)
        msg = comm.write(db, Message(sender_object_id=staff.object_id, channel=CH,
                                     subject="Re: Seilwinde",
                                     body="Danke, das passt.\n\n\n\nBis bald", created_by=staff.id),
                         {"to": [lea.object_id], "cc": [], "bcc": [], "about": []})
        mime = mb._mime(db, box, msg, None)
        assert mime["From"].startswith(f"{staff.display_name} · INEXXIO")
        html = mime.get_body(("html",)).get_content()
        assert ">Seilwinde</h1>" in html and staff.display_name in html
        assert words(inner(html)) == words(msg.body)
        assert msg.body in mime.get_body(("plain",)).get_content()
    finally:
        db.rollback()
        db.close()


def test_a_person_signs_in_the_name_of_the_company_with_a_picture():
    """Name, darunter die Gesellschaft mit IHRER Nummer und Adresse – und das Bild daneben:
    das Profilbild, sonst die Initialen."""
    text = layout.text("Offerte", "Hallo", FIRM, layout.Signer("Clemens Fritsche"))
    sign = text.split("Freundliche Grüsse\n", 1)[1].split("\n")[:3]
    assert sign == ["Clemens Fritsche", "INEXXIO AG", "+41 52 378 22 47 · info@inexxio.com"]
    assert layout.sender_name(layout.Signer("Clemens Fritsche")) == "Clemens Fritsche · INEXXIO"
    assert layout.sender_name(None) == "INEXXIO"
    assert ">CF</td>" in layout.compose("x", "y", FIRM, layout.Signer("Clemens Fritsche")).html
    photo = layout.compose("x", "y", FIRM, layout.Signer("C F", photo="https://p/x.jpg")).html
    assert 'src="https://p/x.jpg"' in photo


def test_an_automatic_mail_is_signed_by_the_company_with_its_mailbox_picture():
    """Geschrieben hat sie niemand (``created_by`` leer) – also unterschreibt das
    Unternehmen, mit dem Bild seines Postfachs."""
    staff = SimpleNamespace(role="employee", display_name="Clemens Fritsche", photo_url=None)
    assert mb.signer_of(staff, SimpleNamespace(created_by=None)) is None
    assert mb.signer_of(staff, SimpleNamespace(created_by=7)).name == "Clemens Fritsche"
    assert mb.signer_of(SimpleNamespace(role="user", display_name="Kunde"),
                        SimpleNamespace(created_by=7)) is None
    html = layout.compose("x", "y", FIRM, None).html
    assert f'src="{FIRM.picture}"' in html and "Monika" not in html


def test_a_typed_closing_is_not_doubled_and_nothing_is_cut():
    body = "Ja, 5 t reichen.\n\nFreundliche Grüsse\nMonika"
    mail = layout.compose("x", body, FIRM, MONIKA)
    assert mail.html.count("Freundliche Grüsse") == 1 and "Monika</p>" in inner(mail.html)
    assert not layout.greeted("Danke für Ihre Nachricht.")


def test_no_stage_and_a_logo_without_a_background():
    """Keine getönte Fläche hinter der Mail, und das Logo ist durchsichtig – mit heller
    Fassung, wo der Client den dunklen Modus meldet."""
    from PIL import Image
    html = layout.compose("x", "y", FIRM, None).html
    assert "#EFEEEB" not in html and "#F7F6F4" not in html
    assert layout.LOGO_DARK in html and "prefers-color-scheme:dark" in html
    pub = Path(__file__).resolve().parents[2] / "frontend" / "public"
    for name in (layout.LOGO, layout.LOGO_DARK):
        im = Image.open(pub / name.lstrip("/"))
        assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0


def test_the_footer_is_two_quiet_lines_without_an_explanation():
    html = layout.compose("x", "y", FIRM, None).html
    foot = html.split("border-top:1px solid", 1)[1]
    assert "INEXXIO AG" in foot and "Waldweg 1" in foot and "+41 52 378 22 47" in foot
    assert "betrifft Ihr Konto" not in html


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


def test_the_mailbox_may_mark_mails_read_and_knows_its_picture():
    """Ohne ``gmail.modify`` liesse sich «UNREAD» nicht entfernen, ohne ``userinfo.profile``
    fehlte das Bild neben der Unterschrift."""
    assert "gmail.modify" in mb.SCOPES and "gmail.readonly" not in mb.SCOPES
    assert "userinfo.profile" in mb.SCOPES


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
