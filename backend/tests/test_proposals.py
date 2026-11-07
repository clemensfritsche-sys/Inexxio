"""►►► **Phase 3 · KI – Erfassen, Ablegen, Vorschläge, das Angeheftete.** ◄◄◄

Die drei Beispiele der Akte (§4.3) laufen durch – Montage-Notiz Hans-Peter, Meeting Heiri,
Kundenmail –, dazu die Regeln des Bauplans: Übernehmen = Tippen, selbst getippt erledigt,
✕ verwirft, zwei gleichzeitig, KI aus, Rechte, «neu ansehen», «zu tun».

Die KI wird nachgebildet (``_Script``/``_Block`` wie in ``tests/test_ai_core.py``) – nie ein echter
Aufruf. Jeder Wächter steht neben der Fehlerform, die er fängt.
"""

import random
import re
import time
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.actor import act
from app.core.config import get_settings
from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models import Log, Mailbox, Message, MessageParty
from app.schemas.admin import CompanySettingsUpdate, ErpAdminUpdate
from app.services import (ai, ai_tools, documents as docs, follow, history, intake, log,
                          people, proposals, sites, tick, todo)
from app.services.communication import write
from app.services.intake import AiPart, AiProposal, AiValue, FileAnswer
from app.services.pins import AiHint, PinAnswer
from tests.factories import new_firm, new_person
from tests.test_ai_core import PDF, _Block, _Script, _answer, _ready

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
DETAIL = {"user": FRONTEND / "user-detail.tsx", "organization": FRONTEND / "organization-detail.tsx"}
UPDATE = {"user": ErpAdminUpdate, "organization": CompanySettingsUpdate}


# ─── Hilfen ────────────────────────────────────────────────────────────────────────────

class _Api:
    """Die echten Routen auf derselben Sitzung – ``commit`` bleibt ein ``flush``; wer handelt,
    setzt die Anmeldung (wie ``core/auth``)."""

    def __init__(self, db, monkeypatch):
        self.db, self.user = db, None
        monkeypatch.setattr(db, "commit", db.flush)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = self._who
        self.client = TestClient(app)

    def _who(self):
        act(self.db, "person", self.user.object_id, "ui")
        return self.user

    def as_(self, user):
        self.user = user
        return self.client


@pytest.fixture
def api(db, monkeypatch):
    a = _Api(db, monkeypatch)
    yield a
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _file_answer(parts, props=()):
    return _answer(parsed=FileAnswer(parts=[AiPart(object_id=o, text=t, subject=s) for o, t, s in parts],
                                     proposals=list(props)))


def _change(oid, field, value):
    return AiProposal(kind="change", object_id=oid, field=field, value=value, type=None, values=[])


def _create(oid, typ, **values):
    return AiProposal(kind="create", object_id=oid, field=None, value=None, type=typ,
                      values=[AiValue(key=k, value=v) for k, v in values.items()])


def _events(db, name, **payload):
    rows = db.query(Log).filter(Log.event == name).order_by(Log.id).all()
    return [r for r in rows if all((r.payload or {}).get(k) == v for k, v in payload.items())]


def _type_phone(db, admin, person, value):
    """Ein Admin tippt ins Feld «Telefon» – derselbe Weg wie ``PATCH /erp/records/{nr}``."""
    act(db, "person", admin.object_id, "ui")
    people.apply_profile_update(db, person, ErpAdminUpdate(phone=value), admin.id, staff=True)
    db.flush()


# ─── Der Wächter über die Felder ───────────────────────────────────────────────────────

def test_every_proposable_field_is_a_column_an_update_field_and_a_field_on_screen():
    """Ein Vorschlag am Feld funktioniert nur, wenn (1) das Log die Spalte unter diesem Namen
    zeigt, (2) das ERP sie per PATCH ändert und (3) die Oberfläche ein Feld mit genau diesem
    ``name`` hat. Bug-Form: ein Feld, das keine Spalte ist (``iban`` heisst ``iban_encrypted``)
    – der Vorschlag bliebe für immer offen."""
    for typ, fields in proposals.FIELDS.items():
        columns = {c.name for c in proposals.MODELS[typ].__table__.columns}
        screen = DETAIL[typ].read_text("utf-8")
        for field in fields:
            assert field in columns, f"{typ}.{field} ist keine Spalte"
            assert field in UPDATE[typ].model_fields, f"{typ}.{field} ändert kein PATCH"
            assert re.search(rf'name="{field}"', screen), f"{typ}.{field} steht nicht am Schirm"


# ─── (a) Montage-Notiz Hans-Peter ──────────────────────────────────────────────────────

def _montage(db):
    firm = new_firm(db, "Muster", "AG")
    hans = new_person(db, "employee", first_name="Hans-Peter", last_name="Keller")
    meier = new_person(db, "user", first_name="Urs", last_name="Meier", company=firm.object_id)
    admin = new_person(db, "admin")
    return firm, hans, meier, admin


NOTE = ("Hans-Peter: beim Kunden Muster AG den Hydraulikschlauch am Kran ersetzt, Telefon von "
        "Herrn Meier ist neu 079 123 45 67")


