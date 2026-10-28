"""►►► **Kommunikation – der eine Dienst** (CRM Schritt 2, ``domain/communication``). ◄◄◄

* ``create``  – eine Nachricht anlegen. Dieselbe Funktion für jede Art.
* ``history`` – der Verlauf einer Person bzw. aller Personen einer Firma.
* ``open_counts`` – je Person, wie viele offene/überfällige Nachrichten in ihrem Verlauf
  stehen (das Zeichen im Feed).

**Offen ist eine Ableitung**, keine Spalte: an uns gerichtet (``domain.to_us``),
Zeitpunkt erreicht, und keine **spätere Nachricht von uns mit demselben Betreff**
(``domain.topic``) erreicht ihren Absender (``answered``). Eine Spalte wäre die zweite
Wahrheit, die beim ersten vergessenen Nachziehen falsch wird.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..domain import communication as dc
from ..models import Message, MessageParty, UserProfile
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
                      mail=dc.is_mail(key), name=name)


def _labels(db: Session, keys: Iterable[str]) -> dict[str, tuple[str, Optional[str]]]:
    """Je Postfach seine Adresse und die Gesellschaft, für die es steht. Ein Verlauf nennt
    damit nie eine nackte Adresse («→ Inexxio AG»)."""
    from .mailbox import address_of, company
    from .sites import legal_name
    out = {}
    for k in {k for k in keys if dc.is_mail(k)}:
        firm = company(db, k)
        out[k] = (address_of(db, k), legal_name(firm) if firm else None)
    return out


def channels(db: Session) -> list[ChannelOut]:
    """►►► **Worüber geschrieben werden kann** – im eigenen Namen, und eine E-Mail über das
    Postfach einer eigenen Gesellschaft. Persönliche Postfächer gibt es nicht. ◄◄◄

    Mit Anbindung nur **verbundene** Postfächer (Betreiber zuerst): ein anderes könnte die
    Mail nicht hinausschicken. Ohne Anbindung wird nur erfasst – dann jede eigene
    Gesellschaft. Dazu Telefon und Intern."""
    from . import mailbox
    from .sites import find_operator, selectable_companies
    op = find_operator(db)
    firms = sorted(selectable_companies(db), key=lambda c: (op is None or c.id != op.id, c.id))
    keys = [dc.company(c.object_id) for c in firms if c.object_id]
    if mailbox.ready():
        keys = [k for k in keys if (mb := mailbox.active(db, k)) is not None and not mb.problem]
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


def _is_staff(people: dict[int, UserProfile], oid: int) -> bool:
    u = people.get(oid)
    return bool(u and u.role in STAFF_ROLES)


def _ref(people: dict[int, UserProfile], oid: int,
         firms: Optional[dict[int, str]] = None) -> PersonRef:
    u = people.get(oid)
    return PersonRef(object_id=oid, name=(u.display_name if u else str(oid)),
                     staff=_is_staff(people, oid),
                     company=(firms or {}).get(u.company_object_id) if u else None,
                     email=(u.email or None) if u else None)


def reply_all(sender: int, roles: dict[str, list[int]]) -> list[int]:
    """►►► **Wen «Antworten» vorbelegt – alle, wie «Allen antworten».** ◄◄◄ Der Absender
    und jeder im «An» und «Cc» der Nachricht, in dieser Reihenfolge, ohne Dubletten; wer
    nicht dabei sein soll, nimmt der Mensch heraus. Bcc bleibt unsichtbar und damit
    draussen. Unsere Postfächer sind keine Personen und kommen gar nicht vor."""
    out: list[int] = []
    for oid in (sender, *roles.get("to", []), *roles.get("cc", [])):
        if oid is not None and oid not in out:
            out.append(oid)
    return out


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
    einer eigenen Gesellschaft schon (ihr Postfach ist der Kanal). Die Angaben müssen
    existieren.

    ►►► **Eine Regel für alles: jede Nachricht hat einen Betreff** – E-Mail, Anruf, Notiz,
    interne Nachricht. Der Betreff ist das Anliegen; ohne ihn liesse sich nicht sagen, was
    eine Nachricht erledigt. Die eine Ausnahme ist Altbestand: das «erledigt ohne Antwort»
    einer Nachricht, die selbst keinen Betreff trägt (dann betrifft es wenigstens ihren
    Absender). ◄◄◄

    **Intern heisst intern**: an eine interne Nachricht gehen nur Mitarbeiter – wen sie
    betrifft, steht im «Betrifft»."""
    try:
        dc.channel(data.channel)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    if not actor.object_id:
        raise HTTPException(400, detail="Ohne Objektnummer lässt sich nichts schreiben.")
    roles = {"to": data.to, "cc": data.cc, "bcc": data.bcc, "about": data.about}
    _assert_people(db, {i for ids in roles.values() for i in ids})
    body = (data.body or "").strip()
    subject = dc.subject_line(data.subject)
    if not subject and (body or not data.about):
        raise HTTPException(400, detail="Eine Nachricht braucht einen Betreff – er ist das "
                                        "Anliegen, zu dem sie gehört.")
    if not dc.channel(data.channel).outside:
        _assert_internal(db, roles)
    if data.delivery != "mail":
        return _create_group(db, data, actor, subject, body)
    sender = actor.object_id
    if data.incoming:
        sender, roles = _incoming_call(data, roles, actor)
    elif body and dc.is_mail(data.channel) and actor.role in STAFF_ROLES:
        _assert_mail(data, roles)
    msg = Message(sender_object_id=sender, channel=data.channel, subject=subject, body=body,
                  at=_aware(data.at) if data.at else _now(), created_by=actor.id)
    write(db, msg, roles)
    _hand_to_mailbox(db, msg, roles)
    return msg


