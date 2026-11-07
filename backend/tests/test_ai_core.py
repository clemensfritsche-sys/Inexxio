"""►►► **Der KI-Kern – Werkzeuge, Rechte, Deckel in Franken** (Phase 3, Schritte 3.1 und 3.7). ◄◄◄

Jeder Wächter steht neben der Fehlerform, die er fängt.
"""

import random
from types import SimpleNamespace

from app.core.config import get_settings
from app.models import Log
from app.services import ai, ai_tools, documents as docs
from tests.factories import new_person

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


class _Block(SimpleNamespace):
    def to_dict(self):
        return {k: v for k, v in vars(self).items()}


def _answer(parsed=None, stop="end_turn", content=(), tin=1000, tout=200):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop, content=list(content),
                           usage=SimpleNamespace(input_tokens=tin, output_tokens=tout))


class _Script:
    """Eine KI, die Zug für Zug antwortet, was das Skript sagt – und mitschreibt, was sie bekam."""

    def __init__(self, *answers):
        self.answers, self.seen = list(answers), []
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kw):
        self.seen.append(kw)
        return self.answers.pop(0)


def _ready(monkeypatch, script, spent=0.0):
    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(ai, "spent_today", lambda db: spent)
    monkeypatch.setattr(ai, "_client", lambda *a: script)


class Out(ai.BaseModel):
    answer: str


# ─── 3.1 Die Schleife mit Werkzeugen ───────────────────────────────────────────────────