def test_montage_note_files_to_the_firm_and_proposes_the_phone(db, api, monkeypatch):
    """Teil an der Firma, ``change``-Vorschlag Telefon an Herrn Meier; «Stimmt so» legt eine
    Notiz an, Übernehmen = Tippen schliesst den Vorschlag (``accepted``)."""
    firm, hans, meier, admin = _montage(db)
    look = _Block(type="tool_use", id="t1", name="find", input={"q": "Meier"})
    script = _Script(_answer(stop="tool_use", content=[look]), _file_answer(
        [(firm.object_id, "Hydraulikschlauch am Kran ersetzt.", "Hydraulikschlauch ersetzt")],
        [_change(meier.object_id, "phone", "079 123 45 67")]))
    _ready(monkeypatch, script)
    r = api.as_(hans).post("/api/v1/erp/intake", json={"text": NOTE, "hint_object_id": firm.object_id})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["problem"] is None and not got["filed"]
    assert [(p["object_id"], p["subject"]) for p in got["parts"]] == [
        (firm.object_id, "Hydraulikschlauch ersetzt")]
    assert got["parts"][0]["label"] == "Unternehmen · Muster AG"
    (prop,) = got["proposals"]
    assert prop["kind"] == "change" and prop["field"] == "phone" and prop["label"] == "Telefon"
    assert prop["value"] == "+41 79 123 45 67" and prop["current"] is None   # wie das Feld speichert
    assert prop["object_id"] == meier.object_id
    # Die Quelle steht für jedes Personal da – ohne die Worte der Erfassung (die sieht nur Hans).
    assert prop["source"]["text"] == "Erfassung von Hans-Peter Keller"
    assert prop["source"]["intake"] == got["id"]
    # Die rohe Eingabe zuerst, die Vorschläge im Namen der Person durch die KI.
    (raw,) = _events(db, "intake", text=NOTE)
    assert raw.actor_kind == "person" and raw.actor_id == hans.object_id and raw.object_id == firm.object_id
    assert all(p.actor_kind == "ai" and p.actor_id == hans.object_id for p in _events(db, "proposal"))
    assert "Meier" in script.seen[1]["messages"][-1]["content"][0]["content"]    # nachgeschlagen
    assert str(firm.object_id) in script.seen[0]["messages"][0]["content"][0]["text"]

    # Am Feld: der Vorschlag steht an Herrn Meier.
    shown = api.as_(admin).get("/api/v1/erp/proposals", params={"object_id": meier.object_id}).json()
    assert [p["id"] for p in shown] == [prop["id"]]

    # «Stimmt so»: eine Notiz an der Firma, Entscheid «übernommen».
    filed = api.as_(hans).post(f"/api/v1/erp/intake/{got['id']}/file", json={"parts": [
        {"object_id": p["object_id"], "text": p["text"], "subject": p["subject"]} for p in got["parts"]]})
    assert filed.status_code == 200, filed.text
    body = filed.json()
    assert body["filed"] and body["notes"][0]["object_id"] == firm.object_id
    note = db.get(Message, body["notes"][0]["message_id"])
    assert note.channel == "note" and note.subject == "Hydraulikschlauch ersetzt"
    about = db.query(MessageParty).filter(MessageParty.message_id == note.id,
                                          MessageParty.role == "about").one()
    assert about.object_id == firm.object_id
    assert _events(db, "proposal.decided")[-1].payload["outcome"] == "accepted"
    assert api.as_(hans).get("/api/v1/erp/intake/open").json() == []

    # Übernehmen = Tippen: derselbe PATCH wie von Hand → zu, Entscheid «übernommen».
    _type_phone(db, admin, meier, prop["value"])
    assert proposals.open_for(db, meier.object_id, admin) == []
    p = proposals.get(db, prop["id"])
    assert proposals.outcome(db, p) == ("accepted", "+41 79 123 45 67")
    act(db, "system", None, "job")                          # der Takt
    assert proposals.settle(db) >= 1 and proposals.settle(db) == 0       # einmal je Vorschlag
    (decided,) = _events(db, "proposal.decided", proposal=prop["id"])
    assert decided.payload["outcome"] == "accepted" and decided.actor_kind == "system"


def test_typed_differently_is_changed_and_x_is_rejected(db, api):
    """Selbst anders getippt erledigt ihn (``changed``, mit dem Wert, den der Mensch nahm); ✕
    verwirft – zweimal ✕ ist ein Fehler, kein zweiter Entscheid."""
    firm, hans, meier, admin = _montage(db)
    src = {"text": "Notiz"}
    a = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                          value="079 111 11 11", source=src, actor=hans.object_id)
    b = proposals.propose(db, object_id=meier.object_id, kind="change", field="last_name",
                          value="Meier-Huber", source=src, actor=hans.object_id)
    _type_phone(db, admin, meier, "079 222 22 22")
    assert proposals.outcome(db, proposals.get(db, a)) == ("changed", "+41 79 222 22 22")
    r = api.as_(admin).post(f"/api/v1/erp/proposals/{b}/reject")
    assert r.status_code == 200 and r.json()["label"] == "Nachname"
    assert proposals.outcome(db, proposals.get(db, b)) == ("rejected", None)
    again = api.as_(admin).post(f"/api/v1/erp/proposals/{b}/reject")
    assert again.status_code == 409 and f"«{b}»" in again.json()["detail"]
    assert proposals.open_for(db, meier.object_id, admin) == []


def test_two_at_once_both_stand_in_the_log_and_both_are_decided(db):
    """Zwei Vorschläge fürs selbe Feld gleichzeitig: beide im Log, beide offen; das Tippen
    entscheidet beide – den einen «übernommen», den anderen «selbst geändert». Ein Zwilling
    (gleiches Feld, gleicher Wert) ist kein dritter."""
    firm, hans, meier, admin = _montage(db)
    src = {"text": "x"}
    a = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                          value="079 333 33 33", source=src, actor=hans.object_id)
    b = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                          value="079 444 44 44", source=src, actor=hans.object_id)
    twin = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                             value="+41 79 444 44 44", source=src, actor=hans.object_id)
    assert a != b and twin == b
    assert len(_events(db, "proposal")) >= 2
    assert {p.id for p in proposals.open_for(db, meier.object_id, admin)} == {a, b}
    _type_phone(db, admin, meier, "079 444 44 44")
    proposals.settle(db)
    assert _events(db, "proposal.decided", proposal=a)[0].payload["outcome"] == "changed"
    assert _events(db, "proposal.decided", proposal=b)[0].payload["outcome"] == "accepted"


