"""Standort-Verteilung einer Charge (``services/location_split.py``).

Reine Funktionen + nackte ``Instance``-Objekte (kein DB nötig): beweist, dass eine Charge
mengengenau auf mehrere Standorte verteilt werden kann – OHNE Teilung der Instanz / ohne
neue Objektnummer –, exakt nach dem Vorbild der Reservierungs-Map. «Ein Bewegen = ein Task».
"""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Instance
from app.services import location_split as ls


def _inst(qty, lid=100000001, ltype="lagerplatz", locations=None, kind="batch"):
    return Instance(object_id=100000050, quantity=Decimal(str(qty)), location_type=ltype,
                    location_id=lid, locations=locations, kind=kind, article_id=1, order_id=1)


def _dist(inst) -> dict:
    return {d["location_id"]: d["quantity"] for d in ls.distribution(inst)}


def test_scalar_only_reports_whole_quantity_at_one_place():
    i = _inst(1000)
    assert _dist(i) == {100000001: 1000.0}
    assert i.locations is None   # nicht verteilt → keine Map, Skalar ist die Wahrheit


def test_partial_move_keeps_object_number_and_splits_location():
    i = _inst(1000)
    ls.move(i, "lagerplatz", 100000002, 300)          # 300 → Band B
    assert _dist(i) == {100000001: 700.0, 100000002: 300.0}
    assert i.locations is not None                     # jetzt verteilt
    assert i.location_id == 100000001                  # Skalar spiegelt die grösste Teilmenge (700)


def test_second_move_empties_source_and_scalar_follows_largest():
    i = _inst(1000)
    ls.move(i, "lagerplatz", 100000002, 300)           # 700@A, 300@B
    ls.move(i, "lagerplatz", 100000003, 700)           # A leert sich → 700@C, 300@B
    assert _dist(i) == {100000003: 700.0, 100000002: 300.0}
    assert i.location_id == 100000003


def test_collapse_to_single_location_drops_the_map():
    i = _inst(1000)
    ls.move(i, "lagerplatz", 100000002, 400)           # 600@A, 400@B
    ls.move(i, "lagerplatz", 100000002, 600, from_id=100000001)  # alles nach B
    assert i.locations is None
    assert i.location_id == 100000002
    assert _dist(i) == {100000002: 1000.0}


def test_reconcile_trims_distribution_after_quantity_drop():
    i = _inst(1000)
    ls.move(i, "lagerplatz", 100000002, 400)           # 600@A, 400@B
    i.quantity = Decimal("700")                        # 300 verschrottet
    ls.reconcile(i)
    assert sum(_dist(i).values()) == pytest.approx(700.0)


def test_fractional_quantities_are_exact():
    i = _inst("2.5", ltype="lagerplatz")               # 2.5 kg
    ls.move(i, "lagerplatz", 100000002, "1.5")
    assert _dist(i) == {100000001: 1.0, 100000002: 1.5}


def test_order_driven_partial_move_uses_reserved_quantity():
    """Kern des Bewegungsschritts: ein Bestands-Auftrag über 10 Stück reserviert mengengenau
    10 der 1000er-Charge; der Schritt verlagert GENAU diese reservierte Teilmenge – der Rest
    bleibt. So entsteht die Verteilung ausschliesslich auftragsgetrieben (nicht an der Instanz)."""
    from app.services.reservation import reserve, reserved_for

    i = _inst(1000)                       # Charge @ Band-Eingang (100000001)
    reserve(i, order_id=555, qty=10)      # Auftrag 555 will 10 Stück umlagern
    share = reserved_for(i, 555)
    assert share == Decimal("10")
    # der Bewegungsschritt bewegt genau die vom Auftrag beanspruchte Teilmenge
    ls.move(i, "lagerplatz", 100000002, share)
    assert _dist(i) == {100000001: 990.0, 100000002: 10.0}
    assert i.object_id == 100000050       # Objektnummer unverändert – keine neue Instanz


def test_guards_reject_invalid_moves():
    with pytest.raises(HTTPException):
        ls.move(_inst(1000), "lagerplatz", 100000002, 0)          # Menge 0
    with pytest.raises(HTTPException):
        ls.move(_inst(1000), "lagerplatz", 100000001, 300)        # Ziel = einziger Standort
    i = _inst(1000)
    ls.move(i, "lagerplatz", 100000002, 400)
    with pytest.raises(HTTPException):
        ls.move(i, "lagerplatz", 100000003, 700, from_id=100000002)  # mehr als am Quellslice


