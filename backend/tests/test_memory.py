"""►►► **Lernen – die ähnlichsten entschiedenen Fälle** (Phase 3, Schritt 3.6). ◄◄◄

Vertex AI wird nachgebildet: jeder Text bekommt Zahlen, die nur von einem Stichwort abhängen –
so ist «ähnlich» im Test eindeutig. Die Suche selbst läuft echt (pgvector).
"""

import math

from app.core.config import get_settings
from app.models import AiMemory
from app.services import ai, log, memory
from tests.factories import new_person


def _vector(word: str) -> list[float]:
    """768 Zahlen je Stichwort – gleiche Stichworte zeigen in dieselbe Richtung."""
    seed = sum(ord(c) for c in word)
    v = [math.sin(seed * (i + 1)) for i in range(ai.EMBED_DIMS)]
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def _fake_vertex(monkeypatch):
    monkeypatch.setattr(get_settings(), "vertex_project", "test")

    def embed(db, text, *, actor, query=False, **kw):
        word = "schlauch" if "schlauch" in text.lower() else "telefon" if "telefon" in text.lower() else text
        return _vector(word)
    monkeypatch.setattr(ai, "embed", embed)


def _proposal(db, oid, source, value):
    payload = {"kind": "change", "field": "phone", "label": "Telefon", "value": value,
               "source": {"text": source}}
    return log.event(db, "proposal", oid, payload), payload


def test_similar_cases_come_with_their_decision(db, monkeypatch):
    """Bug-Form: ein Fall ohne Entscheid zählt mit, oder der Entscheid fehlt im Prompt."""
    _fake_vertex(monkeypatch)
    staff = new_person(db, "employee")
    a, pa = _proposal(db, staff.object_id, "Hans sagt, seine Telefonnummer ist neu", "+41 79 1")
    b, pb = _proposal(db, staff.object_id, "Telefon von Hans geändert", "+41 79 2")
    c, pc = _proposal(db, staff.object_id, "Hydraulikschlauch geplatzt", "x")
    for pid, payload in ((a, pa), (b, pb), (c, pc)):
        assert memory.remember(db, pid, payload, actor=staff)
    log.event(db, "proposal.decided", staff.object_id, {"proposal": a, "outcome": "changed",
                                                        "value": "+41 79 9"})
    log.event(db, "proposal.decided", staff.object_id, {"proposal": c, "outcome": "rejected"})
    db.flush()
    found = memory.similar(db, "neue Telefonnummer von Hans", actor=staff)
    assert [f.proposal for f in found] == [a]                      # b: ohne Entscheid
    assert found[0].outcome == "changed" and found[0].value == "+41 79 9"
    prompt = memory.as_prompt(found)
    assert "selbst geändert (stattdessen: +41 79 9)" in prompt and "Telefon" in prompt


def test_remember_once_and_backfill_what_is_missing(db, monkeypatch):
    _fake_vertex(monkeypatch)
    staff = new_person(db, "employee")
    pid, payload = _proposal(db, staff.object_id, "Telefon neu", "1")
    assert pid in [m[0] for m in memory.missing(db, 50)]
    assert memory.remember(db, pid, payload, actor=staff)
    assert memory.remember(db, pid, payload, actor=staff)          # zweimal = einmal
    assert db.query(AiMemory).filter(AiMemory.log_id == pid).count() == 1
    assert pid not in [m[0] for m in memory.missing(db, 50)]


def test_without_vertex_there_are_no_cases_and_nothing_breaks(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "vertex_project", "")
    staff = new_person(db, "employee")
    pid, payload = _proposal(db, staff.object_id, "Telefon neu", "1")
    assert memory.remember(db, pid, payload, actor=staff) is False
    assert memory.similar(db, "Telefon", actor=staff) == []
    assert memory.as_prompt([]) == ""


def test_the_case_text_names_source_and_proposal():
    t = memory.text_of({"kind": "create", "source": {"text": "Neuer Kunde Muster"},
                        "draft": {"type": "organization", "values": {"company_name": "Muster"}}})
    assert "Neuer Kunde Muster" in t and "company_name: Muster" in t
