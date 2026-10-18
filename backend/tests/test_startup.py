"""►►► **Der Start repariert – er vernichtet nichts, und er ernennt niemanden** (Cleanup
Oktober 2026, Paket 2). ◄◄◄

Gefahren gegen echtes PostgreSQL. Jede Prüfung nennt die Regel und ist gegen ihre
Bug-Form gegengeprüft.
"""

import random

from sqlalchemy import text

from app import main
from app.core import auth
from app.core.database import engine
from app.models import UserProfile
from tests.runner import session


def test_a_misshaped_core_table_is_reported_and_keeps_its_rows(monkeypatch, capsys):
    """Passt eine Prozess-Tabelle nicht zum Modell, steht es im Log – ihre Zeilen bleiben.
    Vorher: ``DROP TABLE … CASCADE`` auf ``orders``, ``process_events`` & Co."""
    session()   # Schema herrichten
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM process_events")).scalar()
    monkeypatch.setattr(main, "_shape_problem",
                        lambda _i, table, _m: "fremde Pflichtspalten: x"
                        if table == "process_events" else None)
    main._check_core_tables_shape()
    with engine.connect() as conn:
        after = conn.execute(text("SELECT count(*) FROM process_events")).scalar()
    assert after == before
    assert "process_events passt nicht zum Modell" in capsys.readouterr().out


def test_a_failing_repair_does_not_take_the_others_with_it(monkeypatch, capsys):
    """Jede Daten-Reparatur hat ihren Savepoint: scheitert eine, laufen die übrigen."""
    ran = []

    def broken(conn, _t, _i):
        conn.execute(text("SELECT * FROM table_that_does_not_exist"))

    def fine(conn, _t, _i):
        conn.execute(text("SELECT 1"))
        ran.append("fine")
    monkeypatch.setattr(main, "_DATA_REPAIRS", (("kaputt", broken), ("heil", fine)))
    main._ensure_columns()
    assert ran == ["fine"]
    assert "Daten-Reparatur «kaputt» fehlgeschlagen" in capsys.readouterr().out


def test_nobody_becomes_admin_by_being_first(monkeypatch):
    """Admin wird nur ``initial_admin_email`` – auch wenn es (noch) keinen Admin gibt.
    Vorher war auf einer leeren Datenbank Admin, wer sich als Erster anmeldete."""
    db = session()
    try:
        db.query(UserProfile).filter(UserProfile.role == "admin").update(
            {UserProfile.role: "employee"}, synchronize_session=False)
        db.flush()
        oid = random.randint(900_000_000, 999_999_999)
        monkeypatch.setattr(auth.settings, "initial_admin_email", f"boss{oid}@x.ch")
        u = auth._create_user(db, f"uid-{oid}", f"first{oid}@x.ch", {})
        assert u.role == "user"
        auth._sync_user_profile(db, u, u.email, {})
        assert u.role == "user"
        boss = auth._create_user(db, f"uid-b{oid}", f"BOSS{oid}@x.ch", {})
        assert boss.role == "admin"
    finally:
        db.rollback()
        db.close()
