"""►►► **Das Angeheftete** (Projektakte §4.3, Bauplan Phase 3, Schritt 3.5). ◄◄◄

Im Verlauf eines Datensatzes, unten beim Neuesten:

* **zuerst alle offenen Vorschläge** (``proposals.open_for``) – immer, unabhängig von der KI;
* **dann die Hinweise der KI** – was an diesem Datensatz jetzt wichtig ist, mit Quelle, so wenig
  wie möglich, auch keine. Sie entstehen nur auf Abruf («neu ansehen», ``refresh``) als Ereignis
  ``pin`` und gelten bis zum nächsten; ein Hinweis lässt sich lösen (``pin.solved``).

«Neu ansehen» ersetzt nur die Hinweise – **nie einen offenen Vorschlag**: die stehen nicht im
``pin``, sie werden bei jedem Lesen aus dem Log abgeleitet.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import UserProfile
from ..schemas.proposals import PinHint, PinnedOut
from . import ai, history, log, proposals

#: So viele Hinweise höchstens – «so wenig wie möglich».
MAX_HINTS = 3
#: So viele Einträge des Verlaufs gehen in die Anfrage (die KI kann weiter nachschlagen).
ENTRIES = 20


class AiHint(BaseModel):
    text: str = Field(description="Der Hinweis, ein Satz, mit Quelle")
    entry: Optional[int] = Field(description="Die Nummer des Eintrags [n], auf den er sich "
                                             "stützt, sonst null")


class PinAnswer(BaseModel):
    hints: list[AiHint]


PIN_FORMAT = """
Antwortformat: `hints` – was an diesem Datensatz jetzt wichtig ist, je ein Satz mit Quelle;
`entry` ist die Nummer [n] des Verlauf-Eintrags, auf den er sich stützt. Leer, wenn nichts
wichtig ist. Offene Vorschläge stehen schon da – nicht wiederholen.
"""


def _latest(db: Session, object_id: int) -> Optional[Any]:
    return db.execute(text("SELECT id, at, payload FROM log WHERE event = 'pin' "
                           "AND object_id = :o ORDER BY id DESC LIMIT 1"),
                      {"o": object_id}).first()


def _solved(db: Session, object_id: int, pin_id: int) -> set[str]:
    return {str(k) for (k,) in db.execute(text(
        "SELECT payload ->> 'key' FROM log WHERE event = 'pin.solved' AND object_id = :o "
        "AND (payload ->> 'pin')::bigint = :p"), {"o": object_id, "p": pin_id})}


def pinned(db: Session, object_id: int, viewer: UserProfile, *,
           problem: Optional[str] = None) -> PinnedOut:
    """►►► **Das Angeheftete** – offene Vorschläge (immer, zuerst) + die ungelösten Hinweise
    des letzten «neu ansehen». ◄◄◄"""
    history.assert_visible(db, object_id, viewer)
    found = proposals.open_for(db, object_id, viewer)
    pin = _latest(db, object_id)
    hints: list[PinHint] = []
    if pin is not None:
        gone = _solved(db, object_id, pin.id)
        hints = [PinHint(key=str(h.get("key")), text=str(h.get("text") or ""),
                         entry_key=h.get("entry_key"))
                 for h in (pin.payload or {}).get("items") or [] if str(h.get("key")) not in gone]
    return PinnedOut(proposals=found, hints=hints, refreshed_at=pin.at if pin else None,
                     problem=problem or None)


def _content(db: Session, object_id: int, viewer: UserProfile,
             entries: list[Any]) -> list[dict[str, Any]]:
    from . import ai_tools
    lines = ["Der Datensatz, der gerade offen ist:", ai_tools.record(db, viewer, object_id), "",
             "Sein Verlauf, die neuesten zuerst:"]
    lines += [f"[{i}] {ai_tools.entry_line(e)}" for i, e in enumerate(entries, 1)] or ["(leer)"]
    open_now = proposals.open_for(db, object_id, viewer)
    if open_now:
        lines += ["", "Offene Vorschläge (stehen schon da):"]
        lines += [f"- {p.label}: {p.value or ''}" for p in open_now]
    return [{"type": "text", "text": "\n".join(lines)}]


def refresh(db: Session, object_id: int, viewer: UserProfile) -> PinnedOut:
    """►►► **«Neu ansehen»** – die KI liest den Datensatz und seinen Verlauf (mit den Rechten
    von ``viewer``) und wählt die Hinweise: ein neues ``pin``, auch ein leeres. Ohne KI bleibt
    alles, wie es war, und ``problem`` sagt warum. ◄◄◄"""
    from . import ai_tools
    from .intake import system_text
    history.assert_visible(db, object_id, viewer)
    entries = history.page(db, object_id, viewer, limit=ENTRIES).entries
    content = _content(db, object_id, viewer, entries) if ai.available(db) else []
    answer = ai.converse(db, task="pin", actor=viewer, system=system_text(PIN_FORMAT),
                         content=content, schema=PinAnswer, tools=ai_tools.tools_for(db, viewer))
    if answer is None:
        return pinned(db, object_id, viewer, problem=ai.problem() or "Die KI hat nichts gezeigt.")
    items = []
    for h in answer.hints:
        body = " ".join(h.text.split())
        if not body or len(items) >= MAX_HINTS:
            continue
        entry = entries[h.entry - 1].key if h.entry and 0 < h.entry <= len(entries) else None
        items.append({"key": str(len(items) + 1), "text": body, "entry_key": entry})
    log.event(db, "pin", object_id, {"items": items}, kind="ai", actor=viewer.object_id)
    return pinned(db, object_id, viewer)


def solve(db: Session, object_id: int, key: str, viewer: UserProfile) -> PinnedOut:
    """Einen Hinweis lösen – er gehört zum letzten ``pin``; ein offener Vorschlag ist kein
    Hinweis (über ihn entscheidet ✕ oder das Feld)."""
    history.assert_visible(db, object_id, viewer)
    pin = _latest(db, object_id)
    keys = {str(h.get("key")) for h in ((pin.payload or {}).get("items") or [])} if pin else set()
    if pin is None or key not in keys:
        raise HTTPException(404, detail=f"Hinweis «{key}» gibt es an «{object_id}» nicht.")
    if key in _solved(db, object_id, pin.id):
        raise HTTPException(409, detail=f"Hinweis «{key}» ist schon gelöst.")
    log.event(db, "pin.solved", object_id, {"pin": pin.id, "key": key})
    return pinned(db, object_id, viewer)
