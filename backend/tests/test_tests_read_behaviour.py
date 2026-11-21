"""►►► **Ein Backend-Test liest keinen Quelltext der Oberfläche** (Änderungsakte C5). ◄◄◄

Regeln der Oberfläche prüft die Oberfläche selbst (``frontend/scripts/*.test.mjs``, auf dem
Syntaxbaum, mit Gegenprobe); Spiegel über die API-Grenze sind erzeugt (``scripts/dump_vocab``,
``dump_statuses``, ``openapi.json``). Einzige Ausnahme: ``test_api_routes`` – er vergleicht die
Aufrufe der Oberfläche mit den Routen dieser App, und die kennt nur das Backend.
"""

import pathlib
import re

TESTS = pathlib.Path(__file__).resolve().parent
ALLOWED = {"test_api_routes.py"}
#: Ein Pfad in die Oberfläche – als Teil eines Pfades, nicht in einem Satz.
_READS = re.compile(r"""["']frontend["']\s*/\s*["']src["']|["']frontend/src|\bFRONTEND\s*(?:/|=)""")


def _hits(text: str) -> list[int]:
    return [n for n, line in enumerate(text.splitlines(), 1) if _READS.search(line)]


def test_no_backend_test_reads_the_frontend_source():
    found = [f"{p.name}:{n}" for p in TESTS.glob("*.py")
             if p.name not in ALLOWED | {pathlib.Path(__file__).name} for n in _hits(p.read_text())]
    assert not found, f"Ein Backend-Test liest die Oberfläche: {found}"
    assert not list(TESTS.glob("test_source_*.py")), "test_source_* gibt es nicht mehr"


def test_the_guard_sees_the_bug_form():
    assert _hits('src = (ROOT / "frontend" / "src" / "lib" / "x.ts").read_text()') == [1]
    assert _hits("labels = _read(FRONTEND / 'lib' / 'record-status.ts')") == [1]
    assert _hits("Dieselbe Regel liest die Oberfläche (``frontend/src/lib/web-link.ts``).") == []
