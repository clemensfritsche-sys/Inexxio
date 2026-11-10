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


def _check_fields(values: dict[str, str], errors: dict[str, str]) -> None:
    for name, limit in LIMITS.items():
        if name in values and len(values[name]) > limit:
            errors.setdefault(name, MSG["tooLong"].replace("{max}", str(limit)))
    if not values["message"]:
        errors.setdefault("message", MSG["message"])
    if not values["name"]:
        errors.setdefault("name", MSG["name"])
    phone, email = values["phone"], values["email"]
    # Die E-Mail ist Pflicht: über sie wird die Person gefunden (oder angelegt), und
    # dorthin gehen Bestätigung und Antwort. Das Telefon ist freiwillig.
    if not email:
        errors.setdefault("email", MSG["emailMissing"])
    if phone and not PHONE_RE.match(phone):
        errors.setdefault("phone", MSG["phone"])
    if email and not people.is_email(email):
        errors.setdefault("email", MSG["email"])


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB".replace(".", ",")


def _photos(files: list[tuple[str, bytes]], errors: dict[str, str]) -> list[Photo]:
    """Die Fotos (Name, Bytes) – Anzahl, Endung und Gesamtgrösse wie im Browser."""
    if len(files) > int(PHOTOS["max"]):
        errors["photos"] = MSG["photosCount"].replace("{max}", str(PHOTOS["max"])).replace("{count}", str(len(files)))
        return []
    photos: list[Photo] = []
    for given, data in files:
        name = Path(given or "foto").name
        ext = Path(name).suffix.lower()
        if ext not in PHOTOS["extensions"]:
            errors["photos"] = MSG["photosType"].replace("{name}", name[:80])
            return []
        safe = re.sub(r"[^\w.\-]+", "_", name)[-80:] or f"foto{ext}"
        photos.append(Photo(filename=safe, data=data))
    total = sum(len(p.data) for p in photos)
    if total > int(PHOTOS["maxTotalBytes"]):
        errors["photos"] = MSG["photosSize"].replace("{size}", mb(total)).replace("{max}", mb(int(PHOTOS["maxTotalBytes"])))
        return []
    return photos


def read(form: dict[str, object], files: list[tuple[str, bytes]]) -> tuple[Inquiry, dict[str, str]]:
    """►► Das Formular als Anfrage – und was daran fehlt (Feld → Satz; leer = gut). ◄◄"""
    errors: dict[str, str] = {}
    values = {name: clean(form.get(name), multiline=(name == "message")) for name in FIELDS}
    _check_fields(values, errors)
    photos = _photos(files, errors)
    source = clean(form.get("source")).lower()
    inq = Inquiry(name=values["name"], email=values["email"].lower(), message=values["message"],
                  phone=values["phone"], company=values["company"],
                  source=source if SOURCE_RE.match(source) else "/kontakt",
                  photos=photos, newsletter=bool(clean(form.get("newsletter"))))
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
    person = people.ensure(db, inq.email, inq.name, inq.phone).object_id
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

    **Darin der Newsletter** (``newsletter.offer``): mit Häkchen die Bitte um Bestätigung,
    ohne eine leise Einladung – nie an Angemeldete oder Abgemeldete."""
    from .newsletter import offer
    box = mailbox.active(db, inquiry.channel)
    if box is None or box.problem:
        return False
    more = extra(inq, inquiry.at, words)
    more.action = offer(db, inquiry.sender_object_id, inq.newsletter)
    outbox.deliver(db, channel=inquiry.channel, to=[inquiry.sender_object_id],
                   subject=words["confirmSubject"], lead=lead(words),
                   kicker=words["kicker"], extra=more)
    return True


def lead(words: dict[str, str]) -> str:
    """Der Anfang der Bestätigung – **ohne den Namen aus dem Formular**: wer eine fremde
    Adresse eintippt, soll durch uns keinen Text an sie schicken können."""
    return f"{dc.greeting('').strip()}\n\n{words['confirmIntro']}\n\n{words['confirmMore']}"


def extra(inq: Inquiry, at: datetime, words: dict[str, str]) -> mail_layout.Extra:
    """Was die Bestätigung **allgemeingültig** trägt – nie, was in der Anfrage steht (kein
    Text, keine Firma, kein Telefon: die Bestätigung ist kein Relais für fremden Inhalt):
    wie viele Fotos angekommen sind, was als Nächstes geschieht, und der Weg, wenn es eilt."""
    n = len(inq.photos)
    photos = (words["photoOne"] if n == 1 else words["photoMany"].replace("{n}", str(n)))
    when = at.astimezone(clock.ZONE).strftime("%-d.%-m.%Y, %H:%M")
    return mail_layout.Extra(
        facts=mail_layout.Facts(title=words["copyTitle"], rows=[(words["factPhotos"], photos)])
        if n else None,
        steps=mail_layout.Steps(title=words["nextTitle"], items=[
            (f"{words['received']} · {when}", True), (words["confirmNext"], False)]),
        call=words["urgent"])
