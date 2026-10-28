"""Wächter: **keine synchrone Arbeit in der Event-Loop.**

Ein ``async def``-Handler läuft in der Event-Loop; jede synchrone Datenbank- oder
HTTP-Arbeit darin hält ALLE Anfragen der Instanz an. FastAPI führt ``def``-Handler im
Threadpool aus – das ist der Normalfall. Die Regel:

1. Ein ``async``-Endpunkt hat einen Grund, ``async`` zu sein: er wartet auf etwas (``await``,
   etwa das Formular oder den Rumpf lesen).
2. In keiner ``async``-Funktion der App geht die Sitzung ``db`` an eine synchrone Stelle –
   weder ``db.…()`` noch ``f(db, …)`` noch ``SessionLocal()``; der Weg ist
   ``run_in_threadpool(f, db, …)``.
"""

import ast
import inspect
import textwrap
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app

APP = Path(__file__).resolve().parents[1] / "app"

#: Bekannt und gemeldet (nicht in diesem Bereich zu ändern): der Webhook des
#: Zahlungsdienstes liest den rohen Rumpf und bucht dann synchron.
KNOWN = {("routers/payments.py", "webhook")}


def _awaits(fn: ast.AST) -> bool:
    return any(isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith)) for n in ast.walk(fn))


def _blocking(fn: ast.AsyncFunctionDef) -> list[str]:
    """Was in dieser async-Funktion die Sitzung synchron anfasst."""
    found = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name == "SessionLocal":
            found.append(f"SessionLocal() in Zeile {node.lineno}")
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "db":
            found.append(f"db.{f.attr}() in Zeile {node.lineno}")
        if name != "run_in_threadpool" and any(
                isinstance(a, ast.Name) and a.id == "db" for a in node.args):
            found.append(f"{name}(db, …) in Zeile {node.lineno}")
    return found


def violations(source: str, where: str) -> list[str]:
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AsyncFunctionDef) and (where, node.name) not in KNOWN:
            out += [f"{where}:{node.name}: {b}" for b in _blocking(node)]
    return out


def test_async_endpoints_wait_for_something():
    lazy = []
    for route in app.routes:
        if isinstance(route, APIRoute) and inspect.iscoroutinefunction(route.endpoint):
            tree = ast.parse(textwrap.dedent(inspect.getsource(route.endpoint)))
            if not _awaits(tree):
                lazy.append(f"{route.path} ({route.endpoint.__name__})")
    assert not lazy, ("async ohne await – als «def» schreiben, dann läuft es im Threadpool: "
                      + ", ".join(lazy))


def test_no_async_function_touches_the_session():
    found = []
    for path in sorted(APP.rglob("*.py")):
        found += violations(path.read_text(encoding="utf-8"), str(path.relative_to(APP)))
    assert not found, "Synchrone DB-Arbeit in der Event-Loop: " + " · ".join(found)


def test_the_guards_catch_their_bug_forms():
    """Gegenprobe: jede Bug-Form schlägt an, die erlaubte Form nicht."""
    bad = {
        "async def h(db):\n    db.commit()\n",
        "async def h(db):\n    svc.record(db, 1)\n",
        "async def mw(request, call_next):\n    s = SessionLocal()\n",
    }
    for src in bad:
        assert violations(src, "x.py"), src
    good = "async def h(db):\n    x = await request.form()\n    return await run_in_threadpool(f, db, x)\n"
    assert not violations(good, "x.py")
    assert not _awaits(ast.parse("async def h(db):\n    return db\n"))
