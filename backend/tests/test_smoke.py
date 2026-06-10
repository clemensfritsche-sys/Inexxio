"""Smoke tests — verify the app can be imported and key modules are present."""
from app.core.config import get_settings
from app.routers import admin, auth, contact, erp, health


def test_settings_loads():
    s = get_settings()
    assert s.app_name


def test_routers_importable():
    assert hasattr(admin, "router")
    assert hasattr(auth, "router")
    assert hasattr(contact, "router")
    assert hasattr(erp, "router")
    assert hasattr(health, "router")
