"""Adressen – **EINE** Darstellung, egal woher sie kommen.

Eine Adresse ist am Ende überall dasselbe, egal ob sie an einer Person oder am
Unternehmen hängt. Die Spaltennamen sind historisch **unterschiedlich** gewachsen
(``address_line1``/``postal_code`` an der Person vs. ``street``+``street_nr``/``zip_code``
am Unternehmen) – dieses Modul ist die eine Stelle, die das übersetzt.

**Kanonische Form** – ein Satz Schlüssel, den jede Anzeige gleich liest::

    {name, street1, street2, zip, city, state, country, email, phone}

**Warum es klein ist.** Es war einmal grösser: Versand-Etiketten, PDF-Briefkopf und der
Zahlungsanbieter lasen hier ihre Adressen, jeder mit eigenem Rückfall. Diese Bereiche
sind entfernt (``docs/attic.md``), und mit ihnen die Funktionen, die nur sie riefen
(``of_user``, ``one_line``, ``lines``, ``same``, ``person_name``). Sie stehen im Tag
``attic/pre-cleanup-2026-08``; wer den Versand zurückbaut, holt sie von dort, statt sie
neu zu erfinden – der Rückfall «Lieferadresse, sonst Wohnadresse» ist die eine Regel,
die man dabei leicht wieder an jeder Aufrufstelle einzeln ausschreibt.

Heute liest die **Anschrift des Unternehmens** (Impressum, Halter-Kette) und die
**Länder-Normalisierung** (Gebietskarte, Währung je Gesellschaft) hier.
"""

from typing import Optional

# Ländername → ISO-2 (tolerant). Die Gebietskarte und die Währung je Gesellschaft
# rechnen mit Codes; eingetippt wird «Schweiz».
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

#: Platzhalter für «keine Strasse hinterlegt» – ein Adressfeld bleibt damit belegt,
#: und ``has_content`` erkennt es als *nicht* ausgefüllt.
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
    """Kanonische Adresse bauen (leere Strasse → ``—``, damit das Feld belegt ist)."""
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


def has_content(a: Optional[dict]) -> bool:
    """Trägt die Adresse echte Ortsangaben (PLZ oder Ort)? ``—``/leer zählt nicht."""
    if not a:
        return False
    return bool(_txt(a.get("zip")) or _txt(a.get("city")))
