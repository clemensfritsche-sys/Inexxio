"""►►► **Der Handgriff – alles, was das ERP kann, durch dieselbe Tür wie ein Klick.** ◄◄◄
(Projektakte, Phase 5 §6.3 und §7)

Ein Handgriff ist ein vorbereiteter Aufruf **genau einer Handlung** des ERP: Methode, Pfad,
Werte. Ausgeführt wird die **echte Route** – im selben Prozess über ASGI, mit den Rechten der
Person (``core/auth.ACTING``) und denselben Prüfungen. Es gibt keinen zweiten Weg daneben.

* **Welche Handlungen** ein Handgriff sein können, folgt aus der Route selbst, ohne Liste
  (``operations``): sie schreibt (nicht ``GET``), verlangt Personal (``require_employee`` oder
  ``require_admin``) und nimmt JSON. Eine Route mit Datei braucht die Hand. Der Assistent
  bereitet nichts an sich selbst vor (Routen aus ``routers/assistant``), und nichts an der
  Anmeldung von Claude (``routers/mcp``).
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
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import outside
from ..core.actor import act
from ..core.database import AMBIENT, SessionLocal
from ..models import UserProfile
from . import log
from ..domain.errors import Conflict, NotFound
from ..domain import policy

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


@lru_cache(maxsize=2)
def _routes(reading: bool) -> tuple[Operation, ...]:
    """Die Routen des Personals – schreibende (``reading=False``) oder lesende (``GET``)."""
    from fastapi.routing import APIRoute, iter_route_contexts

    from ..core.auth import require_admin, require_employee
    from ..main import app
    spec = app.openapi()
    found: list[Operation] = []
    for c in iter_route_contexts(app.routes):
        route = c.route
        methods = set(c.methods or ()) - {"HEAD"}
        if not isinstance(route, APIRoute) or not methods or (methods <= {"GET"}) != reading:
            continue
        if route.endpoint.__module__.endswith(("routers.assistant", "routers.mcp")):
            continue
        calls = _calls(route.dependant)
        # Lesen darf die KI, was jedes Personal darf – nur Admin ist für sie nicht lesbar.
        if require_employee not in calls and (reading or require_admin not in calls):
            continue
        method = sorted(methods)[0]
        op = spec["paths"].get(c.path, {}).get(method.lower(), {})
        content = (op.get("requestBody") or {}).get("content") or {}
        schema = (_resolve({"parameters": op.get("parameters") or []}, spec) if reading else
                  _resolve((content.get("application/json") or {}).get("schema") or {}, spec))
        found.append(Operation(
            name=route.name, method=method, path=c.path,
            summary=_first_sentence(route.endpoint.__doc__ or op.get("summary") or ""),
            admin=require_admin in calls and require_employee not in calls,
            hand=bool(content) and "application/json" not in content,
            schema=schema))
    return tuple(found)


def operations() -> tuple[Operation, ...]:
    """►►► **Alle Handlungen, die ein Handgriff sein können** – abgeleitet, nie gepflegt: sie
    schreiben, verlangen Personal und nehmen JSON (mit Datei: nur von Hand). ◄◄◄"""
    return _routes(False)


def reads() -> tuple[Operation, ...]:
    """►►► **Alles, was das ERP jedem Personal zeigt** – die lesenden Routen (``GET``), die die KI
    mit ``look`` abruft. Abgeleitet wie ``operations``; Admin-Routen sind für sie nicht lesbar. ◄◄◄"""
    return _routes(True)


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
    als der Funktionsname; lesend oder schreibend."""
    return next((o for o in (*operations(), *reads()) if o.key == key), None)


#: Ein Pfad mit Punkt-Teilen, Abfrage, Anker oder Kodierung könnte nach dem Normalisieren eine
#: andere Route treffen als die geprüfte – er ist keine Handlung.
_UNSAFE = re.compile(r"(^|/)\.{1,2}(/|$)|//|[?#%\\]")


def operation_for(method: str, path: str, among: Optional[tuple[Operation, ...]] = None
                  ) -> Optional[Operation]:
    """Die Handlung zu einem konkreten Aufruf (``POST /api/v1/erp/messages``) – unter den
    schreibenden, oder unter ``among``."""
    if _UNSAFE.search(path):
        return None
    for o in among if among is not None else operations():
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", o.path) + "$"
        if o.method == method.upper() and re.match(pattern, path):
            return o
    return None


