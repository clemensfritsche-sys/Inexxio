"""Smoke tests — verify the app can be imported and key modules are wired up."""
import pytest

from app.core.config import get_settings
from app.routers import (
    admin, article_process, articles, auth, contact, erp, health,
    orders, storage_locations,
)


def test_settings_loads():
    s = get_settings()
    assert s.app_name


def test_routers_importable():
    assert hasattr(admin, "router")
    assert hasattr(articles, "router")
    assert hasattr(article_process, "router")
    assert hasattr(orders, "router")
    assert hasattr(storage_locations, "router")
    assert hasattr(auth, "router")
    assert hasattr(contact, "router")
    assert hasattr(erp, "router")
    assert hasattr(health, "router")


def test_models_exposed_from_package():
    """Models are re-exported from the package regardless of their file."""
    from app.models import (
        Article, ArticleProcessStep, AuditLog, CompanySettings, Notification,
        Order, PurchaseOrder, StorageLocation, UserProfile,
    )

    assert UserProfile.__tablename__ == "user_profiles"
    assert Article.__tablename__ == "articles"
    assert ArticleProcessStep.__tablename__ == "article_process_steps"
    assert Order.__tablename__ == "orders"
    assert PurchaseOrder.__tablename__ == "purchase_orders"
    assert StorageLocation.__tablename__ == "storage_locations"
    assert AuditLog.__tablename__ == "audit_log"
    assert Notification.__tablename__ == "notifications"
    assert CompanySettings.__tablename__ == "company_settings"


def test_auth_helpers_decoupled():
    """Auth verification, provisioning and sync are separate, callable units."""
    from app.core import auth

    assert callable(auth._verify_firebase_token)
    assert callable(auth._resolve_user)
    assert callable(auth._sync_user_profile)
    assert callable(auth.get_current_user)


def test_self_update_schema_excludes_employment_fields():
    """Regression guard for the mass-assignment fix."""
    from app.schemas.admin import UserProfileUpdate

    fields = UserProfileUpdate.model_fields.keys()
    for forbidden in ("role", "department", "job_title", "employment_start_date", "weekly_hours"):
        assert forbidden not in fields


def test_article_create_validation():
    """Stammdaten-Pflichtfelder werden validiert (Grösse aufsteigend, Gewicht > 0)."""
    from decimal import Decimal

    from app.schemas.article import ArticleCreate

    ok = ArticleCreate(
        name="  Welle  ", unit="Stk", serialization="unit",
        size="3 X 40 x 600", weight_kg=Decimal("2.5"),
    )
    assert ok.name == "Welle"          # getrimmt
    assert ok.size == "3x40x600"       # normalisiert

    with pytest.raises(ValueError):    # Grösse absteigend
        ArticleCreate(name="x", unit="mm", serialization="batch", size="600x40x3", weight_kg=Decimal("1"))
    with pytest.raises(ValueError):    # Gewicht 0
        ArticleCreate(name="x", unit="mm", serialization="batch", size="1x2", weight_kg=Decimal("0"))
    with pytest.raises(ValueError):    # > 3 Nachkommastellen
        ArticleCreate(name="x", unit="mm", serialization="batch", size="1x2", weight_kg=Decimal("1.2345"))
    with pytest.raises(ValueError):    # ungültige Einheit
        ArticleCreate(name="x", unit="xx", serialization="unit", size="1x2", weight_kg=Decimal("1"))


def test_object_id_allocator_shared_across_types():
    """Der Nummernkreis ist objekttyp-übergreifend (UserProfile + Article)."""
    from app.services import objects

    assert objects.OBJ_ID_START == 100_000_001
    assert objects.UserProfile.object_id in objects._OBJECT_ID_COLUMNS
    assert objects.Article.object_id in objects._OBJECT_ID_COLUMNS
    assert objects.Order.object_id in objects._OBJECT_ID_COLUMNS
    assert objects.StorageLocation.object_id in objects._OBJECT_ID_COLUMNS
    # Bestellungen laufen unter der Auftragsnummer → KEINE eigene Objektnummer
    assert not hasattr(objects, "PurchaseOrder")


def test_landed_unit_cost_calculation():
    """Einstandspreis & Stückpreis netto = Bestellsumme ÷ Menge."""
    from decimal import Decimal

    from app.models import PurchaseOrder
    from app.services.purchase import compute_landed_unit_cost, compute_unit_price

    po = PurchaseOrder(order_id=1, article_id=1, quantity=5, order_total=Decimal("75.00"))
    # 75 / 5 = 15
    assert compute_landed_unit_cost(po) == Decimal("15.0000")
    assert compute_unit_price(po) == Decimal("15.00")

    po.order_total = None  # ohne Bestellsumme kein Preis
    assert compute_landed_unit_cost(po) is None
    assert compute_unit_price(po) is None


