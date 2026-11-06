"""►►► **Der Takt** (``services/tick``, ``core/oidc``, ``POST /api/v1/internal/tick``). ◄◄◄

Gefahren gegen echtes PostgreSQL, ohne Netz: Googles Prüfung des Tokens (``oidc.verify``) und
die Gmail-Abrufe werden ersetzt. Jede Prüfung nennt die Regel und ist gegen ihre Bug-Form
gegengeprüft.
"""

import random
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import oidc
from app.core.config import get_settings
from app.models import Log
from app.services import tick
from tests.runner import session

AUD = "inexxio-tick-test"
SA = "tick@inexxio-test.iam.gserviceaccount.com"
URL = "/api/v1/internal/tick"


def _name(base: str) -> str:
    """Ein eigener Aufgabenname je Test – eigene Sperre, eigene Ereignisse im Log."""
    return f"{base}{random.randint(10**8, 10**9)}"


def _events(name: str) -> list[Log]:
    db = session()
    try:
        return db.query(Log).filter(Log.event == f"tick.{name}").all()
    finally:
        db.close()


@pytest.fixture()
def configured(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "tick_audience", AUD)
    monkeypatch.setattr(s, "tick_service_account", SA)
    session()       # Schema herrichten


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


def _claims(monkeypatch, **claims):
    seen: list[tuple[str, str]] = []

    def fake(token, audience):
        seen.append((token, audience))
        if token == "bad" or audience != AUD:
            raise ValueError("Token ungültig")
        return {"iss": "https://accounts.google.com", "aud": audience,
                "email": SA, "email_verified": True, **claims}
    monkeypatch.setattr(oidc, "verify", fake)
    return seen


# ── Wer darf ─────────────────────────────────────────────────────────────────────────


def test_without_settings_there_is_no_tick(monkeypatch, client):
    """Ohne Zielgruppe ODER Dienstkonto: 503, und nichts läuft – nie ein Takt ohne
    Anmeldung. Bug-Form: eine leere Einstellung hiesse «jeder darf»."""
    ran: list[str] = []
    monkeypatch.setattr(tick, "run", lambda *a, **k: ran.append("x") or [])
    _claims(monkeypatch)
    s = get_settings()
    for aud, sa in (("", ""), (AUD, ""), ("", SA)):
        monkeypatch.setattr(s, "tick_audience", aud)
        monkeypatch.setattr(s, "tick_service_account", sa)
        r = client.post(URL, headers={"Authorization": "Bearer good"})
        assert r.status_code == 503 and "nicht eingerichtet" in r.json()["detail"]
    assert ran == []


