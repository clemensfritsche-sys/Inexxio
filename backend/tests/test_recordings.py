"""►►► **Phase 4 · Sprache – Aufnehmen, Abschreiben, Erfassen.** ◄◄◄

Der Vertrag: ``docs/konzept/phase4-bauplan.md``. Gemini (Vertex AI) wird nachgebildet
(``_Gemini``), Claude ebenso (``_Script`` aus ``tests/test_ai_core.py``) – nie ein echter Aufruf.
Stücke tragen Bytes wie ``b"seg0-0"``, damit man sieht, was in welcher Reihenfolge ankam. Jeder
Wächter steht neben der Fehlerform, die er fängt.
"""

import base64
import json
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core.actor import act
from app.core.config import get_settings
from app.models import Log, RecordingChunk
from app.services import ai, attachments, history, intake, recordings, tick, todo
from app.services.intake import AiPart, FileAnswer
from tests.factories import new_firm, new_person
from tests.test_ai_core import _Script, _answer
from tests.test_proposals import api  # noqa: F401 – die Fixture: echte Routen, dieselbe Sitzung

BASE = "/api/v1/erp/recordings"
#: Die echte Sitzung zu Vertex – die Fixture ersetzt sie.
REAL_SESSION = ai._vertex_session


# ─── Hilfen ────────────────────────────────────────────────────────────────────────────

def said(text, tin=1200, tout=150, thoughts=0, finish="STOP"):
    """Eine Antwort von ``generateContent``."""
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
            "usageMetadata": {"promptTokenCount": tin, "candidatesTokenCount": tout,
                              "thoughtsTokenCount": thoughts}}


class _Gemini:
    """Vertex AI, wie ``_vertex_session`` es liefert: Antwort für Antwort, was das Skript sagt
    (eine Zahl ist ein HTTP-Fehler) – und mitgeschrieben, was ankam."""

    def __init__(self, *answers):
        self.answers, self.seen = list(answers), []

    def post(self, url, data, timeout, headers):
        self.seen.append({"url": url, "body": json.loads(data), "timeout": timeout})
        a = self.answers.pop(0)
        if isinstance(a, int):
            return SimpleNamespace(status_code=a, text="nein", json=lambda: {})
        return SimpleNamespace(status_code=200, text="", json=lambda a=a: a)

    def audio(self, i):
        part = self.seen[i]["body"]["contents"][0]["parts"][0]["inlineData"]
        return base64.b64decode(part["data"]), part["mimeType"]


@pytest.fixture
def gemini(monkeypatch):
    """Vertex eingerichtet, Claude aus (``ai.ready``), der Deckel frei."""
    box = {"g": _Gemini()}
    monkeypatch.setattr(get_settings(), "vertex_project", "p")
    monkeypatch.setattr(ai, "_vertex_paused", {})
    monkeypatch.setattr(ai, "ready", lambda: False)
    monkeypatch.setattr(ai, "spent_today", lambda db: 0.0)
    monkeypatch.setattr(ai, "_vertex_session", lambda: box["g"])

    def use(*answers):
        box["g"] = _Gemini(*answers)
        return box["g"]
    return use


def later(monkeypatch, delta):
    real = recordings._now
    monkeypatch.setattr(recordings, "_now", lambda: real() + delta)


def begin(client, hint=None, mime="audio/webm;codecs=opus"):
    r = client.post(BASE, json={"hint_object_id": hint, "mime": mime})
    assert r.status_code == 200, r.text
    return r.json()


def send(client, rid, segment, seq, raw=None):
    raw = raw if raw is not None else f"seg{segment}-{seq}".encode()
    return client.post(f"{BASE}/{rid}/chunks", data={"segment": str(segment), "seq": str(seq)},
                       files={"file": ("c.webm", raw, "audio/webm")})


def chunks(db, rid):
    return db.query(RecordingChunk).filter(RecordingChunk.recording == rid).count()


def events(db, name, rid):
    return [e for e in db.query(Log).filter(Log.event == name).order_by(Log.id)
            if (e.payload or {}).get("recording") == rid]


# ─── Der Weg: Start → Stücke → Stopp → Abschreiben → Erfassung ─────────────────────────

