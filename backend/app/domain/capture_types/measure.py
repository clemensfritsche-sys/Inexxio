"""Soll-Ist-Vergleich — Sollwert vorgeben, Istwert erfassen.

Der einzige Typ, der die Definition um etwas erweitert: ohne Sollwert gibt es nichts zu
vergleichen. Genau darum wird er beim Anlegen **verlangt** und nicht mit 0 vorbelegt –
eine stille Null wäre ein Sollwert, den niemand gesetzt hat, und jede Messung fiele
durch.

**Die Einheit ist ein freies Wort, keine Liste** (Testnotiz #707). Der Artikel führt zwar
eine geschlossene Liste (``schemas/article.ALLOWED_UNITS`` = Stk · mm · m2 · m3 · kg · l),
aber die beantwortet eine **andere** Frage: *worin wird die Menge geführt* – wie viel
habe ich davon. Hier geht es darum, *worin gemessen wird*. Die beiden überschneiden sich
nur zufällig: «Stk» ist als Messeinheit sinnlos, und °C, bar, Nm, %, s fehlen – zu Recht,
denn als Lagereinheit gäbe es sie nicht. Die Liste wiederzuverwenden hiesse, genau die
Einheit nicht anbieten zu können, die der Anlass war; sie zu erweitern hiesse, °C im
Artikel als Lagereinheit anzubieten.

Eine **zweite** Liste zu pflegen wäre der andere Fehler: Messeinheiten sind offen (jede
Branche hat ihre), und das System rechnet nie mit ihnen – es zeigt sie an. Also ein
kurzes freies Wort, das am Wert klebt.
"""

from typing import Any, Optional

from .base import CaptureType, bad

#: Wie lang eine Einheit sein darf. «mm», «°C», «N·m» – wer mehr braucht, schreibt einen
#: Satz, und der gehört in die Beschriftung des Punktes, nicht hinter die Zahl.
UNIT_MAX = 8


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
        unit = str(point.get("unit") or "").strip()[:UNIT_MAX]
        # Ohne Einheit ist die Zahl eine blosse Zahl – erlaubt, weil es Messungen ohne
        # Einheit gibt (Stückzahl an einem Prüfmerkmal, ein Zählwert). Erzwungen wäre sie
        # ein Pflichtfeld, in das man «-» schreibt.
        return {"target": target, "tolerance": tolerance, "unit": unit}

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
