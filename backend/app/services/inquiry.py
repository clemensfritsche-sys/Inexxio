"""►►► **Eine Anfrage der Website ist eine Nachricht im ERP** (CRM Schritt 3). ◄◄◄

Kein eigener Posteingang, keine zweite Liste: die Anfrage landet dort, wo jede andere
Nachricht landet – im Verlauf der anfragenden Person, **offen**, mit der Zahl am Symbol im
Feed. Drei Regeln, und jede steht schon woanders:

* **Welche Gesellschaft?** Dieselbe, die die Website dem Besucher zeigt
  (``sites.company_for_country`` – Land ≻ Region ≻ Betreiber). Ihr Postfach ist der Kanal.
* **Wer fragt?** Die Person zu dieser E-Mail – angelegt, wenn es sie nicht gibt
  (``people.ensure``, dieselbe Stelle wie bei einer eingehenden Mail; ein Telefon aus dem
  Formular nur bei einer neuen Person).
* **Die Bestätigung beantwortet nichts.** Sie geht über das Postfach der Gesellschaft
  hinaus und steht im Verlauf – aber unter **eigenem Betreff** (``confirmSubject`` ≠
  ``SUBJECT``): sie ist ein anderes Anliegen, die Anfrage bleibt offen, bis ein Mensch
  antwortet. Sonst hebelte die Bestätigung das 2-Stunden-Ziel aus.

**Die Anfrage ist gespeichert, bevor irgendetwas hinausgeht**: scheitert danach die
Bestätigung, bleibt sie als «muss noch hinaus» stehen und geht beim nächsten Abgleich.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..core import clock
from . import phone as tel
from ..domain import communication as dc
from ..models import Message
from . import attachments, mail_layout, mailbox, outbox, people, sites
from .communication import write

#: Das Vokabular der Website (``website/src/config``, generiert von
#: ``website/scripts/export-erp.mjs`` – die CI prüft, dass es aktuell ist). EINE Stelle liest
#: es; der Endpunkt (``routers/contact``) nimmt es von hier.
VOCAB: dict = json.loads(
    (Path(__file__).resolve().parent.parent / "assets" / "website_contact.json").read_text("utf-8")
)
#: Der Betreff der Anfrage im ERP: das Stichwort und, worum es geht – der Anfang der
#: Nachricht. Sie selbst ist die beste Überschrift, und im Verlauf liest man sie sofort.
#: Dieselbe Regel steht für den mailto-Ausweg in ``website/src/lib/inquiry-subject.mjs``.
SUBJECT: str = VOCAB["subject"]["word"]
SUMMARY_MAX: int = VOCAB["subject"]["max"]
#: Die Beschriftungen der Felder – dieselben wie im Formular und im mailto-Ausweg.
LABELS: dict[str, str] = dict(VOCAB["labels"])


#: Was das Formular prüft – dieselben Grenzen und Wörter wie im Browser.
MSG: dict[str, str] = VOCAB["messages"]
LIMITS: dict[str, int] = VOCAB["limits"]
PHOTOS: dict = VOCAB["photos"]
#: Derselbe Ausdruck wie im Browser (``website/src/config/inquiry.mjs`` → ``patterns``); die
#: E-Mail-Regel ist ``people.is_email``.
PHONE_RE = re.compile(VOCAB["patterns"]["phone"])
SOURCE_RE = re.compile(r"^/[a-z0-9/_-]{0,80}$")

#: Die Sprachen der Website (``website/src/config/languages.mjs``): Deutsch und je eine Übersetzung
#: der Wörter des Servers in ``VOCAB["languages"]`` (WEBSITE_PLAN Entscheid 136).
LANGS: tuple[str, ...] = ("de", *VOCAB.get("languages", {}))
#: Was der Server in einer Sprache sagt – je Bereich das Deutsche, darüber die Übersetzung.
WORD_PARTS = ("pages", "messages", "server", "mail", "letter", "newsletter")


def hello(name: str, lang: str = "de") -> str:
    """Die Anrede einer Mail in der Sprache – auf Deutsch die eine des ERP (``communication.greeting``)."""
    if lang_of(lang) == "de":
        return dc.greeting(name)
    return f"{words(lang)['server']['hello']} {name}".strip()


def lang_of(raw: object) -> str:
    """Die Sprache der Seite, von der etwas kam (``?lang=``) – Unbekanntes ist Deutsch."""
    return raw if isinstance(raw, str) and raw in LANGS else "de"


def words(lang: str) -> dict:
    """Die Wörter des Servers in einer Sprache: Meldungen, Antwortseiten, Bestätigung, Newsletter
    (mit dem Wortlaut der Einwilligung) und die Seiten der Website, auf die er führt."""
    over = VOCAB.get("languages", {}).get(lang_of(lang), {})
    return {part: {**VOCAB[part], **over.get(part, {})} for part in WORD_PARTS}
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
FIELDS = ("message", "name", "company", "phone", "email")


@dataclass
class Photo:
    filename: str
    data: bytes


@dataclass
class Inquiry:
    """►► Die EINE Form einer Anfrage – vom Formular bis zur Nachricht. ◄◄"""
    name: str
    email: str
    message: str
    phone: str = ""
    company: str = ""
    source: str = "/kontakt"
    photos: list[Photo] = field(default_factory=list)
    #: Das Häkchen «Post von INEXXIO» – eine Bitte, noch keine Anmeldung: angemeldet
    #: ist erst, wer in der Eingangsbestätigung klickt (Double Opt-in).
    newsletter: bool = False
    #: Die Sprache der Seite – in ihr antworten Meldungen und Bestätigung (``words``).
    lang: str = "de"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    received_at: datetime = field(default_factory=lambda: clock.utcnow())

    @property
    def values(self) -> dict[str, str]:
        """Die Felder des Formulars, wie es sie nennt."""
        return {name: getattr(self, name) for name in FIELDS}


# ─── Einlesen und Prüfen (rein: Text und Bytes hinein, Anfrage und Fehler hinaus) ─────────

def clean(raw: object, multiline: bool = False) -> str:
    """Text bereinigen: Steuerzeichen weg, Zeilenenden vereinheitlicht, einzeilige Felder
    ohne Umbruch (sie landen im Betreff einer E-Mail)."""
    text = raw if isinstance(raw, str) else ""
    text = CONTROL_RE.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    if not multiline:
        text = " ".join(text.split())
    return text.strip()


def _check_fields(values: dict[str, str], errors: dict[str, str], msg: dict[str, str] = MSG) -> None:
    for name, limit in LIMITS.items():
        if name in values and len(values[name]) > limit:
            errors.setdefault(name, msg["tooLong"].replace("{max}", str(limit)))
    if not values["message"]:
        errors.setdefault("message", msg["message"])
    if not values["name"]:
        errors.setdefault("name", msg["name"])
    phone, email = values["phone"], values["email"]
    # Die E-Mail ist Pflicht: über sie wird die Person gefunden (oder angelegt), und
    # dorthin gehen Bestätigung und Antwort. Das Telefon ist freiwillig.
    if not email:
        errors.setdefault("email", msg["emailMissing"])
    if phone and not PHONE_RE.match(phone):
        errors.setdefault("phone", msg["phone"])
    if email and not people.is_email(email):
        errors.setdefault("email", msg["email"])


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB".replace(".", ",")


def _photos(files: list[tuple[str, bytes]], errors: dict[str, str], msg: dict[str, str] = MSG) -> list[Photo]:
    """Die Fotos (Name, Bytes) – Anzahl, Endung und Gesamtgrösse wie im Browser."""
    if len(files) > int(PHOTOS["max"]):
        errors["photos"] = msg["photosCount"].replace("{max}", str(PHOTOS["max"])).replace("{count}", str(len(files)))
        return []
    photos: list[Photo] = []
    for given, data in files:
        name = Path(given or "foto").name
        ext = Path(name).suffix.lower()
        if ext not in PHOTOS["extensions"]:
            errors["photos"] = msg["photosType"].replace("{name}", name[:80])
            return []
        safe = re.sub(r"[^\w.\-]+", "_", name)[-80:] or f"foto{ext}"
        photos.append(Photo(filename=safe, data=data))
    total = sum(len(p.data) for p in photos)
    if total > int(PHOTOS["maxTotalBytes"]):
        errors["photos"] = msg["photosSize"].replace("{size}", mb(total)).replace("{max}", mb(int(PHOTOS["maxTotalBytes"])))
        return []
    return photos


def read(form: dict[str, object], files: list[tuple[str, bytes]],
         lang: str = "de") -> tuple[Inquiry, dict[str, str]]:
    """►► Das Formular als Anfrage – und was daran fehlt (Feld → Satz in der Sprache der Seite;
    leer = gut). ◄◄"""
    lang = lang_of(lang)
    msg = words(lang)["messages"]
    errors: dict[str, str] = {}
    values = {name: clean(form.get(name), multiline=(name == "message")) for name in FIELDS}
    _check_fields(values, errors, msg)
    photos = _photos(files, errors, msg)
    source = clean(form.get("source")).lower()
    inq = Inquiry(name=values["name"], email=values["email"].lower(), message=values["message"],
                  phone=tel.tidy(values["phone"]) or "", company=values["company"],
                  source=source if SOURCE_RE.match(source) else "/kontakt",
                  photos=photos, newsletter=bool(clean(form.get("newsletter"))), lang=lang)
    return inq, errors


def company_for(db: Session, country: Optional[str]):
    """Die eigene Gesellschaft, an die diese Anfrage geht – wie auf der Website."""
    firm = sites.company_for_country(db, country) or sites.find_operator(db)
    if firm is None or not firm.object_id:
        raise RuntimeError("Es gibt keine eigene Gesellschaft, die Anfragen entgegennimmt.")
    return firm


def subject_of(message: str) -> str:
    """«Anfrage: Kran läuft beim Anfahren ruckartig» – der erste Satz, gekappt am Wort.

    Die Bestätigung trägt bewusst einen **anderen** Betreff (``confirmSubject``): ein
    gleicher erledigte die Anfrage, bevor ein Mensch sie gelesen hat."""
    first = next((ln.strip() for ln in (message or "").splitlines() if ln.strip()), "")
    first = re.split(r"(?<=[.!?])\s", " ".join(first.split()), maxsplit=1)[0].rstrip(".")
    if len(first) > SUMMARY_MAX:
        cut = first[:SUMMARY_MAX + 1].rsplit(" ", 1)[0] or first[:SUMMARY_MAX]
        first = cut.rstrip(",;:–- ") + " …"
    return f"{SUBJECT}: {first}" if first else SUBJECT


def _body(inq: Inquiry) -> str:
    facts = [(LABELS["company"], inq.company), (LABELS["phone"], inq.phone),
             (VOCAB["sourceLabel"], inq.source)]
    lines = [f"{label}: {value}" for label, value in facts if value]
    return inq.message.strip() + ("\n\n" + "\n".join(lines) if lines else "")


def record(db: Session, inq: Inquiry, country: Optional[str]) -> Message:
    """Die Anfrage festhalten – gespeichert mit der Anfrage, bevor irgendetwas hinausgeht
    (die Bestätigung geht erst danach, ``mailbox.send_after``).

    Ein Foto, das sich nicht lesen lässt, wirft (``attachments.store_image``: 400/413);
    dann ist nichts gespeichert, und der Aufrufer sagt es am Feld."""
    firm = company_for(db, country)
    person = people.ensure(db, inq.email, inq.name, inq.phone, language=inq.lang).object_id
    files = []
    for p in inq.photos:
        att = attachments.store_image(db, p.data, p.filename)
        files.append({"name": p.filename, "size": len(p.data), "mime": att.mime,
                      "url": attachments.public_url(att)})
    msg = Message(sender_object_id=person, channel=dc.company(firm.object_id),
                  subject=subject_of(inq.message), body=_body(inq), at=clock.utcnow(),
                  created_by=None, attachments=files or None, inbound=True)
    write(db, msg, {"to": [], "cc": [], "bcc": [], "about": []})
    db.flush()
    return msg


def confirm(db: Session, inquiry: Message, inq: Inquiry, words: dict[str, str]) -> bool:
    """Die Bestätigung an die anfragende Person – über das Postfach der Gesellschaft, als
    Nachricht im Verlauf, unter eigenem Betreff (sie erledigt die Anfrage nicht). Ohne
    verbundenes Postfach gibt es keine (``False``): eine Bestätigung, die nie hinausgeht,
    stünde als Lüge im Verlauf.

    **Gebaut an EINER Stelle** (``outbox.deliver``): der Verlauf ist der Inhalt der
    Mail, Wort für Wort. Unterschrieben vom Unternehmen – geschrieben hat sie niemand.

    **Darin der Newsletter** (``newsletter.offer``): nur mit Häkchen, als Bitte um
    Bestätigung – ohne Häkchen keine Einladung, nie an Angemeldete."""
    from .newsletter import offer
    box = mailbox.active(db, inquiry.channel)
    if box is None or box.problem:
        return False
    more = mail_layout.Extra(call=words["urgent"])
    more.action = offer(db, inquiry.sender_object_id, inq.newsletter, inq.lang)
    outbox.deliver(db, channel=inquiry.channel, to=[inquiry.sender_object_id],
                   subject=words["confirmSubject"], lead=lead(words, inq.lang, inq.name),
                   extra=more, lang=inq.lang)
    return True


#: ►►► **Ein Name, der wie ein Name aussieht** – nur dann steht er in der Anrede. ◄◄◄ Das Formular
#: kann jeder mit einer fremden Adresse ausfüllen; ins Namensfeld gehört dann kein beliebiger Text
#: (Link, Werbung, Satz), den wir in unserem Namen an diese Adresse schicken. Buchstaben,
#: Bindestrich und Apostroph, höchstens vier Wörter und 40 Zeichen.
NAME_WORDS, NAME_MAX = 4, 40
_NAME = re.compile(r"^[^\W\d_]+(?:['’-][^\W\d_]+)*$")


def salutation_name(name: str) -> str:
    """Der Name für die Anrede – oder leer, wenn er nicht wie ein Name aussieht."""
    parts = (name or "").split()
    if not parts or len(parts) > NAME_WORDS or len(" ".join(parts)) > NAME_MAX:
        return ""
    return " ".join(parts) if all(_NAME.match(p) for p in parts) else ""


def lead(words: dict[str, str], lang: str = "de", name: str = "") -> str:
    """Der Anfang der Bestätigung – mit dem Namen aus dem Formular nur, wenn er wie ein Name
    aussieht (``salutation_name``)."""
    return (f"{hello(salutation_name(name), lang).strip()}\n\n{words['confirmIntro']}\n\n"
            f"{words['confirmMore']}")