def test_a_recording_becomes_one_intake_in_the_order_of_its_segments(db, api, gemini):  # noqa: F811
    """Bug-Form: Stücke in der Reihenfolge des Ankommens statt nach Nummer, Abschnitte
    vertauscht, das Audio bleibt nach der Abschrift liegen."""
    me = new_person(db, "employee")
    firm = new_firm(db, "Kran")
    c = api.as_(me)
    rec = begin(c, hint=firm.object_id)
    assert rec["state"] == "recording" and rec["hint_object_id"] == firm.object_id
    for seg, seq in ((0, 1), (1, 0), (0, 0)):          # in falscher Reihenfolge angekommen
        assert send(c, rec["id"], seg, seq).status_code == 200
    got = c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 2}).json()
    assert got["state"] == "transcribing" and got["segments"] == 2 and got["seconds"] == 90
    g = gemini(said("Schlauch am Kran ersetzt."), said("Herr Meier ruft morgen an."))
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "done" and got["transcribed"] == 2 and got["problem"] is None
    assert g.audio(0) == (b"seg0-0seg0-1", "audio/webm") and g.audio(1)[0] == b"seg1-0"
    assert "gemini-3.5-flash:generateContent" in g.seen[0]["url"]
    assert "Schweizer Schreibweise" in g.seen[0]["body"]["systemInstruction"]["parts"][0]["text"]
    it = got["intake"]
    assert it["text"] == "Schlauch am Kran ersetzt.\n\nHerr Meier ruft morgen an."
    assert it["hint_object_id"] == firm.object_id and it["problem"] == intake.WAITING
    stored = intake.get(db, it["id"])
    assert stored.actor_id == me.object_id and stored.object_id == firm.object_id
    assert chunks(db, rec["id"]) == 0
    assert [e.payload["intake"] for e in events(db, "recording.done", rec["id"])] == [it["id"]]
    # Die Erfassung zählt als offene Erfassung der Person (Phase 3) – im Namen der Person.
    assert it["id"] in intake.open_ids(db, me)
    assert c.get(f"{BASE}/open").json() == []


def test_a_recording_without_a_stop_counts_as_stopped_after_ten_quiet_minutes(db, api, gemini, monkeypatch):  # noqa: F811
    """Akte: «Abbruch nach 10 Min. → die 10 Min. sind da». Bug-Form: ohne Stopp wird nie
    abgeschrieben (Akku leer, Tab zu – alles verloren)."""
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    for seq in range(3):
        send(c, rec["id"], 0, seq)
    g = gemini(said("Bis hier gesprochen."))
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "recording" and g.seen == []          # läuft noch: nichts tun
    assert rec["id"] not in recordings.due(db, 100)
    later(monkeypatch, timedelta(minutes=10, seconds=1))
    assert c.get(f"{BASE}/open").json()[0]["state"] == "transcribing"
    assert rec["id"] in recordings.due(db, 100)
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "done" and got["intake"]["text"] == "Bis hier gesprochen."
    assert g.audio(0)[0] == b"seg0-0seg0-1seg0-2"


def test_the_same_chunk_twice_is_one_and_the_later_one_counts(db, api, gemini):  # noqa: F811
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0, b"erst")
    send(c, rec["id"], 0, 0, b"seg0-0")
    assert chunks(db, rec["id"]) == 1
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 1})
    g = gemini(said("x"))
    c.post(f"{BASE}/{rec['id']}/advance")
    assert g.audio(0)[0] == b"seg0-0"


def test_a_missing_chunk_in_the_middle_still_transcribes_what_is_there(db, api, gemini):  # noqa: F811
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0)
    send(c, rec["id"], 0, 2)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 1})
    g = gemini(said("Teilweise."))
    assert c.post(f"{BASE}/{rec['id']}/advance").json()["state"] == "done"
    assert g.audio(0)[0] == b"seg0-0seg0-2"


# ─── Rechte und Grenzen ────────────────────────────────────────────────────────────────