# ─── Adressen: EINE Darstellung für Person, Unternehmen, Lagerplatz ──────────────

def test_address_module_harmonises_person_and_company():
    """Die Spaltennamen sind historisch verschieden (``address_line1``/``postal_code`` an
    der Person vs. ``street``+``street_nr``/``zip_code`` am Unternehmen) – heraus kommt
    trotzdem **dieselbe** kanonische Form, inkl. ISO-2-Land."""
    from types import SimpleNamespace

    from app.services import address

    user = SimpleNamespace(
        company_name=None, first_name="Anna", last_name="Meier", email="a@m.ch", phone=None,
        address_line1="Wohnweg 2", address_line2=None, postal_code="3000", city="Bern",
        state_region=None, country="Schweiz",
        ship_address_line1="Bahnhofstrasse 1", ship_address_line2=None,
        ship_postal_code="8000", ship_city="Zürich", ship_state_region=None, ship_country=None,
    )
    company = SimpleNamespace(company_name="Inexxio AG", street="Musterstrasse", street_nr="1",
                              zip_code="8000", city="Zürich", country="Schweiz",
                              email=None, phone=None)

    ship = address.of_user(user, "ship")
    assert ship["street1"] == "Bahnhofstrasse 1" and ship["zip"] == "8000"
    assert ship["name"] == "Anna Meier"
    # Land fehlt an der Lieferadresse → Rückfall auf die Wohnadresse, normalisiert.
    assert ship["country"] == "CH"
    # Rückfall auf die Wohnadresse, wo der Block leer ist.
    assert address.of_user(user, "invoice")["street1"] == "Wohnweg 2"

    comp = address.of_company(company)
    assert comp["street1"] == "Musterstrasse 1"          # street + street_nr zusammengezogen
    assert set(comp) == set(ship)                          # IDENTISCHE Schlüssel

    # Verschiedene Strassen → NICHT derselbe Ort; gleiche Anschrift → doch (herkunftsübergreifend).
    assert address.same(ship, comp) is False
    same_addr = address.make(street1="Musterstrasse 1", zip="8000", city="zuerich", country="CH")
    assert address.same(same_addr, comp) is False          # Ort weicht ab (zuerich ≠ zürich)
    assert address.same(address.make(street1="musterstrasse  1", zip="8000",
                                     city="Zürich", country="Schweiz"), comp) is True
    assert address.one_line(comp).startswith("Inexxio AG · Musterstrasse 1 · 8000 Zürich")
    assert address.lines(comp)[:2] == ["Inexxio AG", "Musterstrasse 1"]
    # Ohne Ortsangabe gilt bewusst NICHT «gleich» (sonst wären zwei Leere derselbe Ort).
    assert address.same(address.make(name="X"), address.make(name="Y")) is False


def test_location_chain_walks_container_nesting_to_the_address():
    """Die Standort-Kette beantwortet «wo genau?»: Instanz → Behälter → Lagerplatz →
    Anschrift. Sie ist zyklensicher und endet am geografischen Blatt."""
    from types import SimpleNamespace

    from app.models import Instance, StorageLocation
    from app.services import locations as loc

    # Behälter 100000007 liegt auf Lagerplatz 100000003.
    behaelter = SimpleNamespace(object_id=100000007, location_type="lagerplatz",
                                location_id=100000003, is_active=True)
    platz = SimpleNamespace(name="Halle Nord", address_street="Musterstrasse 1",
                            address_zip="8000", address_city="Zürich", address_country="CH")

    class _Q:
        """Minimale Query-Attrappe: filter() ist ein No-op, first() liefert das Ergebnis."""
        def __init__(self, r): self._r = r
        def filter(self, *a, **k): return self
        def first(self): return self._r

    class _DB2:
        def query(self, model, *rest):
            if model is Instance:
                return _Q(behaelter)
            if model is StorageLocation:
                return _Q(platz)
            return _Q(None)

    chain = loc.location_chain(_DB2(), "instance", 100000007)
    types = [h["location_type"] for h in chain]
    assert types == ["instance", "lagerplatz", "address"]
    assert chain[-1]["location_id"] is None                    # Adresse hat keine Nummer
    assert "Musterstrasse 1" in chain[-1]["label"]
    assert "8000 Zürich" in chain[-1]["label"]

    # Zyklus (Instanz liegt in sich selbst) bricht ab statt endlos zu laufen.
    selbst = SimpleNamespace(object_id=1, location_type="instance", location_id=1, is_active=True)

    class _QC:
        def __init__(self, r): self._r = r
        def filter(self, *a, **k): return self
        def first(self): return self._r

    class _DBCycle:
        def query(self, model, *rest):
            return _QC(selbst if model is Instance else None)

    assert len(loc.location_chain(_DBCycle(), "instance", 1)) == 1