def test_what_is_no_proposal(db):
    """Bug-Form: die KI schlägt ein Feld vor, das es nicht gibt, einen Wert, der schon steht,
    oder an einer fremden Firma ein Telefon – der Code verwirft es, und ``problem`` sagt warum."""
    firm, hans, meier, admin = _montage(db)
    meier.phone = "+41 79 555 55 55"
    db.flush()
    cases = [
        (meier.object_id, "email", "neu@x.ch", "lässt sich"),
        (meier.object_id, "phone", "079 555 55 55", "ist schon"),
        (meier.object_id, "date_of_birth", "kein Datum", "passt nicht"),
        (firm.object_id, "phone", "044 000 00 00", "fremden Firma"),
        (firm.object_id, "uid_number", "CHE-123", "passt nicht"),
        (999_999_998, "phone", "1", "gibt es nicht"),
    ]
    for oid, field, value, why in cases:
        trouble = proposals.problem(db, object_id=oid, kind="change", field=field, value=value)
        assert trouble and why in trouble, (field, trouble)
        assert proposals.propose(db, object_id=oid, kind="change", field=field, value=value,
                                 source={"text": "x"}, actor=hans.object_id) is None
    ok = proposals.propose(db, object_id=meier.object_id, kind="change", field="date_of_birth",
                           value="3.5.1980", source={"text": "x"}, actor=hans.object_id)
    assert proposals.get(db, ok).payload["value"] == "1980-05-03"


def test_the_record_is_gone(db):
    firm, hans, meier, admin = _montage(db)
    pid = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                            value="079 666 66 66", source={"text": "x"}, actor=hans.object_id)
    meier.is_active = False
    db.flush()
    assert proposals.outcome(db, proposals.get(db, pid)) == ("gone", None)


def test_a_create_proposal_closes_when_the_record_is_made(db):
    """«Entwurf öffnen» → Freigabe legt die Person an → der Vorschlag ist zu (``accepted``).
    Eine Person, die es schon gibt, schlägt niemand ein zweites Mal vor."""
    firm, hans, meier, admin = _montage(db)
    pid = proposals.propose(db, object_id=firm.object_id, kind="create",
                            draft={"type": "user", "values": {"first_name": "Rita",
                                                              "last_name": "Roth",
                                                              "email": "rita@muster.ch",
                                                              "iban": "nie"}},
                            source={"text": "x"}, actor=hans.object_id)
    p = proposals.get(db, pid)
    assert p.payload["draft"]["values"] == {"first_name": "Rita", "last_name": "Roth",
                                            "email": "rita@muster.ch"}
    assert proposals.outcome(db, p) is None
    people.ensure(db, "rita@muster.ch", "Rita Roth")
    db.flush()
    assert proposals.outcome(db, p)[0] == "accepted"
    assert proposals.propose(db, object_id=firm.object_id, kind="create",
                             draft={"type": "user", "values": {"email": meier.email}},
                             source={"text": "x"}, actor=hans.object_id) is None


# ─── (b) Meeting Heiri ─────────────────────────────────────────────────────────────────

MEETING = ("Meeting mit Heiri: 1) Muster AG will die Wartung der Krananlage im März. "
           "2) Beta GmbH reklamiert die Rechnung. 3) Heiri geht im Juni in die Ferien.")


def test_a_meeting_is_split_into_parts_with_their_own_home(db, api, monkeypatch):
    """Mehrere Themen → mehrere Teile mit je eigener Heimat; eine erfundene Nummer verwirft der
    Code. Ändert der Mensch einen Teil, ist der Entscheid «selbst geändert»."""
    muster, beta = new_firm(db, "Muster"), new_firm(db, "Beta", "GmbH")
    heiri = new_person(db, "employee", first_name="Heiri", last_name="Gut")
    me = new_person(db, "employee")
    _ready(monkeypatch, _Script(_file_answer([
        (muster.object_id, "Will die Wartung der Krananlage im März.", "Wartung Krananlage März"),
        (beta.object_id, "Reklamiert die Rechnung.", "Reklamation Rechnung"),
        (heiri.object_id, "Ferien im Juni.", "Ferien Juni"),
        (999_999_997, "erfunden", "x")])))
    got = api.as_(me).post("/api/v1/erp/intake", json={"text": MEETING}).json()
    homes = [p["object_id"] for p in got["parts"]]
    assert homes == [muster.object_id, beta.object_id, heiri.object_id]
    assert api.as_(me).get("/api/v1/erp/intake/open").json()[0]["id"] == got["id"]
    parts = [{"object_id": p["object_id"], "text": p["text"], "subject": p["subject"]}
             for p in got["parts"]]
    parts[2]["object_id"] = me.object_id                     # anderer Datensatz angetippt
    body = api.as_(me).post(f"/api/v1/erp/intake/{got['id']}/file", json={"parts": parts}).json()
    assert body["filed"] and [n["object_id"] for n in body["notes"]] == [
        muster.object_id, beta.object_id, me.object_id]
    assert [p["object_id"] for p in body["parts"]] == [muster.object_id, beta.object_id, me.object_id]
    decided = _events(db, "proposal.decided")[-1]
    assert decided.payload["outcome"] == "changed" and decided.payload["parts"][2]["object_id"] == me.object_id
    again = api.as_(me).post(f"/api/v1/erp/intake/{got['id']}/file", json={"parts": parts})
    assert again.status_code == 409


