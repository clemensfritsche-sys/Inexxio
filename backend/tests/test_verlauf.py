"""►►► **Ein Verlauf für jeden Datensatz** (Phase 2 «Die lernende Firma», Schritte 2.3–2.5). ◄◄◄

Gefahren über die echten Dienste (``services/history``, ``services/communication``) gegen
echtes PostgreSQL. Jeder Wächter nennt seine Bug-Form; wo es geht, zeigt der Test selbst,
dass er anschlägt (Gegenprobe).
"""

import importlib.util
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app.domain.errors import Rejected
from sqlalchemy import text

from app.core.actor import act
from app.core.database import ACTOR_KEY
from app.domain import communication as dc
from app.domain import log as dl
from app.models import Message, MessageParty, UserProfile
from app.schemas.communication import MessageIn
from app.services import communication as comm
from app.services import documents as docs
from app.services.documents import RefIn
from app.services import history
from tests.factories import new_firm, new_person
from tests.runner import BACKEND
from tests.scenarios import World

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture()
def world(db):
    staff = new_person(db, "employee")
    return db, staff


def _note(db, actor, about, subject="Notiz", body="steht hier", **kw):
    return comm.create(db, MessageIn(channel=dc.NOTE, about=about, subject=subject, body=body,
                                     **kw), actor)


def _all(db, oid, viewer, limit):
    """Alle Seiten nacheinander – über den Cursor, wie die Oberfläche beim Rollen."""
    out, before, pages = [], None, 0
    while True:
        p = history.page(db, oid, viewer, before=before, limit=limit)
        out += p.entries
        pages += 1
        assert pages < 200, "Der Cursor kommt nicht vorwärts."
        if not p.before:
            return out
        before = p.before


def _new_request(db, person):
    """Eine neue Handlung (eigene ``request_id``) – wie eine zweite Anfrage."""
    db.info.pop(ACTOR_KEY, None)
    act(db, "person", person.object_id, "test")


# ─── 2.3 Das Anliegen als Spalte ──────────────────────────────────────────────────────

