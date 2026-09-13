"""**Die Währung** – drei Buchstaben, und wie viele Nachkommastellen sie hat.

Ein Betrag ohne Währung ist keine Zahl. «1000» ist tausend Franken oder tausend Yen,
und das sind zwei sehr verschiedene Beträge – solange nur eine Währung vorkommt, fällt
es nicht auf, und beim ersten EU-Kunden ist es still falsch.

## Was hier steht und was bewusst nicht

Dieses Modul beantwortet **zwei** Fragen und keine dritte:

* **Gibt es diese Währung?** (``assert_code`` – streng beim Schreiben)
* **Wie viele Nachkommastellen hat sie?** (``minor_units`` – ISO 4217)

**Es rechnet nicht um.** Ein Kurs ist eine Angabe mit einem Datum, einer Quelle und
einer buchhalterischen Bedeutung (Stichtagskurs, Durchschnittskurs, Bewertung zum
Bilanzstichtag) – das ist Buchhaltung, nicht ein Feld in einem Prozessmodul. Wer
umrechnet, ohne zu sagen *wann* und *woher*, erfindet Zahlen.

**Und es mischt nicht.** Ein Beleg hat **eine** Währung. Zwei Positionen in
verschiedenen Währungen auf einem Papier gibt es nicht: das wären zwei Belege.

## Die Nachkommastellen sind der Punkt, den man vergisst

Fast alle Währungen haben zwei – und darum schreibt man ``f"{x:.2f}"`` und merkt nie,
dass es falsch ist. **JPY, KRW und ISK haben null**, TND und KWD haben **drei**. Ein
Yen-Betrag mit zwei Nachkommastellen ist kein Rundungsfehler, sondern ein Betrag, den
es nicht gibt.

Die Liste ist bewusst **kurz**: die Währungen, in denen ein Schweizer KMU wirklich
fakturiert, plus die drei nullstelligen als Beleg dafür, dass die Regel keine
Behauptung ist. Eine neue Währung ist **eine Zeile**.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: ►►► **Die Vorgabe des Hauses** – dieselbe wie am Unternehmen (``company_settings``).
#:
#: Sie steht hier als *Rückfall*, nicht als Wahrheit: gefragt wird der **Betreiber**
#: (``services/sites.find_operator``), und nur wo es ihn nicht gibt, gilt diese.
DEFAULT = "CHF"

#: Je Währung: Beschriftung und **Nachkommastellen** (ISO 4217 «minor units»).
#:
#: Die Beschriftung ist der Code selbst plus der Name – kein Symbol: «$» ist nicht
#: eindeutig (USD, CAD, AUD …), und ein Code ist in jeder Schrift lesbar.
CURRENCIES: dict[str, tuple[str, int]] = {
    "CHF": ("Schweizer Franken", 2),
    "EUR": ("Euro", 2),
    "USD": ("US-Dollar", 2),
    "GBP": ("Pfund Sterling", 2),
    # ►►► **Null Nachkommastellen** – der Fall, den ein festes `:.2f` still zerstört.
    "JPY": ("Japanischer Yen", 0),
    "KRW": ("Südkoreanischer Won", 0),
    # ►►► **Drei** – die andere Richtung, und genauso echt.
    "KWD": ("Kuwait-Dinar", 3),
}


def assert_code(value: Any) -> str:
    """Die Schreibprüfung. Unbekannt ist ein **Fehler**, kein stiller Rückfall.

    Streng schreiben, tolerant lesen – dieselbe Regel wie bei der Richtung und beim
    Steuersatz. Ein Code, den es nicht gibt, fällt sonst erst auf, wenn jemand eine
    Summe über zwei Währungen zieht.
    """
    text = str(value or "").strip().upper()
    if text not in CURRENCIES:
        raise ValueError(
            f"«{value}» ist keine bekannte Währung. Erlaubt: "
            + ", ".join(f"{c} ({name})" for c, (name, _) in CURRENCIES.items()) + "."
        )
    return text


def label(code: Any) -> str:
    """Wie sie heisst – tolerant gelesen. Unbekanntes nennt sich selbst."""
    text = str(code or "").strip().upper()
    known = CURRENCIES.get(text)
    return f"{text} · {known[0]}" if known else (text or DEFAULT)


def minor_units(code: Any) -> int:
    """**Wie viele Nachkommastellen?** – tolerant gelesen, Rückfall zwei.

    Zwei ist der häufigste Wert und die harmloseste Annahme: eine Währung mit null
    Stellen als zweistellig zu zeigen ist falsch, aber sichtbar; umgekehrt verschwände
    ein Rappen spurlos.
    """
    known = CURRENCIES.get(str(code or "").strip().upper())
    return known[1] if known else 2


def quantum(code: Any) -> Decimal:
    """Die kleinste Einheit dieser Währung – als ``Decimal`` zum Runden.

    ``CHF`` → ``0.01`` · ``JPY`` → ``1`` · ``KWD`` → ``0.001``. Wer damit quantisiert,
    rundet **je Währung** richtig, ohne dass die Rechenstelle die Währung kennen muss.
    """
    return Decimal(1).scaleb(-minor_units(code))


def round_to(value: Decimal, code: Any) -> Decimal:
    """►►► **Auf die kleinste Einheit dieser Währung – kaufmännisch.** ◄◄◄

    **Die eine Rundungsstelle des Hauses.** ``quantize`` rundet ohne Angabe
    *banker's rounding* (``ROUND_HALF_EVEN``): 12.345 wird zu 12.34, 12.355 zu 12.36.
    Das ist eine statistisch saubere Regel und in einer Rechnung die falsche – dort gilt
    kaufmännisch, und eine Anzeige, die anders rundet als die Buchung, ist ein Rappen
    Differenz, den niemand erklären kann.
    """
    return value.quantize(quantum(code), rounding=ROUND_HALF_UP)


def money(value: Decimal, code: Any) -> str:
    """Ein Betrag als **String, in der Genauigkeit seiner Währung**.

    Beträge reisen als Zeichenkette – wo es auf den Rappen ankommt, wird nicht durch
    ``float`` gerechnet, auch nicht auf dem Weg durch JSON. Und sie tragen genau so
    viele Stellen, wie die Währung hat: ein ``1000.00`` in Yen behauptet eine
    Genauigkeit, die es nicht gibt.
    """
    return f"{round_to(value, code):f}"
