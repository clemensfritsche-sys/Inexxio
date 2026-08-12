"""**Die Szenariomatrix als Wächter.** Sie läuft bei jeder Änderung mit.

Die Fälle stehen in ``tests/matrix.py`` – hier steht nur, dass sie laufen müssen. Ein
Fall ist ein Datensatz mit **vorher notiertem Soll**; der Bericht
(``scripts/scenario_report.py``) liest dieselbe Liste und stellt Soll und Ist
nebeneinander.

Warum ein Test je Fall statt einer Schleife: bricht die Matrix, will man den **Namen**
des gebrochenen Falls sehen und nicht «1 von 67 fehlgeschlagen».
"""

import os

import pytest

from tests.matrix import CASES
from tests.runner import run_case, session


def _skip_without_db() -> None:
    try:
        session().close()
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regeln wirklich laufen.")


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_scenario(case):
    """Ein Fall der Matrix – Soll steht in ``matrix.py``, nicht hier."""
    if os.environ.get("INEXXIO_SKIP_MATRIX"):
        pytest.skip("Matrix übersprungen (INEXXIO_SKIP_MATRIX gesetzt).")
    _skip_without_db()
    result = run_case(case)
    if result.verdict == "unmöglich":
        pytest.skip(f"{case.id}: {case.impossible}")
    assert result.verdict != "fehler", f"{case.id} — {case.title}\n{result.error}"
    if case.open_finding:
        # **Ein bekannter Befund darf nicht verrotten.** Solange er offen ist, ist die
        # Abweichung erwartet; hört sie auf, war er behoben – und dann muss die Markierung
        # weg, sonst steht hier eine Ausnahme, die niemand mehr hinterfragt.
        assert result.verdict == "offen", (
            f"{case.id} — {case.title}: Der Befund ({case.open_finding}) ist behoben. "
            f"Bitte ``open_finding`` an diesem Fall entfernen, damit er wieder als "
            f"Wächter zählt."
        )
        pytest.skip(f"{case.id}: bekannter Befund – {case.open_finding}")
    assert not result.diffs, (
        f"{case.id} — {case.title}\n"
        + (f"({case.note})\n" if case.note else "")
        + "\n".join(f"  {d}" for d in result.diffs)
    )
