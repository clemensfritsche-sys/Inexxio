"""►►► **Eine Telefonnummer – geschrieben, gewählt und angezeigt an EINER Stelle.** ◄◄◄

**Überall international** («+41 52 378 22 47»): so steht sie, wo jemand sie eintippt (Konto, ERP,
Formular der Website, Gesellschaft, Adressbuch – gespeichert in dieser Form, ``tidy``), wo das ERP
sie zeigt, auf jedem Papier, unter jeder Mail und auf der Website (``routers/website``,
``services/mail_layout``). Zwei Schreibweisen derselben Nummer wären zwei Nummern.

Eine Landesnummer ohne Vorwahl («079 …») bekommt die Vorwahl des Landes (ohne Land die Schweiz,
wie überall: ``address.iso2``). Gruppiert wird, wo die Gruppierung feststeht (CH, LI); sonst bleiben
die getippten Gruppen nach der Landesvorwahl – eine geratene Gruppe wäre schlechter als keine.
"""

from typing import Optional

from . import address as addr

# Vorwahl je Land – für die Wahl-Adresse (`tel:`) und die Anzeige.
_CALLING = {"CH": "41", "LI": "423", "DE": "49", "AT": "43", "IT": "39", "FR": "33",
            "GB": "44", "US": "1", "NL": "31", "BE": "32", "ES": "34", "LU": "352", "PT": "351"}

# Gruppen nach der Vorwahl (Testnotiz #1187 – «+41795058302» liest niemand).
_GROUPS = {"41": (2, 3, 2, 2), "423": (3, 2, 2)}


def e164(phone: Optional[str], country: Optional[str] = None) -> Optional[str]:
    """Die Nummer zum Wählen («+41523782247»); ohne Ziffern ``None``."""
    raw = "".join(c for c in (phone or "") if c.isdigit() or c == "+")
    if not raw:
        return None
    if raw.startswith("+"):
        return raw
    if raw.startswith("00"):
        return "+" + raw[2:]
    code = _CALLING.get((addr.iso2(country) or "CH").upper())
    return f"+{code}{raw.lstrip('0')}" if code and raw.startswith("0") else raw


def display(phone: Optional[str], e164: Optional[str]) -> Optional[str]:
    """«+41 79 505 83 02» – international; gruppiert, wo die Gruppierung feststeht, sonst die
    Gruppen, wie sie getippt wurden, mit der Vorwahl davor («0171 1234567» → «+49 171 1234567»).
    Ohne erkennbare Landesvorwahl bleibt die Nummer, wie sie kam."""
    number = e164 or ""
    for code, groups in _GROUPS.items():
        rest = number[1 + len(code):]
        if number.startswith(f"+{code}") and rest.isdigit() and len(rest) == sum(groups):
            parts, i = [], 0
            for n in groups:
                parts.append(rest[i:i + n])
                i += n
            return f"+{code} " + " ".join(parts)
    if not (number.startswith("+") and number[1:].isdigit()):
        return phone
    text = " ".join((phone or "").split())
    if text.startswith("+"):
        return text
    if text.startswith("00"):
        return "+" + text[2:].strip()
    for code in sorted(set(_CALLING.values()), key=len, reverse=True):
        if number.startswith(f"+{code}") and text.startswith("0"):
            return f"+{code} {text.lstrip('0').strip()}"
    return number


def tidy(raw: Optional[str], country: Optional[str] = None) -> Optional[str]:
    """►► **Die eine Schreibweise beim Speichern** – was jemand eintippt, wird international
    («052 378 22 47» → «+41 52 378 22 47»). Leer bleibt leer (``None``). ◄◄"""
    text = " ".join((raw or "").split())
    if not text:
        return None
    return display(text, e164(text, country)) or text
