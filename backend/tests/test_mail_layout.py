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
from app.services import outbox
from app.services import portrait
from tests.runner import session
from tests.test_mailbox import CH, COMPANY, _gmail, _person

FIRM = layout.Firm(name="INEXXIO AG", address=["Waldweg 1", "9546 Tuttwil"],
                   phone="+41 52 378 22 47", tel="+41523782247", email="info@inexxio.com",
                   picture="https://lh3.googleusercontent.com/a/konto", city="Tuttwil")
MONIKA = layout.Signer(name="Monika Fritsche")


def words(text: str) -> list[str]:
    return re.findall(r"\w+", h.unescape(re.sub(r"<[^>]+>", " ", text)))


def inner(html: str) -> str:
    return html.split("<!--inhalt-->")[1].split("<!--/inhalt-->")[0]


def pictures(html: str) -> list[tuple[str, str]]:
    """Was die Bilder der Unterschrift zeigen: (Foto, Initialen) – aus ihrer Adresse."""
    return [portrait.read(t) for t in re.findall(re.escape(portrait.PATH) + r'([^"/]+)\.gif', html)]


def test_the_headline_is_the_subject_without_re():
    mail = layout.compose("Re: Traglast Hallenkran", "Guten Tag", FIRM, MONIKA)
    assert ">Traglast Hallenkran</h1>" in mail.html
    assert layout.text("AW: Traglast", "x", FIRM, None).startswith("Traglast\n")


def test_the_history_is_the_mail_word_for_word():
    """►►► Verlauf und Mail aus EINER Angabe – auch mit den Bausteinen der Bestätigung.
    Bug-Form: «Danke für Ihre Nachricht» galt als Grussformel und fiel aus der Mail."""
    extra = layout.Extra(call="Eilt es? Dann rufen Sie uns an:")
    lead = "Guten Tag Anna\n\nDanke für Ihre Nachricht.\n\nFällt Ihnen noch etwas ein?"
    mail = layout.compose("Ihre Anfrage", lead, FIRM, None, extra=extra)
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
    sign = text.split("Beste Grüsse aus Tuttwil\n", 1)[1].split("\n")[:4]
    assert sign[:3] == ["Clemens Fritsche", "INEXXIO AG", "Waldweg 1, 9546 Tuttwil"]
    assert sign[3].startswith("+41 52 378 22 47 · info@inexxio.com · "), "ohne Funktion, mit Website"
    assert layout.sender_name(layout.Signer("Clemens Fritsche")) == "Clemens Fritsche · INEXXIO"
    assert layout.sender_name(None) == "INEXXIO"
    plain = layout.compose("x", "y", FIRM, layout.Signer("Clemens Fritsche")).html
    assert pictures(plain) == [("", "CF")]
    photo = layout.compose("x", "y", FIRM, layout.Signer("C F", photo="https://p/x.jpg")).html
    assert pictures(photo) == [("https://p/x.jpg", "CF")] and "https://p/x.jpg" not in photo


def test_every_mail_signs_through_one_signer():
    """►►► EIN Unterzeichner für jede Mail (``as_signer``): Name UND Profilbild – auch in
    Beleg- und Dokument-Mails. Bug-Form: dort fehlte das Bild, nur das Postfach hatte es."""
    clemens = SimpleNamespace(display_name="Clemens Fritsche", photo_url="https://p/c.jpg")
    assert layout.as_signer(clemens) == layout.Signer("Clemens Fritsche", "https://p/c.jpg")
    assert layout.as_signer(SimpleNamespace(display_name=None, photo_url=None)) == layout.Signer("")
    app = Path(__file__).resolve().parents[1] / "app"
    built = [f.relative_to(app).as_posix() for f in app.rglob("*.py")
             if f.name != "mail_layout.py" and re.search(r"\bSigner\(", f.read_text())]
    assert built == [], f"Unterzeichner an zweiter Stelle gebaut: {built}"


def test_the_picture_opens_once_and_stands():
    """Das Bild des Hauses (``portrait``): ein GIF, zuerst das fertige Bild (Outlook zeigt nur
    dieses), dann einmal die Bewegung, dann Ruhe – keine Schleife, durchsichtig daneben."""
    import io
    from PIL import Image
    gif = Image.open(io.BytesIO(portrait.render(None, "CF")))
    assert gif.n_frames > 10 and "loop" not in gif.info
    first = gif.convert("RGBA")
    gif.seek(gif.n_frames - 1)
    assert first.tobytes() == gif.convert("RGBA").tobytes()
    assert first.getpixel((0, 0))[3] == 0                 # durchsichtig, wo kein Streifen ist
    assert (portrait.WIDTH * 2, portrait.HEIGHT * 2) == first.size


