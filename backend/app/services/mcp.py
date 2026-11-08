"""►►► **MCP – das ERP für den eigenen Claude der Person** (Claude.ai, Desktop, Code, Mobile). ◄◄◄
(``docs/konzept/mcp.md``)

Ein Claude-Client verbindet sich mit ``/api/v1/mcp`` und arbeitet dort **als diese Person**: mit
ihren Rechten, durch dieselben Routen wie ein Klick (``services/handgriff``), mit denselben
Werkzeugen wie das «+» (``ai_tools.tools_for`` · ``erp_tools``). Er **liest** und **bereitet vor**;
ausgeführt wird ein Handgriff von der Person im ERP (Angeheftetes am Datensatz, privat wie ein
Gespräch). Ausführen über MCP ist ein Werkzeug mehr, wenn es so weit ist – sonst ändert sich nichts.

**Anmelden** ist OAuth 2.1 (was jeder Claude-Client spricht) über die Anmeldung, die es schon gibt:
die Person meldet sich im ERP an (Firebase: Magic Link, Google, Passkey) und erlaubt dort. Es gibt
**keine Tabelle** dafür:

* Ein **Client** registriert sich selbst (RFC 7591); seine Kennung IST seine signierte Beschreibung
  (Name, Rückkehr-Adressen, ``core/signed``).
* Der **Code** ist signiert, gilt zwei Minuten, verlangt PKCE (S256) und lässt sich genau einmal
  einlösen: das Einlösen schreibt das Ereignis ``mcp.grant`` – ein eindeutiger Index auf seiner
  Einmal-Nummer weist ein zweites ab.
* **Zugang** (eine Stunde) und **Erneuerung** (90 Tage, bei jedem Gebrauch neu) sind signiert und
  nennen ihre Verbindung (``mcp.grant``); getrennt ist sie mit ``mcp.revoked`` – das prüft jede
  Anfrage. Wer kein Personal mehr ist, kommt nicht mehr hinein.

Das Protokoll ist JSON-RPC über einen einzigen ``POST`` (Streamable HTTP, Antwort als JSON, ohne
Sitzung): ``initialize``, ``ping``, ``tools/list``, ``tools/call``.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Optional
from urllib.parse import urlencode, urlsplit

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import signed
from ..core.config import get_settings
from ..models import UserProfile
from . import access, ai, ai_tools, handgriff, log

PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26")
SCOPE = "erp"
CODE_TTL = 120
ASK_TTL = 600
ACCESS_TTL = 3600
REFRESH_TTL = 90 * 86400

INSTRUCTIONS = (
    "Das ERP von INEXXIO. Du arbeitest als die angemeldete Person, mit ihren Rechten. Suche "
    "Datensätze mit `find`, lies sie mit `record` und `history`, frage das Wissen mit `wissen`. "
    "Was das ERP kann, findest du mit `handlungen` und `handlung`; lesende Routen rufst du mit "
    "`abrufen`. Ändern heisst: mit `vorbereiten` einen Handgriff vorbereiten – die Person führt "
    "ihn im ERP aus. Nenne Datensätze immer mit Nummer und Name.")


class Problem(Exception):
    """Ein OAuth-Fehler: ``error`` (RFC 6749) und ein Satz."""

    def __init__(self, error: str, description: str, status: int = 400):
        super().__init__(description)
        self.error, self.description, self.status = error, description, status

    def body(self) -> dict[str, str]:
        return {"error": self.error, "error_description": self.description}


# ---------------------------------------------------------------------------
# Adressen und Metadaten
# ---------------------------------------------------------------------------

def base() -> str:
    return get_settings().frontend_base_url.rstrip("/")


def resource() -> str:
    return f"{base()}/api/v1/mcp"


def resource_metadata_url() -> str:
    return f"{base()}/.well-known/oauth-protected-resource"


def protected_resource() -> dict[str, Any]:
    """RFC 9728 – wo man sich für das ERP anmeldet."""
    return {"resource": resource(), "authorization_servers": [base()],
            "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"],
            "resource_name": "INEXXIO ERP"}


def authorization_server() -> dict[str, Any]:
    """RFC 8414 – wie man sich anmeldet."""
    oauth = f"{base()}/api/v1/mcp/oauth"
    return {"issuer": base(), "authorization_endpoint": f"{oauth}/authorize",
            "token_endpoint": f"{oauth}/token", "registration_endpoint": f"{oauth}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"], "scopes_supported": [SCOPE]}


# ---------------------------------------------------------------------------
# Client, Anfrage, Code
# ---------------------------------------------------------------------------

def _redirect_ok(uri: Any) -> bool:
    """Eine Rückkehr-Adresse: https, oder http nur auf diesem Rechner (Claude Code)."""
    if not isinstance(uri, str) or len(uri) > 500:
        return False
    u = urlsplit(uri)
    if u.fragment or not u.hostname:
        return False
    return u.scheme == "https" or (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1"))


def register(data: dict[str, Any]) -> dict[str, Any]:
    """►► **Ein Client meldet sich an** (RFC 7591) – seine Kennung ist seine signierte
    Beschreibung; gespeichert wird nichts. ◄◄"""
    uris = data.get("redirect_uris")
    if not isinstance(uris, list) or not 0 < len(uris) <= 5 or not all(_redirect_ok(u) for u in uris):
        raise Problem("invalid_redirect_uri", "Rückkehr-Adressen: https, oder http auf localhost.")
    name = " ".join(str(data.get("client_name") or "Claude").split())[:80] or "Claude"
    client_id = signed.sign({"r": uris, "n": name}, "mcp.client")
    return {"client_id": client_id, "client_name": name, "redirect_uris": uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}


def client_of(client_id: str) -> dict[str, Any]:
    try:
        return signed.read(client_id, "mcp.client")
    except signed.Invalid:
        raise Problem("invalid_client", "Diesen Client kennt das ERP nicht.", 401)


def _fingerprint(client_id: str) -> str:
    return hashlib.sha256(client_id.encode()).hexdigest()[:24]


def ask(q: dict[str, str]) -> str:
    """►► **Die Anfrage eines Clients prüfen** – wer, wohin zurück, PKCE. Was hier nicht stimmt,
    geht nie zurück an eine Adresse (``Problem``); sonst die Seite im ERP, auf der die Person
    erlaubt. ◄◄"""
    client = client_of(q.get("client_id", ""))
    redirect = q.get("redirect_uri") or (client["r"][0] if len(client["r"]) == 1 else "")
    if redirect not in client["r"]:
        raise Problem("invalid_request", "Diese Rückkehr-Adresse gehört nicht zum Client.")
    if q.get("response_type") != "code":
        raise Problem("unsupported_response_type", "Nur «code».")
    if q.get("code_challenge_method") != "S256" or not 43 <= len(q.get("code_challenge", "")) <= 128:
        raise Problem("invalid_request", "PKCE mit S256 ist Pflicht.")
    r = signed.sign({"c": q["client_id"], "ru": redirect, "ch": q["code_challenge"],
                     "s": q.get("state") or "", "n": client["n"]}, "mcp.ask", ASK_TTL)
    return f"{base()}/erp/verbinden?{urlencode({'r': r})}"


def _ask(r: str) -> dict[str, Any]:
    try:
        return signed.read(r, "mcp.ask")
    except signed.Invalid as e:
        raise Problem("invalid_request", f"{e} Bitte im Claude-Client neu verbinden.")


def describe(r: str) -> dict[str, str]:
    """Was die Person erlaubt: welcher Client, zurück wohin."""
    a = _ask(r)
    return {"client": a["n"], "host": urlsplit(a["ru"]).hostname or ""}


def _back(a: dict[str, Any], **params: str) -> str:
    sep = "&" if "?" in a["ru"] else "?"
    return a["ru"] + sep + urlencode({**params, **({"state": a["s"]} if a["s"] else {}), "iss": base()})


def approve(person: UserProfile, r: str, allow: bool) -> str:
    """►► **Die Person erlaubt (oder nicht)** – zurück an den Client, mit Code oder Absage. ◄◄"""
    a = _ask(r)
    if not allow:
        return _back(a, error="access_denied")
    if not access.is_staff(person):
        raise Problem("access_denied", "Das ERP ist nur für Mitarbeitende.", 403)
    code = signed.sign({"p": person.object_id, "c": _fingerprint(a["c"]), "ru": a["ru"],
                        "ch": a["ch"], "k": secrets.token_urlsafe(12), "n": a["n"]},
                       "mcp.code", CODE_TTL)
    return _back(a, code=code)


# ---------------------------------------------------------------------------
# Zugang
# ---------------------------------------------------------------------------

def _tokens(person_id: int, grant: int) -> dict[str, Any]:
    return {"access_token": signed.sign({"p": person_id, "g": grant}, "mcp.access", ACCESS_TTL),
            "token_type": "Bearer", "expires_in": ACCESS_TTL, "scope": SCOPE,
            "refresh_token": signed.sign({"p": person_id, "g": grant}, "mcp.refresh", REFRESH_TTL)}


def _verifier_ok(verifier: str, challenge: str) -> bool:
    digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return secrets.compare_digest(digest, challenge)


def token(db: Session, form: dict[str, str]) -> dict[str, Any]:
    """►►► **Code oder Erneuerung gegen Zugang** (RFC 6749 §4.1.3, §6). ◄◄◄"""
    kind = form.get("grant_type")
    if kind == "authorization_code":
        try:
            c = signed.read(form.get("code", ""), "mcp.code")
        except signed.Invalid:
            raise Problem("invalid_grant", "Der Code ist ungültig oder abgelaufen.")
        if (c["c"] != _fingerprint(form.get("client_id", "")) or c["ru"] != form.get("redirect_uri")
                or not _verifier_ok(form.get("code_verifier", ""), c["ch"])):
            raise Problem("invalid_grant", "Code, Client, Rückkehr-Adresse oder PKCE passen nicht.")
        person = _person(db, c["p"])
        try:
            with db.begin_nested():
                grant = log.event(db, "mcp.grant", person.object_id, {"nonce": c["k"], "client": c["n"]},
                                  kind="person", actor=person.object_id)
        except IntegrityError:
            raise Problem("invalid_grant", "Dieser Code ist schon eingelöst.")
        return _tokens(person.object_id, grant)
    if kind == "refresh_token":
        try:
            t = signed.read(form.get("refresh_token", ""), "mcp.refresh")
        except signed.Invalid:
            raise Problem("invalid_grant", "Die Erneuerung ist ungültig oder abgelaufen.")
        _assert_open(db, t["g"])
        return _tokens(_person(db, t["p"]).object_id, t["g"])
    raise Problem("unsupported_grant_type", "Nur «authorization_code» und «refresh_token».")


def _person(db: Session, object_id: int) -> UserProfile:
    person = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if person is None or not access.is_staff(person):
        raise Problem("invalid_grant", "Das ERP ist nur für Mitarbeitende.")
    return person


_REVOKED = text("SELECT 1 FROM log WHERE event = 'mcp.revoked' AND (payload ->> 'grant')::bigint = :g")


def _assert_open(db: Session, grant: int) -> None:
    if db.execute(_REVOKED, {"g": grant}).first() is not None:
        raise Problem("invalid_grant", "Diese Verbindung ist getrennt.")


def bearer(db: Session, header: Optional[str]) -> tuple[UserProfile, int]:
    """►► **Wer fragt** – aus dem Zugang: die Person (noch Personal) und ihre Verbindung (nicht
    getrennt). Sonst ``Problem`` (401). ◄◄"""
    scheme, _, raw = (header or "").partition(" ")
    if scheme.lower() != "bearer" or not raw:
        raise Problem("invalid_token", "Anmeldung fehlt.", 401)
    try:
        t = signed.read(raw.strip(), "mcp.access")
        _assert_open(db, t["g"])
        return _person(db, t["p"]), t["g"]
    except (signed.Invalid, Problem) as e:
        raise Problem("invalid_token", str(e), 401)


_GRANTS = text("""
SELECT g.id, g.at, g.payload ->> 'client' AS client FROM log g
 WHERE g.event = 'mcp.grant' AND g.object_id = :p
   AND NOT EXISTS (SELECT 1 FROM log x WHERE x.event = 'mcp.revoked'
                     AND (x.payload ->> 'grant')::bigint = g.id)
 ORDER BY g.id DESC""")


def grants(db: Session, person: UserProfile) -> list[dict[str, Any]]:
    """Die offenen Verbindungen der Person – je erlaubtem Client eine."""
    return [{"id": r.id, "at": r.at, "client": r.client or "Claude"}
            for r in db.execute(_GRANTS, {"p": person.object_id})]


def revoke(db: Session, person: UserProfile, grant: int) -> None:
    """**Trennen** – ab sofort gilt kein Zugang und keine Erneuerung dieser Verbindung mehr."""
    if grant not in {g["id"] for g in grants(db, person)}:
        raise Problem("invalid_request", f"Die Verbindung «{grant}» gibt es nicht.", 404)
    log.event(db, "mcp.revoked", person.object_id, {"grant": grant})


# ---------------------------------------------------------------------------
# Das Protokoll
# ---------------------------------------------------------------------------

def tools(db: Session, person: UserProfile, grant: int) -> list[ai.Tool]:
    """Dieselben Werkzeuge wie im «+» – gelesen mit den Rechten der Person; ein Handgriff gehört
    ihr allein (``mcp``) und steht am Datensatz, den er betrifft."""

    def prepare(method: str, path: str, body: Any, line: str, depends: list[int]):
        return handgriff.prepare(db, person, method=method, path=path, body=body, line=line,
                                 home=person.object_id, mcp=grant, depends=depends)

    def where(hid: int) -> str:
        h = handgriff.get(db, hid)
        return f" Die Person führt ihn im ERP aus: {base()}/erp?open={h.object_id}"

    return [*ai_tools.tools_for(db, person), *ai_tools.erp_tools(prepare, person, where)]


def _schema(t: ai.Tool) -> dict[str, Any]:
    return {"name": t.name, "description": t.description,
            "inputSchema": {"type": "object", "properties": t.properties, "required": list(t.required)}}


def _result(rid: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(db: Session, person: UserProfile, grant: int, msg: Any) -> Optional[dict[str, Any]]:
    """►►► **Eine Nachricht des Clients** – die Antwort, oder ``None`` für eine Mitteilung. ◄◄◄"""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(None, -32600, "Keine JSON-RPC-Anfrage.")
    method, rid, params = msg["method"], msg.get("id"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _result(rid, {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                             "capabilities": {"tools": {"listChanged": False}},
                             "serverInfo": {"name": "inexxio", "title": "INEXXIO ERP", "version": "1"},
                             "instructions": INSTRUCTIONS})
    if method == "ping":
        return _result(rid, {})
    if method == "tools/list":
        return _result(rid, {"tools": [_schema(t) for t in tools(db, person, grant)]})
    if method == "tools/call":
        found = {t.name: t for t in tools(db, person, grant)}.get(str(params.get("name")))
        if found is None:
            return _error(rid, -32602, f"Das Werkzeug «{params.get('name')}» gibt es nicht.")
        args = params.get("arguments") or {}
        try:
            with db.begin_nested():
                out = found.run(args if isinstance(args, dict) else {})
            failed = False
        except Exception as e:      # ein Werkzeug scheitert als Antwort, nie als Absturz
            out, failed = f"Geht nicht: {getattr(e, 'detail', None) or e}", True
        return _result(rid, {"content": [{"type": "text", "text": out}], "isError": failed})
    return _error(rid, -32601, f"Die Methode «{method}» gibt es nicht.")
