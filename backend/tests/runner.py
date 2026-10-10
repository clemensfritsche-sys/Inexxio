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


def session():
    """Eine Sitzung gegen echtes PostgreSQL.

    **Das Schema wird genau einmal hergerichtet.** ``_ensure_columns`` nimmt
    ACCESS-EXCLUSIVE-Sperren; bei jedem Aufruf hiesse das, dass zwei gleichzeitige
    Sitzungen (der Nebenläufigkeits-Fall) einander blockieren, bevor sie überhaupt bei der
    Fachlogik sind – und der Test hinge an einer Sperre, die mit der Regel nichts zu tun
    hat.
    """
    global _SCHEMA_READY
    import sys

    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    from app.core.database import Base, SessionLocal, engine

    if not _SCHEMA_READY:
        import app.main as main

        Base.metadata.create_all(engine)
        main._ensure_columns()
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