# ─── (c) Kundenmail ────────────────────────────────────────────────────────────────────

def _mail(db, customer, own, body, subject="Neue Adresse", at=None):
    msg = Message(sender_object_id=customer.object_id, channel=f"c{own.object_id}", subject=subject,
                  body=body, at=at or datetime.now(timezone.utc), created_by=None,
                  gmail_id=f"g{time.time()}")
    write(db, msg, {"to": [], "cc": [], "bcc": [], "about": []})
    return msg


def test_a_customer_mail_with_a_new_phone_in_the_signature_becomes_a_proposal(db, monkeypatch):
    """Nur Mails nach dem ersten Lauf, von einer bekannten Person, je Mail einmal; die Mail ist
    die Quelle. Bug-Form: eine Mail wird zweimal geprüft, oder eine ältere Mail kommt dran."""
    own = new_firm(db, "Inexxio", own=True)
    staff = new_person(db, "admin")
    db.add(Mailbox(channel=f"c{own.object_id}", address="info@inexxio.test",
                   owner_object_id=staff.object_id, token="x"))
    customer = new_person(db, "user", first_name="Vreni", last_name="Kunz")
    customer.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    db.flush()
    monkeypatch.setattr(db, "commit", db.flush)
    if follow.start(db) is None:
        follow.due(db)                                       # der erste Lauf merkt den Start
    other = _mail(db, customer, own, "Danke für die Lieferung.", subject="Lieferung")
    assert other.id > follow.start(db)                       # nach dem Start: kommt dran
    sig = ("Guten Tag, anbei die Bestellung.\n\nFreundliche Grüsse\nVreni Kunz\n"
           "Tel. 079 777 77 77")
    mail = _mail(db, customer, own, sig)
    script = _Script(_answer(parsed=follow.FollowAnswer(proposals=[])),
                     _answer(parsed=follow.FollowAnswer(proposals=[
                         _change(customer.object_id, "phone", "079 777 77 77")])))
    _ready(monkeypatch, script)
    mails, made = follow.run(db, time.monotonic() + 30)
    assert (mails, made) == (2, 1)
    (prop,) = [p for p in proposals.open_for(db, customer.object_id, staff) if p.field == "phone"]
    assert prop.value == "+41 79 777 77 77" and prop.source.object_id == customer.object_id
    assert proposals.get(db, prop.id).source["message_id"] == mail.id
    assert len(_events(db, "mail.followed", message=mail.id)) == 1
    assert follow.run(db, time.monotonic() + 30) == (0, 0)   # je Mail einmal
    assert len(script.seen) == 2


def test_a_new_sender_staff_and_old_mails_are_not_followed(db, monkeypatch):
    own = new_firm(db, "Inexxio", own=True)
    staff = new_person(db, "admin")
    db.add(Mailbox(channel=f"c{own.object_id}", address="info2@inexxio.test",
                   owner_object_id=staff.object_id, token="x"))
    old_customer = new_person(db, "user")
    old_customer.created_at = datetime.now(timezone.utc) - timedelta(days=3)
    db.flush()
    if follow.start(db) is None:
        old = _mail(db, old_customer, own, "vor der Einführung")
        follow.due(db)
        assert old.id not in follow.due(db)
    fresh = new_person(db, "user")                           # erst beim Abgleich entstanden
    colleague = new_person(db, "employee")
    a = _mail(db, fresh, own, "Hallo", at=fresh.created_at - timedelta(minutes=3))
    b = _mail(db, colleague, own, "intern")
    assert not {a.id, b.id} & set(follow.due(db, 100))


# ─── KI aus ────────────────────────────────────────────────────────────────────────────

def test_without_ai_the_input_stays_raw_and_the_tick_catches_up(db, api, monkeypatch):
    """Ohne Schlüssel: ein roher Teil (der ganze Text an der Person), ``problem`` sagt warum, die
    rohe Eingabe steht im Log. Der Takt holt nach – im Namen der Person, die erfasst hat."""
    me = new_person(db, "employee")
    firm = new_firm(db, "Gamma")
    monkeypatch.setattr(ai, "ready", lambda: False)
    got = api.as_(me).post("/api/v1/erp/intake", json={"text": "Gamma ruft morgen zurück"}).json()
    assert got["problem"] == "Kein KI-Schlüssel hinterlegt."
    assert [(p["object_id"], p["text"]) for p in got["parts"]] == [(me.object_id, "Gamma ruft morgen zurück")]
    assert got["id"] in intake.waiting(db, 1000)
    assert api.as_(me).get("/api/v1/erp/intake/open").json()[0]["problem"] == intake.WAITING
    # Der Takt am Deckel bzw. ohne KI: nur, was keine KI braucht.
    assert tick._ai(db, time.monotonic() + 30).get("filed") is None
    script = _Script(_file_answer([(firm.object_id, "Ruft morgen zurück.", "Rückruf")]))
    _ready(monkeypatch, script)
    monkeypatch.setattr(intake, "waiting", lambda db, limit=3: [got["id"]])
    done = tick._ai(db, time.monotonic() + 30)
    assert done["filed"] == 1
    (fp,) = proposals.of_intake(db, got["id"], "file")
    assert fp.actor_id == me.object_id and fp.payload["parts"][0]["object_id"] == firm.object_id
    assert api.as_(me).get("/api/v1/erp/intake/open").json()[0]["parts"][0]["object_id"] == firm.object_id


