"""►►► **Der Newsletter – Einwilligung, Bestätigung, Abmeldung** (``domain/newsletter``). ◄◄◄

* **Zustand** (``latest`` · ``subscribed``): die jüngste Zeile je Person – eine Ableitung,
  keine Spalte. Geschrieben wird nur über ``set_state`` (eine Zeile, wenn sich etwas
  ändert).
* **Bestätigen** (``invite``): eine Mail mit dem einen Knopf, über das Postfach einer
  eigenen Gesellschaft, als Nachricht im Verlauf der Person. Angemeldet ist erst, wer
  klickt (``confirm_url`` → ``routers/newsletter``).
* **Abmelden** (``unsubscribe_url``): ein Link ohne Ablauf, unerratbar (HMAC), in jedem
  Newsletter im Fuss und als ``List-Unsubscribe``-Kopf.

**Die Links tragen ihre Aussage selbst** (Person oder Adresse, Zweck, Quelle, Ablauf),
signiert an der einen Stelle ``core/signed`` – es gibt keine Tabelle offener Bitten. Eine
Anmeldung von der Website legt keine Person an: die Adresse steht im Link, die Person
entsteht mit dem Klick (``confirm``).

Die Wörter kommen von der Website (``website/src/config/newsletter.mjs`` →
``assets/website_contact.json``), damit Häkchen, Mail und Nachweis denselben Satz tragen.
"""

from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import quote

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import signed
from ..core.config import get_settings
from ..domain import communication as dc
from ..domain import newsletter as dn
from ..models import Message, NewsletterConsent, UserProfile
from . import mail_layout
from .inquiry import VOCAB as _SITE
from .people import is_email, normalize_email
from ..domain.errors import Conflict, NotFound, Unavailable
from ..core import clock

WORDS: dict[str, str] = _SITE["newsletter"]
#: Der Satz, dem zugestimmt wird – gespeichert mit jeder Anmeldung.
WORDING: str = WORDS["consent"]
API = "/api/v1/newsletter"



# ---------------------------------------------------------------------------
# Zustand
# ---------------------------------------------------------------------------

def latest(db: Session, oids: Iterable[int]) -> dict[int, NewsletterConsent]:
    """Je Person die jüngste Zeile – ihr heutiger Zustand. Keine Zeile = nie angemeldet."""
    ids = {i for i in oids if i}
    if not ids:
        return {}
    last = (db.query(NewsletterConsent.person_object_id,
                     func.max(NewsletterConsent.id).label("id"))
            .filter(NewsletterConsent.person_object_id.in_(ids))
            .group_by(NewsletterConsent.person_object_id).subquery())
    rows = db.query(NewsletterConsent).join(last, NewsletterConsent.id == last.c.id).all()
    return {r.person_object_id: r for r in rows}


def subscribed(db: Session, oids: Iterable[int]) -> set[int]:
    """Wer von diesen heute angemeldet ist."""
    return {oid for oid, r in latest(db, oids).items() if r.subscribed}


def history(db: Session, oid: int) -> list[NewsletterConsent]:
    return (db.query(NewsletterConsent)
            .filter(NewsletterConsent.person_object_id == oid)
            .order_by(NewsletterConsent.id.desc()).all())


def set_state(db: Session, oid: int, on: bool, source: str,
              actor_id: Optional[int] = None) -> bool:
    """**Die eine Schreibstelle.** Eine neue Zeile, wenn sich der Zustand ändert – sonst
    nichts (zweimal anmelden ist einmal angemeldet). Committet nicht."""
    if source not in dn.SOURCES:
        raise ValueError(f"Quelle «{source}» gibt es nicht.")
    now = latest(db, [oid]).get(oid)
    if (now.subscribed if now else False) == on:
        return False
    db.add(NewsletterConsent(person_object_id=oid, subscribed=on, source=source,
                             wording=WORDING if on else None, at=clock.utcnow(),
                             created_by=actor_id))
    db.flush()
    return True


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

@dataclass
class Link:
    """Was ein Newsletter-Link sagt: die Person – oder, bei einer Anmeldung von der Website,
    nur die Adresse (die Person entsteht erst mit dem Klick) – und die Quelle."""
    person: Optional[int]
    email: str
    source: str


def sign(purpose: str, *, person: Optional[int] = None, email: str = "", source: str = "",
         days: Optional[int] = None) -> str:
    payload: dict = {"p": person} if person else {"m": email}
    payload["s"] = source
    return signed.sign(payload, purpose, days * 86400 if days else None)


def read(token: str, purpose: str) -> Link:
    """Was ein Link sagt – oder ``ValueError`` mit dem Satz für die Seite."""
    try:
        data = signed.read(token, purpose)
        person = int(data["p"]) if data.get("p") else None
        email = normalize_email(str(data.get("m") or ""))
    except (signed.BadLink, TypeError, ValueError):
        raise ValueError(WORDS["invalid"])
    if person is None and not is_email(email):
        raise ValueError(WORDS["invalid"])
    return Link(person=person, email=email, source=str(data.get("s") or ""))


def _url(path: str, token: str) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}{API}/{path}?t={quote(token)}"


def confirm_url(source: str, *, person: Optional[int] = None, email: str = "") -> str:
    return _url("confirm", sign("confirm", person=person, email=email, source=source,
                                days=dn.CONFIRM_DAYS))