def test_the_frozen_topic_of_the_migration_is_the_topic_of_the_domain():
    """Migration 168 füllt ``messages.topic`` mit einer eingefrorenen Abschrift von
    ``domain.topic`` (``casefold`` kennt PostgreSQL nicht). Bug-Form: die beiden rechnen
    verschieden – dann hiesse dasselbe Anliegen vor und nach der Migration anders."""
    path = BACKEND / "alembic" / "versions" / "168_verlauf_anliegen_notiz.py"
    spec = importlib.util.spec_from_file_location("m168", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    samples = [None, "", "  ", "Seilwinde", "RE: AW:  Seilwinde  Kran", "Fwd[2]: Offerte",
               "WG: Straße", "STRASSE", "sv: tr: vs: x", "Re:Re:Re: ", "Antw: Ölwechsel  \n"]
    for s in samples:
        assert mod._topic(s) == dc.topic(s), s
    assert mod._topic("WG: Straße") == "strasse"


def test_the_topic_follows_the_subject_at_the_one_place(world):
    """Das Anliegen setzt das Modell mit dem Betreff – auch bei einer Zeile, die nicht über
    ``create`` entsteht (Abgleich, Tests). Bug-Form: eine Nachricht ohne Anliegen wäre nie
    beantwortet."""
    db, staff = world
    m = Message(sender_object_id=staff.object_id, channel="intern", subject="AW: Straße", body="")
    db.add(m)
    db.flush()
    assert db.execute(text("SELECT topic FROM messages WHERE id = :i"),
                      {"i": m.id}).scalar() == "strasse"
    assert Message(sender_object_id=1, channel="intern").topic in ("", None)


# ─── 2.3 In Seiten ────────────────────────────────────────────────────────────────────

def test_pages_are_stable_with_equal_timestamps(world):
    """►►► **Der Cursor verliert nichts und zeigt nichts doppelt** – auch wenn Nachrichten,
    Dokumente und Änderungen auf die Mikrosekunde dieselbe Zeit tragen. ◄◄◄ Die Reihenfolge
    ist (Zeit, Art, Nummer) absteigend; jede Quelle liefert, was davor liegt.

    Bug-Form: ein Cursor nur über die Zeit (Gleichstand fällt durch oder wiederholt sich)."""
    db, staff = world
    order = World(db).produce(World(db).article(), 1)
    same = db.execute(text("SELECT now()")).scalar()      # die Zeit des Logs dieser Handlung
    for i in range(7):
        _note(db, staff, [order.object_id], subject=f"N{i}", at=same)
    docs.file(db, raw=PDF + b"x1", filename="a.pdf", mime="application/pdf", art="Plan",
              name="A", source="file", refs=[RefIn(object_id=order.object_id)], actor=staff)
    db.flush()
    whole = history.page(db, order.object_id, staff, limit=100)
    assert not whole.before
    for limit in (1, 2, 3, 5):
        paged = _all(db, order.object_id, staff, limit)
        assert [e.key for e in paged] == [e.key for e in whole.entries], limit
    keys = [history.parse(e.key) for e in whole.entries]
    assert keys == sorted(keys, reverse=True)
    kinds = {e.kind for e in whole.entries}
    assert kinds == {"message", "document", "change"}
    notes = [e for e in whole.entries if e.kind == "message"]
    assert len(notes) == 7 and len({e.at for e in notes}) == 1


def test_a_handling_over_several_transactions_stands_once(world):
    """Eine Handlung (``request_id``) kann Zeilen zu verschiedenen Zeiten tragen – der
    Mail-Abgleich speichert je Postfach. Sie steht EINMAL da, bei ihrer jüngsten Zeile.
    Bug-Form: die ältere Zeile allein wird auf der nächsten Seite ein zweiter Block."""
    db, staff = world
    lea = new_person(db)
    now = datetime.now(timezone.utc)
    long_one, other = uuid.uuid4(), uuid.uuid4()
    for at, req, field in ((now - timedelta(hours=2), long_one, "a"),
                           (now - timedelta(hours=1), other, "b"),
                           (now, long_one, "c")):
        db.execute(text(
            "INSERT INTO log (at, actor_kind, source, request_id, object_id, table_name, row_key,"
            " action, changes) VALUES (:at, 'system', 'job', :r, :o, 'user_profiles', '1',"
            " 'update', CAST(:ch AS jsonb))"),
            {"at": at, "r": req, "o": lea.object_id, "ch": f'{{"{field}": [1, 2]}}'})
    whole = history.page(db, lea.object_id, staff, limit=100).entries
    for limit in (1, 2):
        paged = _all(db, lea.object_id, staff, limit)
        assert [e.key for e in paged] == [e.key for e in whole], limit
    mine = [sorted(c.field for r in e.change.rows for c in r.changes) for e in whole
            if e.kind == "change" and e.change.rows[0].changes
            and e.change.rows[0].changes[0].field in "abc"]
    assert mine == [["a", "c"], ["b"]]


def test_a_message_page_never_loads_everything(world):
    """``communication.page`` liest Nummer und Zeit in Stücken, bis die Seite voll ist.
    Bug-Form: der Verlauf baut wieder jede Nachricht (``load`` über alles)."""
    db, staff = world
    lea = new_person(db)
    for i in range(12):
        comm.create(db, MessageIn(channel="intern", about=[lea.object_id], subject=f"S{i}",
                                  body="x"), staff)
    found, _ = comm.page(db, [lea.object_id], None, 5)
    assert len(found) == 5
    older, _ = comm.page(db, [lea.object_id], (found[-1][1], found[-1][0]), 100)
    assert len(older) == 7 and not {i for i, _ in found} & {i for i, _ in older}


def test_a_circular_stays_one_entry_across_pages(world):
    """Ein Rundschreiben steht EINMAL – auch beim Absender, der jede Kopie geschrieben hat,
    und über eine Seitengrenze hinweg. Bug-Form: die Gruppe zerfällt je Seite."""
    db, staff = world
    people = [new_person(db) for _ in range(5)]
    first = comm._create_group(db, MessageIn(channel="c999999990", to=[p.object_id for p in people],
                                             subject="Betriebsferien", body="Zu.",
                                             delivery="circular"), staff, "Betriebsferien", "Zu.")
    for limit in (1, 2, 30):
        found, sizes = comm.page(db, [staff.object_id], None, limit)
        assert [i for i, _ in found] == [first.id]
        assert sizes == {first.id: 5}
    mine, _ = comm.page(db, [people[3].object_id], None, 30)
    assert len(mine) == 1 and mine[0][0] != first.id      # ihre eigene Kopie


# ─── 2.4 Die Notiz ────────────────────────────────────────────────────────────────────

def test_a_note_on_any_record_shows_in_its_history(world):
    """**Notiz an Auftrag, Artikel, Instanz, Dokument erscheint in deren Verlauf** – und nur
    dort (eine Heimat). Bug-Form: «Betrifft» nimmt nur Personen."""
    db, staff = world
    w = World(db)
    article = w.article()
    order = w.produce(article, 1)
    instance = w.instances(order)[0]
    doc, _ = docs.file(db, raw=PDF + b"n", filename="n.pdf", mime="application/pdf",
                       art="Plan", name="B", source="file", refs=[], actor=staff)
    targets = [order.object_id, article.object_id, instance, doc.object_id]
    for t in targets:
        _note(db, staff, [t], subject=f"Zu {t}", body=f"Notiz an {t}")
    for t in targets:
        found = [e.message for e in history.page(db, t, staff).entries if e.kind == "message"]
        assert [m.subject for m in found] == [f"Zu {t}"], t
        assert found[0].about[0].object_id == t and found[0].about[0].name != str(t)
        assert found[0].channel.kind == "note"
    with pytest.raises(Rejected):
        _note(db, staff, [999_999_998])                    # gibt es nicht


def test_a_note_is_never_open_and_never_leaves_the_house(world):
    """Eine Notiz bittet um nichts – auch mit einem Mitarbeiter im «An» nicht offen, nie im
    Zeichen «zu tun», nie hinaus. Gegenprobe: dieselbe Nachricht intern ist offen."""
    db, staff = world
    sara, lea = new_person(db, "employee"), new_person(db)
    note = _note(db, staff, [lea.object_id], to=[sara.object_id], subject="Lager")
    ask = comm.create(db, MessageIn(channel="intern", to=[sara.object_id], about=[lea.object_id],
                                    subject="Lager?", body="x"), staff)
    out = {m.id: m for m in comm.load(db, [note.id, ask.id])}
    assert not out[note.id].open and out[ask.id].open
    counted = {c.object_id: c.open for c in comm.open_counts(db)}
    assert counted.get(sara.object_id) == 1
    assert not note.outgoing and not dc.channel(dc.NOTE).outside


def test_a_note_never_answers(world):
    """Eine Notiz ist Wissen, keine Antwort: auch leer und zum selben Anliegen schliesst sie
    die Frage eines Kunden nicht. Gegenprobe: dieselbe leere Nachricht intern («Erledigt ohne
    Antwort») schliesst sie."""
    db, staff = world
    kunde = new_person(db)
    ask = comm.create(db, MessageIn(channel="intern", to=[staff.object_id],
                                    subject="Offerte?", body="Bitte melden."), kunde)
    _note(db, staff, [kunde.object_id], subject="Offerte?", body="")
    assert ask.id not in comm.answered(db, [ask.id])
    comm.create(db, MessageIn(channel="intern", about=[kunde.object_id], subject="Offerte?",
                              body=""), staff)
    assert ask.id in comm.answered(db, [ask.id])


def test_moving_a_note_writes_both_entries_and_deletes_nothing(world):
    """►►► **Korrektur statt Löschen.** ◄◄◄ Am falschen Datensatz ein Vermerk «ungültig –
    gehört zu …», am richtigen der Inhalt mit «verschoben von …»; die Notiz selbst bleibt,
    wie sie war. Bug-Form: die Notiz wird umgehängt oder gelöscht."""
    db, staff = world
    w = World(db)
    wrong = w.produce(w.article(), 1)
    right = w.article()
    note = _note(db, staff, [wrong.object_id], subject="Lager", body="Palette fehlt")
    before = db.query(Message).count()
    void, moved = comm.move_note(db, note.id, right.object_id, staff)
    assert db.query(Message).count() == before + 2
    db.refresh(note)
    assert note.is_active and note.body == "Palette fehlt"
    assert [p.object_id for p in db.query(MessageParty).filter(
        MessageParty.message_id == note.id)] == [wrong.object_id]
    at_wrong = [e.message for e in history.page(db, wrong.object_id, staff).entries
                if e.kind == "message"]
    assert [m.id for m in at_wrong] == [void.id, note.id]       # die neuesten zuerst
    assert "Ungültig – gehört zu" in void.body and f"{right.object_id:09d}" in void.body
    at_right = [e.message for e in history.page(db, right.object_id, staff).entries
                if e.kind == "message"]
    assert [m.id for m in at_right] == [moved.id]
    assert moved.body.startswith("Palette fehlt") and f"{wrong.object_id:09d}" in moved.body
    with pytest.raises(Rejected):
        comm.move_note(db, note.id, wrong.object_id, staff)      # gehört schon dorthin
    mail = comm.create(db, MessageIn(channel="intern", about=[wrong.object_id], subject="X",
                                     body="y"), staff)
    with pytest.raises(Rejected):
        comm.move_note(db, mail.id, right.object_id, staff)      # nur eine Notiz


def test_mail_goes_only_to_persons(world):
    """An, Cc und Bcc sind Personen – nur «Betrifft» darf ein anderer Datensatz sein.
    Bug-Form: ein Auftrag im «An» bekäme eine Mail."""
    db, staff = world
    order = World(db).produce(World(db).article(), 1)
    with pytest.raises(Rejected):
        comm.create(db, MessageIn(channel="intern", to=[order.object_id], subject="x", body="y"),
                    staff)


# ─── 2.5 Ein Verlauf ──────────────────────────────────────────────────────────────────

def test_changes_are_one_block_per_handling_with_field_old_new(world):
    """Je Handlung (``request_id``) ein Block – wer · Tabelle (übersetzt) · ``feld: alt →
    neu``. Bug-Form: eine Zeile je Feld, oder zwei Handlungen in einem Block."""
    db, staff = world
    lea = new_person(db, first_name="Lea")
    _new_request(db, staff)
    lea.first_name, lea.phone = "Leandra", "+41 44 000 00 00"
    db.flush()
    _new_request(db, staff)
    lea.first_name = "Lea"
    db.flush()
    blocks = [e.change for e in history.page(db, lea.object_id, staff).entries
              if e.kind == "change"]
    assert len(blocks) == 3                            # angelegt · zwei Änderungen
    newest, middle = blocks[0], blocks[1]
    assert newest.actor_id == staff.object_id and newest.actor_name == staff.display_name
    (row,) = newest.rows
    assert (row.table, row.word, row.action) == ("user_profiles", "Person", "update")
    assert [(c.field, c.old, c.new) for c in row.changes] == [("first_name", "Leandra", "Lea")]
    assert {c.field for c in middle.rows[0].changes} == {"first_name", "phone"}
    created = blocks[2].rows[0]
    assert created.action == "insert" and all(c.old is None and c.new for c in created.changes)


def test_the_history_hides_what_it_already_shows(world, monkeypatch):
    """►►► **Eine Ausnahmeliste** (``history.HIDDEN``): die Zeilen einer Nachricht im Log
    wären dieselbe Sache ein zweites Mal, die Vergabe einer Nummer Rauschen. ◄◄◄ Gegenprobe:
    ohne die Liste stehen sie da – der Wächter kann anschlagen."""
    db, staff = world
    lea = new_person(db)
    comm.create(db, MessageIn(channel="intern", about=[lea.object_id], subject="Hallo",
                              body="x"), staff)

    def tables():
        return {r.table for e in history.page(db, lea.object_id, staff).entries
                if e.kind == "change" for r in e.change.rows}
    assert tables() == {"user_profiles"}
    monkeypatch.setattr(history, "HIDDEN", frozenset())
    assert {"message_parties", "objects"} <= tables()


def test_events_show_technically(world):
    """Ein Ereignis steht mit seinem Namen und seinen einfachen Angaben da – kein Satz."""
    from app.services import log
    db, staff = world
    order = World(db).produce(World(db).article(), 1)
    log.event(db, "document.viewed", order.object_id, {"who": "Lea", "n": 3, "deep": {"x": 1}})
    rows = [r for e in history.page(db, order.object_id, staff).entries if e.kind == "change"
            for r in e.change.rows if r.event == "document.viewed"]
    assert rows and rows[0].payload == {"who": "Lea", "n": "3"}


def test_a_company_history_is_that_of_its_people(world):
    """«Verlauf einer Firma = der ihrer Personen» – dazu, was sie selbst betrifft, und ihre
    eigenen Änderungen."""
    db, staff = world
    firm = new_firm(db, "Muster")
    lea = new_person(db, company=firm.object_id)
    a = comm.create(db, MessageIn(channel="intern", about=[lea.object_id], subject="A", body="a"),
                    staff)
    b = _note(db, staff, [firm.object_id], subject="B")
    other = comm.create(db, MessageIn(channel="intern", about=[new_person(db).object_id],
                                      subject="C", body="c"), staff)
    entries = history.page(db, firm.object_id, staff).entries
    ids = {e.message.id for e in entries if e.kind == "message"}
    assert ids == {a.id, b.id} and other.id not in ids
    words = {r.word for e in entries if e.kind == "change" for r in e.change.rows}
    assert words == {"Unternehmen"}


def test_every_table_has_one_word():
    """Ein Wort je Tabelle (``domain/log.TABLE_WORDS``) – für jede, an der das Log schreibt.
    Bug-Form: eine neue Tabelle steht roh im Verlauf."""
    assert set(dl.TABLE_WORDS) == set(dl.OBJECT)
    assert len(set(dl.TABLE_WORDS.values())) == len(dl.TABLE_WORDS)


def test_unknown_records_and_bad_cursors_are_refused(world):
    db, staff = world
    with pytest.raises(Rejected) as e:
        history.page(db, 999_999_997, staff)
    assert e.value.status == 404
    with pytest.raises(Rejected) as e:
        history.page(db, staff.object_id, staff, before="gestern")
    assert e.value.status == 400


def test_time_rows_follow_the_timekeeping_rule(world):
    """Die Zeiterfassung einer Person sehen nur sie selbst und der Admin – auch im Verlauf.
    Gegenprobe: die Person selbst sieht ihre Zeilen."""
    from app.models import TimeContract
    db, staff = world
    lea = new_person(db, "employee")
    db.add(TimeContract(person_object_id=lea.object_id, valid_from=datetime.now().date(),
                        weekly_minutes=2520, workdays=31, vacation_weeks=5,
                        company_object_id=None))
    db.flush()

    def tables(viewer):
        return {r.table for e in history.page(db, lea.object_id, viewer).entries
                if e.kind == "change" for r in e.change.rows}
    assert "time_contracts" in tables(lea)
    assert "time_contracts" not in tables(staff)
    admin = db.query(UserProfile).filter(UserProfile.id == new_person(db, "admin").id).one()
    assert "time_contracts" in tables(admin)


def test_a_planned_message_keeps_its_place(world):
    """Eine Erinnerung in der Zukunft steht als neuester Eintrag – der Cursor trägt auch sie."""
    db, staff = world
    later = comm.create(db, MessageIn(channel="intern", to=[staff.object_id], subject="Morgen",
                                      body="x", at=datetime.now(timezone.utc) + timedelta(days=1)),
                        staff)
    first = history.page(db, staff.object_id, staff, limit=1)
    assert first.entries[0].message.id == later.id and first.entries[0].message.planned


def test_a_mailbox_belongs_to_its_company_not_to_who_connected_it(world):
    """Der Abgleich ändert das Postfach – das steht im Verlauf der Gesellschaft, nicht in dem
    der Person, die es verbunden hat. Bug-Form: ``owner_object_id`` als Ding der Zeile."""
    from app.models import Log, Mailbox
    db, staff = world
    box = Mailbox(channel="c999999955", address=f"v{staff.object_id}@x.ch",
                  owner_object_id=staff.object_id, token="x")
    db.add(box)
    db.flush()
    box.synced_at = datetime.now(timezone.utc)
    db.flush()
    rows = db.query(Log).filter(Log.table_name == "mailboxes", Log.row_key == str(box.id)).all()
    assert len(rows) == 2 and {r.object_id for r in rows} == {999999955}


def test_the_events_of_the_ai_have_their_own_place_not_the_history(world):
    """Ein Gespräch (private Worte), ein Handgriff, das Wissen stehen nicht im Verlauf – sie
    haben das «+» und das Angeheftete; andere Ereignisse schon.
    Bug-Form: die Worte eines Gesprächs stehen für jedes Personal im Verlauf."""
    from app.services import log
    db, staff = world
    lea = new_person(db)
    log.event(db, "talk", lea.object_id, {"by": "person", "text": "geheime Notiz"})
    log.event(db, "handgriff", lea.object_id, {"method": "PATCH", "path": "/x", "line": "Telefon"})
    log.event(db, "document.read", lea.object_id, {"x": "sichtbar"})
    db.flush()
    events = [r.event for e in history.page(db, lea.object_id, staff, limit=50).entries
              if e.change for r in e.change.rows if r.event]
    assert "document.read" in events
    assert not {"talk", "handgriff"} & set(events)
