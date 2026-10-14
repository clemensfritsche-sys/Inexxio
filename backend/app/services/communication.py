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


def channel_out(key: str, label: Optional[str] = None, name: Optional[str] = None
                ) -> ChannelOut:
    """Ein Kanal – ein Postfach heisst wie seine Adresse (``mailbox.address_of``) und
    trägt den Namen, in dem es hinausgeht (``name``)."""
    c = dc.channel(key)
    return ChannelOut(key=c.key, label=label or c.label, kind=c.kind, outside=c.outside,
                      mail=dc.is_mail(key), personal=dc.owner_of(key) is not None,
                      name=name)


def _labels(db: Session, keys: Iterable[str]) -> dict[str, tuple[str, Optional[str]]]:
    """Je Postfach seine Adresse und der Name, für den es steht – die Gesellschaft bzw.
    der Mitarbeiter. Ein Verlauf nennt damit nie eine nackte Adresse («→ Inexxio AG»)."""
    from .mailbox import address_of, company
    from .sites import legal_name
    keys = {k for k in keys if dc.is_mail(k)}
    owners = _people(db, [dc.owner_of(k) for k in keys if dc.owner_of(k) is not None])
    out = {}
    for k in keys:
        firm, owner = company(db, k), owners.get(dc.owner_of(k) or 0)
        name = legal_name(firm) if firm else (owner.display_name if owner else None)
        out[k] = (address_of(db, k), name)
    return out


def channels(db: Session, actor: UserProfile) -> list[ChannelOut]:
    """►►► **Worüber DIESER Mitarbeiter schreiben kann** – geschrieben wird nur im eigenen
    Namen oder in dem einer eigenen Gesellschaft, nie in fremdem. ◄◄◄

    Mit Anbindung nur **verbundene** Postfächer (die Gesellschaften, Betreiber zuerst, und
    das eigene): ein anderes könnte die Mail nicht hinausschicken. Ohne Anbindung wird nur
    erfasst – dann jede eigene Gesellschaft. Dazu Telefon und Intern."""
    from . import mailbox
    from .sites import find_operator, selectable_companies
    op = find_operator(db)
    firms = sorted(selectable_companies(db), key=lambda c: (op is None or c.id != op.id, c.id))
    keys = [dc.company(c.object_id) for c in firms if c.object_id]
    if actor.object_id:
        keys.append(dc.personal(actor.object_id))
    if mailbox.ready():
        keys = [k for k in keys if (mb := mailbox.active(db, k)) is not None and not mb.problem]
    else:
        keys = [k for k in keys if dc.company_of(k) is not None]
    keys += list(dc.CHANNELS)
    labels = _labels(db, keys)
    return [channel_out(k, *labels.get(k, (None, None))) for k in keys]


# ---------------------------------------------------------------------------
# Personen
# ---------------------------------------------------------------------------

def _people(db: Session, ids: Iterable[int]) -> dict[int, UserProfile]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.query(UserProfile).filter(UserProfile.object_id.in_(ids)).all()
    return {u.object_id: u for u in rows}


def _firms(db: Session, people: dict[int, UserProfile]) -> dict[int, str]:
    """Objektnummer der Firma → ihr Name mit Rechtsform – einmal je Antwort, nicht je Zeile."""
    from ..models import CompanySettings
    from .sites import legal_name
    ids = {u.company_object_id for u in people.values() if u.company_object_id}
    if not ids:
        return {}
    rows = db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids)).all()
    return {c.object_id: legal_name(c) for c in rows}


def _ref(people: dict[int, UserProfile], oid: int,
         firms: Optional[dict[int, str]] = None) -> PersonRef:
    u = people.get(oid)
    return PersonRef(object_id=oid, name=(u.display_name if u else str(oid)),
                     staff=bool(u and u.role in STAFF_ROLES),
                     company=(firms or {}).get(u.company_object_id) if u else None,
                     email=(u.email or None) if u else None)


