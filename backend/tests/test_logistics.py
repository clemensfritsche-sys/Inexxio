"""Logistik/Versand (ADR 005): «Versand wird abgeleitet, nicht bestellt».

DB-lose Tests (SimpleNamespace/Fake-Query, wie die übrigen Suiten): Klassifikation
(Rollen-Regel + Geofence), Paket-Schätzung aus Artikel-Daten, EasyPost-Rate-Parsing,
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

    # Zürich HB → Bern (~95 km) – die Geofence-Basis rechnet real.
    d = lg.haversine_m(47.3769, 8.5417, 46.9480, 7.4474)
    assert 90_000 < d < 100_000
    assert lg.haversine_m(47.0, 8.0, 47.0, 8.0) == 0.0
    # Länder tolerant → ISO-2 (Carrier-APIs verlangen Codes); Default CH.
    assert lg.iso2("Schweiz") == "CH" and lg.iso2("deutschland") == "DE"
    assert lg.iso2("fr") == "FR" and lg.iso2(None) == "CH" and lg.iso2("Fantasialand") == "CH"
    # Grösse-String (mm) → cm, grösste Kante zuerst; unparsebar → None (Default-Karton).
    assert lg.parse_dimensions_cm("3x40x600") == (60.0, 4.0, 1.0)
    assert lg.parse_dimensions_cm("Ø 12") is None and lg.parse_dimensions_cm(None) is None


def test_classification_role_rule_and_geofence():
    """Personen nach ROLLE (Kunde/Lieferant = aussen, Mitarbeiter = innen – funktioniert ohne
    Geofence); Lagerplätze nach GPS gegen den Betriebs-Geofence (ohne Geofence = innen)."""
    from app.models import StorageLocation, UserProfile
    from app.services import logistics as lg

    no_fence = SimpleNamespace(site_latitude=None, site_longitude=None, site_radius_m=None)
    fence = SimpleNamespace(site_latitude=Decimal("47.3769"), site_longitude=Decimal("8.5417"),
                            site_radius_m=300)

    customer = SimpleNamespace(role="customer")
    employee = SimpleNamespace(role="employee")
    assert lg.classify_target(_DB({UserProfile: customer}), no_fence, "user", 1) == "outside"
    assert lg.classify_target(_DB({UserProfile: employee}), no_fence, "user", 1) == "inside"

    near = SimpleNamespace(latitude=Decimal("47.3770"), longitude=Decimal("8.5418"))   # ~13 m
    far = SimpleNamespace(latitude=Decimal("46.9480"), longitude=Decimal("7.4474"))    # Bern
    no_gps = SimpleNamespace(latitude=None, longitude=None)
    assert lg.classify_target(_DB({StorageLocation: near}), fence, "lagerplatz", 2) == "inside"
    assert lg.classify_target(_DB({StorageLocation: far}), fence, "lagerplatz", 2) == "outside"
    # Ohne Geofence bzw. ohne GPS gilt der Firmen-Lagerplatz als auf dem Gelände.
    assert lg.classify_target(_DB({StorageLocation: far}), no_fence, "lagerplatz", 2) == "inside"
    assert lg.classify_target(_DB({StorageLocation: no_gps}), fence, "lagerplatz", 2) == "inside"
    # Unbekanntes/leeres Ziel → unknown (kein Versand-Rauschen).
    assert lg.classify_target(_DB({}), fence, None, None) == "unknown"
    assert lg.classify_target(_DB({UserProfile: None}), fence, "user", 9) == "unknown"


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


def test_small_end_to_end_derivation():
    """Kleiner E2E-Durchlauf der Ableitung (ohne DB/Netz):
    (1) Ziel = Kunde → extern/outbound (Versand); (2) Quelle = Lieferant, Ziel = Firmen-
    Lagerplatz → extern/inbound (Abholung); (3) intern → kein externer Transport."""
    from app.models import CompanySettings, StorageLocation, UserProfile
    from app.services import logistics as lg

    fence = SimpleNamespace(site_latitude=None, site_longitude=None, site_radius_m=None)

    # (1) Versand zum Kunden: Schritt-Ziel = Person (Kunde), Instanzen im Haus (standortlos).
    step_out = SimpleNamespace(mode="supplier", target_location_type="user", target_location_id=77)
    db1 = _DB({UserProfile: SimpleNamespace(role="customer"), CompanySettings: fence})
    inst_home = [SimpleNamespace(location_type=None, location_id=None)]
    out = lg.classify_movement(db1, SimpleNamespace(), step_out, inst_home)
    assert out["transport_class"] == "outside" and out["direction"] == "outbound"

    # (2) Abholung beim Lieferanten: Instanzen liegen bei einer externen Person,
    # Ziel = Firmen-Lagerplatz (innen) → inbound (Rücktransport über dieselbe Engine).
    step_in = SimpleNamespace(mode="supplier", target_location_type="lagerplatz", target_location_id=5)
    db2 = _DB({UserProfile: SimpleNamespace(role="supplier"),
               StorageLocation: SimpleNamespace(latitude=None, longitude=None),
               CompanySettings: fence})
    inst_at_supplier = [SimpleNamespace(location_type="user", location_id=88)]
    inb = lg.classify_movement(db2, SimpleNamespace(), step_in, inst_at_supplier)
    assert inb["transport_class"] == "outside" and inb["direction"] == "inbound"

    # (3) Interner Umlagerungs-Schritt: Ziel = Firmen-Lagerplatz, Quelle im Haus → intern.
    db3 = _DB({StorageLocation: SimpleNamespace(latitude=None, longitude=None), CompanySettings: fence})
    internal = lg.classify_movement(db3, SimpleNamespace(), step_in, inst_home)
    assert internal["transport_class"] == "inside" and internal["direction"] == "outbound"


def test_easypost_rate_parsing_and_provider_fallback():
    """Der EasyPost-Adapter übersetzt Rate-Objekte tolerant ins neutrale Format (inkl.
    cm/kg → inch/oz-Umrechnung); ohne EASYPOST_API_KEY ist der Provider 'manual'
    (kein Rate-Shopping, nie kaputt)."""
    from app.services import shipping
    from app.services.shipping.easypost import _parcel_payload, _parse_rate

    ok = _parse_rate({"id": "rate_1", "carrier": "DHLExpress", "rate": "12.50",
                      "currency": "chf", "delivery_days": 2, "service": "ExpressWorldwide"})
    assert ok == {"rate_id": "rate_1", "carrier": "DHLExpress", "service": "ExpressWorldwide",
                  "amount": 12.5, "currency": "CHF", "days": 2, "provider_rate_id": "rate_1"}
    assert _parse_rate({"id": "", "rate": "1"}) is None          # ohne id unbrauchbar
    assert _parse_rate({"id": "x", "rate": "kaputt"}) is None    # ohne Preis unbrauchbar

    # Einheiten: EasyPost rechnet in inches/oz – 30×20×15 cm / 2.9 kg wird korrekt gewandelt.
    p = _parcel_payload({"weight_kg": 2.9, "length_cm": 30, "width_cm": 20, "height_cm": 15})
    assert p == {"length": 11.8, "width": 7.9, "height": 5.9, "weight": 102.3}
    assert _parcel_payload({})["weight"] >= 1.0                  # nie ein 0-oz-Paket

    assert shipping.provider_name() == "manual"      # Testumgebung ohne Key
    provider = shipping.get_provider()
    assert provider.supports_rates is False
    assert provider.rates({}, {}, []) == {"provider_shipment_id": None, "rates": []}


def test_shipping_wiring_end_to_end():
    """Verdrahtung: Shipment-Modell (Fachzeile ohne eigene Nummer), transport_mode am
    Schritt (Whitelist), ShipmentEmbed im Bewegungs-Embed, Endpunkte am Auftrag,
    Geofence-Spalten am Unternehmen, Gefahrgut am Artikel."""
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
        assert c in CompanySettings.__table__.columns
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
