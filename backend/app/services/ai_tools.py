"""►►► **Die Lese-Werkzeuge der KI – sie liest, was jedes Personal sehen darf: nie mehr als die
Person, nie Privates.** ◄◄◄ (Projektakte «Die lernende Firma» §4.3, Schritt 3.1)

Was die KI findet, wird ein Vorschlag oder Hinweis – und den sieht **jedes** Personal. Darum
liest sie nie mit den Rechten der Person, für die sie gerade arbeitet (oft ein Admin oder wer das
Postfach verbunden hat), sondern immer als ``reader``: ein gemeinsamer Betrachter mit der Rolle
``employee`` und **ohne eigene Nummer** – also ohne eigene Zeiterfassung und ohne private
Dokumentteile (``access.may``, ``history.page`` filtern das). Wer handelt, steht trotzdem im Log
(``ai.call`` mit Kosten, Vorschlag und Hinweis im Namen der Person).

Vier Werkzeuge, alle **nur lesend** und alle mit ``reader`` als Betrachter (``tools_for``):

* ``find`` – «welchen Datensatz meinst du?»: Nummer ODER Name (``records.search``, dieselbe
  Suche wie jedes Referenzfeld);
* ``record`` – das Wichtigste eines Datensatzes: seine Angaben (ohne Geheimes und Technisches),
  bei einem Dokument Text und Stichworte – nur, wenn der Akteur es sehen darf
  (``access.may``);
* ``history`` – die neuesten Einträge seines Verlaufs (``history.page`` mit dem Akteur als
  Betrachter: Dokumente nach ``access``, die Zeiterfassung nur selbst/Admin);
* ``wissen`` – im Wissen suchen, nach Bedeutung (``memory.search``: Notizen, Dokumente, Fälle).

Es gibt keinen eigenen Weg an den Regeln vorbei: jedes Werkzeug fragt dieselben Dienste wie die
Oberfläche. Was ``reader`` nicht sehen darf, gibt es für die KI nicht («nicht gefunden»).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain.log import SECRET_COLUMNS
from ..models import (Article, CompanySettings, Document, DocumentRef, Instance, Order,
                      UserProfile)
from . import access, records
from .ai import Tool

#: Spalten, die keine Angabe für die KI sind: Schlüssel, Technik, Zeitstempel der Zeile.
_SKIP = frozenset({"id", "firebase_uid", "photo_url", "created_at", "updated_at", "is_active",
                   "file_id", "sha256", "uid_key", "name_key", "article_id",
                   "process_version", "replaces_object_id"}) | SECRET_COLUMNS

#: Je Typ das Modell, dessen Zeile die Nummer trägt.
_MODELS: dict[str, Any] = {"user": UserProfile, "organization": CompanySettings,
                           "order": Order, "article": Article, "instance": Instance}

#: So viele Einträge des Verlaufs gibt ``history`` höchstens.
HISTORY_LIMIT = 20
_CUT = 600


def _value(v: Any) -> Optional[str]:
    if v is None or v == "" or isinstance(v, (bytes, bytearray, memoryview)):
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    if isinstance(v, (dict, list)):
        return None
    s = str(v)
    return s if len(s) <= _CUT else s[:_CUT] + "…"


def _columns(row: Any) -> list[str]:
    out = []
    for col in row.__table__.columns:
        if col.name in _SKIP:
            continue
        text = _value(getattr(row, col.key, None))
        if text is not None:
            out.append(f"{col.name}: {text}")
    return out


def _not_found(object_id: Any) -> str:
    return f"Datensatz {object_id} nicht gefunden (oder nicht sichtbar)."


def _document(db: Session, viewer: UserProfile, object_id: int) -> str:
    doc = db.query(Document).filter(Document.object_id == object_id).first()
    if doc is None:
        return _not_found(object_id)
    refs = db.query(DocumentRef).filter(DocumentRef.document_id == doc.id,
                                        DocumentRef.is_active.is_(True)).all()
    if not access.may(viewer, refs):
        return _not_found(object_id)
    names = records.labels(db, [r.object_id for r in refs])
    lines = [f"Dokument {object_id}", f"art: {doc.art}", f"name: {doc.name}",
             f"angelegt: {doc.created_at.isoformat() if doc.created_at else ''}"]
    if doc.deleted_at:
        lines.append(f"gelöscht: {doc.deleted_at.isoformat()} ({doc.delete_reason or ''})")
    lines += [f"hängt an: {names[r.object_id].label if r.object_id in names else r.object_id} "
              f"({r.object_id})" for r in refs]
    if doc.keywords:
        lines.append(f"stichworte: {doc.keywords[:400]}")
    if doc.facts:
        lines.append("angaben: " + "; ".join(f"{k}: {v}" for k, v in list(doc.facts.items())[:30]))
    if doc.text:
        lines.append("text: " + doc.text[:3000])
    return "\n".join(lines)


def record(db: Session, viewer: UserProfile, object_id: Any) -> str:
    """Das Wichtigste eines Datensatzes – mit den Rechten von ``viewer``."""
    try:
        oid = int(object_id)
    except (TypeError, ValueError):
        return _not_found(object_id)
    found = records.labels(db, [oid]).get(oid)
    if found is None or not access.is_staff(viewer):
        return _not_found(oid)
    if found.type == "document":
        return _document(db, viewer, oid)
    model = _MODELS[found.type]
    row = db.query(model).filter(model.object_id == oid).first()
    lines = [f"{found.label} ({oid})"] + (_columns(row) if row is not None else [])
    if found.type == "user" and row is not None and row.company_object_id:
        company = records.labels(db, [row.company_object_id]).get(row.company_object_id)
        if company:
            lines.append(f"firma: {company.label} ({company.object_id})")
    if found.type == "order" and row is not None:
        from . import order_state
        lines.append(f"status: {order_state.order_status(db, row)}")
        steps = order_state.steps_of(db, row)
        if steps:
            lines.append("module: " + " → ".join(s.module_type for s in steps))
    return "\n".join(lines)


def entry_line(e: Any) -> str:
    """Ein Eintrag des Verlaufs als eine Zeile für die KI – knapp, ohne Formatierung."""
    when = e.at.isoformat(timespec="minutes")
    if e.message is not None:
        m = e.message
        who = getattr(m.sender, "name", "") or ""
        body = " ".join((m.body or "").split())[:_CUT]
        return f"{when} · Nachricht ({m.channel.label}) von {who} · «{m.subject or ''}»: {body}"
    if e.document is not None:
        d = e.document
        return f"{when} · Dokument {d.object_id}: {d.art} · {d.name}"
    c = e.change
    parts = []
    for r in c.rows:
        if r.event:
            parts.append(r.event + (" " + ", ".join(f"{k}={v}" for k, v in r.payload.items())
                                    if r.payload else ""))
        else:
            parts.append(f"{r.word or r.table} {r.action}: " + ", ".join(
                f"{ch.field} {ch.old or '∅'}→{ch.new or '∅'}" for ch in r.changes))
    who = c.actor_name or c.actor_kind
    return f"{when} · Änderung von {who}: " + "; ".join(parts)[:_CUT]


def history(db: Session, viewer: UserProfile, object_id: Any) -> str:
    """Die neuesten Einträge des Verlaufs – dieselbe Seite, die ``viewer`` sähe."""
    from . import history as hist
    try:
        oid = int(object_id)
        page = hist.page(db, oid, viewer, limit=HISTORY_LIMIT)
    except (TypeError, ValueError, HTTPException):
        return _not_found(object_id)
    if not page.entries:
        return "Noch nichts im Verlauf."
    return "\n".join(entry_line(e) for e in page.entries)


def find(db: Session, viewer: UserProfile, q: Any) -> str:
    """Datensätze nach Nummer oder Name – wie jedes Referenzfeld."""
    if not access.is_staff(viewer):
        return "Nichts gefunden."
    found = records.search(db, str(q or ""))
    if not found:
        return "Nichts gefunden."
    return "\n".join(f"{r.object_id} · {r.label}" for r in found)


def reader() -> UserProfile:
    """►►► **Der gemeinsame Betrachter der KI** – die Rechte, die jedes Personal hat: Rolle
    ``employee``, keine eigene Nummer (nichts ist «seins»), nie gespeichert. ◄◄◄"""
    return UserProfile(role="employee")


def tools_for(db: Session) -> list[Tool]:
    """►►► **Die Werkzeuge für einen Aufruf** – gebunden an ``reader()``, nie an die Person, in
    deren Namen die KI arbeitet (ihr Ergebnis sehen alle). ◄◄◄"""
    viewer = reader()
    return [
        Tool("find", "Sucht Datensätze (Personen, Firmen, Aufträge, Artikel, Instanzen) nach "
                     "Objektnummer oder Name. Gibt «Nummer · Typ · Name» je Treffer.",
             {"q": {"type": "string", "description": "Nummer oder ein Teil des Namens"}},
             lambda a: find(db, viewer, a.get("q"))),
        Tool("record", "Liest die Angaben eines Datensatzes (Person, Firma, Auftrag, Artikel, "
                       "Instanz, Dokument) über seine Objektnummer.",
             {"object_id": {"type": "integer", "description": "9-stellige Objektnummer"}},
             lambda a: record(db, viewer, a.get("object_id"))),
        Tool("history", "Liest die neuesten Einträge im Verlauf eines Datensatzes: Nachrichten, "
                        "Notizen, Dokumente, Änderungen.",
             {"object_id": {"type": "integer", "description": "9-stellige Objektnummer"}},
             lambda a: history(db, viewer, a.get("object_id"))),
        Tool("wissen", "Sucht im Wissen der Firma nach Bedeutung (nicht nach Wörtern): Notizen, "
                       "Dokumente und frühere Entscheide – je Treffer Datum, Datensatz, Inhalt. "
                       "Für «gab es das schon?», «wie war das damals?».",
             {"frage": {"type": "string", "description": "Worum es geht, in eigenen Worten"}},
             lambda a: _knowledge(db, a.get("frage"))),
    ]


def _knowledge(db: Session, question: Any) -> str:
    from . import memory
    return memory.as_lines(memory.search(db, str(question or ""), actor=None))
