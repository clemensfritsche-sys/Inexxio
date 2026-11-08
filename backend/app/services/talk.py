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
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core import clock
from ..models import UserProfile
from ..schemas.assistant import FileRef, TalkMessage, TalkOut
from . import ai, handgriff, log, records

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


class Answer(BaseModel):
    """Was die KI sagt – kurz, wie man im Betrieb redet. Die Handgriffe hat sie mit
    ``vorbereiten`` schon angelegt; hier nennt sie sie nicht noch einmal."""
    text: str = Field(description="Deine Antwort an die Person, kurz und schlicht")


FORMAT = """
Antwortformat: `text` – deine Antwort. Was folgt, bereitest du mit dem Werkzeug `vorbereiten`
vor (je Handlung ein Handgriff), bevor du antwortest; in `text` sagst du kurz, was du vorbereitet
hast und was du wissen müsstest. Wissen (was ist, was gesagt wurde) legst du als Notiz am
richtigen Datensatz ab: Handlung «POST /api/v1/erp/messages» mit `channel` "note", `about` = der
Datensatz, `subject` und `body`.
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
        raise HTTPException(404, detail=f"Gespräch «{talk_id}» gibt es nicht.")
    return r


def assert_may(db: Session, talk_id: int, viewer: UserProfile) -> Any:
    """Ein Gespräch ist privat: wer es führt, und der Admin."""
    r = _first(db, talk_id)
    if viewer.role != "admin" and r.actor_id != viewer.object_id:
        raise HTTPException(404, detail=f"Gespräch «{talk_id}» gibt es nicht.")
    return r


def view(db: Session, talk_id: int, *, problem: Optional[str] = None) -> TalkOut:
    """►► **Ein Gespräch, wie die Oberfläche es zeigt.** ◄◄"""
    first = _first(db, talk_id)
    rows = db.execute(_MESSAGES, {"t": talk_id}).all()
    messages = [TalkMessage(id=r.id, at=r.at, by=(r.payload or {}).get("by") or "person",
                            text=str((r.payload or {}).get("text") or ""),
                            files=[FileRef(**f) for f in (r.payload or {}).get("files") or []])
                for r in rows]
    found = handgriff.view(db, handgriff.load(db, [r.id for r in db.execute(_HANDGRIFFE, {"t": talk_id})]))
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
        recording: Optional[int] = None) -> int:
    """►►► **Die Person sagt etwas** – eine Nachricht ``talk``, sofort. Ohne ``talk`` beginnt ein
    Gespräch (am offenen Datensatz ``hint``, sonst an der Person). Gibt das Gespräch zurück. ◄◄◄"""
    body = clean(body).strip()
    if not body and not files:
        raise HTTPException(400, detail="Eine Nachricht braucht Text oder eine Datei.")
    if talk is not None:
        first = assert_may(db, talk, person)
        home = first.object_id
    else:
        if hint is not None and records.labels(db, [hint]).get(hint) is None:
            raise HTTPException(400, detail=f"Datensatz «{hint}» gibt es nicht.")
        home = hint or person.object_id
    payload: dict[str, Any] = {"by": "person", "text": body[:MAX_SPOKEN if recording else MAX_TEXT]}
    if talk is not None:
        payload["talk"] = talk
    else:
        payload["hint"] = hint
    if files:
        payload["files"] = [f.model_dump() for f in files]
    if recording:
        payload["recording"] = recording
    mid = log.event(db, "talk", home, payload, kind="person", actor=person.object_id)
    return talk or mid


def _reply(db: Session, person: UserProfile, talk_id: int, body: str, home: int) -> None:
    log.event(db, "talk", home, {"talk": talk_id, "by": "ai", "text": body.strip()[:MAX_TEXT]},
              kind="ai", actor=person.object_id)


# ---------------------------------------------------------------------------
# Die KI
# ---------------------------------------------------------------------------

def _transcript(db: Session, talk_id: int, person: UserProfile) -> list[dict[str, Any]]:
    """Das Gespräch, wie die KI es liest – mit den Dateien als Bild bzw. PDF."""
    from . import attachments, memory
    first = _first(db, talk_id)
    hint = (first.payload or {}).get("hint")
    now = clock.now().strftime("%d.%m.%Y %H:%M")
    head = [f"Heute: {now}. Es spricht {person.display_name} ({person.object_id}, "
            f"Rolle {person.role})."]
    if hint:
        rec = records.labels(db, [hint]).get(hint)
        head.append(f"Offen war der Datensatz {hint}" + (f" ({rec.type}: {rec.name})." if rec else "."))
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
            except HTTPException:
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
        lines = ["Handgriffe in diesem Gespräch:"]
        lines += [f"- [{h.id}] {h.state}: {h.line} ({h.method} {h.path})" for h in t.handgriffe]
        blocks.append({"type": "text", "text": "\n".join(lines)})
    return blocks


def _mine(db: Session, talk_id: int, hid: int) -> handgriff.Handgriff:
    """Ein Handgriff **dieses** Gesprächs – die KI greift nie nach einem anderen (einer Mail,
    einem fremden Gespräch)."""
    h = handgriff.get(db, hid)
    if h.talk != talk_id:
        raise HTTPException(403, detail=f"Handgriff «{hid}» gehört nicht zu diesem Gespräch.")
    return h


def _last_said(db: Session, talk_id: int) -> int:
    """Die letzte Nachricht der Person in diesem Gespräch (Log-Id)."""
    return int(db.execute(text(
        "SELECT coalesce(max(id), 0) FROM log WHERE event = 'talk' AND payload ->> 'by' = 'person' "
        "AND (id = :t OR (payload ->> 'talk')::bigint = :t)"), {"t": talk_id}).scalar() or 0)


def tools(db: Session, person: UserProfile, talk_id: int, home: int, *,
          live: bool = False) -> list[ai.Tool]:
    """Lesen wie jedes Personal (``ai_tools``), dazu die Handlungen des ERP: nachschlagen,
    vorbereiten (mit Probelauf), weglegen. **Ausführen** gibt es nur, wenn die Person gerade
    spricht (``live``) – und nur für einen Handgriff dieses Gesprächs, den sie vor ihrer letzten
    Nachricht schon sah. Im Takt (niemand da) und aus Mails nie: das ist eine Regel im Code, nicht
    nur ein Satz an die KI."""
    from . import ai_tools

    def find_ops(a: dict[str, Any]) -> str:
        found = handgriff.find(str(a.get("woerter") or ""))
        return "\n".join(f"{o.key} – {o.summary}" + (" (nur Admin)" if o.admin else "")
                         + (" (nur von Hand: Datei)" if o.hand else "") for o in found) or "Nichts."

    def describe(a: dict[str, Any]) -> str:
        op = handgriff.operation(str(a.get("handlung") or ""))
        if op is None:
            return "Diese Handlung gibt es nicht – schlage mit `handlungen` nach."
        return f"{op.key}\n{op.summary}\nWerte (JSON-Schema): {json.dumps(op.schema, ensure_ascii=False)}"

    def prepare(a: dict[str, Any]) -> str:
        method, _, path = str(a.get("handlung") or "").partition(" ")
        try:
            body = json.loads(a.get("werte_json") or "null")
        except ValueError as exc:
            return f"Die Werte sind kein JSON: {exc}"
        hid, out = handgriff.prepare(db, person, method=method, path=str(a.get("pfad") or path),
                                     body=body, line=str(a.get("zeile") or ""), home=home,
                                     talk=talk_id, depends=list(a.get("wartet_auf") or []))
        if hid is None:
            return f"Geht nicht ({out.status}): {out.detail}"
        return f"Vorbereitet als Handgriff {hid}" + (f" – geht nur von Hand ({out.hand})." if out.hand else ".")

    def drop(a: dict[str, Any]) -> str:
        h = _mine(db, talk_id, int(a.get("handgriff") or 0))
        handgriff.drop(db, person, h.id, by="ai")
        return f"Handgriff {h.id} ist weggelegt."

    def execute(a: dict[str, Any]) -> str:
        h = _mine(db, talk_id, int(a.get("handgriff") or 0))
        if h.id > _last_said(db, talk_id):
            return ("Nicht ausgeführt: diesen Handgriff hat die Person noch nicht gesehen – "
                    "sie entscheidet an der Karte oder mit ihrer nächsten Nachricht.")
        h, out = handgriff.run(db, person, h.id)
        return f"Ausgeführt ({h.id})." if out.ok else f"Nicht ausgeführt: {out.detail or out.hand}"

    int_list = {"type": "array", "items": {"type": "integer"}}
    return [*ai_tools.tools_for(db),
            ai.Tool("handlungen", "Die Handlungen des ERP zu Stichwörtern (Schlüssel und Satz).",
                    {"woerter": {"type": "string"}}, find_ops),
            ai.Tool("handlung", "Felder und Prüfungen einer Handlung (Schlüssel «METHODE /pfad»).",
                    {"handlung": {"type": "string"}}, describe),
            ai.Tool("vorbereiten", "Einen Handgriff vorbereiten – mit Probelauf. `handlung` ist der "
                    "Schlüssel, `pfad` der konkrete Pfad (Platzhalter durch Nummern ersetzt), "
                    "`werte_json` die Werte als JSON, `zeile` ein Satz, was geschieht, mit Nummer "
                    "und Name. Braucht er, was ein anderer Handgriff anlegt: dessen Nummer in "
                    "`wartet_auf` und in den Werten {\"$handgriff\": nummer}.",
                    {"handlung": {"type": "string"}, "pfad": {"type": "string"},
                     "werte_json": {"type": "string"}, "zeile": {"type": "string"},
                     "wartet_auf": int_list}, prepare),
            ai.Tool("weglegen", "Einen Handgriff dieses Gesprächs weglegen (die Person will ihn "
                    "nicht, oder du ersetzt ihn durch einen neuen).",
                    {"handgriff": {"type": "integer"}}, drop),
            *([ai.Tool("ausfuehren", "Einen Handgriff dieses Gesprächs ausführen – NUR, wenn die "
                       "Person es in ihrer letzten Nachricht ausdrücklich sagt («ja, ausführen», "
                       "«leg es ab»).", {"handgriff": {"type": "integer"}}, execute)] if live else [])]


def answer(db: Session, talk_id: int, person: UserProfile, *, live: bool = False) -> Optional[str]:
    """►►► **Die KI antwortet** – liest, schlägt nach, bereitet vor, antwortet. ``None`` = sie
    hat geantwortet, sonst warum nicht (``ai.problem``). ``live`` = die Person hat eben selbst
    geschrieben (nur dann darf ein Wort von ihr ausführen). ◄◄◄"""
    first = _first(db, talk_id)
    content = _transcript(db, talk_id, person) if ai.available(db) else []
    said = ai.converse(db, task="talk", actor=person, system=AUFTRAG + "\n" + FORMAT,
                       content=content, schema=Answer,
                       tools=tools(db, person, talk_id, first.object_id, live=live))
    if said is None:
        return ai.problem() or "Die KI hat nicht geantwortet."
    _reply(db, person, talk_id, said.text or "Erledigt.", first.object_id)
    return None


def converse(db: Session, person: UserProfile, body: str, *, talk: Optional[int] = None,
             hint: Optional[int] = None, files: Optional[list[FileRef]] = None) -> TalkOut:
    """Sagen und antworten lassen – in EINER Anfrage (``ai.until``). Fällt die KI aus, steht
    die Nachricht trotzdem; ``problem`` sagt warum, der Takt antwortet nach."""
    tid = say(db, person, body, talk=talk, hint=hint, files=files)
    handgriff.release(db)       # die Nachricht steht – auch wenn die KI danach scheitert
    trouble = answer(db, tid, person, live=True)
    if trouble and ai.available(db):
        log.event(db, "talk.failed", None, {"talk": tid, "problem": trouble})
    return view(db, tid, problem=trouble)


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
        elif ai.available(db):
            log.event(db, "talk.failed", None, {"talk": tid, "problem": trouble})
        db.commit()
    return n
