"""**Der Beleg — die Vokabel eines Handelsvorgangs, und er gehört keinem Modul.**

Ein Beleg hat drei Stufen und einen Ausgang. Das ist eine Aussage über den **Vorgang**,
nicht über den Modultyp, der ihn ausgelöst hat — und genau darum steht sie hier statt an
einer Modul-Klasse.

**Warum das mehr ist als eine Verschiebung.** Im Datenmodell hing der Beleg nie am Modul:
``purchases`` trägt eine ``step_id`` und keinen Modultyp, ``_can`` liest Stufe × Rolle,
``assert_receivable``/``note_receipt`` fragen nur, ob es zu diesem Schritt einen Beleg
gibt. Es waren genau **zwei Fäden**, die ihn an «Beschaffen» banden: er las dessen
``suppliers`` und dessen ``instruction``. Sind die gekappt (``Module.parties_of`` /
``Module.instruction_for``), trägt **jedes** Modul denselben Beleg — dieselben Stufen,
dieselben Verben, dieselbe Oberfläche.

Das ist die Grundlage dafür, dass eine **Sendung** kein zweites Konzept braucht: eine
Spedition zu beauftragen IST ein Einkauf, ein Tarifvergleich IST der Angebotsspiegel, und
die Sendungsnummer ist das ``tracking``-Feld, das es längst gibt (§9.8/§9.9).

## Und derselbe Beleg trägt den VERKAUF — nur in die andere Richtung

Einkauf und Verkauf sind **dasselbe** Geschäft aus zwei Blickwinkeln: jemand fragt, jemand
nennt einen Preis, jemand sagt zu, jemand erfüllt. Drei Stufen, eine Schwelle, ein Storno –
Wort für Wort dieselbe Maschine. Verschieden sind nur die **Wörter**, die **Gegenpartei**
und die Hand, die den Preis einträgt.

Genau darum steht die Richtung hier als **Daten** (``Flow``) und nicht als Verzweigung im
Dienst: ein ``if direction ==`` wäre die Stelle, an der die beiden auseinanderlaufen –
zuerst in einer Beschriftung, dann in einer Regel.

**Drei Stufen, weil drei Dinge unumkehrbar sind** — nichts zugesagt · zugesagt · erfüllt.
«Preis steht» ist keine vierte: das ist der *Inhalt* der ersten Stufe. Und die **Zahlung**
ist auch keine: sie ändert am Material nichts, sie ist reversibel (Teilzahlung, Mahnung,
Erstattung), und sie steht als eigene Zeile am Beleg (``services/payments``).
"""

from dataclasses import dataclass
from typing import Any, Optional

#: ►►► **Die Stufen — neutral, weil sie in beide Richtungen gelten.** ◄◄◄
#:
#: Sie hiessen einmal ``anfrage``/``bestellung``/``wareneingang``. Das beschrieb den
#: Einkauf und wäre am Verkaufs-Beleg schlicht falsch gewesen: ein Wareneingang, bei dem
#: Ware das Haus verlässt, ist kein Name, sondern ein Irrtum mit Bestand. Wie sie in einer
#: Richtung **heissen**, sagt der ``Flow``.
STAGES: tuple[str, ...] = ("offer", "commitment", "fulfilment")

#: Der Ausgang. **Keine Stufe** – man kommt dort an, statt hindurchzugehen; die gegangene
#: Kette bleibt dabei stehen, wo sie stand (ein Storno macht die Zusage nicht ungeschehen,
#: er sagt nur, dass nichts mehr kommt).
CANCELLED = "cancelled"

#: **Ab hier ist eine zweite Partei gebunden.** Vor dieser Stufe darf das System die
#: Grundlage still nachziehen; ab ihr liegt eine Bestellung beim Lieferanten bzw. eine
#: Zusage beim Kunden, und eine stille Änderung wäre ein Beleg, der nicht mehr stimmt.
BINDING = "commitment"

#: **Die alten Werte bleiben lesbar.** Migration 122 schreibt sie um; diese Zuordnung ist
#: das zweite Netz – ein Beleg aus einer Datenbank, die die Migration nicht gesehen hat,
#: wird verstanden statt mit einem ``KeyError`` quittiert. Streng schreiben, tolerant lesen.
_ALIASES: dict[str, str] = {
    "anfrage": STAGES[0],
    "bestellung": STAGES[1],
    "wareneingang": STAGES[2],
    "storniert": CANCELLED,
}

#: Die beiden Richtungen. **Kaufen** heisst: es kommt herein und wir zahlen; **verkaufen**:
#: es geht hinaus und wir werden bezahlt.
BUY, SELL = "buy", "sell"

#: **Die Zustände einer Angebotszeile.** ``gewaehlt`` entsteht nicht durch Tippen, sondern
#: dadurch, dass bei dieser Zeile zugesagt wurde – ein Zustand ist eine Folge.
#:
#: Sie stehen hier und nicht im Dienst, weil sie den **Beleg** beschreiben: die
#: Zahlungsfrist der gewählten Zeile (``payments.payment_days``) muss dieselbe Vokabel
#: lesen, und ein zweites Literal dort wäre die Stelle, an der beide auseinanderlaufen.
ASKED, QUOTED, DECLINED, CHOSEN = "angefragt", "offeriert", "abgelehnt", "gewaehlt"


