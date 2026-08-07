"""**Die geschlossene Liste der Prozessschrittmodule — die eine Stelle.**

Ein Modul ist kein Freitext: sein Schlüssel steht hier, sein Übergang steht hier, und was
in seiner ``config`` stehen darf, entscheidet ebenfalls diese Datei. Ein Modultyp, den es
hier nicht gibt, ist nicht anlegbar — der Fehler kommt beim **Anlegen**, nicht erst, wenn
zur Laufzeit niemand weiss, was zu tun wäre.

**Der Übergang gehört zum Modul, nicht zum Anwender** (Vorgabe: «fest verdrahtet, nicht
einstellbar»). Ein Datenerfassungs-Modul *misst* – es verändert den Zustand des Stücks
nicht. Es wäre darum falsch, beim Anlegen zwei Status-Auswahlen anzubieten: die einzige
richtige Antwort stünde schon fest, und jede andere wäre ein Prozess, der nicht läuft.
Die Spalten ``status_before``/``status_after`` bleiben (sie sind der Mechanismus, §4) —
sie werden nur nicht mehr **gefragt**, sondern von hier gefüllt.

Das Testmodul ist **ersatzlos entfallen**. Es war ein Testvehikel für den Mechanismus;
den gibt es jetzt echt.
"""

from typing import Any, Optional

from fastapi import HTTPException

from . import capture_types, statuses as st

DATENERFASSUNG = "datenerfassung"


class Module:
    """Ein Modultyp. Was ihn ausmacht: sein Übergang und die Form seiner Konfiguration."""

    def __init__(self, key: str, label: str, status_before: str, status_after: str,
                 tone: str):
        self.key = key
        self.label = label
        self.status_before = status_before
        self.status_after = status_after
        #: **Die Farbfamilie dieses Modultyps** – ein Wort, das das Frontend auf seine
        #: Tokens abbildet (``lib/modules.MODULE_TONE``). Sie steht hier, weil sie zum
        #: Modul gehört und nicht zu einer Komponente: ein neuer Modultyp ist damit ein
        #: Eintrag in dieser Liste, kein Eingriff in die Oberfläche.
        #:
        #: **Getrennt von der Ampel** (grün/orange/rot): ein Modul ist kein Zustand und
        #: darf nicht wie einer aussehen (PROCESS_CORE.md §5.3).
        self.tone = tone

    def clean_config(self, raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Die Konfiguration prüfen und normalisieren. Ohne Konfiguration: ``None``."""
        return None


class Datenerfassung(Module):
    """Im Prozess laufend Daten erfassen und kontrollieren (Richtung Qualitätssicherung).

    **Durchläufer**: Vorher wie Nachher ``Im Prozess``. Es hält fest, was gemessen wurde,
    und rückt das Stück vor. Was aus einem «nicht bestanden» folgt, ist bewusst noch nicht
    entschieden (PROCESS_CORE.md §12.5) – bis dahin ist das Ergebnis eine **Aussage über
    die Messung**, kein Ereignis im Prozess. Ein erfundener Abzweig wäre schlimmer als
    keiner.
    """

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        return {"points": capture_types.clean_points((raw or {}).get("points"))}


MODULES: dict[str, Module] = {
    m.key: m for m in (
        Datenerfassung(
            key=DATENERFASSUNG,
            label="Datenerfassung",
            status_before=st.IM_PROZESS,
            status_after=st.IM_PROZESS,
            tone="slate",
        ),
    )
}

KEYS: tuple[str, ...] = tuple(MODULES)
LABELS: dict[str, str] = {k: m.label for k, m in MODULES.items()}
TONES: dict[str, str] = {k: m.tone for k, m in MODULES.items()}


def get(module_type: Any) -> Module:
    """Modul zu einem Schlüssel. Unbekannt = harter Fehler, kein Rückfall."""
    found = MODULES.get(module_type)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"«{module_type}» ist kein Prozessschrittmodul. Erlaubt: "
                + ", ".join(f"{m.label} ({m.key})" for m in MODULES.values()) + "."
            ),
        )
    return found


def points_of(config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Erfassungspunkte einer gespeicherten Definition — die eine Lesestelle."""
    return list((config or {}).get("points") or [])
