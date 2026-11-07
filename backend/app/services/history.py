"""►►► **Der Verlauf – ein Verlauf für jeden Datensatz** (Projektakte «Die lernende Firma»
§4.2, Schritt 2.5). ◄◄◄

Jede Nummer hat einen Verlauf, gemischt nach Zeit und **in Seiten** (die neuesten 30, ältere
beim Rollen – er wächst nie mit):

* **Nachrichten** (Mail, Anruf, intern, Notiz) – an denen der Datensatz beteiligt ist
  (``communication.scope``: eine Person als Absenderin oder Partei, eine Firma über ihre
  Personen, jeder andere Datensatz über «Betrifft»);
* **Dokumente**, die an ihm hängen (aktive ``document_refs``, ``access.visible``);
* **Änderungen** aus dem Log an seiner Nummer – je Handlung (``request_id``) ein Block,
  technisch: wer · wann · Tabelle · ``feld: alt → neu``; Ereignisse mit Namen und ihren
  einfachen Angaben. Keine Sätze je Ereignis, übersetzt werden nur die Tabellennamen
  (``domain/log.TABLE_WORDS``).

**Die Reihenfolge** ist (Zeit, Art, Nummer), absteigend; der Cursor ``before`` ist genau
dieser Schlüssel. Jede Quelle liefert, was vor ihm liegt – so bleibt eine Seite stabil, auch
wenn mehrere Einträge dieselbe Zeit tragen.

**Sichtbarkeit:** wer einen Datensatz öffnen darf, sieht seinen ganzen Verlauf – mit den
Regeln, die schon gelten: Dokumente nach ``access`` (auch das Dokument selbst), die
Zeiterfassung einer Person nur sie selbst und der Admin (``timekeeping.may_see``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import text, tuple_
from sqlalchemy.orm import Session

from ..domain.log import TABLE_WORDS
from ..models import Document, DocumentRef, UserProfile
from ..schemas.history import (ChangeBlock, DocumentEntry, FieldChange, HistoryEntry,
                               HistoryPage, LogRow)
from . import access, communication, records

#: ►►► **Was der Verlauf aus dem Log NICHT zeigt – die eine Ausnahmeliste.** ◄◄◄
#: * ``messages``, ``message_parties`` – jede Nachricht steht schon als Nachricht da; ihre
#:   Zeilen im Log wären dieselbe Sache ein zweites Mal.
#: * ``objects`` – die Vergabe einer Nummer: Rauschen (die Zeile des Datensatzes sagt es).
#: * ``webauthn_challenges`` – je Anmeldung eine Wegwerf-Frage: Rauschen.
#: ``documents``/``document_refs`` stehen im Log an der Nummer des **Dokuments** (nicht am
#: Datensatz, an dem es hängt) – dort sind sie seine eigenen Änderungen, keine Doppelung.
#: Ereignisse (``action = 'event'``) zeigt er – ausser denen der KI (``HIDDEN_EVENTS``).
HIDDEN = frozenset({"messages", "message_parties", "objects", "webauthn_challenges"})
#: ►► **Die Ereignisse der KI stehen nicht im Verlauf** – sie haben ihren eigenen Ort: eine
#:    Erfassung in «Abgelegt» (nur für die Person, die erfasst hat), ein Vorschlag und ein
#:    Hinweis im Angehefteten; was abgelegt wird, steht danach als Notiz da. Im Verlauf wären sie
#:    dieselbe Sache ein zweites Mal – und der rohe Text einer Erfassung für jeden lesbar. ◄◄
HIDDEN_EVENTS = frozenset({"intake", "intake.failed", "proposal", "proposal.decided", "pin",
                           "pin.solved", "mail.followed", "follow.start"})
_EVENTS = sorted(HIDDEN_EVENTS)
#: Die Zeiterfassung einer Person sieht nur sie selbst und der Admin.
PRIVATE = frozenset({"time_entries", "time_contracts"})

#: Die Art eines Eintrags und ihr Rang bei gleicher Zeit (höher = weiter unten, neuer).
RANK = {"change": 0, "document": 1, "message": 2}
#: Bei einer neuen Zeile nichts zeigen, was jede hat.
_ROUTINE = frozenset({"id", "created_at", "updated_at"})
#: So lang wird ein Wert höchstens gezeigt.
_CUT = 200
#: So viele Angaben eines Ereignisses höchstens.
_PAYLOAD = 8
_BIG = 2 ** 62

Key = tuple[datetime, int, int]


def _key(at: datetime, kind: str, ident: int) -> str:
    return f"{at.isoformat()}~{RANK[kind]}~{ident}"


def parse(cursor: Optional[str]) -> Optional[Key]:
    if not cursor:
        return None
    try:
        at, rank, ident = cursor.split("~")
        return datetime.fromisoformat(at), int(rank), int(ident)
    except ValueError as exc:
        raise HTTPException(400, detail=f"Cursor «{cursor}» ist ungültig.") from exc


def _bound(before: Optional[Key], kind: str) -> Optional[tuple[datetime, int]]:
    """Der Cursor in der Sprache einer Quelle: (Zeit, Nummer) – geliefert wird, was davor
    liegt. Bei gleicher Zeit entscheidet der Rang der Art, dann die Nummer."""
    if before is None:
        return None
    at, rank, ident = before
    mine = RANK[kind]
    return (at, _BIG) if mine < rank else (at, ident) if mine == rank else (at, 0)


# ─── Der Wert eines Feldes ────────────────────────────────────────────────────────────

def _text(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= _CUT else s[:_CUT] + "…"


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _changes_of(action: str, changes: Optional[dict[str, Any]]) -> list[FieldChange]:
    """``feld: alt → neu`` – aus dem, was der Trigger schrieb: bei ``update`` (auch dem
    weichen Löschen) Paare, bei ``insert`` die Werte, bei ``delete`` die alten Werte."""
    if not changes:
        return []
    pairs = action == "update" or isinstance(changes.get("is_active"), list)
    out = []
    for field, v in changes.items():
        if pairs and isinstance(v, list) and len(v) == 2:
            out.append(FieldChange(field=field, old=_text(v[0]), new=_text(v[1])))
        elif not pairs and field not in _ROUTINE and not _empty(v):
            new, old = (None, _text(v)) if action == "delete" else (_text(v), None)
            out.append(FieldChange(field=field, old=old, new=new))
    return out


def _payload_of(payload: Optional[dict[str, Any]]) -> dict[str, str]:
    """Die einfachen Angaben eines Ereignisses (Text, Zahl, ja/nein) – roh, ohne Satz."""
    out: dict[str, str] = {}
    for k, v in (payload or {}).items():
        if isinstance(v, (str, int, float, bool)) and len(out) < _PAYLOAD:
            out[k] = _text(v) or ""
    return out


# ─── Die drei Quellen ─────────────────────────────────────────────────────────────────

#: Gruppiert wird nur ein Fenster der neuesten sichtbaren Zeilen (``_SCAN`` je gesuchtem Block):
#: sonst kostete jede Seite so viel wie das ganze Leben des Datensatzes.
_SCAN = 200

_BLOCKS = text("""
SELECT request_id, max(at) AS at, max(id) AS id FROM (
  SELECT request_id, at, id FROM log
   WHERE object_id = :o AND at <= :bat AND (CASE WHEN action = 'event' THEN event <> ALL(:hidden_events) ELSE table_name <> ALL(:hidden) END)
   ORDER BY at DESC, id DESC LIMIT :scan) w
 GROUP BY request_id
