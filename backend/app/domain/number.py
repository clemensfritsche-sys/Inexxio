"""►►► **Eine Zahl aus einer Eingabe – EINE Stelle** (Betrag, Gewicht, gelesene Werte). ◄◄◄

Wie Menschen in der Schweiz Zahlen schreiben: «1'234.50», «1’234.50», «1 234,50», «1.234,50»,
«1,234.50». Tausender-Zeichen (Apostroph in jeder Form, Leerzeichen) fallen weg; stehen Punkt
UND Komma da, ist das **letzte** der Dezimaltrenner; steht nur eines da, ist es der
Dezimaltrenner – ausser es kommt mehrfach vor («1.234.567»), dann trennt es Tausender.
Gerechnet wird über ``Decimal``, nie ``float``.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

#: Was Tausender trennt: Apostroph in allen Formen und jede Art Leerzeichen.
_GROUPING = re.compile(r"['’‘ʼ\s   ]")


def decimal(value: Any) -> Optional[Decimal]:
    """Die Zahl – ``None``, wenn nichts dasteht; ``ValueError`` mit Satz, wenn es keine ist."""
    if value is None:
        return None
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    raw = _GROUPING.sub("", str(value))
    if not raw:
        return None
    if "," in raw and "." in raw:
        decimal_mark = "," if raw.rfind(",") > raw.rfind(".") else "."
        raw = raw.replace("." if decimal_mark == "," else ",", "")
    for mark in (",", "."):
        if raw.count(mark) > 1:
            raw = raw.replace(mark, "")
    raw = raw.replace(",", ".")
    try:
        found = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"«{value}» ist keine Zahl.")
    if not found.is_finite():
        raise ValueError(f"«{value}» ist keine Zahl.")
    return found


def lenient(text: Any) -> Optional[Decimal]:
    """Eine Zahl aus freiem Text («CHF 1'234.50 inkl. MWST») – ``None``, wenn keine darin steht."""
    found = re.search(r"-?\d[\d'’‘ʼ\s   .,]*", str(text or ""))
    if found is None:
        return None
    try:
        return decimal(found.group(0).strip(" .,"))
    except ValueError:
        return None
