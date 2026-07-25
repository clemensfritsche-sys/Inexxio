"""Wächter gegen ``NameError`` im Backend – die Python-Entsprechung zu ESLint.

**Warum es diesen Test gibt.** Ein im Funktionsrumpf benutzter, aber nie importierter
Name ist in Python **kein** Syntax- oder Importfehler – er fliegt erst, wenn genau
dieser Pfad läuft. Genau so ist ``LocationHop`` in ``routers/instances.py`` durch alle
Netze gerutscht: Tests grün, ``dump_openapi`` grün, Deploy grün, App gestartet – und
trotzdem **jeder** Aufruf von ``GET /erp/instances/{id}`` mit 500 gescheitert, weil der
Name erst zur Laufzeit aufgelöst wird. Das Frontend hat mit ESLint einen Wächter dafür,
das Backend hatte keinen.

**Wie es geprüft wird.** ``symtable`` (stdlib) sagt pro Modul, welche Namen als
**global** aufgelöst werden – inklusive der Namen tief in Funktions-/Klassenrümpfen.
Jeder davon muss nach dem Import tatsächlich im Modul-Namensraum oder in den Builtins
liegen. Funktions-lokale Importe zählen korrekt als lokal und stören nicht.

Nebeneffekt mit gleichem Wert: **jedes** Modul unter ``app/`` muss importierbar sein.
"""

import builtins
import importlib
import pathlib
import symtable

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def _collect(table: symtable.SymbolTable, read: set[str], written: set[str]) -> None:
    """Rekursiv sammeln: als **global** gelesene Namen und **irgendwo gebundene** Namen.

    Das Binden mitzuzählen ist nötig, weil Python 3.12 Comprehensions in den umgebenden
    Scope inlinet (PEP 709): ``ALL = [k for k, _, m in KATALOG]`` legt ``k``/``m`` in die
    Modul-Symboltabelle, obwohl beide zur Laufzeit nie Modul-Attribut werden. Sie sind
    gebunden und damit harmlos – im Gegensatz zu einem Namen, der nur gelesen wird.
    """
    for sym in table.get_symbols():
        name = sym.get_name()
        if sym.is_global() and sym.is_referenced():
            read.add(name)
        if sym.is_assigned() or sym.is_parameter() or sym.is_imported():
            written.add(name)
    for child in table.get_children():
        written.add(child.get_name())          # def/class binden ihren eigenen Namen
        _collect(child, read, written)


def _module_name(path: pathlib.Path) -> str:
    parts = path.relative_to(APP.parent).with_suffix("").parts
    name = ".".join(parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def test_no_undefined_global_names_in_backend():
    findings: list[str] = []

    for path in sorted(APP.rglob("*.py")):
        mod_name = _module_name(path)
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:                      # Modul muss importierbar sein
            findings.append(f"{mod_name}: Import fehlgeschlagen – {type(exc).__name__}: {exc}")
            continue
        source = path.read_text(encoding="utf-8")
        read: set[str] = set()
        written: set[str] = set()
        _collect(symtable.symtable(source, str(path), "exec"), read, written)
        for name in sorted(read - written):
            if not hasattr(mod, name) and not hasattr(builtins, name):
                findings.append(f"{mod_name}: '{name}' wird benutzt, ist aber nirgends definiert/importiert")

    assert not findings, "Undefinierte Namen (NameError zur Laufzeit):\n" + "\n".join(findings)


def test_the_guard_actually_catches_the_bug_it_was_written_for():
    """Selbsttest: ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu
    unterscheiden. Geprüft wird die Form des echten Fehlers – ein Name, der **nur im
    Funktionsrumpf** benutzt und nirgends gebunden wird – gegen die harmlose Form, die
    Python 3.12 durch inlined Comprehensions (PEP 709) in dieselbe Symboltabelle legt."""
    bug = "def build():\n    return [LocationHop(**h) for h in hops()]\n"
    ok = "KATALOG = [('a', 1)]\nALL = [k for k, m in KATALOG]\n"

    def only_read(source: str) -> set[str]:
        read: set[str] = set()
        written: set[str] = set()
        _collect(symtable.symtable(source, "<test>", "exec"), read, written)
        return {n for n in read - written if not hasattr(builtins, n)}

    assert "LocationHop" in only_read(bug)      # der Bug wird gemeldet …
    assert only_read(ok) == set()               # … die Comprehension-Variablen nicht