def test_consumed_component_relocates_via_the_single_write_path():
    """Verbauen setzt den Standort auf die Produkt-Instanz – über ``location_split``,
    damit eine zuvor verteilte Charge ihre veraltete Map NICHT behält."""
    import inspect as _inspect

    from app.services import resource

    src = _inspect.getsource(resource._relocate)
    assert "location_split.set_single" in src
    assert 'inst.location_id = product.object_id' not in src   # kein Direktzugriff mehr


def test_location_chain_survives_every_holder_shape():
    """Die Kette muss JEDE Standort-Form aushalten, die in echten Daten vorkommt –
    auch verwaiste Zeiger (Halter gelöscht) und unbekannte Typen aus Altbeständen.
    Keine davon darf werfen; im Zweifel ist die Kette kurz, aber nie kaputt."""
    from types import SimpleNamespace

    from app.models import CompanySettings, Instance, StorageLocation, UserProfile
    from app.services import locations as loc

    platz = SimpleNamespace(name="Halle Nord", address_street="Musterstrasse 1",
                            address_zip="8000", address_city="Zürich", address_country="Schweiz")
    person = SimpleNamespace(company_name=None, first_name="Anna", last_name="Muster",
                             email="a@b.ch", phone=None, city="Bern", postal_code="3000",
                             address_line1="Weg 2", country="CH",
                             display_name="Anna Muster")
    firma = SimpleNamespace(company_name="Inexxio AG", street="Bahnhofstr", street_nr="5",
                            zip_code="8001", city="Zürich", country="Schweiz",
                            email=None, phone=None)

    class _Q:
        def __init__(self, r): self._r = r
        def filter(self, *a, **k): return self
        def first(self): return self._r

    def _db(*, instance=None, storage=None, user=None, company=None):
        class _DB:
            def query(self, model, *rest):
                return _Q({Instance: instance, StorageLocation: storage,
                           UserProfile: user, CompanySettings: company}.get(model))
        return _DB()

    behaelter = SimpleNamespace(object_id=100000007, location_type="lagerplatz",
                                location_id=100000003, is_active=True)

    cases = [
        # (db, start-typ, start-id, erwartete Stationstypen)
        (_db(instance=behaelter, storage=platz), "instance", 100000007,
         ["instance", "lagerplatz", "address"]),
        (_db(storage=platz), "lagerplatz", 100000003, ["lagerplatz", "address"]),
        (_db(), None, None, []),                              # standortlos
        (_db(), "lagerplatz", 100000999, ["lagerplatz"]),     # Halter gelöscht
        (_db(), "instance", 100000998, ["instance"]),         # Instanz-Halter gelöscht
        (_db(user=person), "user", 100000050, ["user", "address"]),
        (_db(company=firma), "company", 100000060, ["company", "address"]),
        (_db(), "wolke", 100000003, ["wolke"]),               # unbekannter Alt-Typ
        (_db(storage=platz), "lagerplatz", None, []),         # Typ ohne Nummer
    ]
    for db, ltype, lid, expected in cases:
        chain = loc.location_chain(db, ltype, lid)
        assert [h["location_type"] for h in chain] == expected, (ltype, lid)


def test_broken_chain_never_takes_down_the_instance_record():
    """Die Kette ist Dekoration, nicht der Datensatz: scheitert ihre Auflösung, bleibt
    die Instanz lesbar (leere Kette) – statt das Detail mit einem 500 zu blockieren."""
    from types import SimpleNamespace

    from app.routers.instances import safe_location_path

    class _ExplodingDB:
        def query(self, *a, **k):
            raise RuntimeError("relation \"storage_locations\" does not exist")

    inst = SimpleNamespace(object_id=100000455, location_type="lagerplatz",
                           location_id=100000003)
    assert safe_location_path(_ExplodingDB(), inst) == []
