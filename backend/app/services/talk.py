"""►►► **Das Gespräch – du sagst, was ist; die KI redet mit und bereitet vor.** ◄◄◄
(Projektakte, Phase 5 §7)

Ein Gespräch ist eine Folge von Ereignissen ``talk`` im Log: die Nachrichten der Person
(``by: person``) und der KI (``by: ai``, im Namen der Person). Die erste Nachricht IST das
Gespräch (ihre Id); jede weitere nennt es (``talk``). Was die KI vorbereitet, sind Handgriffe
(``services/handgriff``) mit derselben ``talk``.

* **Privat:** ein Gespräch sieht nur, wer es führt, und der Admin.
* **Offen**, solange darin ein Handgriff offen ist oder die KI noch nicht geantwortet hat –
  sonst abgeschlossen und nicht mehr gezeigt (im Log bleibt alles).
* **Die KI** liest, was jedes Personal sehen darf (``ai_tools.reader``), schlägt Handlungen nach
  (``handgriff.find``), bereitet vor (Probelauf mit den Rechten der Person) und führt nur aus,
  wenn die Person es sagt. Fällt sie aus, bleibt das Gespräch Text; der Takt antwortet nach.
"""

from __future__ import annotations

import base64
import json
import queue
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterator, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core import clock, locks
from ..models import UserProfile
from ..schemas.assistant import FileRef, TalkMessage, TalkOut
from . import ai, handgriff, log, record_labels
from ..domain.errors import Forbidden, Invalid, NotFound, Rejected
from ..domain import policy
from ..core import report

#: Der Auftrag an die KI – wörtlich, eine Datei.
AUFTRAG = (Path(__file__).resolve().parents[1] / "assets" / "ai" / "auftrag.md").read_text("utf-8")
#: So lang darf eine getippte Nachricht sein; eine abgeschriebene Aufnahme länger.
MAX_TEXT = 20000
MAX_SPOKEN = 200_000
#: So viele Gespräche holt der Takt je Lauf nach – und so lange und so oft.
CATCH_UP = 3
CATCH_UP_DAYS = 7
TRIES = 3
#: So gross darf eine Datei sein, die die KI liest.
READ_LIMIT = 8 * 1024 * 1024

#: Steuerzeichen, die PostgreSQL nicht aufnimmt (NUL) oder die nur stören – Tab und
#: Zeilenumbruch bleiben (die Stecknadel liest Text aus einer Seite).
_CONTROL = dict.fromkeys([*range(0, 9), 11, 12, *range(14, 32)])


def clean(body: str) -> str:
    return (body or "").translate(_CONTROL)


FORMAT = """
Deine Antwort an die Person: direkt auf das, was sie sagt oder fragt, kurz. Formatieren darfst du
mit Markdown, wo es lesbarer wird (fett, Listen, Überschriften, Code). Erzähl nicht, was du nicht
getan hast. Was
folgt, bereitest du mit `vorbereiten` als Vorschlag vor (je Handlung einer), bevor du antwortest –
auch wenn Werte fehlen, die nur die Person kennt: dann füllst du, was du weisst, und sie ergänzt
es, wo sie den Vorschlag öffnet; frag nicht vorher danach. Ausführen tust du nie: die Person
öffnet jeden Vorschlag dort, wo er wirkt, und übernimmt ihn selbst. Die Handlungen des ERP stehen
unten; ihre Felder liest du mit `handlung`, was das ERP zeigt (Listen, Auswahlen, Bestand,
Module) mit `abrufen`. Wissen (was ist, was gesagt wurde) legst du als Notiz am richtigen
Datensatz ab: Handlung «POST /api/v1/erp/messages» mit `channel` "note", `about` = der Datensatz,
`subject` und `body`.
"""


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------

_MESSAGES = text("""
SELECT id, at, actor_id, object_id, payload FROM log
 WHERE event = 'talk' AND (id = :t OR (payload ->> 'talk')::bigint = :t)
 ORDER BY id""")