@dataclass(frozen=True)
class Flow:
    """**Ein Beleg in EINER Richtung** – alles, was den Einkauf vom Verkauf unterscheidet.

    Und das ist erstaunlich wenig: Wörter, die Gegenpartei und die Frage, ob die Summe
    unser **Einstandspreis** ist. Die Stufen, die Schwelle, der Storno, das Tor (``_can``)
    und die ganze Ausführung sind dieselben.

    Es steht als **Daten** da und nicht als Verzweigung, weil eine Verzweigung sich
    vermehrt: die erste ist eine Beschriftung, die zweite eine Regel, und ab der dritten
    gibt es zwei Belege, die nur noch so tun, als wären sie einer.
    """

    direction: str
    #: Wie der Vorgang heisst und wie er aussieht – die Identität, die mit dem Beleg reist
    #: (``PurchaseEmbed.label``/``tone``). Die Ausführungsstelle schlägt sie nicht in einem
    #: Katalog nach, den nur der Editor lädt.
    label: str
    #: Die Farbfamilie ist ein **Name**, kein Wert: welcher Ton dahintersteht, entscheidet
    #: die Oberfläche (``lib/modules.MODULE_TONE``).
    tone: str
    #: **Wer die Gegenpartei ist** – die Rolle, die ein Benutzer tragen muss, damit man
    #: bei ihm bestellen bzw. ihm verkaufen kann. Sie steht hier und nicht als ``if`` im
    #: Dienst; die Auswahlliste (``/orders/party-options``) fragt dieselbe Angabe, damit
    #: sie nicht etwas anbietet, das der Dienst danach abweist.
    party_role: str
    #: Wie sie im Satz heisst («Lieferant 100000001 ist nicht zugelassen»).
    party_word: str
    #: Die drei Stufen, wie sie in dieser Richtung heissen.
    stage_labels: dict[str, str]
    #: **Was man an der AKTIVEN Stufe tut, um sie zu verlassen** – das Wort auf dem Knopf.
    #: Getrennt von der Beschriftung, weil der Zustand daneben steht: «Bestellen» ↔
    #: «Bestellt» (Testnotiz #596). Die letzte Stufe trägt keines: dort ist man angekommen.
    stage_verbs: dict[str, str]
    #: Wie «zurück» heisst – vor der Schwelle und ab ihr. Das Wort gehört neben die
    #: Wirkung, nicht in die Oberfläche: sonst stünde beim nächsten Fall ein Satz da, den
    #: keine Regel deckt.
    undo_before: str
    undo_after: str

    def label_of(self, stage: str) -> str:
        """Wie diese Stufe heisst. Der Ausgang gehört zu beiden Richtungen gleich."""
        if stage == CANCELLED:
            return "Storniert"
        return self.stage_labels.get(stage, stage)


#: ►►► **Die eine Liste.** Ein dritter Vorgang wäre ein Eintrag, kein Umbau. ◄◄◄
FLOWS: dict[str, Flow] = {
    BUY: Flow(
        direction=BUY,
        label="Beschaffen",
        tone="plum",
        party_role="supplier",
        party_word="Lieferant",
        stage_labels={STAGES[0]: "Anfrage", STAGES[1]: "Bestellung",
                      STAGES[2]: "Wareneingang"},
        stage_verbs={STAGES[0]: "Bestellen", STAGES[1]: "Wareneingang buchen"},
        undo_before="Anfrage zurückziehen",
        undo_after="Bestellung stornieren",
    ),
    SELL: Flow(
        direction=SELL,
        label="Verkauf",
        # Ein eigener Ton, denn Einkauf und Verkauf stehen im **selben** Prozess
        # nebeneinander (Rohteil kaufen → bearbeiten → verkaufen); teilten sie sich eine
        # Farbe, wäre im Fluss nicht zu sehen, in welche Richtung ein Modul zeigt.
        tone="teal",
        party_role="customer",
        party_word="Kunde",
        # **«Zusage» statt «Auftragsbestätigung».** Beides meint dasselbe, aber «Auftrag»
        # ist im System bereits vergeben – für den Datensatz, in dem dieses Modul steckt.
        stage_labels={STAGES[0]: "Angebot", STAGES[1]: "Zusage", STAGES[2]: "Geliefert"},
        stage_verbs={STAGES[0]: "Zusage erfassen", STAGES[1]: "Lieferung buchen"},
        undo_before="Angebot zurückziehen",
        undo_after="Zusage stornieren",
    ),
}

#: Die Vorgabe. Ein Beleg ohne ausdrückliche Richtung ist ein Einkauf – das ist, was jeder
#: bestehende ist, und damit ändert die neue Spalte an keinem von ihnen etwas.
DEFAULT_DIRECTION = BUY


def of(direction: Optional[str]) -> Flow:
    """Der Vorgang zu einer Richtung. Unbekannt → der Einkauf, **nicht** ein Fehler.

    Hier wird gelesen, nicht geschrieben: ein Wert, den es nicht geben dürfte, darf keine
    Auftrags-Anzeige zerlegen. Geschrieben wird ausschliesslich über ``assert_direction``,
    und die weist ab.
    """
    return FLOWS.get(direction or "", FLOWS[DEFAULT_DIRECTION])


def normalize(stage: Optional[str]) -> str:
    """Eine Stufe, wie sie heute heisst – aus jeder Fassung, in der sie gespeichert war."""
    value = stage or STAGES[0]
    return _ALIASES.get(value, value)


def assert_direction(direction: Any) -> str:
    """Die Schreibprüfung. Ohne sie wäre ``of`` eine stille Umgehung der Liste."""
    if direction in FLOWS:
        return str(direction)
    raise ValueError(
        f"«{direction}» ist keine Beleg-Richtung. Erlaubt: " + ", ".join(FLOWS) + "."
    )