def test_by_hand_without_ai_is_still_a_case(db, api, monkeypatch):
    """Von Hand abgelegt, ohne dass die KI je vorschlug: der rohe Teil wird der Vorschlag, über
    den entschieden ist – auch diese Erfassung ist ein Fall."""
    me = new_person(db, "employee")
    monkeypatch.setattr(ai, "ready", lambda: False)
    got = api.as_(me).post("/api/v1/erp/intake", json={"text": "Kurz notiert"}).json()
    body = api.as_(me).post(f"/api/v1/erp/intake/{got['id']}/file", json={"parts": [
        {"object_id": me.object_id, "text": "Kurz notiert"}]}).json()
    assert body["filed"] and body["notes"][0]["object_id"] == me.object_id
    (fp,) = proposals.of_intake(db, got["id"], "file")
    assert _events(db, "proposal.decided", proposal=fp.id)[0].payload["outcome"] == "accepted"
    assert got["id"] not in intake.waiting(db, 1000)


def test_a_failure_counts_and_ends_after_three(db, monkeypatch):
    me = new_person(db, "employee")
    act(db, "person", me.object_id, "ui")
    it = intake.capture(db, "etwas", None, me)
    act(db, "system", None, "test")
    monkeypatch.setattr(intake, "waiting", lambda db, limit=3: [it.id] if len(
        _events(db, "intake.failed", intake=it.id)) < intake.TRIES else [])
    monkeypatch.setattr(db, "commit", db.flush)
    _ready(monkeypatch, _Script(*[_answer(stop="refusal") for _ in range(5)]))
    for _ in range(5):
        intake.catch_up(db, time.monotonic() + 30)
    assert len(_events(db, "intake.failed", intake=it.id)) == intake.TRIES


# ─── Rechte ────────────────────────────────────────────────────────────────────────────

def test_a_person_never_sees_or_files_another_persons_intake(db, api, monkeypatch):
    me, other, admin = new_person(db, "employee"), new_person(db, "employee"), new_person(db, "admin")
    monkeypatch.setattr(ai, "ready", lambda: False)
    got = api.as_(me).post("/api/v1/erp/intake", json={"text": "Privat notiert"}).json()
    assert api.as_(other).get("/api/v1/erp/intake/open").json() == []
    refused = api.as_(other).post(f"/api/v1/erp/intake/{got['id']}/file", json={"parts": [
        {"object_id": other.object_id, "text": "x"}]})
    assert refused.status_code == 404 and f"«{got['id']}»" in refused.json()["detail"]
    customer = new_person(db, "user")
    assert api.as_(customer).get("/api/v1/erp/intake/open").status_code == 403
    ok = api.as_(admin).post(f"/api/v1/erp/intake/{got['id']}/file", json={"parts": [
        {"object_id": me.object_id, "text": "Privat notiert"}]})
    assert ok.status_code == 200 and ok.json()["filed"]


def test_a_file_proposal_shows_only_to_whoever_captured(db, monkeypatch):
    firm = new_firm(db, "Delta")
    me, other = new_person(db, "employee"), new_person(db, "employee")
    act(db, "person", me.object_id, "ui")
    it = intake.capture(db, "Delta braucht Ersatzteile", firm.object_id, me)
    _ready(monkeypatch, _Script(_file_answer([(firm.object_id, "Braucht Ersatzteile.", "Ersatzteile")])))
    assert intake.file_with_ai(db, it, me) is None
    assert [p.kind for p in proposals.open_for(db, firm.object_id, me)] == ["file"]
    assert proposals.open_for(db, firm.object_id, other) == []
    assert proposals.open_counts(db).get(firm.object_id) is None     # zählt bei der Person
    with pytest.raises(Exception):
        proposals.reject(db, proposals.of_intake(db, it.id, "file")[0].id, other)


# ─── Das Angeheftete ───────────────────────────────────────────────────────────────────

def test_refresh_never_takes_away_an_open_proposal(db, api, monkeypatch):
    """«Neu ansehen» ersetzt die Hinweise – die offenen Vorschläge stehen immer zuerst da, auch
    wenn die KI nichts zeigt. Ein Hinweis zeigt auf seinen Eintrag im Verlauf und lässt sich lösen."""
    firm, hans, meier, admin = _montage(db)
    pid = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                            value="079 888 88 88", source={"text": "x"}, actor=hans.object_id)
    first = api.as_(hans).get(f"/api/v1/erp/pins/{meier.object_id}").json()
    assert [p["id"] for p in first["proposals"]] == [pid] and first["hints"] == []
    assert first["refreshed_at"] is None
    act(db, "person", hans.object_id, "ui")
    from app.schemas.communication import MessageIn
    from app.services import communication
    communication.create(db, MessageIn(channel="note", about=[meier.object_id], subject="Kran",
                                       body="Kran quietscht"), hans)
    _ready(monkeypatch, _Script(
        _answer(parsed=PinAnswer(hints=[AiHint(text="Der Kran quietscht (Notiz).", entry=1),
                                        AiHint(text="Zweiter", entry=None)])),
        _answer(parsed=PinAnswer(hints=[]))))
    r = api.as_(hans).post(f"/api/v1/erp/pins/{meier.object_id}/refresh").json()
    assert [p["id"] for p in r["proposals"]] == [pid]
    assert [h["text"] for h in r["hints"]] == ["Der Kran quietscht (Notiz).", "Zweiter"]
    assert r["hints"][0]["entry_key"] and r["hints"][0]["entry_key"].endswith(
        str(db.query(Message).filter(Message.subject == "Kran").one().id))
    assert r["hints"][1]["entry_key"] is None and r["refreshed_at"]
    solved = api.as_(hans).post(f"/api/v1/erp/pins/{meier.object_id}/solve", json={"key": "1"}).json()
    assert [h["key"] for h in solved["hints"]] == ["2"] and [p["id"] for p in solved["proposals"]] == [pid]
    assert api.as_(hans).post(f"/api/v1/erp/pins/{meier.object_id}/solve",
                              json={"key": "1"}).status_code == 409
    empty = api.as_(hans).post(f"/api/v1/erp/pins/{meier.object_id}/refresh").json()
    assert empty["hints"] == [] and [p["id"] for p in empty["proposals"]] == [pid]
    pin = _events(db, "pin")[-1]
    assert pin.actor_kind == "ai" and pin.actor_id == hans.object_id


