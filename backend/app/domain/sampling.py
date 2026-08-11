"""**Die Stichprobenregel — wie viele der wartenden Stücke erfasst werden.**

Eine Angabe, drei Formen: *alle* (Vorgabe) · *Anzahl n* · *Prozent p*. Mehr braucht es
nicht, und ein Formular mit fünf Feldern wäre die falsche Antwort auf eine Frage, die
sich in einem Satz stellen lässt.

**Die Regel gilt je Instanz, nicht je Auftrag.** Das ist keine Vereinfachung, sondern die
fachliche Form: eine Stichprobe wird aus einem **Los** gezogen (ISO 2859-1), und das Los
ist hier die Instanz — die Charge, die physisch als eine Kiste dasteht. «10 % von drei
Chargen» heisst darum 10 % **aus jeder**, nicht 10 % aus dem Haufen; sonst bliebe eine
ganze Charge womöglich ungeprüft, und die Aussage der Stichprobe wäre keine.

Daraus folgt zugleich, dass eine Stichprobe **nie leer** ist: aufgerundet wird, weil
«0 von 5» keine Prüfung ist, sondern ihr Ausfall.
"""

import math
from typing import Any

from fastapi import HTTPException

#: Alle wartenden Stücke werden erfasst. Die Vorgabe — wer nichts sagt, prüft alles.
ALL = "all"
#: Eine feste Anzahl je Instanz.
COUNT = "count"
#: Ein Anteil der Instanz, aufgerundet.
PERCENT = "percent"

MODES = (ALL, COUNT, PERCENT)

#: Was ohne Angabe gilt.
DEFAULT: dict[str, Any] = {"mode": ALL, "value": None}


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def clean(raw: Any) -> dict[str, Any]:
    """Die Regel prüfen und normalisieren. Fehlt sie, gilt **alle**.

    Ein unbekannter Modus ist ein harter Fehler und kein Rückfall auf «alle»: wer
    «prozent» tippen wollte und sich vertippt, prüfte sonst stillschweigend alles – das
    ist zwar die sichere Richtung, aber es ist nicht das, was dasteht.
    """
    if not raw:
        return dict(DEFAULT)
    mode = (raw or {}).get("mode") or ALL
    if mode not in MODES:
        raise _bad(
            f"«{mode}» ist keine Stichprobenregel. Erlaubt: "
            + ", ".join(MODES) + "."
        )
    if mode == ALL:
        return dict(DEFAULT)

    value = (raw or {}).get("value")
    try:
        value = int(str(value).strip())
    except (TypeError, ValueError):
        raise _bad(
            "Die Stichprobe braucht eine Zahl – ohne sie ist nicht entscheidbar, "
            "wie viele Stücke erfasst werden."
        )
    if mode == COUNT and value < 1:
        raise _bad("Eine Stichprobe von weniger als einem Stück ist keine Stichprobe.")
    if mode == PERCENT and not (1 <= value <= 100):
        raise _bad("Der Anteil muss zwischen 1 und 100 Prozent liegen.")
    return {"mode": mode, "value": value}


def size(rule: Any, population: int) -> int:
    """Wie viele Stücke werden aus **dieser Instanz** gezogen?

    Aufgerundet und mindestens eines, höchstens alle. Der Deckel ist keine Kosmetik:
    «Anzahl 12» an einer Instanz mit 5 Stücken zieht 5 – die Regel sagt, wie viele man
    prüfen *will*, nicht wie viele es geben muss.
    """
    if population < 1:
        return 0
    rule = rule or DEFAULT
    mode = rule.get("mode") or ALL
    if mode == ALL:
        return population
    value = int(rule.get("value") or 0)
    drawn = value if mode == COUNT else math.ceil(population * value / 100)
    return max(1, min(population, drawn))


def describe(rule: Any) -> str:
    """Die Regel als Satz – für Anzeige und Fehlermeldung, aus **einer** Quelle."""
    rule = rule or DEFAULT
    mode = rule.get("mode") or ALL
    if mode == ALL:
        return "alle"
    value = rule.get("value")
    return f"{value} je Instanz" if mode == COUNT else f"{value} % je Instanz"
