"""►►► **Der Assistent: Gespräch und Handgriff** (Projektakte, Phase 5 §7). ◄◄◄

Die KI wird nachgebildet (``_Script`` wie in ``tests/test_ai_core.py``) – nie ein echter Aufruf.
Ein Handgriff läuft in eigener Sitzung durch die echte Route; darum sind Personen und Firmen hier
**festgeschrieben**, das Gespräch selbst bleibt in der zurückrollbaren Sitzung.

Bug-Formen, gegen die diese Wächter stehen:
(a) die KI führt aus, ohne dass jemand es sagt; (b) ein Handgriff läuft zweimal;
(c) er überschreibt, was sich seit der Vorbereitung änderte; (d) er kann mehr als die Person;
(e) ein Gespräch ist für andere sichtbar; (f) was aufeinander aufbaut, bekommt die Nummer nicht;
(g) fällt die KI aus, ist die Eingabe weg; (h) ein Handgriff aus einer Mail zählt nirgends;
(i) das Angeheftete fragt die KI bei jedem Öffnen.
"""

import json
import random

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.actor import act
from app.core.auth import ACTING, get_current_user
from app.core.database import AMBIENT, get_db
from app.main import app
from app.models import Message, UserProfile
from app.services import ai, handgriff, log, pins, talk, todo
from tests import factories
from tests.runner import session
from tests.test_ai_core import _Block, _Script, _answer, _ready


# ─── Hilfen ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def house():
    """Admin, Mitarbeiterin, eine Firma – festgeschrieben (ein Handgriff läuft in eigener
    Sitzung und muss sie sehen)."""
    s = session()
    boss = factories.new_person(s, "admin")
    staff = factories.new_person(s, "employee")
    firm = factories.new_firm(s)
    s.commit()
    yield boss, staff, firm
    s.close()


class _Api:
    """Die echten Routen auf der Testsitzung; wer handelt, setzt die Anmeldung."""

    def __init__(self, db):
        self.db, self.user = db, None
        db.commit = db.flush        # Hintergrundarbeit (Aufnahmen) speichert je Einheit – hier nicht
        app.dependency_overrides[get_db] = self._session
        app.dependency_overrides[get_current_user] = self._who
        self.client = TestClient(app)

    def _session(self):
        """Die Testsitzung – ausser in einem Handgriff: der läuft in seiner eigenen Sitzung
        (``AMBIENT``), wie im Betrieb."""
        yield AMBIENT.get() or self.db

    def _who(self):
        acting = ACTING.get()
        if acting is not None:                  # ein Handgriff: die Person, für die er läuft
            return acting
        act(self.db, "person", self.user.object_id, "ui")
        return self.db.query(UserProfile).filter(UserProfile.id == self.user.id).one()

    def as_(self, user):
        self.user = user
        return self.client


@pytest.fixture
def api(db):
    a = _Api(db)
    yield a
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _tool(name, i, **kw):
    return _Block(type="tool_use", id=f"t{i}", name=name, input=kw)


def _prepare(i, key, path, body, line, wait=()):
    return _tool("vorbereiten", i, handlung=key, pfad=path, werte_json=json.dumps(body),
                 zeile=line, wartet_auf=list(wait))


def _turns(*calls, say="Erledigt."):
    """Eine KI, die je Zug ein Werkzeug ruft und dann antwortet."""
    steps = [_answer(stop="tool_use", content=[c]) for c in calls]
    return _Script(*steps, _answer(parsed=talk.Answer(text=say)))


def _note(about, body="Kran 3 quietscht"):
    return {"channel": "note", "about": [about], "subject": "Kran 3", "body": body}


