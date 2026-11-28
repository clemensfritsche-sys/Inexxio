"""►►► **Spam aus dem Formular – aussortiert, nicht gelöscht** (``services/spam``). ◄◄◄

Jede Prüfung nennt ihre Bug-Form.
"""

from types import SimpleNamespace

import pytest

from app.domain.errors import Conflict
from app.models import Message, UserProfile
from app.services import ai, spam, tasks
from app.services import inquiry as svc
from tests import test_contact
from tests.test_contact import CHANNEL, FIRM, JSON, form, inquiries
from tests.support import after_save

world = test_contact.world


@pytest.fixture
def spammy(world, monkeypatch):
    """Die KI hält jede Anfrage für Spam; die Gesellschaft gibt es."""
    monkeypatch.setattr(spam, "screen", lambda _db, _inq: "Werbung ohne Bezug.")
    monkeypatch.setattr(spam, "sites", SimpleNamespace(
        by_object_id=lambda _db, oid: SimpleNamespace(object_id=oid)))
    return world


def _post(world, **extra) -> dict:
    data = form(**extra)
    res = world.client.post("/api/v1/contact", data=data, headers=JSON)
    assert res.status_code == 200 and res.json()["ok"] is True, res.text
    return data


def test_spam_creates_nothing_but_is_held_at_the_company(spammy):
    """Bug-Form: Spam legte eine Person «Robertattaw» an, eine offene Nachricht – und schickte
    eine Bestätigung an eine fremde Adresse."""
    data = _post(spammy, message="Hi, kam dashur të di çmimin tuaj")
    after_save(spammy.db)
    assert spammy.db.query(UserProfile).filter(UserProfile.email == data["email"]).first() is None
    assert spammy.sent == []
    (held,) = [h for h in spam.open_held(spammy.db, FIRM) if h.payload["email"] == data["email"]]
    assert held.payload["message"] == "Hi, kam dashur të di çmimin tuaj"
    assert held.payload["reason"] == "Werbung ohne Bezug."


def test_held_is_a_task_until_someone_decides(spammy):
    """Bug-Form: eine aussortierte Anfrage geriet in Vergessenheit – niemand sah sie."""
    data = _post(spammy)
    (held,) = [h for h in spam.open_held(spammy.db, FIRM) if h.payload["email"] == data["email"]]
    keys = {t.key: t for t in tasks.collect(spammy.db)}
    task = keys[f"held:{held.id}"]
    assert (task.object_id, task.part) == (FIRM, "aussortiert")
    spam.discard(spammy.db, held.id)
    assert f"held:{held.id}" not in {t.key for t in tasks.collect(spammy.db)}
    assert held.id not in [h.id for h in spam.open_held(spammy.db, FIRM)]


def test_no_spam_creates_the_inquiry_as_if_it_just_came(spammy):
    """«Kein Spam»: dieselbe Stelle wie das Formular (``inquiry.record``) – Person, offene
    Nachricht unter «Anfrage», Bestätigung. Bug-Form: eine verwechselte echte Anfrage war weg."""
    data = _post(spammy, name="Anna Muster")
    (held,) = [h for h in spam.open_held(spammy.db, FIRM) if h.payload["email"] == data["email"]]
    message_id = spam.release(spammy.db, held.id)
    after_save(spammy.db)
    (msg,) = inquiries(spammy.db, data["email"])
    assert msg.id == message_id and msg.channel == CHANNEL and msg.subject == svc.SUBJECT
    assert len(spammy.sent) == 1, "die Bestätigung geht jetzt hinaus"
    confirmation = spammy.db.get(Message, spammy.sent[0])
    assert confirmation.subject != svc.SUBJECT, "die Bestätigung erledigt die Anfrage nicht"


def test_one_decision_per_held_inquiry(spammy):
    """Bug-Form: zwei Klicks legten die Anfrage zweimal an (oder «Spam» nach «Kein Spam»)."""
    data = _post(spammy)
    (held,) = [h for h in spam.open_held(spammy.db, FIRM) if h.payload["email"] == data["email"]]
    spam.release(spammy.db, held.id)
    with pytest.raises(Conflict):
        spam.release(spammy.db, held.id)
    with pytest.raises(Conflict):
        spam.discard(spammy.db, held.id)