def test_only_the_person_who_records_sends_and_sees(db, api, gemini):  # noqa: F811
    """Bug-Form: eine Kollegin liest oder füttert die Aufnahme einer anderen Person."""
    me, other = new_person(db, "employee"), new_person(db, "employee")
    admin, customer = new_person(db, "admin"), new_person(db, "user")
    rec = begin(api.as_(me))
    rid = rec["id"]
    for path in ("advance", "stop"):
        r = api.as_(other).post(f"{BASE}/{rid}/{path}", json={"segments": 1})
        assert r.status_code == 404 and f"«{rid}»" in r.json()["detail"]
    r = send(api.as_(other), rid, 0, 0)
    assert r.status_code == 404
    assert send(api.as_(admin), rid, 0, 0).status_code == 403      # sieht sie, nimmt nicht auf
    assert api.as_(admin).post(f"{BASE}/{rid}/stop", json={"segments": 1}).status_code == 403
    assert api.as_(admin).post(f"{BASE}/{rid}/advance").status_code == 200
    assert api.as_(customer).post(BASE, json={"mime": "audio/webm"}).status_code == 403
    assert api.as_(other).get(f"{BASE}/open").json() == []
    assert [r["id"] for r in api.as_(me).get(f"{BASE}/open").json()] == [rid]


def test_a_chunk_is_at_most_4_mb_and_audio_only(db, api, gemini):  # noqa: F811
    me = new_person(db, "employee")
    c = api.as_(me)
    assert c.post(BASE, json={"mime": "video/mp4"}).status_code == 400
    rec = begin(c, mime="audio/mp4")
    assert send(c, rec["id"], 0, 0, b"x" * (recordings.MAX_CHUNK + 1)).status_code == 413
    assert send(c, rec["id"], 0, 0, b"").status_code == 400
    assert send(c, rec["id"], recordings.MAX_SEGMENTS, 0).status_code == 400
    assert send(c, rec["id"], 0, 0, b"x" * recordings.MAX_CHUNK).status_code == 200


def test_after_done_no_more_chunks(db, api, gemini):  # noqa: F811
    """Bug-Form: ein spätes Stück nach der Erfassung bliebe liegen (Audio, das niemand löscht)."""
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 1})
    gemini(said("Fertig."))
    c.post(f"{BASE}/{rec['id']}/advance")
    r = send(c, rec["id"], 0, 1)
    assert r.status_code == 409 and f"«{rec['id']}»" in r.json()["detail"]
    assert chunks(db, rec["id"]) == 0
    # Ein zweiter Stopp, ein zweites Weiter ändern nichts – keine zweite Erfassung.
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 3})
    c.post(f"{BASE}/{rec['id']}/advance")
    assert len(events(db, "recording.done", rec["id"])) == 1
    assert len(events(db, "recording.stop", rec["id"])) == 1


# ─── Was nicht geht: Deckel, keine Einrichtung, Ablehnung, Stille ──────────────────────

def test_without_vertex_or_at_the_cap_it_waits_and_nothing_is_lost(db, api, gemini, monkeypatch):  # noqa: F811
    """Bug-Form: ein Ausfall, den ein späterer Versuch behebt, zählt als Ablehnung – und der
    Abschnitt würde übersprungen."""
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 1})
    monkeypatch.setattr(get_settings(), "vertex_project", "")
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "transcribing" and "VERTEX_PROJECT" in got["problem"]
    monkeypatch.setattr(get_settings(), "vertex_project", "p")
    monkeypatch.setattr(get_settings(), "ai_daily_cap_chf", 1.0)
    monkeypatch.setattr(ai, "spent_today", lambda db: 1.0)
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "transcribing" and "Tagesdeckel" in got["problem"]
    monkeypatch.setattr(ai, "spent_today", lambda db: 0.0)
    gemini(503, 429)
    for _ in range(2):
        assert c.post(f"{BASE}/{rec['id']}/advance").json()["state"] == "transcribing"
    assert events(db, "recording.segment_failed", rec["id"]) == [] and chunks(db, rec["id"]) == 1
    gemini(said("Doch noch."))
    assert c.post(f"{BASE}/{rec['id']}/advance").json()["intake"]["text"] == "Doch noch."