_HANDGRIFFE = text("""
SELECT id FROM log WHERE event = 'handgriff' AND (payload ->> 'talk')::bigint = :t ORDER BY id""")


def _first(db: Session, talk_id: int) -> Any:
    r = db.execute(text("SELECT id, at, actor_id, object_id, payload FROM log "
                        "WHERE id = :t AND event = 'talk' AND payload ->> 'talk' IS NULL"),
                   {"t": talk_id}).first()
    if r is None:
        raise NotFound(f"Gespräch «{talk_id}» gibt es nicht.")
    return r


def assert_may(db: Session, talk_id: int, viewer: UserProfile) -> Any:
    """Ein Gespräch ist privat: wer es führt, und der Admin."""
    r = _first(db, talk_id)
    if not policy.may(viewer, "private", r.actor_id):
        raise NotFound(f"Gespräch «{talk_id}» gibt es nicht.")
    return r


def view(db: Session, talk_id: int, *, problem: Optional[str] = None) -> TalkOut:
    """►► **Ein Gespräch, wie die Oberfläche es zeigt.** ◄◄"""
    first = _first(db, talk_id)
    rows = db.execute(_MESSAGES, {"t": talk_id}).all()
    messages = [TalkMessage(id=r.id, at=r.at, by=(r.payload or {}).get("by") or "person",
                            text=str((r.payload or {}).get("text") or ""),
                            files=[FileRef(**f) for f in (r.payload or {}).get("files") or []])
                for r in rows]
    # Was die KI selbst weglegte (ersetzt), ist kein Ergebnis – die Person sieht nur, was gilt.
    found = handgriff.view(db, [h for h in handgriff.load(db, [r.id for r in db.execute(_HANDGRIFFE, {"t": talk_id})])
                                if not h.replaced])
    waiting = bool(messages) and messages[-1].by == "person"
    is_open = waiting or any(h.state in ("open", "waiting") for h in found)
    if waiting and not problem:
        problem = _failure(db, talk_id) or WAITING
    return TalkOut(id=talk_id, at=first.at, hint_object_id=(first.payload or {}).get("hint"),
                   messages=messages, handgriffe=found, open=is_open, waiting=waiting,
                   problem=problem or None)


#: Das Gespräch wartet auf die KI, ohne dass ein Fehlschlag festgehalten ist.
WAITING = "Die KI hat noch nicht geantwortet – der Takt holt es nach."


def _failure(db: Session, talk_id: int) -> Optional[str]:
    return db.execute(text("SELECT payload ->> 'problem' FROM log WHERE event = 'talk.failed' "
                           "AND (payload ->> 'talk')::bigint = :t ORDER BY id DESC LIMIT 1"),
                      {"t": talk_id}).scalar()


#: «Offen» – EINE Abfrage: ein offener Handgriff im Gespräch, oder die letzte Nachricht ist von
#: der Person (die KI hat noch nicht geantwortet).
_OPEN = text("""
SELECT t.id FROM log t
 WHERE t.event = 'talk' AND t.payload ->> 'talk' IS NULL AND t.actor_id = :me
   AND (EXISTS (SELECT 1 FROM log h WHERE h.event = 'handgriff'
                  AND (h.payload ->> 'talk')::bigint = t.id
                  AND NOT EXISTS (SELECT 1 FROM log x
                                   WHERE x.event IN ('handgriff.done', 'handgriff.dropped')
                                     AND (x.payload ->> 'handgriff')::bigint = h.id))
        OR (SELECT m.payload ->> 'by' FROM log m
             WHERE m.event = 'talk' AND (m.id = t.id OR (m.payload ->> 'talk')::bigint = t.id)
             ORDER BY m.id DESC LIMIT 1) = 'person')
 ORDER BY t.id DESC LIMIT :n""")


def open_ids(db: Session, viewer: UserProfile, limit: int = 50) -> list[int]:
    """Meine offenen Gespräche – die neuesten zuerst (die Zahl am «+»)."""
    return [r.id for r in db.execute(_OPEN, {"me": viewer.object_id or 0, "n": limit})]


