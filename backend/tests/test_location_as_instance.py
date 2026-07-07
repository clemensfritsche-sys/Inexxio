"""Guards für: Lagerplatz-als-Instanz (F), generische Rückverweise, gelockerte Standort-Pflicht."""
import inspect


def test_article_is_location_and_instance_order_nullable():
    from app.models import Article, Instance
    assert "is_location" in Article.__table__.columns
    # Lagerplatz-Instanz hat keinen Auftrag → order_id muss nullable sein
    assert Instance.__table__.columns["order_id"].nullable is True


def test_location_instances_excluded_from_stock_via_disposition():
    # in_stock_clauses verlangt disposition='in_stock' → disposition='location' fällt
    # automatisch raus (kein Sonder-Join nötig). Das ist der Kern der Vereinheitlichung.
    from app.services import inventory
    src = inspect.getsource(inventory.in_stock_clauses)
    assert 'disposition == "in_stock"' in src

    from app.services.locations import create_location_instance
    csrc = inspect.getsource(create_location_instance)
    assert 'disposition="location"' in csrc
    assert "order_id=None" in csrc          # ein Ort ist kein Erzeugnis
    assert 'quality="passed"' in csrc


def test_object_references_is_generic_by_object_number():
    from app.services import references
    assert hasattr(references, "object_references")
    src = inspect.getsource(references.object_references)
    # Kein Standort-Typ-Filter mehr – rein über die (global eindeutige) Objektnummer
    assert "location_id == object_id" in src
    assert "location_type ==" not in src
    # Der Lagerplatz-Wrapper delegiert auf die generische Funktion
    wrap = inspect.getsource(references.storage_location_references)
    assert "object_references(db, loc.object_id)" in wrap


def test_initial_location_no_longer_forces_company():
    from app.services import serialization
    src = inspect.getsource(serialization._initial_location)
    assert "company" not in src            # kein erzwungener Firmen-Standort mehr
    assert "return (None, None)" in src     # standortlos erlaubt


def test_instance_can_be_a_location_target():
    # Eine (Standort-)Instanz ist ein gültiges Bewegungsziel (Hierarchie/Einlagern).
    from app.schemas.movement import LOCATION_TYPES
    assert "instance" in LOCATION_TYPES
