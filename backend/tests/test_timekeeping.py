"""►►► **Zeiterfassung – die Regeln über den echten Dienst, gegen echtes PostgreSQL.** ◄◄◄

Jede Prüfung nennt ihr Soll vorher (docs/zeiterfassung-spezifikation.md). «Heute» ist fest:
Freitag, 23.10.2026, 12:33 in Zürich – die Zeit kommt immer vom Server
(``timekeeping.now_utc``), darum genügt es, sie hier zu setzen.
"""

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.domain import timekeeping as tk
from app.models import CompanySettings, Holiday, TimeEntry, UserProfile
from app.schemas.timekeeping import ContractIn, EntryIn
from app.services import people, time_view, timekeeping as t, todo

NOW = datetime(2026, 10, 23, 12, 33, tzinfo=tk.ZONE)
TODAY = NOW.date()


@pytest.fixture()
def clock(monkeypatch):
    state = {"now": NOW}
    monkeypatch.setattr(t, "now_utc", lambda: state["now"].astimezone(tk.ZONE))
    return state


def _company(db) -> int:
    oid = random.randint(900_000_000, 999_999_999)
    db.add(CompanySettings(object_id=oid, company_name=f"Test {oid}", legal_form="AG",
                           is_own=True, email=""))
    db.flush()
    return oid


def _person(db, company, role="employee", born=date(1990, 6, 11)) -> UserProfile:
    oid = random.randint(900_000_000, 999_999_999)
    u = UserProfile(firebase_uid=f"uid-{oid}", email=f"p{oid}@x.ch", role=role, object_id=oid,
                    first_name="P", last_name=str(oid), company_object_id=company,
                    date_of_birth=born, phone="+41 79 000 00 00")
    db.add(u)
    db.flush()
    return u


def _admin(db, company) -> UserProfile:
    return _person(db, company, role="admin")


def _contract(db, admin, p, start, hours=42, days=(0, 1, 2, 3, 4), weeks=None):
    t.add_contract(db, admin, p, ContractIn(valid_from=start, weekly_minutes=hours * 60,
                                            workdays=list(days), vacation_weeks=weeks))


def _stamp(db, actor, p, d, hhmm, kind="in"):
    t.record(db, actor, p, EntryIn(kind=kind, day=d, time=hhmm))


def _day(db, actor, p, d, pairs):
    for a, b in pairs:
        _stamp(db, actor, p, d, a, "in")
        _stamp(db, actor, p, d, b, "out")


def _view(db, actor, p, month="2026-10"):
    return time_view.view(db, actor, p, month)


def _days(v):
    return {d.day: d for d in v.days}


@pytest.fixture()
def world(db, clock):
    co = _company(db)
    admin = _admin(db, co)
    lena = _person(db, co)
    return db, co, admin, lena


# ─── Soll, Ist, Konto ───────────────────────────────────────────────────────────────

def test_soll_is_weekly_hours_divided_by_workdays(world):
    """Soll: 25 h an Mo–Mi = 8:20 h je Tag; Do/Fr kein Arbeitstag."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1), hours=25, days=(0, 1, 2))
    days = _days(_view(db, lena, lena))
    assert days[date(2026, 10, 19)].soll == 500
    assert days[date(2026, 10, 22)].soll == 0 and not days[date(2026, 10, 22)].workday


def test_account_is_until_yesterday_and_today_runs(world):
    """Stundenkonto = Saldo bis gestern; heute zählt erst ab morgen."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 22))
    _day(db, lena, lena, date(2026, 10, 22), [("07:00", "12:00"), ("12:30", "16:00")])
    _stamp(db, lena, lena, TODAY, "07:00")
    v = _view(db, lena, lena)
    assert v.account == 8 * 60 + 30 - 504          # gestern: 8:30 h gegen 8:24 h
    assert v.present_since == "07:00" and v.today_ist == 5 * 60 + 33