def _assert_group(db: Session, data: MessageIn, actor: UserProfile, body: str) -> list[int]:
    """**Rundschreiben und Newsletter** – die Regeln, und für den Newsletter das Tor: er
    geht nur an Angemeldete. Gibt die Empfänger zurück (ohne Dubletten)."""
    what = dc.DELIVERIES[data.delivery]
    if not dc.is_mail(data.channel) or data.incoming or actor.role not in STAFF_ROLES:
        raise HTTPException(400, detail=f"Ein {what} ist eine E-Mail von uns.")
    if data.cc or data.bcc:
        raise HTTPException(400, detail=f"Ein {what} geht an jede Person einzeln – "
                                        f"ohne Cc und Bcc.")
    ids = list(dict.fromkeys(data.to))
    if not ids or not body:
        raise HTTPException(400, detail=f"Ein {what} braucht Empfänger und Text.")
    if data.delivery == "newsletter":
        from .newsletter import subscribed
        ok = subscribed(db, ids)
        missing = [i for i in ids if i not in ok]
        if missing:
            who = _people(db, missing[:1])[missing[0]].display_name
            raise HTTPException(400, detail=f"«{who}» ist nicht für den Newsletter angemeldet "
                                            f"– er geht nur an Angemeldete.")
    return ids


def _create_group(db: Session, data: MessageIn, actor: UserProfile,
                  subject: Optional[str], body: str) -> Message:
    """►►► **Je Empfänger eine Nachricht** – mit eigener Anrede, im «An» nur er. ◄◄◄ Alle
    zeigen auf die erste (``group_id``). Hinaus gehen sie über den Abgleich
    (``mailbox.send_due``, je Lauf eine Handvoll), nicht in dieser Anfrage: hundert Mails
    in einem Klick hielten ihn sonst minutenlang fest. Gibt die erste zurück."""
    ids = _assert_group(db, data, actor, body)
    people = _people(db, ids)
    at = _aware(data.at) if data.at else _now()
    first: Optional[Message] = None
    for oid in ids:
        msg = Message(sender_object_id=actor.object_id, channel=data.channel, subject=subject,
                      body=f"{dc.greeting(people[oid].display_name)}\n\n{body}", at=at,
                      created_by=actor.id, newsletter=data.delivery == "newsletter",
                      group_id=first.id if first else None)
        roles = {"to": [oid], "cc": [], "bcc": [], "about": []}
        write(db, msg, roles)
        if first is None:
            first, msg.group_id = msg, msg.id
        _hand_to_mailbox(db, msg, roles, now=False)
    assert first is not None
    return first


def _assert_mail(data: MessageIn, roles: dict[str, list[int]]) -> None:
    """**Eine E-Mail braucht einen Empfänger** – eine ohne «An» hätte keinen Adressaten
    (den Betreff verlangt ``create`` für jede Nachricht)."""
    if not roles["to"]:
        raise HTTPException(400, detail="Eine E-Mail braucht mindestens einen Empfänger im «An».")