def test_an_automatic_mail_is_signed_by_the_company_with_its_mailbox_picture(db):
    """Geschrieben hat sie niemand (``created_by`` leer) – also unterschreibt das
    Unternehmen, mit dem Bild seines Postfachs (``outbox.signer``)."""
    staff, kunde = _person(db, "employee"), _person(db)
    assert outbox.signer(db, Message(sender_object_id=staff.object_id, created_by=None)) is None
    assert outbox.signer(db, Message(sender_object_id=staff.object_id, created_by=7)).name \
        == staff.display_name
    assert outbox.signer(db, Message(sender_object_id=kunde.object_id, created_by=7)) is None
    html = layout.compose("x", "y", FIRM, None).html
    assert pictures(html) == [(FIRM.picture, "IA")] and "Monika" not in html
    bare = layout.Firm(name="INEXXIO AG")
    assert pictures(layout.compose("x", "y", bare, None).html) == []


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
    assert not any(tint in html for tint in ("#EFEEEB", "#F7F6F4", "#EEEFF1", "#F5F6F7"))
    assert layout.LOGO_DARK in html and "prefers-color-scheme:dark" in html
    pub = Path(__file__).resolve().parents[2] / "frontend" / "public"
    for name in (layout.LOGO, layout.LOGO_DARK):
        im = Image.open(pub / name.lstrip("/"))
        assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0


def test_the_signature_is_the_footer_and_below_stands_the_strip():
    """►►► **Die Unterschrift ist der Fuss** (Gesellschaft, Anschrift, Telefon, E-Mail, Website –
    direkt nach «Beste Grüsse aus <Ort>»), darunter der **Streifen** mit Bild, Stichwort und Link
    in der Sprache der Mail – in jeder Mail. Bug-Form: ein zweiter Block mit der Anschrift unten,
    vom Text abgekoppelt; oder ein Streifen, der nur deutsch spricht. ◄◄◄"""
    html = layout.compose("x", "y", FIRM, None).html
    sign, strip = html.split("<!--/inhalt-->", 1)[1].split("Nachfolge geregelt", 1)
    assert "Beste Grüsse aus Tuttwil" in sign and "Waldweg 1, 9546 Tuttwil" in sign
    assert "/mail/nachfolge.jpg" in sign + strip and "/ueber-uns#uebergabe" in sign + strip
    assert html.count("Waldweg 1") == 1, "die Anschrift steht einmal – in der Unterschrift"
    fr = layout.compose("x", "y", FIRM, None, lang="fr")
    assert "Succession assurée" in fr.html and "/fr/" in fr.html and "Tuttwil" in fr.html
    assert "Succession assurée" in fr.text and "Nachfolge" not in fr.html
    nowhere = layout.Firm(name="INEXXIO AG")
    assert "Beste Grüsse\n" in layout.text("x", "y", nowhere, None), "ohne Ort ohne «aus»"
    assert "betrifft Ihr Konto" not in html


def test_the_headline_and_the_logo_share_a_row():
    """Kopf: am Computer links die Überschrift (= Betreff), rechts auf gleicher Höhe das Logo –
    eine Zeile, die von rechts nach links läuft (das Logo steht im Quelltext zuerst, damit es am
    Handy über der Überschrift steht, ``.ix-col``); kein Stichwort daneben. Das Logo ist das
    gestapelte mit Unterzeile und «ehemals HS Steiner», dezent (höchstens 200 px), aber nie so
    schmal, dass die Unterzeile unlesbar wird (mindestens 160 px)."""
    html = layout.compose("Angekommen – Danke für Ihre Anfrage", "y", FIRM, None).html
    row = html.split("<!--inhalt-->", 1)[0]
    head = row[row.index('dir="rtl"'):]
    head = head[:head.index("</table>")]
    assert head.index(layout.LOGO) < head.index("<h1") and head.count("<tr>") == 1
    assert ".ix-col{display:block!important" in html
    assert 160 <= layout.LOGO_W <= 200 and "ehemals HS Steiner" in layout.LOGO_ALT


def test_every_link_opens_a_new_window():
    """Ein Link der Mail öffnet ein neues Fenster – im Text, in der Unterschrift, im Streifen."""
    html = layout.compose("x", "Siehe https://inexxio.com/krantechnik", FIRM, None).html
    links = re.findall(r'<a [^>]*href="https?://[^"]*"[^>]*>', html)
    assert links and all('target="_blank"' in a for a in links), links


def test_what_is_done_in_the_erp_is_read_in_gmail_once(monkeypatch):
    """Beantwortet → «UNREAD» weg, genau einmal; Offenes bleibt ungelesen."""
    db = session()
    calls: list[list[str]] = []
    try:
        monkeypatch.setattr(mb, "company_address", lambda _db, _key: COMPANY)
        monkeypatch.setattr(mb, "_company_addresses", lambda _db: {COMPANY: 999999990})
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


def test_the_mail_is_one_centered_column_with_a_hairline():
    """Wie im Artefakt: 600 px, mittig, umrandet von einer Haarlinie – und dieselben
    Elemente tragen im dunklen Modus die dunkle Palette."""
    html = layout.compose("x", "y", FIRM, MONIKA).html
    assert 'align="center"' in html and "max-width:600px" in html
    assert f"border:1px solid {layout.LINE};border-radius:{layout.CARD_R}px" in html
    dark = html.split("prefers-color-scheme:dark", 1)[1]
    for cls in (".ix-bg", ".ix-ink", ".ix-line", ".ix-btn"):
        assert cls in dark
    assert 'class="ix-ink' in html and 'class="ix-bg' in html


def test_the_inquiry_subject_is_always_the_same_word():
    """Was jemand schreibt, steht nie im Betreff (Bug-Form: Spam schrieb ihn mit –
    «Anfrage: Hi, kam dashur të di çmimin tuaj»)."""
    from app.services import inquiry
    assert inquiry.SUBJECT == "Anfrage"
    assert not hasattr(inquiry, "subject_of")