def test_a_segment_refused_twice_is_skipped_with_a_note(db, api, gemini):  # noqa: F811
    """Bug-Form: ein Abschnitt, den Gemini nie abschreibt, hält die ganze Aufnahme für immer an."""
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0)
    send(c, rec["id"], 1, 0)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 2})
    gemini(said("", finish="SAFETY"))
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "transcribing" and "SAFETY" in got["problem"] and got["transcribed"] == 0
    gemini(400, said("Zweiter Teil."))
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "done"
    assert got["intake"]["text"] == "[Abschnitt 1 nicht abgeschrieben]\n\nZweiter Teil."
    assert len(events(db, "recording.segment_failed", rec["id"])) == 2
    (skipped,) = [e for e in events(db, "recording.segment", rec["id"]) if e.payload["segment"] == 0]
    assert skipped.payload["text"] == "" and skipped.payload["skipped"]


def test_silence_is_no_intake(db, api, gemini):  # noqa: F811
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 1})
    gemini(said("   "))
    got = c.post(f"{BASE}/{rec['id']}/advance").json()
    assert got["state"] == "failed" and got["problem"] == recordings.NOTHING and got["intake"] is None
    assert db.query(Log).filter(Log.event == "intake", Log.actor_id == me.object_id).count() == 0
    assert chunks(db, rec["id"]) == 0


# ─── Aufräumen und «zu tun» ────────────────────────────────────────────────────────────

def test_after_a_day_the_audio_is_gone_and_the_recording_failed(db, api, gemini, monkeypatch):  # noqa: F811
    """Akte: «spätestens nach einem Tag». Bug-Form: Audio einer nie abgeschriebenen Aufnahme
    bleibt für immer liegen, und niemand erfährt es."""
    me, other = new_person(db, "employee"), new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0)
    assert recordings.sweep(db) == {"failed": 0, "dropped": 0}
    assert chunks(db, rec["id"]) == 1
    later(monkeypatch, timedelta(hours=24, minutes=1))
    assert recordings.sweep(db)["failed"] == 1
    assert chunks(db, rec["id"]) == 0
    (failed,) = events(db, "recording.failed", rec["id"])
    assert failed.payload["problem"] == recordings.TOO_OLD
    assert send(c, rec["id"], 0, 1).status_code == 409
    assert recordings.sweep(db) == {"failed": 0, "dropped": 0}          # wiederholbar

    def mine(viewer):
        found = {t.object_id: t for t in todo.todo(db, viewer)}.get(viewer.object_id)
        return [(i.label, i.red) for i in found.items if "Aufnahme" in i.label] if found else []
    assert mine(me) == [("1 Aufnahme fehlgeschlagen", True)]
    assert mine(other) == []
    later(monkeypatch, timedelta(days=recordings.FAILED_DAYS + 1))
    assert mine(me) == []


def test_a_stray_chunk_older_than_a_day_goes_too(db, api, gemini, monkeypatch):  # noqa: F811
    me = new_person(db, "employee")
    rec = begin(api.as_(me))
    send(api.as_(me), rec["id"], 0, 0)
    act(db, "person", me.object_id, "ui")
    recordings._end(db, recordings.load(db, rec["id"]), "recording.done", {"intake": None})
    db.add(RecordingChunk(recording=rec["id"], segment=0, seq=5, byte_size=1, data=b"x"))
    db.flush()
    later(monkeypatch, timedelta(hours=25))
    assert recordings.sweep(db) == {"failed": 0, "dropped": 1}
    assert chunks(db, rec["id"]) == 0


# ─── Der Bucket ────────────────────────────────────────────────────────────────────────

class _Bucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        bucket = self

        class Blob:
            def upload_from_string(self, raw, content_type):
                bucket.objects[name] = raw

            def download_as_bytes(self):
                return bucket.objects[name]

            def delete(self):
                bucket.objects.pop(name, None)
        return Blob()

    def list_blobs(self, prefix):
        return [SimpleNamespace(delete=lambda n=n: self.objects.pop(n, None))
                for n in list(self.objects) if n.startswith(prefix)]