def test_holiday_has_no_soll_and_vacation_is_not_taken_on_it(world):
    """Feiertag: Soll 0 – Ferien über den Feiertag ziehen dort nichts ab."""
    db, co, admin, lena = world
    db.add(Holiday(company_object_id=co, day=date(2026, 10, 14), name="Ortsfeiertag"))
    db.flush()
    _contract(db, admin, lena, date(2026, 10, 1))
    t.record(db, lena, lena, EntryIn(kind="absence", art="ferien", day=date(2026, 10, 19),
                                     until=date(2026, 10, 23)))
    led = t.ledger(t.load(db, lena), TODAY, t.now_utc())
    assert led.days[date(2026, 10, 14)].soll == 0
    used = sum(d.vacation_used for d in led.days.values())
    assert used == 5 * 504
    # Ferien über den Feiertag: nur die Arbeitstage zählen
    t.record(db, admin, lena, EntryIn(kind="absence", art="ferien", day=date(2026, 10, 12),
                                      until=date(2026, 10, 16)))
    led = t.ledger(t.load(db, lena), TODAY, t.now_utc())
    assert led.days[date(2026, 10, 14)].vacation_used == 0


def test_sick_during_vacation_gives_the_vacation_back(world):
    """Krank in den Ferien: die neuere Absenz ersetzt an ihren Tagen die ältere."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    t.record(db, lena, lena, EntryIn(kind="absence", art="ferien", day=date(2026, 11, 16),
                                     until=date(2026, 11, 20)))
    t.record(db, lena, lena, EntryIn(kind="absence", art="krank", day=date(2026, 11, 18),
                                     until=date(2026, 11, 19)))
    led = t.ledger(t.load(db, lena), date(2026, 11, 30), t.now_utc())
    assert [led.days[date(2026, 11, d)].vacation_used for d in range(16, 21)] == \
        [504, 504, 0, 0, 504]
    days = _days(_view(db, lena, lena, "2026-11"))
    assert days[date(2026, 11, 18)].absence.replaces.startswith("Ersetzt «Ferien")


def test_contract_change_in_the_middle_of_an_absence_counts_per_day(world):
    """Vertragswechsel mitten in den Ferien: jeder Tag mit seinem Vertrag."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    _contract(db, admin, lena, date(2026, 11, 18), hours=21, days=(0, 1, 2))
    t.record(db, lena, lena, EntryIn(kind="absence", art="ferien", day=date(2026, 11, 16),
                                     until=date(2026, 11, 20)))
    led = t.ledger(t.load(db, lena), date(2026, 11, 30), t.now_utc())
    assert [round(led.days[date(2026, 11, d)].vacation_used) for d in range(16, 21)] == \
        [504, 504, 420, 0, 0]


def test_exit_freezes_the_closing_balance(world):
    """Austritt = 0 h: ab dann kein Soll, keine Ferien; Schlussstand am Vortag."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    _contract(db, admin, lena, date(2026, 10, 20), hours=0, days=())
    v = _view(db, admin, lena)
    exit_ = next(c for c in v.contracts if c.weekly_minutes == 0)
    assert exit_.closing_day == date(2026, 10, 19)
    assert exit_.closing_account == -13 * 504         # 13 Arbeitstage ohne Stempel
    assert _days(v)[date(2026, 10, 21)].soll == 0
    with pytest.raises(HTTPException) as e:
        _stamp(db, lena, lena, date(2026, 10, 21), "07:00")
    assert "kein Vertrag" in e.value.detail


def test_vacation_accrues_daily_across_the_year_end(world, clock):
    """Ferien wachsen jeden Kalendertag – kein Reset zum Jahreswechsel."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 12, 1), weeks=Decimal(5))
    clock["now"] = datetime(2027, 1, 31, 12, 0, tzinfo=tk.ZONE)
    led = t.ledger(t.load(db, lena), date(2027, 1, 31), t.now_utc())
    assert round(led.vacation) == round(62 * 5 * 42 * 60 / 365)


def test_legal_minimum_applies_until_the_20th_birthday(world):
    """Mindestferien: bis zum 20. Geburtstag 5 Wochen – weniger weist der Vertrag ab."""
    db, co, admin, _ = world
    young = _person(db, co, born=date(2008, 3, 14))
    with pytest.raises(HTTPException) as e:
        _contract(db, admin, young, date(2026, 10, 1), weeks=Decimal(4))
    assert "5 Wochen" in e.value.detail
    _contract(db, admin, young, date(2026, 10, 1))
    assert t.load(db, young).contracts[0].vacation_weeks == 5


# ─── Stempel ────────────────────────────────────────────────────────────────────────

