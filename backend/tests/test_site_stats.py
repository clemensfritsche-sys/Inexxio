"""Wächter der Website-Statistik (``services/site_stats``, ``domain/site_sources``).

Geprüft wird das Versprechen der Datenschutzerklärung (keine IP, Kennung nur einen Tag, eine
Anfrage ohne Kennung) und dass jede Quelle in der Auswertung erscheint – auch eine unbekannte.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import get_db
from app.domain import site_sources as src
from app.models import SiteHit, SiteSalt
from app.routers import site_stats as route
from app.services import site_stats as st, site_stats_view as sv, visitor

CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/131.0 Safari/537.36")
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"


@pytest.mark.parametrize("ref,utm,key,channel", [
    ("https://www.google.ch/", None, "google", "search"),
    ("https://gemini.google.com/app", None, "gemini", "ai"),
    ("https://chatgpt.com/", None, "chatgpt", "ai"),
    (None, "chatgpt.com", "chatgpt", "ai"),
    ("https://www.perplexity.ai/search", None, "perplexity", "ai"),
    ("https://claude.ai/chat/1", None, "claude", "ai"),
    ("https://www.bing.com/search?q=x", None, "bing", "search"),
    ("https://l.facebook.com/", None, "facebook", "social"),
    (None, "newsletter", "newsletter", "mail"),
    ("https://verband-beispiel.ch/links", None, "verband-beispiel.ch", "referral"),
    (None, "messe2027", "utm:messe2027", "campaign"),
    (None, None, "direct", "direct"),
    ("", "", "direct", "direct"),
])
def test_every_source_has_a_name(ref, utm, key, channel):
    s = src.source_of(src.host_of(ref), utm)
    assert (s.key, s.channel) == (key, channel)
    assert s.label and s.channel in src.CHANNELS


def test_clean_path_drops_parameters_and_rejects_junk():
    assert st.clean_path("/newsletter/bestaetigt?t=geheim") == "/newsletter/bestaetigt"
    assert st.clean_path("/fr/contact/") == "/fr/contact"
    assert st.clean_path("/") == "/"
    for bad in ("", "kontakt", "/<script>", "/" + "a" * 400, None, 5):
        assert st.clean_path(bad) is None
    assert st.lang_of("/it/servizio") == "it" and st.lang_of("/kontakt") == "de"


def test_device_and_bots():
    assert st.device_of(IPHONE) == "mobile" and st.device_of(CHROME) == "desktop"
    assert st.is_bot("Googlebot/2.1") and st.is_bot("") and not st.is_bot(CHROME)


@pytest.fixture
def client(db):
    db.commit = db.flush
    st._salts.clear()
    visitor.reset()
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _send(client, ua=CHROME, ip="203.0.113.7", **data):
    r = client.post("/api/v1/public/page", content=json.dumps(data),
                       headers={"user-agent": ua, "x-forwarded-for": ip, "content-type": "text/plain"})
    client.app.dependency_overrides[get_db]().flush()   # wie das Ende einer echten Anfrage
    return r


def _hits(db):
    db.flush()          # die Sitzung speichert erst am Ende der Anfrage (kein autoflush)
    return db.execute(select(SiteHit).order_by(SiteHit.id)).scalars().all()


def test_a_visit_is_counted_without_the_address(client, db):
    db.query(SiteHit).delete()
    assert _send(client, k="view", p="/krantechnik/heukrananlagen", r="https://chatgpt.com/",
                 h="inexxio.com", q="?utm_campaign=x").status_code == 204
    _send(client, k="view", p="/kontakt", r="https://inexxio.com/krantechnik/heukrananlagen", h="inexxio.com")
    _send(client, k="call", p="/kontakt")
    _send(client, k="leave", p="/kontakt", v=42)
    _send(client, k="view", p="/kontakt", ua="Googlebot/2.1")            # Roboter
    _send(client, k="nonsense", p="/kontakt")                            # unbekannt
    hits = _hits(db)
    assert [h.kind for h in hits] == ["view", "view", "call", "leave"]
    assert len({h.visitor for h in hits}) == 1                           # derselbe Besuch
    first, second, call = hits[0], hits[1], hits[2]
    assert first.entry and first.ref_host == "chatgpt.com" and first.utm_campaign == "x"
    assert not second.entry and second.ref_host is None                  # innen: keine Quelle
    assert call.entry_path == "/krantechnik/heukrananlagen" and call.ref_host == "chatgpt.com"
    stored = " ".join(str(v) for h in hits for v in vars(h).values())
    assert "203.0.113.7" not in stored                                   # die IP nie


def test_the_key_of_a_day_goes_and_tomorrow_is_another_visit(client, db, monkeypatch):
    from datetime import date
    db.query(SiteSalt).delete()
    monkeypatch.setattr(st.clock, "today", lambda: date(2026, 11, 20))
    _send(client, k="view", p="/")
    monkeypatch.setattr(st.clock, "today", lambda: date(2026, 11, 21))
    _send(client, k="view", p="/")
    a, b = _hits(db)[-2:]
    assert a.visitor != b.visitor
    assert st.prune(db)["salts"] == 1
    assert [s.day for s in db.query(SiteSalt).all()] == [date(2026, 11, 21)]


def test_an_inquiry_carries_its_source_but_no_visitor(client, db):
    _send(client, k="view", p="/fahrzeugtechnik/trommeltausch", r="https://www.google.ch/", h="inexxio.com")
    w = st.Who(ip="203.0.113.7", ua=CHROME)
    st.convert(db, w, "inquiry", "/kontakt", "CH", message_id=None)
    st.convert(db, st.Who(ip="198.51.100.1", ua=CHROME), "inquiry", "/kontakt", "DE")  # ohne Besuch
    db.flush()
    inq = [h for h in _hits(db) if h.kind == "inquiry"]
    assert all(h.visitor is None for h in inq)
    assert inq[-2].entry_path == "/fahrzeugtechnik/trommeltausch" and inq[-2].ref_host == "google.ch"
    out = sv.view(db, 30)
    by_key = {s["key"]: s for s in out["sources"]}
    assert by_key["google"]["inquiries"] >= 1 and by_key["unknown"]["inquiries"] >= 1
    page = next(p for p in out["pages"] if p["path"] == "/fahrzeugtechnik/trommeltausch")
    assert page["inquiries"] >= 1
    assert out["totals"]["inquiries"] >= 2 and len(out["series"]) == 30


def test_view_rejects_unknown_periods(db):
    from app.domain.errors import Invalid
    with pytest.raises(Invalid):
        sv.view(db, 12)
