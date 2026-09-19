"""**Was liest eigentlich niemand mehr?** – die Messung statt der Vermutung.

Aufräumen scheitert nicht am Löschen, sondern an der Frage davor: *wird das noch
gebraucht?* Aus der Erinnerung beantwortet ist sie wertlos – ein Modul, das «alt
aussieht», kann die einzige Lesestelle einer Regel sein, und eines, das vertraut
aussieht, kann seit einem halben Jahr niemand mehr aufrufen. Darum steht die Antwort
hier als **Werkzeug** und nicht als einmalige Handarbeit: sie ist wiederholbar, und
beim nächsten Mal kostet sie eine Minute statt eines Tages.

Vier Fragen, zwei Seiten::

    python -m scripts.deadcode              # alles
    python -m scripts.deadcode --backend
    python -m scripts.deadcode --frontend

**Backend · erreichbar ab ``app.main``.** Der Importgraph, aber mit den zwei Feinheiten,
an denen eine naive Messung falsch liegt: ein Modul zu importieren führt **jedes**
``__init__.py`` seiner Pakete aus (``app.domain.modules`` zieht ``app/domain/__init__.py``
mit), und ein Paket, dessen ``__init__`` seine Geschwister über ``pkgutil.iter_modules``
selbst einsammelt (``domain/capture_types``), hat gar keine geschriebenen Importe – seine
Dateien sind trotzdem alle erreichbar. Ohne beides meldet das Werkzeug Lebendes als tot,
und das ist der teurere Fehler.

**Backend · Namen, die ausserhalb ihres Moduls niemand liest.** Öffentliche Funktionen,
Klassen und Konstanten ohne einen einzigen fremden Leser. Das ist ein **Hinweis**, keine
Anklage: ein Endpunkt wird über den Router aufgerufen, ein Wächter über den Test, ein
Modell über die Beziehung. Der Report sagt deshalb, wie oft ein Name in Tests und
Skripten vorkommt – gelesen wird das Ergebnis, nicht befolgt.

**Frontend · erreichbar ab den Next-Einstiegen** (``page``/``layout``/``not-found``/
``robots``/``icon``) – statische und dynamische Importe.

**Frontend · Exporte, die niemand importiert.** ESLints ``no-unused-vars`` sieht nur
Ungenutztes *innerhalb* einer Datei; ein exportiertes Symbol ist für ihn immer benutzt.
Genau dort sammelt sich der Rest abgeschaffter Bereiche an.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
SRC = ROOT / "frontend" / "src"

#: Wo Namen vorkommen dürfen, ohne dass sie deshalb «benutzt» heissen: Tests und Skripte
#: sind Leser, aber keine Produktion. Sie werden gezählt und getrennt ausgewiesen.
OUTSIDE = ("backend/tests", "backend/scripts")

FRONTEND_ENTRY = re.compile(r"src/app/.*(page|layout|not-found|robots|icon)\.(tsx|ts)$")
EXPORTED = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|const|let|class|type|interface|enum)\s+(\w+)",
    re.M,
)


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
def _module_name(path: pathlib.Path) -> str:
    parts = path.relative_to(ROOT / "backend").with_suffix("").parts
    name = ".".join(parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _backend_modules() -> dict[str, pathlib.Path]:
    return {_module_name(p): p for p in sorted(APP.rglob("*.py"))}


def _imports(path: pathlib.Path, name: str) -> set[str]:
    """Alle Namen, die dieses Modul importiert – absolut aufgelöst."""
    out: set[str] = set()
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return out
    is_pkg = path.name == "__init__.py"
    parts = name.split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                # ``from .x import y`` in einem Paket zählt ab dem Paket selbst,
                # in einem Modul ab dessen Elternpaket.
                depth = node.level - 1 if is_pkg else node.level
                anchor = ".".join(parts[: len(parts) - depth]) if depth else name
                base = f"{anchor}.{base}" if base else anchor
            out.add(base)
            out.update(f"{base}.{a.name}" for a in node.names)
    return out


def _self_discovering(path: pathlib.Path) -> bool:
    """Sammelt dieses ``__init__`` seine Geschwister selbst ein (``pkgutil``)?"""
    return path.name == "__init__.py" and "iter_modules(__path__)" in path.read_text()


def backend_reachable() -> tuple[dict[str, pathlib.Path], set[str]]:
    mods = _backend_modules()
    edges = {name: _imports(path, name) for name, path in mods.items()}

    def resolve(target: str) -> str | None:
        while target:
            if target in mods:
                return target
            target = target.rsplit(".", 1)[0] if "." in target else ""
        return None

    seen: set[str] = set()
    stack = ["app.main"]
    while stack:
        name = stack.pop()
        if name in seen or name not in mods:
            continue
        seen.add(name)
        # Ein Import führt jedes ``__init__`` auf dem Weg dorthin aus.
        parts = name.split(".")
        for i in range(1, len(parts)):
            stack.append(".".join(parts[:i]))
        # Ein Paket, das seine Geschwister selbst einsammelt, zieht sie alle mit.
        if _self_discovering(mods[name]):
            stack += [m for m in mods if m.startswith(name + ".")]
        stack += [r for r in (resolve(t) for t in edges[name]) if r]
    return mods, seen


def _is_endpoint(node: ast.AST) -> bool:
    """``@router.get(...)`` & Co. – über HTTP erreichbar, nicht über einen Import."""
    for dec in getattr(node, "decorator_list", []):
        src = ast.dump(dec)
        if "'router'" in src or "'app'" in src:
            return True
    return False


def _public_names(path: pathlib.Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_") and not _is_endpoint(node):
                out.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_") and t.id.isupper():
                    out.append(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if not node.target.id.startswith("_") and node.target.id.isupper():
                out.append(node.target.id)
    return out


def backend_unread(mods: dict[str, pathlib.Path], seen: set[str]) -> dict[str, list[str]]:
    """Öffentliche Namen erreichbarer Module, die ausserhalb ihres Moduls niemand liest."""
    texts = {p: p.read_text() for p in mods.values()}
    outside = {
        p: p.read_text()
        for d in OUTSIDE
        for p in (ROOT / d).rglob("*.py")
    }
    result: dict[str, list[str]] = {}
    for name in sorted(seen):
        path = mods[name]
        if path.name == "__init__.py":
            continue
        dead = []
        own = texts[path]
        for sym in _public_names(path):
            pat = re.compile(rf"\b{re.escape(sym)}\b")
            if any(pat.search(t) for q, t in texts.items() if q != path):
                continue
            hits = sum(1 for t in outside.values() if pat.search(t))
            note = ""
            if hits:
                note = f"  (nur Tests/Skripte: {hits}×)"
            elif len(pat.findall(own)) > 1:
                note = "  (nur modulintern – Kandidat für _-Präfix)"
            dead.append(sym + note)
        if dead:
            result[str(path.relative_to(ROOT))] = dead
    return result


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
def _frontend_files() -> dict[str, pathlib.Path]:
    return {
        p.relative_to(ROOT).as_posix(): p
        for p in sorted(SRC.rglob("*"))
        if p.is_file() and p.suffix in (".ts", ".tsx")
    }


def _resolve_import(spec: str, frm: pathlib.Path, files: dict[str, pathlib.Path]) -> str | None:
    if spec.startswith("@/"):
        base = SRC / spec[2:]
    elif spec.startswith("."):
        base = (frm.parent / spec).resolve()
    else:
        return None
    for suffix in (".tsx", ".ts", "/index.tsx", "/index.ts"):
        cand = pathlib.Path(str(base) + suffix)
        try:
            key = cand.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if key in files:
            return key
    return None


def frontend_reachable() -> tuple[dict[str, pathlib.Path], set[str]]:
    files = _frontend_files()
    edges: dict[str, set[str]] = defaultdict(set)
    for key, path in files.items():
        text = path.read_text()
        specs = re.findall(r"""from ['"]([^'"]+)['"]""", text)
        specs += re.findall(r"""import\(\s*['"]([^'"]+)['"]\s*\)""", text)
        for spec in specs:
            found = _resolve_import(spec, path, files)
            if found:
                edges[key].add(found)
    seen: set[str] = set()
    stack = [k for k in files if FRONTEND_ENTRY.search(k)]
    while stack:
        key = stack.pop()
        if key in seen:
            continue
        seen.add(key)
        stack += list(edges[key])
    return files, seen


def frontend_unimported(files: dict[str, pathlib.Path]) -> dict[str, list[str]]:
    texts = {k: p.read_text() for k, p in files.items()}
    result: dict[str, list[str]] = {}
    for key, text in texts.items():
        if key.startswith("frontend/src/app/"):
            continue                      # Seiten exportieren für Next, nicht für uns
        dead = [
            sym for sym in EXPORTED.findall(text)
            if not any(re.search(rf"\b{re.escape(sym)}\b", o) for q, o in texts.items() if q != key)
        ]
        if dead:
            result[key] = dead
    return result


# ---------------------------------------------------------------------------
def _section(title: str, rows: list[str]) -> int:
    print(f"\n{title}  ({len(rows)})")
    print("─" * 78)
    for row in rows:
        print(f"  {row}")
    if not rows:
        print("  – nichts gefunden")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backend", action="store_true")
    ap.add_argument("--frontend", action="store_true")
    args = ap.parse_args()
    both = not (args.backend or args.frontend)
    total = 0

    if both or args.backend:
        mods, seen = backend_reachable()
        unreached = sorted(set(mods) - seen)
        total += _section(
            "BACKEND · Module, die von app.main aus nicht erreichbar sind",
            [f"{mods[m].relative_to(ROOT)}  ({len(mods[m].read_text().splitlines())} Zeilen)"
             for m in unreached],
        )
        unread = backend_unread(mods, seen)
        total += _section(
            "BACKEND · öffentliche Namen ohne fremden Leser",
            [f"{path}: {', '.join(names)}" for path, names in sorted(unread.items())],
        )

    if both or args.frontend:
        files, seen = frontend_reachable()
        total += _section(
            "FRONTEND · Dateien, die von keiner Seite aus erreichbar sind",
            sorted(set(files) - seen),
        )
        unimported = frontend_unimported(files)
        total += _section(
            "FRONTEND · Exporte, die niemand importiert",
            [f"{path}: {', '.join(names)}" for path, names in sorted(unimported.items())],
        )

    print(f"\n{total} Fundstellen. Jede ist ein **Hinweis**: prüfen, dann entscheiden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
