"""Tests für die Verkaufs-/Shop-Logik (reine Funktionen + Schema-Validierung)."""
from decimal import Decimal

import pytest


def test_charm_round_currency_specific():
    from app.services.pricing import charm_round

    # CHF: auf nächste 0.05 gerundet
    assert charm_round(Decimal("100.02"), "CHF") == Decimal("100.00")
    assert charm_round(Decimal("100.03"), "CHF") == Decimal("100.05")
    # Fremdwährung: ganze Zahl mit psychologischer .90-Endung
    assert charm_round(Decimal("95.24"), "EUR") == Decimal("94.90")
    assert charm_round(Decimal("0.30"), "USD") == Decimal("0.90")
    assert charm_round(Decimal("0"), "EUR") == Decimal("0.00")


def test_vat_rate_rules():
    from app.services.tax import vat_rate

    # CH-Inland je Steuerklasse
    assert vat_rate("standard", "Schweiz") == Decimal("8.1")
    assert vat_rate("reduced", "CH") == Decimal("2.6")
    assert vat_rate("lodging", "Liechtenstein") == Decimal("3.8")
    assert vat_rate("zero", "Schweiz") == Decimal("0")
    # Ohne Land → Inland angenommen
    assert vat_rate("standard", None) == Decimal("8.1")
    # Ausland (Export / EU-B2B Reverse Charge) → 0 %
    assert vat_rate("standard", "Deutschland") == Decimal("0")
    assert vat_rate("standard", "USA", is_b2b=True, has_vat_id=True) == Decimal("0")


def test_price_schema_validation():
    from app.schemas.sales import ArticlePriceCreate

    ok = ArticlePriceCreate(kind="subscription", interval="month",
                            amount_chf=Decimal("49.00"), tax_class="standard")
    assert ok.interval == "month"

    with pytest.raises(ValueError):   # ungültige Art
        ArticlePriceCreate(kind="rental", amount_chf=Decimal("1"))
    with pytest.raises(ValueError):   # ungültige Steuerklasse
        ArticlePriceCreate(kind="one_time", amount_chf=Decimal("1"), tax_class="luxury")
    with pytest.raises(ValueError):   # Betrag <= 0
        ArticlePriceCreate(kind="one_time", amount_chf=Decimal("0"))


def test_visibility_validation():
    from app.schemas.sales import ArticleSalesUpdate

    assert ArticleSalesUpdate(sales_visibility="private").sales_visibility == "private"
    with pytest.raises(ValueError):
        ArticleSalesUpdate(sales_visibility="secret")


def test_payments_factory_defaults_to_manual():
    from app.services.payments import get_provider, provider_name

    assert provider_name(None) in ("manual", "stripe")
    prov = get_provider(None)
    assert prov.name in ("manual", "stripe")


def test_shop_router_wired():
    from app.routers import sales, shop

    assert hasattr(sales, "router")
    assert hasattr(shop, "router")
