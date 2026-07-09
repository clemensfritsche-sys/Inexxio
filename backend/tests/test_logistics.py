"""Logistik/Versand (ADR 005): «Versand wird abgeleitet, nicht bestellt».

DB-lose Tests (SimpleNamespace/Fake-Query, wie die übrigen Suiten): Klassifikation
(Rolle + Adress-Vergleich, ohne Geofence), Paket-Schätzung aus Artikel-Daten, Shippo-Rate-Parsing,
Verdrahtung (Modell/Schema/Endpunkte/Registry) und ein kleiner End-to-End-Durchlauf
der Ableitung (Kunde → extern/outbound, Abholung → inbound, intern → kein Versand).
"""

from decimal import Decimal
from types import SimpleNamespace


class _Q:
    """Minimale Query-Attrappe: filter() ist ein No-op, first()/all() liefern das Ergebnis."""

    def __init__(self, result):
        self._r = result

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._r[0] if isinstance(self._r, list) else self._r

    def all(self):
        return self._r if isinstance(self._r, list) else ([self._r] if self._r else [])


class _DB:
    def __init__(self, by_model: dict):
        self._by_model = by_model

    def query(self, model, *rest):
        return _Q(self._by_model.get(model))


def test_haversine_and_iso2_and_dimensions():
    from app.services import logistics as lg

    # Zürich HB → Bern (~95 km) – Distanz-Helfer rechnet real.
    d = lg.haversine_m(47.3769, 8.5417, 46.9480, 7.4474)
    assert 90_000 < d < 100_000
    assert lg.haversine_m(47.0, 8.0, 47.0, 8.0) == 0.0
    # Länder tolerant → ISO-2 (Carrier-APIs verlangen Codes); Default CH.
    assert lg.iso2("Schweiz") == "CH" and lg.iso2("deutschland") == "DE"
    assert lg.iso2("fr") == "FR" and lg.iso2(None) == "CH" and lg.iso2("Fantasialand") == "CH"
    # Grösse-String (mm) → cm, grösste Kante zuerst; unparsebar → None (Default-Karton).
    assert lg.parse_dimensions_cm("3x40x600") == (60.0, 4.0, 1.0)
    assert lg.parse_dimensions_cm("Ø 12") is None and lg.parse_dimensions_cm(None) is None


def test_location_kind_and_same_place():
    """Ownership per ROLLE (Kunde/Lieferant = extern, Mitarbeiter/Lagerplatz = intern) und
    Adress-Vergleich (normalisiert Strasse+PLZ+Ort+Land) – die Basis der Geofence-losen
    Versand-Ableitung."""
    from app.models import StorageLocation, UserProfile
    from app.services import logistics as lg

    assert lg.location_kind(_DB({UserProfile: SimpleNamespace(role="customer")}), "user", 1) == "external_person"
    assert lg.location_kind(_DB({UserProfile: SimpleNamespace(role="supplier")}), "user", 1) == "external_person"
    assert lg.location_kind(_DB({UserProfile: SimpleNamespace(role="employee")}), "user", 1) == "internal"
    assert lg.location_kind(_DB({StorageLocation: SimpleNamespace()}), "lagerplatz", 2) == "internal"
    assert lg.location_kind(_DB({}), None, None) == "unknown"
    assert lg.location_kind(_DB({UserProfile: None}), "user", 9) == "unknown"

    a = {"street1": "Bahnhofstrasse 1", "zip": "8000", "city": "Zürich", "country": "CH"}
    b = {"street1": "bahnhofstrasse 1", "zip": "8000", "city": "zürich", "country": "ch"}
    c = {"street1": "Andere 2", "zip": "3000", "city": "Bern", "country": "CH"}
    assert lg.same_place(a, b) is True          # normalisiert gleich (Gross/Klein, Leerzeichen)
    assert lg.same_place(a, c) is False         # anderer Ort
    assert lg.same_place(a, None) is False
    assert lg.same_place({"zip": "", "city": ""}, {"zip": "", "city": ""}) is False   # ohne Adresse nicht «gleich»