def unsubscribe_url(oid: int) -> str:
    return _url("unsubscribe", sign("unsubscribe", person=oid))


def confirm(db: Session, link: Link) -> int:
    """**Der Klick in der Bitte um Bestätigung** – angemeldet, mit Quelle und Wortlaut. Ohne
    Person (Anmeldung von der Website) entsteht sie erst jetzt (``people.ensure``). Gibt die
    Objektnummer zurück; committet nicht."""
    from . import people
    oid = link.person or people.ensure(db, link.email).object_id
    set_state(db, oid, True, link.source if link.source in dn.SOURCES else "website")
    return oid


def footer(oid: int) -> mail_layout.Unsubscribe:
    """Der Abmeldelink im Fuss eines Newsletters an diese Person."""
    return mail_layout.Unsubscribe(text=WORDS["footer"], label=WORDS["unsubscribe"],
                                   url=unsubscribe_url(oid))


# ---------------------------------------------------------------------------
# Einladen
# ---------------------------------------------------------------------------

def offer(db: Session, oid: int, asked: bool) -> Optional[mail_layout.Action]:
    """►►► **Der Knopf in der Eingangsbestätigung einer Anfrage.** ◄◄◄ Hat die Person das
    Häkchen gesetzt, ist er die Bestätigung; sonst eine leise Einladung – aber nie an
    jemanden, der schon angemeldet ist oder sich abgemeldet hat."""
    now = latest(db, [oid]).get(oid)
    if now is not None and (now.subscribed or not asked):
        return None
    return mail_layout.Action(
        title=WORDS["inviteTitle"], text=WORDS["inviteAsked" if asked else "inviteOffer"],
        label=WORDS["confirmButton" if asked else "inviteButton"],
        url=confirm_url("inquiry", person=oid))


def sending_channel(db: Session, country: Optional[str] = None) -> Optional[str]:
    """Das Postfach, über das eine Bitte um Bestätigung hinausgeht – die Gesellschaft zum
    Land (wie auf der Website), sonst der Betreiber. ``None`` = keines verbunden."""
    from . import mailbox, sites
    firm = sites.company_for_country(db, country) or sites.find_operator(db)
    if firm is None or not firm.object_id or not mailbox.ready():
        return None
    key = dc.company(firm.object_id)
    box = mailbox.active(db, key)
    return key if box is not None and not box.problem else None


def _box(db: Session, channel: Optional[str]):
    """Das Postfach, über das die Bitte hinausgeht – 503 ohne (eine Bitte, die nie
    hinausgeht, stünde als Lüge im Verlauf)."""
    from . import mailbox
    channel = channel or sending_channel(db)
    box = mailbox.active(db, channel) if channel else None
    if box is None or box.problem:
        raise Unavailable("Kein Postfach verbunden – die Bitte um Bestätigung "
                                        "kann nicht hinausgehen.")
    return channel, box


def _lead(name: str) -> str:
    return f"{dc.greeting(name).strip()}\n\n{WORDS['confirmLead']}"


def _ask(url: str) -> mail_layout.Extra:
    """Der eine Knopf der Bitte um Bestätigung."""
    return mail_layout.Extra(action=mail_layout.Action(
        title="", text="", label=WORDS["confirmButton"], url=url, note=WORDS["confirmIgnore"]))


def invite(db: Session, oid: int, source: str, channel: Optional[str] = None, *,
           by_name: bool = True) -> Message:
    """**Die Bitte um Bestätigung** – eine Mail an die Person, als Nachricht in ihrem
    Verlauf, unterschrieben vom Unternehmen. Committet und sendet. 409, wenn sie schon
    angemeldet ist; 503 ohne verbundenes Postfach. Von der Website (``by_name=False``) ohne
    Namen in der Anrede: der Name stammt womöglich aus einem öffentlichen Formular."""
    from . import outbox
    if oid in subscribed(db, [oid]):
        raise Conflict("Diese Person ist schon angemeldet.")
    channel, _ = _box(db, channel)
    person = db.query(UserProfile).filter(UserProfile.object_id == oid).first()
    if person is None:
        raise NotFound(f"Person «{oid}» gibt es nicht.")
    return outbox.deliver(db, channel=channel, to=[oid], subject=WORDS["confirmSubject"],
                          lead=_lead(person.display_name if by_name else ""),
                          kicker=WORDS["kicker"], extra=_ask(confirm_url(source, person=oid)))


def invite_address(db: Session, email: str, source: str, channel: Optional[str] = None) -> None:
    """**Die Bitte an eine Adresse, zu der es noch keine Person gibt** (Anmeldung von der
    Website). Angelegt wird nichts: die Adresse steht im signierten Link, die Person entsteht
    erst mit dem Klick (``confirm``). Ohne Person gibt es keinen Verlauf – die Mail geht
    direkt hinaus; 503, wenn das nicht geht."""
    from . import mailbox, outbox
    channel, _ = _box(db, channel)
    mail = mail_layout.compose(WORDS["confirmSubject"], _lead(""), outbox.firm(db, channel),
                               None, kicker=WORDS["kicker"],
                               extra=_ask(confirm_url(source, email=email)))
    if not mailbox.send_direct(db, channel, email, WORDS["confirmSubject"], mail):
        raise Unavailable("Die Bitte um Bestätigung ging nicht hinaus.")
