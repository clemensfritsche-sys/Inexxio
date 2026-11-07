"""Geografie – **Weltregionen** + Land→Region-Zuordnung (für die Gebiets-/Multi-Gesellschaften-
Aufteilung).

Kernidee der Gebietsaufteilung (siehe ADR 006): die Welt ist in **feste Regionen** partitioniert,
und **jede Region gehört genau EINER Gesellschaft** – standardmässig dem **Betreiber**, andere
Gesellschaften «beissen sich» einzelne Regionen ab (``company_territories``). Weil jede Region
einen Besitzer hat und jedes Land in genau einer Region liegt, gehört **jeder Fleck der Erde
jemandem** (Totalität) – ein unbekanntes/unzugeordnetes Land fällt an den Betreiber.

Diese Datei ist **reine Stammdaten** (keine DB): die Regionsliste (Code + Label + grobe
geografische Position für die abstrakte Weltkarte) und die ISO-2-Land→Region-Map. Die Auflösung
«welche Gesellschaft gehört zu diesem Land» steht in ``services/sites.company_for_country``
(Region → Territorium-Besitzer → Betreiber-Fallback).

Ausschlaggebend ist die **Rechnungsadresse** des Kunden (sein rechtlicher Sitz = wer ihn beliefert/
fakturiert); die **Steuer** richtet sich getrennt nach der **Lieferadresse** (Stripe Tax). Siehe
ADR 006.
"""

# ─── Weltregionen (fix, partitionieren die Welt) ─────────────────────────────────
# ``pos`` = grobe Kachel-Position (Spalte, Zeile) für die abstrakte Weltkarte im Frontend –
# links→rechts, oben→unten, sodass die Kacheln grob wie eine Weltkarte liegen.
REGIONS: tuple[dict, ...] = (
    {"code": "NAM", "label": "Nordamerika", "pos": [0, 0]},
    {"code": "EUR", "label": "Europa", "pos": [1, 0]},
    {"code": "ASIA", "label": "Asien", "pos": [2, 0]},
    {"code": "LATAM", "label": "Lateinamerika", "pos": [0, 1]},
    {"code": "AFR", "label": "Afrika", "pos": [1, 1]},
    {"code": "MEA", "label": "Naher Osten", "pos": [1, 2]},
    {"code": "OCE", "label": "Ozeanien", "pos": [2, 1]},
)

REGION_CODES: tuple[str, ...] = tuple(r["code"] for r in REGIONS)


# ─── ISO-2-Land → Region ─────────────────────────────────────────────────────────
# Umfassend über die realistisch relevanten Märkte. Ein hier NICHT gelistetes Land ist kein
# Fehler: es fällt in ``company_for_country`` auf den **Betreiber** zurück (sicherer Default,
# Totalität bleibt gewahrt). Transkontinentale Länder sind kaufmännisch zugeordnet
# (z. B. Türkei/Kaukasus → Naher Osten, Russland → Europa).

_BY_REGION: dict[str, tuple[str, ...]] = {
    "NAM": ("US", "CA"),
    "LATAM": (
        "MX", "GT", "BZ", "SV", "HN", "NI", "CR", "PA", "CO", "VE", "EC", "PE", "BO", "CL",
        "AR", "UY", "PY", "BR", "GY", "SR", "GF", "CU", "DO", "HT", "JM", "TT", "BS", "BB",
        "PR", "AG", "DM", "GD", "KN", "LC", "VC", "AI", "AW", "KY", "BM", "CW", "SX", "TC",
        "VG", "VI", "GP", "MQ", "BQ",
    ),
    "EUR": (
        "AL", "AD", "AT", "BA", "BE", "BG", "BY", "CH", "CY", "CZ", "DE", "DK", "EE", "ES",
        "FI", "FO", "FR", "GB", "GI", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU",
        "LV", "MC", "MD", "ME", "MK", "MT", "NL", "NO", "PL", "PT", "RO", "RS", "RU", "SE",
        "SI", "SK", "SM", "UA", "VA", "XK", "GG", "JE", "IM", "AX",
    ),
    "MEA": ("AE", "BH", "IQ", "IR", "IL", "JO", "KW", "LB", "OM", "PS", "QA", "SA", "SY",
            "TR", "YE", "AM", "AZ", "GE"),
    "AFR": (
        "DZ", "AO", "BJ", "BW", "BF", "BI", "CM", "CV", "CF", "TD", "KM", "CG", "CD", "CI",
        "DJ", "EG", "GQ", "ER", "SZ", "ET", "GA", "GM", "GH", "GN", "GW", "KE", "LS", "LR",
        "LY", "MG", "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW", "ST", "SN",
        "SC", "SL", "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG", "ZM", "ZW",
    ),
    "ASIA": (
        "AF", "BD", "BT", "BN", "KH", "CN", "HK", "IN", "ID", "JP", "KZ", "KG", "LA", "MO",
        "MY", "MV", "MN", "MM", "NP", "KP", "KR", "PK", "PH", "SG", "LK", "TW", "TJ", "TH",
        "TM", "UZ", "VN",
    ),
    "OCE": ("AU", "NZ", "FJ", "PG", "SB", "VU", "WS", "TO", "KI", "FM", "MH", "NR", "PW",
            "TV", "NC", "PF", "GU", "AS", "CK", "NU", "TK"),
}

COUNTRY_REGION: dict[str, str] = {
    cc: region for region, countries in _BY_REGION.items() for cc in countries
}



def region_of_country(country: str | None) -> str | None:
    """Region eines ISO-2-Ländercodes (Grossschreibung egal). ``None`` für unbekannte/leere
    Länder – der Aufrufer (``sites.company_for_country``) behandelt das als Betreiber-Fallback."""
    if not country:
        return None
    return COUNTRY_REGION.get(country.strip().upper())


# ─── Gebiet = Region ODER einzelnes Land (Ausnahme) ──────────────────────────────
# Ein **Gebietsanspruch** (``company_territories``) trägt entweder einen Regions-Code
# («EUR») oder – als **Ausnahme** – einen ISO-2-Ländercode («LI»). Beides in EINER Spalte,
# weil es fachlich EINE Sache ist: «dieses Gebiet fakturiert Gesellschaft X». Der
# Unterschied wird **abgeleitet, nicht gespeichert** – ISO-2 hat exakt 2 Zeichen, jeder
# Regions-Code mindestens 3 (NAM/EUR/ASIA/…), eine Kollision ist also unmöglich.
# Vorrang bei der Auflösung: **Land ≻ Region ≻ Betreiber** (``sites.company_for_country``).

def is_country_code(area: str | None) -> bool:
    """Ist dieser Gebiets-Code ein **Land** (ISO-2) statt einer Region? Rein aus der Form
    abgeleitet – siehe oben."""
    return len((area or "").strip()) == 2


def normalize_area(area: str | None) -> str | None:
    """Gebiets-Code normalisieren (Grossschreibung) und prüfen: bekannte Region ODER
    bekanntes Land. ``None``, wenn beides nicht zutrifft (der Aufrufer wirft dann 400) –
    so kann kein Anspruch auf ein Gebiet entstehen, das es gar nicht gibt."""
    code = (area or "").strip().upper()
    if code in REGION_CODES:
        return code
    if is_country_code(code) and code in COUNTRY_REGION:
        return code
    return None
