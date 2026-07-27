"""Tests für die Testnotizen (in-app Feedback) – reine Funktionen + Schema-Validierung."""
from types import SimpleNamespace

import pytest


def test_module_only_outside_production(monkeypatch):
    """Die Notizfunktion ist ein Werkzeug der Testumgebung – die Produktion kennt sie nicht."""
    from app.services import feedback as svc

    monkeypatch.setattr(svc, "get_settings", lambda: SimpleNamespace(app_env="production"))
    assert svc.is_enabled() is False
    monkeypatch.setattr(svc, "get_settings", lambda: SimpleNamespace(app_env="development"))
    assert svc.is_enabled() is True


def test_every_signed_in_role_may_report():
    """Melden darf JEDE Rolle (auch Kunde/Lieferant) – nur das SEHEN ist eingeschränkt."""
    from app.routers import feedback as router_mod
    from app.services.feedback import STAFF_ROLES, _is_staff

    # Der Router hängt an get_current_user, NICHT an require_employee: sonst könnte aus
    # Kunden-/Lieferantensicht nicht gemeldet werden (ausdrückliche Anforderung).
    source = router_mod.__doc__ or ""
    assert "require_employee" not in open(router_mod.__file__, encoding="utf-8").read()
    assert "Rolle" in source

    assert STAFF_ROLES == ("admin", "employee")
    assert _is_staff(SimpleNamespace(role="admin")) is True
    assert _is_staff(SimpleNamespace(role="employee")) is True
    assert _is_staff(SimpleNamespace(role="customer")) is False
    assert _is_staff(SimpleNamespace(role="supplier")) is False


def test_status_whitelist():
    from app.schemas.feedback import FeedbackUpdate

    assert FeedbackUpdate(status="done").status == "done"
    assert FeedbackUpdate(status="dismissed").status == "dismissed"
    assert FeedbackUpdate(status="open").status == "open"
    with pytest.raises(ValueError):
        FeedbackUpdate(status="wontfix")


def test_context_error_buffer_is_capped():
    """Eine Notiz ist kein Log-Sammler: höchstens 5 Fehler à 300 Zeichen."""
    from app.schemas.feedback import FeedbackContext

    ctx = FeedbackContext(errors=[f"fehler {i}" for i in range(20)] + ["x" * 5000])
    assert len(ctx.errors) == 5
    assert all(len(e) <= 300 for e in ctx.errors)
    assert ctx.errors[-1] == "x" * 300      # der jüngste Fehler bleibt erhalten


def test_note_body_is_bounded():
    from app.schemas.feedback import FeedbackCreate

    with pytest.raises(ValueError):
        FeedbackCreate(body="")
    with pytest.raises(ValueError):
        FeedbackCreate(body="x" * 2001)
    assert FeedbackCreate(body="passt", route="/erp?open=100000123").target_object_id is None


def test_note_is_no_business_object():
    """Kein Nummernkreis, kein Feed, kein Event-Strom: eine Notiz ist ein Meta-Artefakt.

    Bekäme sie eine Objektnummer, wanderte Entwicklungs-Rauschen in die ökonomische
    Wahrheit des Systems (Objektregistry, Rückverweise, Audit)."""
    from app.models import FeedbackNote
    from app.services.objects import _TYPE_MODELS

    assert not hasattr(FeedbackNote, "object_id")
    assert FeedbackNote not in _TYPE_MODELS.values()