def test_refresh_without_ai_keeps_everything(db, api, monkeypatch):
    firm, hans, meier, admin = _montage(db)
    pid = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                            value="079 999 99 99", source={"text": "x"}, actor=hans.object_id)
    monkeypatch.setattr(ai, "ready", lambda: False)
    r = api.as_(hans).post(f"/api/v1/erp/pins/{meier.object_id}/refresh").json()
    assert [p["id"] for p in r["proposals"]] == [pid] and r["problem"] == "Kein KI-Schlüssel hinterlegt."
    assert _events(db, "pin") == [] or all(e.object_id != meier.object_id for e in _events(db, "pin"))


# ─── «zu tun» ──────────────────────────────────────────────────────────────────────────

def test_todo_counts_proposals_my_intakes_and_the_cap(db, monkeypatch):
    firm, hans, meier, admin = _montage(db)
    for value in ("079 100 00 00", "079 200 00 00"):
        proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                          value=value, source={"text": "x"}, actor=hans.object_id)
    act(db, "person", hans.object_id, "ui")
    intake.capture(db, "noch abzulegen", None, hans)
    act(db, "system", None, "test")

    def items(viewer, oid):
        found = {t.object_id: t for t in todo.todo(db, viewer)}.get(oid)
        return [i for i in found.items if i.section in ("vorschlaege", "ki")] if found else []
    assert [(i.label, i.count) for i in items(hans, meier.object_id)] == [("2 Vorschläge", 2)]
    assert [(i.label, i.count) for i in items(hans, hans.object_id)] == [("1 Erfassung ablegen", 1)]
    assert items(admin, hans.object_id) == []                    # nur meine
    op = sites.find_operator(db) or new_firm(db, "Betreiber", own=True, is_operator=True)
    monkeypatch.setattr(ai, "near_cap", lambda db: True)
    assert [i.label for i in items(admin, op.object_id)] == ["KI: 80 % des Tagesdeckels"]
    assert items(hans, op.object_id) == []


def test_the_tick_writes_the_decisions_and_logs_what_it_did(db, monkeypatch):
    firm, hans, meier, admin = _montage(db)
    pid = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                            value="079 300 00 00", source={"text": "x"}, actor=hans.object_id)
    _type_phone(db, admin, meier, "079 300 00 00")
    act(db, "system", None, "test")
    monkeypatch.setattr(ai, "ready", lambda: False)
    monkeypatch.setattr(db, "commit", db.flush)
    assert tick._ai(db, time.monotonic() + 30)["decided"] >= 1
    assert _events(db, "proposal.decided", proposal=pid)[0].actor_kind == "system"
    assert any(t.name == "ai" for t in tick.TASKS)


def test_no_ai_call_outside_the_gate():
    """Die KI ruft nur ``services/ai.py`` – die neuen Dienste gehen durch ``converse``."""
    services = Path(__file__).resolve().parents[1] / "app" / "services"
    for name in ("proposals.py", "intake.py", "pins.py", "follow.py"):
        source = (services / name).read_text("utf-8")
        assert "anthropic" not in source and "_client(" not in source, name


# ─── Befunde der Prüfung (Phase 3) ─────────────────────────────────────────────────────

def _sick_note(db, owner):
    """Ein Arztzeugnis am Nachweis einer Absenz – sehen dürfen es nur die Person und der Admin."""
    act(db, "person", owner.object_id, "ui")
    doc, _ = docs.file(db, raw=PDF + str(random.random()).encode(), filename="z.pdf",
                       mime="application/pdf", art="Arztzeugnis", name="Zeugnis Grippe",
                       source="file", refs=[], actor=owner)
    doc.text = "Diagnose: geheim"
    docs.set_field(db, document_object_id=doc.object_id, object_id=owner.object_id,
                   part="time:42", field="time.proof", actor=owner)
    db.flush()
    return doc


def test_1_an_admin_refresh_reads_only_what_every_staff_may_see(db, api, monkeypatch):
    """►► **Die KI liest, was jedes Personal sehen darf** – auch wenn ein Admin «neu ansehen»
    drückt: ihre Hinweise sieht jedes Personal. Das Arztzeugnis der Person steht weder in der
    Anfrage noch liefern es die Werkzeuge. Bug-Form: die Werkzeuge lesen mit dem Admin. ◄◄"""
    owner, admin = new_person(db, "employee"), new_person(db, "admin")
    doc = _sick_note(db, owner)
    assert "Zeugnis Grippe" in ai_tools.history(db, admin, owner.object_id)    # der Admin sähe es
    look = [_Block(type="tool_use", id="t1", name="record", input={"object_id": doc.object_id}),
            _Block(type="tool_use", id="t2", name="history", input={"object_id": owner.object_id})]
    script = _Script(_answer(stop="tool_use", content=look),
                     _answer(parsed=PinAnswer(hints=[AiHint(text="Nichts Besonderes.", entry=None)])))
    _ready(monkeypatch, script)
    r = api.as_(admin).post(f"/api/v1/erp/pins/{owner.object_id}/refresh")
    assert r.status_code == 200, r.text
    asked = script.seen[0]["messages"][0]["content"][0]["text"]
    record, history = script.seen[1]["messages"][-1]["content"][:2]
    assert "Zeugnis" not in asked and "geheim" not in asked
    assert "nicht gefunden" in record["content"] and "Zeugnis" not in history["content"]
    assert _events(db, "pin")[-1].actor_id == admin.object_id               # der Admin handelt
    # Ein Datensatz, den nicht jedes Personal sieht, sieht die KI gar nicht erst an.
    private = api.as_(admin).post(f"/api/v1/erp/pins/{doc.object_id}/refresh").json()
    assert "nicht jedes Personal" in private["problem"]


