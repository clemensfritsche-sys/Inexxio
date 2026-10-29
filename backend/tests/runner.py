"""Die Fälle fahren – **eine** Stelle, zwei Leser (Wächter und Bericht).

Jeder Fall bekommt eine eigene Sitzung und wird danach zurückgerollt. Das ist keine
Bequemlichkeit: Fälle, die aufeinander aufbauen, verdecken genau die Fehler, die zwischen
den Schritten entstehen – und ein fehlgeschlagener Fall dürfte die folgenden nicht
verfärben.
"""

import os
import pathlib
from typing import Optional

from tests.matrix import CASES
from tests.scenarios import Case, Result, World

BACKEND = pathlib.Path(__file__).resolve().parents[1]


_SCHEMA_READY = False
_NO_DATABASE: Optional[str] = None

# In der CI ist die Datenbank PFLICHT (``INEXXIO_REQUIRE_DB=1``): fehlt sie, ist das ein
# Fehler, kein Skip – sonst gingen rund 300 Prüfungen still auf «skipped», und der Job
# bliebe grün. Lokal ohne PostgreSQL überspringen sie sich mit Grund.
REQUIRE_DB = os.environ.get("INEXXIO_REQUIRE_DB") == "1"


def no_database(reason: str):
    """Keine Datenbank: in der CI ein Fehler, lokal ein Skip mit Grund – an EINER Stelle."""
    import pytest

    message = (f"Kein PostgreSQL erreichbar ({reason}) – DATABASE_URL setzen, damit "
               f"diese Regeln wirklich laufen.")
    if REQUIRE_DB:
        pytest.fail(f"{message} (INEXXIO_REQUIRE_DB=1: die Datenbank ist Pflicht)",
                    pytrace=False)
    pytest.skip(message)


def session():
    """Eine Sitzung gegen echtes PostgreSQL – die EINE Stelle, an der Tests sie holen.

    **Das Schema kommt genau einmal aus den Migrationen** – wie im Betrieb
    (``alembic upgrade head``, dann die Trigger aus der Fachschicht wie beim Start). Fehlt
    die Datenbank, entscheidet ``no_database`` (und merkt es sich: ein zweiter
    Verbindungsversuch je Test kostete nur Zeit).
    """
    global _SCHEMA_READY, _NO_DATABASE
    import sys

    if _NO_DATABASE:
        no_database(_NO_DATABASE)
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    from sqlalchemy.exc import OperationalError

    from app.core.database import SessionLocal, engine

    if not _SCHEMA_READY:
        import subprocess

        import app.main as main

        if not str(engine.url).startswith("postgresql"):
            _NO_DATABASE = f"{engine.url.drivername} statt PostgreSQL"
            no_database(_NO_DATABASE)
        try:
            engine.connect().close()
        except OperationalError as exc:
            _NO_DATABASE = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
            no_database(_NO_DATABASE)
        env = {**os.environ, "DATABASE_URL": engine.url.render_as_string(hide_password=False)}
        run = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
                             env=env, capture_output=True, text=True)
        assert run.returncode == 0, f"alembic upgrade head scheiterte:\n{run.stderr[-3000:]}"
        with SessionLocal() as db:
            main._sync_database_rules(db)
            db.commit()
        _SCHEMA_READY = True
    return SessionLocal()


def run_case(case: Case, *, keep: bool = False) -> Result:
    """Einen Fall fahren.

    ``keep`` **committet** einen erfolgreich gelaufenen Fall, statt ihn zurückzurollen.
    Das ist der Weg, aus der Matrix einen echten Datenbestand zu machen, über den die
    Invarianten laufen können – ein Fall, der scheiterte, bleibt trotzdem draussen: sein
    Halbzustand wäre ein erfundener Befund.
    """
    if case.impossible:
        return Result(case=case, verdict="unmöglich")
    db = session()
    result = Result(case=case)
    try:
        result.ist = case.run(World(db)) or {}
        if case.open_finding:
            # Ein bekannter Befund: die Abweichung ist erwartet – ihr **Ausbleiben**
            # nicht. Wer ihn behebt, entfernt die Markierung; bis dahin ist der Fall
            # sichtbar offen und die CI trotzdem grün.
            result.verdict = "offen" if result.diffs else "behoben"
        else:
            result.verdict = "abweichung" if result.diffs else "ok"
    except Exception as exc:                                   # noqa: BLE001
        result.verdict = "fehler"
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            if keep and result.verdict == "ok":
                db.commit()
            else:
                db.rollback()
        except Exception:                                      # noqa: BLE001
            db.rollback()
        finally:
            db.close()
    return result


def run_all(only: Optional[set[str]] = None, *, keep: bool = False) -> list[Result]:
    return [run_case(c, keep=keep) for c in CASES if not only or c.id in only]
