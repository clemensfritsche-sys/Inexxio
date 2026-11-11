"""►►► **Kommunikation – der eine Dienst** (CRM Schritt 2, ``domain/communication``). ◄◄◄

* ``create``  – eine Nachricht anlegen. Dieselbe Funktion für jede Art (auch die Notiz).
* ``page`` – der Verlauf **in Seiten** (die neuesten zuerst, ``before`` ist
  der Cursor): einer Person, aller Personen einer Firma, oder die Nachrichten, die einen
  beliebigen Datensatz «betreffen» (``scope``). Nie alles auf einmal.
* ``open_counts`` – je Person, wie viele offene/überfällige Nachrichten in ihrem Verlauf
  stehen (das Zeichen im Feed).
* ``move_note`` – eine Notiz gehört woandershin: Vermerk am falschen, Inhalt am richtigen
  Datensatz; gelöscht wird nichts.

**Offen ist eine Ableitung**, keine Spalte: an uns gerichtet (``domain.to_us``),
Zeitpunkt erreicht, und keine **spätere Nachricht von uns mit demselben Betreff**
(``domain.topic``) erreicht ihren Absender (``answered``). Eine Spalte wäre die zweite
Wahrheit, die beim ersten vergessenen Nachziehen falsch wird. Das Anliegen selbst steht als
Spalte da (``messages.topic``, aus dem Betreff, der sich nie ändert) – so ist «beantwortet»
**eine Abfrage** (``_ANSWERED``), die je Kandidatin nur ihr eigenes Anliegen ansieht.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..domain import communication as dc
from ..models import Message, MessageParty, UserProfile
from ..schemas.communication import ChannelOut, MessageIn, MessageOut, OpenCount, PersonRef
from ..domain.policy import STAFF_ROLES
from ..domain.errors import Invalid, NotFound
from ..domain import policy
from ..core import clock



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

    Nur **verbundene** Postfächer (Betreiber zuerst): ein anderes könnte die Mail nicht
    hinausschicken. Ist keines verbunden, gibt es keine E-Mail – nur Telefon und Intern."""
    from . import mailbox
    from .sites import find_operator, selectable_companies
    op = find_operator(db)
    firms = sorted(selectable_companies(db), key=lambda c: (op is None or c.id != op.id, c.id))
    keys = [k for k in (dc.company(c.object_id) for c in firms if c.object_id)
            if (mb := mailbox.active(db, k)) is not None and not mb.problem]
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
    return policy.is_staff(u)


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
        raise Invalid(f"Person «{missing[0]}» gibt es nicht.")


