"""Gemeinsame Test-Infrastruktur – die EINE Datenbank-Fixture.

Eine Sitzung holt jeder Test über ``tests.runner.session()`` (direkt) oder über die
Fixture ``db`` (sie rollt danach zurück und schliesst). Eigene ``_db()``-Kopien je Datei
gibt es nicht mehr: zwölf Kopien verhielten sich ohne PostgreSQL verschieden – 208 Tests
übersprangen sich, 80 wurden rot.

**In der CI ist die Datenbank Pflicht** (``INEXXIO_REQUIRE_DB=1``): ist sie nicht
erreichbar, bricht der Lauf sofort mit einem Satz ab, statt still ~300 Prüfungen zu
überspringen. Lokal ohne PostgreSQL überspringen sie sich mit Grund (``pytest -rs``
zeigt jeden).
"""

import pytest

from tests import runner


def pytest_sessionstart(session):
    """Pflicht-Datenbank: einmal am Anfang prüfen, nicht 300-mal einzeln scheitern."""
    if not runner.REQUIRE_DB:
        return
    import os

    from sqlalchemy import text

    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")

    from app.core.database import engine
    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1"))
    except Exception as exc:                                   # noqa: BLE001
        pytest.exit(f"INEXXIO_REQUIRE_DB=1, aber kein PostgreSQL erreichbar "
                    f"({type(exc).__name__}: {str(exc).splitlines()[0]}).", returncode=1)


@pytest.fixture
def db():
    """Eine Sitzung gegen echtes PostgreSQL, danach zurückgerollt und geschlossen."""
    s = runner.session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