def _say(api, who, text, **kw):
    r = api.as_(who).post("/api/v1/erp/assistant/talks", json={"text": text, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# ─── Gespräch und Handgriff ────────────────────────────────────────────────────────────

def test_the_ai_prepares_and_only_the_person_executes(db, api, house, monkeypatch):
    """(a) Die KI bereitet vor – geschrieben ist danach nichts; erst «Ausführen» legt die Notiz
    ab. (b) Ein zweites Ausführen ist 409."""
    _boss, staff, firm = house
    body = f"Kran 3 quietscht ({random.randint(1, 10**9)})"
    _ready(monkeypatch, _turns(_prepare(1, "POST /api/v1/erp/messages", "/api/v1/erp/messages",
                                        _note(firm.object_id, body), f"Notiz an {firm.object_id}")))
    t = _say(api, staff, "Bei Muster quietscht Kran 3.", hint_object_id=firm.object_id)
    (h,) = t["handgriffe"]
    assert h["state"] == "open" and h["object_id"] == firm.object_id and t["open"]
    assert t["messages"][-1]["by"] == "ai"
    assert db.query(Message).filter(Message.body == body).count() == 0, "(a)"
    r = api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run", json={})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(Message).filter(Message.id == r.json()["data"]["id"]).one().channel == "note"
    again = api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run", json={})
    assert again.status_code == 409, "(b)"
    assert talk.view(db, t["id"]).open is False


def test_what_builds_on_another_waits_and_then_gets_its_number(db, api, house, monkeypatch):
    """(f) Firma anlegen, dann eine Notiz an genau diese Firma: die Notiz wartet, und nach dem
    Ausführen der Firma trägt sie deren Nummer."""
    boss, _staff, _firm = house
    name = f"Neu {random.randint(1, 10**9)}"
    first = _prepare(1, "POST /api/v1/admin/companies", "/api/v1/admin/companies",
                     {"company_name": name, "legal_form": "AG"}, f"Firma {name} anlegen")
    _ready(monkeypatch, _turns(first))
    t = _say(api, boss, f"Lege {name} an.")
    (a,) = t["handgriffe"]
    second = _prepare(2, "POST /api/v1/erp/messages", "/api/v1/erp/messages",
                      {"channel": "note", "about": [{"$handgriff": a["id"]}], "subject": "Neu",
                       "body": "Kontakt über die Messe."}, "Notiz an die neue Firma", wait=[a["id"]])
    _ready(monkeypatch, _turns(second))
    t = _say(api, boss, "Und notiere: Kontakt über die Messe.", talk=t["id"])
    b = next(h for h in t["handgriffe"] if h["id"] != a["id"])
    assert b["state"] == "waiting" and b["waits_for"] == [a["id"]]
    blocked = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{b['id']}/run", json={})
    assert blocked.status_code == 409 and "Wartet" in blocked.json()["detail"]
    made = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{a['id']}/run", json={}).json()
    firm_nr = made["handgriff"]["result"]
    assert firm_nr
    note = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{b['id']}/run", json={})
    assert note.status_code == 200, note.text
    db.expire_all()
    from app.models import MessageParty
    about = db.query(MessageParty).filter(MessageParty.message_id == note.json()["data"]["id"],
                                          MessageParty.role == "about").one()
    assert about.object_id == firm_nr


def test_what_changed_since_it_was_prepared_is_not_overwritten(db, api, house, monkeypatch):
    """(c) Telefon alt → neu vorbereitet; jemand ändert die Person dazwischen – Ausführen weist
    ab und nennt die Änderung. Mit bewusst geänderten Werten geht es."""
    boss, staff, _firm = house
    path = f"/api/v1/erp/records/{staff.object_id}"
    _ready(monkeypatch, _turns(_prepare(1, "PATCH /api/v1/erp/records/{object_id}", path,
                                        {"phone": "+41 52 111 11 11"}, "Telefon neu")))
    (h,) = _say(api, boss, "Neue Nummer.", hint_object_id=staff.object_id)["handgriffe"]
    other = session()
    p = other.query(UserProfile).filter(UserProfile.id == staff.id).one()
    act(other, "person", boss.object_id, "ui")
    p.first_name = "Geändert"
    other.commit()
    other.close()
    r = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run", json={})
    assert r.status_code == 409 and "Seit der Vorbereitung geändert" in r.json()["detail"], "(c)"
    r = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run",
                           json={"body": {"phone": "+41 52 222 22 22"}})
    assert r.status_code == 200, r.text


def test_the_ai_cannot_prepare_what_the_person_may_not_do(db, api, house, monkeypatch):
    """(d) Eine Mitarbeiterin – die Änderung einer Person darf nur ein Admin: der Probelauf weist
    ab, es entsteht kein Handgriff, und die KI erfährt den Grund."""
    boss, staff, _firm = house
    script = _turns(_prepare(1, "PATCH /api/v1/erp/records/{object_id}",
                             f"/api/v1/erp/records/{boss.object_id}", {"phone": "1"}, "x"))
    _ready(monkeypatch, script)
    t = _say(api, staff, "Ändere die Nummer vom Chef.")
    assert t["handgriffe"] == []
    result = script.seen[1]["messages"][-1]["content"][0]["content"]
    assert result.startswith("Geht nicht (403)"), "(d)"


def test_a_conversation_is_private(db, api, house, monkeypatch):
    """(e) Ein Gespräch und seine Handgriffe sieht nur, wer es führt (und der Admin)."""
    boss, staff, firm = house
    other = factories.new_person(db, "employee")
    _ready(monkeypatch, _turns(_prepare(1, "POST /api/v1/erp/messages", "/api/v1/erp/messages",
                                        _note(firm.object_id), "Notiz")))
    t = _say(api, staff, "Privat.")
    hid = t["handgriffe"][0]["id"]
    assert api.as_(other).get(f"/api/v1/erp/assistant/talks/{t['id']}").status_code == 404
    assert api.as_(other).post(f"/api/v1/erp/assistant/handgriffe/{hid}/drop").status_code == 404
    assert api.as_(boss).get(f"/api/v1/erp/assistant/talks/{t['id']}").status_code == 200
    assert pins.pinned(db, firm.object_id, other).handgriffe == []
    assert [h.id for h in pins.pinned(db, firm.object_id, staff).handgriffe] == [hid]


def test_without_the_ai_the_words_stay_and_the_tick_answers_later(db, api, house, monkeypatch):
    """(g) KI aus: die Nachricht steht, das Gespräch wartet und sagt warum; der Takt antwortet
    nach."""
    _boss, staff, _firm = house
    monkeypatch.setattr(ai, "ready", lambda: False)
    t = _say(api, staff, "Wichtig: Lieferung kommt Dienstag.")
    assert t["waiting"] and t["problem"] and t["messages"][0]["text"].startswith("Wichtig")
    assert t["id"] in talk.open_ids(db, staff)
    _ready(monkeypatch, _turns(say="Notiert."))
    monkeypatch.setattr(talk, "_WAITING", talk.text(
        "SELECT :t AS id WHERE :days > 0 AND :tries > 0 AND :n > 0").bindparams(t=t["id"]))
    import time
    assert talk.catch_up(db, time.monotonic() + 30) == 1
    assert talk.view(db, t["id"]).messages[-1].text == "Notiert."


def test_drop_and_the_conversation_closes(db, api, house, monkeypatch):
    _boss, staff, firm = house
    _ready(monkeypatch, _turns(_prepare(1, "POST /api/v1/erp/messages", "/api/v1/erp/messages",
                                        _note(firm.object_id), "Notiz")))
    t = _say(api, staff, "Notiere.")
    hid = t["handgriffe"][0]["id"]
    assert api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{hid}/drop").status_code == 200
    assert t["id"] not in talk.open_ids(db, staff)
    assert api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{hid}/run", json={}).status_code == 409


def test_a_handgriff_from_a_mail_counts_at_its_record(db, house):
    """(h) Aus einer Mail vorbereitet: am Datensatz in «zu tun», für jedes Personal sichtbar."""
    boss, staff, firm = house
    msg = Message(sender_object_id=firm.object_id, channel="note", subject="Mail", body="x")
    db.add(msg)
    db.flush()
    hid, out = handgriff.prepare(db, boss, method="POST", path="/api/v1/erp/messages",
                                 body=_note(firm.object_id), line="Notiz", home=firm.object_id,
                                 mail=msg.id)
    assert hid and out.ok
    counted = {t.object_id: t for t in todo.todo(db, staff)}
    assert any(i.section == "handgriffe" for i in counted[firm.object_id].items)
    assert [h.id for h in pins.pinned(db, firm.object_id, staff).handgriffe] == [hid]


def test_the_pinned_knowledge_asks_the_ai_only_after_a_change(db, house, monkeypatch):
    """(i) Zweimal öffnen ohne Änderung: ein Aufruf der KI. Ändert sich etwas am Datensatz, wählt
    sie neu."""
    boss, _staff, firm = house
    script = _Script(_answer(parsed=pins.PinAnswer(items=[])), _answer(parsed=pins.PinAnswer(items=[])))
    _ready(monkeypatch, script)
    assert pins.pinned(db, firm.object_id, boss).stale
    pins.refresh(db, firm.object_id, boss)
    assert not pins.pinned(db, firm.object_id, boss).stale
    pins.refresh(db, firm.object_id, boss)
    assert len(script.seen) == 1, "(i) ohne Änderung keine zweite Frage"
    act(db, "person", boss.object_id, "ui")
    log.event(db, "test.change", firm.object_id, {})
    assert pins.pinned(db, firm.object_id, boss).stale
    pins.refresh(db, firm.object_id, boss)
    assert len(script.seen) == 2


def test_a_handgriff_needing_the_hand_is_opened_not_run(db, house):
    """Ein Dokument mit Datei geht nur von Hand – der Handgriff entsteht, Ausführen weist ab,
    «von Hand erledigt» schliesst ihn."""
    boss, _staff, firm = house
    hid, out = handgriff.prepare(db, boss, method="POST", path="/api/v1/erp/documents",
                                 body={"art": "Lieferschein", "name": "LS 1"}, line="Dokument",
                                 home=firm.object_id, talk=None)
    assert hid and out.ok
    (h,) = handgriff.view(db, handgriff.load(db, [hid]))
    assert h.hand
    with pytest.raises(HTTPException) as e:
        handgriff.run(db, boss, hid)
    assert e.value.status_code == 409
    assert handgriff.settle(db, boss, hid, None).done is not None