def _assert_internal(db: Session, roles: dict[str, list[int]]) -> None:
    """**An eine interne Nachricht gehen nur Mitarbeiter.** Sie verlässt das Haus nie – ein
    Kunde im «An» bekäme sie nicht, und sie wartete für immer auf ihn. Wen sie betrifft,
    steht im «Betrifft»."""
    people = _people(db, [i for r in ("to", "cc", "bcc") for i in roles[r]])
    outside = [u for u in people.values() if u.role not in STAFF_ROLES]
    if outside:
        raise HTTPException(400, detail=f"Eine interne Nachricht geht nur an Mitarbeiter – "
                                        f"«{outside[0].display_name}» gehört ins «Betrifft».")


def _incoming_call(data: MessageIn, roles: dict[str, list[int]], actor: UserProfile
                   ) -> tuple[int, dict[str, list[int]]]:
    """«Wurde angerufen»: der eine Kontakt im «An» ist der Anrufer, ich der Angerufene."""
    if not dc.channel(data.channel).live:
        raise HTTPException(400, detail="«Wurde angerufen» gibt es nur bei einem Anruf.")
    if len(roles["to"]) != 1:
        raise HTTPException(400, detail="Ein eingehender Anruf hat genau einen Anrufer.")
    return roles["to"][0], {**roles, "to": [actor.object_id]}


def write(db: Session, msg: Message, roles: dict[str, list[int]]) -> Message:
    """**Die eine Schreibstelle** – für eine erfasste wie für eine abgeglichene Nachricht
    (``services/mailbox``): Zeile und Beteiligte (ohne Dubletten)."""
    db.add(msg)
    db.flush()
    seen: set[tuple[int, str]] = set()
    for role, ids in roles.items():
        for oid in ids:
            if (oid, role) not in seen:
                seen.add((oid, role))
                db.add(MessageParty(message_id=msg.id, person_object_id=oid, role=role))
    db.flush()
    return msg


def _hand_to_mailbox(db: Session, msg: Message, roles: dict[str, list[int]], *,
                     now: bool = True) -> None:
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
    if now and _aware(msg.at) <= _now():
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


#: **Was die Regel «beantwortet/offen» liest** – Zeilen statt Objekte: die Regel fragt fünf
#: Spalten.
_READ = (Message.id, Message.at, Message.channel, Message.subject, Message.sender_object_id)


def answered(db: Session, msgs: list[Message],
             roles: dict[int, dict[str, list[int]]]) -> set[int]:
    """►►► **Beantwortet ist, was eine spätere Nachricht VON UNS mit demselben Betreff
    erreicht.** ◄◄◄ Erreicht heisst: ihr Absender ist an der Antwort beteiligt (als
    Absender, An, Cc, Bcc oder Betrifft). Damit erledigt eine Antwort **alle** offenen
    Nachrichten dieses Anliegens, und «erledigt ohne Antwort» ist dieselbe Regel – eine
    stille interne Nachricht mit dem Betreff, die den Absender betrifft. Schreibt ein Kunde
    im selben Anliegen nach, wartet seine Nachricht weiter: sie ist jünger als die Antwort.

    **Wer fragt, beantwortet seine Frage nicht selbst**: schreibe ich einer Kollegin, und
    schreibe ich danach noch einmal zum selben Betreff, wartet die Frage weiter auf sie.
    Die eine Ausnahme ist die Erinnerung an mich selbst (ich stehe in ihrem «An») – die
    erledige ich.

    Gefragt wird **über alle Nachrichten**, nicht nur die geladenen: im Verlauf einer
    Person, die aus dem Cc genommen wurde, steht die Antwort nicht – erledigt ist die
    Nachricht trotzdem, und zwar überall gleich.

    **Wer von aussen schreibt, bekommt seine Antwort von aussen** – eine Mail oder ein
    Anruf. Eine interne Nachricht mit Text, die ihn betrifft («kannst du hinfahren?»),
    ist eine Rückfrage im Haus und keine Antwort an ihn; er wartet weiter. Die eine
    interne, die ihn erledigt, ist die ohne Text: «Erledigt ohne Antwort»."""
    if not msgs:
        return set()
    since = min(_aware(m.at) for m in msgs)
    # Nur die Spalten, die die Regel liest – die gebaute Mail (``html``) gehört nicht dazu,
    # und über alle eigenen Nachrichten seit der ältesten Kandidatin wären das Megabytes.
    ours = db.query(*_READ, Message.body).join(
            UserProfile, UserProfile.object_id == Message.sender_object_id
        ).filter(Message.is_active.is_(True), Message.at >= since,
                 Message.at <= _now(),     # eine geplante noch nicht
                 UserProfile.role.in_(STAFF_ROLES)).all()
    if not ours:
        return set()
    parts: dict[int, set[int]] = defaultdict(set)
    for mid, oid in db.query(MessageParty.message_id, MessageParty.person_object_id).filter(
            MessageParty.message_id.in_([r.id for r in ours])).all():
        parts[mid].add(oid)
    by_topic: dict[str, list[tuple[datetime, int, int, set[int], bool]]] = defaultdict(list)
    for r in ours:
        reaches_out = dc.channel(r.channel).outside or not (r.body or "").strip()
        by_topic[dc.topic(r.subject)].append(
            (_aware(r.at), r.id, r.sender_object_id, parts[r.id] | {r.sender_object_id},
             reaches_out))
    staff = {oid for (oid,) in db.query(UserProfile.object_id).filter(
        UserProfile.object_id.in_({m.sender_object_id for m in msgs}),
        UserProfile.role.in_(STAFF_ROLES)).all()}
    done: set[int] = set()
    for m in msgs:
        at = _aware(m.at)
        own = m.sender_object_id in roles.get(m.id, {}).get("to", [])
        for r_at, r_id, r_sender, who, reaches_out in by_topic.get(dc.topic(m.subject), []):
            later = r_at > at or (r_at == at and r_id > m.id)
            asker = r_sender == m.sender_object_id and not own
            heard = reaches_out or m.sender_object_id in staff
            if r_id != m.id and later and not asker and heard and m.sender_object_id in who:
                done.add(m.id)
                break
    return done


