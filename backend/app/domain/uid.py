"""►►► **Die UID — die eine Kennung, an der eine Firma erkannt wird.** ◄◄◄

Eine Firma ist eine **Rechtsperson**, und eine Rechtsperson hat eine amtliche Nummer: in
der Schweiz die **UID** (``CHE-123.456.789``), in der EU die **USt-IdNr./VAT-ID**
(``DE123456789``). Gleiche Nummer heisst gleiche Firma – das ist der einzige Schlüssel,
der zwischen zwei Menschen, die dieselbe Firma eintippen, ohne Rückfrage entscheidet.

**Geprüft wird hier, nicht bei einem Register.** Eine Abfrage beim UID-Register wäre ein
fremder Dienst im Speicherpfad (Ausfall, Kontingent, Datenschutz), und sie beantwortet
eine Frage, die wir nicht haben: ob die Nummer *gültig* ist, sagt bei der UID schon ihre
**Prüfziffer** (eCH-0097, Modulo 11). Was danach noch falsch sein kann – eine gültige
Nummer einer *anderen* Firma –, findet auch kein Register.

**Was nicht die Schweiz ist, wird nur in der Form geprüft**: zwei Buchstaben Land, danach
2–13 Buchstaben oder Ziffern. Die Prüfziffern der EU-Länder sind 27 verschiedene
Verfahren; sie hier nachzubauen hiesse, 27 Stellen zu pflegen, die beim ersten falschen
Verfahren eine echte Nummer abweisen.

Drei Funktionen, eine Form: ``normalize`` (wie gespeichert und verglichen wird),
``problem`` (warum eine Eingabe keine Nummer ist – oder ``None``) und ``display`` (wie sie
auf einem Beleg steht).
"""

from __future__ import annotations

import re
from typing import Optional

#: Die Zusätze, die eine Schweizer UID als MWST-Nummer kennzeichnen («CHE-… MWST»).
_SUFFIXES = ("MWST", "TVA", "IVA", "VAT")
#: Die Gewichte der Prüfziffer (eCH-0097 §2.2).
_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4)
_FOREIGN = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,13}$")


def normalize(raw: Optional[str]) -> str:
    """**Wie eine Nummer gespeichert und verglichen wird** – ohne Satzzeichen, gross,
    ohne MWST-Zusatz. «CHE-123.456.789 MWST» und «che123456789» sind dieselbe Nummer.
    Leer bleibt leer."""
    text = "".join(ch for ch in (raw or "").upper() if ch.isalnum())
    for suffix in _SUFFIXES:
        if text.startswith("CHE") and text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def _check_digit(digits: str) -> Optional[int]:
    """Die Prüfziffer der ersten acht Ziffern – ``None``, wo es keine gibt (Rest 10)."""
    total = sum(int(d) * w for d, w in zip(digits, _WEIGHTS))
    check = 11 - total % 11
    if check == 11:
        return 0
    return None if check == 10 else check


def problem(raw: Optional[str]) -> Optional[str]:
    """►►► **Warum diese Eingabe keine UID ist** – oder ``None``. ◄◄◄

    Der Satz nennt die Eingabe, wie sie getippt wurde: «CHE-123.456.789» ist keine
    gültige UID – nicht «ungültige Eingabe»."""
    key = normalize(raw)
    shown = (raw or "").strip()
    if not key:
        return None
    if key.startswith("CHE"):
        digits = key[3:]
        if len(digits) != 9 or not digits.isdigit():
            return (f"«{shown}» ist keine UID – sie hat die Form CHE-123.456.789 "
                    f"(neun Ziffern).")
        if _check_digit(digits[:8]) != int(digits[8]):
            return (f"«{shown}» ist keine gültige UID – die Prüfziffer stimmt nicht. "
                    f"Bitte die Nummer mit dem Handelsregister vergleichen.")
        return None
    if not _FOREIGN.match(key) or not any(ch.isdigit() for ch in key):
        return (f"«{shown}» ist keine UID bzw. USt-IdNr. – sie beginnt mit dem Land "
                f"(CHE-…, DE…, ATU…).")
    return None


def display(raw: Optional[str]) -> str:
    """**Wie die Nummer auf einem Beleg steht** – die Schweizer UID gegliedert
    (``CHE-123.456.789``), jede andere so, wie das Land sie schreibt."""
    key = normalize(raw)
    if key.startswith("CHE") and len(key) == 12 and key[3:].isdigit():
        d = key[3:]
        return f"CHE-{d[0:3]}.{d[3:6]}.{d[6:9]}"
    return key