def test_parcels_from_article_data_with_hazmat():
    """EIN Paket aus den bewegten Instanzen: Gewicht = Σ (Artikelgewicht × Menge), Abmessung
    aus der grössten parsebaren Artikel-Grösse; Gefahrgut-Flag, sobald EIN Artikel markiert ist."""
    from app.models import Article
    from app.services import logistics as lg

    a1 = SimpleNamespace(id=1, weight_kg=Decimal("0.05"), size="3x40x600", is_hazmat=False)
    a2 = SimpleNamespace(id=2, weight_kg=Decimal("1.2"), size=None, is_hazmat=True)
    db = _DB({Article: [a1, a2]})
    instances = [
        SimpleNamespace(article_id=1, quantity=Decimal("10")),   # 0.5 kg
        SimpleNamespace(article_id=2, quantity=Decimal("2")),    # 2.4 kg
    ]
    parcels, hazmat = lg.build_parcels(db, instances)
    assert hazmat is True and len(parcels) == 1
    p = parcels[0]
    assert p["weight_kg"] == 2.9
    assert (p["length_cm"], p["width_cm"], p["height_cm"]) == (60.0, 4.0, 1.0)
    # Ohne Artikel-Daten: Standardkarton + Mindestgewicht (nie ein unversendbares 0-kg-Paket).
    parcels2, hazmat2 = lg.build_parcels(_DB({Article: []}), [SimpleNamespace(article_id=9, quantity=1)])
    assert hazmat2 is False and parcels2[0]["weight_kg"] == lg.DEFAULT_WEIGHT_KG


def test_classify_movement_address_based():
    """E2E-Ableitung OHNE Geofence: (1) Ziel Kunde → extern/outbound; (2) Ware beim
    Lieferanten, Ziel internes Lager → extern/inbound (Abholung); (3) Ziel-Lagerplatz OHNE
    Adresse → innerbetrieblich; (4) freies Ziel (kein Standort) → unknown (keine Box)."""
    from app.models import StorageLocation, UserProfile
    from app.services import logistics as lg

    no_addr = SimpleNamespace(name="L", address_street=None, address_zip=None,
                              address_city=None, address_country=None)
    inst_home = [SimpleNamespace(location_type=None, location_id=None)]

    # (1) Ziel = Kunde (externe Rolle) → extern/outbound.
    step_cust = SimpleNamespace(mode="supplier", target_location_type="user", target_location_id=77)
    out = lg.classify_movement(_DB({UserProfile: SimpleNamespace(role="customer")}),
                               SimpleNamespace(), step_cust, inst_home)
    assert out["transport_class"] == "outside" and out["direction"] == "outbound"

    # (2) Quelle = Lieferant (Ware liegt dort), Ziel = internes Lager → extern/inbound.
    step_in = SimpleNamespace(mode="supplier", target_location_type="lagerplatz", target_location_id=5)
    db2 = _DB({UserProfile: SimpleNamespace(role="supplier"), StorageLocation: no_addr})
    inb = lg.classify_movement(db2, SimpleNamespace(), step_in,
                               [SimpleNamespace(location_type="user", location_id=88)])
    assert inb["transport_class"] == "outside" and inb["direction"] == "inbound"

    # (3) Ziel = Lagerplatz OHNE Adresse, Quelle im Haus → innerbetrieblich (kein Versand).
    internal = lg.classify_movement(_DB({StorageLocation: no_addr}), SimpleNamespace(), step_in, inst_home)
    assert internal["transport_class"] == "inside"

    # (4) Freies Ziel (kein Standort hinterlegt) → unknown → keine Versand-Box.
    step_free = SimpleNamespace(mode="supplier", target_location_type=None, target_location_id=None)
    unk = lg.classify_movement(_DB({}), SimpleNamespace(), step_free, inst_home)
    assert unk["transport_class"] == "unknown"


def test_shippo_rate_parsing_and_provider_fallback():
    """Der Shippo-Adapter übersetzt Rate-Objekte tolerant ins neutrale Format (Shippo
    rechnet nativ in cm/kg – keine Umrechnung nötig); ohne SHIPPO_API_KEY ist der
    Provider 'manual' (kein Rate-Shopping, nie kaputt)."""
    from app.services import shipping
    from app.services.shipping.shippo import _parse_rate

    ok = _parse_rate({"object_id": "r1", "provider": "Swiss Post", "amount": "12.50",
                      "currency": "chf", "estimated_days": 2,
                      "servicelevel": {"name": "PostPac Priority"}})
    assert ok == {"rate_id": "r1", "carrier": "Swiss Post", "service": "PostPac Priority",
                  "amount": 12.5, "currency": "CHF", "days": 2, "provider_rate_id": "r1"}
    assert _parse_rate({"object_id": "", "amount": "1"}) is None      # ohne id unbrauchbar
    assert _parse_rate({"object_id": "x", "amount": "kaputt"}) is None  # ohne Preis unbrauchbar

    assert shipping.provider_name() == "manual"      # Testumgebung ohne Key
    provider = shipping.get_provider()
    assert provider.supports_rates is False
    assert provider.rates({}, {}, []) == {"provider_shipment_id": None, "rates": [], "messages": []}