def test_swipe_is_idempotent_and_ignores_a_double_swipe(world, clock):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    t.swipe(db, lena, lena, "in", "key-0000001")
    t.swipe(db, lena, lena, "in", "key-0000001")            # dasselbe Netzpaket
    clock["now"] = NOW + timedelta(seconds=20)
    t.swipe(db, lena, lena, "out", "key-0000002")           # Doppelklick
    stamps = [r for r in t.load(db, lena).live if r.kind in tk.STAMPS]
    assert [s.kind for s in stamps] == ["in"]
    clock["now"] = NOW + timedelta(hours=4)
    t.swipe(db, lena, lena, "out", "key-0000003")
    t.swipe(db, lena, lena, "out", "key-0000004")           # zweites Gerät, schon weg
    assert [s.kind for s in t.load(db, lena).live if s.kind in tk.STAMPS] == ["in", "out"]


def test_a_forgotten_out_leaves_the_day_open_and_the_next_swipe_is_in(world, clock):
    """Kommen ohne Gehen: nach 14 h ist der Tag offen (Aufgabe), der Knopf zeigt Kommen."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    _stamp(db, lena, lena, date(2026, 10, 22), "07:45")
    b = t.load(db, lena)
    assert t.running(b, t.now_utc()) is None
    assert [k for k, _, _ in t.tasks(b, t.now_utc())] == ["open"]
    t.swipe(db, lena, lena, "in", "key-0000010")
    v = _view(db, lena, lena)
    assert v.default_day == date(2026, 10, 22)
    assert _days(v)[date(2026, 10, 22)].open
    # Nachtragen schliesst ihn
    _stamp(db, lena, lena, date(2026, 10, 22), "16:30", "out")
    assert t.tasks(t.load(db, lena), t.now_utc()) == []


def test_out_after_midnight_belongs_to_the_day_of_in(world):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1), days=range(7))
    _stamp(db, lena, lena, date(2026, 10, 20), "22:00")
    _stamp(db, lena, lena, date(2026, 10, 20), "02:00", "out")
    d = t.ledger(t.load(db, lena), TODAY, t.now_utc()).days[date(2026, 10, 20)]
    assert d.ist == 240 and "night" in d.hints


def test_dst_change_counts_the_real_hours(world, clock):
    """Zeitumstellung 25.10.2026: 00:00–06:00 sind 7 echte Stunden."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1), days=range(7))
    clock["now"] = datetime(2026, 10, 25, 12, 0, tzinfo=tk.ZONE)
    _day(db, lena, lena, date(2026, 10, 25), [("00:00", "06:00")])
    d = t.ledger(t.load(db, lena), date(2026, 10, 31), t.now_utc()).days[date(2026, 10, 25)]
    assert d.ist == 7 * 60


def test_sequence_future_and_full_day_absence_are_refused(world):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    with pytest.raises(HTTPException) as e:
        _stamp(db, lena, lena, date(2026, 10, 21), "17:00", "out")
    assert "fehlt «Kommen»" in e.value.detail
    with pytest.raises(HTTPException) as e:
        _stamp(db, lena, lena, TODAY, "18:00")
    assert e.value.detail == "Liegt in der Zukunft – jetzt ist es 12:33."
    t.record(db, lena, lena, EntryIn(kind="absence", art="krank", day=date(2026, 10, 21)))
    with pytest.raises(HTTPException) as e:
        _stamp(db, lena, lena, date(2026, 10, 21), "07:00")
    assert "ganzer Tag" in e.value.detail


def test_an_unchanged_edit_records_nothing_and_a_change_is_marked(world):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    _day(db, lena, lena, date(2026, 10, 21), [("07:55", "16:30")])
    first = next(r for r in t.load(db, lena).live if r.kind == "in")
    n = db.query(TimeEntry).filter(TimeEntry.person_object_id == lena.object_id).count()
    t.record(db, lena, lena, EntryIn(kind="in", replaces_id=first.id, time="07:55"))
    assert db.query(TimeEntry).filter(TimeEntry.person_object_id == lena.object_id).count() == n
    t.record(db, lena, lena, EntryIn(kind="in", replaces_id=first.id, time="07:35"))
    stamp = _days(_view(db, lena, lena))[date(2026, 10, 21)].stamps[0]
    assert stamp.time == "07:35" and stamp.mark.kind == "changed"
    assert stamp.mark.tip.startswith("Vorher 07:55")


