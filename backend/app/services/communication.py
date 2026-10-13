"""►►► **Kommunikation – der eine Dienst** (CRM Schritt 2, ``domain/communication``). ◄◄◄

* ``create``  – eine Nachricht anlegen. Dieselbe Funktion für jede Art.
* ``history`` – der Verlauf einer Person bzw. aller Personen einer Firma.
* ``open_counts`` – je Person, wie viele offene/überfällige Nachrichten in ihrem Verlauf
  stehen (das Zeichen im Feed).

**Offen ist eine Ableitung**, keine Spalte: an uns gerichtet (``domain.to_us``),
Zeitpunkt erreicht, und keine Nachricht nennt sie in «Antwort auf». Eine Spalte wäre die
zweite Wahrheit, die beim ersten vergessenen Nachziehen falsch wird.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..domain import communication as dc
from ..models import Message, MessageParty, MessageReply, UserProfile
from ..schemas.communication import ChannelOut, MessageIn, MessageOut, OpenCount, PersonRef
from .people import STAFF_ROLES


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def channel_out(key: str, label: Optional[str] = None) -> ChannelOut:
    """Ein Kanal – ein Postfach heisst wie seine Adresse (``mailbox.address_of``)."""
    c = dc.channel(key)
    return ChannelOut(key=c.key, label=label or c.label, kind=c.kind, outside=c.outside,
                      mail=dc.is_mail(key))


def _labels(db: Session, keys: Iterable[str]) -> dict[str, str]:
    from .mailbox import address_of
    return {k: address_of(db, k) for k in set(keys) if dc.is_mail(k)}


def channels(db: Session, actor: UserProfile) -> list[ChannelOut]:
    """Die Kanäle, über die dieser Mitarbeiter schreiben kann: das Unternehmen, sein
    eigenes Postfach (wenn verbunden), Telefon, Intern."""
    from .mailbox import active
    keys = list(dc.CHANNELS)
    if actor.object_id and active(db, dc.personal(actor.object_id)) is not None:
        keys.insert(1, dc.personal(actor.object_id))
    labels = _labels(db, keys)
    return [channel_out(k, labels.get(k)) for k in keys]


# ---------------------------------------------------------------------------
# Personen
# ---------------------------------------------------------------------------

def _people(db: Session, ids: Iterable[int]) -> dict[int, UserProfile]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.query(UserProfile).filter(UserProfile.object_id.in_(ids)).all()
    return {u.object_id: u for u in rows}


def _ref(people: dict[int, UserProfile], oid: int) -> PersonRef:
    u = people.get(oid)
    return PersonRef(object_id=oid, name=(u.display_name if u else str(oid)),
                     staff=bool(u and u.role in STAFF_ROLES))


def _assert_people(db: Session, ids: set[int]) -> None:
    found = set(_people(db, ids))
    missing = sorted(ids - found)
    if missing:
        raise HTTPException(400, detail=f"Person «{missing[0]}» gibt es nicht.")


# ---------------------------------------------------------------------------
# Anlegen
# ---------------------------------------------------------------------------

def create(db: Session, data: MessageIn, actor: UserProfile) -> Message:
    """**Eine Nachricht – dieselbe Funktion für E-Mail, Anruf, Notiz, Frage, Erinnerung.**

    Zwei Prüfungen, mehr braucht es nicht: die Angaben müssen existieren, und eine
    Nachricht ohne Text muss etwas beantworten (sonst sagt sie nichts – mit «Antwort auf»
    ist sie das «erledigt ohne Antwort»)."""
    try:
        dc.channel(data.channel)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    roles = {"to": data.to, "cc": data.cc, "bcc": data.bcc, "about": data.about}
    _assert_people(db, {data.sender, *(i for ids in roles.values() for i in ids)})
    body = (data.body or "").strip()
    if not body and not data.reply_to:
        raise HTTPException(400, detail="Eine Nachricht ohne Text muss etwas beantworten.")
    replies = sorted(set(data.reply_to))
    if replies:
        known = {i for (i,) in db.query(Message.id).filter(
            Message.id.in_(replies), Message.is_active.is_(True)).all()}
        if set(replies) - known:
            raise HTTPException(400, detail="«Antwort auf» nennt eine Nachricht, die es nicht gibt.")
    msg = Message(sender_object_id=data.sender, channel=data.channel,
                  subject=(data.subject or "").strip() or None, body=body,
                  at=_aware(data.at) if data.at else _now(), created_by=actor.id)
    write(db, msg, roles, replies)
    _hand_to_mailbox(db, msg, roles)
    return msg


def write(db: Session, msg: Message, roles: dict[str, list[int]],
          replies: Iterable[int]) -> Message:
    """**Die eine Schreibstelle** – für eine erfasste wie für eine abgeglichene Nachricht
    (``services/mailbox``): Zeile, Beteiligte (ohne Dubletten), «Antwort auf»."""
    db.add(msg)
    db.flush()
    seen: set[tuple[int, str]] = set()
    for role, ids in roles.items():
        for oid in ids:
            if (oid, role) not in seen:
                seen.add((oid, role))
                db.add(MessageParty(message_id=msg.id, person_object_id=oid, role=role))
    for rid in sorted(set(replies)):
        db.add(MessageReply(message_id=msg.id, reply_to_id=rid))
    db.flush()
    return msg


def _hand_to_mailbox(db: Session, msg: Message, roles: dict[str, list[int]]) -> None:
    """**Eine Mail von uns nach aussen geht hinaus** – über das Postfach ihres Kanals.

    Nur, wo es eine Anbindung gibt (``mailbox.ready``) – sonst wird sie wie bisher nur
    erfasst. Gibt es sie, ist das Postfach Pflicht: eine Mail, die das ERP als
    «verschickt» zeigt und die nie hinausging, wäre schlimmer als eine Ablehnung."""
    from . import mailbox
    outward = roles["to"] or roles["cc"] or roles["bcc"]
    if not (dc.is_mail(msg.channel) and outward and mailbox.ready()):
        return
    sender = _people(db, [msg.sender_object_id]).get(msg.sender_object_id)
    if not (sender and sender.role in STAFF_ROLES):
        return          # eine eingegangene Mail, von Hand erfasst – sie ging nie hinaus
    mailbox.assert_may_send(db, msg.channel, sender)
    msg.outgoing = True
    if _aware(msg.at) <= _now():
        mailbox.send(db, msg)


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------

def _ids_for(db: Session, persons: list[int]) -> list[int]:
    """Die Nachrichten, an denen eine dieser Personen beteiligt ist (Regel 2)."""
    if not persons:
        return []
    as_party = select(MessageParty.message_id).where(
        MessageParty.person_object_id.in_(persons))
    rows = db.query(Message.id).filter(
        Message.is_active.is_(True),
        or_(Message.sender_object_id.in_(persons), Message.id.in_(as_party)),
    ).all()
    return [r for (r,) in rows]


def load(db: Session, ids: list[int]) -> list[MessageOut]:
    if not ids:
        return []
    msgs = db.query(Message).filter(Message.id.in_(ids)).order_by(Message.at, Message.id).all()
    parties = db.query(MessageParty).filter(MessageParty.message_id.in_(ids)).all()
    replies = db.query(MessageReply).filter(MessageReply.message_id.in_(ids)).all()
    answered = {rid for (rid,) in db.query(MessageReply.reply_to_id).join(
        Message, Message.id == MessageReply.message_id).filter(
        MessageReply.reply_to_id.in_(ids), Message.is_active.is_(True)).all()}
    people = _people(db, [m.sender_object_id for m in msgs]
                     + [p.person_object_id for p in parties])
    by_msg: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for p in parties:
        by_msg[p.message_id][p.role].append(p.person_object_id)
    reply_to: dict[int, list[int]] = defaultdict(list)
    for r in replies:
        reply_to[r.message_id].append(r.reply_to_id)
    now = _now()
    labels = _labels(db, [m.channel for m in msgs])
    return [_out(m, by_msg[m.id], reply_to[m.id], m.id in answered, people, now, labels)
            for m in msgs]


def _out(m: Message, roles: dict[str, list[int]], reply_to: list[int], answered: bool,
         people: dict[int, UserProfile], now: datetime, labels: dict[str, str]) -> MessageOut:
    from .mailbox import gmail_url
    sender = _ref(people, m.sender_object_id)
    refs = {r: [_ref(people, i) for i in roles.get(r, [])] for r in dc.ROLES}
    at = _aware(m.at)
    is_open = (at <= now and not answered and dc.to_us(
        channel_key=m.channel, sender_staff=sender.staff,
        to_staff=any(p.staff for p in refs["to"])))
    return MessageOut(
        id=m.id, channel=channel_out(m.channel, labels.get(m.channel)), sender=sender,
        to=refs["to"], cc=refs["cc"], bcc=refs["bcc"], about=refs["about"],
        subject=m.subject, body=m.body, at=at, reply_to=sorted(reply_to),
        ours=sender.staff, open=is_open,
        overdue=is_open and now - at > dc.OVERDUE_AFTER, planned=at > now,
        pending=bool(m.outgoing), attachments=m.attachments or [],
        gmail_url=gmail_url(labels[m.channel], m) if m.channel in labels else None,
    )


def history(db: Session, *, person: Optional[int] = None,
            company: Optional[int] = None) -> list[MessageOut]:
    """Der Verlauf – einer Person, oder aller Personen einer Firma (Regel 2)."""
    persons: list[int] = []
    if person:
        persons = [person]
    elif company:
        persons = [oid for (oid,) in db.query(UserProfile.object_id).filter(
            UserProfile.company_object_id == company,
            UserProfile.object_id.isnot(None)).all()]
    return load(db, _ids_for(db, persons))


def open_counts(db: Session) -> list[OpenCount]:
    """**Das Zeichen im Feed**: je Person die offenen Nachrichten in ihrem Verlauf.

    Gelesen werden nur Kandidaten – Zeitpunkt erreicht und unbeantwortet –, die Regel
    selbst ist dieselbe wie im Verlauf (``_out``), keine zweite Fassung."""
    answered = select(MessageReply.reply_to_id).join(
        Message, Message.id == MessageReply.message_id).where(Message.is_active.is_(True))
    ids = [i for (i,) in db.query(Message.id).filter(
        Message.is_active.is_(True), Message.at <= _now(),
        Message.id.notin_(answered)).all()]
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for m in load(db, ids):
        if not m.open:
            continue
        involved = {m.sender.object_id, *(p.object_id for r in (m.to, m.cc, m.bcc, m.about)
                                          for p in r)}
        for oid in involved:
            counts[oid][0] += 1
            counts[oid][1] += int(m.overdue)
    return [OpenCount(object_id=k, open=v[0], overdue=v[1]) for k, v in counts.items()]