def load(db: Session, ids: list[int]) -> list[MessageOut]:
    if not ids:
        return []
    msgs = db.query(Message).filter(Message.id.in_(ids)).order_by(Message.at, Message.id).all()
    parties = db.query(MessageParty).filter(MessageParty.message_id.in_(ids)).all()
    people = _people(db, [m.sender_object_id for m in msgs]
                     + [p.person_object_id for p in parties])
    by_msg: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for p in parties:
        by_msg[p.message_id][p.role].append(p.person_object_id)
    done = answered(db, msgs, by_msg)
    now = _now()
    labels = _labels(db, [m.channel for m in msgs])
    firms = _firms(db, people)
    return [_out(m, by_msg[m.id], m.id in done, people, now, labels, firms) for m in msgs]


def _state(m: Message, roles: dict[str, list[int]], answered: bool,
           staff: Callable[[int], bool], now: datetime) -> tuple[bool, bool]:
    """►►► **Offen und überfällig – die EINE Regel** (Regel 3). ◄◄◄ Gelesen vom Verlauf
    (``_out``) **und** vom Zeichen im Feed (``open_counts``): zwei Fassungen hiessen
    zwei Zahlen für dieselbe Nachricht."""
    at = _aware(m.at)
    is_open = (at <= now and not answered and dc.to_us(
        channel_key=m.channel, sender_staff=staff(m.sender_object_id),
        to_staff=any(staff(i) for i in roles.get("to", []))))
    return is_open, is_open and now - at > dc.OVERDUE_AFTER


