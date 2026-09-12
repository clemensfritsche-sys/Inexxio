"""**Incoterms 2020** – wer trägt Kosten und Risiko, und bis wohin.

►►► **Warum ein Katalog und kein Freitext.** ◄◄◄ Dieselbe Begründung wie bei Währung und
Steuersatz: «FOB» getippt ist noch keine Vereinbarung, und ein Tippfehler fällt erst auf,
wenn ein Container im Hafen steht. Die elf Klauseln sind die vollständige Liste der ICC;
eine zwölfte gibt es nicht, und eine eigene Abkürzung wäre keine Klausel, sondern eine
Behauptung.

►►► **Und warum jede eine Erklärung trägt.** ◄◄◄ Genau hier entstehen die Fragen – es ist
die Stelle im ganzen Beleg, an der ein Kürzel über Tausende Franken entscheidet. Die
Erklärung steht darum **am Katalog**, nicht in der Oberfläche: sie ist eine Eigenschaft
der Klausel, und die Karte soll sie nicht zum zweiten Mal formulieren.

**Der benannte Ort ist Pflicht**, sobald eine Klausel gewählt ist: «FCA» allein ist keine
Vereinbarung, «FCA Rorschach» ist eine. Das ist keine Formalie – bei ``FCA`` entscheidet
genau dieser Ort, wo das Risiko übergeht.

*Die vier See-Klauseln tragen ihren Hinweis im Text: sie für Luftfracht oder einen Camion
zu wählen ist der häufigste Fehler überhaupt, und er fällt erst im Schadensfall auf.*
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

#: Wie das Feld heisst (Testnotiz #947). **Die Jahreszahl steht nicht dabei**: eine
#: Beschriftung sagt, worum es geht – die Fassung steht in der Erklärung der gewählten
#: Klausel, und die steht auf dem Beleg sichtbar darunter.
LABEL = "Lieferbedingung"
#: Was neben der Klausel steht. **Ohne ihn ist sie keine Vereinbarung.**
PLACE_LABEL = "Benannter Ort"
PLACE_HINT = "Der Ort, auf den sich die Klausel bezieht – z. B. «Rorschach»."


def of(key: Optional[str]) -> Optional[Incoterm]:
    """Die Klausel zu einem Kürzel – ``None``, wenn es keine ist.

    **Tolerant beim Lesen**: ein eingefrorener Vorgang kann eine Klausel tragen, die eine
    spätere Fassung nicht mehr führt, und eine Anzeige darf daran nicht zerbrechen.
    """
    return _BY_KEY.get((key or "").strip().upper()) if key else None


def assert_incoterm(value: Any) -> Optional[str]:
    """Die Schreibprüfung. **Leer ist erlaubt** – nicht jedes Geschäft hat eine Klausel.

    Ein unbekanntes Kürzel ist ein **Fehler mit Liste**, kein stilles Verwerfen: wer
    «DAT» schickt (die Klausel von 2010, die es 2020 nicht mehr gibt), soll das lesen.
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
    """**Wie die Vereinbarung auf dem Beleg steht** – «FCA Rorschach (Incoterms 2020)».

    Eine Stelle, an der sie gebaut wird; im Browser zusammengesetzt wäre sie die zweite
    Schreibweise, und die beiden lauteten beim nächsten Feld verschieden.
    """
    term = of(key)
    if term is None:
        return None
    return " ".join(x for x in (term.key, (place or "").strip()) if x) + " (Incoterms 2020)"
