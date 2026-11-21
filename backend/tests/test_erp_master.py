"""►►► **ERP ist Master – auch für den Zugang einer Person.** ◄◄◄

Was eine Person im Konto an sich selbst sieht oder tut (``/api/v1/auth/…``), kann das ERP am
Datensatz auch – oder es steht begründet in ``policy.SELF_SERVICE`` als ``SelfOnly``. Dazu der
Zugang am Datensatz (Passkeys, Verbindungen mit Claude: ``routers/access``) und die Regel, wann
eine Verbindung mit Claude noch offen ist (``mcp._OPEN``).
"""

from datetime import timedelta

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient

from app.core import clock, signed
from app.core.actor import act
from app.core.auth import get_current_user
from app.core.database import get_db
from app.domain import policy
from app.main import app
from app.models import WebAuthnCredential
from app.services import mcp
from tests.test_mcp import _connect


def _calls(dependant) -> set:
    out = set()
    for d in dependant.dependencies:
        out.add(d.call)
        out |= _calls(d)
    return out


def _routes() -> dict[str, set]:
    """«METHODE /pfad» → die Abhängigkeiten der Route."""
    out = {}
    for c in iter_route_contexts(app.routes):
        if not isinstance(c.route, APIRoute):
            continue
        for m in set(c.methods or ()) - {"HEAD"}:
            out[f"{m} {c.path}"] = _calls(c.route.dependant)
    return out


def _self_service(routes: dict[str, set]) -> set[str]:
    """Die Selbstbedienung: Routen unter ``/api/v1/auth/``, für die man angemeldet ist."""
    return {k for k, calls in routes.items()
            if k.split(" ", 1)[1].startswith("/api/v1/auth/") and get_current_user in calls}


def missing_mirrors(routes: dict[str, set], table: dict) -> list[str]:
    """Was gegen «ERP ist Master» verstösst – leer, wenn alles stimmt."""
    wrong = [f"«{k}» hat kein Gegenstück im ERP und steht nicht in SELF_SERVICE."
             for k in sorted(_self_service(routes) - set(table))]
    wrong += [f"«{k}» steht in SELF_SERVICE, ist aber keine Route der Selbstbedienung."
              for k in sorted(set(table) - _self_service(routes))]
    for k, v in table.items():
        if isinstance(v, policy.SelfOnly):
            wrong += [] if v.why.strip() else [f"«{k}» ist SelfOnly ohne Grund."]
            continue
        for erp in (v if isinstance(v, tuple) else (v,)):
            if erp not in routes or not erp.split(" ", 1)[1].startswith("/api/v1/erp/"):
                wrong.append(f"Das Gegenstück «{erp}» von «{k}» ist keine Route des ERP.")
    return wrong


def test_everything_a_person_does_outside_the_erp_the_erp_can_do():
    assert missing_mirrors(_routes(), policy.SELF_SERVICE) == []


def test_the_guard_catches_its_bug_forms():
    """Bug-Formen: (a) eine neue Selbstbedienungs-Route ohne Eintrag; (b) ein Gegenstück, das es
    nicht (mehr) gibt – z. B. so, wie es vor dieser Runde für Passkeys und Claude war; (c) ein
    SelfOnly ohne Grund."""
    routes = _routes()
    table = dict(policy.SELF_SERVICE)
    assert missing_mirrors({**routes, "POST /api/v1/auth/me/neu": {get_current_user}}, table)
    without = {k: v for k, v in routes.items() if "/erp/records/{object_id}/passkeys" not in k
               and "/erp/records/{object_id}/mcp" not in k}
    found = missing_mirrors(without, table)
    assert len(found) == 4 and all("Gegenstück" in f for f in found), found
    assert missing_mirrors(routes, {**table, "POST /api/v1/auth/me/email-check": policy.SelfOnly(" ")})


# ---------------------------------------------------------------------------
# Der Zugang am Datensatz
# ---------------------------------------------------------------------------

