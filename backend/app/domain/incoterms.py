"""**Incoterms 2020** – wer trägt Kosten und Risiko, und bis wohin.

►►► **Ein Katalog, kein Freitext** ◄◄◄ – die elf Klauseln der ICC, jede mit ihrer Erklärung
(am Katalog, nicht in der Oberfläche).

**Der benannte Ort ist Pflicht**, sobald eine Klausel gewählt ist («FCA Rorschach»).
Die vier See-Klauseln nennen ihre Einschränkung im Text.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Incoterm:
    """Eine Klausel – Kürzel, Name und der eine Satz, der sie erklärt."""

    key: str
    label: str
    #: **Was sie bedeutet, in einem Satz** – für den, der sie zum ersten Mal sieht.
    hint: str


#: **Alle elf Klauseln der Incoterms 2020**, in der Reihenfolge der ICC: zuerst die sieben
#: für **jede** Transportart, dann die vier nur für See- und Binnenschiff.
INCOTERMS: tuple[Incoterm, ...] = (
    Incoterm("EXW", "Ab Werk",
             "Der Käufer holt ab. Ab unserer Rampe trägt er Kosten und Risiko."),
    Incoterm("FCA", "Frei Frachtführer",
             "Wir übergeben dem Transporteur des Käufers. Ab der Übergabe trägt er "
             "Kosten und Risiko."),
    Incoterm("CPT", "Frachtfrei",
             "Wir zahlen den Transport bis zum Zielort – das Risiko geht aber schon bei "
             "der Übergabe an den ersten Frachtführer über."),
    Incoterm("CIP", "Frachtfrei versichert",
             "Wie CPT, und wir zahlen zusätzlich die Transportversicherung."),
    Incoterm("DAP", "Geliefert benannter Ort",
             "Wir liefern bis zum Ort. Abgeladen wird vom Käufer, den Einfuhrzoll zahlt "
             "er."),
    Incoterm("DPU", "Geliefert entladen",
             "Wie DAP, und wir laden zusätzlich ab."),
    Incoterm("DDP", "Geliefert verzollt",
             "Wir tragen alles bis zur Tür – inklusive Einfuhrzoll und Einfuhrsteuer."),
    Incoterm("FAS", "Frei Längsseite Schiff",
             "Nur See-/Binnenschiff. Wir stellen die Ware am Kai neben das Schiff."),
    Incoterm("FOB", "Frei an Bord",
             "Nur See-/Binnenschiff. Wir bringen die Ware an Bord; ab da trägt der "
             "Käufer."),
    Incoterm("CFR", "Kosten und Fracht",
             "Nur See-/Binnenschiff. Wir zahlen die Seefracht bis zum Zielhafen – das "
             "Risiko geht an Bord über."),
    Incoterm("CIF", "Kosten, Versicherung, Fracht",
             "Wie CFR, zusätzlich mit Versicherung."),
)

_BY_KEY: dict[str, Incoterm] = {t.key: t for t in INCOTERMS}

#: Wie das Feld heisst – ohne Jahreszahl (die Fassung steht in der Erklärung der Klausel).
LABEL = "Lieferbedingung"
#: Was neben der Klausel steht. **Ohne ihn ist sie keine Vereinbarung.**
PLACE_LABEL = "Benannter Ort"

#: ►►► **Der Ort ist kein Feld – die Klausel sagt, woher er kommt.** ◄◄◄ Bei den E- und
#: F-Klauseln geht das Risiko beim **Leistungserbringer** über (seine Versandadresse), bei
#: den C- und D-Klauseln am **Ziel** (die Lieferadresse).
AT_OURS: frozenset[str] = frozenset({"EXW", "FCA", "FAS", "FOB"})


def place_at_ours(key: Optional[str]) -> bool:
    """Liegt der benannte Ort dieser Klausel **beim Leistungserbringer** (E/F) – sonst am
    Ziel (C/D)."""
    term = of(key)
    return term is not None and term.key in AT_OURS


def of(key: Optional[str]) -> Optional[Incoterm]:
    """Die Klausel zu einem Kürzel – ``None``, wenn es keine ist.

    **Tolerant beim Lesen** (eingefrorene Vorgänge).
    """
    return _BY_KEY.get((key or "").strip().upper()) if key else None


def assert_incoterm(value: Any) -> Optional[str]:
    """Die Schreibprüfung. **Leer ist erlaubt** – nicht jedes Geschäft hat eine Klausel.

    Ein unbekanntes Kürzel ist ein **Fehler mit Liste**, kein stilles Verwerfen.
    """
    if value in (None, ""):
        return None
    term = of(str(value))
    if term is None:
        raise ValueError(
            f"«{value}» ist keine Incoterms-2020-Klausel. Erlaubt: "
            + ", ".join(t.key for t in INCOTERMS) + "."
        )
    return term.key


def sentence(key: Optional[str], place: Optional[str]) -> Optional[str]:
    """**Wie die Vereinbarung auf dem Beleg steht** – «FCA Rorschach».

    Die eine Stelle, an der sie gebaut wird; **ohne Jahreszahl** (die Fassung steht einmal
    in der Erklärung der Klausel).
    """
    term = of(key)
    if term is None:
        return None
    return " ".join(x for x in (term.key, (place or "").strip()) if x)
