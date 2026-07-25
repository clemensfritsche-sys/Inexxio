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


def _referenced_globals(table: symtable.SymbolTable, out: set[str]) -> set[str]:
    """Alle als global aufgelösten, gelesenen Namen – rekursiv über alle Scopes."""
    for sym in table.get_symbols():
        if sym.is_global() and sym.is_referenced():
            out.add(sym.get_name())
    for child in table.get_children():
        _referenced_globals(child, out)
    return out


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
        for name in sorted(_referenced_globals(symtable.symtable(source, str(path), "exec"), set())):
            if not hasattr(mod, name) and not hasattr(builtins, name):
                findings.append(f"{mod_name}: '{name}' wird benutzt, ist aber nirgends definiert/importiert")

    assert not findings, "Undefinierte Namen (NameError zur Laufzeit):\n" + "\n".join(findings)
