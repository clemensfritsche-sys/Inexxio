"""►►► **Im Wissen suchen – nach Bedeutung** (Phase 5 §8.4). ◄◄◄

Vertex AI wird nachgebildet: jeder Text bekommt Zahlen, die nur von einem Stichwort abhängen –
so ist «ähnlich» im Test eindeutig. Die Suche selbst läuft echt (pgvector).

Bug-Formen: (a) eine Notiz mit anderen Wörtern wird nicht gefunden; (b) gefunden wird, was nicht
jedes Personal sehen darf (ein Handgriff aus einem Gespräch, der nie ausgeführt wurde); (c) ein
Eintrag bekommt zweimal Zahlen; (d) ohne Vertex scheitert etwas.
"""

import math
import time
from datetime import datetime, timezone

from app.core.actor import act
from app.core.config import get_settings
from app.models import AiMemory, Message
from app.schemas.communication import MessageIn
from app.services import ai, communication, log, memory
from tests.factories import new_firm, new_person


def _vector(word: str) -> list[float]:
    """768 Zahlen je Stichwort – gleiche Stichworte zeigen in dieselbe Richtung."""
    seed = sum(ord(c) for c in word)
    v = [math.sin(seed * (i + 1)) for i in range(ai.EMBED_DIMS)]
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


#: «tropft» und «undicht» meinen dieselbe Sache – im nachgebildeten Vertex dasselbe Stichwort.
def _word(text: str) -> str:
    t = text.lower()
    if "tropf" in t or "undicht" in t:
        return "dicht"
    return "telefon" if "telefon" in t else t[:20]


def _fake_vertex(monkeypatch):
    monkeypatch.setattr(get_settings(), "vertex_project", "test")
    monkeypatch.setattr(ai, "embed", lambda db, text, *, actor, query=False, **kw: _vector(_word(text)))


def _note(db, who, about, subject, body):
    act(db, "person", who.object_id, "ui")
    return communication.create(db, MessageIn(channel="note", about=[about], subject=subject,
                                              body=body), who)


def test_a_note_is_found_by_meaning_not_by_words(db, monkeypatch):
    """(a) «Die Pumpe tropft» findet «Wellendichtung undicht» – mit Datum und Datensatz."""
    _fake_vertex(monkeypatch)
    staff = new_person(db, "employee")
    firm = new_firm(db)
    note = _note(db, staff, firm.object_id, "Pumpe P3", "Wellendichtung undicht, getauscht.")
    _note(db, staff, firm.object_id, "Anruf", "Neue Telefonnummer der Zentrale.")
    db.flush()
    assert memory.catch_up(db, time.monotonic() + 30) >= 2
    found = memory.search(db, "Die Pumpe tropft wieder", actor=None, kinds=("note",))
    mine = [f for f in found if f.ref_id == note.id]
    assert mine and mine[0].object_id == firm.object_id
    assert "Wellendichtung" in memory.as_lines(mine)


def test_only_what_every_staff_may_see_is_remembered(db, monkeypatch):
    """(b) Ein Handgriff aus einem Gespräch wird erst ein Fall, wenn er ausgeführt ist;
    weggelegt bleibt er privat. Aus einer Mail zählt auch das Weglegen."""
    _fake_vertex(monkeypatch)
    staff = new_person(db, "employee")
    act(db, "person", staff.object_id, "ui")
    payload = {"method": "PATCH", "path": "/api/v1/erp/records/1", "line": "Telefon neu"}
    private = log.event(db, "handgriff", staff.object_id, {**payload, "talk": 1})
    done = log.event(db, "handgriff", staff.object_id, {**payload, "talk": 1})
    mailed = log.event(db, "handgriff", staff.object_id, {**payload, "mail": 1})
    log.event(db, "handgriff.dropped", staff.object_id, {"handgriff": private, "by": "person"})
    log.event(db, "handgriff.done", staff.object_id, {"handgriff": done})
    log.event(db, "handgriff.dropped", staff.object_id, {"handgriff": mailed, "by": "person"})
    db.flush()
    memory.catch_up(db, time.monotonic() + 30)
    kept = {m.ref_id for m in db.query(AiMemory).filter(AiMemory.kind == "handgriff")}
    assert done in kept and mailed in kept
    assert private not in kept, "(b) ein privater, nie ausgeführter Handgriff"
    text = db.get(AiMemory, ("handgriff", done)).text
    assert "Telefon neu" in text and "ausgeführt" in text


def test_remembering_twice_is_once_and_without_vertex_nothing_fails(db, monkeypatch):
    """(c) zweimal = einmal; (d) ohne Vertex: keine Suche, kein Fehler."""
    _fake_vertex(monkeypatch)
    at = datetime.now(timezone.utc)
    assert memory.remember(db, "note", 987654321, "Telefon", at, actor=None)
    assert memory.remember(db, "note", 987654321, "Telefon", at, actor=None)
    assert db.query(AiMemory).filter(AiMemory.ref_id == 987654321).count() == 1
    monkeypatch.setattr(get_settings(), "vertex_project", "")
    assert memory.search(db, "Telefon", actor=None) == []
    assert memory.catch_up(db, time.monotonic() + 30) == 0
    assert memory.as_prompt([]) == ""
    assert db.query(Message).count() >= 0


def test_a_deleted_document_is_no_case_anymore(db, monkeypatch):
    """(e) Ein gelöschtes Dokument bekommt keine Zahlen mehr – und schon vorhandene finden
    nichts mehr: die Datei und das Gelesene sind weg, die Erinnerung daran auch."""
    import uuid

    from app.services import documents
    _fake_vertex(monkeypatch)
    staff = new_person(db, "employee")
    act(db, "person", staff.object_id, "ui")
    doc, _ = documents.file(db, raw=b"%PDF-1.4\n" + uuid.uuid4().bytes, filename="p.pdf",
                            mime="application/pdf", art="Prüfbericht", name="Pumpe P3 undicht",
                            source="file", refs=[], actor=staff, text="Pumpe tropft")
    db.flush()
    memory.catch_up(db, time.monotonic() + 30)
    def found() -> set[int]:
        return {f.ref_id for f in memory.search(db, "Die Pumpe tropft", actor=None,
                                                 kinds=("document",))}
    assert doc.object_id in found(), "vorher"
    documents.delete(db, doc, "falsch abgelegt", staff)
    db.flush()
    assert doc.object_id not in found(), "(e) ein gelöschtes Dokument wird noch gefunden"
    db.query(AiMemory).filter(AiMemory.kind == "document").delete()
    memory.catch_up(db, time.monotonic() + 30)
    assert not db.query(AiMemory).filter(AiMemory.kind == "document",
                                         AiMemory.ref_id == doc.object_id).count(), \
        "(e) ein gelöschtes Dokument bekommt wieder Zahlen"
