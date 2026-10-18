"""►►► **Eine Anfrage der Website ist eine Nachricht im ERP** (CRM Schritt 3). ◄◄◄

Kein eigener Posteingang, keine zweite Liste: die Anfrage landet dort, wo jede andere
Nachricht landet – im Verlauf der anfragenden Person, **offen**, mit der Zahl am Symbol im
Feed. Drei Regeln, und jede steht schon woanders:

* **Welche Gesellschaft?** Dieselbe, die die Website dem Besucher zeigt
  (``sites.company_for_country`` – Land ≻ Region ≻ Betreiber). Ihr Postfach ist der Kanal.
* **Wer fragt?** Die Person zu dieser E-Mail – angelegt, wenn es sie nicht gibt
  (``mailbox.person_for``, dieselbe Stelle wie bei einer eingehenden Mail).
* **Die Bestätigung beantwortet nichts.** Sie geht über das Postfach der Gesellschaft
  hinaus und steht im Verlauf – aber unter **eigenem Betreff** (``confirmSubject`` ≠
  ``SUBJECT``): sie ist ein anderes Anliegen, die Anfrage bleibt offen, bis ein Mensch
  antwortet. Sonst hebelte die Bestätigung das 2-Stunden-Ziel aus.

**Die Anfrage ist gespeichert, bevor irgendetwas hinausgeht**: scheitert danach die
Bestätigung, bleibt sie als «muss noch hinaus» stehen und geht beim nächsten Abgleich.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..domain import communication as dc
from ..models import Message
from . import attachments, mailbox, sites
from .communication import write

SUBJECT = "Anfrage über die Website"


@dataclass
class Photo:
    filename: str
    data: bytes


@dataclass
class Inquiry:
    name: str
    email: str
    message: str
    phone: str = ""
    company: str = ""
    source: str = "/kontakt"
    photos: list[Photo] = field(default_factory=list)


def company_for(db: Session, country: Optional[str]):
    """Die eigene Gesellschaft, an die diese Anfrage geht – wie auf der Website."""
    firm = sites.company_for_country(db, country) or sites.find_operator(db)
    if firm is None or not firm.object_id:
        raise RuntimeError("Es gibt keine eigene Gesellschaft, die Anfragen entgegennimmt.")
    return firm


def _body(inq: Inquiry) -> str:
    facts = [("Firma", inq.company), ("Telefon", inq.phone), ("Seite", inq.source)]
    lines = [f"{label}: {value}" for label, value in facts if value]
    return inq.message.strip() + ("\n\n" + "\n".join(lines) if lines else "")


def record(db: Session, inq: Inquiry, country: Optional[str]) -> Message:
    """Die Anfrage festhalten – **committet**, bevor irgendetwas hinausgeht.

    Ein Foto, das sich nicht lesen lässt, wirft (``attachments.store_image``: 400/413);
    dann ist nichts gespeichert, und der Aufrufer sagt es am Feld."""
    firm = company_for(db, country)
    person = mailbox.person_for(db, inq.name, inq.email, inq.phone)
    files = []
    for p in inq.photos:
        att = attachments.store_image(db, p.data, p.filename, None)
        files.append({"name": p.filename, "size": len(p.data),
                      "url": attachments.public_url(att)})
    msg = Message(sender_object_id=person, channel=dc.company(firm.object_id),
                  subject=SUBJECT, body=_body(inq), at=datetime.now(timezone.utc),
                  created_by=None, attachments=files or None)
    write(db, msg, {"to": [], "cc": [], "bcc": [], "about": []})
    db.commit()
    return msg


def confirm(db: Session, inquiry: Message, text: str, subject: str) -> bool:
    """Die Bestätigung an die anfragende Person – über das Postfach der Gesellschaft, als
    Nachricht im Verlauf, unter eigenem Betreff (sie erledigt die Anfrage nicht). Ohne verbundenes Postfach gibt es keine
    (``False``): eine Bestätigung, die nie hinausgeht, stünde als Lüge im Verlauf."""
    box = mailbox.active(db, inquiry.channel)
    if not mailbox.ready() or box is None or box.problem:
        return False
    msg = Message(sender_object_id=box.owner_object_id, channel=inquiry.channel,
                  subject=subject, body=text, at=datetime.now(timezone.utc),
                  created_by=None, outgoing=True)
    write(db, msg, {"to": [inquiry.sender_object_id], "cc": [], "bcc": [], "about": []})
    db.commit()
    mailbox.send(db, msg)       # scheitert es, bleibt ``outgoing`` – der Abgleich holt nach
    db.commit()
    return True


def confirmation_text(db: Session, inquiry: Message, name: str, intro: str, nxt: str,
                      closing: str) -> str:
    """Der Text der Bestätigung – Absender ist die Gesellschaft, an die sie ging."""
    from . import address as addr
    firm = mailbox.company(db, inquiry.channel)
    sign = [sites.legal_name(firm)] if firm else []
    if firm is not None:
        sign += [line for line in addr.lines(addr.of_company(firm)) if line.strip("— ")]
        sign += [f"Telefon {firm.phone}"] if firm.phone else []
        sign += [firm.email] if firm.email else []
    return "\n".join([f"Guten Tag {name}", "", intro, "", inquiry.body, "", nxt, "",
                      closing, *sign])