def test_a_wrong_or_missing_token_is_refused(configured, monkeypatch, client):
    """Ohne Token, mit ungültigem Token, fremder Zielgruppe, fremdem Konto oder unbestätigter
    Adresse läuft nichts (401 · 403)."""
    ran: list[str] = []
    monkeypatch.setattr(tick, "run", lambda *a, **k: ran.append("x") or [])
    seen = _claims(monkeypatch)
    assert client.post(URL).status_code == 401
    assert client.post(URL, headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.post(URL, headers={"Authorization": "Bearer bad"}).status_code == 401
    assert seen[-1] == ("bad", AUD), "geprüft wird gegen die Zielgruppe der Umgebung"
    monkeypatch.setattr(get_settings(), "tick_audience", "inexxio-tick-andere")
    assert client.post(URL, headers={"Authorization": "Bearer good"}).status_code == 401
    monkeypatch.setattr(get_settings(), "tick_audience", AUD)
    _claims(monkeypatch, email="jemand@example.com")
    assert client.post(URL, headers={"Authorization": "Bearer good"}).status_code == 403
    _claims(monkeypatch, email_verified=False)
    assert client.post(URL, headers={"Authorization": "Bearer good"}).status_code == 403
    assert ran == []


def test_google_out_of_reach_is_503_not_a_pass(configured, monkeypatch, client):
    from google.auth import exceptions

    def down(token, audience):
        raise exceptions.TransportError("Netz weg")
    monkeypatch.setattr(oidc, "verify", down)
    assert client.post(URL, headers={"Authorization": "Bearer good"}).status_code == 503


def test_a_valid_token_runs_every_task_as_the_system(configured, monkeypatch, client):
    """Mit gültigem Token läuft jede Aufgabe aus ``TASKS`` einmal, und in ihrer Sitzung
    handelt das System (``job``) – Bug-Form: eine Aufgabe ohne Handelnden scheiterte beim
    ersten Schreiben."""
    _claims(monkeypatch)
    actors: list[str] = []

    def who(db, _deadline):
        actors.append(db.execute(text("SELECT log_actor() ->> 'kind' || '/' || "
                                      "(log_actor() ->> 'source')")).scalar())
        return {}
    names = [_name("a"), _name("b")]
    monkeypatch.setattr(tick, "TASKS", tuple(tick.Task(n, who) for n in names))
    r = client.post(URL, headers={"Authorization": "Bearer good"})
    assert r.status_code == 200
    assert [(t["name"], t["state"]) for t in r.json()["tasks"]] == [(n, "ok") for n in names]
    assert actors == ["system/job", "system/job"]


def test_the_tick_route_names_who_acts():
    """Der Wächter über alle Routen (``tests/test_log.py``) kennt den Takt; ohne die
    Markierung der Abhängigkeit meldete er ihn."""
    from tests.test_log import routes_without_actor

    from app.main import app
    assert routes_without_actor(app) == []
    oidc.require_tick.log_actor = False
    try:
        assert any(URL in r for r in routes_without_actor(app))
    finally:
        oidc.require_tick.log_actor = True


# ── Wie die Aufgaben laufen ──────────────────────────────────────────────────────────


def test_a_failing_task_does_not_stop_the_others(configured, monkeypatch, client):
    """Eine Aufgabe scheitert: gemeldet (500, damit Cloud Scheduler mitzählt), die nächste
    läuft trotzdem. Bug-Form: die Ausnahme brach den ganzen Lauf ab."""
    _claims(monkeypatch)
    after: list[str] = []

    def boom(_db, _deadline):
        raise RuntimeError("kaputt")
    bad, good = _name("boom"), _name("next")
    monkeypatch.setattr(tick, "TASKS", (tick.Task(bad, boom),
                                        tick.Task(good, lambda *_: after.append("x") or {})))
    r = client.post(URL, headers={"Authorization": "Bearer good"})
    assert r.status_code == 500
    states = {t["name"]: (t["state"], t["detail"]) for t in r.json()["tasks"]}
    assert states[bad][0] == "failed" and "kaputt" in states[bad][1]
    assert states[good] == ("ok", None) and after == ["x"]


def test_a_task_running_elsewhere_is_skipped():
    """Hält ein anderer Lauf die Sperre einer Aufgabe, wird sie übersprungen, nicht
    verdoppelt; danach ist die Sperre wieder frei. Bug-Form: ohne Sperre liefe sie zweimal."""
    from app.core.database import engine
    session()
    name = _name("locked")
    ran: list[str] = []
    task = tick.Task(name, lambda *_: ran.append("x") or {})
    with engine.connect() as other:
        other.execute(text("SELECT pg_advisory_lock(:s, :k)"),
                      {"s": tick.LOCK_SPACE, "k": tick.lock_key(name)})
        out = tick.run((task,))
        assert (out[0].state, ran) == ("skipped", [])
        other.execute(text("SELECT pg_advisory_unlock(:s, :k)"),
                      {"s": tick.LOCK_SPACE, "k": tick.lock_key(name)})
    assert tick.run((task,))[0].state == "ok" and ran == ["x"]
    assert tick.run((task,))[0].state == "ok" and ran == ["x", "x"], \
        "die Sperre ist nach dem Lauf frei"


def test_no_time_left_starts_nothing():
    """Nach der Zeitgrenze beginnt keine Aufgabe mehr – Bug-Form: der Lauf überschritte die
    60 s von Cloud Run, und die Anfrage bräche mitten in einer Aufgabe ab."""
    session()
    ran: list[str] = []
    out = tick.run((tick.Task(_name("late"), lambda *_: ran.append("x") or {}),),
                   start_within=0)
    assert out[0].state == "skipped" and ran == []


def test_what_happened_is_logged_and_nothing_when_nothing_happened():
    """Ein Ereignis ``tick.<name>`` mit den Zahlen, wenn etwas geschah – keines bei
    Leerlauf (288 Läufe am Tag). Bug-Form: jeder Lauf schriebe eine Zeile."""
    session()
    idle, busy = _name("idle"), _name("busy")
    tick.run((tick.Task(idle, lambda *_: {"new": 0, "sent": 0}),
              tick.Task(busy, lambda *_: {"new": 2, "sent": 0})))
    assert _events(idle) == []
    [ev] = _events(busy)
    assert ev.payload == {"new": 2} and (ev.actor_kind, ev.source) == ("system", "job")


def test_a_failed_task_writes_nothing():
    """Was eine gescheiterte Aufgabe schrieb, ist zurückgerollt – auch ihr Ereignis."""
    session()
    name = _name("half")

    def half(db, _deadline):
        from app.services import log
        log.event(db, f"tick.{name}", None, {"x": 1})
        raise RuntimeError("halb")
    assert tick.run((tick.Task(name, half),))[0].state == "failed"
    assert _events(name) == []


def test_the_seal_runs_in_the_tick(monkeypatch):
    """Das Siegel ist eine Aufgabe des Takts: danach ist kein abgeschlossener Tag mehr
    offen; versiegelte Tage stehen als ``tick.seal`` im Log."""
    from app.services import log
    session()
    seal = next(t for t in tick.TASKS if t.name == "seal")
    assert tick.run((seal,))[0].state == "ok"
    db = session()
    try:
        assert log.seal_due(db) == 0, "nichts mehr fällig"
        db.rollback()
    finally:
        db.close()
    before = len(_events("seal"))
    monkeypatch.setattr(log, "seal_due", lambda _db: 2)
    out = tick.run((seal,))
    assert out[0].done == {"days": 2} and len(_events("seal")) == before + 1


# ── Mails ohne Browser ───────────────────────────────────────────────────────────────


def test_the_tick_sends_a_due_mail_signed_by_its_writer(monkeypatch):
    """Der Takt handelt als System – die Mail geht trotzdem im Namen dessen hinaus, der sie
    geschrieben hat (``created_by``), und ``tick.mail`` zählt sie. Bug-Form: der Versand
    nähme den Handelnden (das System) als Absender, oder liefe nur aus dem offenen ERP."""
    import base64
    import email
    import email.policy

    from app.models import Mailbox, Message, MessageParty, UserProfile
    from app.services import mailbox as mb
    from tests.factories import new_person

    a = session()
    staff = new_person(a, "employee", first_name="Tina", last_name="Takt")
    lea = new_person(a, "user")
    box = Mailbox(channel="c999999977", address=f"takt{staff.object_id}@x.ch",
                  owner_object_id=staff.object_id, token="x", history_id="h1")
    msg = Message(sender_object_id=staff.object_id, channel=box.channel, subject="Offerte Takt",
                  body="Guten Tag", at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                  outgoing=True, created_by=staff.id)
    a.add_all([box, msg])
    a.flush()
    a.add(MessageParty(message_id=msg.id, person_object_id=lea.object_id, role="to"))
    a.commit()
    posted: dict[str, str] = {}

    def post(_token, body, what):
        if what == str(msg.id):
            posted["raw"] = body["raw"]
        return {"id": f"g{msg.id}", "threadId": "t"}, ""
    monkeypatch.setattr(mb, "ready", lambda: True)
    monkeypatch.setattr(mb, "_access", lambda _mb: "tok")
    monkeypatch.setattr(mb, "_new_ids", lambda _t, start: ([], start))
    monkeypatch.setattr(mb, "_post", post)
    monkeypatch.setattr(mb, "_rfc_id", lambda *_: None)
    try:
        before = len(_events("mail"))
        mail = next(t for t in tick.TASKS if t.name == "mail")
        out = tick.run((mail,))
        assert out[0].state == "ok" and out[0].done.get("sent", 0) >= 1
        sent = email.message_from_bytes(base64.urlsafe_b64decode(posted["raw"]),
                                        policy=email.policy.default)
        assert "Tina Takt" in str(sent["From"])
        a.expire_all()
        assert a.get(Message, msg.id).outgoing is False
        assert len(_events("mail")) == before + 1
    finally:
        a.rollback()
        a.query(MessageParty).filter(MessageParty.message_id == msg.id).delete()
        a.query(Message).filter(Message.id == msg.id).delete()
        a.query(Mailbox).filter(Mailbox.id == box.id).delete()
        a.query(UserProfile).filter(UserProfile.id.in_([staff.id, lea.id])).delete()
        a.commit()
        a.close()


def test_sending_stops_at_the_deadline(monkeypatch):
    """Nach der Zeitgrenze beginnt der Versand keine Mail mehr – sie wartet auf den nächsten
    Lauf. Bug-Form: ``deadline`` würde nicht beachtet."""
    from app.models import Mailbox, Message
    from app.services import mailbox as mb
    from tests.factories import new_person
    db = session()
    try:
        db.commit = db.flush
        staff = new_person(db, "employee")
        box = Mailbox(channel="c999999976", address=f"dl{staff.object_id}@x.ch",
                      owner_object_id=staff.object_id, token="x")
        msg = Message(sender_object_id=staff.object_id, channel=box.channel, subject="Später",
                      body="x", at=datetime(2000, 1, 1, tzinfo=timezone.utc), outgoing=True)
        db.add_all([box, msg])
        db.flush()
        tried: list[int] = []
        monkeypatch.setattr(mb, "send", lambda _db, m, _t=None: tried.append(m.id) or True)
        assert mb.send_due(db, deadline=0.0) == 0 and tried == []
        mb.send_due(db, deadline=None)
        assert msg.id in tried
    finally:
        db.rollback()
        db.close()