def test_with_a_bucket_the_bytes_live_there_and_go_after_the_commit(db, api, gemini, monkeypatch):  # noqa: F811
    """Bug-Form: die Bytes stehen trotz Bucket in der Datenbank – oder bleiben im Bucket liegen."""
    store = _Bucket()
    monkeypatch.setattr(attachments, "bucket", lambda: store)
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 1)
    send(c, rec["id"], 0, 0)
    assert sorted(store.objects) == [f"recordings/{rec['id']}/0-0", f"recordings/{rec['id']}/0-1"]
    assert db.query(RecordingChunk.data).filter(RecordingChunk.recording == rec["id"]).all() == [
        (None,), (None,)]
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 1})
    g = gemini(said("Aus dem Bucket."))
    assert c.post(f"{BASE}/{rec['id']}/advance").json()["state"] == "done"
    assert g.audio(0)[0] == b"seg0-0seg0-1"
    assert store.objects                                   # vor dem Commit noch da …
    db.dispatch.after_commit(db)
    assert store.objects == {}                             # … danach weg


# ─── Die Tür: ai.transcribe ────────────────────────────────────────────────────────────

def test_transcribe_logs_its_cost_and_never_retries_under_a_time_limit(db, gemini, monkeypatch):
    """Bug-Form: ein Aufruf ohne ``ai.call`` (der Deckel sähe ihn nie), die Denk-Tokens nicht
    mitgezählt, oder ein zweiter Versuch, der die 60 s bricht."""
    me = new_person(db, "employee")
    g = gemini(said("Hallo", tin=2000, tout=100, thoughts=50))
    with ai.until(20):
        assert ai.transcribe(db, b"seg0-0", "audio/webm;codecs=opus", actor=me) == "Hallo"
    assert 0 < g.seen[0]["timeout"] <= 20
    call = (db.query(Log).filter(Log.event == "ai.call", Log.actor_id == me.object_id)
            .order_by(Log.id.desc()).first())
    assert call.payload["task"] == "transcribe" and call.payload["model"] == ai.TRANSCRIBE_MODEL
    assert call.payload["in"] == 2000 and call.payload["out"] == 150
    assert call.payload["chf"] == ai.cost_chf(ai.TRANSCRIBE_MODEL, 2000, 150) > 0
    assert ai.TRANSCRIBE_MODEL in ai.PRICES
    # Die Sitzung zu Vertex: unter ``until`` ohne zweiten Versuch.
    import google.auth
    import google.auth.transport.requests as transport
    seen = []
    monkeypatch.setattr(ai, "_vertex_session", REAL_SESSION)
    monkeypatch.setattr(google.auth, "default", lambda scopes: (object(), "p"))
    monkeypatch.setattr(transport, "AuthorizedSession",
                        lambda creds, max_refresh_attempts: seen.append(max_refresh_attempts))
    ai._vertex_session()
    with ai.until(20):
        ai._vertex_session()
    assert seen == [2, 0]


def test_a_refusing_vertex_is_paused_for_transcribing_too(db, gemini):
    """Bug-Form: ohne Einrichtung stünde jeder Takt einen Fehlversuch mehr im Log."""
    g = gemini(403)
    assert ai.transcribe(db, b"x", "audio/webm", actor=None) is None and "setup-vertex" in ai.problem()
    assert not ai.refused()                                 # nicht eingerichtet ≠ Inhalt abgelehnt
    assert ai.transcribe(db, b"x", "audio/webm", actor=None) is None and len(g.seen) == 1
    assert "in einer Stunde" in ai.problem() and not ai.transcribe_ready()


def test_no_call_to_vertex_outside_the_gate():
    """Abschreiben geht nur durch ``services/ai.py``."""
    from pathlib import Path
    source = (Path(recordings.__file__)).read_text("utf-8")
    assert "aiplatform" not in source and "_vertex" not in source and "google.auth" not in source


# ─── Verlauf und Takt ──────────────────────────────────────────────────────────────────