def test_the_ai_looks_up_with_a_tool_and_then_answers(db, monkeypatch):
    """Bug-Form: das Werkzeug wird nie ausgeführt oder sein Ergebnis geht nicht zurück."""
    staff = new_person(db, "employee")
    target = new_person(db, "user")
    call = _Block(type="tool_use", id="t1", name="record", input={"object_id": target.object_id})
    script = _Script(_answer(stop="tool_use", content=[_Block(type="text", text="…"), call]),
                     _answer(parsed=Out(answer="ok")))
    _ready(monkeypatch, script)
    got = ai.converse(db, task="file", actor=staff, system="s", schema=Out,
                      content=[{"type": "text", "text": "x"}], tools=ai_tools.tools_for(db))
    assert got == Out(answer="ok")
    result = script.seen[1]["messages"][-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "t1"
    assert str(target.object_id) in result["content"] and not result["is_error"]
    assert script.seen[0]["tools"][0]["strict"] is True
    assert script.seen[0]["output_config"] == {"effort": "low"}
    calls = db.query(Log).filter(Log.event == "ai.call", Log.actor_id == staff.object_id).all()
    assert len(calls) == 2 and all(c.actor_kind == "ai" and c.payload["chf"] > 0 for c in calls)


def test_a_failing_tool_is_an_answer_not_a_crash(db, monkeypatch):
    staff = new_person(db, "employee")
    call = _Block(type="tool_use", id="t1", name="nope", input={})
    script = _Script(_answer(stop="tool_use", content=[call]), _answer(parsed=Out(answer="x")))
    _ready(monkeypatch, script)
    assert ai.converse(db, task="file", actor=staff, system="s", schema=Out, content=[],
                       tools=ai_tools.tools_for(db)) == Out(answer="x")
    assert script.seen[1]["messages"][-1]["content"][0]["is_error"] is True


def test_endless_looking_up_ends_without_an_answer(db, monkeypatch):
    staff = new_person(db, "employee")
    rounds = ai.TASKS["file"].rounds
    script = _Script(*[_answer(stop="tool_use", content=[
        _Block(type="tool_use", id=f"t{i}", name="find", input={"q": "x"})]) for i in range(rounds)])
    _ready(monkeypatch, script)
    assert ai.converse(db, task="file", actor=staff, system="s", schema=Out, content=[],
                       tools=ai_tools.tools_for(db)) is None
    assert "keinem Ergebnis" in ai.problem() and len(script.seen) == rounds


# ─── 3.1 Die KI sieht nie mehr als die Person ───────────────────────────────────────────

def test_the_ai_never_sees_more_than_the_person(db):
    """Ein Arztzeugnis am Nachweis einer Absenz sieht nur die Person selbst und der Admin – die
    KI im Namen einer Kollegin sieht es weder über ``record`` noch über ``history``.
    Bug-Form: ein Werkzeug liest an ``access`` vorbei."""
    owner, colleague = new_person(db, "employee"), new_person(db, "employee")
    admin = new_person(db, "admin")
    doc, _ = docs.file(db, raw=PDF + str(random.random()).encode(), filename="z.pdf",
                       mime="application/pdf", art="Arztzeugnis", name="Zeugnis Grippe",
                       source="file", refs=[], actor=owner)
    doc.text = "Diagnose: geheim"
    docs.set_field(db, document_object_id=doc.object_id, object_id=owner.object_id,
                   part="time:42", field="time.proof", actor=owner)
    db.flush()
    assert "geheim" in ai_tools.record(db, owner, doc.object_id)
    assert "geheim" in ai_tools.record(db, admin, doc.object_id)
    assert "nicht gefunden" in ai_tools.record(db, colleague, doc.object_id)
    assert "Zeugnis Grippe" in ai_tools.history(db, admin, owner.object_id)
    assert "Zeugnis Grippe" not in ai_tools.history(db, colleague, owner.object_id)
    assert "nicht gefunden" in ai_tools.history(db, colleague, doc.object_id)


def test_a_customer_gets_nothing_from_the_tools(db, make_person):
    customer, other = new_person(db, "user"), new_person(db, "user")
    assert "nicht gefunden" in ai_tools.record(db, customer, other.object_id)
    assert ai_tools.find(db, customer, other.last_name or "x") == "Nichts gefunden."


def test_record_shows_no_secrets_or_technique(db):
    person = new_person(db, "employee")
    text = ai_tools.record(db, person, person.object_id)
    assert person.email in text and "firebase_uid" not in text and "\nid:" not in text


# ─── 3.7 Der Deckel in Franken ──────────────────────────────────────────────────────────

def test_cost_follows_the_price_list():
    assert ai.cost_chf("claude-sonnet-5-5", 1_000_000, 0) == round(2.0 * ai.CHF_PER_USD, 6)
    assert ai.cost_chf("claude-haiku-5-5", 100_000, 0) == round(0.1 * 0.10 * ai.CHF_PER_USD, 6)
    # Haiku über 100'000 Eingabe-Tokens: der höhere Preis
    assert ai.cost_chf("claude-haiku-5-5", 200_000, 0) == round(0.2 * 0.50 * ai.CHF_PER_USD, 6)
    # Unbekanntes Modell: der teuerste Preis (lieber zu früh am Deckel)
    assert ai.cost_chf("unbekannt", 1_000_000, 0) >= ai.cost_chf("claude-sonnet-5-5", 1_000_000, 0)


def test_the_day_adds_up_in_francs_and_stops_at_the_cap(db, monkeypatch):
    """Bug-Form: der Deckel zählt Aufrufe statt Franken – zwei teure Aufrufe kämen durch."""
    staff = new_person(db, "employee")
    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(get_settings(), "ai_daily_cap_chf", 0.05)
    before = ai.spent_today(db)
    ai._record(db, "file", "claude-sonnet-5-5", staff, {"in": 20_000, "out": 2_000})   # 0.048 CHF
    assert abs(ai.spent_today(db) - before - 0.048) < 1e-9
    monkeypatch.setattr(ai, "spent_today", lambda db: 0.048)
    assert ai.available(db) and ai.near_cap(db)
    monkeypatch.setattr(ai, "spent_today", lambda db: 0.05)
    assert not ai.available(db)
    assert ai.converse(db, task="file", actor=staff, system="s", schema=Out, content=[]) is None
    assert "Tagesdeckel" in ai.problem()


def test_without_vertex_there_are_no_meaning_numbers_but_no_error(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "vertex_project", "")
    assert ai.embed(db, "Hydraulikschlauch geplatzt", actor=None) is None
    assert "nicht eingerichtet" in ai.problem()


def test_a_refusing_vertex_is_asked_once_an_hour_not_every_tick(db, monkeypatch):
    """Bug-Form: ohne Einrichtung stünde jeder Takt einen Fehlversuch mehr im Log."""
    calls = []

    class Session:
        def post(self, *a, **kw):
            calls.append(1)
            return SimpleNamespace(status_code=403, text="denied")

    monkeypatch.setattr(get_settings(), "vertex_project", "p")
    monkeypatch.setattr(ai, "_vertex_session", lambda: Session())
    monkeypatch.setattr(ai, "_vertex_paused", {})
    assert ai.embed(db, "x", actor=None) is None and "setup-vertex" in ai.problem()
    assert ai.embed(db, "y", actor=None) is None and len(calls) == 1
    assert "in einer Stunde" in ai.problem()


def test_a_flow_with_a_time_limit_never_gives_a_call_more_time(db, monkeypatch):
    """Cloud Scheduler und Firebase Hosting warten 60 s – ``ai.until`` kürzt jeden Aufruf darin.
    Bug-Form: ein Aufruf nimmt seine eigene Grenze (45 s), obwohl nur noch 10 s bleiben."""
    staff = new_person(db, "employee")
    seen = []
    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(ai, "spent_today", lambda db: 0.0)
    monkeypatch.setattr(ai, "_client", lambda timeout, retries: seen.append(timeout) or _Script(
        _answer(parsed=Out(answer="ok"))))
    with ai.until(10):
        assert ai.converse(db, task="file", actor=staff, system="s", schema=Out, content=[])
    assert 0 < seen[0] <= 10
    with ai.until(1):
        assert ai.converse(db, task="file", actor=staff, system="s", schema=Out, content=[]) is None
    assert "zu lange" in ai.problem()
