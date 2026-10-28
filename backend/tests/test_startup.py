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
