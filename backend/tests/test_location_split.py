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


def _inst(qty, lid=100000001, ltype="instance", locations=None, kind="batch"):
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


# ─── Ort («place»): kein Objekt, darum nicht verteilbar ──────────────────────────

def test_place_holds_the_whole_quantity_and_is_not_splittable():
    """Ein **Ort** (Adresse/GPS ohne Objektnummer) hält per Definition die GANZE Menge.

    Das ist keine willkürliche Einschränkung, sondern die ehrliche Abbildung: die
    Verteilungs-Map ist nach Objektnummer geschlüsselt, und eine Adresse kann zwei Plätze
    am selben Standort gar nicht unterscheiden («Band A» und «Wareneingang» haben dieselbe
    Anschrift). Wer innerhalb eines Standorts verteilen will, nutzt Behälter-Instanzen."""
    inst = _inst(1000, lid=None, ltype="place")
    inst.place = {"name": "Aussenlager", "zip": "8000", "city": "Zürich"}

    # Die Verteilung meldet EINEN Eintrag über die ganze Menge – ohne Objektnummer.
    dist = ls.distribution(inst)
    assert dist == [{"location_type": "place", "location_id": None, "quantity": 1000.0}]

    # Eine Teilmenge auf einen Ort zu verlagern wird klar abgewiesen (statt still zu scheitern).
    with pytest.raises(HTTPException) as e:
        ls.move(inst, "place", 0, 10)
    assert "ganze Menge" in e.value.detail

    # Auf eine Behälter-Instanz ist dieselbe Teilmenge sehr wohl verlagerbar.
    inst2 = _inst(1000, lid=100000001, ltype="instance")
    ls.move(inst2, "instance", 100000002, 10)
    assert _dist(inst2) == {100000001: 990.0, 100000002: 10.0}


def test_place_identity_is_its_address():
    """Ein Ort hat keine Nummer – seine Identität ist die (normalisierte) Adresse.
    Darauf beruht der Ist↔Soll-Abgleich (``is_at``) und damit die No-op-Erkennung."""
    inst = _inst(5, lid=None, ltype="place")
    inst.place = {"name": "Aussenlager", "zip": "8000", "city": "Zürich"}

    assert ls.is_at(inst, "place", None, {"name": "AUSSENLAGER", "zip": "8000", "city": "zürich"})
    assert not ls.is_at(inst, "place", None, {"zip": "3000", "city": "Bern"})
    assert not ls.is_at(inst, "instance", 100000001)

    # Wechsel auf einen anderen Ort führt eine verteilte Charge wieder zusammen.
    inst.locations = {"100000001": {"t": "instance", "q": "2"},
                      "100000002": {"t": "instance", "q": "3"}}
    ls.set_target(inst, "place", None, {"zip": "3000", "city": "Bern"})
    assert inst.locations is None and inst.location_id is None
    assert inst.place["city"] == "Bern" and inst.location_type == "place"