def test_seven_day_rule_locks_the_employee_not_the_admin(world):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    with pytest.raises(HTTPException) as e:
        _day(db, lena, lena, date(2026, 10, 15), [("07:00", "16:00")])
    assert e.value.status_code == 403 and "abgeschlossen" in e.value.detail
    _day(db, admin, lena, date(2026, 10, 15), [("07:00", "16:00")])
    days = _days(_view(db, lena, lena))
    assert days[date(2026, 10, 15)].locked and not days[date(2026, 10, 16)].locked
    assert days[date(2026, 10, 15)].stamps[0].mark.kind == "added"
    assert not any(d.locked for d in _view(db, admin, lena).days)


def test_only_self_and_admin_see_the_time(world):
    db, co, admin, lena = world
    other = _person(db, co)
    _contract(db, admin, lena, date(2026, 10, 1))
    assert not t.may_see(other, lena) and t.may_see(admin, lena) and t.may_see(lena, lena)
    with pytest.raises(HTTPException) as e:
        _stamp(db, other, lena, date(2026, 10, 22), "07:00")
    assert e.value.status_code == 403


# ─── Absenzen und Hinweise ──────────────────────────────────────────────────────────

def test_proof_task_appears_from_day_three_and_goes_with_the_upload(world):
    db, co, admin, lena = world
    from app.models import Attachment
    _contract(db, admin, lena, date(2026, 10, 1))
    t.record(db, lena, lena, EntryIn(kind="absence", art="krank", day=date(2026, 10, 19),
                                     until=date(2026, 10, 21)))
    b = t.load(db, lena)
    assert [k for k, _, _ in t.tasks(b, t.now_utc())] == ["proof"]
    db.add(Attachment(token="tok-proof-1", mime="image/jpeg", data=b"x", byte_size=1))
    db.flush()
    a = next(r for r in b.live if r.kind == "absence")
    t.record(db, lena, lena, EntryIn(kind="proof", replaces_id=a.id,
                                     proof_url="/api/v1/attachments/tok-proof-1"))
    assert t.tasks(t.load(db, lena), t.now_utc()) == []


def test_absence_rules(world):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    _day(db, lena, lena, date(2026, 10, 20), [("07:00", "16:00")])
    with pytest.raises(HTTPException) as e:          # Stempel am Tag → nur Stunden
        t.record(db, lena, lena, EntryIn(kind="absence", art="bezahlt", day=date(2026, 10, 20)))
    assert "«Stunden» wählen" in e.value.detail
    t.record(db, lena, lena, EntryIn(kind="absence", art="bezahlt", day=date(2026, 10, 20),
                                     minutes=90, note="Arzt"))
    with pytest.raises(HTTPException) as e:
        t.record(db, lena, lena, EntryIn(kind="absence", art="bezahlt", day=date(2026, 10, 21),
                                         minutes=600))
    assert "Mehr als ein ganzer Tag (8:24 h)" in e.value.detail
    with pytest.raises(HTTPException) as e:
        t.record(db, lena, lena, EntryIn(kind="absence", art="ferien", day=date(2026, 10, 24)))
    assert "kein Arbeitstag" in e.value.detail
    a = next(r for r in t.load(db, lena).live if r.kind == "absence")
    t.record(db, lena, lena, EntryIn(kind="void", replaces_id=a.id))
    assert not [r for r in t.load(db, lena).live if r.kind == "absence"]


def test_unpaid_leave_removes_soll_and_accrual(world):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    t.record(db, lena, lena, EntryIn(kind="absence", art="unbezahlt", day=date(2026, 10, 19)))
    d = t.ledger(t.load(db, lena), TODAY, t.now_utc()).days[date(2026, 10, 19)]
    assert d.soll == 0 and d.accrual == 0 and d.saldo == 0


def test_hints_pause_rest_week_u18_sunday(world):
    db, co, admin, _ = world
    jonas = _person(db, co, born=date(2009, 3, 14))
    _contract(db, admin, jonas, date(2026, 10, 1), days=(0, 1, 2, 3, 4))
    _day(db, admin, jonas, date(2026, 10, 12), [("07:00", "17:00")])     # ohne Pause, > 9 h
    _day(db, admin, jonas, date(2026, 10, 13), [("04:30", "12:00")])     # Ruhe 12 h fehlt, Nacht
    _day(db, admin, jonas, date(2026, 10, 18), [("09:00", "11:00")])     # Sonntag
    led = t.ledger(t.load(db, jonas), TODAY, t.now_utc())
    assert {"pause", "u18"} <= set(led.days[date(2026, 10, 12)].hints)
    assert {"rest", "night"} <= set(led.days[date(2026, 10, 13)].hints)
    assert "sunday" in led.days[date(2026, 10, 18)].hints


