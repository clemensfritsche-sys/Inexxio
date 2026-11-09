"""EIN Fehlermodell (``domain/errors``, Änderungsakte U6): jede Abweisung hat dieselbe Form, und
Fachschicht und Dienste kennen kein HTTP."""

import pathlib
import re

from fastapi.testclient import TestClient

from app.domain.errors import Conflict, rejected
from app.main import app

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def test_no_service_and_no_domain_speaks_http():
    """Bug-Form: ein ``HTTPException`` in einem Dienst – die Abweisung hätte zwei Formen, und die
    Fachschicht hinge wieder am Web-Rahmen."""
    hits = [str(p.relative_to(APP)) for p in APP.rglob("*.py")
            if p.name != "main.py" and re.search(r"\bHTTPException\b", p.read_text())]
    assert not hits, f"HTTPException ausserhalb von main.py: {hits}"
    domain = [str(p.relative_to(APP)) for p in (APP / "domain").rglob("*.py")
              if re.search(r"^\s*(from|import) (fastapi|starlette)", p.read_text(), re.M)]
    assert not domain, f"Die Fachschicht importiert den Web-Rahmen: {domain}"


def test_every_rejection_has_one_shape():
    client = TestClient(app)
    unknown = client.get("/api/v1/gibt-es-nicht")
    assert unknown.status_code == 404 and unknown.json()["code"] == "not_found" and unknown.json()["detail"]
    anonymous = client.get("/api/v1/erp/records")
    assert anonymous.status_code in (401, 403) and set(anonymous.json()) == {"detail", "code"}
    assert Conflict("x", code="pick_stale").body() == {"detail": "x", "code": "pick_stale"}
    assert rejected(404, "weg").status == 404 and rejected(418, "?").status == 400
