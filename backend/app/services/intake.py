"""►►► **Erfassen und Ablegen** (Projektakte §4.3/§4.4, Bauplan Phase 3, Schritte 3.2 und 3.3). ◄◄◄

* ``capture`` – die rohe Eingabe **sofort** ins Log (Ereignis ``intake``, am Datensatz, der dabei
  offen war, sonst an der Person). Was danach auch geschieht: sie ist da.
* ``file_with_ai`` – die KI legt ab (``ai.converse``, Aufgabe ``file``, mit den Lese-Werkzeugen
  ``ai_tools.tools_for`` – was jedes Personal sehen darf): Teile mit je einer Heimat + was
  daraus folgt. **Aus einer Aufnahme** (lang) nennt die KI je Teil nur einen **Bereich
  nummerierter Absätze** (``spoken_parts``); den Text baut der Code wörtlich aus dem Original –
  nie gekürzt, nichts doppelt, jeder Absatz genau einmal. Das Ergebnis ist ein **Vorschlag**
  ``file`` (die Teile) und die übrigen Vorschläge (``change``/``create``). Ungültige Nummern und
  Felder verwirft der Code, nicht die KI. Ohne KI: kein Vorschlag, ein roher Teil und ``problem``;
  der Takt holt nach (``catch_up``).
* ``file`` – «Stimmt so»: je Teil eine **Notiz** an seinem Datensatz (``communication.create``,
  Kanal ``note``), dann der Entscheid über den ``file``-Vorschlag (``accepted``, wenn unverändert,
  sonst ``changed``) – Notizen und Entscheid in EINER Transaktion: kam ein zweites «Stimmt so»
  zuvor, ist das 409 und keine Notiz bleibt.

**Die Worte einer Erfassung sieht nur, wer erfasst hat** – bis «Stimmt so» sie als Notiz ablegt.
Die Quelle eines ``change``/``create`` nennt darum nur «Erfassung von <Name>» (``source_of``),
nie den Text.

Eine Erfassung gehört der Person, die erfasst hat: nur sie (oder ein Admin) sieht sie offen und
legt sie ab (``may_see`` ↔ ``assert_may``).
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import UserProfile
from ..schemas.proposals import IntakeOut, NoteRef
from . import ai, log, proposals, records

#: Der Auftrag an die KI – wörtlich aus der Akte (§4.3), eine Datei.
AUFTRAG = (Path(__file__).resolve().parents[1] / "assets" / "ai" / "auftrag.md").read_text("utf-8")

#: So lang ist eine Erfassung höchstens (wie eine Nachricht).
MAX_TEXT = 20000
#: So lang ist eine Erfassung aus einer Aufnahme höchstens – drei Stunden Gesprochenes.
MAX_SPOKEN = 200_000
#: Der Takt: so viele Erfassungen je Lauf, so alt höchstens, so oft höchstens versucht.
CATCH_UP = 3
CATCH_UP_DAYS = 7
TRIES = 3


# ─── Die Antwortform der KI ────────────────────────────────────────────────────────────

class AiPart(BaseModel):
    object_id: int = Field(description="Objektnummer des Datensatzes, an dem dieser Teil "
                                       "später gesucht wird")
    text: str = Field(description="Was dort steht – der Teil des Festgehaltenen, wörtlich "
                                  "oder knapp")
    subject: str = Field(description="Betreff, wenige Worte")


class AiValue(BaseModel):
    key: str
    value: str


class AiProposal(BaseModel):
    kind: Literal["change", "create"]
    object_id: int = Field(description="change: der Datensatz, dessen Feld sich ändert; "
                                       "create: der Datensatz, an dem der Vorschlag steht")
    field: Optional[str] = Field(description="change: der Feldname, sonst null")
    value: Optional[str] = Field(description="change: der neue Wert, sonst null")
    type: Optional[Literal["user", "organization"]] = Field(
        description="create: was angelegt wird, sonst null")
    values: list[AiValue] = Field(description="create: die Werte des Entwurfs, sonst leer")


class FileAnswer(BaseModel):
    parts: list[AiPart]
    proposals: list[AiProposal]


class AiRange(BaseModel):
    """Ein Teil einer Aufnahme – als Bereich der nummerierten Absätze, nicht als Text."""
    model_config = ConfigDict(populate_by_name=True)
    object_id: int = Field(description="Objektnummer des Datensatzes, an dem dieser Teil "
                                       "später gesucht wird")
    subject: str = Field(description="Betreff, wenige Worte")
    start: int = Field(alias="from", description="Erster Absatz dieses Teils (Nummer)")
    end: int = Field(alias="to", description="Letzter Absatz dieses Teils (Nummer, einschliesslich)")


class SpokenAnswer(BaseModel):
    parts: list[AiRange]
    proposals: list[AiProposal]


def fields_text() -> str:
    """Welche Felder ein Vorschlag ändern bzw. ein Entwurf vorausfüllen darf."""
    lines = [f"- ändern an {t}: " + ", ".join(f"{k} ({w})" for k, w in fs.items())
             for t, fs in proposals.FIELDS.items()]
    lines += [f"- anlegen ({t}): " + ", ".join(fs) for t, fs in proposals.CREATE_FIELDS.items()]
    return "\n".join(lines)


FILE_FORMAT = """
Antwortformat: `parts` – das Festgehaltene in Teilen, je Teil der Datensatz (Objektnummer), an
dem er später gesucht wird, sein Text und ein kurzer Betreff; `proposals` – was daraus folgt:
`change` (ein Feld eines Datensatzes ändern) oder `create` (eine Person oder Firma anlegen).
Erlaubte Felder:
"""


SPOKEN_FORMAT = """
Antwortformat: Das Festgehaltene ist eine Abschrift in nummerierten Absätzen («[n] …»).
`parts` – das Festgehaltene in Teilen, je Teil der Datensatz (Objektnummer), an dem er später
gesucht wird, ein kurzer Betreff und der Bereich der Absätze: `from` (erster) und `to` (letzter,
einschliesslich). Schreibe den Text NICHT ab – nur die Nummern. Jeder Absatz gehört zu genau
einem Teil; was keinem gehört, legt das System an den Datensatz, der offen war. `proposals` – was
daraus folgt: `change` (ein Feld eines Datensatzes ändern) oder `create` (eine Person oder Firma
anlegen). Erlaubte Felder:
"""


def system_text(fmt: str) -> str:
    """Der Systemtext einer Aufgabe: der Auftrag + nur ihr Antwortformat."""
    return f"{AUFTRAG.strip()}\n{fmt.rstrip()}\n{fields_text()}"


# ─── Lesen ─────────────────────────────────────────────────────────────────────────────

class Intake(BaseModel):
    id: int
    at: datetime
    object_id: int
    actor_id: Optional[int]
    text: str
    hint: Optional[int]
    #: Die Aufnahme, aus der der Text kommt (Phase 4) – sonst getippt.
    recording: Optional[int] = None


def get(db: Session, intake_id: int) -> Intake:
    r = db.execute(text("SELECT id, at, object_id, actor_id, payload FROM log "
                        "WHERE id = :i AND event = 'intake'"), {"i": intake_id}).first()
    if r is None:
        raise HTTPException(404, detail=f"Erfassung «{intake_id}» gibt es nicht.")
    p = r.payload or {}
    return Intake(id=r.id, at=r.at, object_id=r.object_id, actor_id=r.actor_id,
                  text=str(p.get("text") or ""), hint=p.get("hint"), recording=p.get("recording"))


def _may(it: Intake, viewer: UserProfile) -> bool:
    return viewer.role == "admin" or (it.actor_id is not None and it.actor_id == viewer.object_id)


def may_see(db: Session, intake_id: int, viewer: UserProfile) -> bool:
    """Sieht ``viewer`` diese Erfassung? Die Person, die erfasst hat, und ein Admin."""
    try:
        return _may(get(db, intake_id), viewer)
    except HTTPException:
        return False


def assert_may(db: Session, intake_id: int, viewer: UserProfile) -> Intake:
    it = get(db, intake_id)
    if not _may(it, viewer):
        raise HTTPException(404, detail=f"Erfassung «{intake_id}» gibt es nicht.")
    return it


def first_words(body: str, n: int = 6) -> str:
    words = body.split()
    return " ".join(words[:n])[:80] + ("…" if len(words) > n else "")


def raw_part(it: Intake) -> dict[str, Any]:
    """Der eine rohe Teil: der ganze Text am Hinweis bzw. an der Person."""
    return {"object_id": it.object_id, "text": it.text, "subject": first_words(it.text)}


def _failure(db: Session, intake_id: int) -> Optional[str]:
    r = db.execute(text("SELECT payload ->> 'problem' FROM log WHERE event = 'intake.failed' "
                        "AND (payload ->> 'intake')::bigint = :i ORDER BY id DESC LIMIT 1"),
                   {"i": intake_id}).scalar()
    return r


WAITING = "Die KI hat noch nicht abgelegt – der Takt holt es nach; von Hand geht es jederzeit."


def view(db: Session, it: Intake, *, problem: Optional[str] = None) -> IntakeOut:
    """►►► **Eine Erfassung, wie die Oberfläche sie zeigt** – Teile (Vorschlag der KI, sonst
    roh), offene Vorschläge, ob und wohin abgelegt. ◄◄◄"""
    found = proposals.of_intake(db, it.id)
    files = [p for p in found if p.kind == "file"]
    done = proposals.decided(db, [p.id for p in files])
    final = next((done[p.id] for p in reversed(files)
                  if done.get(p.id, {}).get("outcome") in ("accepted", "changed")), None)
    if final is not None and final.get("parts") is not None:
        parts = final["parts"]
    elif files:
        parts = files[-1].payload.get("parts") or [raw_part(it)]
    else:
        parts = [raw_part(it)]
    names = records.labels(db, [int(p.get("object_id") or 0) for p in parts])
    others = [p for p in found if p.kind != "file" and proposals.derive(db, p) is None
              and p.id not in proposals.decided(db, [p.id])]
    if not files and final is None and not problem:
        problem = _failure(db, it.id) or WAITING
    return IntakeOut(id=it.id, at=it.at, text=it.text, hint_object_id=it.hint,
                     parts=[proposals.part_out(p, names) for p in parts],
                     proposals=proposals.out(db, others), filed=final is not None,
                     notes=[NoteRef(**n) for n in (final or {}).get("notes") or []],
                     problem=problem or None)


_OPEN = text("""
SELECT i.id FROM log i
 WHERE i.event = 'intake' AND i.actor_id = :me
   AND NOT EXISTS (
     SELECT 1 FROM log p JOIN log d ON d.event = 'proposal.decided'
                                   AND (d.payload ->> 'proposal')::bigint = p.id
      WHERE p.event = 'proposal' AND p.object_id = i.object_id AND p.id > i.id
        AND p.payload ->> 'kind' = 'file'
        AND (p.payload -> 'source' ->> 'intake')::bigint = i.id)
 ORDER BY i.id DESC LIMIT :n""")


def open_ids(db: Session, viewer: UserProfile, limit: int = 50) -> list[int]:
    """Meine Erfassungen, die noch nicht abgelegt (und nicht verworfen) sind – die neuesten zuerst."""
    return [r.id for r in db.execute(_OPEN, {"me": viewer.object_id, "n": limit})]


def open_intakes(db: Session, viewer: UserProfile, limit: int = 50) -> list[IntakeOut]:
    return [view(db, get(db, i)) for i in open_ids(db, viewer, limit)]


# ─── Erfassen ──────────────────────────────────────────────────────────────────────────

def capture(db: Session, body: str, hint: Optional[int], actor: UserProfile, *,
            recording: Optional[int] = None) -> Intake:
    """►►► **Festhalten** – die rohe Eingabe als Ereignis ``intake``, sofort. ◄◄◄ Am Datensatz,
    der offen war (``hint``), sonst an der Person. Der Aufrufer committet, bevor die KI läuft.
    **Erfasst hat immer ``actor``** – auch wenn der Takt eine Aufnahme zu Ende abschreibt
    (``recording``: die Aufnahme, aus der der Text kommt; dann darf er länger sein)."""
    body = (body or "").strip()
    if not body:
        raise HTTPException(400, detail="Eine Erfassung braucht Text.")
    if hint is not None and records.labels(db, [hint]).get(hint) is None:
        raise HTTPException(400, detail=f"Datensatz «{hint}» gibt es nicht.")
    home = hint or actor.object_id
    payload: dict[str, Any] = {"text": body[:MAX_SPOKEN if recording else MAX_TEXT], "hint": hint}
    if recording:
        payload["recording"] = recording
    iid = log.event(db, "intake", home, payload, kind="person", actor=actor.object_id)
    return get(db, iid)


def _prompt(db: Session, it: Intake, actor: UserProfile) -> list[dict[str, Any]]:
    from . import memory
    head = [f"Festgehalten von {actor.display_name} ({actor.object_id}) am "
            f"{it.at.isoformat(timespec='minutes')}."]
    if it.hint:
        head.append(f"Offen war der Datensatz {it.hint}.")
    cases = memory.as_prompt(memory.similar(db, it.text[:MAX_TEXT], actor=actor))
    said = it.text
    if it.recording:
        said = "\n".join(f"[{n}] {p.strip()}" for n, p in enumerate(paragraphs(it.text), 1))
    body = "\n".join(head) + ("\n\n" + cases if cases else "") + "\n\nFestgehalten:\n" + said
    return [{"type": "text", "text": body}]


#: Ein Absatz einer Abschrift ist höchstens etwa so lang – längere Zeilen (ein Sprecher, fünf
#: Minuten am Stück) werden an Satzenden geteilt, damit die KI auch darin trennen kann.
PARAGRAPH = 1200


def paragraphs(text: str) -> list[str]:
    """►► **Die Absätze einer Abschrift – ohne ein Zeichen zu verlieren**: zusammengesetzt
    ergeben sie genau den Text (``"".join(paragraphs(t)) == t``). Geteilt an Zeilen (Leerzeilen,
    Sprecherwechsel), lange Zeilen an Satzenden; Leerraum hängt am Absatz davor. ◄◄"""
    out: list[str] = []
    for line in re.split(r"(?<=\n)", text):
        if not line:
            continue
        if not line.strip() and out:
            out[-1] += line
            continue
        pieces = re.split(r"(?<=[.!?…])(?=\s)", line) if len(line) > PARAGRAPH else [line]
        current = ""
        for piece in pieces:
            if current and len(current) + len(piece) > PARAGRAPH:
                out.append(current)
                current = ""
            current += piece
        if current:
            out.append(current)
    return out


def spoken_parts(db: Session, answer: SpokenAnswer, it: Intake,
                 actor: UserProfile) -> list[dict[str, Any]]:
    """►►► **Die Teile einer Aufnahme, wörtlich aus dem Original** – je Teil die Absätze seines
    Bereichs, die noch keinem gehören (nichts doppelt); was keinem Teil gehört (oder einem
    Datensatz, den es nicht gibt), geht an den Datensatz der Erfassung. Jeder Absatz steht genau
    einmal, nichts ist gekürzt. ◄◄◄"""
    paras = paragraphs(it.text)
    owner: list[Optional[int]] = [None] * len(paras)
    claims: list[tuple[int, str]] = []
    for r in answer.parts:
        if not valid_target(db, r.object_id, actor):
            continue
        k = len(claims)
        claims.append((r.object_id, " ".join(r.subject.split())[:255]))
        for i in range(max(1, min(r.start, r.end)), min(len(paras), max(r.start, r.end)) + 1):
            if owner[i - 1] is None:
                owner[i - 1] = k
    home = next((k for k, (oid, _) in enumerate(claims) if oid == it.object_id), None)
    if home is None and None in owner:
        home = len(claims)
        claims.append((it.object_id, ""))
    owner = [home if o is None else o for o in owner]
    out = []
    for k, (oid, subject) in enumerate(claims):
        body = "".join(p for p, o in zip(paras, owner) if o == k).strip()
        if body:
            out.append((owner.index(k), {"object_id": oid, "text": body,
                                         "subject": subject or first_words(body)}))
    return [part for _, part in sorted(out, key=lambda x: x[0])] or [raw_part(it)]


def valid_target(db: Session, object_id: int, viewer: UserProfile) -> bool:
    """Ein Datensatz, an den ``viewer`` ablegen kann – er existiert und ist sichtbar."""
    from ..models import Document, DocumentRef
    from . import access
    found = records.labels(db, [object_id]).get(object_id)
    if found is None:
        return False
    if found.type != "document":
        return True
    doc = db.query(Document).filter(Document.object_id == object_id).one()
    refs = db.query(DocumentRef).filter(DocumentRef.document_id == doc.id,
                                        DocumentRef.is_active.is_(True)).all()
    return access.may(viewer, refs)


def _parts(db: Session, answer: FileAnswer, it: Intake, actor: UserProfile) -> list[dict[str, Any]]:
    out = [{"object_id": p.object_id, "text": p.text.strip(),
            "subject": (" ".join(p.subject.split())[:255] or first_words(p.text))}
           for p in answer.parts if p.text.strip() and valid_target(db, p.object_id, actor)]
    return out or [raw_part(it)]


def follow_up(db: Session, items: list[AiProposal], *, home: int, source: dict[str, Any],
              actor: UserProfile) -> list[int]:
    """Die Vorschläge der KI festhalten – was nicht gilt, verwirft ``proposals.propose``."""
    made = []
    for item in items:
        if item.kind == "change":
            pid = proposals.propose(db, object_id=item.object_id, kind="change", field=item.field,
                                    value=item.value, source=source, actor=actor.object_id)
        else:
            where = item.object_id if valid_target(db, item.object_id, actor) else home
            pid = proposals.propose(db, object_id=where, kind="create", source=source,
                                    draft={"type": item.type,
                                           "values": {v.key: v.value for v in item.values}},
                                    actor=actor.object_id)
        if pid is not None and pid not in made:
            made.append(pid)
    return made


def source_of(it: Intake, actor: UserProfile) -> dict[str, Any]:
    """►►► **Die Quelle eines Vorschlags aus einer Erfassung – ohne ihre Worte.** ◄◄◄ Ein
    ``change``/``create`` steht für jedes Personal da; der Text der Erfassung gehört bis «Stimmt
    so» nur der Person, die erfasst hat."""
    return {"text": f"Erfassung von {actor.display_name}", "object_id": it.hint,
            "intake": it.id, "at": it.at}


def file_with_ai(db: Session, it: Intake, actor: UserProfile) -> Optional[str]:
    """►►► **Die KI legt ab** – ein ``file``-Vorschlag mit den Teilen, dazu die übrigen
    Vorschläge. Gibt ``None`` zurück, wenn es klappte, sonst warum nicht (``ai.problem``). ◄◄◄"""
    from . import ai_tools
    if proposals.of_intake(db, it.id, "file"):
        return None
    # Ohne KI kein Nachschlagen der Fälle (auch das kostet) – ``converse`` sagt dann nur warum.
    content = _prompt(db, it, actor) if ai.available(db) else []
    spoken = bool(it.recording)
    answer = ai.converse(db, task="file", actor=actor,
                         system=system_text(SPOKEN_FORMAT if spoken else FILE_FORMAT),
                         content=content, schema=SpokenAnswer if spoken else FileAnswer,
                         tools=ai_tools.tools_for(db))
    if answer is None:
        return ai.problem() or "Die KI hat nichts abgelegt."
    source = source_of(it, actor)
    # Während die KI las, kann die Person von Hand abgelegt (oder der Takt nachgeholt) haben –
    # dann gibt es keinen zweiten ``file``-Vorschlag.
    if not proposals.of_intake(db, it.id, "file"):
        parts = (spoken_parts(db, answer, it, actor) if isinstance(answer, SpokenAnswer)
                 else _parts(db, answer, it, actor))
        proposals.propose(db, object_id=it.object_id, kind="file", source=source,
                          parts=parts, actor=actor.object_id)
    follow_up(db, answer.proposals, home=it.object_id, source=source, actor=actor)
    return None


# ─── Ablegen («Stimmt so») ─────────────────────────────────────────────────────────────

def _clean(db: Session, parts: list[Any], viewer: UserProfile) -> list[dict[str, Any]]:
    if not parts:
        raise HTTPException(400, detail="Ablegen braucht mindestens einen Teil.")
    out = []
    for p in parts:
        body = (p.text or "").strip()
        if not body:
            raise HTTPException(400, detail=f"Der Teil für «{p.object_id}» hat keinen Text.")
        if not valid_target(db, p.object_id, viewer):
            raise HTTPException(400, detail=f"Datensatz «{p.object_id}» gibt es nicht.")
        out.append({"object_id": p.object_id, "text": body,
                    "subject": " ".join((p.subject or "").split())[:255] or first_words(body)})
    return out


def _unchanged(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> bool:
    key = lambda ps: [(int(p.get("object_id") or 0), " ".join(str(p.get("text") or "").split()),  # noqa: E731
                       " ".join(str(p.get("subject") or "").split())) for p in ps]
    return key(a) == key(b)


def pieces(text: str, limit: int = MAX_TEXT) -> list[str]:
    """►► **Ein langer Teil wird zu mehreren Notizen** (eine Notiz trägt höchstens ``limit``
    Zeichen) – getrennt an Absätzen, sonst an Zeilen, sonst an Wörtern; nichts geht verloren. ◄◄"""
    text = text.strip()
    out: list[str] = []
    while len(text) > limit:
        cut = max(text.rfind("\n\n", 0, limit), text.rfind("\n", 0, limit), text.rfind(" ", 0, limit))
        cut = cut if cut > limit // 2 else limit
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return out + [text] if text or not out else out


def file(db: Session, intake_id: int, parts: list[Any], actor: UserProfile) -> Intake:
    """►►► **«Stimmt so»** – je Teil eine Notiz an seinem Datensatz, dann der Entscheid. ◄◄◄
    Gab es noch keinen Vorschlag (KI aus), entsteht er hier – als der rohe Teil, den der Mensch
    sah – damit auch diese Erfassung ein Fall ist."""
    from ..domain import communication as dc
    from ..schemas.communication import MessageIn
    from . import communication
    it = assert_may(db, intake_id, actor)
    files = proposals.of_intake(db, it.id, "file")
    done = proposals.decided(db, [p.id for p in files])
    if any(d.get("outcome") in ("accepted", "changed") for d in done.values()):
        raise HTTPException(409, detail=f"Erfassung «{intake_id}» ist schon abgelegt.")
    clean = _clean(db, parts, actor)
    open_files = [p for p in files if p.id not in done]
    if not open_files:
        pid = proposals.propose(db, object_id=it.object_id, kind="file", parts=[raw_part(it)],
                                source=source_of(it, actor), actor=actor.object_id, ai=False)
        open_files = proposals.load(db, [pid]) if pid else []
    # Notizen und Entscheid in EINER Transaktion: kam ein anderes «Stimmt so» zuvor, weist der
    # eindeutige Entscheid ab (409) und der Savepoint nimmt auch die Notizen zurück.
    with db.begin_nested():
        notes = []
        for p in clean:
            chunks = pieces(p["text"])
            for n, body in enumerate(chunks, 1):
                subject = p["subject"] if len(chunks) == 1 else f"{p['subject']} ({n}/{len(chunks)})"
                msg = communication.create(db, MessageIn(
                    channel=dc.NOTE, about=[p["object_id"]], subject=subject[:255], body=body), actor)
                notes.append({"object_id": p["object_id"], "message_id": msg.id})
        chosen = open_files[-1]
        kept = _unchanged(chosen.payload.get("parts") or [], clean)
        proposals.decide(db, chosen, "accepted" if kept else "changed", notes=notes,
                         **({} if kept else {"parts": clean}))
        for other in open_files[:-1]:
            proposals.decide(db, other, "gone")
    return it


# ─── Der Takt ──────────────────────────────────────────────────────────────────────────

_WAITING = text("""
SELECT i.id FROM log i
 WHERE i.event = 'intake' AND i.at >= now() - make_interval(days => :days)
   AND NOT EXISTS (SELECT 1 FROM log p WHERE p.event = 'proposal' AND p.object_id = i.object_id
                     AND p.id > i.id AND p.payload ->> 'kind' = 'file'
                     AND (p.payload -> 'source' ->> 'intake')::bigint = i.id)
   AND (SELECT count(*) FROM log f WHERE f.event = 'intake.failed'
          AND (f.payload ->> 'intake')::bigint = i.id) < :tries
 ORDER BY i.id LIMIT :n""")


def waiting(db: Session, limit: int = CATCH_UP) -> list[int]:
    """Erfassungen ohne ``file``-Vorschlag (die KI war aus) – die ältesten zuerst."""
    return [r.id for r in db.execute(_WAITING, {"days": CATCH_UP_DAYS, "tries": TRIES,
                                                "n": limit})]


def catch_up(db: Session, deadline: float, limit: int = CATCH_UP) -> int:
    """►►► **Nachholen, was die KI nicht ablegte** – im Namen der Person, die erfasst hat. Ein
    Fehlschlag, der nicht am Deckel lag, zählt (``intake.failed``); nach ``TRIES`` bleibt die
    Erfassung für den Menschen. Committet je Erfassung. ◄◄◄"""
    n = 0
    for iid in waiting(db, limit):
        if time.monotonic() >= deadline or not ai.available(db):
            break
        it = get(db, iid)
        person = db.query(UserProfile).filter(UserProfile.object_id == it.actor_id).first()
        if person is None:
            continue
        trouble = file_with_ai(db, it, person)
        if trouble is None:
            n += 1
        elif ai.available(db):
            log.event(db, "intake.failed", None, {"intake": iid, "problem": trouble})
        db.commit()
    return n
