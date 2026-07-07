"""Guards für: Consent-Gate (versionierte Dokument-Bestätigung), generischer Rückverweis,
gelockerte Standort-Pflicht (Re-Apply von A/B/C ohne D)."""
import inspect
from types import SimpleNamespace


# ─── Consent-Gate ─────────────────────────────────────────────────────────────

def test_consent_role_scope_pure():
    from app.services import consent
    assert consent._role_in_scope("supplier", ["all"]) is True
    assert consent._role_in_scope("supplier", ["supplier"]) is True
    assert consent._role_in_scope("customer", ["supplier"]) is False
    assert consent._role_in_scope("employee", []) is False
    assert consent._role_in_scope(None, ["all"]) is True


def test_consent_required_kinds_from_config():
    from app.services import consent
    settings = SimpleNamespace(legal_ack_config={"agb": ["all"], "supplier_terms": ["supplier"]})
    assert set(consent.required_kinds(settings, "customer")) == {"agb"}
    assert set(consent.required_kinds(settings, "supplier")) == {"agb", "supplier_terms"}
    # Ohne Konfiguration blockiert nichts (sicherer Default).
    assert consent.required_kinds(SimpleNamespace(legal_ack_config=None), "admin") == []


def test_pending_document_serialization():
    from app.schemas.consent import PendingDocument
    pd = PendingDocument.model_validate({
        "kind": "agb", "title": "AGB", "object_number": 100000123, "document_date": None,
        "content": {"title": "AGB", "subtitle": None, "sections": [{"heading": "1", "body": "x"}]},
    })
    assert pd.content.title == "AGB"
    assert PendingDocument.model_validate({"kind": "datenschutz", "title": "DS"}).content is None


def test_acknowledgement_model_and_endpoints_wired():
    from app.models import DocumentAcknowledgement
    for col in ("user_id", "kind", "version_object_id", "accepted_at"):
        assert col in DocumentAcknowledgement.__table__.columns
    from app.routers import consent as consent_router
    paths = {r.path for r in consent_router.router.routes}
    assert "/api/v1/consent/pending" in paths
    assert "/api/v1/consent/acknowledge" in paths
    # Consent gilt für ALLE Rollen: die Endpunkte hängen an get_current_user (nicht require_employee).
    src = inspect.getsource(consent_router.list_pending) + inspect.getsource(consent_router.acknowledge)
    assert "get_current_user" in src
    assert "require_employee" not in src


# ─── B: generischer Rückverweis (Re-Apply) ────────────────────────────────────

def test_object_references_generic_no_type_filter():
    from app.services import references
    assert hasattr(references, "object_references")
    src = inspect.getsource(references.object_references)
    assert "location_id == object_id" in src
    assert "location_type ==" not in src
    assert "object_references(db, loc.object_id)" in inspect.getsource(references.storage_location_references)
    from app.routers import object_refs
    assert "/api/v1/erp/objects/{object_id}/references" in {r.path for r in object_refs.router.routes}


# ─── C: Standort-Pflicht entfernt (Re-Apply) ──────────────────────────────────

def test_initial_location_no_company_default():
    from app.services import serialization
    src = inspect.getsource(serialization._initial_location)
    assert "company" not in src
    assert "return (None, None)" in src
