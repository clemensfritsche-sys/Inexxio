"""►►► **Eine Telefonnummer – gewählt und angezeigt an EINER Stelle.** ◄◄◄

Die Website zeigt sie (``routers/website``), jede Mail unterschreibt mit ihr
(``services/mail_layout``) – zwei Schreibweisen derselben Nummer wären zwei Nummern.
"""

from . import address as addr

# Vorwahl je Land – für die Wahl-Adresse (`tel:`).
_CALLING = {"CH": "41", "LI": "423", "DE": "49", "AT": "43", "IT": "39", "FR": "33"}

# Anzeige: so, wie man die Nummer im Land schreibt (Testnotiz #1187 – «+41795058302» liest
# niemand). Gruppen nach der Vorwahl; ein Land ohne Eintrag bleibt wie erfasst – eine
# geratene Gruppierung wäre schlechter als keine.
_GROUPS = {"41": (2, 3, 2, 2), "423": (3, 2, 2)}


def e164(phone: str | None, country: str | None) -> str | None:
    raw = "".join(c for c in (phone or "") if c.isdigit() or c == "+")
    if not raw:
        return None
    if raw.startswith("+"):
        return raw
    if raw.startswith("00"):
        return "+" + raw[2:]
    code = _CALLING.get((addr.iso2(country) or "").upper())
    return f"+{code}{raw.lstrip('0')}" if code and raw.startswith("0") else raw


def display(phone: str | None, e164: str | None) -> str | None:
    """«+41 79 505 83 02» statt «+41795058302» – nur, wo die Gruppierung feststeht."""
    for code, groups in _GROUPS.items():
        rest = (e164 or "")[1 + len(code):]
        if (e164 or "").startswith(f"+{code}") and rest.isdigit() and len(rest) == sum(groups):
            parts, i = [], 0
            for n in groups:
                parts.append(rest[i:i + n])
                i += n
            return f"+{code} " + " ".join(parts)
    return phone
