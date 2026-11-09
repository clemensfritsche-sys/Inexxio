"""**Jede Route, die die Oberfläche ruft, gibt es im Backend** – mit derselben Methode.

Ein Aufruf ins Leere fällt sonst erst auf, wenn jemand den Knopf drückt (Messung im
Cleanup Oktober 2026: ``api.deleteStep`` rief ``DELETE …/steps/{id}``, den es nicht gab).

``frontend/src/lib/api.ts`` nennt jeden Pfad **so, wie das Backend ihn registriert**
(``'/api/v1/erp/orders/{object_id}'``), und immer mit seiner Methode: ``call('get', …)``,
``upload(…)`` (POST), ``Route<'get'>``, ``In<'post', …>``, ``Res<'get', …>``. Der Compiler
prüft das gegen die generierten Typen (``types/api.ts``); die CI prüft, dass ``openapi.json``
aktuell ist. Dieser Wächter prüft dasselbe gegen die **registrierten** Routen der App – ohne
Compiler und ohne Abschrift – und verlangt, dass kein Pfad an den Typen vorbei gebaut wird.
Daneben jede andere ``/api/v1/…``-Angabe in Frontend und Website (ohne Methode: dort
genügt, dass es den Pfad gibt).
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
API_TS = ROOT / "frontend" / "src" / "lib" / "api.ts"
PARAM = "\x00"                      # Platzhalter für einen Pfad-Parameter

# Ein Pfad mit seiner Methode – die Formen, in denen `api.ts` einen Pfad nennt.
TYPED = re.compile(
    r"(?:call\(|Route<|In<|Res<)\s*'(get|post|put|patch|delete)'[>,]\s*(?:=\s*)?'(/api/v1/[^']*)'"
    r"|upload\(\s*'(/api/v1/[^']*)'")
ANY_PATH = re.compile(r"""['"`](/api/v1/[^'"`]*)""")
ANY_LITERAL = re.compile(r"(/api/v1/[^'\"`\s?#]*)")


def _backend_routes() -> set[tuple[str, str]]:
    sys.path.insert(0, str(BACKEND))
    from app.main import app

    from tests._routes import api_routes
    return {(method, path) for path, methods in api_routes(app) for method in methods}


def _calls(src: str) -> list[tuple[str, str]]:
    """Jede (Methode, Pfad) aus dem Client – genau so geschrieben, wie das Backend sie nennt."""
    return [((m.group(1) or "post").upper(), m.group(2) or m.group(3)) for m in TYPED.finditer(src)]


def _code(src: str) -> str:
    """Ohne Kommentare – ein Pfad in einer Erklärung ist kein Aufruf."""
    return re.sub(r"(?<![:\\])//[^\n]*", "", re.sub(r"/\*.*?\*/", "", src, flags=re.S))


def _problems(src: str, routes: set[tuple[str, str]]) -> list[str]:
    """Was im Client nicht stimmt: Aufrufe ohne Route, Pfade an den Typen vorbei."""
    src = _code(src)
    calls = _calls(src)
    missing = [f"{m} {p}" for m, p in calls if (m, p) not in routes]
    typed = {p for _, p in calls}
    loose = [p for p in (m.group(1) for m in ANY_PATH.finditer(src)) if p not in typed]
    return missing + [f"ohne Methode und Typ: {p}" for p in loose]


def test_every_client_call_hits_a_route_with_that_method():
    src = _code(API_TS.read_text(encoding="utf-8"))
    # Ein Wächter, der nichts findet, ist von einem kaputten nicht zu unterscheiden.
    assert len(_calls(src)) >= 100, f"Nur {len(_calls(src))} Aufrufe gefunden – der Leser ist blind."
    problems = _problems(src, _backend_routes())
    assert not problems, (
        "Diese Pfade aus lib/api.ts treffen keine Route des Backends:\n  " + "\n  ".join(problems))


def test_the_guard_catches_its_bug_form():
    """Der Wächter schlägt an: falscher Pfad, falsche Methode, Pfad an den Typen vorbei."""
    routes = {("GET", "/api/v1/erp/orders/{object_id}"), ("POST", "/api/v1/erp/documents")}
    ok = ("this.call('get', '/api/v1/erp/orders/{object_id}', { path: { object_id: 1 } });\n"
          "this.upload('/api/v1/erp/documents', form);")
    assert _problems(ok, routes) == []
    assert _problems("this.call('delete', '/api/v1/erp/orders/{object_id}')", routes) == [
        "DELETE /api/v1/erp/orders/{object_id}"]
    assert _problems("this.call('get', '/api/v1/erp/order/{object_id}')", routes) == [
        "GET /api/v1/erp/order/{object_id}"]
    assert _problems("this.call('get', '/api/v1/erp/orders/{id}')", routes) == [
        "GET /api/v1/erp/orders/{id}"]
    assert _problems("this.request(`/api/v1/erp/steps/${id}`, { method: 'DELETE' })", routes) == [
        "ohne Methode und Typ: /api/v1/erp/steps/${id}"]


def _segments(path: str) -> list[str]:
    return [seg if seg == PARAM else seg.split(PARAM)[0]
            for seg in path.split("?")[0].strip("/").split("/")]


def test_every_other_api_path_in_frontend_and_website_exists():
    routes = [path.strip("/").split("/") for _, path in _backend_routes()]
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
            if not any(len(segs) == len(bs) and all(
                    f == b or (f == PARAM and b.startswith("{")) for f, b in zip(segs, bs))
                    for bs in routes):
                missing.append(f"{path.relative_to(ROOT)}: {m.group(1)}")
    assert found >= 3, f"Nur {found} Pfade gefunden – der Leser ist blind."
    assert not missing, "Diese Pfade gibt es im Backend nicht:\n  " + "\n  ".join(missing)