# ---------------------------------------------------------------------------
# Sagen
# ---------------------------------------------------------------------------

def say(db: Session, person: UserProfile, body: str, *, talk: Optional[int] = None,
        hint: Optional[int] = None, files: Optional[list[FileRef]] = None,
        recordings: Optional[list[int]] = None) -> int:
    """►►► **Die Person sagt etwas** – eine Nachricht ``talk``, sofort. Ohne ``talk`` beginnt ein
    Gespräch (am offenen Datensatz ``hint``, sonst an der Person). ``recordings`` = die Aufnahmen,
    deren Text darin steht (erst jetzt gelten sie als gesendet). Gibt das Gespräch zurück. ◄◄◄"""
    recordings = sorted(set(recordings or []))
    body = clean(body).strip()
    if not body and not files:
        raise Invalid("Eine Nachricht braucht Text oder eine Datei.")
    limit = MAX_SPOKEN if recordings else MAX_TEXT
    if len(body) > limit:
        raise Invalid(f"Die Nachricht ist zu lang ({len(body)} Zeichen).")
    if recordings:
        from . import recordings as spoken
        for rid in recordings:
            if spoken.load(db, rid).actor_id != person.object_id:
                raise Forbidden(f"Aufnahme «{rid}» ist nicht deine.")
    if talk is not None:
        first = assert_may(db, talk, person)
        home = first.object_id
    else:
        if hint is not None and record_labels.labels(db, [hint]).get(hint) is None:
            raise Invalid(f"Datensatz «{hint}» gibt es nicht.")
        home = hint or person.object_id
    payload: dict[str, Any] = {"by": "person", "text": body[:limit]}
    if talk is not None:
        payload["talk"] = talk
    else:
        payload["hint"] = hint
    if files:
        payload["files"] = [f.model_dump() for f in files]
    if recordings:
        payload["recordings"] = recordings
    mid = log.event(db, "talk", home, payload, kind="person", actor=person.object_id)
    return talk or mid


def _reply(db: Session, person: UserProfile, talk_id: int, body: str, home: int) -> None:
    log.event(db, "talk", home, {"talk": talk_id, "by": "ai", "text": body.strip()[:MAX_TEXT]},
              kind="ai", actor=person.object_id)


# ---------------------------------------------------------------------------
# Die KI
# ---------------------------------------------------------------------------

def _transcript(db: Session, talk_id: int, person: UserProfile) -> list[dict[str, Any]]:
    """Das Gespräch, wie die KI es liest – der offene Datensatz gleich dabei (wie ihn jedes
    Personal sieht), die Dateien als Bild bzw. PDF."""
    from . import ai_tools, attachments, memory
    first = _first(db, talk_id)
    hint = (first.payload or {}).get("hint")
    now = clock.stamp(clock.now())
    head = [f"Heute: {now}. Es spricht {person.display_name} ({person.object_id}, "
            f"Rolle {person.role})."]
    if hint:
        rec = record_labels.labels(db, [hint]).get(hint)
        head.append(f"Offen war der Datensatz {hint}" + (f" ({rec.type}: {rec.name})." if rec else ".")
                    + "\n" + ai_tools.record(db, ai_tools.reader(), hint))
    blocks: list[dict[str, Any]] = [{"type": "text", "text": "\n".join(head)}]
    t = view(db, talk_id)
    said = " ".join(m.text for m in t.messages if m.by == "person")[-4000:]
    cases = memory.as_prompt(memory.search(db, said, actor=person, kinds=("handgriff",)))
    if cases:
        blocks.append({"type": "text", "text": cases})
    for m in t.messages:
        who = "Person" if m.by == "person" else "Du"
        blocks.append({"type": "text", "text": f"{who} ({m.at:%d.%m. %H:%M}): {m.text}"})
        for f in m.files:
            try:
                raw = attachments.bytes_of(attachments.get_by_token(db, f.token))
            except Rejected:
                raw = b""
            if not raw or len(raw) > READ_LIMIT:
                blocks.append({"type": "text", "text": f"[Datei {f.name}: nicht lesbar]"})
            elif f.mime.startswith("image/"):
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": f.mime,
                                                           "data": base64.b64encode(raw).decode()}})
            elif f.mime == "application/pdf":
                blocks.append({"type": "document", "source": {"type": "base64",
                               "media_type": "application/pdf",
                               "data": base64.b64encode(raw).decode()}})
            blocks.append({"type": "text", "text": f"[Datei «{f.name}» – Schlüssel {f.token}]"})
    if t.handgriffe:
        lines = ["Vorschläge in diesem Gespräch:"]
        lines += [f"- [{h.id}] {h.state}: {h.line} ({h.method} {h.path})" for h in t.handgriffe]
        blocks.append({"type": "text", "text": "\n".join(lines)})
    return blocks


