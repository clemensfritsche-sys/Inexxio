"""►►► **Aufgaben – wer macht was** (Projektakte `docs/konzept/aufgaben.md`). ◄◄◄

Gefahren über den echten Dienst (``services/tasks``) gegen echtes PostgreSQL. Jeder Wächter
nennt seine Bug-Form:

- eine Aufgabe bei zwei Personen · eine Person mit zwei Aufgaben (unmöglich, nicht verboten)
- zugeteilt ohne Kompetenz · eine Kompetenz ohne Person
- nicht das früheste Datum zuerst (Arztpraxis-Modell)
- die Kompetenz folgt nicht dem Ort
- Anwesenheit: Neues ohne Einstempeln · Absenz behält die Aufgabe
- Abgeben: dieselbe Aufgabe kommt sofort zurück
- Sichtbarkeit: fremde Aufgaben für Mitarbeitende, verwaiste ohne «!»
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.domain import competences as comp
from app.domain import modules
from app.domain.errors import Conflict, Invalid
from app.models import TaskFocus, UserProfile
from app.schemas.communication import MessageIn
from app.schemas.timekeeping import EntryIn
from app.services import communication, people, tasks
from app.services import timekeeping as tk
from tests.factories import new_person, post_office
from tests.test_timekeeping import NOW, TODAY, _admin, _company, _contract, _stamp

TALK = comp.KOMMUNIZIEREN


def _staff(db, *competences: str, role: str = "employee") -> UserProfile:
    return new_person(db, role, competences=list(competences))


def _mail(db, actor: UserProfile, *, minutes_ago: int, subject: str):
    """Eine Mail eines Kunden an uns – offen, bis wir antworten."""
    customer = new_person(db, "user")
    sender = db.query(UserProfile).filter(UserProfile.object_id == customer.object_id).one()
    at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    communication.create(db, MessageIn(channel="c999999990", subject=subject, body="?", at=at),
                         sender)
    return customer


def _focus(db) -> dict[int, str]:
    return {r.person_object_id: r.task_key
            for r in db.query(TaskFocus).filter(TaskFocus.task_key.isnot(None)).all()}


def _only(db, *people: UserProfile) -> None:
    """Nur diese Personen sind Personal – was die Datenbank sonst noch kennt, stört nicht."""
    keep = [p.id for p in people]
    db.execute(text("UPDATE user_profiles SET role = 'user' WHERE role IN ('admin', 'employee') "
                    "AND NOT (id = ANY(:keep))"), {"keep": keep})
    db.flush()


@pytest.fixture()
def office(db, monkeypatch):
    post_office(db, monkeypatch)
    # Die Stammdaten der Testpersonen sind unvollständig – das wären eigene Aufgaben, die hier
    # nur stören (geprüft wird anderswo, dass sie entstehen).
    monkeypatch.setattr(people, "missing_fields", lambda u: [])
    return db


# ─── Kompetenzen ───────────────────────────────────────────────────────────────────────

def test_every_module_names_its_competence_and_a_step_may_choose_another():
    """Bug-Formen: ein Modul ohne Vorgabe (dessen Schritte bekäme jeder); die Wahl am Schritt
    wird nicht gespeichert oder speichert die Vorgabe doppelt; ein unbekanntes Wort geht durch."""
    for m in modules.MODULES.values():
        assert m.competence in comp.COMPETENCES, m.key
    move = modules.get("bewegen")
    assert move.competence_of(move.clean_step(None)) == comp.BEWEGEN
    chosen = move.clean_step({"competence": "Elektrik"})
    assert (chosen or {}).get("competence") == "Elektrik"
    assert move.competence_of(chosen) == "Elektrik"
    assert "competence" not in (move.clean_step({"competence": comp.BEWEGEN}) or {})
    with pytest.raises(Invalid):
        move.clean_step({"competence": "Zaubern"})


def test_the_last_person_cannot_lose_a_competence(db):
    """Bug-Formen: eine Kompetenz ohne Person; ein Kunde bekommt Kompetenzen."""
    lea = _staff(db, "Kranprüfung")
    with pytest.raises(Invalid):
        tasks.set_competences(db, lea, [])
    nico = _staff(db)
    tasks.set_competences(db, nico, ["Kranprüfung"])
    tasks.set_competences(db, lea, [])
    assert lea.competences == [] and nico.competences == ["Kranprüfung"]
    with pytest.raises(Invalid):
        tasks.set_competences(db, new_person(db, "user"), [TALK])


# ─── Die Kompetenz folgt dem Ort ───────────────────────────────────────────────────────

def test_a_mail_from_outside_is_a_task_at_the_customer_for_whoever_can_communicate(office):
    db = office
    lea = _staff(db, TALK)
    customer = _mail(db, lea, minutes_ago=5, subject="Prüftermin")
    found = [t for t in tasks.collect(db) if t.object_id == customer.object_id]
    assert len(found) == 1
    task = found[0]
    assert task.part == "kommunikation" and task.competence == TALK and task.only is None


# ─── Zuteilung ─────────────────────────────────────────────────────────────────────────

def test_one_task_per_person_one_person_per_task_earliest_first(office):
    """Bug-Formen: zwei Personen an einer Aufgabe; eine Person mit zweien; die jüngere zuerst;
    jemand ohne Kompetenz bekommt sie."""
    db = office
    lea, marco, nico = _staff(db, TALK), _staff(db, TALK), _staff(db)
    _only(db, lea, marco, nico)
    old = _mail(db, lea, minutes_ago=90, subject="Alt")
    new = _mail(db, lea, minutes_ago=10, subject="Neu")
    tasks.dispatch(db)
    focus = _focus(db)
    assert nico.object_id not in focus
    keys = [focus.get(lea.object_id), focus.get(marco.object_id)]
    assert sorted(k.split(":")[1] for k in keys) == sorted(
        [str(old.object_id), str(new.object_id)])
    assert len(set(keys)) == 2
    first = min((lea, marco), key=lambda p: p.object_id)       # gleich lange frei
    assert focus[first.object_id].startswith(f"msg:{old.object_id}:")
    with pytest.raises(Exception):
        db.add(TaskFocus(person_object_id=nico.object_id, task_key=keys[0],
                         since=datetime.now(timezone.utc)))
        db.flush()


def test_handing_back_gives_it_to_the_next_and_not_back_at_once(office):
    db = office
    lea, marco = _staff(db, TALK), _staff(db, TALK)
    _only(db, lea, marco)
    _mail(db, lea, minutes_ago=30, subject="Eins")
    tasks.dispatch(db)
    holder = next(p for p in (lea, marco) if p.object_id in _focus(db))
    other = marco if holder is lea else lea
    key = _focus(db)[holder.object_id]
    tasks.hand(db, holder, key)
    focus = _focus(db)
    assert focus.get(other.object_id) == key and holder.object_id not in focus
    with pytest.raises(Conflict):
        tasks.hand(db, holder, key)


def test_a_task_that_nobody_present_can_do_shows_to_everyone(office):
    """Bug-Formen: eine verwaiste Aufgabe ist unsichtbar; eine Mitarbeiterin sieht fremde."""
    db = office
    lea = _staff(db, TALK)
    nico = _staff(db, "Kranprüfung")
    admin = _staff(db, "Kranprüfung", role="admin")
    _only(db, lea, nico, admin)
    customer = _mail(db, lea, minutes_ago=5, subject="Frage")
    view = tasks.view(db, nico)
    assert not [m for m in view.visible if m.object_id == customer.object_id], (
        "Die Mail hat Lea – Nico sieht sie nicht.")
    assert [m for m in tasks.view(db, admin).visible if m.object_id == customer.object_id]
    mine = tasks.view(db, lea)
    assert mine.mine is not None and mine.mine.object_id == customer.object_id
    lea.competences = []
    nico.competences = ["Kranprüfung", TALK]
    tasks.dispatch(db)
    nico.competences = ["Kranprüfung"]
    db.flush()
    tasks.hand(db, nico, f"msg:{customer.object_id}:" + _focus(db)[nico.object_id].split(":")[2])
    orphan = [m for m in tasks.view(db, nico).visible if m.object_id == customer.object_id]
    assert orphan and orphan[0].orphan, "Niemand da kann sie – «!» für alle."


# ─── Anwesenheit in drei Sätzen ────────────────────────────────────────────────────────

def test_presence_in_three_sentences(db, monkeypatch):
    """Satz 1: ohne Einstempeln nichts Neues (ohne Zeiterfassung: da). Satz 2: was man hat,
    bleibt. Satz 3: ausser bei einer Absenz."""
    monkeypatch.setattr(tk, "now_utc", lambda: NOW)
    co = _company(db)
    admin = _admin(db, co)
    lena = new_person(db, "employee", company=co, date_of_birth=date(1990, 6, 11))
    now = NOW.astimezone(timezone.utc)
    assert tasks.presence(db, admin, now).here, "Ohne Zeiterfassung gilt man als da."
    _contract(db, admin, lena, date(2026, 10, 1))
    seen = tasks.presence(db, lena, now)
    assert not seen.here and not seen.absent, "Nicht eingestempelt: nichts Neues, nichts weg."
    _stamp(db, lena, lena, TODAY, "07:30")
    assert tasks.presence(db, lena, now).here
    ill = new_person(db, "employee", company=co, date_of_birth=date(1991, 2, 3))
    _contract(db, admin, ill, date(2026, 10, 1))
    tk.record(db, ill, ill, EntryIn(kind="absence", art="krank", day=TODAY))
    assert tasks.presence(db, ill, now).absent, "Absenz: was sie hat, geht weiter."
