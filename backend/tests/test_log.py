"""►►► **Das Log – die Wächter** (Projektakte «Die lernende Firma» §1). ◄◄◄

Was wahr sein muss, damit das Log die eine Wahrheit ist:

* jede Tabelle hat den Zeilen-Trigger, und das Log weiss, an welchem Ding sie hängt;
* ohne Handelnden scheitert jede Änderung;
* jede Route, die an die Datenbank geht, setzt einen Handelnden;
* ein Eintrag hält wer, woher, Vorgang, Ding und nur das Geänderte fest – Geheimes nie;
* Ereignisse stehen in derselben Transaktion (beides oder nichts);
* das Log ist weder änder- noch löschbar; nur die Schwärzung, und die trägt sich ein;
* die Siegel bemerken jede nachträgliche Änderung.

Jeder Wächter ist gegen seine Bug-Form gegengeprüft (im Test selbst, wo es geht).
"""

import datetime as dt
import uuid

import pytest
from sqlalchemy import text

from tests.runner import session


@pytest.fixture
def db():
    s = session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _entries(db, table, row):
    from app.models import Log
    return (db.query(Log).filter(Log.table_name == table, Log.row_key == str(row))
            .order_by(Log.id).all())


# ── Abdeckung ────────────────────────────────────────────────────────────────────────


def test_every_table_is_known_to_the_log():
    """Jede Tabelle des Modells steht in ``OBJECT`` oder ``EXEMPT``. Bug-Form: eine neue
    Tabelle ohne Eintrag – ``missing`` meldet sie, und der Start bricht ab."""
    import app.models  # noqa: F401
    from app.core.database import Base
    from app.domain import log as d

    assert d.missing(list(Base.metadata.tables)) == []
    assert d.missing(["neue_tabelle"]) == ["neue_tabelle"]
    with pytest.raises(RuntimeError, match="neue_tabelle"):
        d.triggers_sql({"neue_tabelle": []})


def test_every_table_has_the_row_trigger(db):
    """In der Datenbank (nach Migration + Start) trägt jede Tabelle ``trg_log_row``."""
    import app.models  # noqa: F401
    from app.core.database import Base
    from app.domain import log as d

    have = {r[0] for r in db.execute(text(
        "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE t.tgname = :n AND NOT t.tgisinternal"), {"n": d.ROW_TRIGGER})}
    want = {t for t in Base.metadata.tables if t not in d.EXEMPT}
    assert want - have == set(), f"Ohne Trigger: {sorted(want - have)}"


# ── Wer handelt ──────────────────────────────────────────────────────────────────────


def test_a_change_without_an_actor_fails():
    """Bug-Form: ohne ``log_actor`` im Trigger ginge die Änderung still durch."""
    from app.core.database import SessionLocal
    from app.models import ObjectRef

    raw = SessionLocal()                    # bewusst OHNE ``act``
    try:
        raw.add(ObjectRef(object_id=999_999_901, object_type="test"))
        with pytest.raises(Exception, match="niemand handelt"):
            raw.flush()
    finally:
        raw.rollback()
        raw.close()


def routes_without_actor(app) -> list[str]:
    """Routen, die eine Datenbank-Sitzung bekommen, aber keinen Handelnden setzen
    (``core/auth.get_current_user`` oder ``core/actor.public``)."""
    from fastapi.routing import iter_route_contexts

    from app.core.database import get_db

    def calls(dep, acc):
        acc.append(dep.call)
        for sub in dep.dependencies:
            calls(sub, acc)
        return acc

    out = []
    for ctx in iter_route_contexts(app.routes):
        route = getattr(ctx, "route", ctx)
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        found = calls(dependant, [])
        if get_db in found and not any(getattr(c, "log_actor", False) for c in found):
            out.append(f"{sorted(route.methods)} {route.path}")
    return out


