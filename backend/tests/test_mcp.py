"""MCP – das ERP für den eigenen Claude der Person (``services/mcp``, ``docs/konzept/mcp.md``).

Geprüft wird der ganze Weg eines Claude-Clients (anmelden, erlauben, Code tauschen, fragen,
erneuern, trennen) und die Regeln, die ihn sicher machen: PKCE, ein Code genau einmal, nur
Personal, getrennt ist getrennt, ein Handgriff aus Claude gehört der Person.
"""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.core.actor import act
from app.main import app
from app.services import handgriff, mcp

REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def _code(person, client_id: str, challenge: str) -> str:
    page = mcp.ask({"client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
                    "code_challenge": challenge, "code_challenge_method": "S256", "state": "xyz"})
    r = parse_qs(urlsplit(page).query)["r"][0]
    assert mcp.describe(r) == {"client": "Claude", "host": "claude.ai"}
    back = parse_qs(urlsplit(mcp.approve(person, r, True)).query)
    assert back["state"] == ["xyz"]
    return back["code"][0]


def _connect(db, person) -> tuple[str, dict]:
    client_id = mcp.register({"redirect_uris": [REDIRECT], "client_name": "Claude"})["client_id"]
    verifier, challenge = _pkce()
    code = _code(person, client_id, challenge)
    act(db, "external", None, "mcp")
    tokens = mcp.token(db, {"grant_type": "authorization_code", "code": code, "client_id": client_id,
                            "redirect_uri": REDIRECT, "code_verifier": verifier})
    return client_id, tokens


def test_a_claude_client_connects_asks_refreshes_and_is_cut_off(db, make_person):
    person = make_person("employee")
    _, tokens = _connect(db, person)
    who, grant = mcp.bearer(db, f"Bearer {tokens['access_token']}")
    assert who.object_id == person.object_id

    hello = mcp.handle(db, who, grant, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                        "params": {"protocolVersion": "2025-06-18"}})
    assert hello["result"]["protocolVersion"] == "2025-06-18"
    names = {t["name"] for t in mcp.handle(db, who, grant, {"jsonrpc": "2.0", "id": 2,
                                                            "method": "tools/list"})["result"]["tools"]}
    assert {"find", "record", "history", "wissen", "handlungen", "handlung", "abrufen",
            "vorbereiten"} <= names
    assert "ausfuehren" not in names                       # ausgeführt wird im ERP
    found = mcp.handle(db, who, grant, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                        "params": {"name": "find", "arguments": {"q": str(person.object_id)}}})
    assert str(person.object_id) in found["result"]["content"][0]["text"]
    assert mcp.handle(db, who, grant, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    again = mcp.token(db, {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]})
    assert mcp.bearer(db, f"Bearer {again['access_token']}")[1] == grant

    assert [g["id"] for g in mcp.grants(db, person)] == [grant]
    mcp.revoke(db, person, grant)
    assert mcp.grants(db, person) == []
    with pytest.raises(mcp.Problem) as cut:
        mcp.bearer(db, f"Bearer {again['access_token']}")
    assert cut.value.status == 401
    with pytest.raises(mcp.Problem):
        mcp.token(db, {"grant_type": "refresh_token", "refresh_token": again["refresh_token"]})


def test_a_code_works_exactly_once_and_only_with_its_verifier(db, make_person):
    """Bug-Form: ohne ``ix_log_mcp_grant`` liesse sich ein abgefangener Code ein zweites Mal
    tauschen; ohne PKCE-Prüfung ohne den Schlüssel des Clients."""
    person = make_person("employee")
    client_id = mcp.register({"redirect_uris": [REDIRECT]})["client_id"]
    verifier, challenge = _pkce()
    code = _code(person, client_id, challenge)
    act(db, "external", None, "mcp")
    form = {"grant_type": "authorization_code", "code": code, "client_id": client_id,
            "redirect_uri": REDIRECT, "code_verifier": "falsch-" + verifier}
    with pytest.raises(mcp.Problem, match="PKCE"):
        mcp.token(db, form)
    form["code_verifier"] = verifier
    mcp.token(db, form)
    with pytest.raises(mcp.Problem, match="schon eingelöst"):
        mcp.token(db, form)


def test_only_staff_and_only_registered_return_addresses(db, make_person):
    client_id = mcp.register({"redirect_uris": [REDIRECT]})["client_id"]
    _, challenge = _pkce()
    with pytest.raises(mcp.Problem):
        mcp.ask({"client_id": client_id, "redirect_uri": "https://boese.example/cb",
                 "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256"})
    with pytest.raises(mcp.Problem):
        mcp.register({"redirect_uris": ["http://boese.example/cb"]})
    assert mcp.register({"redirect_uris": ["http://localhost:33418/callback"]})["client_id"]
    with pytest.raises(mcp.Problem):
        _code(make_person("user"), client_id, challenge)


def test_a_handgriff_from_claude_belongs_to_the_person():
    """Was der eigene Claude vorbereitet, ist privat wie ein Gespräch."""
    mine = handgriff.Handgriff(1, None, 100000001, 100000002, {"mcp": 7})
    owner = type("P", (), {"role": "employee", "object_id": 100000002})()
    other = type("P", (), {"role": "employee", "object_id": 100000003})()
    assert handgriff.may(mine, owner) and not handgriff.may(mine, other)
    assert handgriff.may(handgriff.Handgriff(2, None, 100000001, None, {"mail": 3}), other)


def test_the_door_says_where_to_log_in():
    client = TestClient(app)
    res = client.post("/api/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert res.status_code == 401
    assert "resource_metadata=" in res.headers["www-authenticate"]
    meta = client.get("/.well-known/oauth-protected-resource").json()
    assert meta["resource"].endswith("/api/v1/mcp")
    server = client.get("/.well-known/oauth-authorization-server").json()
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert client.get("/api/v1/mcp").status_code == 405


def test_claude_logins_are_no_handgriffe():
    """Die Anmeldung von Claude (``routers/mcp``) ist nichts, was eine KI vorbereitet."""
    assert not [o for o in handgriff.operations() if "/mcp" in o.path]
