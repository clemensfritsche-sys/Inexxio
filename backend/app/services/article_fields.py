"""**Die Spezifikation eines Artikels – als Auskunft, die mitreisen kann.**

Sie beschreibt **die Sache**: Abmessungen, Gewicht, Werkstoff, Oberfläche, Zeichnung,
Gefahrgut. Was mit ihr geschehen soll, steht **nicht** hier – das ist der Auftrag an den
Lieferanten (``Beschaffen.INSTRUCTION``), und eine Bestellnummer gehört ihm, nicht dem
Teil (die Angebotszeile bzw. ``Purchase.reference``). Drei Schichten, drei Orte.

**Sie wird nicht ausgewählt, sie reist mit.** Vorher stand hier ein Katalog mit einer
Spalte ``mandatory`` – die Grundlage einer Konfiguration «welche Felder sieht der
Lieferant?» je Beschaffungs-Schritt. Sie hatte **null Aufrufer** (der Basis-Neuaufbau
hat sie entfernt) und käme auch nicht zurück: bei zwei zugelassenen Lieferanten müsste
dieselbe Frage zweimal beantwortet werden, und eine Spezifikation, die je nach Empfänger
anders lautet, ist keine. Wer etwas nicht zeigen will, schreibt es nicht in die
Spezifikation.

**Was bewusst NICHT mitreist:** ``serialization`` (sagt, wie *wir* zählen, nicht was das
Teil ist), ``min_order_qty``/``safety_stock`` (unsere Dispositionsgrössen) und
``supplier_article_number`` – die Nummer gehört genau **einem** Lieferanten, und sie
allen zu zeigen wäre genau der Fehler, den die dritte Schicht vermeidet.
"""

from decimal import Decimal
from typing import Any, Optional

from ..models import Article

#: Reihenfolge = Anzeige-Reihenfolge. ``(Feld, Beschriftung, Einheit)`` – die Einheit
#: steht hier, weil sie zum Feld gehört und nicht zur Ansicht (eine Zahl ohne Einheit ist
#: keine Angabe).
SPEC_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("size", "Grösse", "mm"),
    ("weight_kg", "Gewicht", "kg"),
    ("material", "Werkstoff", ""),
    ("surface", "Oberfläche", ""),
    ("cad_url", "Zeichnung", ""),
    ("is_hazmat", "Gefahrgut", ""),
)


def _value(article: Article, key: str) -> Optional[str]:
    raw: Any = getattr(article, key, None)
    if key == "is_hazmat":
        # Ein «Nein» ist keine Auskunft – nur die Gefahr wird genannt.
        return "Ja" if raw else None
    if raw in (None, ""):
        return None
    if isinstance(raw, Decimal):
        return format(raw.normalize(), "f")
    return str(raw)


def specification(article: Optional[Article]) -> list[dict[str, str]]:
    """Die gefüllten Spezifikations-Felder eines Artikels – ``[{label, value}]``.

    **Leere Felder fallen weg**: eine Zeile «Werkstoff: —» sagt weniger als keine Zeile,
    und der Empfänger soll sehen, was gilt, nicht was fehlt.
    """
    if article is None:
        return []
    out: list[dict[str, str]] = []
    for key, label, unit in SPEC_FIELDS:
        value = _value(article, key)
        if value is not None:
            out.append({"label": label, "value": f"{value} {unit}".strip()})
    return out
