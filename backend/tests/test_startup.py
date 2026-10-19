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


def test_a_failing_repair_does_not_take_the_others_with_it(db, monkeypatch, capsys):
    """Jede Daten-Reparatur hat ihren Savepoint: scheitert eine, laufen die übrigen.
    (``db``: die Reparaturen laufen gegen die echte Datenbank.)"""
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


def _start_code() -> str:
    """Der **Code** von ``main.py`` – ohne Kommentare und Docstrings, die die entfernten
    Netze ja gerade beschreiben."""
    import ast
    import pathlib
    src = pathlib.Path(main.__file__).read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                src = src.replace(doc, "")
    return "\n".join(line.split("#")[0] for line in src.splitlines())


def test_the_start_drops_no_column_and_writes_no_unmapped_one():
    """►►► **Der Start doppelt keine Migration, die längst gelaufen ist** (Cleanup B-20,
    B-22, B-23). ◄◄◄ Das Drop-Netz lief bei jedem Start ``DROP COLUMN IF EXISTS`` über
    28 Spalten (je ein ACCESS-EXCLUSIVE-Lock), die Übernahme der Firmentexte dropte acht
    weitere, und der Artikel-Status wurde nachgeführt, obwohl ihn seit Migration 121 kein
    Modell mehr kennt. Gedroppt wird in einer Migration, nicht beim Start.

    Bug-Formen: (a) ein ``DROP COLUMN`` steht wieder im Start-Code; (b) der Start schreibt
    ``articles.status``; (c) die Firmentext-Übernahme läuft wieder im Netz."""
    code = _start_code()
    assert "DROP COLUMN" not in code, "Der Start droppt wieder Spalten (a)."
    assert "UPDATE articles SET status" not in code, "Der Start schreibt articles.status (b)."
    assert "move_company_texts" not in code, "Die Firmentext-Übernahme ist zurück im Netz (c)."


_CORRECTS_FKS = (
    "SELECT c.conname FROM pg_constraint c JOIN pg_attribute a "
    "ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
    "WHERE c.conrelid = 'vouchers'::regclass AND c.contype = 'f' "
    "AND a.attname = 'corrects_id'")


def test_the_correction_reference_gets_its_index_and_key_from_the_net():
    """►►► **Index und Fremdschlüssel von ``vouchers.corrects_id`` stehen im Netz**
    (Cleanup B-52). ◄◄◄ Kam die Spalte über das Spalten-Netz (``alembic upgrade head``
    gescheitert), war sie ein blankes ``BIGINT``: kein Index, und kein Riegel, der einen
    Verweis auf einen gelöschten Beleg auf ``NULL`` setzt. ``create_all`` legt beides nur
    mit einer **neuen** Tabelle an.

    Gefahren auf einer Datenbank, der beides fehlt – in einer Transaktion, die danach
    verworfen wird. Bug-Form: der Netz-Eintrag fehlt → beides bleibt weg."""
    session()   # Schema herrichten
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            for fk in conn.execute(text(_CORRECTS_FKS)).scalars().all():
                conn.execute(text(f"ALTER TABLE vouchers DROP CONSTRAINT {fk}"))
            conn.execute(text("DROP INDEX IF EXISTS ix_vouchers_corrects_id"))
            for stmt in main._RAW_INDEX_SAFETY_NET:
                conn.execute(text(stmt))
            index = conn.execute(text(
                "SELECT 1 FROM pg_indexes WHERE tablename = 'vouchers' "
                "AND indexname = 'ix_vouchers_corrects_id'")).first()
            key = conn.execute(text(
                "SELECT confdeltype FROM pg_constraint WHERE conrelid = 'vouchers'::regclass "
                "AND contype = 'f' AND conname = 'fk_vouchers_corrects'")).scalar()
            # Ein zweiter Lauf legt nichts doppelt an und scheitert nicht.
            for stmt in main._RAW_INDEX_SAFETY_NET:
                conn.execute(text(stmt))
            keys = len(conn.execute(text(_CORRECTS_FKS)).scalars().all())
        finally:
            tx.rollback()
    assert index is not None, "Ohne Netz-Eintrag fehlt ix_vouchers_corrects_id."
    assert key == "n", "Ohne Netz-Eintrag fehlt der Fremdschlüssel (ON DELETE SET NULL)."
    assert keys == 1, f"Der zweite Lauf hat einen zweiten Fremdschlüssel angelegt ({keys})."
