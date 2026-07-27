"""Kennzahlen aus der Historie – die EINE Stelle für «Median, dazu die Spanne».

Abgeleitete Werte (Durchlaufzeit, Einstandspreis) werden im ERP nach demselben Muster
gezeigt: der **Median** trägt die Aussage, Kleinst- und Grösstwert stehen untergeordnet
daneben.

Warum Median und nicht Durchschnitt: ein einzelner Eil-Auftrag oder eine Kleinstmenge zu
Apothekerpreisen zieht den Mittelwert weg – der Median bleibt bei dem, was üblich ist.
Genau das ist die Frage hinter «wie lange dauert das» und «was kostet das normalerweise».
"""

from statistics import median
from typing import Iterable, Optional, TypeVar

T = TypeVar("T")


def spread(values: Iterable[Optional[T]]) -> tuple:
    """``(median, kleinster, grösster)`` – oder dreimal ``None`` ohne Datenpunkte.

    Typ-erhaltend: ``Decimal`` bleibt ``Decimal`` (Geld), ``float`` bleibt ``float``
    (Tage). ``None``-Werte werden übersprungen.
    """
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return (None, None, None)
    return (median(vals), vals[0], vals[-1])