def answer_targets(sender: int, sender_staff: bool, roles: dict[str, list[int]],
                   me: Optional[int]) -> set[int]:
    """►►► **Wen eine Antwort erreichen muss** – mindestens einen davon. ◄◄◄

    Schrieb jemand **von aussen**, ist es genau er: eine Antwort, die ihn nicht erreicht,
    ist keine (eine Notiz an einen Kollegen beantwortet die Frage des Kunden nicht). Schrieb
    **einer von uns**, ist es jeder Beteiligte ausser mir – die Frage einer Kollegin
    beantworte ich ihr, meine Mail an einen Kunden setze ich bei ihm fort. Bleibt niemand
    (meine eigene Erinnerung), ist die Antwort an niemanden gebunden."""
    if not sender_staff:
        return {sender}
    return ({sender, *roles.get("to", []), *roles.get("cc", [])} - {me, None})


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

    **Absender ist, wer angemeldet ist** – geschrieben wird nie in fremdem Namen; im Namen
    einer eigenen Gesellschaft schon (ihr Postfach ist der Kanal), über das persönliche
    Postfach eines anderen nicht. Die Angaben müssen existieren, «Antwort auf» nennt
    **höchstens eine** Nachricht, und eine Nachricht ohne Text muss etwas beantworten
    (sonst sagt sie nichts – mit «Antwort auf» ist sie das «erledigt ohne Antwort»)."""
    try:
        dc.channel(data.channel)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    if not actor.object_id:
        raise HTTPException(400, detail="Ohne Objektnummer lässt sich nichts schreiben.")
    owner = dc.owner_of(data.channel)
    if owner is not None and owner != actor.object_id:
        raise HTTPException(403, detail=f"Über das Postfach von «{owner}» schreibt nur "
                                        f"sein Besitzer.")
    roles = {"to": data.to, "cc": data.cc, "bcc": data.bcc, "about": data.about}
    _assert_people(db, {i for ids in roles.values() for i in ids})
    body = (data.body or "").strip()
    if not body and data.reply_to is None:
        raise HTTPException(400, detail="Eine Nachricht ohne Text muss etwas beantworten.")
    sender = actor.object_id
    if data.incoming:
        sender, roles = _incoming_call(data, roles, actor)
    elif body and dc.is_mail(data.channel) and actor.role in STAFF_ROLES:
        _assert_mail(data, roles)
    replies = [data.reply_to] if data.reply_to is not None else []
    if replies:
        _assert_answers(db, data.reply_to, roles, body, actor, sender)
    msg = Message(sender_object_id=sender, channel=data.channel,
                  subject=(data.subject or "").strip() or None, body=body,
                  at=_aware(data.at) if data.at else _now(), created_by=actor.id)
    write(db, msg, roles, replies)
    _hand_to_mailbox(db, msg, roles)
    return msg


def _assert_mail(data: MessageIn, roles: dict[str, list[int]]) -> None:
    """**Eine E-Mail ist erst vollständig mit Empfänger und Betreff.** Eine ohne «An»
    hätte keinen Adressaten, eine ohne Betreff ist im Postfach des Empfängers eine leere
    Zeile. Bei einer Antwort steht «Re: …» schon da (die Oberfläche belegt es vor)."""
    if not roles["to"]:
        raise HTTPException(400, detail="Eine E-Mail braucht mindestens einen Empfänger im «An».")
    if not (data.subject or "").strip():
        raise HTTPException(400, detail="Eine E-Mail braucht einen Betreff.")


def _incoming_call(data: MessageIn, roles: dict[str, list[int]], actor: UserProfile
                   ) -> tuple[int, dict[str, list[int]]]:
    """«Wurde angerufen»: der eine Kontakt im «An» ist der Anrufer, ich der Angerufene."""
    if not dc.channel(data.channel).live:
        raise HTTPException(400, detail="«Wurde angerufen» gibt es nur bei einem Anruf.")
    if len(roles["to"]) != 1:
        raise HTTPException(400, detail="Ein eingehender Anruf hat genau einen Anrufer.")
    return roles["to"][0], {**roles, "to": [actor.object_id]}


def _assert_answers(db: Session, reply_to: int, roles: dict[str, list[int]], body: str,
                    actor: UserProfile, author: int) -> None:
    """Eine Antwort erreicht, wem sie antwortet (``answer_targets``). «Erledigt ohne
    Antwort» (kein Text) ist an niemanden gerichtet und darum frei. Wer selbst anruft, ist
    erreicht – bei «wurde angerufen» ist der Kontakt der Absender."""
    parent = db.query(Message).filter(Message.id == reply_to,
                                      Message.is_active.is_(True)).first()
    if parent is None:
        raise HTTPException(400, detail=f"«Antwort auf» nennt die Nachricht «{reply_to}», "
                                        f"die es nicht gibt.")
    if not body:
        return
    parties = db.query(MessageParty).filter(MessageParty.message_id == parent.id).all()
    proles: dict[str, list[int]] = defaultdict(list)
    for p in parties:
        proles[p.role].append(p.person_object_id)
    people = _people(db, [parent.sender_object_id])
    sender = people.get(parent.sender_object_id)
    targets = answer_targets(parent.sender_object_id,
                             bool(sender and sender.role in STAFF_ROLES), proles,
                             actor.object_id)
    if targets and not targets & {*roles["to"], *roles["cc"], author}:
        names = _people(db, targets)
        who = ", ".join(sorted(names[t].display_name for t in targets if t in names)) \
            or ", ".join(str(t) for t in sorted(targets))
        raise HTTPException(400, detail=f"Eine Antwort geht an «{who}» – bitte ins «An» "
                                        f"nehmen oder «Antwort auf» entfernen.")


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


def _answers(db: Session):
    """►►► **Beantwortet ist, worauf eine Nachricht VON UNS antwortet.** ◄◄◄ Schreibt ein
    Kunde im selben Faden nach, ist seine erste Frage damit nicht erledigt – sie wartet
    weiter auf uns. Die eine Abfrage für Verlauf und Feed-Zeichen."""
    return (db.query(MessageReply.reply_to_id)
            .join(Message, Message.id == MessageReply.message_id)
            .join(UserProfile, UserProfile.object_id == Message.sender_object_id)
            .filter(Message.is_active.is_(True), UserProfile.role.in_(STAFF_ROLES)))


def load(db: Session, ids: list[int]) -> list[MessageOut]:
    if not ids:
        return []
    msgs = db.query(Message).filter(Message.id.in_(ids)).order_by(Message.at, Message.id).all()
    parties = db.query(MessageParty).filter(MessageParty.message_id.in_(ids)).all()
    replies = db.query(MessageReply).filter(MessageReply.message_id.in_(ids)).all()
    answered = {rid for (rid,) in _answers(db).filter(MessageReply.reply_to_id.in_(ids)).all()}
    people = _people(db, [m.sender_object_id for m in msgs]
                     + [p.person_object_id for p in parties])
    by_msg: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for p in parties:
        by_msg[p.message_id][p.role].append(p.person_object_id)
    reply_to: dict[int, int] = {}
    for r in sorted(replies, key=lambda r: r.reply_to_id):
        reply_to.setdefault(r.message_id, r.reply_to_id)
    now = _now()
    labels = _labels(db, [m.channel for m in msgs])
    firms = _firms(db, people)
    return [_out(m, by_msg[m.id], reply_to.get(m.id), m.id in answered, people, now, labels,
                 firms) for m in msgs]


def _out(m: Message, roles: dict[str, list[int]], reply_to: Optional[int], answered: bool,
         people: dict[int, UserProfile], now: datetime,
         labels: dict[str, tuple[str, Optional[str]]],
         firms: Optional[dict[int, str]] = None) -> MessageOut:
    from .mailbox import gmail_url
    sender = _ref(people, m.sender_object_id, firms)
    refs = {r: [_ref(people, i, firms) for i in roles.get(r, [])] for r in dc.ROLES}
    targets = answer_targets(m.sender_object_id, sender.staff, roles, None)
    at = _aware(m.at)
    is_open = (at <= now and not answered and dc.to_us(
        channel_key=m.channel, sender_staff=sender.staff,
        to_staff=any(p.staff for p in refs["to"])))
    address, name = labels.get(m.channel, (None, None))
    body, signature = (dc.split_signature(m.body or "", sender.name) if dc.is_mail(m.channel)
                       else (m.body or "", None))
    return MessageOut(
        id=m.id, channel=channel_out(m.channel, address, name), sender=sender,
        to=refs["to"], cc=refs["cc"], bcc=refs["bcc"], about=refs["about"],
        subject=m.subject, body=body, signature=signature, at=at, reply_to=reply_to,
        answer_to=[_ref(people, i, firms) for i in sorted(targets) if i in people],
        ours=sender.staff, open=is_open,
        overdue=is_open and now - at > dc.OVERDUE_AFTER, planned=at > now,
        pending=bool(m.outgoing), attachments=m.attachments or [],
        gmail_url=gmail_url(address, m) if address else None,
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


def holders(m: MessageOut) -> set[int]:
    """►►► **Wo eine offene Nachricht zählt – dort, wo die Sache liegt.** ◄◄◄ Mit
    «Betrifft» bei den Betroffenen (eine Notiz über Unisto an mich zählt bei Unisto, nicht
    bei mir); sonst bei den Externen, die beteiligt sind (der Kunde, der schreibt); und nur,
    wo es keine gibt, bei den Mitarbeitern im «An» (die interne Frage an die Kollegin)."""
    if m.about:
        return {p.object_id for p in m.about}
    everyone = [m.sender, *m.to, *m.cc, *m.bcc]
    outside = {p.object_id for p in everyone if not p.staff}
    return outside or {p.object_id for p in m.to}


def open_counts(db: Session) -> list[OpenCount]:
    """**Das Zeichen im Feed**: je Person die offenen Nachrichten in ihrem Verlauf.

    Gelesen werden nur Kandidaten – Zeitpunkt erreicht und unbeantwortet –, die Regel
    selbst ist dieselbe wie im Verlauf (``_out``), keine zweite Fassung."""
    answered = _answers(db).subquery()
    ids = [i for (i,) in db.query(Message.id).filter(
        Message.is_active.is_(True), Message.at <= _now(),
        Message.id.notin_(select(answered.c.reply_to_id))).all()]
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for m in load(db, ids):
        if not m.open:
            continue
        for oid in holders(m):
            counts[oid][0] += 1
            counts[oid][1] += int(m.overdue)
    return [OpenCount(object_id=k, open=v[0], overdue=v[1]) for k, v in counts.items()]