def _assert_records(db: Session, ids: set[int]) -> None:
    """**«Betrifft» darf jeder Datensatz sein** – eine Person, eine Firma, ein Auftrag, ein
    Artikel, eine Instanz, ein Dokument. Er muss nur existieren."""
    from .record_labels import labels
    missing = sorted(ids - set(_people(db, ids)) - set(labels(db, ids)))
    if missing:
        raise Invalid(f"Datensatz «{missing[0]}» gibt es nicht.")


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
    betrifft, steht im «Betrifft». **«Betrifft» darf jeder Datensatz sein** (die Notiz am
    Auftrag); An, Cc und Bcc sind immer Personen – nur sie bekommen etwas."""
    try:
        dc.channel(data.channel)
    except ValueError as exc:
        raise Invalid(str(exc)) from exc
    if not actor.object_id:
        raise Invalid("Ohne Objektnummer lässt sich nichts schreiben.")
    roles = {"to": data.to, "cc": data.cc, "bcc": data.bcc, "about": data.about}
    _assert_people(db, {i for r in ("to", "cc", "bcc") for i in roles[r]})
    _assert_records(db, set(data.about))
    body = (data.body or "").strip()
    subject = dc.subject_line(data.subject)
    if not subject and (body or not data.about):
        raise Invalid("Eine Nachricht braucht einen Betreff – er ist das "
                                        "Anliegen, zu dem sie gehört.")
    if not dc.channel(data.channel).outside:
        _assert_internal(db, roles)
    if data.delivery != "mail":
        return _create_group(db, data, actor, subject, body)
    sender = actor.object_id
    if data.incoming:
        sender, roles = _incoming_call(data, roles, actor)
    elif body and dc.is_mail(data.channel) and policy.is_staff(actor):
        _assert_mail(data, roles)
    msg = Message(sender_object_id=sender, channel=data.channel, subject=subject, body=body,
                  at=_aware(data.at) if data.at else clock.utcnow(), created_by=actor.id,
                  inbound=data.incoming or not policy.is_staff(actor))
    write(db, msg, roles)
    _hand_to_mailbox(db, msg, roles)
    return msg


def _assert_group(db: Session, data: MessageIn, actor: UserProfile, body: str) -> list[int]:
    """**Rundschreiben und Newsletter** – die Regeln, und für den Newsletter das Tor: er
    geht nur an Angemeldete. Gibt die Empfänger zurück (ohne Dubletten)."""
    what = dc.DELIVERIES[data.delivery]
    if not dc.is_mail(data.channel) or data.incoming or not policy.is_staff(actor):
        raise Invalid(f"Ein {what} ist eine E-Mail von uns.")
    if data.cc or data.bcc:
        raise Invalid(f"Ein {what} geht an jede Person einzeln – "
                                        f"ohne Cc und Bcc.")
    ids = list(dict.fromkeys(data.to))
    if not ids or not body:
        raise Invalid(f"Ein {what} braucht Empfänger und Text.")
    if data.delivery == "newsletter":
        from .newsletter import subscribed
        ok = subscribed(db, ids)
        missing = [i for i in ids if i not in ok]
        if missing:
            who = _people(db, missing[:1])[missing[0]].display_name
            raise Invalid(f"«{who}» ist nicht für den Newsletter angemeldet "
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
    at = _aware(data.at) if data.at else clock.utcnow()
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
        raise Invalid("Eine E-Mail braucht mindestens einen Empfänger im «An».")


def _assert_internal(db: Session, roles: dict[str, list[int]]) -> None:
    """**An eine interne Nachricht gehen nur Mitarbeiter.** Sie verlässt das Haus nie – ein
    Kunde im «An» bekäme sie nicht, und sie wartete für immer auf ihn. Wen sie betrifft,
    steht im «Betrifft»."""
    people = _people(db, [i for r in ("to", "cc", "bcc") for i in roles[r]])
    outside = [u for u in people.values() if not policy.is_staff(u)]
    if outside:
        raise Invalid(f"Eine interne Nachricht geht nur an Mitarbeiter – "
                                        f"«{outside[0].display_name}» gehört ins «Betrifft».")


def _incoming_call(data: MessageIn, roles: dict[str, list[int]], actor: UserProfile
                   ) -> tuple[int, dict[str, list[int]]]:
    """«Wurde angerufen»: der eine Kontakt im «An» ist der Anrufer, ich der Angerufene."""
    if not dc.channel(data.channel).live:
        raise Invalid("«Wurde angerufen» gibt es nur bei einem Anruf.")
    if len(roles["to"]) != 1:
        raise Invalid("Ein eingehender Anruf hat genau einen Anrufer.")
    return roles["to"][0], {**roles, "to": [actor.object_id]}


def write(db: Session, msg: Message, roles: dict[str, list[int]]) -> Message:
    """**Die eine Schreibstelle** – für eine erfasste wie für eine abgeglichene Nachricht
    (``services/mailbox``): Zeile und Beteiligte (ohne Dubletten). Das Anliegen
    (``topic``) setzt das Modell mit dem Betreff (``Message._topic``)."""
    db.add(msg)
    db.flush()
    seen: set[tuple[int, str]] = set()
    for role, ids in roles.items():
        for oid in ids:
            if (oid, role) not in seen:
                seen.add((oid, role))
                db.add(MessageParty(message_id=msg.id, object_id=oid, role=role))
    db.flush()
    return msg


def _hand_to_mailbox(db: Session, msg: Message, roles: dict[str, list[int]], *,
                     now: bool = True) -> None:
    """**Eine Mail von uns nach aussen geht hinaus** – über das Postfach ihres Kanals. Das
    Postfach ist Pflicht: eine Mail, die das ERP als «verschickt» zeigt und die nie
    hinausging, wäre schlimmer als eine Ablehnung. Einen Modus «nur erfassen» gibt es nicht."""
    from . import mailbox, outbox
    outward = roles["to"] or roles["cc"] or roles["bcc"]
    if not (dc.is_mail(msg.channel) and outward):
        return
    if msg.inbound:
        return          # eine eingegangene Mail, von Hand erfasst – sie ging nie hinaus
    sender = _people(db, [msg.sender_object_id]).get(msg.sender_object_id)
    mailbox.assert_may_send(db, msg.channel, sender)
    msg.outgoing = True
    outbox.build(db, msg)       # gebaut jetzt – der Verlauf ist ab hier, was hinausgeht
    if now:
        mailbox.send_after(db)




# ---------------------------------------------------------------------------
# Beantwortet – EINE Abfrage
# ---------------------------------------------------------------------------

#: ►►► **Beantwortet ist, was eine spätere Nachricht VON UNS mit demselben Betreff
#: erreicht** – als Bedingung über eine Kandidatin ``m`` (Spalten ``id``, ``at``,
#: ``sender_object_id``, ``topic``, ``inbound``). ◄◄◄ Die eine Fassung der Regel; ``answered``
#: fragt sie für eine Liste, ``open_counts`` für alle, die an uns gehen. Je Kandidatin liest
#: sie nur ihr eigenes Anliegen ab ihrem Zeitpunkt (Index ``ix_messages_topic_at``).
#:
#: * **von uns** heisst: sie ging hinaus (``inbound`` aus) – die Richtung der Nachricht,
#:   nicht die Rolle ihres Absenders;
#: * **und sie ist auch draussen**: eine Mail, die noch wartet (``outgoing``) oder nicht
#:   gesendet wurde (``_FAILED``), hat niemanden erreicht und beantwortet nichts;
#: * **erreicht**: ihr Absender ist an der Antwort beteiligt (Absender, An, Cc, Bcc,
#:   Betrifft) – damit erledigt eine Antwort alle offenen Nachrichten des Anliegens;
#: * **wer fragt, beantwortet seine Frage nicht selbst** – ausser was von aussen kam (ein
#:   Mitarbeiter von seiner privaten Adresse) und der Erinnerung an mich (ich stehe in
#:   ihrem «An»);
#: * **was von aussen kam, bekommt die Antwort nach aussen** (eine Mail, ein Anruf);
#:   intern erledigt es nur die Nachricht ohne Text («Erledigt ohne Antwort»). «Ohne
#:   Text» heisst: kein Zeichen ausser Leerraum (``!~ '\S'``, wie ``str.strip``).
#: * eine **geplante** Antwort (Zeitpunkt in der Zukunft) beantwortet noch nichts.
#: Wer zu uns gehört – einmal je Abfrage gelesen (``MATERIALIZED``: ein paar Zeilen, und der
#: Planer schätzt danach richtig, statt jede Nachricht teuer einzupreisen). Gebraucht nur
#: noch für «an einen Mitarbeiter» (die Erinnerung, die interne Frage).
_STAFF = ("WITH staff AS MATERIALIZED (SELECT object_id FROM user_profiles "
          "WHERE role = ANY(:staff) AND object_id IS NOT NULL) ")

#: ►►► **Nicht gesendet – die EINE Regel** (über eine Nachricht ``{m}``): der Versand gab auf
#: (``mail.gave_up``), sie wartet nicht mehr und ging nie hinaus (keine Gmail-Nummer). Gelesen
#: von «beantwortet» (``_ANSWERED``) und von der Anzeige an der Mail (``failed``). ◄◄◄
_FAILED = ("(NOT {m}.outgoing AND {m}.gmail_id IS NULL AND EXISTS ("
           "SELECT 1 FROM log g WHERE g.event = 'mail.gave_up' AND g.table_name = 'messages' "
           "AND g.row_key = {m}.id::text))")


def failed(db: Session, ids: list[int]) -> set[int]:
    """Welche dieser Nachrichten gingen nicht hinaus (``_FAILED``)?"""
    if not ids:
        return set()
    rows = db.execute(text(f"SELECT m.id FROM messages m WHERE m.id = ANY(:ids) AND "
                           f"{_FAILED.format(m='m')}"), {"ids": list(ids)})
    return {i for (i,) in rows}


def resend(db: Session, message_id: int, actor: UserProfile) -> Message:
    """**Neu senden** – eine Mail, die nicht hinausging, wieder zum Versand geben. Gezählt
    werden die Versuche danach von vorn (``mail.resend``)."""
    from . import log, mailbox
    msg = db.query(Message).filter(Message.id == message_id, Message.is_active.is_(True)).first()
    if msg is None or not dc.is_mail(msg.channel):
        raise NotFound("Diese Mail gibt es nicht.")
    if message_id not in failed(db, [message_id]):
        raise Invalid(f"Die Mail «{msg.subject or ''}» wartet nicht auf einen neuen Versuch.")
    mailbox.assert_may_send(db, msg.channel, actor)
    msg.outgoing = True
    log.event(db, "mail.resend", msg.sender_object_id, {}, table="messages", row=msg.id)
    mailbox.send_after(db)
    return msg


_ANSWERED = """EXISTS (
  SELECT 1 FROM messages r
   WHERE r.topic = m.topic AND r.is_active AND r.at <= :now AND r.id <> m.id
     AND r.channel <> 'note' AND NOT r.inbound AND NOT r.outgoing
     AND NOT """ + _FAILED.format(m="r") + """
     AND (r.at > m.at OR (r.at = m.at AND r.id > m.id))
     AND (m.inbound OR r.sender_object_id <> m.sender_object_id OR EXISTS (
            SELECT 1 FROM message_parties own WHERE own.message_id = m.id
               AND own.role = 'to' AND own.object_id = m.sender_object_id))
     AND (r.channel <> ALL(:inside) OR r.body !~ '\\S' OR NOT m.inbound)
     AND (r.sender_object_id = m.sender_object_id OR EXISTS (
            SELECT 1 FROM message_parties w WHERE w.message_id = r.id
               AND w.object_id = m.sender_object_id)))"""


def _rule_params() -> dict:
    return {"staff": list(STAFF_ROLES), "now": clock.utcnow(),
            "inside": [k for k, c in dc.CHANNELS.items() if not c.outside]}


def answered(db: Session, ids: list[int]) -> set[int]:
    """►►► **Welche dieser Nachrichten sind beantwortet?** (``_ANSWERED``) ◄◄◄

    Gefragt wird **über alle Nachrichten**, nicht nur die geladenen: im Verlauf einer
    Person, die aus dem Cc genommen wurde, steht die Antwort nicht – erledigt ist die
    Nachricht trotzdem, und zwar überall gleich. Schreibt ein Kunde im selben Anliegen nach,
    wartet seine Nachricht weiter: sie ist jünger als die Antwort."""
    if not ids:
        return set()
    rows = db.execute(text(f"SELECT m.id FROM messages m WHERE m.id = ANY(:ids) "
                           f"AND {_ANSWERED}"),
                      {"ids": list(ids), **_rule_params()})
    return {i for (i,) in rows}


# ---------------------------------------------------------------------------
# Lesen – in Seiten
# ---------------------------------------------------------------------------

#: So viele Einträge hat eine Seite des Verlaufs – wie WhatsApp: die neuesten, ältere beim
#: Rollen.
PAGE = 30
#: Ein Cursor: (Zeitpunkt, id) – geliefert wird, was **davor** liegt.
Before = tuple[datetime, int]


def scope(db: Session, object_id: int) -> list[int]:
    """►►► **Wessen Nachrichten im Verlauf eines Datensatzes stehen** (Regel 2). ◄◄◄ Eine
    Firma spiegelt ihre Personen (dazu, was sie selbst betrifft); jeder andere Datensatz ist
    er selbst – eine Person als Absenderin oder Beteiligte, alles andere über «Betrifft».
    (Personen hat nur eine Firma: ``company_object_id`` zeigt auf nichts anderes.)"""
    return [object_id, *(oid for (oid,) in db.query(UserProfile.object_id).filter(
        UserProfile.company_object_id == object_id, UserProfile.object_id.isnot(None)).all())]


_INVOLVED = ("(m.sender_object_id = ANY(:t) OR m.id IN ("
             "SELECT message_id FROM message_parties WHERE object_id = ANY(:t)))")

_PAGE = text(f"""
SELECT m.id, m.at, m.group_id FROM messages m
 WHERE m.is_active AND {_INVOLVED} AND (m.at, m.id) < (:bat, :bid)
 ORDER BY m.at DESC, m.id DESC LIMIT :n""")

#: ►► **Ein Rundschreiben steht im Verlauf EINMAL.** ◄◄ Je Gruppe die Kopie an diese
#:    Person(en), sonst die erste – unter den Kopien, die im Verlauf stehen; dazu, an wie
#:    viele es ging. Ohne Zustand: eine Kopie erscheint, wenn sie die gewählte ist – so
#:    bleibt eine Gruppe auch über eine Seitengrenze hinweg eine Zeile.
_GROUPS = text(f"""
SELECT m.group_id, count(*) AS n,
       min(m.id) FILTER (WHERE {_INVOLVED} AND EXISTS (
           SELECT 1 FROM message_parties p WHERE p.message_id = m.id AND p.role = 'to'
              AND p.object_id = ANY(:t))) AS mine,
       min(m.id) FILTER (WHERE {_INVOLVED}) AS first
  FROM messages m WHERE m.group_id = ANY(:g) AND m.is_active GROUP BY m.group_id""")

#: Die unerreichbare Grenze – «vor allem».
_END = (datetime(9999, 1, 1, tzinfo=timezone.utc), 2 ** 62)


def page(db: Session, targets: list[int], before: Optional[Before], limit: int
         ) -> tuple[list[tuple[int, datetime]], dict[int, int]]:
    """►►► **Eine Seite des Verlaufs** – die ``limit`` neuesten Nachrichten vor ``before``,
    an denen einer der ``targets`` beteiligt ist (Absender oder Partei), die neueste zuerst;
    dazu je Rundschreiben, an wie viele es ging. ◄◄◄ Gelesen werden nur Nummer und Zeit, in
    Stücken, bis die Seite voll ist – nie der ganze Verlauf."""
    out: list[tuple[int, datetime]] = []
    sizes: dict[int, int] = {}
    if not targets or limit <= 0:
        return out, sizes
    bound = before or _END
    while len(out) < limit:
        batch = db.execute(_PAGE, {"t": targets, "bat": bound[0], "bid": bound[1],
                                   "n": limit * 2}).all()
        if not batch:
            break
        groups = {r.group_id for r in batch if r.group_id}
        reps: dict[int, int] = {}
        if groups:
            for g, n, mine, first in db.execute(_GROUPS, {"t": targets, "g": list(groups)}):
                reps[g] = mine or first
                sizes[mine or first] = n
        for r in batch:
            if not r.group_id or reps.get(r.group_id) == r.id:
                out.append((r.id, r.at))
                if len(out) == limit:
                    break
        bound = (batch[-1].at, batch[-1].id)
        if len(batch) < limit * 2:
            break
    shown = {i for i, _ in out}
    return out, {k: v for k, v in sizes.items() if k in shown}


def _names(db: Session, ids: Iterable[int]) -> dict[int, str]:
    """Wie ein beteiligter Datensatz heisst, der keine Person ist («Auftrag · …»)."""
    from .record_labels import labels
    return {k: r.label for k, r in labels(db, ids).items()}


def load(db: Session, ids: list[int]) -> list[MessageOut]:
    if not ids:
        return []
    msgs = db.query(Message).filter(Message.id.in_(ids)).order_by(Message.at, Message.id).all()
    parties = db.query(MessageParty).filter(MessageParty.message_id.in_(ids)).all()
    people = _people(db, [m.sender_object_id for m in msgs] + [p.object_id for p in parties])
    names = _names(db, ({p.object_id for p in parties}
                        | {m.sender_object_id for m in msgs}) - set(people))
    by_msg: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for p in parties:
        by_msg[p.message_id][p.role].append(p.object_id)
    done = answered(db, [m.id for m in msgs])
    lost = failed(db, [m.id for m in msgs])
    now = clock.utcnow()
    labels = _labels(db, [m.channel for m in msgs])
    firms = _firms(db, people)
    out = [_out(m, by_msg[m.id], m.id in done, people, now, labels, firms, names)
           for m in msgs]
    for o in out:
        o.failed = o.id in lost
    return out


def _state(m, roles: dict[str, list[int]], answered: bool,
           staff: Callable[[int], bool], now: datetime) -> tuple[bool, bool]:
    """►►► **Offen und überfällig – die EINE Regel** (Regel 3). ◄◄◄ Gelesen vom Verlauf
    (``_out``) **und** vom Zeichen im Feed (``open_counts``): zwei Fassungen hiessen
    zwei Zahlen für dieselbe Nachricht."""
    at = _aware(m.at)
    is_open = (at <= now and not answered and dc.to_us(
        channel_key=m.channel, inbound=m.inbound,
        to_staff=any(staff(i) for i in roles.get("to", []))))
    return is_open, is_open and now - at > dc.OVERDUE_AFTER


def _out(m: Message, roles: dict[str, list[int]], answered: bool,
         people: dict[int, UserProfile], now: datetime,
         labels: dict[str, tuple[str, Optional[str]]],
         firms: Optional[dict[int, str]] = None,
         names: Optional[dict[int, str]] = None) -> MessageOut:
    from .mailbox import gmail_url

    def ref(i: int) -> PersonRef:
        """Eine Person wie immer; ein anderer Datensatz («Betrifft», die Gesellschaft als
        Absenderin einer automatischen Mail) mit seinem Namen."""
        if i in people or not names or i not in names:
            return _ref(people, i, firms)
        return PersonRef(object_id=i, name=names[i])
    sender = ref(m.sender_object_id)
    refs = {r: [ref(i) for i in roles.get(r, [])] for r in dc.ROLES}
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
        ours=not m.inbound, open=is_open,
        overdue=overdue, planned=at > now,
        pending=bool(m.outgoing), attachments=m.attachments or [],
        gmail_url=gmail_url(address, m) if address else None,
        delivery=dc.delivery_of(m.group_id, m.newsletter),
    )


#: Die Nachrichten, die an uns gehen können und nicht beantwortet sind – Kandidatinnen für
#: «offen». Was wir selbst hinausschicken, ist nie offen; ein stiller Kanal (Gespräch,
#: Notiz) auch nicht. Was hier steht, entscheidet danach ``_state`` – die eine Regel.
_UNANSWERED = text(f"""{_STAFF}
SELECT m.id, m.at, m.channel, m.sender_object_id, m.inbound FROM messages m
 WHERE m.is_active AND m.at <= :now AND m.channel <> ALL(:quiet)
   AND (m.inbound
        OR m.id IN (SELECT t.message_id FROM message_parties t
                     WHERE t.role = 'to' AND t.object_id IN (SELECT object_id FROM staff)))
   AND NOT {_ANSWERED}""")


def open_counts(db: Session) -> list[OpenCount]:
    """**Das Zeichen im Feed**: je Person die offenen Nachrichten in ihrem Verlauf.

    Dieselbe Regel wie im Verlauf (``_state``, ``_ANSWERED``) – gezählt wird bei **jedem**
    Beteiligten. **Gezählt, nicht gebaut**: die Datenbank liefert nur, was an uns geht und
    unbeantwortet ist (``_UNANSWERED``) – ein paar Zeilen statt des ganzen Bestands; erst
    für sie werden Beteiligte geladen und ``_state`` gefragt."""
    params = {**_rule_params(), "quiet": [k for k in dc.CHANNELS if dc.quiet(k)]}
    msgs = db.execute(_UNANSWERED, params).all()
    if not msgs:
        return []
    roles: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for mid, oid, role in db.query(MessageParty.message_id, MessageParty.object_id,
                                   MessageParty.role).filter(
            MessageParty.message_id.in_([m.id for m in msgs])).all():
        roles[mid][role].append(oid)
    everyone = {m.sender_object_id for m in msgs} | {
        i for r in roles.values() for ids in r.values() for i in ids}
    staff = {oid for (oid,) in db.query(UserProfile.object_id).filter(
        UserProfile.object_id.in_(everyone), UserProfile.role.in_(STAFF_ROLES)).all()}
    now = params["now"]
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for m in msgs:
        is_open, overdue = _state(m, roles[m.id], False, staff.__contains__, now)
        if not is_open:
            continue
        r = roles[m.id]
        involved = {m.sender_object_id, *(i for k in dc.ROLES
                                          for i in r.get(k, []))}
        for oid in involved:
            counts[oid][0] += 1
            counts[oid][1] += int(overdue)
    return [OpenCount(object_id=k, open=v[0], overdue=v[1]) for k, v in counts.items()]


@dataclass(frozen=True)
class OpenThread:
    """Ein offenes Anliegen als Aufgabe (``services/tasks``): wo es steht, seit wann, und – an
    eine Mitarbeiterin intern – nur für sie."""
    place: int
    topic: str
    at: datetime
    only: Optional[int]


def open_threads(db: Session) -> list[OpenThread]:
    """►► **Die offenen Anliegen** – dieselbe Regel wie im Verlauf und am Zeichen (``_state``).
    Von aussen: am Absender (eine fremde Person). Intern an Personal: an jeder Angesprochenen,
    nur für sie. Je Ort und Anliegen eines, mit der ältesten offenen Nachricht. ◄◄"""
    params = {**_rule_params(), "quiet": [k for k in dc.CHANNELS if dc.quiet(k)]}
    msgs = db.execute(_UNANSWERED, params).all()
    if not msgs:
        return []
    ids = [m.id for m in msgs]
    roles: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for mid, oid, role in db.query(MessageParty.message_id, MessageParty.object_id,
                                   MessageParty.role).filter(
            MessageParty.message_id.in_(ids)).all():
        roles[mid][role].append(oid)
    topics = dict(db.query(Message.id, Message.topic).filter(Message.id.in_(ids)).all())
    everyone = {m.sender_object_id for m in msgs} | {
        i for r in roles.values() for v in r.values() for i in v}
    staff = {oid for (oid,) in db.query(UserProfile.object_id).filter(
        UserProfile.object_id.in_(everyone), UserProfile.role.in_(STAFF_ROLES)).all()}
    now = params["now"]
    found: dict[tuple[int, str], OpenThread] = {}
    for m in msgs:
        is_open, _ = _state(m, roles[m.id], False, staff.__contains__, now)
        if not is_open:
            continue
        topic = topics.get(m.id) or ""
        places = ([(m.sender_object_id, None)] if m.inbound else
                  [(i, i) for i in roles[m.id].get("to", []) if i in staff])
        for place, only in places:
            at = _aware(m.at)
            old = found.get((place, topic))
            if old is None or at < old.at:
                found[(place, topic)] = OpenThread(place=place, topic=topic, at=at, only=only)
    return list(found.values())


# ---------------------------------------------------------------------------
# Korrektur statt Löschen
# ---------------------------------------------------------------------------

def move_note(db: Session, message_id: int, to_object_id: int, actor: UserProfile
              ) -> tuple[Message, Message]:
    """►►► **Eine Notiz gehört woandershin – korrigiert wird, nicht gelöscht.** ◄◄◄

    **Eine Heimat**: gültig ist immer genau ein Datensatz. Am falschen steht danach ein
    Vermerk «ungültig – gehört zu <Nummer Name>», der die Notiz nennt (Betreff und
    Zeitpunkt); am richtigen ihr Inhalt mit dem Verweis «verschoben von …». Die Notiz selbst
    bleibt, wie sie war – die Geschichte ändert sich nicht. Beide Einträge gehen durch
    ``create`` (dieselben Regeln, derselbe Handelnde). Gibt (Vermerk, neue Notiz) zurück.

    Angestossen wird das heute nur im Dienst (die KI schlägt es in Phase 3 vor)."""
    from .objects import obj_nr
    note = db.query(Message).filter(Message.id == message_id, Message.is_active.is_(True)).first()
    if note is None or note.channel != dc.NOTE:
        raise NotFound("Diese Notiz gibt es nicht.")
    home = [oid for (oid,) in db.query(MessageParty.object_id).filter(
        MessageParty.message_id == note.id, MessageParty.role == "about").all()]
    if to_object_id in home:
        raise Invalid(f"Die Notiz gehört schon zu «{obj_nr(to_object_id)}».")
    _assert_records(db, {to_object_id})
    names = {**_names(db, [to_object_id, *home]),
             **{k: u.display_name for k, u in _people(db, [to_object_id, *home]).items()}}

    def called(oid: int) -> str:
        return f"{obj_nr(oid)} {names[oid]}" if names.get(oid) else obj_nr(oid)
    subject = note.subject or "Notiz"
    when = clock.stamp(_aware(note.at))
    void = create(db, MessageIn(
        channel=dc.NOTE, about=home, subject=subject,
        body=f"Ungültig – gehört zu {called(to_object_id)}: die Notiz «{subject}» "
             f"vom {when}."), actor)
    origin = ", ".join(called(o) for o in home) or called(note.sender_object_id)
    moved = create(db, MessageIn(
        channel=dc.NOTE, about=[to_object_id], subject=subject,
        body=f"{note.body}\n\nVerschoben von {origin} (Notiz vom {when})."), actor)
    return void, moved
