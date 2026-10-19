"""Gemeinsame Hilfen der Quelltext-Wächter (``test_frontend_mirrors.py`` und
``test_source_*.py``): Pfade, Datei lesen, Code ohne Kommentare, Rumpf eines
Bauteils."""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"


def _read(path: pathlib.Path) -> str:
    assert path.exists(), f"Erwartete Datei fehlt: {path}"
    return path.read_text(encoding="utf-8")


def _code(source: str) -> str:
    """Nur der Code — Kommentare und Docstrings raus.

    Ein Waechter, der einen Kommentar liest, prueft die Erklaerung statt der Sache: er
    schlaegt an, weil jemand den Fehler *beschreibt*, den er verhindern soll. Genau das
    ist beim Schreiben dieser Runde passiert.
    """
    # Blockkommentare: /* … */ und JSX {/* … */}, dazu Python-Docstrings.
    without = re.sub(r"\{?/\*[\s\S]*?\*/\}?", "", source)
    without = re.sub(r'"""[\s\S]*?"""', "", without)
    # Zeilenkommentare nur am Zeilenanfang – sonst trifft es «https://».
    return "\n".join(
        l for l in without.split("\n")
        if not l.lstrip().startswith(("//", "#", "*"))
    )


def _at(source: str, head: str) -> int:
    """Die Stelle, an der **genau dieser** Name steht — nicht der, der so anfaengt.

    ``source.index("function Money")`` trifft auch ``function MoneyBar``: der Waechter
    laese danach den Rumpf eines **anderen** Bauteils und schlueg aus einem Grund fehl,
    der nichts mit ihm zu tun hat (gemessen, als neben ``Money`` eine ``MoneyBar``
    entstand). Dieselbe Stumpfheit wie damals beim Teilen am ersten Vorkommen eines
    Namens — nur eine Ebene frueher.
    """
    m = re.search(re.escape(head) + r"(?![A-Za-z0-9_$])", source)
    assert m is not None, f"«{head}» steht nicht in der Datei."
    return m.start()


def _body(source: str, name: str, *, kind: str = "def") -> str:
    """Der Rumpf genau einer Funktion/Klasse – ohne die nächste mitzunehmen.

    Ein blosses ``split`` läuft bis ans Dateiende und trifft dann Nachbarn, die gar nicht
    gemeint waren; der Test schlüge aus einem Grund fehl, der nichts mit ihm zu tun hat.
    """
    head = f"{kind} {name}"
    start = _at(source, head)
    rest = source[start + len(head):]
    # Python endet beim nächsten Top-Level-Konstrukt, TypeScript beim nächsten
    # ``export``/``function``. Dieselbe Absicht, zwei Sprachen – die Alternative wäre ein
    # Parser für eine Frage, die eine Zeile beantwortet.
    # TypeScript endet beim nächsten Konstrukt auf Spalte 0 – oder bei einer
    # eingerückten ``function``, die eine verschachtelte Hilfsfunktion abgrenzt. Ein
    # eingerücktes ``const`` bleibt bewusst draussen: das ist ganz normaler Rumpf.
    stop = (r"\n(?:def |class |@)" if kind in ("def", "class")
            else r"\n(?:export |function |interface |const |/\*\*)|\n\s+function ")
    end = re.search(stop, rest)
    return rest[: end.start()] if end else rest


def _component(source: str, name: str) -> str:
    """Der **ganze** Rumpf einer React-Komponente – verschachtelte Helfer inbegriffen.

    ``_body`` bricht bewusst an einer eingerückten ``function`` ab: dort grenzt sie eine
    verschachtelte Hilfsfunktion ab, und ein Wächter, der über sie hinausliest, prüfte
    fremden Code. Für eine **Komponente** ist das genau falsch herum – ihr JSX steht
    hinter solchen Helfern, und der Wächter sähe von der Sache, um die es geht, gar
    nichts. Gemessen: an ``ModuleFields`` (eine verschachtelte ``setPoint``) lieferte
    ``_body`` **249 Zeichen**, und die eigene Bug-Form ging durch.

    Hier endet der Rumpf darum erst am nächsten Konstrukt **auf Spalte 0**.
    """
    start = _at(source, f"function {name}")
    rest = source[start + len(f"function {name}"):]
    end = re.search(r"\n(?:export |function |interface |const |type |/\*\*)", rest)
    return rest[: end.start()] if end else rest


def _expr(window: str) -> str:
    """Der **Wert** einer `label:`-Zuweisung – bis zum Komma auf gleicher Klammerebene.

    Ohne diese Abgrenzung liest ein Wächter das Nachbarfeld mit und meldet
    `label: 'Zielort', expected: target.object_id` als Fehler, obwohl das Label sauber ist.
    """
    body = window[window.index(":") + 1:]
    depth = 0
    for i, ch in enumerate(body):
        if ch in "([{`":
            depth += 1
        elif ch in ")]}`":
            depth -= 1
            if depth < 0:
                return body[:i]
        elif ch == "," and depth == 0:
            return body[:i]
    return body


DEAL_WORK = FRONTEND / "components" / "erp" / "beleg-work.tsx"


def _beleg() -> str:
    return _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")


def _module_ui() -> str:
    return _read(FRONTEND / "components" / "erp" / "module-ui.tsx")


_USER_SURFACES = ("components/erp/user-detail.tsx",
                  "components/account/sections/profile-section.tsx")


def _unconditional(src: str, title: str) -> str:
    """Steht dieser ``SubBlock`` **ohne Bedingung** da? Sonst der Grund als Satz.

    ►►► **Gefragt ist die Zeile DAVOR, nicht die danach.** ◄◄◄ Der erste Anlauf schnitt
    am ``<SubBlock`` und las den Rest – also genau das Stück **hinter** der Bedingung, und
    liess damit seine eigene Bug-Form durch (gemessen). Ein `{cond && (` steht entweder
    auf derselben Zeile oder am Ende der vorigen; beide werden geprüft.
    """
    line = src.rfind("\n", 0, _at(src, f'title="{title}"')) + 1
    head = src[line:src.index("\n", line)].strip()
    before = src[:line].rstrip().rsplit("\n", 1)[-1].strip()
    if not head.startswith("<SubBlock"):
        return f"«{title}» steht hinter einer Bedingung: {head[:80]}"
    if before.endswith(("&& (", "? (", "&&", "?")):
        return f"«{title}» steht hinter einer Bedingung: {before[-80:]}"
    return ""


def _address_field() -> str:
    return _code(_read(FRONTEND / "components" / "erp" / "address-field.tsx"))


def _frontend_sources(*suffixes: str):
    """Jede Quelldatei des Frontends – ohne die generierten Typen und die Token-Datei."""
    for path in sorted(FRONTEND.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        rel = path.relative_to(FRONTEND).as_posix()
        if rel == "types/api.ts" or rel.startswith("styles/design-system/"):
            continue
        yield rel, _read(path)
