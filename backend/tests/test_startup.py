"""►►► **Der Start baut kein Schema – er vernichtet nichts, und er ernennt niemanden**
(Cleanup Oktober 2026). ◄◄◄

Gefahren gegen echtes PostgreSQL. Jede Prüfung nennt die Regel und ist gegen ihre
Bug-Form gegengeprüft.
"""

import random

from sqlalchemy import text

from app import main
from app.core import auth
from app.models import UserProfile
from tests.runner import session


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


def test_the_start_builds_no_schema():
    """**Das Schema baut allein die Migration** – der Start legt nichts an, ändert keine
    Spalte und löscht nichts (gedroppt wird in einer Migration, nicht beim Start).

    Bug-Formen: ein ``create_all``, ``ALTER TABLE``, ``ADD``/``DROP COLUMN`` oder
    ``DROP TABLE`` steht wieder im Start-Code; der Start schreibt eine Spalte, die kein
    Modell kennt (``articles.status``)."""
    code = _start_code()
    for word in ("create_all", "ALTER TABLE", "ADD COLUMN", "DROP COLUMN", "DROP TABLE",
                 "UPDATE articles SET status"):
        assert word not in code, f"Der Start baut wieder am Schema («{word}»)."


def test_the_start_runs_twice_without_harm():
    """Mehrere Worker und Instanzen starten gegen dieselbe Datenbank: der Start (Trigger,
    Betreiber, Rechtstexte) läuft beliebig oft und legt nichts doppelt an."""
    from fastapi.testclient import TestClient

    from app.models import CompanySettings
    session()   # Schema herrichten
    for _ in range(2):
        with TestClient(main.app):
            pass
    db = session()
    try:
        assert db.query(CompanySettings).filter(CompanySettings.is_operator).count() == 1
        trigger = db.execute(text("SELECT count(*) FROM pg_trigger "
                                  "WHERE tgname = 'trg_instance_units_terminal'")).scalar()
        assert trigger == 1
    finally:
        db.close()


def test_every_database_url_uses_the_installed_driver():
    """Ohne Treiber in der Adresse wählt SQLAlchemy ab 2.1 psycopg 3 – installiert ist
    psycopg2. Ein ``postgresql://`` aus einem Secret liesse den Dienst sonst beim Start
    abstürzen. Bug-Form (gegengeprüft): ohne den Validator bleibt die Adresse, wie sie ist."""
    from app.core.config import Settings
    for raw in ("postgresql://u:p@h/db", "postgres://u:p@h/db"):
        assert Settings(database_url=raw).database_url == "postgresql+psycopg2://u:p@h/db"
    keep = "postgresql+psycopg2://u:p@/db?host=/cloudsql/x"
    assert Settings(database_url=keep).database_url == keep
