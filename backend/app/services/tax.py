"""MWST-Sätze (Schweiz) – bewusst **einfach** (siehe Aufgabe: kein OSS/IOSS, keine
Stripe Tax). Regeln aus CLAUDE.md:

    CH Standard   8.1 %   (tax_class='standard')
    CH Reduziert  2.6 %   (tax_class='reduced')
    CH Beherbergung 3.8 % (tax_class='lodging')
    Export / Nicht-CH 0 % (Lieferung ins Ausland)
    EU B2B 0 % + Reverse Charge (VAT-ID auf Rechnung)

Steuerklasse ``zero`` ist immer 0 %. Liechtenstein gehört zum CH-MWST-Raum.
"""

from decimal import Decimal

# Steuerklasse → CH-Inlandsatz (Prozent).
CH_RATES = {
    "standard": Decimal("8.1"),
    "reduced": Decimal("2.6"),
    "lodging": Decimal("3.8"),
    "zero": Decimal("0"),
}
TAX_CLASSES = tuple(CH_RATES.keys())

# Länder im CH-MWST-Raum (CH + Liechtenstein), tolerant gegenüber Schreibweisen.
_CH_AREA = {"schweiz", "switzerland", "ch", "suisse", "svizzera",
            "liechtenstein", "li", "fl"}


def is_ch_area(country: str | None) -> bool:
    if not country:
        return True   # ohne Angabe wird CH (Inland) angenommen
    return country.strip().lower() in _CH_AREA


def vat_rate(tax_class: str, ship_country: str | None = None,
             is_b2b: bool = False, has_vat_id: bool = False) -> Decimal:
    """MWST-Satz (Prozent) für eine Steuerklasse + Lieferland.

    Inland (CH/FL): Satz je Klasse. Ausland: 0 % (Export bzw. EU-B2B Reverse Charge).
    ``is_b2b``/``has_vat_id`` sind für die spätere Belegausweisung (Reverse Charge)
    vorgesehen – am Satz ändern sie im MVP nichts (Ausland ist ohnehin 0 %)."""
    cls = tax_class if tax_class in CH_RATES else "standard"
    if cls == "zero":
        return Decimal("0")
    if is_ch_area(ship_country):
        return CH_RATES[cls]
    # Ausland: Export 0 % bzw. EU-B2B 0 % + Reverse Charge (VAT-ID auf Rechnung).
    # TODO(Erweiterung): EU-B2C lokale Sätze via OSS/IOSS – bewusst NICHT gebaut.
    return Decimal("0")
