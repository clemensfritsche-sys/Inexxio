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
from contextlib import nullcontext

import pytest
from app.domain.errors import Rejected
from fastapi.testclient import TestClient

from app.core.actor import act
from app.core.auth import ACTING, get_current_user
from app.core.database import AMBIENT, get_db
from app.main import app
from app.models import Log, Message, UserProfile
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
        talk.OWN_SESSION = lambda: nullcontext(db)     # die Antwort sieht die Testsitzung
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
    talk.OWN_SESSION = talk._own_session


def _tool(name, i, **kw):
    return _Block(type="tool_use", id=f"t{i}", name=name, input=kw)


def _prepare(i, key, path, body, line, wait=()):
    return _tool("vorbereiten", i, handlung=key, pfad=path, werte_json=json.dumps(body),
                 zeile=line, wartet_auf=list(wait))


def _turns(*calls, say="Erledigt."):
    """Eine KI, die je Zug ein Werkzeug ruft und dann antwortet."""
    steps = [_answer(stop="tool_use", content=[c]) for c in calls]
    return _Script(*steps, _answer(content=[_Block(type="text", text=say)]))


def _note(about, body="Kran 3 quietscht"):
    return {"channel": "note", "about": [about], "subject": "Kran 3", "body": body}


def _lines(r):
    """Der Stream: je Zeile ein JSON (Leerzeilen sind Lebenszeichen)."""
    assert r.status_code == 200, r.text
    return [json.loads(x) for x in r.text.splitlines() if x.strip()]


def _say(api, who, text, **kw):
    """Sagen – und das Gespräch, wie es am Ende des Streams steht."""
    lines = _lines(api.as_(who).post("/api/v1/erp/assistant/talks", json={"text": text, **kw}))
    assert "talk" in lines[-1], lines
    return lines[-1]["talk"]


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
    r = api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run")
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(Message).filter(Message.id == r.json()["data"]["id"]).one().channel == "note"
    again = api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run")
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
    blocked = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{b['id']}/run")
    assert blocked.status_code == 409 and "Wartet" in blocked.json()["detail"]
    made = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{a['id']}/run").json()
    firm_nr = made["handgriff"]["result"]
    assert firm_nr
    note = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{b['id']}/run")
    assert note.status_code == 200, note.text
    db.expire_all()
    from app.models import MessageParty
    about = db.query(MessageParty).filter(MessageParty.message_id == note.json()["data"]["id"],
                                          MessageParty.role == "about").one()
    assert about.object_id == firm_nr


def test_a_change_shows_old_and_new_as_it_is_now(db, api, house, monkeypatch):
    """(c) Telefon alt → neu vorbereitet: der Vorschlag zeigt am Datensatz, was er ändert – «alt»
    aus derselben Route, **wie es jetzt ist**. Ändert jemand dazwischen, zeigt er den neuen Stand,
    und «Übernehmen» tut genau das Gezeigte (Bug-Form: «alt» eingefroren, still überschrieben)."""
    boss, staff, _firm = house
    path = f"/api/v1/erp/records/{staff.object_id}"
    _ready(monkeypatch, _turns(_prepare(1, "PATCH /api/v1/erp/records/{object_id}", path,
                                        {"phone": "+41 52 111 11 11"}, "Telefon neu")))
    (h,) = _say(api, boss, "Neue Nummer.", hint_object_id=staff.object_id)["handgriffe"]
    (change,) = h["changes"]
    assert change["field"] == "phone" and change["after"] == "+41 52 111 11 11"
    other = session()
    p = other.query(UserProfile).filter(UserProfile.id == staff.id).one()
    act(other, "person", boss.object_id, "ui")
    p.phone = "+41 52 999 99 99"
    other.commit()
    other.close()
    (seen,) = api.as_(boss).get(f"/api/v1/erp/assistant/handgriffe/{h['id']}").json()["changes"]
    assert seen["before"] == "+41 52 999 99 99", "(c) wie es jetzt ist"
    r = api.as_(boss).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run")
    assert r.status_code == 200, r.text
    db.expire_all()
    assert "111 11 11" in db.query(UserProfile).filter(UserProfile.id == staff.id).one().phone


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
    assert api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{hid}/run").status_code == 409


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
    from datetime import timedelta
    monkeypatch.setattr(pins, "QUIET", timedelta(0))      # die Ruhezeit prüft der nächste Test
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


def test_a_document_is_made_in_its_draft(db, house):
    """Ein Dokument braucht seine Datei – der Vorschlag entsteht ohne Probelauf (die Datei kommt
    mit dem Entwurf); «im Entwurf erledigt» schliesst ihn, und er nennt, was entstand."""
    boss, _staff, firm = house
    hid, out = handgriff.prepare(db, boss, method="POST", path="/api/v1/erp/documents",
                                 body={"art": "Lieferschein", "name": "LS 1"}, line="Dokument",
                                 home=firm.object_id, talk=None)
    assert hid and out.ok
    done = handgriff.settle(db, boss, hid, 100000123)
    assert done.done is not None and done.done["result"] == 100000123
    with pytest.raises(Rejected):
        handgriff.settle(db, boss, hid, None)


