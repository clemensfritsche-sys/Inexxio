"""►►► **Das Angeheftete – was an diesem Datensatz jetzt zählt.** ◄◄◄ (Phase 5 §8.3)

Unten im Verlauf jedes Datensatzes, zwei Teile:

* **offene Handgriffe** (immer, zuerst) – aus Mails für jedes Personal, aus Gesprächen nur die
  eigenen (``handgriff.open_at``);
* **das Wissen, das jetzt zählt** – höchstens ``MAX`` Aussagen, jede mit Datum und Quelle (eine
  Notiz, ein Dokument). Gewählt von der KI, als Ereignis ``pin`` mit der **Marke des Umfelds**
  (``surroundings.mark``). Beim Öffnen kommt sofort der letzte Stand; hat sich im Umfeld seither
  etwas geändert (``stale``), wählt ``refresh`` neu – sonst nicht (kein Aufruf, keine Kosten). Am
  Deckel oder ohne KI bleibt der letzte Stand.

Die KI liest dafür, was jedes Personal sehen darf (``ai_tools.reader``).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import UserProfile
from ..schemas.assistant import KnowledgeOut, PinnedOut
from . import ai, handgriff, history, log, surroundings

#: So viele Aussagen höchstens – «so wenig wie möglich, auch nichts».
MAX = 3
#: So viele Einträge des Verlaufs gehen in die Anfrage (die KI kann weiter nachschlagen).
ENTRIES = 20


class AiKnowledge(BaseModel):
    text: str = Field(description="Die Aussage, ein Satz, mit Datum und Quelle")
    entry: Optional[int] = Field(description="Die Nummer [n] des Eintrags, auf den sie sich stützt, "
                                             "sonst null")


class PinAnswer(BaseModel):
    items: list[AiKnowledge]


FORMAT = """
Jemand öffnet diesen Datensatz. Was ist hier jetzt wichtig – aus dem Verlauf, dem Umfeld und dem
Wissen der Firma (Werkzeug `wissen`)? Höchstens drei Aussagen, je ein Satz mit Datum und Quelle;
Neues vor Altem; widersprechen sich zwei Einträge, sag es. Nichts Wichtiges: leer.
Antwortformat: `items` – je Aussage `text` und `entry` (die Nummer [n] des Eintrags, sonst null).
"""


def _latest(db: Session, object_id: int) -> Optional[Any]:
    return db.execute(text("SELECT id, at, payload FROM log WHERE event = 'pin' "
                           "AND object_id = :o ORDER BY id DESC LIMIT 1"), {"o": object_id}).first()


def _stale(db: Session, object_id: int, pin: Optional[Any]) -> tuple[bool, int]:
    now = surroundings.mark(db, surroundings.of(db, object_id))
    seen = int(((pin.payload or {}).get("seen") or 0)) if pin is not None else -1
    return now > seen, now


def pinned(db: Session, object_id: int, viewer: UserProfile, *,
           problem: Optional[str] = None) -> PinnedOut:
    """Das Angeheftete, wie es ist – ohne die KI zu fragen."""
    history.assert_visible(db, object_id, viewer)
    pin = _latest(db, object_id)
    stale, mark = _stale(db, object_id, pin)
    items = [KnowledgeOut(**i) for i in ((pin.payload or {}).get("items") or [])] if pin else []
    return PinnedOut(handgriffe=handgriff.open_at(db, object_id, viewer), knowledge=items,
                     chosen_at=pin.at if pin else None, stale=stale, mark=mark,
                     problem=problem or None)


#: Ein Datensatz, den nicht jedes Personal sieht (ein privates Dokument): kein Wissen.
PRIVATE = "Diesen Datensatz sieht nicht jedes Personal – die KI sieht ihn nicht an."


def _content(db: Session, object_id: int, reader: UserProfile, entries: list[Any],
             near: list[int]) -> list[dict[str, Any]]:
    from . import ai_tools, records
    names = records.labels(db, near[1:])
    lines = ["Der Datensatz, der gerade geöffnet wird:", ai_tools.record(db, reader, object_id), "",
             "Sein Verlauf, die neuesten zuerst:"]
    lines += [f"[{i}] {ai_tools.entry_line(e)}" for i, e in enumerate(entries, 1)] or ["(leer)"]
    if names:
        lines += ["", "Sein Umfeld:"] + [f"- {r.object_id} {r.type}: {r.name}" for r in names.values()]
    return [{"type": "text", "text": "\n".join(lines)}]


def refresh(db: Session, object_id: int, viewer: UserProfile) -> PinnedOut:
    """►►► **Neu wählen – nur, wenn sich im Umfeld etwas geändert hat.** ◄◄◄ Die KI liest den
    Datensatz, seinen Verlauf und sein Umfeld (als ``reader``; ``viewer`` handelt) und wählt das
    Wissen: ein neues ``pin`` mit der Marke, auch ein leeres. Ohne KI bleibt der letzte Stand."""
    from . import ai_tools
    from .talk import AUFTRAG
    history.assert_visible(db, object_id, viewer)
    pin = _latest(db, object_id)
    stale, mark = _stale(db, object_id, pin)
    if not stale:
        return pinned(db, object_id, viewer)
    reader = ai_tools.reader()
    try:
        entries = history.page(db, object_id, reader, limit=ENTRIES).entries
    except HTTPException:
        return pinned(db, object_id, viewer, problem=PRIVATE)
    near = surroundings.of(db, object_id)
    content = _content(db, object_id, reader, entries, near) if ai.available(db) else []
    answer = ai.converse(db, task="pin", actor=viewer, system=AUFTRAG + "\n" + FORMAT,
                         content=content, schema=PinAnswer, tools=ai_tools.tools_for(db))
    if answer is None:
        return pinned(db, object_id, viewer, problem=ai.problem() or "Die KI hat nichts gewählt.")
    items = []
    for k in answer.items:
        body = " ".join(k.text.split())
        if not body or len(items) >= MAX:
            continue
        entry = entries[k.entry - 1] if k.entry and 0 < k.entry <= len(entries) else None
        items.append(_source(body, entry))
    log.event(db, "pin", object_id, {"items": items, "seen": mark}, kind="ai",
              actor=viewer.object_id)
    return pinned(db, object_id, viewer)


def _source(body: str, entry: Any) -> dict[str, Any]:
    """Die Aussage mit ihrer Quelle – die Nachricht bzw. das Dokument des Verlauf-Eintrags."""
    out: dict[str, Any] = {"text": body}
    if entry is None:
        return out
    out["at"] = getattr(entry, "at", None)
    message = getattr(entry, "message", None)
    document = getattr(entry, "document", None)
    if message is not None:
        out["source_message_id"] = getattr(message, "id", None)
    if document is not None:
        out["source_object_id"] = getattr(document, "object_id", None)
    return out