def test_every_route_with_a_database_names_who_acts():
    """Bug-Form (gegengeprüft): eine Route mit Sitzung, aber ohne Handelnden, wird gemeldet –
    im Betrieb scheiterte ihr erstes Schreiben."""
    from fastapi import Depends, FastAPI

    from app.core.database import get_db
    from app.main import app

    assert routes_without_actor(app) == []
    bad = FastAPI()

    @bad.post("/x")
    def x(db=Depends(get_db)):              # noqa: ANN001
        return None

    assert routes_without_actor(bad) == ["['POST'] /x"]


# ── Ein Eintrag ──────────────────────────────────────────────────────────────────────


def test_a_row_change_is_logged_with_who_where_and_only_what_changed(db, make_person):
    from app.core.actor import act

    person = make_person("user")
    db.flush()
    act(db, "person", person.object_id, "ui")
    person.phone = "+41 79 000 00 00"
    db.flush()
    rows = _entries(db, "user_profiles", person.id)
    assert rows[0].action == "insert" and rows[0].object_id == person.object_id
    last = rows[-1]
    assert last.action == "update" and last.actor_kind == "person"
    assert last.actor_id == person.object_id and last.source == "ui"
    assert set(last.changes) == {"phone"}, "nur das Geänderte, nie updated_at"
    assert last.changes["phone"][1] == "+41 79 000 00 00"
    assert last.request_id == rows[0].request_id, "eine Sitzung = ein Vorgang"


def test_only_a_timestamp_is_no_change(db, make_person):
    person = make_person("user")
    db.flush()
    before = len(_entries(db, "user_profiles", person.id))
    db.execute(text("UPDATE user_profiles SET updated_at = now() + interval '1 minute' "
                    "WHERE id = :i"), {"i": person.id})
    assert len(_entries(db, "user_profiles", person.id)) == before


def test_soft_delete_is_a_delete(db, make_firm):
    firm = make_firm()
    db.flush()
    firm.is_active = False
    db.flush()
    assert _entries(db, "company_settings", firm.id)[-1].action == "delete"


def test_secrets_never_stand_in_the_log(db, make_person):
    """Token, Challenges, Schlüssel und Binäres stehen als «[geheim]» da. Bug-Form: ohne die
    Liste stünde der Zugangs-Token im Klartext."""
    from app.models import WebAuthnChallenge

    person = make_person("user")
    db.flush()
    ch = WebAuthnChallenge(user_id=person.id, challenge="SUPERGEHEIM-" + uuid.uuid4().hex,
                           purpose="register",
                           expires_at=dt.datetime.now(dt.timezone.utc))
    db.add(ch)
    db.flush()
    (row,) = _entries(db, "webauthn_challenges", ch.id)
    assert row.changes["challenge"] == "[geheim]"
    assert row.object_id == person.object_id
    assert "SUPERGEHEIM" not in str(row.changes)


# ── Ereignisse ───────────────────────────────────────────────────────────────────────


def test_an_event_lives_and_dies_with_its_transaction(db):
    from app.models import Log
    from app.services import log

    marker = uuid.uuid4().hex
    nested = db.begin_nested()
    log.event(db, "test.marker", None, {"m": marker})
    nested.rollback()
    assert not db.query(Log).filter(Log.payload["m"].astext == marker).count()
    eid = log.event(db, "test.marker", 123, {"m": marker}, kind="ai", actor=456)
    row = db.get(Log, eid)
    assert (row.action, row.event, row.object_id) == ("event", "test.marker", 123)
    assert (row.actor_kind, row.actor_id, row.source) == ("ai", 456, "test")


def test_process_events_are_read_through_the_view(db):
    """Geschrieben ins Log, gelesen als ``ProcessEvent`` – in der Reihenfolge, mit Auftrag,
    Modul, Stück, Vorher/Nachher, Nutzlast und handelnder Person."""
    from app.models import ProcessEvent
    from tests.scenarios import World

    w = World(db)
    order = w.produce(w.article(), 2)
    events = (db.query(ProcessEvent).filter(ProcessEvent.order_id == order.id)
              .order_by(ProcessEvent.id).all())
    assert events and events[0].kind == "start"
    assert all(e.instance_unit_id and e.status_before and e.status_after for e in events)
    assert [e.id for e in events] == sorted(e.id for e in events)


