"""**Die Stichprobenregel — welcher ANTEIL der wartenden Stücke erfasst wird.**

Eine Angabe, und es ist eine Zahl: der **Anteil in Prozent**. *Alle* ist dabei kein
eigener Modus, sondern schlicht 100 % – damit gibt es keine zweite Form, die man
verwechseln könnte, und die Oberfläche kann Kurzwege anbieten (alle · ½ · ¼ · frei),
ohne dass daraus verschiedene Regeln werden.

**Die Bezugsgrösse ist die Gesamtmenge, nicht die einzelne Instanz.** Ein Modul steht im
Prozess und sieht, was davorsteht: die Summe aller wartenden Einzelinstanzen. Eine Regel
«je Instanz» wäre eine Aussage über etwas, das an dieser Stelle niemand fragt – bei drei
Chargen ergäbe «10 %» dreimal eine eigene Ziehung, und die Zahl auf dem Bildschirm
stimmte mit keiner davon überein.

Daraus folgt zugleich, dass eine Stichprobe **nie leer** ist: aufgerundet wird, weil
«0 von 5» keine Prüfung ist, sondern ihr Ausfall.
"""

import math
from typing import Any

from fastapi import HTTPException

#: Der volle Anteil – jedes wartende Stück wird erfasst. Die Vorgabe.
FULL = 100

#: Was ohne Angabe gilt.
DEFAULT: dict[str, Any] = {"percent": FULL}


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def clean(raw: Any) -> dict[str, Any]:
    """Die Regel prüfen und normalisieren. Fehlt sie, gilt **alle**.

    Angenommen wird die eine Form ``{"percent": n}``. Eine unleserliche Zahl ist ein
    harter Fehler und kein Rückfall auf «alle»: wer sich vertippt, prüfte sonst
    stillschweigend alles – das ist zwar die sichere Richtung, aber es ist nicht das,
    was dasteht.
    """
    if not raw:
        return dict(DEFAULT)
    value = raw.get("percent") if isinstance(raw, dict) else raw
    if value in (None, ""):
        return dict(DEFAULT)
    try:
        percent = int(str(value).strip())
    except (TypeError, ValueError):
        raise _bad(
            "Die Stichprobe braucht eine Zahl – ohne sie ist nicht entscheidbar, "
            "wie viele Stücke erfasst werden."
        )
    if not 1 <= percent <= FULL:
        raise _bad("Der Anteil muss zwischen 1 und 100 Prozent liegen.")
    return {"percent": percent}


def percent_of(rule: Any) -> int:
    """Der Anteil einer gespeicherten Regel — **die eine Lesestelle**.

    Sie liest tolerant, weil Definitionen älter sein können als die Regel selbst: die
    frühere Form trug ``{"mode": …, "value": …}`` und meinte «je Instanz». Geschrieben
    wird nur noch die neue Form (``clean``); gelesen werden beide, damit eine Vorlage aus
    der Zeit davor weiter das tut, was dort steht.
    """
    rule = rule or DEFAULT
    if "percent" in rule:
        return int(rule.get("percent") or FULL)
    mode = rule.get("mode") or "all"
    if mode == "percent":
        return int(rule.get("value") or FULL)
    return FULL


def size(rule: Any, population: int) -> int:
    """Wie viele Stücke werden aus **allem, was hier wartet**, gezogen?

    **Aufgerundet, mindestens eines, höchstens alle.** Aufgerundet, weil eine Stichprobe,
    die auf null fällt, keine Prüfung mehr ist; der Deckel, weil «12 von 5» keine Menge
    ist. Beide Grenzen sind die konservative Richtung – im Zweifel wird mehr geprüft,
    nicht weniger.
    """
    if population < 1:
        return 0
    rule = rule or DEFAULT
    # Altbestand: eine feste **Anzahl**. Sie galt einmal je Instanz und gilt jetzt über
    # die Gesamtmenge – dieselbe Umdeutung wie überall hier, statt eine zweite Regel.
    if "percent" not in rule and (rule.get("mode") == "count"):
        return max(1, min(population, int(rule.get("value") or 0)))
    percent = percent_of(rule)
    if percent >= FULL:
        return population
    return max(1, min(population, math.ceil(population * percent / 100)))


def describe(rule: Any) -> str:
    """Die Regel als Satz – für Anzeige und Fehlermeldung, aus **einer** Quelle.

    Die Bezugsgrösse steht mit dabei: «50 %» allein liesse offen, wovon.
    """
    rule = rule or DEFAULT
    if "percent" not in rule and rule.get("mode") == "count":
        return f"{int(rule.get('value') or 0)} Stück"
    percent = percent_of(rule)
    return "alle" if percent >= FULL else f"{percent} % der Gesamtmenge"
