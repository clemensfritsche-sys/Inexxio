"""►►► **Eine unbestätigte Adresse bekommt nichts** (``core/auth``). ◄◄◄

Angelegt, übernommen, auf eine neue E-Mail umgestellt und zum Admin befördert wird nur mit
``email_verified``. Eine Anmeldung mit Passkey findet die Person über die UID. Gefahren gegen
echtes PostgreSQL; jede Prüfung ist gegen ihre Bug-Form gegengeprüft.
"""

import random
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.core import auth
from app.models import UserProfile


def _token(uid: str, email: str, verified: bool, **extra) -> dict:
    return {"uid": uid, "email": email, "email_verified": verified, **extra}


def _n() -> int:
    return random.randint(10**8, 10**9)


def test_an_unverified_address_creates_no_person(db):
    n = _n()
    with pytest.raises(HTTPException) as exc:
        auth._resolve_user(db, f"uid-{n}", f"neu{n}@x.ch", _token(f"uid-{n}", f"neu{n}@x.ch", False))
    assert exc.value.status_code == 403 and "bestätigt" in exc.value.detail
    assert db.query(UserProfile).filter(UserProfile.email == f"neu{n}@x.ch").count() == 0
    db.commit = db.flush
    u = auth._resolve_user(db, f"uid-{n}", f"neu{n}@x.ch", _token(f"uid-{n}", f"neu{n}@x.ch", True))
    assert u.object_id and u.firebase_uid == f"uid-{n}"


def test_an_unverified_address_takes_over_nobody(db):
    """Eine intern angelegte Person (``mail:…``) übernimmt nur, wer die Adresse bestätigt."""
    db.commit = db.flush
    n = _n()
    lea = UserProfile(firebase_uid=f"mail:lea{n}@x.ch", email=f"lea{n}@x.ch", role="user",
                      object_id=n)
    db.add(lea)
    db.flush()
    with pytest.raises(HTTPException):
        auth._resolve_user(db, f"fb-{n}", lea.email, _token(f"fb-{n}", lea.email, False))
    assert lea.firebase_uid == f"mail:lea{n}@x.ch"
    assert auth._resolve_user(db, f"fb-{n}", lea.email, _token(f"fb-{n}", lea.email, True)) is lea
    assert lea.firebase_uid == f"fb-{n}"


def test_a_passkey_login_finds_the_person_by_its_uid(db):
    """Ein Custom Token (Passkey) muss keine bestätigte Adresse tragen – die Person gibt es."""
    db.commit = db.flush
    n = _n()
    u = UserProfile(firebase_uid=f"fb-{n}", email=f"pk{n}@x.ch", role="user", object_id=n)
    db.add(u)
    db.flush()
    decoded = {"uid": f"fb-{n}", "firebase": {"sign_in_provider": "custom"}}
    assert auth._resolve_user(db, f"fb-{n}", "", decoded) is u


def test_promotion_and_email_change_need_a_verified_address(db, monkeypatch):
    db.commit = db.flush
    n = _n()
    monkeypatch.setattr(auth.settings, "initial_admin_email", f"boss{n}@x.ch")
    u = UserProfile(firebase_uid=f"fb-{n}", email=f"alt{n}@x.ch", role="user", object_id=n)
    db.add(u)
    db.flush()
    auth._sync_user_profile(db, u, f"boss{n}@x.ch", _token(u.firebase_uid, f"boss{n}@x.ch", False))
    assert (u.role, u.email) == ("user", f"alt{n}@x.ch")
    auth._sync_user_profile(db, u, f"boss{n}@x.ch", _token(u.firebase_uid, f"boss{n}@x.ch", True))
    assert (u.role, u.email) == ("admin", f"boss{n}@x.ch")


def test_the_last_login_comes_from_the_token(db):
    """``last_login_at`` = ``auth_time`` des Tokens, bei jeder Anmeldung – geschrieben nur bei
    einer Änderung (ein erneuertes Token derselben Anmeldung schreibt nichts)."""
    db.commit = db.flush
    n = _n()
    u = UserProfile(firebase_uid=f"fb-{n}", email=f"t{n}@x.ch", role="user", object_id=n)
    db.add(u)
    db.flush()
    at = 1_790_000_000
    auth._sync_user_profile(db, u, u.email, _token(u.firebase_uid, u.email, True, auth_time=at))
    assert u.last_login_at == datetime.fromtimestamp(at, timezone.utc)


def test_passkey_challenges_are_limited_like_every_public_door(db, monkeypatch):
    """Jede Challenge ist eine Zeile – ohne Grenze füllte eine Schleife die Tabelle. Dieselbe
    Begrenzung wie Anfrage und Newsletter (``services/visitor``)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    from app.routers import passkey as router
    from app.services import passkey, visitor
    visitor.reset()
    monkeypatch.setattr(passkey, "begin_authentication", lambda _db, _r: {"challenge": "x"})
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    h = {"X-Forwarded-For": "203.0.113.9"}
    for _ in range(router.LOGIN_LIMIT):
        assert client.post("/api/v1/auth/passkeys/login/options", headers=h).status_code == 200
    assert client.post("/api/v1/auth/passkeys/login/options", headers=h).status_code == 429
    visitor.reset()