def find(words: str, limit: int = 12) -> list[Operation]:
    """Die Handlungen, die zu den Wörtern passen (Name, Satz, Pfad) – die KI schlägt nach,
    statt alle in jeder Anfrage mitzubekommen."""
    terms = [t for t in re.split(r"\W+", words.lower()) if len(t) > 2]
    scored = []
    for o in (*operations(), *reads()):
        text = f"{o.name} {o.summary} {o.path}".lower()
        hits = sum(t in text for t in terms)
        if hits or not terms:
            scored.append((-hits, o.name, o))
    return [o for *_k, o in sorted(scored)[:limit]]


# ---------------------------------------------------------------------------
# Aufrufen
# ---------------------------------------------------------------------------

def _request(method: str, path: str, body: Any, params: Optional[dict[str, Any]] = None
             ) -> httpx.Response:
    """Die Route über ASGI aufrufen – in einer eigenen Ereignisschleife dieses Threads; der
    Kontext (Sitzung, Person, Probelauf) reist mit."""
    from ..main import app

    async def go() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://handgriff") as c:
            return await c.request(method, path, json=body if body is not None else None,
                                   params=params or None)
    return asyncio.run(go())


def _detail(res: httpx.Response) -> tuple[Any, str, str]:
    try:
        data = res.json()
    except ValueError:
        data = None
    if res.is_success:
        return data, "", ""
    if isinstance(data, dict):
        return None, said(data.get("detail")), str(data.get("hand") or "")
    return None, res.reason_phrase, ""


def said(detail: Any) -> str:
    """Der Satz einer Abweisung – auch die Liste, die die Prüfung der Werte liefert (422):
    «feld: was nicht stimmt» je Fehler."""
    if isinstance(detail, list):
        parts = []
        for e in detail:
            if isinstance(e, dict):
                where = ".".join(str(x) for x in (e.get("loc") or [])[1:]) or "Werte"
                parts.append(f"{where}: {e.get('msg') or ''}".strip())
        return "; ".join(parts)[:600]
    return str(detail or "")


def look(path: str, params: Optional[dict[str, Any]] = None,
         viewer: Optional[UserProfile] = None) -> Outcome:
    """►►► **Lesen, was das ERP zeigt** – eine lesende Route, durch dieselbe Tür wie ein Klick,
    mit den Rechten, die jedes Personal hat (``ai_tools.reader``) – oder mit denen von ``viewer``,
    wenn das Ergebnis allein bei ihm bleibt (MCP). In eigener Sitzung, danach
    verworfen und ohne Weg nach aussen: ein Lesepfad, der nebenbei schreibt, hinterlässt nichts. ◄◄◄"""
    from ..core.auth import ACTING
    from .ai_tools import reader
    if operation_for("GET", path, reads()) is None:
        return Outcome(400, detail=f"«GET {path}» ist nichts, was das ERP zeigt.")
    db = SessionLocal()
    act(db, "ai", viewer.object_id if viewer is not None else None, "handgriff")
    tokens = (AMBIENT.set(db), ACTING.set(viewer or reader()))
    try:
        with outside.probe():
            res = _request("GET", path, None, {k: v for k, v in (params or {}).items() if v is not None})
        data, detail, hand = _detail(res)
        return Outcome(res.status_code, data, detail, hand)
    finally:
        db.rollback()
        AMBIENT.reset(tokens[0])
        ACTING.reset(tokens[1])
        db.close()


@dataclass(frozen=True)
class Step:
    """Ein Aufruf einer Handlung; ``ref`` = der Handgriff, dessen Nummer spätere Schritte
    einsetzen (``{"$handgriff": ref}``)."""
    method: str
    path: str
    body: Any = None
    ref: Optional[int] = None


class Waiting(Exception):
    """Ein Platzhalter ``{"$handgriff": n}`` zeigt auf einen Handgriff ohne Nummer."""


