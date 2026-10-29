"""**Jede Route, die die Oberfläche ruft, gibt es im Backend** – mit derselben Methode.

Ein Aufruf ins Leere fällt sonst erst auf, wenn jemand den Knopf drückt (Messung im
Cleanup Oktober 2026: ``api.deleteStep`` rief ``DELETE …/steps/{id}``, den es nicht gab).
Verglichen wird der **Client** (``frontend/src/lib/api.ts``: ``this.get/post/…`` und
``fetch(`${API_BASE}…`)``) gegen die **registrierten** Routen der App – nicht gegen eine
Abschrift. Daneben jede andere ``/api/v1/…``-Angabe in Frontend und Website (ohne
Methode: dort genügt, dass es den Pfad gibt).

Ein Pfad-Parameter (``${id}``) passt auf jeden ``{name}`` des Backends; was hinter ``?``
steht, ist Query und zählt nicht.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
API_TS = ROOT / "frontend" / "src" / "lib" / "api.ts"
PARAM = "\x00"                      # Platzhalter für einen ``${…}``-Ausdruck

CLIENT_CALL = re.compile(r"this\.(get|post|patch|put|delete)(?:<[^\n]*?>)?\(\s*(['`])")
FETCH_CALL = re.compile(r"fetch\(\s*`\$\{API_BASE\}")
ANY_LITERAL = re.compile(r"(/api/v1/[^'\"`\s?#]*)")


def _string_at(src: str, i: int, quote: str) -> str:
    """Das String-Literal ab ``i`` (nach dem Anführungszeichen); ``${…}`` → ``PARAM``."""
    out, depth = [], 0
    while i < len(src):
        c = src[i]
        if depth == 0 and c == quote:
            return "".join(out)
        if quote == "`" and depth == 0 and src.startswith("${", i):
            depth, i = 1, i + 2
            out.append(PARAM)
            continue
        if depth:
            depth += {"{": 1, "}": -1}.get(c, 0)
        else:
            out.append(c)
        i += 1
    raise AssertionError(f"Unbeendetes Literal ab Zeichen {i}")


def _segments(path: str) -> list[str] | None:
    """``/api/v1/x/${id}?a=b`` → ``['api','v1','x', PARAM]``; ``None`` = nicht prüfbar."""
    path = path.split("?")[0]
    if not path.startswith("/api/"):
        return None                 # beginnt mit einem Ausdruck (z. B. ``addressBase``)
    parts = []
    for seg in path.strip("/").split("/"):
        if seg == PARAM:
            parts.append(PARAM)
        else:
            # ``articles${q ? `?${q}` : ''}`` – ein Ausdruck, der an einem Wort klebt, ist
            # die Query, kein Pfad-Teil.
            parts.append(seg.split(PARAM)[0])
    return parts


def _backend_routes() -> list[tuple[str, list[str]]]:
    sys.path.insert(0, str(BACKEND))
    from app.main import app

    from tests._routes import api_routes
    return [(method, path.strip("/").split("/")) for path, methods in api_routes(app)
            for method in methods]


def _matches(front: list[str], back: list[str]) -> bool:
    return len(front) == len(back) and all(
        f == b or (f == PARAM and b.startswith("{")) for f, b in zip(front, back))


def _client_calls() -> list[tuple[str, str, list[str]]]:
    src = API_TS.read_text(encoding="utf-8")
    calls = []
    for m in CLIENT_CALL.finditer(src):
        path = _string_at(src, m.end(), m.group(2))
        calls.append((m.group(1).upper(), path, _segments(path)))
    for m in FETCH_CALL.finditer(src):
        path = _string_at(src, m.end(), "`")
        call = src[m.end():src.find(");", m.end())]
        method = re.search(r"method:\s*'(\w+)'", call)
        calls.append(((method.group(1) if method else "GET").upper(), path,
                      _segments(path)))
    return calls


def test_every_client_call_hits_a_route_with_that_method():
    routes = _backend_routes()
    calls = _client_calls()
    checked = [(m, p, s) for m, p, s in calls if s is not None]
    # Ein Wächter, der nichts findet, ist von einem kaputten nicht zu unterscheiden.
    assert len(checked) >= 60, f"Nur {len(checked)} Aufrufe gefunden – der Leser ist blind."
    missing = [f"{m} {p.replace(PARAM, '{…}')}" for m, p, s in checked
               if not any(m == bm and _matches(s, bs) for bm, bs in routes)]
    assert not missing, (
        "Diese Aufrufe aus lib/api.ts treffen keine Route des Backends:\n  "
        + "\n  ".join(missing))


def test_every_other_api_path_in_frontend_and_website_exists():
    routes = _backend_routes()
    sources = [p for d in ("frontend/src", "frontend/scripts", "website/src", "website/scripts")
               for p in (ROOT / d).rglob("*")
               if p.suffix in (".ts", ".tsx", ".mjs", ".js", ".astro") and p.is_file()
               and p not in (API_TS, ROOT / "frontend" / "src" / "types" / "api.ts")]
    found, missing = 0, []
    for path in sources:
        text = re.sub(r"\$\{[^}]*\}", PARAM, path.read_text(encoding="utf-8"))
        for m in ANY_LITERAL.finditer(text):
            segs = _segments(m.group(1))
            found += 1
            if not any(_matches(segs, bs) for _, bs in routes):
                missing.append(f"{path.relative_to(ROOT)}: {m.group(1)}")
    assert found >= 3, f"Nur {found} Pfade gefunden – der Leser ist blind."
    assert not missing, "Diese Pfade gibt es im Backend nicht:\n  " + "\n  ".join(missing)
