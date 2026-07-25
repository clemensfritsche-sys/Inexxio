"""Adressen – **EINE** Darstellung für Person, Unternehmen und Lagerplatz.

Eine Adresse ist am Ende überall dasselbe, egal ob sie an einer Person (Liefer-/
Rechnungs-/Wohnadresse), am Unternehmen (Firmensitz) oder an einem Lagerplatz hängt.
Die Spaltennamen sind historisch **unterschiedlich** gewachsen
(``address_line1``/``postal_code`` an der Person vs. ``street``+``street_nr``/``zip_code``
am Unternehmen) – dieses Modul ist die eine Stelle, die das übersetzt.

**Kanonische Form** (identisch mit dem Versand-Adress-Snapshot, damit Carrier-Adapter,
Etiketten und Briefköpfe dieselben Schlüssel sehen)::

    {name, street1, street2, zip, city, country, email, phone}

Vorher baute **jede** Stelle ihre Adresse selbst zusammen – mit je eigener
Fallback-Logik (``ship_* or *``) und eigenem Strassen-Join: ``services/logistics``,
``services/document_render`` (Briefkopf), ``services/payments/stripe_provider``,
``services/ai/tools`` und die Settings-Router. Genau diese Duplikate holt dieses Modul
zusammen; ``country`` wird dabei konsequent nach ISO-2 normalisiert.
"""

import re
from typing import Optional

# Ländername → ISO-2 (tolerant; Carrier-APIs verlangen Codes).
_COUNTRY_ISO2 = {
    "schweiz": "CH", "switzerland": "CH", "suisse": "CH", "svizzera": "CH", "ch": "CH",
    "deutschland": "DE", "germany": "DE", "de": "DE",
    "österreich": "AT", "oesterreich": "AT", "austria": "AT", "at": "AT",
    "frankreich": "FR", "france": "FR", "fr": "FR",
    "italien": "IT", "italy": "IT", "it": "IT",
    "liechtenstein": "LI", "li": "LI",
    "usa": "US", "vereinigte staaten": "US", "united states": "US", "us": "US",
    "grossbritannien": "GB", "united kingdom": "GB", "uk": "GB", "gb": "GB",
    "niederlande": "NL", "netherlands": "NL", "nl": "NL",
    "belgien": "BE", "belgium": "BE", "be": "BE",
    "spanien": "ES", "spain": "ES", "es": "ES",
}

# Platzhalter für «keine Strasse hinterlegt» – Carrier-Adapter erwarten ein Feld.
DASH = "—"


def iso2(country: Optional[str]) -> str:
    """Ländername → ISO-2 (tolerant); Default CH (Sitz des Unternehmens)."""
    c = (country or "").strip().lower()
    if not c:
        return "CH"
    if c in _COUNTRY_ISO2:
        return _COUNTRY_ISO2[c]
    return c.upper() if len(c) == 2 else "CH"


def _txt(v) -> str:
    return str(v).strip() if v is not None else ""


def _join(*parts) -> str:
    """Nicht-leere Teile mit Leerzeichen verbinden (z. B. Strasse + Hausnummer)."""
    return " ".join(p for p in (_txt(p) for p in parts) if p)


def make(*, name: str = "", street1: str = "", street2: str = "", zip: str = "",
         city: str = "", state: str = "", country=None, email=None, phone=None) -> dict:
    """Kanonische Adresse bauen (leere Strasse → ``—``, damit Carrier-Felder belegt sind)."""
    return {
        "name": _txt(name),
        "street1": _txt(street1) or DASH,
        "street2": _txt(street2) or None,
        "zip": _txt(zip),
        "city": _txt(city),
        "state": _txt(state) or None,
        "country": iso2(country),
        "email": _txt(email) or None,
        "phone": _txt(phone) or None,
    }


# ─── Herkünfte ────────────────────────────────────────────────────────────────────

def person_name(u) -> str:
    """Anzeigename einer Person für eine Adresse: Firma ≻ Vor-/Nachname ≻ E-Mail."""
    return (
        _txt(getattr(u, "company_name", None))
        or _join(getattr(u, "first_name", None), getattr(u, "last_name", None))
        or _txt(getattr(u, "email", None))
        or "Empfänger"
    )


