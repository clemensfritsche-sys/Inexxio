"""Katalog der Artikel-Stammdaten, die einem Lieferanten freigegeben werden können.

Pflichtfelder (``mandatory``) sind IMMER für den Lieferanten sichtbar und können
nicht abgewählt werden. Weitere (optionale) Felder lassen sich pro Beschaffungs-
Schritt per Tag-Auswahl freigeben. Wächst das Artikel-Stammdatenmodell, hier
ergänzen – die Auswahl-UI und die Lieferantensicht ziehen automatisch nach.
"""

# Reihenfolge = Anzeige-Reihenfolge. (key, label, mandatory)
SUPPLIER_FIELD_CATALOG = [
    ("name", "Bezeichnung", True),
    ("unit", "Einheit", True),
    ("serialization", "Serialisierung", True),
    ("size", "Grösse (mm)", True),
    ("weight_kg", "Gewicht (kg)", True),
    ("supplier_article_number", "Lief.-Artikelnummer", False),
]

ALL_FIELD_KEYS = [k for k, _, _ in SUPPLIER_FIELD_CATALOG]
MANDATORY_FIELD_KEYS = [k for k, _, m in SUPPLIER_FIELD_CATALOG if m]


def normalize_shared_fields(values: list | None) -> list[str]:
    """Auswahl bereinigen: unbekannte Keys verwerfen, Pflichtfelder erzwingen,
    Katalog-Reihenfolge herstellen."""
    selected = set(values or [])
    selected |= set(MANDATORY_FIELD_KEYS)
    return [k for k in ALL_FIELD_KEYS if k in selected]
