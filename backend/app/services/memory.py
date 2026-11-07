"""►►► **Lernen ohne Training – die Erfahrung der KI** (Projektakte §4.3, Schritt 3.6). ◄◄◄

Jeder Vorschlag mit Entscheid ist ein **Fall** (im Log: ``proposal`` + ``proposal.decided``).
Bevor die KI ablegt oder vorschlägt, bekommt sie die **ähnlichsten** entschiedenen Fälle mit –
wie wir früher ihre Vorschläge bestätigt, geändert oder verworfen haben – und richtet sich
danach. «Ähnlich» heisst: ähnliche Bedeutung, nicht gleiche Wörter (Bedeutungs-Zahlen von
Vertex AI über ``ai.embed``, gesucht mit pgvector in ``ai_memory``).

* ``shareable`` – **nur ein Fall, dessen Inhalt jedes Personal sehen darf, wird eingebettet**:
  ``change``/``create`` (ihre Quelle nennt keine Worte einer Erfassung) und ``file`` nur, wenn er
  abgelegt wurde (``accepted``/``changed`` – dann steht der Inhalt als Notiz da). Ein verworfener
  ``file`` bleibt bei der Person, die erfasst hat.
* ``text_of`` – was von einem Fall eingebettet wird (Quelle + Vorschlag, bei ``file`` die Teile,
  wie sie abgelegt wurden), EINE Stelle.
* ``remember`` – die Zahlen eines **entschiedenen** Falls ablegen (beim Entscheid: ✕, «Stimmt
  so»; was dort nicht ging und was der Takt entschied, holt der Takt nach: ``missing``).
* ``similar`` – die ähnlichsten Fälle zu einem Text; ``as_prompt`` macht daraus den Abschnitt
  für die Anfrage. Weil ``ai_memory`` nur Entschiedenes und Teilbares hält, ist jeder Nachbar
  aus dem Index ein Fall – die Suche verliert keine an einen nachträglichen Filter.

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


#: Die Entscheide, mit denen ein ``file`` ein Fall für alle ist (abgelegt = als Notiz sichtbar).
FILED = ("accepted", "changed")


def shareable(payload: dict[str, Any], decided: Optional[dict[str, Any]]) -> bool:
    """►►► **Darf dieser Fall in jede Anfrage?** – entschieden, und sein Inhalt ist für jedes
    Personal sichtbar. ◄◄◄"""
    if not decided:
        return False
    if payload.get("kind") == "file":
        return decided.get("outcome") in FILED
    return payload.get("kind") in ("change", "create")


def text_of(payload: dict[str, Any], decided: Optional[dict[str, Any]] = None) -> str:
    """►►► **Was von einem Fall eingebettet wird** – die Quelle und der Vorschlag selbst,
    knapp; bei einem ``file`` die Teile, wie sie abgelegt wurden. EINE Stelle für ``remember``
    und den Takt. ◄◄◄"""
    source = (payload.get("source") or {}).get("text") or ""
    kind = payload.get("kind") or ""
    if kind == "change":
        what = f"Feld {payload.get('label') or payload.get('field')} → {payload.get('value')}"
    elif kind == "create":
        draft = payload.get("draft") or {}
        values = ", ".join(f"{k}: {v}" for k, v in (draft.get("values") or {}).items())
        what = f"neu anlegen ({draft.get('type')}): {values}"
    elif kind == "file":
        parts = (decided or {}).get("parts") or payload.get("parts") or []
        what = "ablegen: " + " | ".join(
            f"{p.get('object_id')}: {str(p.get('text') or '')[:200]}" for p in parts)
    else:
        what = str(payload.get("label") or "")
    return f"Quelle: {source[:1500]}\nVorschlag ({kind}): {what[:1500]}"


def remember(db: Session, proposal_id: int, payload: dict[str, Any], *,
             decided: Optional[dict[str, Any]], actor: Optional[UserProfile]) -> bool:
    """Die Bedeutungs-Zahlen eines entschiedenen Falls ablegen – ``True``, wenn sie jetzt da
    sind. Ein Fall, der nicht ``shareable`` ist, bekommt nie welche (``False``)."""
    if not shareable(payload, decided):
        return False
    if db.get(AiMemory, proposal_id) is not None:
        return True
    body = text_of(payload, decided)
    values = ai.embed(db, body, actor=actor)
    if values is None:
        return False
    db.add(AiMemory(log_id=proposal_id, embedding=values, text=body))
    db.flush()
    return True


#: Entschiedene, teilbare Fälle ohne Zahlen (dieselbe Regel wie ``shareable``) – je Vorschlag
#: gibt es genau einen Entscheid (``ix_log_decided`` ist eindeutig).
_MISSING = text("""
SELECT p.id, p.payload, p.actor_id, d.payload AS decided
  FROM log d
  JOIN log p ON p.id = (d.payload ->> 'proposal')::bigint AND p.event = 'proposal'
  LEFT JOIN ai_memory m ON m.log_id = p.id
 WHERE d.event = 'proposal.decided' AND m.log_id IS NULL
   AND (p.payload ->> 'kind' IN ('change', 'create')
        OR (p.payload ->> 'kind' = 'file' AND d.payload ->> 'outcome' = ANY(:filed)))
 ORDER BY d.id DESC LIMIT :n""")


def missing(db: Session, limit: int = 20
            ) -> list[tuple[int, dict[str, Any], Optional[int], dict[str, Any]]]:
    """Entschiedene Fälle ohne Bedeutungs-Zahlen – die zuletzt entschiedenen zuerst (der Takt
    holt sie nach): (Vorschlag, Nutzlast, in wessen Namen, Entscheid)."""
    return [(r.id, r.payload or {}, r.actor_id, r.decided or {})
            for r in db.execute(_MISSING, {"n": limit, "filed": list(FILED)})]


#: Erst die nächsten Nachbarn (reine Index-Suche, HNSW), dann ihr Entscheid – jeder Eintrag in
#: ``ai_memory`` ist entschieden, also geht keiner an den Join verloren.
_SIMILAR = text("""
SELECT n.log_id, n.text, n.distance, d.payload AS decided
  FROM (SELECT m.log_id, m.text, (m.embedding <=> CAST(:q AS vector)) AS distance
          FROM ai_memory m
         WHERE m.is_active
         ORDER BY m.embedding <=> CAST(:q AS vector)
         LIMIT :k) n
  JOIN log d ON d.event = 'proposal.decided' AND (d.payload ->> 'proposal')::bigint = n.log_id
 ORDER BY n.distance""")


def similar(db: Session, query: str, *, actor: Optional[UserProfile], k: int = CASES) -> list[Case]:
    """►►► **Die ähnlichsten Fälle** (entschieden, für jedes Personal sichtbar) zu einem Text –
    oder keine (kein Vertex, Deckel, Fehler, noch keine Fälle). Nie eine Ausnahme. ◄◄◄"""
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
