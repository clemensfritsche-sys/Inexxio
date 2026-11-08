"""►►► **Im Wissen suchen – nach Bedeutung, nicht nach Wörtern.** ◄◄◄ (Phase 5 §8.4)

Was die Firma weiss, steht in **Notizen** und **Dokumenten**; wie sie über Vorschläge der KI
entschied, in **entschiedenen Handgriffen** (Fälle). Jeder solche Eintrag bekommt Bedeutungs-Zahlen
(Vertex AI über ``ai.embed``, pgvector in ``ai_memory``). «Die Pumpe tropft» findet dann auch
«Wellendichtung undicht» – andere Wörter, dieselbe Sache.

* ``KINDS`` – ``handgriff`` · ``note`` · ``document``; je Art EINE Stelle, die sagt, was eingebettet
  wird (``_TEXT``) und welche noch fehlen (``_MISSING``). Der Takt holt nach (``catch_up``).
* **Nur, was jedes Personal sehen darf:** ein Handgriff aus einem Gespräch erst, wenn er
  ausgeführt ist (dann steht sein Ergebnis ohnehin da); weggelegte nur aus Mails. Notizen und
  Dokumente werden beim Suchen gegen die Rechte des Lesers geprüft (``ai_tools.reader``).
* ``search`` – die ähnlichsten Einträge zu einem Text, mit Datum und Datensatz; ``as_prompt``
  macht aus Fällen den Abschnitt für die Anfrage.

Ohne Vertex (nicht eingerichtet, Deckel, Fehler) gibt es keine Suche nach Bedeutung – sonst
fehlt nichts. ``ai_memory`` ist eine Ableitung und entsteht im Takt neu.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import AiMemory, UserProfile
from . import ai

#: Die Arten im Gedächtnis.
KINDS = ("handgriff", "note", "document")
#: So viele Treffer höchstens.
FOUND = 5
#: Ab dieser Kosinus-Distanz (0 = gleich, 2 = Gegenteil) ist nichts mehr «ähnlich».
FAR = 0.6
#: So viele Einträge holt der Takt je Lauf nach.
PER_RUN = 20
#: So viel Text eines Dokuments wird eingebettet.
DOC_TEXT = 6000


@dataclass(frozen=True)
class Found:
    kind: str
    ref_id: int
    text: str
    at: datetime
    distance: float
    #: Der Datensatz, an dem es steht (Notiz: woran sie hängt; Dokument: es selbst).
    object_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Was eingebettet wird – je Art EINE Abfrage, die Text und Datum liefert
# ---------------------------------------------------------------------------

#: Handgriffe mit Entscheid, die jedes Personal sehen darf; der Entscheid ist Teil des Texts.
_HANDGRIFFE = """
SELECT h.id AS ref_id, coalesce(d.at, x.at) AS at, h.object_id,
       concat('Quelle: ', CASE WHEN h.payload ->> 'mail' IS NULL THEN 'Gespräch' ELSE 'Mail' END,
              E'\\nHandgriff: ', h.payload ->> 'line', ' (', h.payload ->> 'method', ' ',
              h.payload ->> 'path', E')\\n⇒ ',
              CASE WHEN d.id IS NOT NULL THEN 'ausgeführt' ELSE 'verworfen' END) AS text
  FROM log h
  LEFT JOIN log d ON d.event = 'handgriff.done' AND (d.payload ->> 'handgriff')::bigint = h.id
  LEFT JOIN log x ON x.event = 'handgriff.dropped' AND (x.payload ->> 'handgriff')::bigint = h.id
                 AND x.payload ->> 'by' = 'person'
 WHERE h.event = 'handgriff'
   AND (d.id IS NOT NULL OR (x.id IS NOT NULL AND h.payload ->> 'mail' IS NOT NULL))"""

#: Notizen (Wissen an einem Datensatz) – Betreff und Text, am Datensatz, an dem sie hängen.
_NOTES = """
SELECT m.id AS ref_id, m.at, p.object_id,
       concat(coalesce(m.subject, ''), E'\\n', left(m.body, 4000)) AS text
  FROM messages m
  JOIN message_parties p ON p.message_id = m.id AND p.role = 'about'
 WHERE m.channel = 'note' AND m.is_active"""

#: Dokumente – Art, Name, Stichworte und der gelesene Text.
_DOCUMENTS = f"""
SELECT d.object_id AS ref_id, d.created_at AS at, d.object_id,
       concat(d.art, ' · ', d.name, E'\\n', coalesce(d.keywords::text, ''), E'\\n',
              left(coalesce(d.text, ''), {DOC_TEXT})) AS text
  FROM documents d
 WHERE d.is_active"""

_SOURCES = {"handgriff": _HANDGRIFFE, "note": _NOTES, "document": _DOCUMENTS}


def _missing(db: Session, kind: str, limit: int) -> list[Any]:
    sql = (f"SELECT s.ref_id, s.at, s.text FROM ({_SOURCES[kind]}) s "
           f"WHERE NOT EXISTS (SELECT 1 FROM ai_memory a WHERE a.kind = :k AND a.ref_id = s.ref_id) "
           f"AND length(trim(s.text)) > 3 ORDER BY s.at DESC LIMIT :n")
    return db.execute(text(sql), {"k": kind, "n": limit}).all()


def remember(db: Session, kind: str, ref_id: int, body: str, at: datetime, *,
             actor: Optional[UserProfile]) -> bool:
    """Die Zahlen eines Eintrags ablegen – ``True``, wenn sie jetzt da sind."""
    if db.get(AiMemory, (kind, ref_id)) is not None:
        return True
    values = ai.embed(db, body, actor=actor)
    if values is None:
        return False
    db.add(AiMemory(kind=kind, ref_id=ref_id, at=at, embedding=values, text=body))
    db.flush()
    return True


def catch_up(db: Session, deadline: float, limit: int = PER_RUN) -> int:
    """►► **Der Takt: was noch keine Zahlen hat** – Fälle, Notizen, Dokumente, die neuesten
    zuerst. Speichert je Eintrag; ohne Vertex oder am Deckel: nichts. ◄◄"""
    if not ai.embed_ready():
        return 0
    n = 0
    for kind in KINDS:
        for r in _missing(db, kind, limit):
            if time.monotonic() >= deadline:
                return n
            if not remember(db, kind, int(r.ref_id), r.text, r.at, actor=None):
                return n            # Deckel, Vertex aus, Fehler – im nächsten Lauf
            db.commit()
            n += 1
    return n


# ---------------------------------------------------------------------------
# Suchen
# ---------------------------------------------------------------------------

_NEAREST = text("""
SELECT m.kind, m.ref_id, m.text, m.at, (m.embedding <=> CAST(:q AS vector)) AS distance
  FROM ai_memory m
 WHERE m.is_active AND m.kind = ANY(:kinds)
 ORDER BY m.embedding <=> CAST(:q AS vector)
 LIMIT :k""")


def _where(db: Session, rows: list[Any]) -> dict[tuple[str, int], int]:
    """Der Datensatz je Treffer: Notiz → woran sie hängt, Dokument → es selbst, Fall → sein
    Datensatz."""
    out: dict[tuple[str, int], int] = {}
    notes = [r.ref_id for r in rows if r.kind == "note"]
    if notes:
        for mid, oid in db.execute(text("SELECT message_id, object_id FROM message_parties "
                                        "WHERE role = 'about' AND message_id = ANY(:ids)"),
                                   {"ids": notes}):
            out.setdefault(("note", mid), oid)
    cases = [r.ref_id for r in rows if r.kind == "handgriff"]
    if cases:
        for hid, oid in db.execute(text("SELECT id, object_id FROM log WHERE id = ANY(:ids)"),
                                   {"ids": cases}):
            out[("handgriff", hid)] = oid
    for r in rows:
        if r.kind == "document":
            out[("document", r.ref_id)] = r.ref_id
    return out


def _visible(db: Session, object_ids: Iterable[int]) -> set[int]:
    """Was jedes Personal sehen darf – gelesen als gemeinsamer Betrachter."""
    from fastapi import HTTPException

    from . import ai_tools, history
    reader = ai_tools.reader()
    ok = set()
    for oid in set(object_ids):
        try:
            history.assert_visible(db, oid, reader)
            ok.add(oid)
        except HTTPException:
            pass
    return ok


def search(db: Session, query: str, *, actor: Optional[UserProfile],
           kinds: tuple[str, ...] = KINDS, k: int = FOUND) -> list[Found]:
    """►►► **Die ähnlichsten Einträge** zu einem Text – nur, was jedes Personal sehen darf, die
    nächsten zuerst. Nie eine Ausnahme: ohne Vertex, am Deckel, ohne Einträge: leer. ◄◄◄"""
    if not query.strip() or not ai.embed_ready():
        return []
    if not db.execute(text("SELECT EXISTS (SELECT 1 FROM ai_memory WHERE kind = ANY(:k))"),
                      {"k": list(kinds)}).scalar():
        return []
    values = ai.embed(db, query[:4000], actor=actor, query=True)
    if values is None:
        return []
    q = "[" + ",".join(f"{v:.7g}" for v in values) + "]"
    rows = [r for r in db.execute(_NEAREST, {"q": q, "kinds": list(kinds), "k": k * 3})
            if r.distance is not None and r.distance <= FAR]
    where = _where(db, rows)
    seen = _visible(db, where.values())
    out = [Found(r.kind, r.ref_id, r.text, r.at, float(r.distance), where.get((r.kind, r.ref_id)))
           for r in rows if where.get((r.kind, r.ref_id)) in seen]
    return out[:k]


def as_prompt(found: list[Found]) -> str:
    """Fälle als Abschnitt der Anfrage – wie wir früher über Handgriffe der KI entschieden."""
    cases = [f for f in found if f.kind == "handgriff"]
    if not cases:
        return ""
    lines = ["So haben wir früher über ähnliche Handgriffe entschieden – richte dich danach:"]
    lines += [f"- {c.text.replace(chr(10), ' · ')}" for c in cases]
    return "\n".join(lines)


def as_lines(found: list[Found]) -> str:
    """Wissen als Text für die KI – je Treffer Datum, Art, Datensatz und Inhalt."""
    words = {"note": "Notiz", "document": "Dokument", "handgriff": "Fall"}
    return "\n".join(f"- {f.at:%d.%m.%Y} · {words[f.kind]} {f.ref_id} an {f.object_id}: "
                     f"{f.text.replace(chr(10), ' · ')[:600]}" for f in found) or "Nichts gefunden."
