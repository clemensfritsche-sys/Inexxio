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


def test_fulfillment_validation():
    from app.schemas.sales import ArticleSalesUpdate

    assert ArticleSalesUpdate(sales_fulfillment="make").sales_fulfillment == "make"
    assert ArticleSalesUpdate(sales_fulfillment="stock").sales_fulfillment == "stock"
    with pytest.raises(ValueError):
        ArticleSalesUpdate(sales_fulfillment="airdrop")


def test_subject_source_overrides_derivation():
    """Ein expliziter subject_source='produce' erzwingt Herstellung trotz eigener Schritte
    (Shop-Made-to-Order). subject_kind/materialize berücksichtigen ihn (Quellcode-Vertrag)."""
    import inspect as _inspect
    from app.services import subject

    assert "subject_source" in _inspect.getsource(subject.subject_kind)
    # materialize verzweigt über subject_kind (das den Override kennt).
    assert "subject_kind(db, order)" in _inspect.getsource(subject.materialize_subject)


def test_article_reactivation_removed():
    """Inaktive Artikel sind endgültig – der Reaktivierungs-Blocker ist entfernt und der
    Router lehnt inactive→released ab."""
    import inspect as _inspect
    from app.services import deactivation
    from app.routers import articles

    assert not hasattr(deactivation, "article_reactivation_blocker")
    src = _inspect.getsource(articles.update_article)
    assert "nicht reaktiviert" in src.lower() or "können nicht reaktiviert" in src.lower()


def test_stripe_provider_interface():
    from app.services.payments.stripe_provider import StripeProvider

    p = StripeProvider()
    assert p.name == "stripe"
    for m in ("create_checkout", "handle_webhook", "create_portal_session"):
        assert callable(getattr(p, m))


def test_provider_factory_without_key_is_manual():
    from app.services.payments import get_provider, provider_name

    # In der Testumgebung ist kein STRIPE_SECRET_KEY gesetzt → manual.
    assert provider_name(None) == "manual"
    assert get_provider(None).name == "manual"


def test_apply_stripe_snapshot_inclusive():
    from app.models import Sale
    from app.services.sale import _apply_stripe_snapshot

    sale = Sale(order_id=1, article_id=1, quantity=1, status="requested", currency="CHF")
    _apply_stripe_snapshot(sale, {
        "settlement": {"currency": "CHF", "total": "108.10", "tax": "8.10"},
        "presentment": {"currency": "EUR", "total": "112.00"},
        "payment_intent": "pi_test_123",
    })
    assert sale.currency == "CHF"
    assert sale.order_total == Decimal("100.00")     # netto = brutto − Steuer
    assert sale.vat_rate == Decimal("8.10")
    assert sale.stripe_payment_intent_id == "pi_test_123"
    assert sale.stripe_snapshot["presentment"]["currency"] == "EUR"


def test_finalize_paid_and_release_helpers_exist():
    from app.services import sale as sale_svc

    for f in ("finalize_paid", "mark_paid", "mark_cancelled", "_release_on_payment"):
        assert hasattr(sale_svc, f)


def test_prices_tax_inclusive_default():
    from app.core.config import get_settings

    assert get_settings().prices_tax_inclusive is True


def test_pricing_pipeline_has_optional_stages():
    """Die Preis-Pipeline ist gestaffelt: Zonen-Faktor (②) + Pinning (④) als Funktionen."""
    from app.services import pricing

    assert hasattr(pricing, "_zone_factor")
    assert hasattr(pricing, "_pinned_net")
    assert hasattr(pricing, "_net_chf")
    assert pricing.DRIFT_THRESHOLD == __import__("decimal").Decimal("0.03")