def test_supplier_fields_mandatory_always_included():
    """Pflicht-Stammdaten sind für den Lieferanten immer sichtbar."""
    from app.services.article_fields import MANDATORY_FIELD_KEYS, normalize_shared_fields

    assert set(normalize_shared_fields(None)) >= set(MANDATORY_FIELD_KEYS)
    assert set(normalize_shared_fields([])) >= set(MANDATORY_FIELD_KEYS)
    out = normalize_shared_fields(["unknown_key", "name"])
    assert "unknown_key" not in out                      # unbekannt verworfen
    assert set(MANDATORY_FIELD_KEYS) <= set(out)         # Pflicht erzwungen


def test_purchase_responsibility_separation():
    """Lieferant offeriert/bestätigt, Besteller gibt frei/nimmt Ware an – getrennt."""
    from app.models import PurchaseOrder, UserProfile
    from app.services.purchase import _transition_allowed

    staff = UserProfile(role="employee", id=1)
    supplier = UserProfile(role="supplier", id=2)
    po = PurchaseOrder(order_id=1, article_id=1, quantity=1, mode="supplier", supplier_id=2)

    assert _transition_allowed(po, "quoted", supplier) is True
    assert _transition_allowed(po, "quoted", staff) is False
    assert _transition_allowed(po, "approved", staff) is True
    assert _transition_allowed(po, "approved", supplier) is False
    assert _transition_allowed(po, "received", staff) is True
    assert _transition_allowed(po, "received", supplier) is False

    po.mode = "webshop"
    po.supplier_id = None
    assert _transition_allowed(po, "quoted", staff) is True
    assert _transition_allowed(po, "approved", staff) is True


def test_purchase_order_transitions_map():
    """Statusübergänge sind eng definiert (kein Sprung über Stufen)."""
    from app.services.purchase import _FROM

    assert _FROM["approved"] == {"quoted"}
    assert _FROM["received"] == {"confirmed"}
    assert "received" not in _FROM["approved"]


def test_purchase_order_update_schema_validates_status():
    """Ungültiger Zielstatus wird abgelehnt; gültiger akzeptiert."""
    from decimal import Decimal

    import pytest

    from app.schemas.purchase_order import PurchaseOrderUpdate

    assert PurchaseOrderUpdate(status="approved").status == "approved"
    with pytest.raises(ValueError):
        PurchaseOrderUpdate(status="erledigt")
    with pytest.raises(ValueError):
        PurchaseOrderUpdate(order_total=Decimal("-1"))


def test_process_step_requires_consistent_mode():
    """Lieferant-Modus braucht supplier_id, Webshop-Modus braucht URL."""
    import pytest

    from app.schemas.article_process_step import ArticleProcessStepCreate

    ok = ArticleProcessStepCreate(mode="supplier", supplier_id=42)
    assert ok.supplier_id == 42
    ok2 = ArticleProcessStepCreate(mode="webshop", webshop_url="https://shop.example/x")
    assert ok2.webshop_url == "https://shop.example/x"
    with pytest.raises(ValueError):
        ArticleProcessStepCreate(mode="supplier")
    with pytest.raises(ValueError):
        ArticleProcessStepCreate(mode="webshop")


def test_order_desired_date_must_be_future():
    """Wunsch-Liefertermin in der Vergangenheit wird abgelehnt, heute/Zukunft ok."""
    from datetime import date, timedelta

    import pytest

    from app.schemas.order import OrderCreate

    assert OrderCreate(desired_delivery_date=date.today()).desired_delivery_date == date.today()
    future = date.today() + timedelta(days=5)
    assert OrderCreate(desired_delivery_date=future).desired_delivery_date == future
    with pytest.raises(ValueError):
        OrderCreate(desired_delivery_date=date.today() - timedelta(days=1))


def test_lifecycle_locks_after_release():
    """Nach Freigabe sind nur noch Status/is_active änderbar."""
    import pytest

    from app.services.lifecycle import ensure_mutable

    # Entwurf: alles erlaubt
    ensure_mutable("draft", {"name": "x", "status": "released"}, "Artikel")
    # Freigegeben: nur Status/is_active
    ensure_mutable("released", {"status": "inactive"}, "Artikel")
    ensure_mutable("released", {"is_active": False}, "Artikel")
    with pytest.raises(Exception):
        ensure_mutable("released", {"name": "neu"}, "Artikel")
    with pytest.raises(Exception):
        ensure_mutable("completed", {"quantity": 5}, "Auftrag")


def test_order_status_allows_completed():
    """Auftrag kann automatisch abgeschlossen werden (Status 'completed')."""
    from app.schemas.order import ALLOWED_STATUS, OrderUpdate

    assert "completed" in ALLOWED_STATUS
    assert OrderUpdate(status="completed").status == "completed"


def test_purchase_runs_under_order_without_own_number():
    """Bestellung hat keine eigene Objektnummer; sie läuft unter dem Auftrag."""
    from app.models import PurchaseOrder
    from app.schemas.order import OrderResponse
    from app.schemas.purchase_order import PurchaseEmbed

    assert not hasattr(PurchaseOrder, "object_id")
    assert "object_id" not in PurchaseEmbed.model_fields
    # Auftrag bettet den Beschaffungsschritt ein
    assert "purchase" in OrderResponse.model_fields
