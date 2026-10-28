"""►►► **Newsletter und Rundschreiben** (``services/newsletter``, ``communication``). ◄◄◄

Gefahren über die echten Dienste gegen echtes PostgreSQL, ohne Netz: das Postfach ist ein
Ersatz, der festhält, was hinausginge. Jede Prüfung nennt die Regel, die sie hält.
"""

import random
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models import Message, MessageParty, UserProfile
from app.routers import contact
from app.routers import newsletter as router
from app.schemas.communication import MessageIn
from app.services import communication as comm
from app.services import inquiry
from app.services import mail_layout
from app.services import mailbox as mb
from app.services import newsletter as nl

CH = "c999999992"


def _person(db, role="user") -> UserProfile:
    oid = random.randint(900_000_000, 999_999_999)
    u = UserProfile(firebase_uid=f"uid-{oid}", email=f"p{oid}@x.ch", role=role,
                    object_id=oid, first_name="Lea", last_name=f"M{oid}")
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def world(db, monkeypatch):
    db.commit = db.flush            # zurückrollbar bleiben
    staff = _person(db, "employee")
    box = SimpleNamespace(owner_object_id=staff.object_id, problem=None,
                          address="info@example.ch", picture="")
    monkeypatch.setattr(mb, "ready", lambda: True)
    monkeypatch.setattr(mb, "active", lambda _db, ch: box if ch == CH else None)
    monkeypatch.setattr(mb, "assert_may_send", lambda *_a: None)
    monkeypatch.setattr(mb, "company", lambda _db, _ch: None)
    monkeypatch.setattr(nl, "sending_channel", lambda _db, _c=None: CH)
    app = FastAPI()
    for r in (router.router, router.me_router, router.erp_router):
        app.include_router(r)
    app.dependency_overrides[get_db] = lambda: db
    contact.reset_rate_limit()
    yield SimpleNamespace(db=db, staff=staff, box=box, client=TestClient(app))


def _group(db, first: Message) -> list[Message]:
    return db.query(Message).filter(Message.group_id == first.id).order_by(Message.id).all()


# ------------------------------------------------------------------ Einwilligung

def test_two_states_and_every_change_is_a_row(world):
    """Angemeldet oder nicht – die jüngste Zeile. Zweimal anmelden ist einmal; eine
    Abmeldung ist eine neue Zeile, keine Änderung. Die Anmeldung trägt den Wortlaut."""
    db, p = world.db, _person(world.db)
    assert nl.subscribed(db, [p.object_id]) == set()
    assert nl.set_state(db, p.object_id, True, "account")
    assert not nl.set_state(db, p.object_id, True, "account")
    assert nl.subscribed(db, [p.object_id]) == {p.object_id}
    assert nl.set_state(db, p.object_id, False, "link")
    rows = nl.history(db, p.object_id)
    assert [r.subscribed for r in rows] == [False, True]
    assert rows[1].wording == nl.WORDING and rows[0].wording is None
    with pytest.raises(ValueError):
        nl.set_state(db, p.object_id, True, "erfunden")


def test_a_link_cannot_be_forged_reused_for_another_purpose_or_kept_forever(monkeypatch):
    t = nl.sign(123, "confirm", "website", days=1)
    assert nl.read(t, "confirm") == (123, "website")
    with pytest.raises(ValueError):
        nl.read(t, "unsubscribe")                       # ein Zweck je Link
    raw, _, sig = t.partition(".")
    with pytest.raises(ValueError):
        nl.read(f"{raw}.{'0' * len(sig)}", "confirm")    # gefälscht
    monkeypatch.setattr(time, "time", lambda: 10**12)
    with pytest.raises(ValueError):
        nl.read(t, "confirm")                           # abgelaufen
    assert nl.read(nl.sign(5, "unsubscribe"), "unsubscribe") == (5, "")   # ohne Ablauf


