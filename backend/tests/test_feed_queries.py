"""►►► **Eine Liste kostet nicht eine Abfrage je Zeile** (Feed, «zu tun», Firmen, Dokumente). ◄◄◄

Gemessen wird die Zahl der SQL-Anweisungen für wenige und für viele Zeilen: sie darf nicht
mit der Zahl der Zeilen wachsen. Bug-Form: je Zeile eine Abfrage (Adressen, Firma, Betreiber,
Personen der Firma, Datei-Link).
"""

import random
from contextlib import contextmanager

from sqlalchemy import event

from app.models import UserProfile
from app.routers import admin, erp
from app.services import todo
from tests.factories import new_firm, new_person


@contextmanager
def _counted(db):
    seen: list[str] = []

    def count(_conn, _cur, statement, *_a):
        seen.append(statement)
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", count)


def _firms(db, n: int) -> list:
    out = []
    for _ in range(n):
        firm = new_firm(db, f"Q{random.randint(1, 10**9)}")
        new_person(db, company=firm.object_id)
        out.append(firm)
    return out


def test_the_company_list_does_not_ask_per_company(db):
    _firms(db, 2)
    db.expire_all()
    with _counted(db) as few:
        admin.list_companies(db=db, _=None)
    _firms(db, 8)
    db.expire_all()
    with _counted(db) as many:
        admin.list_companies(db=db, _=None)
    assert len(many) == len(few), (len(few), len(many))


def test_the_people_feed_and_todo_do_not_ask_per_person(db, monkeypatch):
    _firms(db, 3)
    db.expire_all()
    with _counted(db) as few:
        erp.list_erp_records(db=db, _=None)
    _firms(db, 8)
    db.expire_all()
    with _counted(db) as many:
        erp.list_erp_records(db=db, _=None)
    assert len(many) == len(few), (len(few), len(many))
    staff = db.query(UserProfile).filter(UserProfile.role == "admin").first() or UserProfile(
        role="employee", object_id=None)
    db.expire_all()
    with _counted(db) as before:
        todo.todo(db, staff)
    _firms(db, 8)
    db.expire_all()
    with _counted(db) as after:
        todo.todo(db, staff)
    assert len(after) <= len(before) + 2, (len(before), len(after))
