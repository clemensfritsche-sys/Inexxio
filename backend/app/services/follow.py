"""►►► **Was aus einer eingehenden Mail folgt** (Projektakte §4.3, Bauplan «Der Takt»). ◄◄◄

Die Kundin schreibt, unten in der Signatur steht eine neue Telefonnummer – die KI bereitet einen
**Handgriff** vor (``ai.converse``, Aufgabe ``follow``, im Takt). Geprüft wird nur, was:

* **von aussen an uns** kam (abgeglichen aus dem Postfach einer eigenen Gesellschaft),
* **von einer bekannten Person** (die es schon gab, als die Mail ankam – ein neuer Absender
  entsteht erst beim Abgleich aus der Mail; Massenpost legt der Abgleich gar nicht erst an),
* **nach der Einführung** – der Startpunkt ist ein Ereignis (``follow.start``, die höchste
  Nachrichtennummer beim ersten Lauf), keine Spalte; ältere Mails bleiben, wie sie sind,
* **je Mail einmal** – Ereignis ``mail.followed`` (mit der Nummer der Nachricht), geschrieben
  bei Erfolg oder nach dem ``TRIES``-ten Fehlschlag; ein vorübergehender Fehler (529, Netz,
  Zeitgrenze) zählt als ``mail.follow_failed`` und die Mail kommt im nächsten Takt wieder. Am
  Deckel kein Versuch und kein Zählen.

Ergebnis sind Handgriffe mit der Mail als Quelle (``services/handgriff``, Probelauf mit den
Rechten der Person, die das Postfach verbunden hat). Sie stehen am Datensatz und zählen dort in
«zu tun»; ausgeführt wird erst, wenn ein Mensch es tippt. Gelesen wird, was jedes Personal sehen
darf (``ai_tools.reader``).
"""

from __future__ import annotations

import time
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Message, UserProfile
from . import ai, handgriff, log

#: So viele Mails je Lauf des Takts.
PER_RUN = 5
#: So oft wird eine Mail höchstens versucht – danach gilt sie als geprüft (mit dem Grund).
TRIES = 3


class FollowAnswer(BaseModel):
    note: str = Field(description="Ein Satz für das Protokoll: was du vorbereitet hast, oder «nichts»")


FOLLOW_FORMAT = """
Eine Mail ist eingegangen. Was folgt daraus im ERP (eine neue Telefonnummer aus der Signatur,
eine Bestellung, ein Termin, Wissen zu einem Datensatz)? Bereite es mit `vorbereiten` vor – je
Handlung ein Handgriff am richtigen Datensatz; ein Mensch entscheidet. Folgt nichts, bereite
nichts vor. Antwortformat: `note` – ein Satz, was du vorbereitet hast.
"""
def start(db: Session) -> Optional[int]:
    """Die höchste Nachrichtennummer bei der Einführung – ``None`` vor dem ersten Lauf."""
    v = db.execute(text("SELECT (payload ->> 'after')::bigint FROM log WHERE event = "
                        "'follow.start' ORDER BY id LIMIT 1")).scalar()
    return None if v is None else int(v)


def begin(db: Session) -> int:
    """Der erste Lauf: den Startpunkt festhalten (ältere Mails bleiben, wie sie sind)."""
    after = int(db.execute(text("SELECT coalesce(max(id), 0) FROM messages")).scalar() or 0)
    log.event(db, "follow.start", None, {"after": after})
    return after


_CANDIDATES = text("""
SELECT m.id FROM messages m
  JOIN user_profiles u ON u.object_id = m.sender_object_id
 WHERE m.id > :after AND m.is_active AND m.created_by IS NULL AND m.gmail_id IS NOT NULL
   AND m.channel ~ '^c[0-9]+$' AND NOT m.outgoing
   AND u.role <> ALL(:staff) AND u.is_active AND u.created_at < m.at
   AND NOT EXISTS (SELECT 1 FROM log l WHERE l.event = 'mail.followed'
                     AND l.object_id = m.sender_object_id
                     AND (l.payload ->> 'message')::bigint = m.id)
 ORDER BY m.id LIMIT :n""")


def due(db: Session, limit: int = PER_RUN) -> list[int]:
    """Die Mails, die noch auf ihre Folgen warten – die ältesten zuerst."""
    after = start(db)
    if after is None:
        begin(db)
        return []
    from .people import STAFF_ROLES
    return [r.id for r in db.execute(_CANDIDATES, {"after": after, "n": limit,
                                                   "staff": list(STAFF_ROLES)})]


def _reader(db: Session, msg: Message) -> Optional[UserProfile]:
    """In wessen Namen gelesen wird: wer das Postfach verbunden hat (Personal)."""
    from . import mailbox
    from .people import STAFF_ROLES
    mb = mailbox.active(db, msg.channel)
    if mb is None:
        return None
    person = db.query(UserProfile).filter(UserProfile.object_id == mb.owner_object_id).first()
    return person if person is not None and person.role in STAFF_ROLES else None


