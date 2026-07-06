"""Mengen-Arithmetik mit Dezimalstellen (kg · m² · m³ · l · Stk).

**Eine** Stelle für alle Bestandsmengen. Mengen sind ``Decimal`` mit bis zu drei
Nachkommastellen (DB: ``NUMERIC(14,3)``) – exakt, kein ``float`` in der Fachlogik.
Damit funktioniert die **Abrechnung/Reservierung/FIFO für JEDE Einheit**, auch
Bruchmengen (0.75 m², 2.5 kg), nicht nur ganze Stück.

Warum hier zentral: die Reservierungs-Map (``instances.reservations``) speichert
Mengen als JSON – ``Decimal`` ist nicht JSON-serialisierbar, darum werden die
Werte als **String** abgelegt und über ``to_qty`` exakt zurückgelesen. So bleibt
die Menge über den ganzen Weg (DB ↔ JSON ↔ Python) verlustfrei.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

# Drei Nachkommastellen – deckt Gramm/Milliliter/mm² etc. ab (Numeric(14,3)).
QTY_EXP = Decimal("0.001")
ZERO = Decimal("0")
ONE = Decimal("1")


def to_qty(v) -> Decimal:
    """Beliebigen Mengenwert (int/float/str/Decimal/None) → ``Decimal`` mit max. drei
    Nachkommastellen. ``None`` → 0. ``float`` wird über ``str`` geführt (keine
    Binär-Ungenauigkeit wie ``Decimal(0.1)``)."""
    if v is None:
        return ZERO
    if isinstance(v, Decimal):
        d = v
    elif isinstance(v, bool):        # bool ist ein int – hier nie eine Menge
        d = Decimal(int(v))
    elif isinstance(v, float):
        d = Decimal(str(v))
    else:
        try:
            d = Decimal(str(v).strip())
        except Exception:
            return ZERO
    return d.quantize(QTY_EXP, rounding=ROUND_HALF_UP)


def qty_sum(values: Iterable) -> Decimal:
    """Summe von Mengen (jede via ``to_qty`` normalisiert) – exakt."""
    total = ZERO
    for v in values:
        total += to_qty(v)
    return total


def is_whole(v) -> bool:
    """Ist die Menge ganzzahlig? (Einzelteil-Artikel dürfen nur ganze Stück haben –
    2.5 Schrauben gibt es nicht; kg/m²/… dürfen Bruchmengen sein.)"""
    d = to_qty(v)
    return d == d.to_integral_value()


def qty_key(v) -> str:
    """JSON-sichere Darstellung einer Menge für die Reservierungs-Map (String, exakt)."""
    return str(to_qty(v))