def test_a_process_event_without_an_order_fails(db):
    from app.services import log

    with pytest.raises(Exception, match="ohne Auftrag"):
        log.process_events(db, [dict(order_id=-1, step_id=None, instance_unit_id=1, kind="step",
                                     status_before="a", status_after="b", payload=None,
                                     actor_id=None)])


# ── Unveränderlich, versiegelt, geschwärzt ───────────────────────────────────────────


@pytest.mark.parametrize("sql", [
    "UPDATE log SET event = 'x' WHERE id = (SELECT max(id) FROM log)",
    "DELETE FROM log WHERE id = (SELECT max(id) FROM log)",
    "TRUNCATE log",
    "UPDATE log_seal SET hash = 'x'",
    "DELETE FROM log_seal",
])
def test_the_log_cannot_be_changed(db, sql):
    from app.services import log

    log.event(db, "test.immutable", None, {})
    _old_entries(db, 3)
    log.seal_due(db)                       # damit ``log_seal`` eine Zeile hat
    with pytest.raises(Exception, match="wird nie geändert oder gelöscht"):
        db.execute(text(sql))


def _old_entries(db, days_ago: int, n: int = 2):
    at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)
    for i in range(n):
        db.execute(text(
            "INSERT INTO log (at, actor_kind, source, request_id, object_id, action, event, "
            "payload) VALUES (:at, 'system', 'test', gen_random_uuid(), 777000001, 'event', "
            "'test.old', CAST(:p AS jsonb))"), {"at": at, "p": f'{{"i": {i}}}'})
    return at.date()


def test_the_seal_notices_a_later_change(db):
    """Bug-Form (gegengeprüft): ein umgeschriebener Eintrag in einem versiegelten Tag – die
    Kette bricht genau an diesem Tag."""
    from app.services import log

    day = _old_entries(db, 3)
    _old_entries(db, 2)
    assert log.seal_due(db) >= 2
    assert log.seal_due(db) == 0, "ein Tag wird nur einmal versiegelt"
    assert log.tampered(db) == []
    db.execute(text("ALTER TABLE log DISABLE TRIGGER trg_log_immutable"))
    db.execute(text("UPDATE log SET payload = '{\"i\": 99}' WHERE event = 'test.old' "
                    "AND (at AT TIME ZONE 'UTC')::date = :d"), {"d": day})
    db.execute(text("ALTER TABLE log ENABLE TRIGGER trg_log_immutable"))
    assert str(day) in log.tampered(db)


def test_redaction_is_the_only_change_and_logs_itself(db):
    from app.models import Log
    from app.services import log

    _old_entries(db, 3)
    log.seal_due(db)
    assert log.redact(db, 777000001, "Löschbegehren") >= 2
    rows = db.query(Log).filter(Log.object_id == 777000001, Log.event == "test.old").all()
    assert all(r.payload == {"geschwärzt": True} for r in rows)
    note = db.query(Log).filter(Log.object_id == 777000001,
                                Log.event == "log.redacted").one()
    assert note.payload["reason"] == "Löschbegehren"
    assert log.tampered(db) == [], "eine Schwärzung ist erklärt, nicht verdächtig"
    assert any(not r["ok"] and r["redacted"] for r in log.verify(db))


def test_redaction_never_blanks_process_history(db):
    """Prozess-Ereignisse tragen die Auftragsnummer als Ding – geschwärzt fielen die Stücke
    aus Bild, Journey und Stückliste. Bug-Form (gegengeprüft): ohne den Ausschluss in
    ``log_redact`` stünde ``order_id`` der Sicht danach leer."""
    from app.models import ProcessEvent
    from app.services import log
    from tests.scenarios import World

    w = World(db)
    order = w.produce(w.article(), 1)
    before = db.query(ProcessEvent).filter(ProcessEvent.order_id == order.id).count()
    log.redact(db, order.object_id, "Test")
    assert db.query(ProcessEvent).filter(ProcessEvent.order_id == order.id).count() == before