def _mine(db: Session, talk_id: int, hid: int) -> handgriff.Handgriff:
    """Ein Handgriff **dieses** Gesprächs – die KI greift nie nach einem anderen (einer Mail,
    einem fremden Gespräch)."""
    h = handgriff.get(db, hid)
    if h.talk != talk_id:
        raise Forbidden(f"Handgriff «{hid}» gehört nicht zu diesem Gespräch.")
    return h


def _last_said(db: Session, talk_id: int) -> int:
    """Die letzte Nachricht der Person in diesem Gespräch (Log-Id)."""
    return int(db.execute(text(
        "SELECT coalesce(max(id), 0) FROM log WHERE event = 'talk' AND payload ->> 'by' = 'person' "
        "AND (id = :t OR (payload ->> 'talk')::bigint = :t)"), {"t": talk_id}).scalar() or 0)


def tools(db: Session, person: UserProfile, talk_id: int, home: int) -> list[ai.Tool]:
    """Lesen wie jedes Personal (``ai_tools``), dazu die Handlungen des ERP: Felder nachlesen,
    abrufen, vorbereiten (mit Probelauf), weglegen. **Ausführen gibt es nicht** – die Person
    übernimmt jeden Vorschlag selbst, dort, wo er wirkt. Die Liste der Handlungen steht im Auftrag
    (``ai_tools.catalog``), darum fehlt das Nachschlagen nach Stichwörtern."""
    from . import ai_tools

    def prepare(method: str, path: str, body: Any, line: str, depends: list[int]):
        return handgriff.prepare(db, person, method=method, path=path, body=body, line=line,
                                 home=home, talk=talk_id, depends=depends)

    def drop(a: dict[str, Any]) -> str:
        h = _mine(db, talk_id, int(a.get("handgriff") or 0))
        handgriff.drop(db, person, h.id, by="ai")
        return f"Handgriff {h.id} ist weggelegt."

    return [*ai_tools.tools_for(db), *ai_tools.erp_tools(prepare, lookup=False),
            ai.Tool("weglegen", "Einen Vorschlag dieses Gesprächs weglegen (die Person will ihn "
                    "nicht, oder du ersetzt ihn durch einen neuen).",
                    {"handgriff": {"type": "integer"}}, drop, doing="legt weg: Vorschlag")]


def _claim(db: Session, talk_id: int) -> bool:
    """Die Sperre auf dieses Gespräch, bis zum Ende der Transaktion – ``False``, wenn schon
    jemand antwortet."""
    return locks.xact(db, locks.TALK, talk_id, wait=False)


def _waiting(db: Session, talk_id: int) -> bool:
    """Ist die letzte Nachricht von der Person (die KI ist dran)?"""
    return db.execute(text(
        "SELECT payload ->> 'by' FROM log WHERE event = 'talk' "
        "AND (id = :t OR (payload ->> 'talk')::bigint = :t) ORDER BY id DESC LIMIT 1"),
        {"t": talk_id}).scalar() == "person"