@pytest.fixture
def as_who(db, monkeypatch):
    monkeypatch.setattr(db, "commit", db.flush)
    who = {}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: who["p"]

    def client(person):
        who["p"] = person
        act(db, "person", person.object_id, "test")
        return TestClient(app)
    yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _passkey(db, person) -> WebAuthnCredential:
    act(db, "person", person.object_id, "test")
    row = WebAuthnCredential(user_id=person.id, credential_id=f"cred-{person.id}", public_key=b"k",
                             sign_count=0, rp_id="localhost", device_name="Laptop")
    db.add(row)
    db.flush()
    return row


def test_the_admin_and_the_person_see_and_cut_the_access_an_employee_does_not(db, make_person, as_who):
    person, admin, colleague = make_person("employee"), make_person("admin"), make_person("employee")
    key = _passkey(db, person)
    _, _ = _connect(db, person)
    base = f"/api/v1/erp/records/{person.object_id}"

    other = as_who(colleague)
    assert other.get(f"{base}/passkeys").status_code == 403
    assert other.get(f"{base}/mcp").status_code == 403
    assert other.get(base).json()["may_access"] is False

    me = as_who(person)
    assert [p["device_name"] for p in me.get(f"{base}/passkeys").json()] == ["Laptop"]
    assert me.get(base).json()["may_access"] is True

    boss = as_who(admin)
    grants = boss.get(f"{base}/mcp").json()
    assert len(grants) == 1 and grants[0]["used"]
    assert boss.post(f"{base}/mcp/{grants[0]['id']}/revoke").json() == []
    assert boss.post(f"{base}/mcp/{grants[0]['id']}/revoke").status_code == 404
    assert boss.delete(f"{base}/passkeys/{key.id}").status_code == 204
    assert boss.get(f"{base}/passkeys").json() == []
    # Das Konto sieht dieselbe Wahrheit – derselbe Dienst.
    assert as_who(person).get("/api/v1/auth/me/mcp").json() == []


def test_a_connection_unused_for_longer_than_a_refresh_lives_is_not_connected(db, make_person, monkeypatch):
    """Trennt die Person in Claude selbst, erfährt das ERP es nie. Was seit ``REFRESH_TTL`` nicht
    benutzt wurde, lässt sich nie mehr erneuern – es steht nicht mehr in der Liste und wird
    abgewiesen. Bug-Form: die Liste zeigt jede nicht getrennte Verbindung, für immer."""
    person = make_person("employee")
    client_id, tokens = _connect(db, person)
    assert len(mcp.grants(db, person)) == 1

    later = clock.utcnow() + timedelta(seconds=mcp.REFRESH_TTL + 60)
    monkeypatch.setattr(clock, "utcnow", lambda: later)
    assert mcp.grants(db, person) == []
    form = {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id}
    with pytest.raises(mcp.Problem, match="getrennt"):
        mcp.token(db, form)

    # Und die Erneuerung selbst trägt ihren Ablauf (signiert, ``REFRESH_TTL``): dieselbe, abgelaufen.
    old = signed.sign(signed.read(tokens["refresh_token"], "mcp.refresh"), "mcp.refresh", -1)
    with pytest.raises(mcp.Problem, match="abgelaufen"):
        mcp.token(db, {**form, "refresh_token": old})


def test_a_refresh_keeps_a_connection_open_and_says_when_it_was_used(db, make_person):
    person = make_person("employee")
    client_id, tokens = _connect(db, person)
    first = mcp.grants(db, person)[0]
    mcp.token(db, {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
                   "client_id": client_id})
    again = mcp.grants(db, person)[0]
    assert again["id"] == first["id"] and again["used"] >= first["used"]


def test_the_access_of_a_person_is_no_handgriff():
    """Passkeys entfernen und Claude trennen bereitet keine KI vor (``handgriff._routes``)."""
    from app.services import handgriff
    assert not [o for o in (*handgriff.operations(), *handgriff.reads())
                if "/passkeys" in o.path or o.path.endswith(("/mcp", "/revoke"))]
