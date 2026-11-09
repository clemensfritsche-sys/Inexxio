"""►►► **Die Lese-Werkzeuge der KI – sie liest, was jedes Personal sehen darf: nie mehr als die
Person, nie Privates.** ◄◄◄ (Projektakte «Die lernende Firma» §4.3, Schritt 3.1)

Was die KI findet, wird ein Vorschlag oder Hinweis – und den sieht **jedes** Personal. Darum
liest sie nie mit den Rechten der Person, für die sie gerade arbeitet (oft ein Admin oder wer das
Postfach verbunden hat), sondern immer als ``reader``: ein gemeinsamer Betrachter mit der Rolle
``employee`` und **ohne eigene Nummer** – also ohne eigene Zeiterfassung und ohne private
Dokumentteile (``access.may``, ``history.page`` filtern das). Wer handelt, steht trotzdem im Log
(``ai.call`` mit Kosten, Vorschlag und Hinweis im Namen der Person).

Vier Werkzeuge, alle **nur lesend** und alle mit ``reader`` als Betrachter (``tools_for``):

* ``find`` – «welchen Datensatz meinst du?»: Nummer ODER Name (``record_labels.search``, dieselbe
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

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Optional
from functools import lru_cache

from sqlalchemy.orm import Session

from ..models import (Document, DocumentRef, UserProfile)
from . import access, record_labels
from .ai import Tool
from ..domain.errors import Rejected
from ..domain import policy

#: ►► **Wo die KI einen Datensatz liest: die Route, die ihn auch einem Menschen zeigt** – mit
#: denselben Rechten und derselben Auswahl der Felder; eine neue Spalte erreicht sie nur, wenn die
#: Route sie zeigt. (Dokumente: ``_document`` – dazu der gelesene Text, nach ``access``.) ◄◄
ROUTES: dict[str, str] = {
    "user": "/api/v1/erp/records/{}",
    "organization": "/api/v1/admin/companies/{}",
    "article": "/api/v1/erp/articles/{}",
    "order": "/api/v1/erp/orders/{}",
    "instance": "/api/v1/erp/instances/{}",
}
#: So viel einer Antwort geht an die KI (Zeichen).
RECORD_MAX = 6000

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
    s = str(v)
    return s if len(s) <= _CUT else s[:_CUT] + "…"


def _pruned(v: Any) -> Any:
    """Ohne Leeres – was nichts sagt, kostet nur."""
    if isinstance(v, dict):
        out = {k: _pruned(x) for k, x in v.items()}
        return {k: x for k, x in out.items() if x not in (None, "", [], {})}
    if isinstance(v, list):
        return [x for x in (_pruned(x) for x in v) if x not in (None, "", [], {})]
    return v


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
    names = record_labels.labels(db, [r.object_id for r in refs])
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
    found = record_labels.labels(db, [oid]).get(oid)
    if found is None or not policy.is_staff(viewer):
        return _not_found(oid)
    if found.type == "document":
        return _document(db, viewer, oid)
    from . import handgriff
    out = handgriff.look(ROUTES[found.type].format(oid), viewer=viewer, db=db)
    if not out.ok:
        return _not_found(oid)
    text = json.dumps(_pruned(out.data), ensure_ascii=False, default=str, separators=(",", ":"))
    return f"{found.label} ({oid})\n" + (text if len(text) <= RECORD_MAX else text[:RECORD_MAX] + "…")


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
    except (TypeError, ValueError, Rejected):
        return _not_found(object_id)
    if not page.entries:
        return "Noch nichts im Verlauf."
    return "\n".join(entry_line(e) for e in page.entries)


def find(db: Session, viewer: UserProfile, q: Any) -> str:
    """Datensätze nach Nummer oder Name – wie jedes Referenzfeld."""
    if not policy.is_staff(viewer):
        return "Nichts gefunden."
    found = record_labels.search(db, str(q or ""))
    if not found:
        return "Nichts gefunden."
    return "\n".join(f"{r.object_id} · {r.label}" for r in found)


def reader() -> UserProfile:
    """►►► **Der gemeinsame Betrachter der KI** – die Rechte, die jedes Personal hat: Rolle
    ``employee``, keine eigene Nummer (nichts ist «seins»), nie gespeichert. ◄◄◄"""
    return UserProfile(role="employee")


def tools_for(db: Session, viewer: Optional[UserProfile] = None) -> list[Tool]:
    """►►► **Die Werkzeuge für einen Aufruf** – gebunden an ``reader()``, nie an die Person, in
    deren Namen die KI arbeitet (ihr Ergebnis sehen alle). Nur wo das Ergebnis allein bei der
    Person bleibt (ihr eigener Claude über MCP, ``services/mcp``), liest sie mit deren Rechten
    (``viewer``). ◄◄◄"""
    viewer = viewer or reader()
    return [
        Tool("find", "Sucht Datensätze (Personen, Firmen, Aufträge, Artikel, Instanzen) nach "
                     "Objektnummer oder Name. Gibt «Nummer · Typ · Name» je Treffer.",
             {"q": {"type": "string", "description": "Nummer oder ein Teil des Namens"}},
             lambda a: find(db, viewer, a.get("q")), doing="sucht"),
        Tool("record", "Liest die Angaben eines Datensatzes (Person, Firma, Auftrag, Artikel, "
                       "Instanz, Dokument) über seine Objektnummer.",
             {"object_id": {"type": "integer", "description": "9-stellige Objektnummer"}},
             lambda a: record(db, viewer, a.get("object_id")), doing="liest"),
        Tool("history", "Liest die neuesten Einträge im Verlauf eines Datensatzes: Nachrichten, "
                        "Notizen, Dokumente, Änderungen.",
             {"object_id": {"type": "integer", "description": "9-stellige Objektnummer"}},
             lambda a: history(db, viewer, a.get("object_id")), doing="liest den Verlauf von"),
        Tool("wissen", "Sucht im Wissen der Firma nach Bedeutung (nicht nach Wörtern): Notizen, "
                       "Dokumente und frühere Entscheide – je Treffer Datum, Datensatz, Inhalt. "
                       "Für «gab es das schon?», «wie war das damals?».",
             {"frage": {"type": "string", "description": "Worum es geht, in eigenen Worten"}},
             lambda a: _knowledge(db, a.get("frage")), doing="sucht im Wissen:"),
    ]


#: Vorbereiten: (Methode, Pfad, Werte, Zeile, wartet auf) → (Handgriff oder None, Ergebnis).
Prepare = Callable[[str, str, Any, str, list[int]], tuple[Optional[int], Any]]


def _op_line(o: Any) -> str:
    return (f"{o.key} – {o.summary}" + (" (lesen: `abrufen`)" if o.method == "GET" else "")
            + (" (nur Admin)" if o.admin else "") + (" (mit Datei: im Entwurf)" if o.hand else ""))


@lru_cache(maxsize=1)
def catalog() -> str:
    """►►► **Was das ERP kann – als Text für den Auftrag** (Schlüssel und Satz je Handlung). ◄◄◄
    Niemand pflegt sie: sie entsteht aus den Routen (``handgriff.operations`` · ``reads``), einmal
    je Start. Steht sie im Auftrag, schlägt die KI nicht erst nach (ein Zug weniger); im
    Zwischenspeicher des Anbieters kostet sie einen Zehntel."""
    from . import handgriff
    return ("Die Handlungen des ERP (schreibende mit `vorbereiten`, lesende mit `abrufen`):\n"
            + "\n".join(_op_line(o) for o in (*handgriff.operations(), *handgriff.reads())))


def erp_tools(prepare: Prepare, viewer: Optional[UserProfile] = None,
              where: Callable[[int], str] = lambda hid: "", *, lookup: bool = True) -> list[Tool]:
    """►►► **Was das ERP kann – EINE Stelle für jede KI** (das «+», Claude über MCP): nachschlagen,
    abrufen (eine lesende Route mit den Rechten von ``viewer``, sonst ``reader``), vorbereiten
    (Probelauf, dann ein Vorschlag; ``prepare`` sagt, wo er hingehört; ``where`` hängt an, wo ihn
    die Person findet). Ausführen gehört nicht hierher – das tut die Person. ``lookup=False``:
    die Liste der Handlungen steht schon im Auftrag (``catalog``), nachschlagen entfällt. ◄◄◄"""
    from . import handgriff

    def find_ops(a: dict[str, Any]) -> str:
        found = handgriff.find(str(a.get("woerter") or ""))
        return "\n".join(_op_line(o) for o in found) or "Nichts."

    def fetch(a: dict[str, Any]) -> str:
        try:
            params = json.loads(a.get("abfrage_json") or "null") or {}
        except ValueError as exc:
            return f"Die Abfrage ist kein JSON: {exc}"
        out = handgriff.look(str(a.get("pfad") or ""), params if isinstance(params, dict) else {},
                             viewer=viewer)
        if not out.ok:
            return f"Geht nicht ({out.status}): {out.detail}"
        return json.dumps(out.data, ensure_ascii=False, default=str)

    def describe(a: dict[str, Any]) -> str:
        op = handgriff.operation(str(a.get("handlung") or ""))
        if op is None:
            return "Diese Handlung gibt es nicht – schlage mit `handlungen` nach."
        return f"{op.key}\n{op.summary}\nWerte (JSON-Schema): {json.dumps(op.schema, ensure_ascii=False)}"

    def prepared(a: dict[str, Any]) -> str:
        method, _, path = str(a.get("handlung") or "").partition(" ")
        try:
            body = json.loads(a.get("werte_json") or "null")
        except ValueError as exc:
            return f"Die Werte sind kein JSON: {exc}"
        hid, out = prepare(method, str(a.get("pfad") or path), body, str(a.get("zeile") or ""),
                           [int(x) for x in a.get("wartet_auf") or []])
        if hid is None:
            return f"Geht nicht ({out.status}): {out.detail}"
        if handgriff.incomplete(out):
            return (f"Vorbereitet als Vorschlag {hid}, noch unvollständig: {out.detail} – die Person "
                    f"ergänzt es, wo sie ihn öffnet.{where(hid)}")
        return f"Vorbereitet als Vorschlag {hid}.{where(hid)}"

    int_list = {"type": "array", "items": {"type": "integer"}}
    return [
        *([] if not lookup else [Tool("handlungen", "Was das ERP kann und zeigt, zu Stichwörtern: Schlüssel und Satz "
             "(lesende mit `abrufen`, schreibende mit `vorbereiten`).",
             {"woerter": {"type": "string"}}, find_ops, doing="schlägt nach:")]),
        Tool("handlung", "Felder einer Handlung bzw. Angaben einer Abfrage (Schlüssel "
             "«METHODE /pfad»).", {"handlung": {"type": "string"}}, describe,
             doing="liest die Handlung"),
        Tool("abrufen", "Lesen, was das ERP zeigt – eine lesende Route (`GET`). `pfad` konkret "
             "(Platzhalter durch Nummern ersetzt), `abfrage_json` die Abfrage als JSON-Objekt "
             "(oder {}).",
             {"pfad": {"type": "string"}, "abfrage_json": {"type": "string"}}, fetch,
             doing="ruft ab:"),
        Tool("vorbereiten", "Einen Vorschlag vorbereiten – mit Probelauf; die Person öffnet und "
             "übernimmt ihn selbst. `handlung` ist der Schlüssel, `pfad` der konkrete Pfad "
             "(Platzhalter durch Nummern ersetzt), `werte_json` die Werte als JSON, `zeile` ein "
             "kurzer Satz in Alltagssprache, was geschieht, mit dem Namen. Braucht er, was ein "
             "anderer Vorschlag anlegt: dessen Nummer in `wartet_auf` und in den Werten "
             "{\"$handgriff\": nummer}.",
             {"handlung": {"type": "string"}, "pfad": {"type": "string"},
              "werte_json": {"type": "string"}, "zeile": {"type": "string"},
              "wartet_auf": int_list}, prepared, doing="bereitet vor:", shows="zeile"),
    ]


def _knowledge(db: Session, question: Any) -> str:
    from . import memory
    return memory.as_lines(memory.search(db, str(question or ""), actor=None))
