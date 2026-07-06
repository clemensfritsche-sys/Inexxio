"""Bruchmengen-Engine (#8): Mengen als Decimal für kg · m² · m³ · l (nicht nur ganze Stück).

Reine Funktionen + nackte Model-Objekte (kein DB nötig) – beweist, dass Reservierung,
FIFO-Allokation und Stichproben mit Nachkommastellen exakt rechnen und die Reservierungs-
Map JSON-sicher (String) bleibt.
"""
import json
from decimal import Decimal


def test_to_qty_normalizes_all_inputs():
    from app.services.quantity import to_qty

    assert to_qty(None) == Decimal("0")
    assert to_qty(5) == Decimal("5")
    assert to_qty("2.5") == Decimal("2.500")
    assert to_qty(2.5) == Decimal("2.5")
    # float-Ungenauigkeit wird über str vermieden + auf 3 NK gerundet (kein 0.1+0.2-Drift)
    assert to_qty(0.1) + to_qty(0.2) == Decimal("0.300")
    assert to_qty("2.6667") == Decimal("2.667")   # ROUND_HALF_UP auf 3 NK


def test_is_whole_distinguishes_unit_from_batch():
    from app.services.quantity import is_whole

    assert is_whole(5) is True
    assert is_whole(Decimal("5.000")) is True
    assert is_whole("2.5") is False
    assert is_whole(0.75) is False


def test_allocate_handles_fractional_need_and_candidates():
    from app.services.inventory import allocate

    # 2.5 kg über zwei Chargen (1.0 + 4.0) → 1.0 aus der ersten, 1.5 aus der zweiten
    out = allocate(Decimal("2.5"), [Decimal("1.0"), Decimal("4.0")])
    assert out == [Decimal("1.000"), Decimal("1.500")]
    assert sum(out) == Decimal("2.500")
    # Unterdeckung: nur so viel wie vorhanden
    assert allocate(Decimal("10"), [Decimal("2.5")]) == [Decimal("2.500")]


def test_reservation_roundtrip_is_decimal_and_json_safe():
    from app.models import Instance
    from app.services.reservation import free_qty, reserve, reserved_for, release, consume

    inst = Instance(quantity=Decimal("10"), reservations=None, reserved_quantity=Decimal("0"))

    reserve(inst, 42, Decimal("2.5"))
    assert reserved_for(inst, 42) == Decimal("2.500")
    assert free_qty(inst) == Decimal("7.500")
    # Map-Werte sind Strings → JSONB-serialisierbar (kein Decimal in JSON)
    assert isinstance(inst.reservations["42"], str)
    json.dumps(inst.reservations)   # darf nicht werfen
    assert inst.reserved_for_order_id == 42

    # zweiter Auftrag: additive, mengengenaue Reservierung
    reserve(inst, 7, Decimal("0.25"))
    assert inst.reserved_quantity == Decimal("2.750")
    assert free_qty(inst) == Decimal("7.250")
    assert inst.reserved_for_order_id is None   # mehr als ein Auftrag → kein Einzel-Zeiger

    # Verbrauch mindert Menge UND Reservierung mengengenau
    consume(inst, 42, Decimal("1.5"))
    assert inst.quantity == Decimal("8.500")
    assert reserved_for(inst, 42) == Decimal("1.000")

    # Freigabe der Restreservierung
    assert release(inst, 42) == Decimal("1.000")
    assert reserved_for(inst, 42) == Decimal("0")


def test_reduce_quantity_trims_overhang_reservations():
    from app.models import Instance
    from app.services.reservation import reduce_quantity, reserved_for, reserve

    inst = Instance(quantity=Decimal("5"), reservations=None, reserved_quantity=Decimal("0"))
    reserve(inst, 1, Decimal("4"))
    # Teil-Verschrottung von 2.5 → Menge 2.5, die 4er-Reservierung wird auf 2.5 getrimmt
    cut = reduce_quantity(inst, Decimal("2.5"))
    assert cut == Decimal("2.500")
    assert inst.quantity == Decimal("2.500")
    assert reserved_for(inst, 1) == Decimal("2.500")


def test_required_sample_supports_fractional_batches():
    from app.services.process import required_sample

    # Charge 2.5 kg: 100 % → 3 Proben (ceil), 40 % → 1
    assert required_sample(Decimal("2.5"), 100) == 3
    assert required_sample(Decimal("2.5"), 40) == 1
    # Einzelteil (ganze Menge): unverändertes Verhalten
    assert required_sample(5, 100) == 5
    assert required_sample(5, 50) == 3          # ceil(2.5)
    assert required_sample(0, 100) == 0