def test_while_someone_types_the_knowledge_is_chosen_at_most_once_in_a_while(db, house, monkeypatch):
    """Auto-Save ändert alle paar Sekunden etwas – die KI wählt trotzdem nur einmal je ``QUIET``
    (Bug-Form: jeder Tastendruck kostet einen Aufruf und frisst den Deckel)."""
    boss, _staff, firm = house
    script = _Script(_answer(parsed=pins.PinAnswer(items=[])), _answer(parsed=pins.PinAnswer(items=[])))
    _ready(monkeypatch, script)
    pins.refresh(db, firm.object_id, boss)
    act(db, "person", boss.object_id, "ui")
    log.event(db, "test.change", firm.object_id, {})
    pins.refresh(db, firm.object_id, boss)
    assert len(script.seen) == 1


def test_the_ai_never_executes(db, house):
    """Die KI bereitet vor, ausführen tut nur die Person – im Gespräch, aus Mails und über MCP
    gibt es kein Werkzeug dafür (Bug-Form: «ausführen auf ein Wort» kommt zurück)."""
    from app.services import follow, mcp
    boss, staff, firm = house
    names = {t.name for t in talk.tools(db, staff, 1, firm.object_id)}
    names |= {t.name for t in mcp.tools(db, staff, 1)}
    msg = Message(sender_object_id=firm.object_id, channel="note", subject="Mail", body="x")
    db.add(msg)
    db.flush()
    names |= {t.name for t in follow._tools(db, msg, boss, staff)}
    assert "vorbereiten" in names
    assert not {n for n in names if "ausf" in n or n in ("run", "execute")}


def test_a_rolled_back_savepoint_keeps_the_mails_of_the_request(db):
    """Nach dem Speichern läuft, was vorher angemeldet war – ein verworfener Sicherungspunkt nimmt
    nur seine eigenen Haken mit (Bug-Form: eine Vorschau im Sicherungspunkt löschte den Versand
    der ganzen Anfrage)."""
    from app.core import outside
    from app.core.database import SessionLocal
    s = SessionLocal()
    ran = []
    try:
        outside.after(s, lambda: ran.append("vorher"))
        sp = s.begin_nested()
        outside.after(s, lambda: ran.append("verworfen"))
        sp.rollback()
        with s.begin_nested():
            outside.after(s, lambda: ran.append("behalten"))
        s.commit()
    finally:
        s.close()
    assert ran == ["vorher", "behalten"]


def test_a_crafted_path_is_no_handgriff():
    """Punkt-Teile, Abfrage, Kodierung: nach dem Normalisieren träfe der Pfad eine andere Route
    als die geprüfte – keine Handlung."""
    for path in ("/api/v1/erp/messages/../assistant/talks", "/api/v1/erp/messages?x=1",
                 "/api/v1/erp/records/%2e%2e/1", "/api/v1/erp//messages"):
        assert handgriff.operation_for("POST", path) is None, path
    assert handgriff.operation_for("POST", "/api/v1/erp/messages") is not None


# ─── Feinschliff: unvollständig, lesen, live, Stopp ─────────────────────────────────────

def test_missing_values_make_a_card_that_waits_for_the_person(db, api, house, monkeypatch):
    """Fehlen nur Werte (die Route sagt 400/422), wird es trotzdem ein Vorschlag – die Person
    ergänzt sie im Entwurf; «Übernehmen» ohne sie sagt den Satz der Route. Was sie nicht darf,
    wird nie einer (``test_the_ai_cannot_prepare_what_the_person_may_not_do``)."""
    _boss, staff, _firm = house
    script = _turns(_prepare(1, "POST /api/v1/erp/articles", "/api/v1/erp/articles",
                             {"name": "ERP"}, "Artikel «ERP» anlegen"))
    _ready(monkeypatch, script)
    t = _say(api, staff, "Leg den Artikel ERP an.")
    (h,) = t["handgriffe"]
    assert h["state"] == "open"
    result = script.seen[1]["messages"][-1]["content"][0]["content"]
    assert "unvollständig" in result
    r = api.as_(staff).post(f"/api/v1/erp/assistant/handgriffe/{h['id']}/run")
    assert r.status_code == 400 and "Abmessungen" in r.json()["detail"]   # der Satz der Route


def test_the_ai_reads_what_every_staff_member_sees(db, house):
    """«abrufen»: jede lesende Route des Personals, durch die echte Route – nichts, was nur ein
    Admin sieht, und keine schreibende."""
    out = handgriff.look("/api/v1/erp/orders/module-catalog")
    assert out.ok and out.data, out.detail
    assert not handgriff.look("/api/v1/admin/territories").ok          # nur Admin
    assert not handgriff.look("/api/v1/erp/messages").ok               # schreibt
    keys = {o.key for o in handgriff.reads()}
    assert "GET /api/v1/erp/orders/module-catalog" in keys
    assert not any(k.startswith("GET /api/v1/erp/assistant") for k in keys)