def of_user(u, kind: str = "ship") -> dict:
    """Adresse einer Person. ``kind`` wählt den Block, mit Rückfall auf die Wohnadresse:

    * ``ship``    – Lieferadresse (Standard: wohin Ware geht)
    * ``invoice`` – Rechnungsadresse
    * ``home``    – Wohn-/Kontaktadresse (kein Rückfall nötig)

    Der Rückfall war bisher an jeder Aufrufstelle einzeln ausgeschrieben
    (``u.ship_postal_code or u.postal_code`` …) – hier steht er genau einmal."""
    prefix = {"ship": "ship_", "invoice": "invoice_", "home": ""}.get(kind, "ship_")

    def pick(field: str):
        """Feld aus dem gewählten Block, sonst aus der Wohnadresse."""
        val = getattr(u, f"{prefix}{field}", None) if prefix else None
        return val if _txt(val) else getattr(u, field, None)

    return make(
        name=person_name(u),
        street1=pick("address_line1"), street2=pick("address_line2"),
        zip=pick("postal_code"), city=pick("city"),
        state=pick("state_region"), country=pick("country"),
        email=getattr(u, "email", None), phone=getattr(u, "phone", None),
    )


def of_company(s) -> dict:
    """Adresse des Unternehmens (Firmensitz). ``street``+``street_nr`` werden zur
    kanonischen ``street1`` zusammengezogen."""
    return make(
        name=_txt(getattr(s, "company_name", None)) or "Inexxio",
        street1=_join(getattr(s, "street", None), getattr(s, "street_nr", None)),
        zip=getattr(s, "zip_code", None), city=getattr(s, "city", None),
        country=getattr(s, "country", None),
        email=getattr(s, "email", None), phone=getattr(s, "phone", None),
    )


def of_storage(loc) -> dict:
    """Adresse eines Lagerplatzes (``address_*``-Felder)."""
    return make(
        name=_txt(getattr(loc, "name", None)) or "Lagerplatz",
        street1=getattr(loc, "address_street", None),
        zip=getattr(loc, "address_zip", None), city=getattr(loc, "address_city", None),
        country=getattr(loc, "address_country", None),
    )


# ─── Darstellung & Vergleich ──────────────────────────────────────────────────────

def has_content(a: Optional[dict]) -> bool:
    """Trägt die Adresse echte Ortsangaben (PLZ oder Ort)? ``—``/leer zählt nicht."""
    if not a:
        return False
    return bool(_txt(a.get("zip")) or _txt(a.get("city")))


def one_line(a: Optional[dict]) -> Optional[str]:
    """Einzeilige Anzeige: «Name · Strasse · PLZ Ort · Land» (leere Teile entfallen)."""
    if not a:
        return None
    bits = [a.get("name"), a.get("street1"), _join(a.get("zip"), a.get("city")), a.get("country")]
    return " · ".join(b for b in (_txt(x) for x in bits) if b and b != DASH) or None


def lines(a: Optional[dict]) -> list[str]:
    """Mehrzeilige Anzeige (Briefkopf/Etikett): Name / Strasse / Zusatz / PLZ Ort / Land."""
    if not a:
        return []
    out = [_txt(a.get("name")), _txt(a.get("street1")), _txt(a.get("street2")),
           _join(a.get("zip"), a.get("city")), _txt(a.get("country"))]
    return [x for x in out if x and x != DASH]


def _norm(v) -> str:
    """Bestandteil normalisieren (klein, ohne Sonderzeichen) für den Vergleich."""
    return re.sub(r"[^a-z0-9]", "", _txt(v).lower())


def same(a: Optional[dict], b: Optional[dict]) -> bool:
    """Zwei Adressen als **gleicher Ort** werten (Strasse+PLZ+Ort+Land normalisiert).

    Ohne echte Ortsangabe (siehe ``has_content``) gilt bewusst *nicht* «gleich» – sonst
    würden zwei leere Adressen als derselbe Ort durchgehen."""
    if not has_content(a) or not has_content(b):
        return False
    key = lambda x: (_norm(x.get("street1")), _norm(x.get("zip")),
                     _norm(x.get("city")), _norm(x.get("country")))
    return key(a) == key(b)