def test_1_follow_with_an_admins_mailbox_reads_like_every_staff(db, monkeypatch):
    """Folgen aus der Mail im Postfach eines Admins: die Werkzeuge lesen gleich (ohne Privates)."""
    own = new_firm(db, "Inexxio", own=True)
    admin = new_person(db, "admin")
    db.add(Mailbox(channel=f"c{own.object_id}", address="info3@inexxio.test",
                   owner_object_id=admin.object_id, token="x"))
    customer = new_person(db, "user", first_name="Rosa", last_name="Graf")
    customer.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    doc = _sick_note(db, new_person(db, "employee"))
    act(db, "system", None, "test")
    monkeypatch.setattr(db, "commit", db.flush)
    if follow.start(db) is None:
        follow.due(db)
    mail = _mail(db, customer, own, "Bitte Zeugnis prüfen")
    script = _Script(_answer(stop="tool_use", content=[_Block(
        type="tool_use", id="t1", name="record", input={"object_id": doc.object_id})]),
        _answer(parsed=follow.FollowAnswer(proposals=[])))
    _ready(monkeypatch, script)
    monkeypatch.setattr(follow, "due", lambda db, limit=5: [mail.id])
    follow.run(db, time.monotonic() + 30)
    assert "nicht gefunden" in script.seen[1]["messages"][-1]["content"][0]["content"]
    assert ai_tools.record(db, admin, doc.object_id).startswith("Dokument")  # der Admin sähe es


def _old_open(db, person, n):
    """``n`` alte offene Vorschläge – nichts im Log erledigt sie."""
    return [log.event(db, "proposal", person.object_id, {
        "kind": "change", "field": "last_name", "label": "Nachname", "value": f"Alt {i}",
        "source": {"text": "x"}}) for i in range(n)]


def test_3_settle_never_hangs_behind_old_open_proposals(db):
    """3 alte offene + 1 übernommener → ``settle(limit=3)`` schreibt den Entscheid. Bug-Form:
    der Takt liest die ältesten Unentschiedenen und kommt nie über sie hinaus."""
    firm, hans, meier, admin = _montage(db)
    _old_open(db, meier, 3)
    pid = proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                            value="079 400 00 00", source={"text": "x"}, actor=hans.object_id)
    _type_phone(db, admin, meier, "079 400 00 00")
    act(db, "system", None, "job")
    assert proposals.settle(db, limit=3) >= 1
    assert _events(db, "proposal.decided", proposal=pid)[0].payload["outcome"] == "accepted"


class _Count:
    """Zählt die SQL-Anweisungen an der Verbindung der Sitzung."""

    def __init__(self, db):
        self.engine, self.n = db.get_bind(), 0

    def _hit(self, *a, **kw):
        self.n += 1

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self._hit)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._hit)


def test_4_todo_costs_a_fixed_number_of_queries_however_many_proposals(db):
    """«zu tun» mit 50 offenen Vorschlägen braucht so viele Abfragen wie mit einem – und die
    Vorschläge zählt EINE. Bug-Form: je Vorschlag neun Abfragen (ableiten einzeln)."""
    firm, hans, meier, admin = _montage(db)
    _old_open(db, meier, 1)
    with _Count(db) as one:
        todo.todo(db, hans)
    _old_open(db, meier, 49)
    with _Count(db) as fifty:
        found = {t.object_id: t for t in todo.todo(db, hans)}[meier.object_id]
    assert fifty.n == one.n
    assert [i.count for i in found.items if i.section == "vorschlaege"] == [50]
    with _Count(db) as counts:
        proposals.open_counts(db)
    assert counts.n == 1
    # Was das Log schon erledigt hat, zählt nicht mehr – auch ohne Takt.
    proposals.propose(db, object_id=meier.object_id, kind="change", field="phone",
                      value="079 500 00 00", source={"text": "x"}, actor=hans.object_id)
    assert proposals.open_counts(db)[meier.object_id] == 51
    _type_phone(db, admin, meier, "079 500 00 00")
    assert proposals.open_counts(db)[meier.object_id] == 50


class _Overloaded:
    """Eine KI, die mit 529 antwortet (ausgelastet)."""

    def __init__(self):
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kw):
        err = Exception("overloaded")
        err.status_code = 529
        raise err