def test_the_events_of_a_recording_are_not_in_the_history(db, api, gemini):  # noqa: F811
    """Bug-Form: die Abschrift (privat, bis sie abgelegt ist) stünde für jedes Personal im
    Verlauf des Datensatzes."""
    me, colleague = new_person(db, "employee"), new_person(db, "employee")
    firm = new_firm(db, "Geheim")
    c = api.as_(me)
    rec = begin(c, hint=firm.object_id)
    send(c, rec["id"], 0, 0)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 1})
    gemini(said("Vertraulich besprochen."))
    c.post(f"{BASE}/{rec['id']}/advance")
    assert {e.event for e in db.query(Log).filter(Log.event.like("recording.%"))} >= {
        "recording.start", "recording.stop", "recording.segment", "recording.done"}
    for oid in (firm.object_id, me.object_id):
        page = history.page(db, oid, colleague).model_dump_json()
        assert "recording." not in page and "Vertraulich" not in page


def test_the_tick_finishes_a_recording_without_a_browser(db, api, gemini, monkeypatch):  # noqa: F811
    """Tab zu nach dem Stopp: der Takt schreibt ab, erfasst und lässt die KI ablegen."""
    me = new_person(db, "employee")
    firm = new_firm(db, "Takt")
    c = api.as_(me)
    rec = begin(c)
    for seg in range(2):
        send(c, rec["id"], seg, 0)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 2})
    gemini(said("Erster."), said("Zweiter."))
    script = _Script(_answer(parsed=FileAnswer(parts=[AiPart(
        object_id=firm.object_id, text="Erster. Zweiter.", subject="Takt")], proposals=[])))
    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(ai, "_client", lambda *a: script)
    act(db, "system", None, "job")
    done = tick._voice(db, time.monotonic() + 30)
    assert done["finished"] == 1
    (end,) = events(db, "recording.done", rec["id"])
    it = intake.get(db, end.payload["intake"])
    assert it.text == "Erster.\n\nZweiter." and it.actor_id == me.object_id
    assert intake.view(db, it).parts[0].object_id == firm.object_id    # die KI hat abgelegt
    assert any(t.name == "voice" for t in tick.TASKS)
    assert tick._voice(db, time.monotonic() + 30) == {"failed": 0, "dropped": 0}


def test_what_is_written_after_a_day_is_kept_the_rest_is_noted(db, api, gemini, monkeypatch):  # noqa: F811
    """Nach einem Tag geht das Audio – aber was schon abgeschrieben ist, wird die Erfassung.
    Bug-Form: eine halb abgeschriebene Stunde ist nach einem Tag ganz weg."""
    me = new_person(db, "employee")
    c = api.as_(me)
    rec = begin(c)
    send(c, rec["id"], 0, 0)
    send(c, rec["id"], 1, 0)
    c.post(f"{BASE}/{rec['id']}/stop", json={"segments": 2})
    gemini(said("Erster Teil steht."), 503)
    assert c.post(f"{BASE}/{rec['id']}/advance").json()["state"] == "transcribing"
    later(monkeypatch, timedelta(hours=24, minutes=1))
    assert recordings.sweep(db)["failed"] == 0
    (done,) = events(db, "recording.done", rec["id"])
    assert done.payload["partial"] is True and chunks(db, rec["id"]) == 0
    text = intake.get(db, done.payload["intake"]).text
    assert text == "Erster Teil steht.\n\n[Abschnitt 2 nicht abgeschrieben]"


def test_a_long_part_becomes_several_notes(db, api):  # noqa: F811
    """Eine Stunde Gesprochenes ist länger als eine Notiz trägt – «Stimmt so» legt sie in
    Stücken ab, nichts geht verloren. Bug-Form: 422 und die Abschrift ist nicht ablegbar."""
    me, firm = new_person(db, "employee"), new_firm(db, "Kran")
    para = ("Wort " * 1990).strip()                       # ~9950 Zeichen
    long = "\n\n".join([para] * 5)                        # ~50'000 Zeichen
    got = intake.pieces(long)
    assert len(got) == 3 and all(len(p) <= intake.MAX_TEXT for p in got)
    assert " ".join(" ".join(got).split()) == " ".join(long.split())          # kein Wort fehlt
    act(db, "person", me.object_id, "ui")
    it = intake.capture(db, long, firm.object_id, me, recording=1)
    r = api.as_(me).post(f"/api/v1/erp/intake/{it.id}/file",
                         json={"parts": [{"object_id": firm.object_id, "text": long, "subject": "Sitzung"}]})
    assert r.status_code == 200, r.text
    notes = r.json()["notes"]
    assert len(notes) == 3
