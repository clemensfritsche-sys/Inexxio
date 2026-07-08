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
    return Instance(quantity=Decimal(str(qty)), location_type=ltype, location_id=lid,
                    locations=locations, kind=kind, article_id=1, order_id=1)


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


def test_guards_reject_invalid_moves():
    with pytest.raises(HTTPException):
        ls.move(_inst(1000), "lagerplatz", 100000002, 0)          # Menge 0
    with pytest.raises(HTTPException):
        ls.move(_inst(1000), "lagerplatz", 100000001, 300)        # Ziel = einziger Standort
    i = _inst(1000)
    ls.move(i, "lagerplatz", 100000002, 400)
    with pytest.raises(HTTPException):
        ls.move(i, "lagerplatz", 100000003, 700, from_id=100000002)  # mehr als am Quellslice