def test_bookings_move_account_and_vacation_and_are_admin_only(world):
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 23))
    with pytest.raises(HTTPException):
        t.record(db, lena, lena, EntryIn(kind="booking", day=TODAY, minutes=600, note="x"))
    t.record(db, admin, lena, EntryIn(kind="booking", day=TODAY, minutes=240,
                                      vacation_minutes=1512, note="Übertrag bei Einführung"))
    v = _view(db, lena, lena)
    assert v.account == 240 and v.vacation >= 1512 and v.bookings[0].by == admin.display_name


# ─── Was die Datenbank selbst festhält ──────────────────────────────────────────────

def test_entries_are_append_only_in_the_database(world):
    """Der Trigger verbietet UPDATE und DELETE – Gegenprobe: ohne Trigger ginge es."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    _stamp(db, lena, lena, date(2026, 10, 22), "07:00")
    eid = t.load(db, lena).live[0].id
    sp = db.begin_nested()
    with pytest.raises(Exception, match="nie geändert"):
        db.execute(text("UPDATE time_entries SET minutes = 1 WHERE id = :i"), {"i": eid})
    sp.rollback()
    sp = db.begin_nested()
    db.execute(text("ALTER TABLE time_entries DISABLE TRIGGER trg_time_entries_append_only"))
    db.execute(text("UPDATE time_entries SET minutes = 1 WHERE id = :i"), {"i": eid})
    sp.rollback()


# ─── Pflichtfelder und «zu tun» ─────────────────────────────────────────────────────

def test_required_fields_include_birthdate_for_staff_only(world):
    db, co, admin, lena = world
    lena.date_of_birth = None
    assert [m["key"] for m in people.missing_fields(lena)] == ["date_of_birth", "addresses"]
    lena.role = "user"
    assert [m["key"] for m in people.missing_fields(lena)] == ["addresses"]


def test_todo_counts_time_tasks_for_self_and_admin_only(world):
    db, co, admin, lena = world
    other = _person(db, co)
    _contract(db, admin, lena, date(2026, 10, 1))
    _stamp(db, lena, lena, date(2026, 10, 22), "07:45")
    rows = {r.object_id: r for r in todo.todo(db, admin)}
    assert any(i.section == "zeiterfassung" for i in rows[lena.object_id].items)
    rows = {r.object_id: r for r in todo.todo(db, other)}
    assert not any(i.section == "zeiterfassung" for i in rows[lena.object_id].items)


def test_preview_says_what_an_absence_does_before_it_is_saved(world):
    """Dieselbe Regel wie beim Speichern: Arbeitstage, Stunden, Ersetzt, Ferien danach."""
    db, co, admin, lena = world
    _contract(db, admin, lena, date(2026, 10, 1))
    t.record(db, lena, lena, EntryIn(kind="absence", art="ferien", day=date(2026, 11, 16),
                                     until=date(2026, 11, 20)))
    before = round(t.ledger(t.load(db, lena), TODAY, t.now_utc()).vacation)
    p = t.preview(db, lena, lena, EntryIn(kind="absence", art="krank", day=date(2026, 11, 18),
                                          until=date(2026, 11, 19)))
    assert p["problem"] is None and p["workdays"] == 2 and p["minutes"] == 2 * 504
    # Ferien danach = heute minus alle geplanten: 3 statt 5 Ferientage bleiben geplant.
    assert p["replaces"] == "Ferien an 2 Tagen" and p["vacation_after"] == before - 3 * 504
    p = t.preview(db, lena, lena, EntryIn(kind="absence", art="ferien", day=date(2026, 11, 23),
                                          until=date(2026, 11, 24)))
    assert p["vacation_after"] == before - 7 * 504
    p = t.preview(db, lena, lena, EntryIn(kind="in", day=TODAY, time="18:00"))
    assert p["problem"] == "Liegt in der Zukunft – jetzt ist es 12:33."
