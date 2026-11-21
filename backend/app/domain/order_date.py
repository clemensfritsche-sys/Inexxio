"""►►► **Das eine Datum am Auftrag** (Projektakte ``docs/konzept/aufgaben.md`` §5). ◄◄◄

Ein Auftrag trägt **genau ein** Datum – «bis» oder «ab», nie beide, nichts zu rechnen:

* **«bis» X** – fertig bis X (Liefertermin); am Ende des Prozessbilds;
* **«ab» X** – nicht vor X (Service, Inspektion); am Start des Prozessbilds;
* **keins** – so schnell wie möglich.

Gespeichert nur am Auftrag (``orders.date_kind`` · ``orders.date_on``); die Zahlung zeigt es,
die Aufgaben lesen es. Zwei Formen derselben Regel: ``problem`` (der Satz) ↔ ``clean`` (wirft).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

UNTIL = "until"
FROM = "from"

#: Schlüssel → (Wort im Prozessbild, Wort auf dem Papier).
KINDS: dict[str, tuple[str, str]] = {
    UNTIL: ("bis", "Liefertermin"),
    FROM: ("ab", "Ausführung ab"),
}


def _day(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def problem(raw: Any, today: date) -> Optional[str]:
    """**Was an diesem Datum nicht stimmt** – ein Satz, oder ``None``. Leer ist erlaubt (keins)."""
    if raw in (None, {}, ""):
        return None
    if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
        return "Das Datum ist «bis» oder «ab»."
    on = _day(raw.get("on"))
    if on is None:
        return f"«{raw.get('on')}» ist kein Datum."
    if on < today:
        return "Das Datum liegt in der Vergangenheit – es ist heute oder später."
    return None


def clean(raw: Any, today: date) -> tuple[Optional[str], Optional[date]]:
    """►► **``(Art, Tag)`` wie gespeichert** – ``(None, None)`` für keins; sonst ``ValueError``
    mit dem Satz aus ``problem``. ◄◄"""
    why = problem(raw, today)
    if why:
        raise ValueError(why)
    if raw in (None, {}, ""):
        return None, None
    return raw["kind"], _day(raw["on"])


def paper(kind: Optional[str]) -> str:
    return KINDS.get(kind or "", ("", ""))[1]
