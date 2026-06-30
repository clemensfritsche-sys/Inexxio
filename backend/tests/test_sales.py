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

    # Zwei Abo-Typen: Nutzungsabo (usage) | Produktabo (product). Steuerklasse entfällt.
    ok = ArticlePriceCreate(kind="subscription", interval="month",
                            sub_type="product", amount_chf=Decimal("49.00"))
    assert ok.interval == "month" and ok.sub_type == "product"

    with pytest.raises(ValueError):   # ungültige Art
        ArticlePriceCreate(kind="rental", amount_chf=Decimal("1"))
    with pytest.raises(ValueError):   # ungültiger Abo-Typ
        ArticlePriceCreate(kind="subscription", sub_type="lifetime", amount_chf=Decimal("1"))
    with pytest.raises(ValueError):   # Betrag <= 0
        ArticlePriceCreate(kind="one_time", amount_chf=Decimal("0"))


def test_visibility_validation():
    from app.schemas.sales import ArticleSalesUpdate

    assert ArticleSalesUpdate(sales_visibility="private").sales_visibility == "private"
    assert ArticleSalesUpdate(sales_visibility="public").sales_visibility == "public"
    with pytest.raises(ValueError):   # 'unlisted' (Verborgen) ist entfernt
        ArticleSalesUpdate(sales_visibility="unlisted")
    with pytest.raises(ValueError):
        ArticleSalesUpdate(sales_visibility="secret")


def test_cart_checkout_schema():
    from app.schemas.shop import ShopCheckout, ShopCheckoutItem

    ok = ShopCheckout(items=[ShopCheckoutItem(article_object_id=100000001, price_id=5, quantity=2)])
    assert ok.items[0].quantity == 2
    with pytest.raises(ValueError):   # leerer Warenkorb
        ShopCheckout(items=[])
    with pytest.raises(ValueError):   # Menge <= 0
        ShopCheckoutItem(article_object_id=1, quantity=0)


def test_deferred_intent_helpers_exist():
    """Defer-Modell: der Warenkorb wird als CheckoutIntent gehalten; die Aufträge entstehen
    erst bei der Zahlung (fulfill_intent) bzw. werden bei Abbruch aufgelöst (cancel_intent)."""
    from app.services import sales as sales_svc
    from app.models import CheckoutIntent

    for f in ("checkout", "fulfill_intent", "cancel_intent", "price_options"):
        assert hasattr(sales_svc, f)
    assert CheckoutIntent.__tablename__ == "checkout_intents"


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


def test_make_to_order_is_demand_supply_not_override():
    """Make-to-Order ist KEIN Sonderfall mehr: kein subject_source-Override, kein verketteter
    Produktionsauftrag. Ein Verkauf «auf Bestellung» ist ein normaler Verkaufsauftrag (Subjekt
    stock/FIFO); die Fehlmenge deckt ein Nachschub-Unter-Auftrag (services/supply)."""
    import inspect as _inspect
    from app.models import Order
    from app.services import sales, subject, supply

    # subject_kind leitet rein aus der Auftragsgestalt ab – keine Quellen-Übersteuerung mehr.
    assert "subject_source" not in _inspect.getsource(subject.subject_kind)
    assert "subject_source" not in Order.__table__.columns.keys()
    assert "fulfilled_by_order_id" not in Order.__table__.columns.keys()
    # Der Shop dockt über DENSELBEN Mechanismus an wie der ERP-Knopf: ensure_supply.
    assert "ensure_supply" in _inspect.getsource(sales.fulfill_intent)
    assert not hasattr(sales, "_create_production_order")
    assert hasattr(supply, "ensure_supply")


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