def _out(m: Message, roles: dict[str, list[int]], answered: bool,
         people: dict[int, UserProfile], now: datetime,
         labels: dict[str, tuple[str, Optional[str]]],
         firms: Optional[dict[int, str]] = None) -> MessageOut:
    from .mailbox import gmail_url
    sender = _ref(people, m.sender_object_id, firms)
    refs = {r: [_ref(people, i, firms) for i in roles.get(r, [])] for r in dc.ROLES}
    at = _aware(m.at)
    is_open, overdue = _state(m, roles, answered, lambda i: _is_staff(people, i), now)
    address, name = labels.get(m.channel, (None, None))
    body, signature = (dc.split_signature(m.body or "", sender.name) if dc.is_mail(m.channel)
                       else (m.body or "", None))
    return MessageOut(
        id=m.id, channel=channel_out(m.channel, address, name), sender=sender,
        to=refs["to"], cc=refs["cc"], bcc=refs["bcc"], about=refs["about"],
        subject=m.subject, topic=dc.title(m.subject), body=body, signature=signature, at=at,
        reply_subject=dc.reply_subject(m.subject),
        reply_all=[_ref(people, i, firms) for i in reply_all(m.sender_object_id, roles)
                   if i in people],
        ours=sender.staff, open=is_open,
        overdue=overdue, planned=at > now,
        pending=bool(m.outgoing), attachments=m.attachments or [],
        gmail_url=gmail_url(address, m) if address else None,
        delivery=dc.delivery_of(m.group_id, m.newsletter),
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
    ids, sizes = _collapse(db, _ids_for(db, persons), set(persons))
    out = load(db, ids)
    for m in out:
        m.recipients = sizes.get(m.id, 0)
    return out


def _collapse(db: Session, ids: list[int], persons: set[int]
              ) -> tuple[list[int], dict[int, int]]:
    """►►► **Ein Rundschreiben steht im Verlauf EINMAL.** ◄◄◄ Je Gruppe bleibt die Kopie an
    diese Person (bzw. eine dieser Personen); wer es geschrieben hat, sieht die erste. Dazu
    je verbliebener Nachricht, an wie viele es ging."""
    rows = db.query(Message.id, Message.group_id).filter(
        Message.id.in_(ids), Message.group_id.isnot(None)).all() if ids else []
    if not rows:
        return ids, {}
    theirs = {mid for (mid,) in db.query(MessageParty.message_id).filter(
        MessageParty.message_id.in_([r.id for r in rows]), MessageParty.role == "to",
        MessageParty.person_object_id.in_(persons))}
    pick: dict[int, int] = {}
    for mid, gid in sorted(rows):
        if gid not in pick or (mid in theirs and pick[gid] not in theirs):
            pick[gid] = mid
    drop = {r.id for r in rows} - set(pick.values())
    sizes = db.query(Message.group_id, func.count(Message.id)).filter(
        Message.group_id.in_(list(pick)), Message.is_active.is_(True)
    ).group_by(Message.group_id).all()
    return [i for i in ids if i not in drop], {pick[g]: n for g, n in sizes}


def open_counts(db: Session) -> list[OpenCount]:
    """**Das Zeichen im Feed**: je Person die offenen Nachrichten in ihrem Verlauf.

    Dieselbe Regel wie im Verlauf (``_state``, ``answered``) – gezählt wird bei **jedem**
    Beteiligten. **Gezählt, nicht gebaut**: geladen werden nur die Spalten, die die Regel
    liest, und nur die Nachrichten, die an uns gehen können (``dc.to_us``: von aussen, oder
    ein Mitarbeiter im «An») – was wir selbst hinausschicken, ist nie offen."""
    live = [k for k, c in dc.CHANNELS.items() if c.live]
    now = _now()
    staff_ids = select(UserProfile.object_id).where(UserProfile.role.in_(STAFF_ROLES),
                                                    UserProfile.object_id.isnot(None))
    to_staff = select(MessageParty.message_id).where(MessageParty.role == "to",
                                                     MessageParty.person_object_id.in_(staff_ids))
    msgs = db.query(*_READ).filter(
            Message.is_active.is_(True), Message.at <= now, Message.channel.notin_(live),
            or_(Message.sender_object_id.notin_(staff_ids), Message.id.in_(to_staff))
            ).order_by(Message.at, Message.id).all()
    if not msgs:
        return []
    roles: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for mid, oid, role in db.query(MessageParty.message_id, MessageParty.person_object_id,
                                   MessageParty.role).filter(
            MessageParty.message_id.in_([m.id for m in msgs])).all():
        roles[mid][role].append(oid)
    everyone = {m.sender_object_id for m in msgs} | {
        i for r in roles.values() for ids in r.values() for i in ids}
    staff = {oid for (oid,) in db.query(UserProfile.object_id).filter(
        UserProfile.object_id.in_(everyone), UserProfile.role.in_(STAFF_ROLES)).all()}
    # Was auch ohne Antwort nicht offen wäre, braucht ``answered`` nicht zu fragen – die
    # Regel bleibt dieselbe, nur in dieser Reihenfolge ausgewertet.
    maybe = [m for m in msgs if _state(m, roles[m.id], False, staff.__contains__, now)[0]]
    done = answered(db, maybe, roles)
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for m in maybe:
        is_open, overdue = _state(m, roles[m.id], m.id in done, staff.__contains__, now)
        if not is_open:
            continue
        r = roles[m.id]
        involved = {m.sender_object_id, *(i for k in dc.ROLES
                                          for i in r.get(k, []))}
        for oid in involved:
            counts[oid][0] += 1
            counts[oid][1] += int(overdue)
    return [OpenCount(object_id=k, open=v[0], overdue=v[1]) for k, v in counts.items()]