def test_the_answer_streams_its_steps(db, api, house, monkeypatch):
    """Live wie bei Claude: je Schritt eine Zeile, am Ende das Gespräch; jeder Zug im Log mit
    seiner Dauer."""
    _boss, staff, firm = house
    _ready(monkeypatch, _turns(_prepare(1, "POST /api/v1/erp/messages", "/api/v1/erp/messages",
                                        _note(firm.object_id), "Notiz an die Firma")))
    lines = _lines(api.as_(staff).post("/api/v1/erp/assistant/talks", json={"text": "Notiz bitte."}))
    assert {"step": "bereitet vor: Notiz an die Firma"} in lines
    assert {"text": "Erledigt."} in lines                                 # Wort für Wort
    assert lines[-1]["talk"]["messages"][-1] | {"text": "Erledigt."} == lines[-1]["talk"]["messages"][-1]
    calls = db.query(Log).filter(Log.event == "ai.call").order_by(Log.id.desc()).limit(2).all()
    assert all("ms" in c.payload for c in calls)


def test_stop_halts_before_the_next_step(db, house, monkeypatch):
    """«Stopp»: die KI hält vor ihrem nächsten Schritt an; das Gespräch hat eine Antwort
    («Angehalten.»), der Takt holt nichts nach."""
    _boss, staff, _firm = house
    _ready(monkeypatch, _turns(say="Nie gesagt."))
    tid = talk.say(db, staff, "Mach etwas Langes.")
    talk.stop(db, staff, tid)
    assert talk.answer(db, tid, staff) is None
    t = talk.view(db, tid)
    assert t.messages[-1].text == talk.HALTED and not t.waiting


def test_what_the_ai_replaced_is_not_shown(db, house):
    """Die Person sieht nur das Ergebnis: was die KI selbst weglegte (ersetzt), steht nicht im
    Gespräch; was die Person weglegte, schon (sie hat es entschieden)."""
    _boss, staff, firm = house
    tid = talk.say(db, staff, "Notizen bitte.")
    ids = []
    for i in range(2):
        hid, out = handgriff.prepare(db, staff, method="POST", path="/api/v1/erp/messages",
                                     body=_note(firm.object_id, f"Notiz {i}"), line=f"Notiz {i}",
                                     home=firm.object_id, talk=tid)
        assert hid, out.detail
        ids.append(hid)
    handgriff.drop(db, staff, ids[0], by="ai")
    handgriff.drop(db, staff, ids[1])
    assert [h.id for h in talk.view(db, tid).handgriffe] == [ids[1]]


# ─── Runde 15: schneller, vorab, nur das Ergebnis ──────────────────────────────────────

def test_the_ai_gets_what_it_needs_up_front(db, api, house, monkeypatch):
    """Schnell, weil sie nicht erst nachschlägt: die Liste der Handlungen steht im Auftrag (aus
    den Routen, im Zwischenspeicher), der offene Datensatz im Gespräch – nachschlagen nach
    Stichwörtern gibt es im «+» nicht mehr."""
    _boss, staff, firm = house
    script = _turns()
    _ready(monkeypatch, script)
    _say(api, staff, "Was ist hier los?", hint_object_id=firm.object_id)
    sent = script.seen[0]
    system = sent["system"][0]["text"]
    assert "POST /api/v1/erp/messages" in system and "GET /api/v1/erp/orders/module-catalog" in system
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert firm.company_name in sent["messages"][0]["content"][0]["text"]
    assert "handlungen" not in {t["name"] for t in sent["tools"]}


def test_at_a_glance_is_ready_before_anyone_opens(db, house, monkeypatch):
    """«Auf einen Blick» rechnet der Takt vorab – für einen Datensatz, den jemand öffnete und in
    dessen Umfeld sich seither etwas änderte; danach ist nichts mehr fällig (Bug-Form: es wird
    erst beim Öffnen gerechnet, oder bei jedem Lauf neu)."""
    import time
    boss, _staff, firm = house
    monkeypatch.setattr(pins, "QUIET", pins.timedelta(0))
    script = _Script(_answer(parsed=pins.PinAnswer(items=[])), _answer(parsed=pins.PinAnswer(items=[])))
    _ready(monkeypatch, script)
    monkeypatch.setattr(pins, "_OPENED", talk.text("SELECT :o AS object_id WHERE :days > 0 AND :n > 0")
                        .bindparams(o=firm.object_id))
    pins.refresh(db, firm.object_id, boss)                 # jemand öffnete ihn
    act(db, "person", boss.object_id, "ui")
    log.event(db, "test.change", firm.object_id, {})       # etwas ändert sich
    assert pins.ahead(db, time.monotonic() + 30) == 1
    assert pins.ahead(db, time.monotonic() + 30) == 0      # nichts mehr fällig
    assert len(script.seen) == 2
    assert pins.pinned(db, firm.object_id, boss).stale is False