def test_without_ai_every_inquiry_goes_through(world, monkeypatch):
    """Im Zweifel kein Spam: keine KI, ein Fehler, eine unbrauchbare Antwort – die Anfrage
    kommt an. Bug-Form: ein Ausfall der KI verschluckte echte Anfragen."""
    monkeypatch.setattr(ai, "ask", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("weg")))
    data = _post(world)
    assert len(inquiries(world.db, data["email"])) == 1
    monkeypatch.setattr(ai, "ask", lambda *a, **k: None)
    data = _post(world)
    assert len(inquiries(world.db, data["email"])) == 1


def test_the_verdict_of_the_ai_decides(world, monkeypatch):
    """Was die KI sagt, gilt – «kein Spam» geht durch, «Spam» wird aussortiert."""
    monkeypatch.setattr(ai, "ask", lambda *a, **k: spam.Verdict(spam=False, reason="Kunde"))
    assert spam.screen(world.db, svc.Inquiry(name="A", email="a@b.ch", message="Kran?")) is None
    monkeypatch.setattr(ai, "ask", lambda *a, **k: spam.Verdict(spam=True, reason=" Bot  "))
    assert spam.screen(world.db, svc.Inquiry(name="A", email="a@b.ch", message="x")) == "Bot"


def _held_once(world, monkeypatch, **extra) -> dict:
    """Eine Anfrage, die die KI aussortiert – danach sagt die KI «kein Spam» (sie urteilt nicht
    jedes Mal gleich)."""
    monkeypatch.setattr(ai, "ask", lambda *a, **k: spam.Verdict(spam=True, reason="Bot"))
    data = _post(world, **extra)
    monkeypatch.setattr(ai, "ask", lambda *a, **k: spam.Verdict(spam=False, reason="Kunde"))
    return data


def test_a_held_sender_stays_held_even_if_the_ai_changes_its_mind(world, monkeypatch):
    """Bug-Form (Produktion, 28.11.2026): «Robertattaw» mit dwals100@aol.com um 10:23
    aussortiert, um 10:29 mit demselben Text durch – Person, offene Nachricht, Bestätigung an
    eine fremde Adresse."""
    data = _held_once(world, monkeypatch)
    _post(world, email=data["email"].upper(), message="Hola, quería saber tu precio.")
    assert inquiries(world.db, data["email"]) == []
    held = [h for h in spam.open_held(world.db, FIRM) if h.payload["email"].lower() == data["email"].lower()]
    assert len(held) == 2 and "gleicher Absender" in held[0].payload["reason"]


def test_same_name_and_firm_stay_held_under_a_new_address(world, monkeypatch):
    """Bug-Form: derselbe Bot (Name «Robertattaw», Firma «google») mit jeder Anfrage unter einer
    neuen Adresse."""
    _held_once(world, monkeypatch, name="Robertattaw", company="google")
    data = _post(world, name=" robertattaw ", company="Google")
    assert inquiries(world.db, data["email"]) == []


def test_a_name_alone_or_a_released_sender_is_not_held(world, monkeypatch):
    """Gegenprobe: ohne Firma reicht der Name nicht (zwei echte «Anna Muster»), und wer «Kein
    Spam» bekam, wird wieder von der KI beurteilt."""
    _held_once(world, monkeypatch, name="Anna Muster", company="")
    data = _post(world, name="Anna Muster", company="")
    assert len(inquiries(world.db, data["email"])) == 1
    first = _held_once(world, monkeypatch)
    (held,) = [h for h in spam.open_held(world.db, FIRM) if h.payload["email"] == first["email"]]
    monkeypatch.setattr(spam, "sites", SimpleNamespace(
        by_object_id=lambda _db, oid: SimpleNamespace(object_id=oid)))
    spam.release(world.db, held.id)
    _post(world, email=first["email"])
    assert len(inquiries(world.db, first["email"])) == 2