def _content(db: Session, msg: Message, sender: UserProfile, reader: UserProfile
             ) -> list[dict[str, Any]]:
    from . import memory
    body = f"Betreff: {msg.subject or ''}\n\n{msg.body or ''}"
    cases = memory.as_prompt(memory.search(db, body, actor=reader, kinds=("handgriff",)))
    head = (f"Eine Mail an uns von {sender.display_name} ({sender.object_id}), "
            f"am {msg.at.isoformat(timespec='minutes')}.")
    return [{"type": "text", "text": head + ("\n\n" + cases if cases else "") + "\n\n" + body}]


def _tools(db: Session, msg: Message, sender: UserProfile, reader: UserProfile) -> list[ai.Tool]:
    """Lesen, nachschlagen, vorbereiten – ohne Weglegen und Ausführen: aus einer Mail wird nur
    vorbereitet (die Handgriffe stehen am Datensatz, wer ihn öffnet, entscheidet)."""
    from . import talk
    keep = ("find", "record", "history", "wissen", "handlungen", "handlung")
    tools = [t for t in talk.tools(db, reader, 0, sender.object_id) if t.name in keep]

    def prepare(a: dict[str, Any]) -> str:
        import json
        method, _, path = str(a.get("handlung") or "").partition(" ")
        try:
            body = json.loads(a.get("werte_json") or "null")
        except ValueError as exc:
            return f"Die Werte sind kein JSON: {exc}"
        hid, out = handgriff.prepare(db, reader, method=method, path=str(a.get("pfad") or path),
                                     body=body, line=str(a.get("zeile") or ""),
                                     home=sender.object_id, mail=msg.id,
                                     depends=list(a.get("wartet_auf") or []))
        return f"Vorbereitet als Handgriff {hid}." if hid else f"Geht nicht ({out.status}): {out.detail}"
    spec = next(t for t in talk.tools(db, reader, 0, sender.object_id) if t.name == "vorbereiten")
    return [*tools, ai.Tool(spec.name, spec.description, spec.properties, prepare)]


def failures(db: Session, message_id: int) -> int:
    """Wie oft das Prüfen dieser Mail schon scheiterte (``mail.follow_failed``)."""
    return int(db.execute(text(
        "SELECT count(*) FROM log WHERE event = 'mail.follow_failed' "
        "AND (payload ->> 'message')::bigint = :m"), {"m": message_id}).scalar() or 0)


def follow_one(db: Session, message_id: int) -> Optional[int]:
    """►►► **Eine Mail auf ihre Folgen prüfen** – gibt die Zahl der Handgriffe zurück, oder
    ``None``, wenn die KI gerade nicht da ist (dann kommt die Mail im nächsten Lauf wieder). Ein
    Fehlschlag zählt; erst der ``TRIES``-te schliesst die Mail ab. ◄◄◄"""
    msg = db.get(Message, message_id)
    sender = db.query(UserProfile).filter(UserProfile.object_id == msg.sender_object_id).first()
    reader = _reader(db, msg)
    if reader is None or sender is None:
        log.event(db, "mail.followed", msg.sender_object_id,
                  {"message": msg.id, "problem": "Kein Personal an diesem Postfach."})
        return 0
    if not ai.available(db):
        return None
    from .talk import AUFTRAG
    before = _made(db, msg.id)
    answer = ai.converse(db, task="follow", actor=reader, system=AUFTRAG + "\n" + FOLLOW_FORMAT,
                         content=_content(db, msg, sender, reader), schema=FollowAnswer,
                         tools=_tools(db, msg, sender, reader))
    if answer is None:
        if not ai.available(db):
            return None
        trouble = ai.problem() or "Die KI hat nichts geliefert."
        log.event(db, "mail.follow_failed", sender.object_id, {"message": msg.id, "problem": trouble})
        if failures(db, msg.id) < TRIES:
            return 0
        log.event(db, "mail.followed", sender.object_id, {"message": msg.id, "handgriffe": 0,
                                                          "problem": trouble})
        return 0
    made = _made(db, msg.id) - before
    log.event(db, "mail.followed", sender.object_id, {"message": msg.id, "handgriffe": made})
    return made


def _made(db: Session, message_id: int) -> int:
    return int(db.execute(text("SELECT count(*) FROM log WHERE event = 'handgriff' "
                               "AND (payload ->> 'mail')::bigint = :m"), {"m": message_id}).scalar() or 0)


def run(db: Session, deadline: float, limit: int = PER_RUN) -> tuple[int, int]:
    """Der Takt: die fälligen Mails, je eine Transaktion. Gibt (Mails, Handgriffe) zurück –
    «Mails» zählt auch die gescheiterten Versuche."""
    mails = made = 0
    for mid in due(db, limit):
        if time.monotonic() >= deadline:
            break
        found = follow_one(db, mid)
        if found is None:
            break
        mails, made = mails + 1, made + found
        db.commit()
    return mails, made
