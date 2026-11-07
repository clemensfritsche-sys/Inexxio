"""►►► **Lernen – die ähnlichsten entschiedenen Fälle** (Phase 3, Schritt 3.6). ◄◄◄

Vertex AI wird nachgebildet: jeder Text bekommt Zahlen, die nur von einem Stichwort abhängen –
so ist «ähnlich» im Test eindeutig. Die Suche selbst läuft echt (pgvector).
"""

import math

from app.core.config import get_settings
from app.models import AiMemory
from app.services import ai, log, memory, proposals
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


def _decide(db, pid, outcome, **extra):
    """Der Entscheid – über die eine Stelle, die dabei die Zahlen ablegt."""
    return proposals.decide(db, proposals.get(db, pid), outcome, **extra)


def test_similar_cases_come_with_their_decision(db, monkeypatch):
    """Erst der Entscheid macht einen Fall – und erst dann gibt es Zahlen. Bug-Form: ein Fall
    ohne Entscheid zählt mit (oder bekommt schon beim Vorschlag Zahlen), oder der Entscheid
    fehlt im Prompt."""
    _fake_vertex(monkeypatch)
    staff = new_person(db, "employee")
    a, _ = _proposal(db, staff.object_id, "Hans sagt, seine Telefonnummer ist neu", "+41 79 1")
    b, _ = _proposal(db, staff.object_id, "Telefon von Hans geändert", "+41 79 2")
    c, _ = _proposal(db, staff.object_id, "Hydraulikschlauch geplatzt", "x")
    assert db.query(AiMemory).filter(AiMemory.log_id.in_([a, b, c])).count() == 0
    _decide(db, a, "changed", value="+41 79 9")
    _decide(db, c, "rejected")
    db.flush()
    assert {m.log_id for m in db.query(AiMemory).filter(AiMemory.log_id.in_([a, b, c]))} == {a, c}
    found = memory.similar(db, "neue Telefonnummer von Hans", actor=staff)
    assert [f.proposal for f in found] == [a]                      # b: ohne Entscheid
    assert found[0].outcome == "changed" and found[0].value == "+41 79 9"
    prompt = memory.as_prompt(found)
    assert "selbst geändert (stattdessen: +41 79 9)" in prompt and "Telefon" in prompt


def test_a_proposal_gets_no_numbers_until_it_is_decided(db, monkeypatch):
    """Bug-Form: ``propose`` legt schon Zahlen ab – ein unentschiedener Vorschlag (vielleicht
    nie gesehen) wäre ein Fall."""
    _fake_vertex(monkeypatch)
    staff, customer = new_person(db, "employee"), new_person(db, "user")
    pid = proposals.propose(db, object_id=customer.object_id, kind="change", field="phone",
                            value="079 123 00 00", source={"text": "Telefon neu"},
                            actor=staff.object_id)
    assert db.get(AiMemory, pid) is None
    _decide(db, pid, "rejected")
    assert db.get(AiMemory, pid) is not None


def test_remember_once_and_backfill_what_is_missing(db, monkeypatch):
    """Nur Entschiedenes fehlt; was beim Entscheid nicht ging, holt der Takt nach."""
    _fake_vertex(monkeypatch)
    staff = new_person(db, "employee")
    pid, payload = _proposal(db, staff.object_id, "Telefon neu", "1")
    assert pid not in [m[0] for m in memory.missing(db, 50)]       # unentschieden: kein Fall
    _decide(db, pid, "accepted", remember=False)                   # wie ``settle`` im Takt
    (row,) = [m for m in memory.missing(db, 50) if m[0] == pid]
    assert row[3]["outcome"] == "accepted"
    assert memory.remember(db, pid, payload, decided=row[3], actor=staff)
    assert memory.remember(db, pid, payload, decided=row[3], actor=staff)   # zweimal = einmal
    assert db.query(AiMemory).filter(AiMemory.log_id == pid).count() == 1
    assert pid not in [m[0] for m in memory.missing(db, 50)]


def _file(db, oid, words):
    payload = {"kind": "file", "label": "Ablegen", "source": {"text": "Erfassung von X"},
               "parts": [{"object_id": oid, "text": words, "subject": "x"}]}
    return log.event(db, "proposal", oid, payload)


def test_a_discarded_capture_of_another_person_never_comes_back(db, monkeypatch):
    """►► **Gedächtnis ohne fremde Privatsachen.** Ein verworfener ``file`` (die Worte sah nur,
    wer erfasste) bekommt nie Zahlen und kommt in keine Anfrage; ein abgelegter schon – seine
    Teile stehen als Notiz da, und zwar so, wie der Mensch sie ablegte. Bug-Form: ``similar``
    liefert die Worte eines verworfenen ``file`` einer anderen Person. ◄◄"""
    _fake_vertex(monkeypatch)
    me, other = new_person(db, "employee"), new_person(db, "employee")
    secret = _file(db, other.object_id, "Telefon privat: Scheidung, bitte niemandem sagen")
    _decide(db, secret, "rejected")
    kept = _file(db, me.object_id, "Telefon der Firma, KI-Fassung")
    _decide(db, kept, "changed", parts=[{"object_id": me.object_id, "text": "Telefon der Firma, "
                                         "abgelegt", "subject": "Telefon"}])
    db.flush()
    assert db.get(AiMemory, secret) is None
    assert secret not in [m[0] for m in memory.missing(db, 500)]
    found = memory.similar(db, "Telefon", actor=me)
    assert secret not in [f.proposal for f in found] and kept in [f.proposal for f in found]
    text = next(f.text for f in found if f.proposal == kept)
    assert "abgelegt" in text and "KI-Fassung" not in text
    assert not memory.remember(db, secret, proposals.get(db, secret).payload,
                               decided={"outcome": "rejected"}, actor=me)


def test_without_vertex_there_are_no_cases_and_nothing_breaks(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "vertex_project", "")
    staff = new_person(db, "employee")
    pid, payload = _proposal(db, staff.object_id, "Telefon neu", "1")
    _decide(db, pid, "rejected")
    assert db.get(AiMemory, pid) is None
    assert memory.remember(db, pid, payload, decided={"outcome": "rejected"}, actor=staff) is False
    assert memory.similar(db, "Telefon", actor=staff) == []
    assert memory.as_prompt([]) == ""


def test_the_case_text_names_source_and_proposal():
    t = memory.text_of({"kind": "create", "source": {"text": "Neuer Kunde Muster"},
                        "draft": {"type": "organization", "values": {"company_name": "Muster"}}})
    assert "Neuer Kunde Muster" in t and "company_name: Muster" in t