def test_the_erp_cannot_subscribe_anyone_it_can_only_ask(world, monkeypatch):
    """Die Einladung ist eine Mail im Verlauf der Person; angemeldet ist sie erst mit ihrem
    Klick – mit der Quelle aus dem Link. Wer angemeldet ist, bekommt keine zweite Bitte."""
    db, p = world.db, _person(world.db)
    sent: list[Message] = []
    monkeypatch.setattr(mb, "send", lambda _db, m: sent.append(m) or True)
    m = nl.invite(db, p.object_id, "invitation")
    assert sent[-1].id == m.id and m.subject == nl.WORDS["confirmSubject"]
    assert [x.person_object_id for x in db.query(MessageParty).filter(
        MessageParty.message_id == m.id)] == [p.object_id]
    assert nl.WORDS["confirmButton"] in m.body and "/api/v1/newsletter/confirm?t=" in m.body
    assert nl.subscribed(db, [p.object_id]) == set()         # noch nicht angemeldet
    token = m.body.split("confirm?t=")[1].split()[0]
    res = world.client.get(f"/api/v1/newsletter/confirm?t={token}", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/newsletter/bestaetigt"
    (row,) = nl.history(db, p.object_id)
    assert row.subscribed and row.source == "invitation" and row.wording == nl.WORDING
    with pytest.raises(HTTPException) as exc:
        nl.invite(db, p.object_id, "invitation")
    assert exc.value.status_code == 409


def test_the_unsubscribe_link_shows_a_button_and_one_click_works_directly(world):
    """Ein Link-Scanner ruft GET auf – davon wird niemand abgemeldet. Der Knopf (POST)
    meldet ab, ebenso «Abbestellen» im Mailprogramm (RFC 8058)."""
    db, p = world.db, _person(world.db)
    nl.set_state(db, p.object_id, True, "account")
    t = nl.sign(p.object_id, "unsubscribe")
    page = world.client.get(f"/api/v1/newsletter/unsubscribe?t={t}")
    assert page.status_code == 200 and 'method="post"' in page.text
    assert nl.subscribed(db, [p.object_id]) == {p.object_id}
    res = world.client.post(f"/api/v1/newsletter/unsubscribe?t={t}", follow_redirects=False)
    assert res.status_code == 303 and nl.subscribed(db, [p.object_id]) == set()
    nl.set_state(db, p.object_id, True, "account")
    res = world.client.post(f"/api/v1/newsletter/unsubscribe?t={t}",
                            content="List-Unsubscribe=One-Click",
                            headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert res.status_code == 200 and nl.history(db, p.object_id)[0].source == "one_click"
    assert world.client.get("/api/v1/newsletter/unsubscribe?t=kaputt").status_code == 400


# ------------------------------------------------------------------ Versandarten

def _send(world, delivery, to, **kw):
    return comm.create(world.db, MessageIn(channel=CH, to=to, subject="Betriebsferien",
                                           body="Wir sind vom 1. bis 14. August zu.",
                                           delivery=delivery, **kw), world.staff)


def test_a_circular_is_one_mail_per_person_with_her_own_greeting(world):
    """Rundschreiben: je Person eine Nachricht, im «An» nur sie, mit ihrer Anrede – so
    steht im Verlauf, was hinausging. Hinaus geht es über den Abgleich, nicht im Klick."""
    db = world.db
    a, b = _person(db), _person(db)
    first = _send(world, "circular", [a.object_id, b.object_id, a.object_id])
    copies = _group(db, first)
    assert len(copies) == 2 and all(m.outgoing and not m.newsletter for m in copies)
    for m, p in zip(copies, (a, b)):
        assert m.body.startswith(f"Guten Tag {p.display_name}\n\n")
        assert [x.person_object_id for x in db.query(MessageParty).filter(
            MessageParty.message_id == m.id)] == [p.object_id]
    with pytest.raises(HTTPException):
        _send(world, "circular", [a.object_id], cc=[b.object_id])


def test_the_history_shows_a_circular_once(world):
    """Wer es schrieb, sieht es einmal (mit der Zahl der Empfänger); jede Empfängerin
    sieht ihre eigene Kopie."""
    db = world.db
    a, b = _person(db), _person(db)
    first = _send(world, "circular", [a.object_id, b.object_id])
    mine = [m for m in comm.history(db, person=world.staff.object_id) if m.subject == "Betriebsferien"]
    assert len(mine) == 1 and mine[0].recipients == 2 and mine[0].delivery == "circular"
    (theirs,) = [m for m in comm.history(db, person=b.object_id) if m.delivery == "circular"]
    assert theirs.id == _group(db, first)[1].id and [p.object_id for p in theirs.to] == [b.object_id]


def test_a_newsletter_goes_only_to_subscribers_and_checks_again_when_sending(world, monkeypatch):
    """Das Tor sitzt im Dienst: ohne Einwilligung 400 mit Namen. Und wer sich zwischen
    Schreiben und Senden abmeldet, bekommt ihn nicht – die Kopie wird zurückgezogen.
    Gegenprobe der Bug-Form: ohne die zweite Prüfung ginge sie hinaus."""
    db = world.db
    a, b = _person(db), _person(db)
    nl.set_state(db, a.object_id, True, "account")
    with pytest.raises(HTTPException) as exc:
        _send(world, "newsletter", [a.object_id, b.object_id])
    assert b.display_name in exc.value.detail
    nl.set_state(db, b.object_id, True, "account")
    first = _send(world, "newsletter", [a.object_id, b.object_id])
    ca, cb = _group(db, first)
    assert ca.newsletter and cb.newsletter
    nl.set_state(db, b.object_id, False, "link")
    monkeypatch.setattr(mb, "_access", lambda _mb: None)    # nicht ins Netz
    assert mb.send(db, cb) is False and not cb.is_active and not cb.outgoing
    assert mb._consents(db, ca) and not mb._consents(db, cb)


def test_a_newsletter_carries_the_unsubscribe_link_in_footer_and_header(world):
    db = world.db
    a = _person(db)
    nl.set_state(db, a.object_id, True, "account")
    first = _send(world, "newsletter", [a.object_id])
    mime = mb._mime(db, world.box, first, None)
    url = nl.unsubscribe_url(a.object_id)
    assert mime["List-Unsubscribe"] == f"<{url}>"
    assert mime["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    html = mime.get_body(("html",)).get_content()
    assert nl.WORDS["footer"] in html and url.replace("&", "&amp;") in html
    assert url not in first.body                    # der Abmeldelink steht im Fuss, nicht im Inhalt
    plain = _send(world, "circular", [a.object_id])
    assert "List-Unsubscribe" not in mb._mime(db, world.box, plain, None)


# ------------------------------------------------------------------ Kontaktformular

def test_the_inquiry_confirmation_asks_or_invites_but_never_twice(world):
    """Mit Häkchen bittet die Eingangsbestätigung um den Klick, ohne lädt sie leise ein;
    wer angemeldet ist oder sich abgemeldet hat, bekommt keinen Knopf."""
    db = world.db
    p = _person(db)
    asked, offered = nl.offer(db, p.object_id, True), nl.offer(db, p.object_id, False)
    assert asked.text == nl.WORDS["inviteAsked"] and offered.text == nl.WORDS["inviteOffer"]
    assert nl.read(asked.url.split("t=")[1].replace("%3D", "="), "confirm")[1] == "inquiry"
    nl.set_state(db, p.object_id, True, "account")
    assert nl.offer(db, p.object_id, True) is None
    nl.set_state(db, p.object_id, False, "link")
    assert nl.offer(db, p.object_id, False) is None and nl.offer(db, p.object_id, True)
    mail = mail_layout.compose("x", "Text", mail_layout.Firm(name="F"), None,
                               extra=mail_layout.Extra(action=asked))
    assert asked.url in mail.body and asked.label in mail.html
    assert inquiry.Inquiry(name="", email="", message="").newsletter is False

