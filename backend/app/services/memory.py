"""►►► **Lernen ohne Training – die Erfahrung der KI** (Projektakte §4.3, Schritt 3.6). ◄◄◄

Jeder Vorschlag mit Entscheid ist ein **Fall** (im Log: ``proposal`` + ``proposal.decided``).
Bevor die KI ablegt oder vorschlägt, bekommt sie die **ähnlichsten** entschiedenen Fälle mit –
wie wir früher ihre Vorschläge bestätigt, geändert oder verworfen haben – und richtet sich
danach. «Ähnlich» heisst: ähnliche Bedeutung, nicht gleiche Wörter (Bedeutungs-Zahlen von
Vertex AI über ``ai.embed``, gesucht mit pgvector in ``ai_memory``).

* ``text_of`` – was von einem Vorschlag eingebettet wird (Quelle + Vorschlag), EINE Stelle.
* ``remember`` – die Zahlen eines Vorschlags ablegen (gleich beim Vorschlag; was nicht ging,
  holt der Takt nach: ``missing``).
* ``similar`` – die ähnlichsten entschiedenen Fälle zu einem Text; ``as_prompt`` macht daraus
  den Abschnitt für die Anfrage.

Ohne Vertex (nicht eingerichtet, Deckel, Fehler) gibt es keine Fälle – sonst nichts. Nichts wird
vergessen: ``ai_memory`` ist eine Ableitung aus dem Log und entsteht im Takt neu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import AiMemory, UserProfile
from . import ai

#: So viele ähnliche Fälle gehen höchstens in eine Anfrage.
CASES = 5
#: Ab dieser Kosinus-Distanz (0 = gleich, 2 = Gegenteil) ist ein Fall nicht mehr «ähnlich».
FAR = 0.6

#: Die Wörter der Entscheide – so liest die KI ihre Fälle.
OUTCOMES = {"accepted": "übernommen", "changed": "selbst geändert", "rejected": "verworfen",
            "gone": "erledigt sich (Datensatz weg)"}


@dataclass(frozen=True)
class Case:
    proposal: int
    text: str
    outcome: str
    #: Bei «selbst geändert»: was der Mensch stattdessen nahm.
    value: Optional[str]
    distance: float


def text_of(payload: dict[str, Any]) -> str:
    """►►► **Was von einem Vorschlag eingebettet wird** – die Quelle und der Vorschlag selbst,
    knapp. EINE Stelle für ``remember`` und den Takt. ◄◄◄"""
    source = (payload.get("source") or {}).get("text") or ""
    kind = payload.get("kind") or ""
    if kind == "change":
        what = f"Feld {payload.get('label') or payload.get('field')} → {payload.get('value')}"
    elif kind == "create":
        draft = payload.get("draft") or {}
        values = ", ".join(f"{k}: {v}" for k, v in (draft.get("values") or {}).items())
        what = f"neu anlegen ({draft.get('type')}): {values}"
    elif kind == "file":
        what = "ablegen: " + " | ".join(
            f"{p.get('object_id')}: {p.get('text', '')[:200]}" for p in payload.get("parts") or [])
    else:
        what = str(payload.get("label") or "")
    return f"Quelle: {source[:1500]}\nVorschlag ({kind}): {what[:1500]}"


def remember(db: Session, proposal_id: int, payload: dict[str, Any], *,
             actor: Optional[UserProfile]) -> bool:
    """Die Bedeutungs-Zahlen eines Vorschlags ablegen – ``True``, wenn sie jetzt da sind."""
    if db.get(AiMemory, proposal_id) is not None:
        return True
    body = text_of(payload)
    values = ai.embed(db, body, actor=actor)
    if values is None:
        return False
    db.add(AiMemory(log_id=proposal_id, embedding=values, text=body))
    db.flush()
    return True


_MISSING = text("""
SELECT l.id, l.payload, l.actor_id FROM log l
  LEFT JOIN ai_memory m ON m.log_id = l.id
 WHERE l.event = 'proposal' AND m.log_id IS NULL
 ORDER BY l.id DESC LIMIT :n""")


def missing(db: Session, limit: int = 20) -> list[tuple[int, dict[str, Any], Optional[int]]]:
    """Vorschläge ohne Bedeutungs-Zahlen – die neuesten zuerst (der Takt holt sie nach)."""
    return [(r.id, r.payload or {}, r.actor_id) for r in db.execute(_MISSING, {"n": limit})]


_SIMILAR = text("""
SELECT m.log_id, m.text, d.payload AS decided, (m.embedding <=> CAST(:q AS vector)) AS distance
  FROM ai_memory m
  JOIN LATERAL (SELECT payload FROM log
                 WHERE event = 'proposal.decided'
                   AND (payload ->> 'proposal')::bigint = m.log_id
                 ORDER BY id DESC LIMIT 1) d ON true
 WHERE m.is_active
 ORDER BY m.embedding <=> CAST(:q AS vector)
 LIMIT :k""")


def similar(db: Session, query: str, *, actor: Optional[UserProfile], k: int = CASES) -> list[Case]:
    """►►► **Die ähnlichsten entschiedenen Fälle** zu einem Text – oder keine (kein Vertex,
    Deckel, Fehler, noch keine Fälle). Nie eine Ausnahme. ◄◄◄"""
    if not ai.embed_ready():
        return []
    has_cases = db.execute(text("SELECT EXISTS (SELECT 1 FROM ai_memory)")).scalar()
    if not has_cases:
        return []
    values = ai.embed(db, query, actor=actor, query=True)
    if values is None:
        return []
    q = "[" + ",".join(f"{v:.7g}" for v in values) + "]"
    out = []
    for r in db.execute(_SIMILAR, {"q": q, "k": k}):
        if r.distance is None or r.distance > FAR:
            continue
        decided = r.decided or {}
        out.append(Case(proposal=r.log_id, text=r.text, outcome=str(decided.get("outcome") or ""),
                        value=decided.get("value"), distance=float(r.distance)))
    return out


def as_prompt(cases: list[Case]) -> str:
    """Die Fälle als Abschnitt der Anfrage – leer, wenn es keine gibt."""
    if not cases:
        return ""
    lines = ["So haben wir früher über ähnliche Vorschläge entschieden – richte dich danach:"]
    for c in cases:
        verdict = OUTCOMES.get(c.outcome, c.outcome)
        if c.outcome == "changed" and c.value:
            verdict += f" (stattdessen: {c.value})"
        lines.append(f"- {c.text.replace(chr(10), ' · ')} ⇒ {verdict}")
    return "\n".join(lines)
