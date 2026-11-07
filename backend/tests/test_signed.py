"""►►► **Signierte Links an EINER Stelle** (``core/signed``). ◄◄◄

Ein Link trägt Inhalt, Zweck und Ablauf; mit ``LINK_SECRET`` signiert, geprüft mit dem neuen
UND dem früheren Schlüssel – verschickte Abmeldelinks ohne Ablauf bleiben gültig.
"""

import base64
import hashlib
import hmac
import json
import time

import pytest

from app.core import signed
from app.core.config import get_settings
from app.services import newsletter as nl


def _old_newsletter_link(oid: int, purpose: str) -> str:
    """Ein Link, wie ihn der Newsletter vor ``core/signed`` ausstellte (Schlüssel aus der
    Datenbankverbindung) – solche sind in verschickten Mails unterwegs."""
    key = hashlib.sha256(f"newsletter:{get_settings().database_url}".encode()).digest()
    raw = base64.urlsafe_b64encode(json.dumps({"p": oid, "u": purpose, "s": ""},
                                              separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{raw}.{hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]}"


def test_purpose_forgery_and_expiry(monkeypatch):
    monkeypatch.setattr(get_settings(), "link_secret", "neu-geheim")
    t = signed.sign({"c": "c1"}, "mailbox", 60)
    assert signed.read(t, "mailbox") == {"c": "c1"}
    with pytest.raises(signed.Invalid):
        signed.read(t, "unsubscribe")                           # ein Zweck je Link
    raw, _, sig = t.partition(".")
    with pytest.raises(signed.Invalid):
        signed.read(f"{raw}.{'0' * len(sig)}", "mailbox")       # gefälscht
    monkeypatch.setattr(time, "time", lambda: 10**12)
    with pytest.raises(signed.Invalid):
        signed.read(t, "mailbox")                               # abgelaufen
    with pytest.raises(ValueError):
        signed.sign({"u": 1}, "x")                              # reserviert


def test_the_new_key_signs_and_old_links_stay_valid(monkeypatch):
    """Bug-Formen: (a) mit ``LINK_SECRET`` wäre jeder verschickte Abmeldelink tot; (b) es
    signierte weiter der alte Schlüssel; (c) ein mit dem neuen Schlüssel signierter Link
    gälte ohne ihn."""
    old = _old_newsletter_link(42, "unsubscribe")
    assert nl.read(old, "unsubscribe").person == 42             # ohne LINK_SECRET
    monkeypatch.setattr(get_settings(), "link_secret", "neu-geheim")
    assert nl.read(old, "unsubscribe").person == 42, "(a)"
    fresh = nl.sign("unsubscribe", person=42)
    raw, _, sig = fresh.partition(".")
    assert sig == hmac.new(b"neu-geheim", raw.encode(), hashlib.sha256).hexdigest()[:32], "(b)"
    monkeypatch.setattr(get_settings(), "link_secret", "")
    with pytest.raises(ValueError):
        nl.read(fresh, "unsubscribe")                           # (c)
