"""►►► **Das Feld sagt selbst, was es braucht** – für die Oberfläche und für die KI. ◄◄◄

Die KI liest von einer Handlung nur, was die Route über sich sagt (``handgriff.operations`` →
JSON-Schema). Steht eine Regel nur im Prüfcode, sieht sie sie nicht und rät. Darum drei Wächter,
je mit ihrer Bug-Form:

1. **Jedes Feld einer Handlung hat eine Beschreibung** – Bug-Form: «size: string», die Regel
   (drei Masse, aufsteigend, mm) steht nur im Prüfer.
2. **Kein Feldprüfer korrigiert still** – ein zu langer Text wird abgewiesen, nie gekürzt.
   Bug-Form: der Name wurde auf 32 Zeichen geschnitten, der Probelauf merkte nichts.
3. **Eine Abweisung nennt ihr Feld** (``field`` · ``fields``) – Bug-Form: nur ein Satz, die
   Oberfläche weiss nicht, an welches Feld er gehört.
"""

import inspect
import typing

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.services import handgriff

# Eine Zeichenkette, die kein Putzen ändert (trimmen, gross, klein) – nur eine Kürzung.
LONG = "1" * 5000


def _undescribed(schema, where: str, out: list[str]) -> None:
    if isinstance(schema, dict):
        for name, prop in (schema.get("properties") or {}).items():
            if not (isinstance(prop, dict) and prop.get("description")):
                out.append(f"{where}.{name}")
            _undescribed(prop, f"{where}.{name}", out)
        for key in ("items", "anyOf", "allOf", "oneOf"):
            for sub in (schema[key] if isinstance(schema.get(key), list) else [schema.get(key)]):
                _undescribed(sub, where, out)


def test_every_field_of_an_operation_says_what_it_is():
    missing: list[str] = []
    for op in handgriff.operations():
        _undescribed(op.schema or {}, op.key, missing)
    assert not missing, "Ohne Beschreibung (die KI sieht nur den Typ):\n" + "\n".join(
        sorted(set(missing)))


def _body_models() -> list[type[BaseModel]]:
    """Die Modelle, die eine Handlung als Rumpf nimmt – samt den verschachtelten."""
    from app.main import app
    keys = {o.key for o in handgriff.operations()}
    found: list[type[BaseModel]] = []

    def walk(tp) -> None:
        if inspect.isclass(tp) and issubclass(tp, BaseModel):
            if tp not in found:
                found.append(tp)
                for f in tp.model_fields.values():
                    walk(f.annotation)
        else:
            for arg in typing.get_args(tp):
                walk(arg)

    for c in iter_route_contexts(app.routes):
        if not isinstance(c.route, APIRoute):
            continue
        for method in set(c.methods or ()) - {"HEAD"}:
            if f"{method} {c.path}" in keys:
                for param in c.route.dependant.body_params:
                    walk(param.field_info.annotation)
    return found


def _takes_text(annotation) -> bool:
    return annotation is str or str in typing.get_args(annotation)


def test_no_field_shortens_a_value_silently():
    shortened: list[str] = []
    for model in _body_models():
        for name, field in model.model_fields.items():
            if not _takes_text(field.annotation):
                continue
            try:
                got = model.__pydantic_validator__.validate_assignment(
                    model.model_construct(), name, LONG)
            except ValidationError:
                continue                       # abgewiesen – mit Satz, gut so
            value = getattr(got, name, LONG)
            if isinstance(value, str) and value != LONG and len(value) < len(LONG):
                shortened.append(f"{model.__name__}.{name}")
    assert not shortened, "Still gekürzt statt abgewiesen: " + ", ".join(shortened)


@pytest.fixture
def client(db, monkeypatch):
    from app.core.auth import get_current_user
    from app.core.database import get_db
    from app.main import app
    from tests.factories import new_person

    staff = new_person(db, "employee")
    monkeypatch.setattr(db, "commit", db.flush)
    app.dependency_overrides[get_current_user] = lambda: staff
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_a_rejection_names_its_field(client):
    r = client.post("/api/v1/erp/articles/validate",
                    json={"name": "Welle", "size": "40x3", "weight_kg": "abc"})
    assert r.status_code == 422
    body = r.json()
    assert body["field"] in ("size", "weight_kg")
    assert set(body["fields"]) == {"size", "weight_kg"}, body


def test_a_partner_is_always_a_person(db):
    """Bug-Form: eine Firma wird als Partner modelliert – der Fehler kommt erst beim Handeln,
    mit einem Satz, der nichts erklärt («kein Datensatz, mit dem man handeln kann»)."""
    from app.domain.errors import Invalid
    from app.services import articles, voucher_input
    from tests.factories import new_person
    from app.services import sites

    firm = sites.resolve(db, {"company_name": "Digitec Galaxus", "legal_form": "AG"}, None,
                         allow_own=False)
    person = new_person(db, "user")
    pay = {"module_type": "beleg", "config": {"direction": "out", "parties": [
        {"party": firm.object_id, "ref": "https://www.galaxus.ch/…"}]}}
    [why] = voucher_input.step_party_problems(db, [pay])
    assert "ist eine Firma" in why and "Person" in why
    spec = {"name": "Satz PB 5543", "size": "36x70x200", "weight_kg": "0.327", "steps": [pay]}
    assert articles.validate_draft(db, spec) == [why]
    pay["config"]["parties"][0]["party"] = person.object_id
    assert articles.validate_draft(db, spec) == []
    try:
        voucher_input.assert_party(db, firm.object_id)
        raise AssertionError("Eine Firma darf kein Partner sein.")
    except Invalid as e:
        assert e.field == "party"