def test_shippo_messages_surfaced():
    """Bei leerer Tarifliste ist Shippos ``messages``-Array die einzige Erklärung
    (z. B. »Herkunftsland nicht unterstützt«, wenn in der Testumgebung nur ein
    US-Carrier verbunden ist). Der Adapter reicht sie lesbar & dedupliziert durch."""
    from app.services.shipping.shippo import _messages

    raw = [
        {"source": "USPS", "code": "origin", "text": "The origin country CH is not supported."},
        {"source": "USPS", "code": "origin", "text": "The origin country CH is not supported."},  # Dublette
        {"text": "Please connect a carrier account."},
        "roher String",
    ]
    assert _messages(raw) == [
        "USPS: The origin country CH is not supported.",
        "Please connect a carrier account.",
        "roher String",
    ]
    assert _messages(None) == [] and _messages([]) == []


def test_quote_surfaces_provider_messages():
    """``logistics.quote`` verschluckt eine leere Tarifliste NICHT: der Anbieter-Hinweis
    (oder ein Herkunfts-Hinweis) landet in der Fehlermeldung – geprüft an der Quelle."""
    import inspect as _inspect

    from app.services import logistics

    src = _inspect.getsource(logistics.quote)
    assert 'result.get("messages")' in src          # Hinweise werden gelesen
    assert "Anbieter-Hinweis" in src or "Carrier-Konto" in src  # und dem Nutzer gezeigt


def test_shipping_wiring_end_to_end():
    """Verdrahtung: Shipment-Modell (Fachzeile ohne eigene Nummer), transport_mode am
    Schritt (Whitelist), ShipmentEmbed im Bewegungs-Embed, Endpunkte am Auftrag,
    Gefahrgut am Artikel (Geofence entfernt – adress-basiert)."""
    import inspect as _inspect

    from app.models import Article, ArticleProcessStep, CompanySettings, Shipment
    from app.routers import orders as orders_router
    from app.schemas.article_process_step import (
        ALLOWED_TRANSPORT_MODES, ArticleProcessStepCreate, ArticleProcessStepUpdate,
    )
    from app.schemas.movement import MovementEmbed
    from app.schemas.shipment import ShipmentEmbed
    from app.services import logistics, movement

    cols = Shipment.__table__.columns.keys()
    assert "object_id" not in cols and {"order_id", "step_id", "direction", "status",
                                        "rates", "label_url", "tracking_number"} <= set(cols)
    assert ALLOWED_TRANSPORT_MODES == ("auto", "carrier", "self", "none")
    assert "transport_mode" in ArticleProcessStep.__table__.columns
    assert "transport_mode" in ArticleProcessStepCreate.model_fields
    assert "transport_mode" in ArticleProcessStepUpdate.model_fields
    assert "is_hazmat" in Article.__table__.columns
    for c in ("site_latitude", "site_longitude", "site_radius_m"):
        assert c not in CompanySettings.__table__.columns   # Geofence entfernt (adress-basiert)
    assert "shipment" in MovementEmbed.model_fields
    assert {"transport_class", "direction", "rates", "provider_ready"} <= set(ShipmentEmbed.model_fields)
    paths = {r.path for r in orders_router.router.routes}
    assert "/api/v1/erp/orders/{object_id}/shipment/quote" in paths
    assert "/api/v1/erp/orders/{object_id}/shipment/buy" in paths
    assert "/api/v1/erp/orders/{object_id}/shipment" in paths
    # Der Vollzug (Bewegung quittieren) schliesst den Versand-Beleg + übernimmt Tracking.
    src = _inspect.getsource(movement.record_movement)
    assert "complete_for_movement" in src
    # Ein gekaufter Versand wird nicht doppelt gekauft (idempotent).
    assert 'ship.status == "purchased"' in _inspect.getsource(logistics.buy)


def test_quote_marks_cheapest_default_and_fastest_hint():
    """Best-Offer-Policy: der GÜNSTIGSTE Tarif ist die Default-Auswahl (cheapest=True),
    der schnellste wird als Alternative markiert (fastest=True) – geprüft an der
    Sortier-/Markierungslogik von ``logistics.quote`` (Quelle, ohne Provider-Call)."""
    import inspect as _inspect

    from app.services import logistics

    src = _inspect.getsource(logistics.quote)
    assert 'raw.sort(key=lambda r: r["amount"])' in src         # aufsteigend nach Preis
    assert '"cheapest"' in src and 'i == 0' in src              # billigster = Default
    assert '"fastest"' in src                                    # Schnellster-Hinweis
