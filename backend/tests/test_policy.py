"""Wer darf was – EINE Stelle (``domain/policy``, Änderungsakte U5)."""

import pathlib
import re
from types import SimpleNamespace

import pytest

from app.domain import policy
from app.domain.errors import Forbidden
from app.routers import erp
from app.schemas.admin import ErpAdminUpdate

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Ein Vergleich der Rolle einer Person – ``p.role`` / ``MessageParty.role`` sind die Rolle einer
#: Nachricht («to», «about»), etwas anderes.
_ROLE_CHECK = re.compile(
    r"\b(?!p\b|MessageParty\b)\w+\.role\s*(?:==|!=)\s*[\"'](?:admin|employee|user)[\"']"
    r"|\b(?!p\b|MessageParty\b)\w+\.role\s+(?:not\s+)?in\s+(?:\w+\.)?STAFF_ROLES")


def test_no_role_is_compared_outside_the_one_place():
    """Bug-Form: eine Rollenprüfung in einem Dienst – eine Regel, die die Tabelle nicht kennt."""
    hits = [f"{p.relative_to(APP)}:{n}" for p in APP.rglob("*.py") if p.name != "policy.py"
            for n, line in enumerate(p.read_text().splitlines(), 1) if _ROLE_CHECK.search(line)]
    assert not hits, f"Rollenprüfung ausserhalb von domain/policy: {hits}"


def _who(role, oid=100000001):
    return SimpleNamespace(role=role, object_id=oid)


def test_the_three_kinds_of_rules():
    admin, staff, other, customer = _who("admin"), _who("employee", 1), _who("employee", 2), _who("user", 1)
    assert policy.may(staff, "person.edit") and not policy.may(customer, "person.edit")
    assert policy.may(admin, "time.contract") and not policy.may(staff, "time.contract")
    assert policy.may(staff, "time.see", owner=1) and not policy.may(other, "time.see", owner=1)
    assert policy.may(admin, "time.see", owner=1)
    assert not policy.may(customer, "time.see", owner=1)          # Kunde: nie, auch nicht «selbst»
    with pytest.raises(Forbidden, match="nur der Admin"):
        policy.require(staff, "time.contract")
    assert policy.inside(None) and policy.inside(staff) and not policy.inside(customer)


def test_every_staff_member_edits_customers_but_only_the_admin_staff_and_roles(make_person):
    """Änderungsakte U4: Kundendaten ändert jedes Personal; Rollen und Mitarbeitende der Admin."""
    staff, admin = make_person("employee"), make_person("admin")
    customer, colleague = make_person("user"), make_person("employee")
    erp._may_edit(staff, customer)
    erp._may_edit(admin, colleague, role=True)
    with pytest.raises(Forbidden):
        erp._may_edit(staff, colleague)
    with pytest.raises(Forbidden):
        erp._may_edit(staff, customer, role=True)
    assert "role" in ErpAdminUpdate(role="employee").model_fields_set
    assert erp._record(customer, viewer=staff).may_edit and not erp._record(colleague, viewer=staff).may_edit


def test_the_doors_of_the_routes_read_the_rules():
    """Bug-Form: ``require_role("admin")`` prüfte an der Tabelle vorbei – eigener Satz, eigene Liste."""
    from typing import get_args

    from app.core import auth
    from app.schemas.admin import Role

    assert get_args(Role) == policy.ROLES
    staff, customer, admin = _who("employee"), _who("user"), _who("admin")
    assert auth.require_employee(staff) is staff and auth.require_admin(admin) is admin
    with pytest.raises(Forbidden, match=policy.RULES["erp"].why):
        auth.require_employee(customer)
    with pytest.raises(Forbidden, match=policy.RULES["admin"].why):
        auth.require_admin(staff)
