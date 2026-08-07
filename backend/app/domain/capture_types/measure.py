"""Soll-Ist-Vergleich — Sollwert vorgeben, Istwert erfassen.

Der einzige Typ, der die Definition um etwas erweitert: ohne Sollwert gibt es nichts zu
vergleichen. Genau darum wird er beim Anlegen **verlangt** und nicht mit 0 vorbelegt –
eine stille Null wäre ein Sollwert, den niemand gesetzt hat, und jede Messung fiele
durch.
"""

from typing import Any, Optional

from .base import CaptureType, bad


def _number(value: Any) -> Optional[float]:
    """Zahl oder ``None``. Ein Komma wird akzeptiert – getippt wird es ohnehin."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


class Measure(CaptureType):
    key = "measure"
    label = "Soll-Ist-Vergleich"
    order = 50

    def clean(self, point: dict[str, Any]) -> dict[str, Any]:
        label = point.get("label")
        target = _number(point.get("target"))
        if target is None:
            raise bad(
                f"«{label}»: ein Soll-Ist-Vergleich braucht einen Sollwert. "
                f"Ohne ihn gibt es nichts zu vergleichen."
            )
        tolerance = _number(point.get("tolerance"))
        if tolerance is None:
            tolerance = 0.0
        if tolerance < 0:
            raise bad(f"«{label}»: die Toleranz kann nicht negativ sein.")
        return {"target": target, "tolerance": tolerance}

    def missing(self, point: dict[str, Any], value: Any) -> bool:
        return _number(value) is None

    def verdict(self, point: dict[str, Any], value: Any) -> Optional[bool]:
        actual = _number(value)
        if actual is None:
            return False
        target = _number(point.get("target"))
        if target is None:
            # Kann nach ``clean`` nicht vorkommen. Hier steht bewusst kein «bestanden»:
            # eine Messung ohne Soll ist eine Ablesung, kein Urteil.
            return None
        return abs(actual - target) <= (_number(point.get("tolerance")) or 0.0)


TYPE = Measure()
