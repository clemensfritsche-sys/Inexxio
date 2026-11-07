"""►►► **Was aus einer eingehenden Mail folgt** (Projektakte §4.3, Bauplan «Der Takt»). ◄◄◄

Die Kundin schreibt, unten in der Signatur steht eine neue Telefonnummer – die KI schlägt vor,
sie zu übernehmen (``ai.converse``, Aufgabe ``follow``, im Takt). Geprüft wird nur, was:

* **von aussen an uns** kam (abgeglichen aus dem Postfach einer eigenen Gesellschaft),
* **von einer bekannten Person** (die es schon gab, als die Mail ankam – ein neuer Absender
  entsteht erst beim Abgleich aus der Mail; Massenpost legt der Abgleich gar nicht erst an),
* **nach der Einführung** – der Startpunkt ist ein Ereignis (``follow.start``, die höchste
  Nachrichtennummer beim ersten Lauf), keine Spalte; ältere Mails bleiben, wie sie sind,
* **je Mail einmal** – Ereignis ``mail.followed`` (mit der Nummer der Nachricht).

Ergebnis sind Vorschläge (``change``/``create``) mit der Mail als Quelle; geschrieben wird erst
nach dem Klick eines Menschen. Gelesen wird mit den Rechten der Person, die das Postfach
verbunden hat.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Message, UserProfile
from . import ai, log
from .intake import AiProposal, follow_up, system_text

#: So viele Mails je Lauf des Takts.
PER_RUN = 5


class FollowAnswer(BaseModel):
    proposals: list[AiProposal]


FOLLOW_FORMAT = """
Antwortformat: `proposals` – was aus dieser Mail folgt: `change` (ein Feld eines Datensatzes
ändern, z. B. eine neue Telefonnummer aus der Signatur) oder `create` (eine Person oder Firma
anlegen). Leer, wenn nichts folgt.
Erlaubte Felder:
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
    cases = memory.as_prompt(memory.similar(db, body, actor=reader))
    head = (f"Eine Mail an uns von {sender.display_name} ({sender.object_id}), "
            f"am {msg.at.isoformat(timespec='minutes')}.")
    return [{"type": "text", "text": head + ("\n\n" + cases if cases else "") + "\n\n" + body}]


def follow_one(db: Session, message_id: int) -> Optional[int]:
    """►►► **Eine Mail auf ihre Folgen prüfen** – gibt die Zahl der Vorschläge zurück, oder
    ``None``, wenn die KI gerade nicht da ist (dann kommt die Mail im nächsten Lauf wieder). ◄◄◄"""
    msg = db.get(Message, message_id)
    sender = db.query(UserProfile).filter(UserProfile.object_id == msg.sender_object_id).first()
    reader = _reader(db, msg)
    if reader is None or sender is None:
        log.event(db, "mail.followed", msg.sender_object_id,
                  {"message": msg.id, "problem": "Kein Personal an diesem Postfach."})
        return 0
    if not ai.available(db):
        return None
    from . import ai_tools
    answer = ai.converse(db, task="follow", actor=reader, system=system_text(FOLLOW_FORMAT),
                         content=_content(db, msg, sender, reader), schema=FollowAnswer,
                         tools=ai_tools.tools_for(db, reader))
    if answer is None and not ai.available(db):
        return None
    source = {"text": f"Mail von {sender.display_name}: {msg.subject or ''}"[:300],
              "object_id": sender.object_id, "message_id": msg.id, "at": msg.at}
    made = follow_up(db, answer.proposals, home=sender.object_id, source=source,
                     actor=reader) if answer is not None else []
    log.event(db, "mail.followed", sender.object_id,
              {"message": msg.id, "proposals": len(made),
               **({"problem": ai.problem()} if answer is None else {})})
    return len(made)


def run(db: Session, deadline: float, limit: int = PER_RUN) -> tuple[int, int]:
    """Der Takt: die fälligen Mails, je eine Transaktion. Gibt (Mails, Vorschläge) zurück."""
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