def test_5_a_passing_error_does_not_throw_a_mail_away(db, monkeypatch):
    """529 zählt als Fehlschlag (``mail.follow_failed``), die Mail kommt wieder; erst nach dem
    dritten gilt sie als geprüft. Am Deckel kein Versuch, kein Zählen. Bug-Form: der erste
    Fehler schreibt ``mail.followed`` – die Mail ist für immer verloren."""
    own = new_firm(db, "Inexxio", own=True)
    staff = new_person(db, "employee")
    db.add(Mailbox(channel=f"c{own.object_id}", address="info4@inexxio.test",
                   owner_object_id=staff.object_id, token="x"))
    customer = new_person(db, "user")
    customer.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    db.flush()
    monkeypatch.setattr(db, "commit", db.flush)
    if follow.start(db) is None:
        follow.due(db)
    mail = _mail(db, customer, own, "Neue Nummer 079 999 00 00")
    monkeypatch.setattr(get_settings(), "ai_daily_cap_chf", 10.0)
    _ready(monkeypatch, _Overloaded(), spent=10.0)
    assert follow.follow_one(db, mail.id) is None                       # am Deckel: nichts
    assert _events(db, "mail.follow_failed", message=mail.id) == []
    _ready(monkeypatch, _Overloaded())
    for n in range(1, follow.TRIES + 1):
        assert mail.id in follow.due(db, 100)
        assert follow.follow_one(db, mail.id) == 0
        assert len(_events(db, "mail.follow_failed", message=mail.id)) == n
        assert len(_events(db, "mail.followed", message=mail.id)) == (1 if n == follow.TRIES else 0)
    assert mail.id not in follow.due(db, 100)
    (done,) = _events(db, "mail.followed", message=mail.id)
    assert "antwortet gerade nicht" in done.payload["problem"]
    assert "mail.follow_failed" in history.HIDDEN_EVENTS


def test_6_under_a_time_limit_the_sdk_never_retries(db, monkeypatch):
    """Unter ``ai.until`` bekommt der Client keinen zweiten Versuch – wiederholen ist Sache des
    Takts. Bug-Form: das SDK wiederholt einen 529 und bricht die 60 s."""
    staff = new_person(db, "employee")
    seen = []
    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(ai, "spent_today", lambda db: 0.0)
    monkeypatch.setattr(ai, "_client", lambda timeout, retries: seen.append(retries) or _Script(
        _answer(parsed=FileAnswer(parts=[], proposals=[]))))
    monkeypatch.setitem(ai.TASKS, "slow", ai.Task(model="claude-sonnet-5-5", max_tokens=10,
                                                  timeout=30.0, retries=2))
    ai.converse(db, task="slow", actor=staff, system="s", schema=FileAnswer, content=[])
    with ai.until(40):
        ai.converse(db, task="slow", actor=staff, system="s", schema=FileAnswer, content=[])
    assert seen == [2, 0]
    assert ai.TASKS["follow"].retries == 0 and ai.TASKS["follow"].timeout <= 45


def test_7_proposals_of_a_record_need_the_right_to_see_it(db, api):
    """``GET /proposals?object_id=`` prüft die Sichtbarkeit wie das Angeheftete. Bug-Form: eine
    Kollegin liest die Vorschläge an einem Arztzeugnis."""
    owner, colleague = new_person(db, "employee"), new_person(db, "employee")
    doc = _sick_note(db, owner)
    url = "/api/v1/erp/proposals"
    assert api.as_(owner).get(url, params={"object_id": doc.object_id}).status_code == 200
    r = api.as_(colleague).get(url, params={"object_id": doc.object_id})
    assert r.status_code == 404 and f"«{doc.object_id}»" in r.json()["detail"]


def test_8_twice_stimmt_so_is_one_note_per_part(db, api, monkeypatch):
    """Zwei «Stimmt so», die beide noch nichts Abgelegtes sahen (zwei Fenster): der eindeutige
    Entscheid weist den zweiten ab (409) – und nimmt seine Notizen mit zurück. Bug-Form: zwei
    Entscheide, jede Notiz doppelt."""
    me = new_person(db, "employee")
    monkeypatch.setattr(ai, "ready", lambda: False)
    got = api.as_(me).post("/api/v1/erp/intake", json={"text": "Zweimal abgelegt"}).json()
    parts = {"parts": [{"object_id": me.object_id, "text": "Zweimal abgelegt", "subject": "Zweimal"}]}
    url = f"/api/v1/erp/intake/{got['id']}/file"
    assert api.as_(me).post(url, json=parts).status_code == 200
    real = proposals.decided
    monkeypatch.setattr(proposals, "decided", lambda db, ids: {})   # das zweite Fenster
    again = api.as_(me).post(url, json=parts)
    monkeypatch.setattr(proposals, "decided", real)
    assert again.status_code == 409 and "schon entschieden" in again.json()["detail"]
    assert db.query(Message).filter(Message.subject == "Zweimal").count() == 1
    (fp,) = proposals.of_intake(db, got["id"], "file")
    assert len(_events(db, "proposal.decided", proposal=fp.id)) == 1
    with pytest.raises(HTTPException) as twice:
        proposals.decide(db, fp, "rejected")
    assert twice.value.status_code == 409


def test_8_filed_by_hand_while_the_ai_reads_leaves_no_second_file(db, monkeypatch):
    """Legt die Person von Hand ab, während die KI liest, schreibt die KI danach keinen
    ``file``-Vorschlag mehr. Bug-Form: zwei ``file`` zu einer Erfassung."""
    me = new_person(db, "employee")
    act(db, "person", me.object_id, "ui")
    it = intake.capture(db, "Während die KI liest", None, me)

    class _Meanwhile(_Script):
        def _parse(self, **kw):
            intake.file(db, it.id, [SimpleNamespace(object_id=me.object_id, text="von Hand",
                                                    subject="Hand")], me)
            return super()._parse(**kw)
    _ready(monkeypatch, _Meanwhile(_file_answer([(me.object_id, "von der KI", "KI")])))
    assert intake.file_with_ai(db, it, me) is None
    (only,) = proposals.of_intake(db, it.id, "file")
    assert only.payload["parts"][0]["text"] == "Während die KI liest"      # der rohe Teil