HAVING (max(at), max(id)) < (:bat, :bid)
   -- Eine Handlung über mehrere Transaktionen (der Mail-Abgleich) steht dort, wo ihre
   -- jüngste Zeile steht – liegt die schon vor dem Cursor, war sie auf einer früheren Seite.
   AND NOT EXISTS (SELECT 1 FROM log l
                    WHERE l.request_id = w.request_id AND l.object_id = :o
                      AND (CASE WHEN l.action = 'event' THEN l.event <> ALL(:hidden_events) ELSE l.table_name <> ALL(:hidden) END)
                      AND (l.at, l.id) >= (:bat, :bid))
 ORDER BY 2 DESC, 3 DESC LIMIT :n""")

_ROWS = text("""
SELECT request_id, actor_kind, actor_id, source, action, table_name, row_key, event,
       changes, payload FROM log
 WHERE object_id = :o AND request_id::text = ANY(:r) AND (CASE WHEN action = 'event' THEN event <> ALL(:hidden_events) ELSE table_name <> ALL(:hidden) END)
 ORDER BY id""")


def _changes(db: Session, oid: int, hidden: list[str], before: Optional[Key], n: int
             ) -> list[HistoryEntry]:
    bound = _bound(before, "change") or (datetime(9999, 1, 1, tzinfo=timezone.utc), _BIG)
    blocks = db.execute(_BLOCKS, {"o": oid, "hidden": hidden, "hidden_events": _EVENTS, "bat": bound[0],
                                  "bid": bound[1], "n": n, "scan": n * _SCAN}).all()
    if not blocks:
        return []
    rows: dict[Any, list[Any]] = {}
    for r in db.execute(_ROWS, {"o": oid, "hidden": hidden, "hidden_events": _EVENTS,
                                "r": [str(b.request_id) for b in blocks]}):
        rows.setdefault(r.request_id, []).append(r)
    actors = _names(db, {r[0].actor_id for r in rows.values() if r[0].actor_id})
    out = []
    for b in blocks:
        rs = rows.get(b.request_id, [])
        head = rs[0]
        out.append(HistoryEntry(
            key=_key(b.at, "change", b.id), kind="change", at=b.at,
            change=ChangeBlock(
                actor_kind=head.actor_kind, actor_id=head.actor_id,
                actor_name=actors.get(head.actor_id), source=head.source,
                rows=[LogRow(action=r.action, table=r.table_name,
                             word=TABLE_WORDS.get(r.table_name or ""), row=r.row_key,
                             event=r.event, changes=_changes_of(r.action, r.changes),
                             payload=_payload_of(r.payload)) for r in rs])))
    return out


def _documents(db: Session, oid: int, viewer: UserProfile, before: Optional[Key], n: int
               ) -> list[HistoryEntry]:
    q = (db.query(DocumentRef.id, DocumentRef.created_at, DocumentRef.part, DocumentRef.field,
                  Document.object_id, Document.art, Document.name, Document.deleted_at)
         .join(Document, Document.id == DocumentRef.document_id)
         .filter(DocumentRef.object_id == oid, DocumentRef.is_active.is_(True)))
    bound = _bound(before, "document")
    if bound is not None:
        q = q.filter(tuple_(DocumentRef.created_at, DocumentRef.id) < bound)
    rows = access.visible(q, viewer).order_by(
        DocumentRef.created_at.desc(), DocumentRef.id.desc()).limit(n).all()
    return [HistoryEntry(key=_key(r.created_at, "document", r.id), kind="document",
                         at=r.created_at,
                         document=DocumentEntry(object_id=r.object_id, art=r.art, name=r.name,
                                                part=r.part, field=r.field,
                                                deleted=r.deleted_at is not None))
            for r in rows]


def _messages(db: Session, oid: int, before: Optional[Key], n: int) -> list[HistoryEntry]:
    found, sizes = communication.page(db, communication.scope(db, oid),
                                      _bound(before, "message"), n)
    built = {m.id: m for m in communication.load(db, [i for i, _ in found])}
    out = []
    for i, at in found:
        m = built[i]
        m.recipients = sizes.get(i, 0)
        out.append(HistoryEntry(key=_key(at, "message", i), kind="message", at=at, message=m))
    return out


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    people = {u.object_id: u.display_name for u in
              db.query(UserProfile).filter(UserProfile.object_id.in_(ids)).all()} if ids else {}
    rest = records.labels(db, ids - set(people))
    return {**people, **{k: r.label for k, r in rest.items()}}


# ─── Die Seite ─────────────────────────────────────────────────────────────────────────

def assert_visible(db: Session, oid: int, viewer: UserProfile) -> Optional[UserProfile]:
    """Wer den Datensatz öffnen darf, sieht seinen Verlauf. Gibt die Person zurück, wenn der
    Datensatz eine ist (ihre Zeiterfassung hat eine eigene Regel)."""
    found = records.labels(db, [oid]).get(oid)
    if found is None:
        raise HTTPException(404, detail=f"Datensatz «{oid}» gibt es nicht.")
    if found.type == "document":
        doc = db.query(Document).filter(Document.object_id == oid).one()
        refs = db.query(DocumentRef).filter(DocumentRef.document_id == doc.id,
                                            DocumentRef.is_active.is_(True)).all()
        if not access.may(viewer, refs):
            raise HTTPException(404, detail=f"Datensatz «{oid}» gibt es nicht.")
    if found.type == "user":
        return db.query(UserProfile).filter(UserProfile.object_id == oid).one()
    return None


def page(db: Session, oid: int, viewer: UserProfile, *, before: Optional[str] = None,
         limit: int = communication.PAGE) -> HistoryPage:
    """►►► **Eine Seite des Verlaufs** – die ``limit`` neuesten Einträge vor ``before``. ◄◄◄
    Jede Quelle liefert höchstens ``limit + 1``; gemischt wird nach (Zeit, Art, Nummer), und
    ob es weitergeht, sagt der eine Eintrag zu viel."""
    from .timekeeping import may_see
    person = assert_visible(db, oid, viewer)
    cursor = parse(before)
    hidden = set(HIDDEN)
    if person is not None and not may_see(viewer, person):
        hidden |= PRIVATE
    n = limit + 1
    merged = (_changes(db, oid, sorted(hidden), cursor, n) + _documents(db, oid, viewer, cursor, n)
              + _messages(db, oid, cursor, n))
    merged.sort(key=lambda e: (e.at, RANK[e.kind], int(e.key.rsplit("~", 1)[1])), reverse=True)
    shown = merged[:limit]
    return HistoryPage(entries=shown,
                       before=shown[-1].key if len(merged) > limit and shown else None)
