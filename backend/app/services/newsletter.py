"""►►► **Der Newsletter – Einwilligung, Bestätigung, Abmeldung** (``domain/newsletter``). ◄◄◄

* **Zustand** (``latest`` · ``subscribed``): die jüngste Zeile je Person – eine Ableitung,
  keine Spalte. Geschrieben wird nur über ``set_state`` (eine Zeile, wenn sich etwas
  ändert).
* **Bestätigen** (``invite``): eine Mail mit dem einen Knopf, über das Postfach einer
  eigenen Gesellschaft, als Nachricht im Verlauf der Person. Angemeldet ist erst, wer
  klickt (``confirm_url`` → ``routers/newsletter``).
* **Abmelden** (``unsubscribe_url``): ein Link ohne Ablauf, unerratbar (HMAC), in jedem
  Newsletter im Fuss und als ``List-Unsubscribe``-Kopf.

**Die Links tragen ihre Aussage selbst** (Person, Zweck, Quelle, Ablauf), signiert – es
gibt keine Tabelle offener Bitten. Der Schlüssel wird aus der Datenbankverbindung
abgeleitet: geheim, auf jeder Instanz gleich, und ohne eine zweite Einstellung, die
jemand setzen müsste. Wechselt das Datenbank-Passwort, gelten alte Links nicht mehr –
die Seite sagt es, und das Konto bleibt der Weg.

Die Wörter kommen von der Website (``website/src/config/newsletter.mjs`` →
``assets/website_contact.json``), damit Häkchen, Mail und Nachweis denselben Satz tragen.
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Iterable, Optional
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..domain import communication as dc
from ..domain import newsletter as dn
from ..models import Message, NewsletterConsent, UserProfile
from . import mail_layout
from .inquiry import VOCAB as _SITE

WORDS: dict[str, str] = _SITE["newsletter"]
#: Der Satz, dem zugestimmt wird – gespeichert mit jeder Anmeldung.
WORDING: str = WORDS["consent"]
API = "/api/v1/newsletter"


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
            .filter(NewsletterConsent.person_object_id.in_(ids),
                    NewsletterConsent.is_active.is_(True))
            .group_by(NewsletterConsent.person_object_id).subquery())
    rows = db.query(NewsletterConsent).join(last, NewsletterConsent.id == last.c.id).all()
    return {r.person_object_id: r for r in rows}


def subscribed(db: Session, oids: Iterable[int]) -> set[int]:
    """Wer von diesen heute angemeldet ist."""
    return {oid for oid, r in latest(db, oids).items() if r.subscribed}


def history(db: Session, oid: int) -> list[NewsletterConsent]:
    return (db.query(NewsletterConsent)
            .filter(NewsletterConsent.person_object_id == oid,
                    NewsletterConsent.is_active.is_(True))
            .order_by(NewsletterConsent.id.desc()).all())


def subscribers(db: Session) -> list[UserProfile]:
    """Alle, die heute angemeldet sind – die Empfänger eines Newsletters."""
    last = (db.query(func.max(NewsletterConsent.id))
            .filter(NewsletterConsent.is_active.is_(True))
            .group_by(NewsletterConsent.person_object_id))
    oids = [oid for (oid,) in db.query(NewsletterConsent.person_object_id).filter(
        NewsletterConsent.id.in_(last), NewsletterConsent.subscribed.is_(True)).all()]
    if not oids:
        return []
    return (db.query(UserProfile).filter(UserProfile.object_id.in_(oids))
            .order_by(UserProfile.last_name, UserProfile.first_name).all())


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
                             wording=WORDING if on else None, at=_now(),
                             created_by=actor_id))
    db.flush()
    return True


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

def _key() -> bytes:
    return hashlib.sha256(f"newsletter:{get_settings().database_url}".encode()).digest()


def sign(oid: int, purpose: str, source: str = "", days: Optional[int] = None) -> str:
    data = {"p": oid, "u": purpose, "s": source}
    if days:
        data["e"] = int(time.time()) + days * 86400
    raw = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()
                                   ).decode().rstrip("=")
    sig = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def read(token: str, purpose: str) -> tuple[int, str]:
    """(Person, Quelle) aus einem Link – oder ``ValueError`` mit dem Satz für die Seite."""
    raw, _, sig = (token or "").partition(".")
    good = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not raw or not hmac.compare_digest(sig, good):
        raise ValueError(WORDS["invalid"])
    data = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    if data.get("u") != purpose or ("e" in data and data["e"] < time.time()):
        raise ValueError(WORDS["invalid"])
    return int(data["p"]), str(data.get("s") or "")


def _url(path: str, token: str) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}{API}/{path}?t={quote(token)}"


def confirm_url(oid: int, source: str) -> str:
    return _url("confirm", sign(oid, "confirm", source, dn.CONFIRM_DAYS))


def unsubscribe_url(oid: int) -> str:
    return _url("unsubscribe", sign(oid, "unsubscribe"))


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
        url=confirm_url(oid, "inquiry"))


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


def invite(db: Session, oid: int, source: str, channel: Optional[str] = None) -> Message:
    """**Die Bitte um Bestätigung** – eine Mail an die Person, als Nachricht in ihrem
    Verlauf, unterschrieben vom Unternehmen. Committet und sendet.

    409, wenn sie schon angemeldet ist; 503 ohne verbundenes Postfach (eine Bitte, die nie
    hinausgeht, stünde als Lüge im Verlauf)."""
    from . import mailbox
    if oid in subscribed(db, [oid]):
        raise HTTPException(409, detail="Diese Person ist schon angemeldet.")
    channel = channel or sending_channel(db)
    box = mailbox.active(db, channel) if channel else None
    if box is None or box.problem:
        raise HTTPException(503, detail="Kein Postfach verbunden – die Bitte um Bestätigung "
                                        "kann nicht hinausgehen.")
    person = db.query(UserProfile).filter(UserProfile.object_id == oid).first()
    if person is None:
        raise HTTPException(404, detail=f"Person «{oid}» gibt es nicht.")
    firm = mail_layout.firm_of(mailbox.company(db, channel), box.address, box.picture or "")
    subject = WORDS["confirmSubject"]
    lead = f"Guten Tag {person.display_name}\n\n{WORDS['confirmLead']}"
    action = mail_layout.Action(title="", text="", label=WORDS["confirmButton"],
                                url=confirm_url(oid, source), note=WORDS["confirmIgnore"])
    mail = mail_layout.compose(subject, lead, firm, None, kicker=WORDS["kicker"],
                               extra=mail_layout.Extra(action=action))
    msg = Message(sender_object_id=box.owner_object_id, channel=channel, subject=subject,
                  body=mail.body, html=mail.html, at=_now(), created_by=None, outgoing=True)
    from .communication import write
    write(db, msg, {"to": [oid], "cc": [], "bcc": [], "about": []})
    db.commit()
    mailbox.send(db, msg)       # scheitert es, bleibt ``outgoing`` – der Abgleich holt nach
    db.commit()
    return msg