def fill(value: Any, results: dict[int, int]) -> Any:
    """►► **Platzhalter einsetzen** – ``{"$handgriff": n}`` wird die Nummer, die Handgriff
    ``n`` angelegt hat (Regel 2: aufeinander aufbauen). ◄◄"""
    if isinstance(value, dict):
        if set(value) == {"$handgriff"}:
            ref = int(value["$handgriff"])
            if ref not in results:
                raise Waiting(ref)
            return results[ref]
        return {k: fill(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [fill(v, results) for v in value]
    if isinstance(value, str):
        return re.sub(r"\{\$handgriff:(\d+)\}", lambda m: _place(int(m.group(1)), results), value)
    return value


def _place(ref: int, results: dict[int, int]) -> str:
    if ref not in results:
        raise Waiting(ref)
    return str(results[ref])


#: So lange wartet ein Handgriff höchstens auf eine Sperre – danach ist es ein klarer 409, nie ein
#: Hängen (die Anfrage, die ihn startet, wartet auf ihn).
LOCK_TIMEOUT = "8s"
#: Der Raum der Advisory-Sperre «dieser Handgriff läuft gerade» (je Handgriff ein Schlüssel).
_LOCK_SPACE = 5051


def _busy(detail: str) -> bool:
    return "lock timeout" in detail.lower() or "LockNotAvailable" in detail


def call(person_id: int, steps: list[Step], *, probe: bool, results: Optional[dict[int, int]] = None,
         done: Optional[Callable[[Session, Any], None]] = None, once: Optional[int] = None) -> Outcome:
    """►►► **Handlungen aufrufen – als diese Person, in eigener Sitzung, der Reihe nach.** ◄◄◄

    ``probe``: danach wird alles verworfen. Sonst wird gespeichert – zusammen mit ``done``
    (``handgriff.done``), oder gar nicht. Was ein Schritt anlegt, setzen die folgenden für
    ``{"$handgriff": ref}`` ein. Die Antwort ist die des letzten Schritts – scheitert einer
    davor, seine. Nur Handlungen aus ``operations``. ``once`` = der Handgriff, der genau einmal
    läuft: seine Sperre wird vor dem ersten Schritt genommen und «schon ausgeführt?» danach
    geprüft – ein zweiter Klick wartet und läuft dann nicht mehr (auch nichts nach aussen)."""
    from ..core.auth import ACTING
    for st in steps:
        if operation_for(st.method, st.path) is None:
            return Outcome(400, detail=f"«{st.method} {st.path}» ist keine Handlung des ERP.")
    db = SessionLocal()
    person = db.query(UserProfile).filter(UserProfile.id == person_id).first()
    if person is None:
        db.close()
        return Outcome(404, detail="Diese Person gibt es nicht.")
    act(db, "person", person.object_id, "handgriff")
    db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
    tokens = (AMBIENT.set(db), ACTING.set(person))
    known = dict(results or {})
    try:
        if once is not None and _taken(db, once):
            db.rollback()
            return Outcome(409, detail=f"Handgriff «{once}» ist nicht mehr offen.")
        out = Outcome(400, detail="Nichts zu tun.")
        for st in steps:
            try:
                path, body = fill(st.path, known), fill(st.body, known)
            except Waiting as w:
                db.rollback()
                return Outcome(409, detail=f"Wartet auf Handgriff {w.args[0]}.")
            if probe:
                with outside.probe():
                    res = _request(st.method, path, body)
            else:
                res = _request(st.method, path, body)
            data, detail, hand = _detail(res)
            if res.status_code >= 500 and _busy(detail):
                detail, status = "Der Datensatz ist gerade in Arbeit – bitte gleich noch einmal.", 409
            else:
                status = res.status_code
            out = Outcome(status, data, detail, hand)
            if not out.ok:
                break
            if st.ref is not None and result_of(data) is not None:
                known[st.ref] = result_of(data)
        if probe or not out.ok:
            db.rollback()
            return out
        if done is not None:
            done(db, out.data)
        db.commit()
        return out
    except IntegrityError:
        db.rollback()
        return Outcome(409, detail="Dieser Handgriff ist schon ausgeführt.")
    finally:
        AMBIENT.reset(tokens[0])
        ACTING.reset(tokens[1])
        db.close()


def _taken(db: Session, hid: int) -> bool:
    """Sperre auf diesen Handgriff (bis zum Ende der Transaktion), dann: ist er noch offen?"""
    db.execute(text("SELECT pg_advisory_xact_lock(:s, :k)"),
               {"s": _LOCK_SPACE, "k": hid & 0x7FFF_FFFF})
    return bool(db.execute(text(
        "SELECT EXISTS (SELECT 1 FROM log WHERE event IN ('handgriff.done', 'handgriff.dropped') "
        "AND (payload ->> 'handgriff')::bigint = :h)"), {"h": hid}).scalar())


def release(db: Session) -> None:
    """►► **Was die Anfrage bis hier schrieb, ist gespeichert, bevor ein Handgriff läuft.** ◄◄
    Ein Handgriff läuft in eigener Sitzung, während die Anfrage auf ihn wartet; hielte sie noch
    eine Sperre (die Anmeldung schreibt die Person), warteten beide aufeinander. Die eine bewusste
    Ausnahme von «einmal am Ende» – und nur hier."""
    db.commit()


def result_of(data: Any) -> Optional[int]:
    """Die Nummer, die eine Handlung angelegt hat – aus ihrer Antwort (``object_id``)."""
    if isinstance(data, dict):
        oid = data.get("object_id")
        return oid if isinstance(oid, int) else None
    return None


def dumps(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# Der vorbereitete Handgriff – Ereignisse im Log
# ---------------------------------------------------------------------------
#
# ``handgriff``          am Datensatz, den er betrifft: {talk?, mail?, method, path, body, line,
#                        depends, seen, hand?, by} – vorbereitet, der Probelauf gelang
# ``handgriff.done``     {handgriff, result?}: ausgeführt – eindeutig je Handgriff
# ``handgriff.dropped``  {handgriff, by}: weggelegt (oder durch einen neuen ersetzt)
#
# Offen ist abgeleitet: ohne ``done`` und ohne ``dropped``.

@dataclass
class Handgriff:
    id: int
    at: Any
    object_id: int
    actor_id: Optional[int]
    payload: dict[str, Any]
    done: Optional[dict[str, Any]] = None
    dropped: bool = False
    #: Die KI selbst hat ihn weggelegt (ersetzt) – für die Person kein Ergebnis.
    replaced: bool = False

    @property
    def talk(self) -> Optional[int]:
        return self.payload.get("talk")

    @property
    def private(self) -> bool:
        """Die Person hat ihn für sich vorbereiten lassen – im «+» oder in ihrem Claude (MCP)."""
        return self.talk is not None or self.payload.get("mcp") is not None

    @property
    def depends(self) -> list[int]:
        return [int(d) for d in self.payload.get("depends") or []]

    @property
    def is_open(self) -> bool:
        return self.done is None and not self.dropped


_LOAD = text("""
SELECT h.id, h.at, h.object_id, h.actor_id, h.payload,
       d.payload AS done,
       (SELECT x.payload ->> 'by' FROM log x WHERE x.event = 'handgriff.dropped'
         AND (x.payload ->> 'handgriff')::bigint = h.id LIMIT 1) AS dropped_by
  FROM log h
  LEFT JOIN log d ON d.event = 'handgriff.done' AND (d.payload ->> 'handgriff')::bigint = h.id
 WHERE h.event = 'handgriff' AND h.id = ANY(:ids)
 ORDER BY h.id""")


def load(db: Session, ids: list[int]) -> list[Handgriff]:
    if not ids:
        return []
    return [Handgriff(r.id, r.at, r.object_id, r.actor_id, r.payload or {}, r.done,
                      r.dropped_by is not None, r.dropped_by == "ai")
            for r in db.execute(_LOAD, {"ids": list(ids)})]


def get(db: Session, hid: int) -> Handgriff:
    found = load(db, [hid])
    if not found:
        raise NotFound(f"Handgriff «{hid}» gibt es nicht.")
    return found[0]


def may(h: Handgriff, viewer: UserProfile) -> bool:
    """►►► **Wer einen Handgriff sieht und entscheidet**: aus einem Gespräch nur, wer es führt
    (und der Admin) – ein Gespräch ist privat, ebenso was ihr Claude vorbereitet (MCP); aus einer
    Mail jedes Personal. ◄◄◄"""
    if not h.private:
        return True
    return policy.may(viewer, "private", h.actor_id)


def assert_may(db: Session, hid: int, viewer: UserProfile) -> Handgriff:
    h = get(db, hid)
    if not may(h, viewer):
        raise NotFound(f"Handgriff «{hid}» gibt es nicht.")
    return h


def _path_target(path: str) -> Optional[int]:
    """Die Objektnummer im Pfad – an ihr handelt die Handlung (``/records/100000123``)."""
    m = re.search(r"/(\d{9})(?:/|$)", path)
    return int(m.group(1)) if m else None


def _body_target(body: Any) -> Optional[int]:
    """Sonst der erste Datensatz in den Werten (``…object_id``, ``about``, ``to``)."""
    if not isinstance(body, dict):
        return None
    for key, value in body.items():
        if key.endswith("object_id") and isinstance(value, int):
            return value
    for key in ("about", "to"):
        values = body.get(key)
        if isinstance(values, list) and values and isinstance(values[0], int):
            return values[0]
    return None


def target_of(path: str, body: Any, home: int) -> int:
    """►► **Der Datensatz, den ein Handgriff betrifft** – dort steht er im Angehefteten. ◄◄"""
    return _path_target(path) or _body_target(body) or home


def _seen(db: Session, object_id: int) -> int:
    return int(db.execute(text("SELECT coalesce(max(id), 0) FROM log WHERE object_id = :o"),
                          {"o": object_id}).scalar() or 0)


#: Geändert heisst: eine Zeile des Datensatzes wurde geändert oder gelöscht – was neu an ihm
#: entsteht (eine Nachricht der Person, ein Dokument), ändert nicht, was vorbereitet wurde.
_CHANGED = text("""
SELECT table_name, event, changes FROM log
 WHERE object_id = :o AND id > :seen AND action IN ('update', 'delete')
 ORDER BY id LIMIT 20""")


def changed_since(db: Session, h: Handgriff) -> list[str]:
    """►►► **Regel 3: inzwischen geändert?** – nur, wenn die Handlung **an** einem Datensatz
    handelt (seine Nummer steht im Pfad): was sich dort seit der Vorbereitung geändert hat, in
    Worten. Leer = nichts. ◄◄◄"""
    oid = _path_target(fill_or_raw(h.payload.get("path") or ""))
    if oid is None:
        return []
    from ..domain.log import TABLE_WORDS
    out: list[str] = []
    for r in db.execute(_CHANGED, {"o": oid, "seen": int(h.payload.get("seen") or 0)}):
        word = TABLE_WORDS.get(r.table_name or "", r.table_name or "")
        fields = ", ".join(sorted((r.changes or {}).keys())[:4])
        line = f"{word}: {fields}" if fields else str(word)
        if line not in out:
            out.append(line)
    return out


def fill_or_raw(path: str) -> str:
    return re.sub(r"\{\$handgriff:\d+\}", "", path)


def prepare(db: Session, person: UserProfile, *, method: str, path: str, body: Any, line: str,
            home: int, talk: Optional[int] = None, mail: Optional[int] = None,
            mcp: Optional[int] = None, depends: Optional[list[int]] = None) -> tuple[Optional[int], Outcome]:
    """►►► **Einen Handgriff vorbereiten** – erst der Probelauf (als ``person``; offene
    Handgriffe, auf die er wartet, laufen davor mit), dann das Ereignis ``handgriff``. Geht er
    nicht, entsteht nichts, und das ``Outcome`` sagt warum (die KI korrigiert). Was nur von Hand
    geht, wird trotzdem ein Handgriff – «Öffnen». ◄◄◄"""
    op = operation_for(method, re.sub(r"\{\$handgriff:\d+\}", "100000001", path))
    if op is None:
        return None, Outcome(400, detail=f"«{method} {path}» ist keine Handlung des ERP.")
    # Worauf er wartet, muss die Person sehen dürfen – sonst gäbe es keine Kette, nur ein Leck.
    mine = [d for d in load(db, [int(x) for x in depends or []]) if may(d, person)]
    deps = [d.id for d in mine]
    before = [d for d in mine if d.is_open]
    known = {d.id: int(d.done.get("result")) for d in mine if d.done and d.done.get("result")}
    steps = [Step(d.payload["method"], d.payload["path"], d.payload.get("body"), d.id)
             for d in before] + [Step(method, path, body)]
    out = Outcome(200) if op.hand else call(person.id, steps, probe=True, results=known)
    # Ging der Probelauf nach aussen (KI, Zahlung), ist er bis dorthin gelungen – der echte Lauf
    # darf es; nur eine Datei braucht die Hand. Fehlen nur Werte (400, 422), wird er trotzdem eine
    # Karte – die Person ergänzt sie («Entwurf öffnen», «Ändern»); was sie nicht darf, nie.
    if not out.ok and not out.hand and not op.hand and not incomplete(out):
        return None, out
    target = target_of(path, body, home)
    payload: dict[str, Any] = {
        "method": method, "path": path, "body": body, "line": " ".join(line.split())[:300],
        "depends": deps, "seen": _seen(db, target), "hand": "Datei" if op.hand else "",
        "missing": out.detail if incomplete(out) else ""}
    if talk is not None:
        payload["talk"] = talk
    if mail is not None:
        payload["mail"] = mail
    if mcp is not None:
        payload["mcp"] = mcp
    hid = log.event(db, "handgriff", target, payload, kind="ai", actor=person.object_id)
    return hid, out


def incomplete(out: Outcome) -> bool:
    """►► **Es fehlen nur Werte** – die Route wies die Werte ab (400, 422), nicht die Person oder
    die Sache. Das ergänzt die Person; alles andere (Rechte, unbekannt, gesperrt) nie. ◄◄"""
    return out.status in (400, 422) and not out.hand


def _results(db: Session, deps: list[int]) -> tuple[dict[int, int], list[int]]:
    """Die Nummern der Handgriffe, auf die einer wartet – und welche noch offen sind."""
    known, waiting = {}, []
    for d in load(db, deps):
        if d.done and d.done.get("result"):
            known[d.id] = int(d.done["result"])
        elif d.is_open:
            waiting.append(d.id)
    return known, waiting


def run(db: Session, viewer: UserProfile, hid: int, body: Any = None) -> tuple[Handgriff, Outcome]:
    """►►► **Ausführen – genau einmal, ganz oder gar nicht.** ◄◄◄ Als ``viewer`` (seine Rechte),
    durch die echte Route. Abgewiesen wird, was nicht offen ist, worauf er noch wartet, was nur
    von Hand geht, und – ohne geänderte Werte – was sich seit der Vorbereitung geändert hat
    (Regel 3). ``body`` = die Werte, wie die Person sie geändert hat."""
    h = assert_may(db, hid, viewer)
    if not h.is_open:
        raise Conflict(f"Handgriff «{hid}» ist schon "
                                        f"{'ausgeführt' if h.done else 'weggelegt'}.")
    if h.payload.get("hand") and body is None:
        raise Conflict(f"Das geht nur von Hand ({h.payload['hand']}).")
    if h.payload.get("missing") and body is None:
        raise Conflict(f"Unvollständig – {h.payload['missing']}")
    known, waiting = _results(db, h.depends)
    if waiting:
        raise Conflict(f"Wartet auf Handgriff {', '.join(map(str, waiting))}.")
    if body is None:
        changed = changed_since(db, h)
        if changed:
            raise Conflict("Seit der Vorbereitung geändert: "
                                            + " · ".join(changed) + ".")

    def done(s: Session, data: Any) -> None:
        log.event(s, "handgriff.done", h.object_id, {"handgriff": h.id, "result": result_of(data)})
    step = Step(h.payload["method"], h.payload["path"], h.payload.get("body") if body is None else body)
    release(db)
    out = call(viewer.id, [step], probe=False, results=known, done=done, once=h.id)
    db.expire_all()
    return get(db, hid), out


def probe(db: Session, viewer: UserProfile, hid: int, body: Any) -> Outcome:
    """Eine geänderte Fassung prüfen («Ändern») – derselbe Probelauf, dieselbe Meldung der Route."""
    h = assert_may(db, hid, viewer)
    known, _waiting = _results(db, h.depends)
    release(db)
    return call(viewer.id, [Step(h.payload["method"], h.payload["path"], body)], probe=True,
                results=known)


def drop(db: Session, viewer: UserProfile, hid: int, by: str = "person") -> Handgriff:
    """**Weg** – der Handgriff geschieht nicht. Zweimal ist einmal; ausgeführt ist ausgeführt."""
    h = assert_may(db, hid, viewer)
    if h.done is not None:
        raise Conflict(f"Handgriff «{hid}» ist schon ausgeführt.")
    if not h.dropped:
        log.event(db, "handgriff.dropped", h.object_id, {"handgriff": h.id, "by": by},
                  kind="ai" if by == "ai" else None, actor=viewer.object_id if by == "ai" else None)
    db.flush()
    return get(db, hid)


def settle(db: Session, viewer: UserProfile, hid: int, result: Optional[int]) -> Handgriff:
    """**Von Hand erledigt** – ein Handgriff, der nur von Hand ging (Datei, Entwurf), ist getan:
    die Person hat es eben selbst gemacht. ``result`` = was dabei entstand."""
    h = assert_may(db, hid, viewer)
    if not h.is_open:
        raise Conflict(f"Handgriff «{hid}» ist nicht mehr offen.")
    log.event(db, "handgriff.done", h.object_id, {"handgriff": h.id, "result": result,
                                                 "hand": True})
    db.flush()
    return get(db, hid)


def state_of(h: Handgriff, waiting: bool) -> str:
    if h.done is not None:
        return "done"
    if h.dropped:
        return "dropped"
    return "waiting" if waiting else "open"


def view(db: Session, found: list[Handgriff]) -> list[Any]:
    """Die Karten – Name des Datensatzes, Quelle, Zustand, worauf sie warten."""
    from ..schemas.assistant import HandgriffOut
    from . import records
    names = records.labels(db, [h.object_id for h in found])
    open_ids = {h.id for h in load(db, sorted({d for h in found for d in h.depends})) if h.is_open}
    mails = _mail_sources(db, [int(h.payload["mail"]) for h in found if h.payload.get("mail")])
    out = []
    for h in found:
        op = operation_for(h.payload.get("method") or "", fill_or_raw(h.payload.get("path") or ""))
        waits = [d for d in h.depends if d in open_ids]
        rec = names.get(h.object_id)
        out.append(HandgriffOut(
            id=h.id, at=h.at, object_id=h.object_id, label=rec.name if rec else "",
            line=str(h.payload.get("line") or ""), method=h.payload.get("method") or "",
            path=h.payload.get("path") or "", body=h.payload.get("body"),
            state=state_of(h, bool(waits)), result=(h.done or {}).get("result"),
            source=mails.get(int(h.payload.get("mail") or 0),
                                "Claude" if h.payload.get("mcp") is not None else "Gespräch"), talk=h.talk,
            hand=str(h.payload.get("hand") or ""), missing=str(h.payload.get("missing") or ""),
            waits_for=waits,
            summary=op.summary if op else ""))
    return out


def _mail_sources(db: Session, ids: list[int]) -> dict[int, str]:
    from ..models import Message
    if not ids:
        return {}
    out = {}
    for m in db.query(Message).filter(Message.id.in_(ids)).all():
        sender = db.query(UserProfile).filter(UserProfile.object_id == m.sender_object_id).first()
        out[m.id] = f"Mail von {sender.display_name if sender else '?'}: {m.subject or ''}"[:200]
    return out


_OPEN_AT = text("""
SELECT h.id FROM log h
 WHERE h.event = 'handgriff' AND h.object_id = :o
   AND ((h.payload ->> 'talk' IS NULL AND h.payload ->> 'mcp' IS NULL) OR h.actor_id = :me)
   AND NOT EXISTS (SELECT 1 FROM log x WHERE x.event IN ('handgriff.done', 'handgriff.dropped')
                     AND (x.payload ->> 'handgriff')::bigint = h.id)
 ORDER BY h.id""")


def open_at(db: Session, object_id: int, viewer: UserProfile) -> list[Any]:
    """►►► **Die offenen Handgriffe an einem Datensatz** – aus Mails für jedes Personal, aus
    Gesprächen nur die eigenen (ein Gespräch ist privat). ◄◄◄"""
    ids = [r.id for r in db.execute(_OPEN_AT, {"o": object_id, "me": viewer.object_id or 0})]
    return view(db, load(db, ids))


_OPEN_MAIL_COUNTS = text("""
SELECT h.object_id, count(*) AS n FROM log h
 WHERE h.event = 'handgriff' AND h.payload ->> 'mail' IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM log x WHERE x.event IN ('handgriff.done', 'handgriff.dropped')
                     AND (x.payload ->> 'handgriff')::bigint = h.id)
 GROUP BY h.object_id""")


def open_mail_counts(db: Session) -> dict[int, int]:
    """Offene Handgriffe aus Mails je Datensatz – sie zählen dort in «zu tun» (EINE Abfrage)."""
    return {r.object_id: int(r.n) for r in db.execute(_OPEN_MAIL_COUNTS)}