def _stopped(db: Session, talk_id: int) -> bool:
    """Hat die Person seit ihrer letzten Nachricht «Stopp» gedrückt (``talk.stop``)?"""
    return bool(db.execute(text(
        "SELECT EXISTS (SELECT 1 FROM log WHERE event = 'talk.stop' "
        "AND (payload ->> 'talk')::bigint = :t AND id > :said)"),
        {"t": talk_id, "said": _last_said(db, talk_id)}).scalar())


#: Warum keine Antwort kam: jemand anders (Stream oder Takt) antwortet gerade.
BUSY = "Die KI antwortet schon."
#: Die Antwort, wenn die Person anhielt – sie schliesst den Zug (der Takt holt nichts nach).
HALTED = "Angehalten."


def answer(db: Session, talk_id: int, person: UserProfile, *,
           on_step: Optional[Callable[[str], None]] = None,
           on_text: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """►►► **Die KI antwortet** – liest, bereitet vor, antwortet. ``None`` = sie hat geantwortet
    (oder es war nichts zu tun), sonst warum nicht (``ai.problem``). ``on_step`` hört jeden
    Schritt, ``on_text`` jedes Stück ihrer Antwort (live im «+»). Antwortet schon jemand (Stream
    oder Takt), wartet diese Antwort nicht darauf.

    **Schnell, weil sie mitbekommt, was sie braucht:** den offenen Datensatz (im Gespräch) und die
    Liste der Handlungen (im Auftrag, im Zwischenspeicher) – sie schlägt nicht erst nach. ◄◄◄"""
    from . import ai_tools
    first = _first(db, talk_id)
    if not _claim(db, talk_id):
        return BUSY
    if not _waiting(db, talk_id):
        return None
    content = _transcript(db, talk_id, person) if ai.available(db) else []
    said = ai.converse(db, task="talk", actor=person,
                       system=AUFTRAG + "\n" + FORMAT + "\n" + ai_tools.catalog(),
                       content=content, schema=None,
                       tools=tools(db, person, talk_id, first.object_id),
                       on_step=on_step, on_text=on_text, stopped=lambda: _stopped(db, talk_id))
    if said is None and ai.problem() == ai.STOPPED:
        _reply(db, person, talk_id, HALTED, first.object_id)
        return None
    if said is None:
        return ai.problem() or "Die KI hat nicht geantwortet."
    _reply(db, person, talk_id, said or "Erledigt.", first.object_id)
    return None


def stop(db: Session, person: UserProfile, talk_id: int) -> None:
    """**Stopp** – die KI hält vor ihrem nächsten Schritt an (``talk.stop``, über alle Instanzen
    hinweg: ein Ereignis, kein Merker im Speicher). Was sie schon vorbereitete, bleibt."""
    first = assert_may(db, talk_id, person)
    log.event(db, "talk.stop", first.object_id, {"talk": talk_id}, kind="person",
              actor=person.object_id)


#: Ein Lebenszeichen im Stream, solange die KI arbeitet – keine Leitung schläft ein.
ALIVE_S = 15


def stream(person_id: int, talk_id: int) -> Iterator[bytes]:
    """►►► **Die Antwort live** (Projektakte, «wie Claude»): je Zeile ein JSON – zuerst ``{"talk": …}``
    (die Nachricht steht), dann ``{"step": …}`` je Schritt der KI und ``{"text": …}`` je Stück ihrer
    Antwort, am Ende ``{"talk": …}`` (das Gespräch, wie die Oberfläche es zeigt).
    Die KI arbeitet in eigenem Faden und eigener Sitzung; reisst die Leitung ab, arbeitet sie
    zu Ende und speichert – das Gespräch zeigt es beim nächsten Öffnen. Begrenzt durch Schritte,
    Deckel und «Stopp», nicht durch eine Uhr. ◄◄◄"""
    lines: queue.Queue[Optional[dict[str, Any]]] = queue.Queue()
    threading.Thread(target=_answer_alone, args=(person_id, talk_id, lines.put),
                     daemon=True, name=f"talk-{talk_id}").start()
    while True:
        try:
            item = lines.get(timeout=ALIVE_S)
        except queue.Empty:
            yield b"\n"
            continue
        if item is None:
            return
        yield (json.dumps(item, ensure_ascii=False, default=str) + "\n").encode()


@contextmanager
def _own_session() -> Iterator[Session]:
    from ..core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#: Woher die Antwort ihre Sitzung hat – eine eigene, unabhängig von der Anfrage (die Tests
#: geben hier ihre Testsitzung).
OWN_SESSION: Callable[[], ContextManager[Session]] = _own_session


def _answer_alone(person_id: int, talk_id: int, put: Callable[[Optional[dict[str, Any]]], None]) -> None:
    """Die Antwort in eigener Sitzung – im Namen der Person, gespeichert am Ende."""
    try:
        with OWN_SESSION() as db:
            _answer_in(db, person_id, talk_id, put)
    finally:
        put(None)


def _answer_in(db: Session, person_id: int, talk_id: int,
               put: Callable[[Optional[dict[str, Any]]], None]) -> None:
    from ..core.actor import act
    try:
        person = db.query(UserProfile).filter(UserProfile.id == person_id).first()
        if person is None:
            put({"error": "Diese Person gibt es nicht."})
            return
        act(db, "person", person.object_id, "ui")
        put({"talk": view(db, talk_id).model_dump(mode="json")})     # die Nachricht steht sofort
        trouble = answer(db, talk_id, person, on_step=lambda st: put({"step": st}),
                         on_text=lambda piece: put({"text": piece}))
        if trouble and trouble != BUSY and ai.available(db):
            log.event(db, "talk.failed", None, {"talk": talk_id, "problem": trouble})
        db.commit()
        put({"talk": view(db, talk_id, problem=trouble).model_dump(mode="json")})
    except Exception as exc:                                   # noqa: BLE001
        db.rollback()
        report.warn(f"talk {talk_id} failed: {exc!r}")
        put({"error": "Die KI ist gestolpert – deine Nachricht ist gespeichert, der Takt antwortet nach."})


# ---------------------------------------------------------------------------
# Der Takt
# ---------------------------------------------------------------------------

_WAITING = text("""
SELECT t.id FROM log t
 WHERE t.event = 'talk' AND t.payload ->> 'talk' IS NULL
   AND t.at >= now() - make_interval(days => :days)
   AND (SELECT m.payload ->> 'by' FROM log m
         WHERE m.event = 'talk' AND (m.id = t.id OR (m.payload ->> 'talk')::bigint = t.id)
         ORDER BY m.id DESC LIMIT 1) = 'person'
   AND (SELECT max(m.at) FROM log m
         WHERE m.event = 'talk' AND (m.id = t.id OR (m.payload ->> 'talk')::bigint = t.id))
       < now() - interval '1 minute'
   AND (SELECT count(*) FROM log f WHERE f.event = 'talk.failed'
          AND (f.payload ->> 'talk')::bigint = t.id) < :tries
 ORDER BY t.id LIMIT :n""")


def catch_up(db: Session, deadline: float, limit: int = CATCH_UP) -> int:
    """►►► **Nachholen, worauf die KI nicht antwortete** – im Namen der Person. Ein
    Fehlschlag, der nicht am Deckel lag, zählt (``talk.failed``); nach ``TRIES`` bleibt das
    Gespräch für den Menschen. Speichert je Gespräch. ◄◄◄"""
    n = 0
    for (tid,) in db.execute(_WAITING, {"days": CATCH_UP_DAYS, "tries": TRIES, "n": limit}).all():
        if time.monotonic() >= deadline or not ai.available(db):
            break
        first = _first(db, tid)
        person = db.query(UserProfile).filter(UserProfile.object_id == first.actor_id).first()
        if person is None:
            continue
        trouble = answer(db, tid, person)
        if trouble is None:
            n += 1
        elif trouble != BUSY and ai.available(db):
            log.event(db, "talk.failed", None, {"talk": tid, "problem": trouble})
        db.commit()
    return n
