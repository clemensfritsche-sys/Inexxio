"""Smoke tests — verify the app can be imported and key modules are wired up."""
import pytest

from app.core.config import get_settings
from app.routers import admin, articles, auth, contact, erp, health


def test_settings_loads():
    s = get_settings()
    assert s.app_name


def test_routers_importable():
    assert hasattr(admin, "router")
    assert hasattr(articles, "router")
    assert hasattr(auth, "router")
    assert hasattr(contact, "router")
    assert hasattr(erp, "router")
    assert hasattr(health, "router")


def test_models_exposed_from_package():
    """Models are re-exported from the package regardless of their file."""
    from app.models import Article, AuditLog, CompanySettings, Notification, UserProfile

    assert UserProfile.__tablename__ == "user_profiles"
    assert Article.__tablename__ == "articles"
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
        ArticleCreate(name="x", unit="m", serialization="batch", size="600x40x3", weight_kg=Decimal("1"))
    with pytest.raises(ValueError):    # Gewicht 0
        ArticleCreate(name="x", unit="m", serialization="batch", size="1x2", weight_kg=Decimal("0"))
    with pytest.raises(ValueError):    # > 3 Nachkommastellen
        ArticleCreate(name="x", unit="m", serialization="batch", size="1x2", weight_kg=Decimal("1.2345"))
    with pytest.raises(ValueError):    # ungültige Einheit
        ArticleCreate(name="x", unit="xx", serialization="unit", size="1x2", weight_kg=Decimal("1"))


def test_object_id_allocator_shared_across_types():
    """Der Nummernkreis ist objekttyp-übergreifend (UserProfile + Article)."""
    from app.services import objects

    assert objects.OBJ_ID_START == 100_000_001
    assert objects.UserProfile.object_id in objects._OBJECT_ID_COLUMNS
    assert objects.Article.object_id in objects._OBJECT_ID_COLUMNS
