"""►►► **Gmail meldet neue Mails selbst** (Push über Pub/Sub, ``mailbox.watch`` · ``push``). ◄◄◄

Die Anmeldung bei Gmail hält höchstens sieben Tage – der Takt erneuert sie, bevor sie
abläuft. Ein gemeldetes Postfach holt der Browser nicht mehr ab; die Meldung holt es sofort,
der Takt bleibt das Netz. Jede Prüfung nennt ihre Bug-Form.
"""

import base64
import json
from datetime import timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import clock
from app.core.database import get_db
from app.core.oidc import require_tick
from app.routers import communication as router
from app.services import mailbox as mb
from tests import test_mailbox
from tests.test_mailbox import COMPANY

world = test_mailbox.world     # dieselbe Bühne: Postfach, Mitarbeiter, eigene Adresse

TOPIC = "projects/inexxio-dev/topics/inexxio-mail"


class _Resp:
    def __init__(self, data, status=200):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


def _push_on(monkeypatch):
    monkeypatch.setattr(mb, "ready", lambda: True)
    monkeypatch.setattr(mb, "get_settings", lambda: SimpleNamespace(gmail_topic=TOPIC))
    monkeypatch.setattr(mb, "_token", lambda _mb, _t=None: "tok")


def test_the_mailbox_asks_gmail_to_report_and_renews_before_it_ends(world, monkeypatch):
    """Bug-Form ohne Erneuerung: nach sieben Tagen meldete Gmail nichts mehr, und niemand
    merkte es. Erneuert wird, was in weniger als einem Tag abläuft – sonst nichts."""
    db, _staff, box = world
    _push_on(monkeypatch)
    asked: list[dict] = []
    end = clock.utcnow() + timedelta(days=7)
    monkeypatch.setattr(mb.httpx, "post", lambda url, **kw: asked.append(kw["json"]) or _Resp(
        {"historyId": "9", "expiration": str(int(end.timestamp() * 1000))}))
    mb.watch(db, box)
    assert asked == [{"topicName": TOPIC, "labelIds": ["INBOX", "SENT"],
                      "labelFilterBehavior": "INCLUDE"}]
    assert box.watch_until and abs((box.watch_until - end).total_seconds()) < 1
    mb.watch(db, box)
    assert len(asked) == 1, "noch sechs Tage – nicht erneut"
    box.watch_until = clock.utcnow() + timedelta(hours=3)
    mb.watch(db, box)
    assert len(asked) == 2, "läuft heute ab – erneuert"


def test_without_a_topic_nothing_is_asked(world, monkeypatch):
    db, _staff, box = world
    monkeypatch.setattr(mb, "get_settings", lambda: SimpleNamespace(gmail_topic=""))
    monkeypatch.setattr(mb.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    mb.watch(db, box)
    assert box.watch_until is None


def test_a_reported_mailbox_is_fetched_by_the_report_not_by_the_browser(world, monkeypatch):
    """Bug-Form: jeder offene Browser holte alle 30 s bei Gmail ab, auch wenn Gmail selbst
    meldet. Jetzt holt der Browser dort nichts – die Meldung holt sofort, der Takt als Netz."""
    db, _staff, box = world
    _push_on(monkeypatch)
    box.watch_until = clock.utcnow() + timedelta(days=5)
    box.synced_at = None
    db.flush()
    fetched: list[str] = []
    monkeypatch.setattr(mb, "_sync_one", lambda _db, m, *_a, **_k: fetched.append(m.channel) or 0)
    monkeypatch.setattr(mb, "_mark_read", lambda *_a, **_k: None)
    monkeypatch.setattr(mb, "send_due", lambda *_a, **_k: 0)
    monkeypatch.setattr(db, "commit", db.flush)
    mb.sync_all(db, browser=True)
    assert box.channel not in fetched
    mb.sync_all(db)
    assert box.channel in fetched, "der Takt holt trotzdem – das Netz"
    fetched.clear()
    assert mb.push(db, COMPANY.upper()) == 0 and fetched == [box.channel]
    fetched.clear()
    assert mb.push(db, "fremd@example.org") == 0 and fetched == []


def test_the_report_of_pubsub_reaches_the_mailbox(world, monkeypatch):
    """Die Meldung kommt als Umschlag von Pub/Sub (``message.data`` base64) – angemeldet wie
    der Takt (``require_tick``); was nicht lesbar ist, wird bestätigt und vergessen (204)."""
    db, _staff, _box = world
    got: list[str] = []
    monkeypatch.setattr(mb, "push", lambda _db, address: got.append(address) or 0)
    app = FastAPI()
    app.include_router(router.callback_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_tick] = lambda: None
    client = TestClient(app)
    data = base64.b64encode(json.dumps({"emailAddress": COMPANY, "historyId": 7}).encode()).decode()
    assert client.post("/api/v1/mail/push", json={"message": {"data": data}}).status_code == 204
    assert client.post("/api/v1/mail/push", json={"message": {"data": "kaputt"}}).status_code == 204
    assert got == [COMPANY]
