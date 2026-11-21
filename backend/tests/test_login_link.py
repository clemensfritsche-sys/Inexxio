"""►►► **Der Anmeldelink im Kleid des Hauses** (``services/login_link``, ``POST /api/v1/auth/link``). ◄◄◄

Gefahren über die echte Route gegen echtes PostgreSQL, ohne Netz: Firebase und das Postfach
sind Ersatz, der festhält, was hinausginge. Jede Prüfung nennt die Regel, die sie hält.
"""

import random
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models import UserProfile
from app.routers import auth as router
from app.services import login_link, visitor
from app.services import mailbox as mb
from app.services import newsletter as nl
from tests.factories import quiet_outbox

CH = "c999999993"


@pytest.fixture
def world(db, monkeypatch):
    db.commit = db.flush            # zurückrollbar bleiben
    quiet_outbox(db)
    box = SimpleNamespace(problem=None, address="info@example.ch", picture="")
    monkeypatch.setattr(mb, "active", lambda _db, ch: box if ch == CH else None)
    monkeypatch.setattr(mb, "company", lambda _db, _ch: None)
    monkeypatch.setattr(nl, "sending_channel", lambda _db, _c=None: CH)
    asked: list = []
    monkeypatch.setattr(login_link, "make_link", lambda email: asked.append(email) or
                        f"https://example.firebaseapp.com/__/auth/action?mode=signIn&oobCode=X&e={email}")
    out: list = []
    monkeypatch.setattr(mb, "send_direct", lambda _db, ch, to, subj, mail: out.append(
        (ch, to, subj, mail)) or True)
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_db] = lambda: db
    visitor.reset()
    yield SimpleNamespace(db=db, out=out, asked=asked, client=TestClient(app))


def _email() -> str:
    return f"anmelden{random.randint(1, 10**9)}@kunde.ch"


def test_the_link_goes_out_in_the_house_mail_and_creates_nobody(world):
    """►►► **Der Link kommt vom Haus, nicht von Google** – aus dem Postfach der Gesellschaft, in
    der einen Vorlage, mit EINEM Knopf; angelegt wird nichts (die Person entsteht bei der
    Anmeldung). Bug-Form: die Mail kam von noreply@…firebaseapp.com im Kleid von Google."""
    email = _email()
    res = world.client.post("/api/v1/auth/link", json={"email": f"  {email.upper()} "})
    assert res.status_code == 200 and res.json() == {"sent": True}
    (ch, to, subject, mail), = world.out
    assert ch == CH and to == email and world.asked == [email]
    assert subject == login_link.WORDS["subject"]
    assert "oobCode=X" in mail.html and login_link.WORDS["button"] in mail.html
    assert "oobCode=X" in mail.text, "die Textfassung trägt den Link auch"
    assert world.db.query(UserProfile).filter(UserProfile.email == email).count() == 0


def test_without_a_mailbox_the_answer_says_so(world, monkeypatch):
    """Ohne verbundenes Postfach geht nichts hinaus – und die Antwort sagt es (``sent=false``),
    damit die Oberfläche den Link über Firebase schickt. Bug-Form: «gesendet», aber nichts kam."""
    monkeypatch.setattr(nl, "sending_channel", lambda _db, _c=None: None)
    res = world.client.post("/api/v1/auth/link", json={"email": _email()})
    assert res.json() == {"sent": False} and world.out == [] and world.asked == []


def test_a_failing_firebase_or_gmail_falls_back(world, monkeypatch):
    """Erzeugt Firebase keinen Link oder weist Gmail ab: ``sent=false`` statt eines Fehlers."""
    def broken(_email):
        raise RuntimeError("identitytoolkit unreachable")
    monkeypatch.setattr(login_link, "make_link", broken)
    assert world.client.post("/api/v1/auth/link", json={"email": _email()}).json() == {"sent": False}
    monkeypatch.setattr(login_link, "make_link", lambda e: "https://x/y")
    monkeypatch.setattr(mb, "send_direct", lambda *_a: False)
    assert world.client.post("/api/v1/auth/link", json={"email": _email()}).json() == {"sent": False}


def test_nonsense_and_floods_send_nothing(world):
    """Keine Adresse → nichts; mehr als ``LINK_LIMIT`` je Absender und Stunde → nichts (die
    Oberfläche nimmt dann Firebase, das selbst begrenzt). Bug-Form: das Formular als Mail-Kanone."""
    assert world.client.post("/api/v1/auth/link", json={"email": "kein-mail"}).json() == {"sent": False}
    for _ in range(router.LINK_LIMIT):
        assert world.client.post("/api/v1/auth/link", json={"email": _email()}).json()["sent"]
    assert world.client.post("/api/v1/auth/link", json={"email": _email()}).json() == {"sent": False}
    assert len(world.out) == router.LINK_LIMIT


def test_the_link_always_leads_to_our_own_page(monkeypatch):
    """Wohin der Link führt, bestimmt der Server – nie eine Adresse aus der Anfrage."""
    from app.core import config
    monkeypatch.setattr(config.get_settings(), "frontend_base_url", "https://inexxio.com/")
    assert login_link.continue_url() == "https://inexxio.com/login/verify"
