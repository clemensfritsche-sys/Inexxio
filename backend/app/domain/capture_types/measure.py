"""Soll-Ist-Vergleich — Sollwert vorgeben, Istwert erfassen.

Der Sollwert wird beim Anlegen **verlangt**, nie mit 0 vorbelegt. **Die Einheit ist ein
freies, kurzes Wort** (°C, bar, Nm …), keine Liste: die Lagereinheiten des Artikels
(``schemas/article.ALLOWED_UNITS``) beantworten eine andere Frage, und gerechnet wird mit
Messeinheiten nie – sie werden angezeigt.
"""

from typing import Any, Optional

from .. import number
from .base import CaptureType, bad

#: Wie lang eine Einheit sein darf («mm», «°C», «N·m»); mehr gehört in die Beschriftung.
UNIT_MAX = 8


def _number(value: Any) -> Optional[float]:
    """Zahl oder ``None`` – gelesen wie jede Zahl im ERP (``domain/number``: «1'250», «1,5»).
    Gespeichert wird sie als ``float`` (die Einstellung ist JSON)."""
    try:
        found = number.decimal(value)
    except ValueError:
        return None
    return None if found is None else float(found)


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
        unit = str(point.get("unit") or "").strip()[:UNIT_MAX]
        # Ohne Einheit erlaubt – es gibt Messungen ohne Einheit (Zählwert).
        return {"target": target, "tolerance": tolerance, "unit": unit}

    def missing(self, point: dict[str, Any], value: Any) -> bool:
        return _number(value) is None

    def verdict(self, point: dict[str, Any], value: Any) -> Optional[bool]:
        actual = _number(value)
        if actual is None:
            return False
        target = _number(point.get("target"))
        if target is None:
            # Kann nach ``clean`` nicht vorkommen; ohne Soll ist es eine Ablesung, kein Urteil.
            return None
        return abs(actual - target) <= (_number(point.get("tolerance")) or 0.0)


TYPE = Measure()
