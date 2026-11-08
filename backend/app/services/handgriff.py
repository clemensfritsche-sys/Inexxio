"""►►► **Der Handgriff – alles, was das ERP kann, durch dieselbe Tür wie ein Klick.** ◄◄◄
(Projektakte, Phase 5 §6.3 und §7)

Ein Handgriff ist ein vorbereiteter Aufruf **genau einer Handlung** des ERP: Methode, Pfad,
Werte. Ausgeführt wird die **echte Route** – im selben Prozess über ASGI, mit den Rechten der
Person (``core/auth.ACTING``) und denselben Prüfungen. Es gibt keinen zweiten Weg daneben.

* **Welche Handlungen** ein Handgriff sein können, folgt aus der Route selbst, ohne Liste
  (``operations``): sie schreibt (nicht ``GET``), verlangt Personal (``require_employee`` oder
  ``require_admin``) und nimmt JSON. Eine Route mit Datei braucht die Hand. Der Assistent
  bereitet nichts an sich selbst vor (Routen aus ``routers/assistant``).
* **Probelauf** (``call(..., probe=True)``): in eigener Sitzung ganz durch, dann verworfen.
  Was dabei nach aussen ginge oder zwischendurch speicherte, gibt ``NeedsHand``
  (``core/outside``).
* **Ausführen** (``call(..., probe=False, done=…)``): derselbe Weg; ``done`` schreibt in
  **derselben** Transaktion das Ereignis ``handgriff.done`` – ein eindeutiger Index macht
  «genau einmal».
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Optional

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import outside
from ..core.actor import act
from ..core.database import AMBIENT, SessionLocal
from ..models import UserProfile

#: Was eine Handlung höchstens an Beschreibung mitbringt (Tokens sind Geld).
_SUMMARY = 300


@dataclass(frozen=True)
class Operation:
    """Eine Handlung des ERP, wie die KI sie sieht – aus der Route abgeleitet."""
    name: str
    method: str
    path: str
    summary: str
    admin: bool
    hand: bool                      # nimmt eine Datei – geht nur mit der Hand
    schema: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"


@dataclass
class Outcome:
    """Was ein Aufruf ergab: ``ok`` (2xx), sonst ``detail`` – der Satz der Route; ``hand`` =
    braucht die Person selbst (``NeedsHand``)."""
    status: int
    data: Any = None
    detail: str = ""
    hand: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self.hand


# ---------------------------------------------------------------------------
# Die Handlungen – aus den Routen
# ---------------------------------------------------------------------------

def _calls(dependant) -> set[Callable]:
    out: set[Callable] = set()
    for d in dependant.dependencies:
        out.add(d.call)
        out |= _calls(d)
    return out


def _first_sentence(doc: str) -> str:
    text = re.sub(r"[►◄*`]", "", " ".join((doc or "").split()))
    return text.strip()[:_SUMMARY]


@lru_cache(maxsize=1)
def operations() -> tuple[Operation, ...]:
    """►►► **Alle Handlungen, die ein Handgriff sein können** – abgeleitet, nie gepflegt. ◄◄◄"""
    from fastapi.routing import APIRoute, iter_route_contexts

    from ..core.auth import require_admin, require_employee
    from ..main import app
    spec = app.openapi()
    found: list[Operation] = []
    for c in iter_route_contexts(app.routes):
        route = c.route
        methods = set(c.methods or ()) - {"HEAD"}
        if not isinstance(route, APIRoute) or not methods or methods <= {"GET"}:
            continue
        if route.endpoint.__module__.endswith("routers.assistant"):
            continue
        calls = _calls(route.dependant)
        if require_employee not in calls and require_admin not in calls:
            continue
        method = sorted(methods)[0]
        op = spec["paths"].get(c.path, {}).get(method.lower(), {})
        content = (op.get("requestBody") or {}).get("content") or {}
        schema = _resolve((content.get("application/json") or {}).get("schema") or {}, spec)
        found.append(Operation(
            name=route.name, method=method, path=c.path,
            summary=_first_sentence(route.endpoint.__doc__ or op.get("summary") or ""),
            admin=require_admin in calls and require_employee not in calls,
            hand=bool(content) and "application/json" not in content,
            schema=schema))
    return tuple(found)


def _resolve(schema: Any, spec: dict[str, Any], depth: int = 0) -> Any:
    """``$ref`` aufgelöst – die Felder einer Handlung stehen an einer Stelle."""
    if depth > 6:
        return {}
    if isinstance(schema, dict):
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            return _resolve(spec["components"]["schemas"].get(name, {}), spec, depth + 1)
        return {k: _resolve(v, spec, depth) for k, v in schema.items()
                if k not in ("title",) or depth == 0}
    if isinstance(schema, list):
        return [_resolve(v, spec, depth) for v in schema]
    return schema


def operation(key: str) -> Optional[Operation]:
    """Eine Handlung über ihren Schlüssel «METHODE /pfad/{platzhalter}» – eindeutig, anders
    als der Funktionsname."""
    return next((o for o in operations() if o.key == key), None)


def operation_for(method: str, path: str) -> Optional[Operation]:
    """Die Handlung zu einem konkreten Aufruf (``POST /api/v1/erp/messages``)."""
    for o in operations():
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", o.path) + "$"
        if o.method == method.upper() and re.match(pattern, path):
            return o
    return None


def find(words: str, limit: int = 12) -> list[Operation]:
    """Die Handlungen, die zu den Wörtern passen (Name, Satz, Pfad) – die KI schlägt nach,
    statt alle in jeder Anfrage mitzubekommen."""
    terms = [t for t in re.split(r"\W+", words.lower()) if len(t) > 2]
    scored = []
    for o in operations():
        text = f"{o.name} {o.summary} {o.path}".lower()
        hits = sum(t in text for t in terms)
        if hits or not terms:
            scored.append((-hits, o.name, o))
    return [o for *_k, o in sorted(scored)[:limit]]


# ---------------------------------------------------------------------------
# Aufrufen
# ---------------------------------------------------------------------------

def _request(method: str, path: str, body: Any) -> httpx.Response:
    """Die Route über ASGI aufrufen – in einer eigenen Ereignisschleife dieses Threads; der
    Kontext (Sitzung, Person, Probelauf) reist mit."""
    from ..main import app

    async def go() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://handgriff") as c:
            return await c.request(method, path, json=body if body is not None else None)
    return asyncio.run(go())


def _detail(res: httpx.Response) -> tuple[Any, str, str]:
    try:
        data = res.json()
    except ValueError:
        data = None
    if res.is_success:
        return data, "", ""
    if isinstance(data, dict):
        return None, str(data.get("detail") or ""), str(data.get("hand") or "")
    return None, res.reason_phrase, ""


def call(person_id: int, method: str, path: str, body: Any, *, probe: bool,
         done: Optional[Callable[[Session, Any], None]] = None) -> Outcome:
    """►►► **Eine Handlung aufrufen – als diese Person, in eigener Sitzung.** ◄◄◄

    ``probe``: danach wird alles verworfen. Sonst wird gespeichert – zusammen mit ``done``
    (``handgriff.done``), oder gar nicht. Nur Handlungen aus ``operations``."""
    from ..core.auth import ACTING
    if operation_for(method, path) is None:
        return Outcome(400, detail=f"«{method} {path}» ist keine Handlung des ERP.")
    db = SessionLocal()
    person = db.query(UserProfile).filter(UserProfile.id == person_id).first()
    if person is None:
        db.close()
        return Outcome(404, detail="Diese Person gibt es nicht.")
    act(db, "person", person.object_id, "handgriff")
    tokens = (AMBIENT.set(db), ACTING.set(person))
    try:
        if probe:
            with outside.probe():
                res = _request(method, path, body)
        else:
            res = _request(method, path, body)
        data, detail, hand = _detail(res)
        out = Outcome(res.status_code, data, detail, hand)
        if probe or not out.ok:
            db.rollback()
            return out
        if done is not None:
            done(db, data)
        db.commit()
        return out
    except IntegrityError:
        db.rollback()
        return Outcome(409, detail="Dieser Handgriff ist schon ausgeführt.")
    finally:
        AMBIENT.reset(tokens[0])
        ACTING.reset(tokens[1])
        db.close()


def result_of(data: Any) -> Optional[int]:
    """Die Nummer, die eine Handlung angelegt hat – aus ihrer Antwort (``object_id``)."""
    if isinstance(data, dict):
        oid = data.get("object_id")
        return oid if isinstance(oid, int) else None
    return None


def dumps(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True)
