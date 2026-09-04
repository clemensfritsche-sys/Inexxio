"""**Der Geldvorgang — eine Richtung, drei Stufen, zwei Arten von Zeile.**

Dieses Modul ist der Fachkern des Prozessschrittmoduls «Zahlung» (``domain/modules.
Zahlung``). Es steht **vollständig für sich**: keine Datenbank, kein Dienst – und
ausdrücklich **kein Import** aus ``domain/procurement`` oder ``domain/money``. Wer die
Module «Beschaffen» und «Verkauf» eines Tages ersatzlos löscht, muss hier keine Zeile
anfassen.

## Warum es das gibt

Einkauf und Verkauf waren zwei Module, und daneben standen Fälle, die in keines von
beiden passten: eine Spedition, die man beauftragt (ein Einkauf **im** Bewegen-Modul),
eine Leistung ohne Artikel, eine Vorauszahlung. Jeder dieser Fälle bekam ein eigenes
Stück Mechanik, und die Mechanik wuchs schneller als die Fälle.

Der kleinste gemeinsame Nenner ist **nicht** «Ware», sondern **Geld mit einer zweiten
Partei**. Ein Vorgang hat genau eine Richtung – es kommt herein oder es geht hinaus –,
und alles Weitere ist in beiden Richtungen dieselbe Maschine: jemand nennt einen Preis,
beide sagen zu, es wird gefordert, es wird gezahlt.

## Die eine Regel, die es robust macht

**Dieses Modul bewegt keine Stücke.** Es misst nicht, es sondert nicht aus, es verbaut
nicht, es bewegt nicht, und es ändert keinen Zustand: die Einzelinstanzen stehen davor,
warten und laufen danach unverändert weiter (``Im Prozess`` → ``Im Prozess``).

Daraus folgt die Robustheit ohne eine einzige Prüfung: **keine andere Regel im System
muss von diesem Modul wissen.** Es gibt keinen neuen Status, keinen Ausgang, keine
Kettenregel, keinen Ortswechsel und keine Zeile in der Prozess-Engine. Was mit den
Stücken *physisch* geschieht, sagen die Module davor und danach – kommissioniert wird
mit «Bewegen», ausgeliefert mit «Bewegen», ausgesondert mit «Aussondern».

Wer diesem Modul einen Statuswechsel gäbe, hätte in drei Wochen wieder die Fragen, aus
denen es entstanden ist.

## Drei Achsen, keine Reihenfolge

**Ware · Forderung · Geld** sind unabhängig, und jedes Szenario ist eine andere *Folge*
derselben Grundhandlungen:

=============================  ==========================================
Szenario                       Folge
=============================  ==========================================
Rechnung mit Zahlungsziel      zusagen → abschliessen → fordern → zahlen
Vorauszahlung                  zusagen → fordern → zahlen → abschliessen
Anzahlung + Schlussrechnung    zusagen → fordern → zahlen → … → fordern
Gutschrift / Kulanz            negative Forderung, ohne Ware
Erstattung                     negative Zahlung, auch nach dem Storno
=============================  ==========================================

Für **keines** davon gibt es hier einen Modus. Der einzige Schalter ist ``prepaid``, und
der schreibt keine Reihenfolge vor – er verhindert nur, dass das Modul abgeschlossen
wird, solange nicht bezahlt ist.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from . import currency as cur

# ---------------------------------------------------------------------------
# ►►► DIE RICHTUNG — das eine Feld, aus dem alles Übrige folgt ◄◄◄
# ---------------------------------------------------------------------------

#: **Geld kommt herein** – wir stellen Rechnung, die Gegenpartei ist ein Kunde.
IN = "in"
#: **Geld geht hinaus** – wir bekommen Rechnung, die Gegenpartei ist ein Lieferant.
OUT = "out"

# ---------------------------------------------------------------------------
# ►►► DIE STUFEN — ZWEI, weil zwei Dinge unumkehrbar sind ◄◄◄
# ---------------------------------------------------------------------------
#
# **nichts zugesagt · zugesagt.** Das ist die ganze Verpflichtungskette; alles andere ist
# eine Folge davon.
#
# ``DONE`` und ``CANCELLED`` sind **Ausgänge, keine Stufen** – man kommt dort an, statt
# hindurchzugehen. «Abgeschlossen» stand einmal als dritte Stufe da und war genau das
# Missverständnis: ein **Zustand** in einer Reihe von **Schritten**.
#
# Und die dritte Zeile in der Karte ist das **Geld** – aber es ist keine Stufe: eine
# Zahlung macht aus einem Angebot keine Zusage, sie ist reversibel (Teilzahlung,
# Erstattung), und sie darf **vor** der Erfüllung stehen (Vorauszahlung) wie danach
# (Zahlungsziel). Wer sie als dritte Stufe führte, hätte für die Vorauszahlung ein ``if``.

OFFER = "offer"
AGREED = "agreed"
DONE = "done"
CANCELLED = "cancelled"

STAGES: tuple[str, ...] = (OFFER, AGREED)

# ---------------------------------------------------------------------------
# ►►► DIE ANGEBOTSZEILEN — der Vorgang hat ZWEI Parteien ◄◄◄
# ---------------------------------------------------------------------------
#
# Ein Geldvorgang ist kein Formular, das eine Seite ausfüllt: jemand fragt, der andere
# nennt einen Preis, einer sagt zu. Je zugelassener Gegenpartei eine Zeile.
#
# ``gewaehlt`` entsteht **nicht durch Tippen**, sondern dadurch, dass bei dieser Zeile
# zugesagt wurde – ein Zustand ist eine Folge.
ASKED, QUOTED, DECLINED, CHOSEN = "angefragt", "offeriert", "abgelehnt", "gewaehlt"

QUOTE_STATES: tuple[str, ...] = (ASKED, QUOTED, DECLINED, CHOSEN)

#: **Ab hier ist eine zweite Partei gebunden.** Davor darf man frei ändern; ab hier ist
#: eine Änderung ein Storno – draussen liegt eine Zusage, die jemand gelesen hat.
BINDING = AGREED

# ---------------------------------------------------------------------------
# ►►► DIE ZEILEN — zwei Arten, ein Vorzeichen ◄◄◄
# ---------------------------------------------------------------------------
#
# ``CHARGE``   die **Forderung** (Rechnung). Negativ = Gutschrift.
# ``PAYMENT``  das **Geld**. Negativ = Erstattung.
#
# Zwei Arten und nicht zwei Tabellen: beide sind «eine Zeile Geld an diesem Vorgang»,
# beide tragen Betrag, Datum, Referenz. Und zwei Arten und nicht eine: ohne die
# Unterscheidung liesse sich «wie viel hat er wirklich gezahlt» nicht mehr beantworten,
# und eine Gutschrift sähe aus wie eine offene Rechnung.

CHARGE = "charge"
PAYMENT = "payment"

KINDS: tuple[str, ...] = (CHARGE, PAYMENT)

# ---------------------------------------------------------------------------
# ►►► WAS IN BEIDEN RICHTUNGEN GLEICH HEISST — Konstanten, keine Tabelle ◄◄◄
# ---------------------------------------------------------------------------
#
# «Kunde» ↔ «Lieferant» standen einmal als zwei Werte in ``Direction``, und jede
# Aufrufstelle musste sich die richtige holen. Es ist aber **dieselbe Rolle**: der andere
# im Geschäft. Ein Wort dafür ist nicht nur kürzer, es nimmt eine ganze Klasse von Fehlern
# weg – die Wahl des falschen Wortes gibt es dann gar nicht mehr.
#
# **Und Singular = Plural.** Damit ist das «Kundeen»-Problem (#787) *strukturell*
# erledigt statt durch einen zweiten gepflegten Wert: es gibt keine Beugung, die jemand
# rechnen könnte.

#: Der andere im Geschäft – in beiden Richtungen und in beiden Numeri.
PARTY = "Partner"

#: **Was man an der Schwelle tut**: das *Angebot* annehmen – der Auftrag ist das Ergebnis
#: (Testnotiz #826). «Auftrag bestätigen» benannte die Folge statt der Handlung.
AGREE_VERB = "Angebot annehmen"
#: ►►► **Was man tut, wenn nichts mehr davorsteht** (Testnotiz #848). ◄◄◄
#:
#: «Auftrag erledigt» meinte den falschen Auftrag: es klang nach dem ERP-Datensatz, gemeint
#: ist **dieses Modul**. Ein *Vorgang* ist genau dieser Geldvorgang – das Wort steht seit
#: jeher dafür im Haus, und es verwechselt sich mit nichts.
FINISH_VERB = "Vorgang abschliessen"
#: Die eine Gegenhandlung.
UNDO = "Auftrag stornieren"

#: ►►► **Die beiden Geld-Zeilen — in beiden Richtungen dasselbe Wort** (#828). ◄◄◄
#:
#: «Rechnung stellen» ↔ «Rechnung erfassen» und «Zahlungseingang» ↔ «Zahlung» waren vier
#: Wörter für zwei Handlungen. **Erfasst** wird beides, egal in welche Richtung es fliesst –
#: das System bucht eine Zeile, es überweist nichts. Zwei Wörter weniger, die auseinander
#: laufen können.
CHARGE_WORD = "Rechnung erfassen"
PAYMENT_WORD = "Zahlung erfassen"
#: Das Wort für den offenen Betrag – aus unserer Sicht in beiden Richtungen «Offen».
OPEN_WORD = "Offen"
#: Die Überschrift der dritten Zeile der Karte.
MONEY_LABEL = "Rechnung & Zahlung"

#: **Was bei ihm zu tun ist** – seine Artikelnummer, sein Shop-Link oder ein Satz.
#:
#: Eine Eigenschaft der **Paarung** Modul × Partner (derselbe Lieferant führt je Teil eine
#: andere Nummer), und sie gilt in **beiden** Richtungen: beim Einkauf sagt sie, wie man
#: bei ihm bestellt, beim Verkauf, was er bekommt. Ein Feld, das es nur auf einer Seite
#: gibt, wäre wieder eine Verzweigung – und der frühere Satz «Was ist daran zu tun?» am
#: Vorgang war ihre optionale Doppelung (Testnotiz #805).
TASK = "Was ist zu tun?"
TASK_HINT = "Artikelnummer, Link oder Beschreibung"

# ---------------------------------------------------------------------------
# ►►► WER DEN PREIS NENNT — der Urheber eines Angebots ◄◄◄
# ---------------------------------------------------------------------------
#
# Ein Angebot hat einen **Urheber**, und der ist in den beiden Richtungen ein anderer
# (Testnotiz #837):
#
# * **Ausgabe**: wir fragen an, **er** nennt den Preis, wir wählen aus.
# * **Einnahme**: **wir** nennen den Preis, er nimmt an oder lehnt ab.
#
# Das ist keine Formulierungsfrage, sondern eine andere **Abfolge**. Vorher schickte
# ``ask`` in beiden Richtungen eine leere Zeile hinaus – beim Verkauf sähe der Kunde ein
# Angebot ohne Preis, und wir müssten ihn danach nachtragen. Steht der Urheber als
# **Angabe** da, folgt daraus beides ohne eine Verzweigung: wer nennt, füllt **vor** dem
# Hinausgehen, und wer nicht nennt, darf den fremden Preis nicht ändern.

#: **Wir** nennen den Preis (Einnahme) – das Angebot geht mit dem Betrag hinaus.
BY_US = "us"
#: **Die Gegenpartei** nennt ihn (Ausgabe) – wir fragen an und warten auf die Offerte.
BY_PARTY = "party"

# ---------------------------------------------------------------------------
# ►►► DIE NUMMER EINER ZEILE — nur, wo sie von AUSSEN kommt ◄◄◄
# ---------------------------------------------------------------------------
#
# Eine Nummer, die **wir** vergeben, tippt niemand ab (Testnotiz #840): sie entsteht aus
# der Serie, lückenlos und ohne Doppelung. Ein Eingabefeld daneben ist die zweite Aussage
# über dieselbe Sache – und die getippte gewinnt, auch wenn sie falsch ist.
#
# Das Feld gibt es darum genau dort, wo die Nummer **von aussen** kommt: an einer
# Lieferantenrechnung (sie steht auf seinem Papier) und an jeder Zahlung (QR-Referenz,
# Zahlungszweck, die Id des Zahlungsdienstes).

#: ►►► **Die Nummer der Gegenpartei – EIN Feld für BEIDE Zeilen-Arten** (#840/#850). ◄◄◄
#:
#: Die Regel galt zuerst nur für die Rechnung, und an der Zahlung stand weiter ein Feld –
#: obwohl bei einer **Einnahme** auch die Zahlung unsere Nummer trägt (sie referenziert
#: unsere Rechnung). Zwei Regeln für dieselbe Frage laufen genau so auseinander.
#:
#: Jetzt gilt einer für beide: **wo wir nummerieren, tippt niemand**, und wo die
#: Gegenpartei nummeriert, ist es ihre Angabe – ihre Belegnummer, ihr Zahlungszweck.
PARTY_REFERENCE = "Beleg-/Zahlungsreferenz des Partners"


@dataclass(frozen=True)
class Direction:
    """**Ein Geldvorgang in EINER Richtung** – alles, was die beiden unterscheidet.

    Und das ist ausschliesslich **Sprache**: Wörter für die Stufen, für die Gegenpartei
    und für die beiden Geld-Zeilen. Stufen, Schwelle, Storno, Tor und Rechenweg sind in
    beiden Richtungen identisch.

    Es steht als **Daten** da und nicht als Verzweigung, weil eine Verzweigung sich
    vermehrt: die erste ist eine Beschriftung, die zweite eine Regel, und ab der dritten
    gibt es zwei Vorgänge, die nur noch so tun, als wären sie einer.
    """

    key: str
    #: Wie der Vorgang heisst – die Überschrift über dem Block («Einnahme» · «Ausgabe»).
    label: str
    #: Ein Satz, der sagt, was passiert. Er steht im Editor neben der Wahl.
    hint: str
    #: **Die beiden Stufen, wie sie in dieser Richtung heissen** – «Angebot» ↔ «Anfrage».
    #: Einer der vier echten Unterschiede: wer zuerst fragt, ist nicht derselbe.
    stage_labels: dict[str, str]
    #: **Wie man auf den Partner zugeht** – der eine Punkt, an dem die Richtung eine echte
    #: Handlung unterscheidet: bei einer Ausgabe fragt man an, bei einer Einnahme bietet
    #: man an.
    ask_verb: str
    #: ►►► **Wer den Preis nennt** – ``BY_US`` ↔ ``BY_PARTY`` (Testnotiz #837). ◄◄◄
    #:
    #: Daraus folgt die ganze Abfolge: wer nennt, füllt **vor** dem Hinausgehen (das
    #: Angebot geht mit dem Betrag hinaus), und wer nicht nennt, ändert den fremden Preis
    #: nicht – er nimmt an oder lehnt ab.
    quoted_by: str
    #: **Wie die Nummer einer Geld-Zeile entsteht.** ``None`` heisst «wir nummerieren» –
    #: dann gibt es **kein** Eingabefeld, weder an der Rechnung noch an der Zahlung
    #: (#840/#850). Sonst der Name des Feldes.
    reference: Optional[str]

    #: ►►► **Was man TUT, ist in beiden Richtungen dasselbe.** ◄◄◄
    #:
    #: Das Verb der Schwelle, das des Abschlusses, die Gegenhandlung, die beiden Geld-Wörter
    #: und die Überschrift lauteten in beiden Richtungen gleich – als Feld waren sie fünf
    #: Werte, die jemand einzeln hätte ändern können. Als Konstante sind sie eine Aussage.
    @property
    def stage_verbs(self) -> dict[str, str]:
        return {OFFER: AGREE_VERB, AGREED: FINISH_VERB}

    @property
    def undo(self) -> str:
        return UNDO

    @property
    def charge_word(self) -> str:
        return CHARGE_WORD

    @property
    def payment_word(self) -> str:
        return PAYMENT_WORD

    @property
    def open_word(self) -> str:
        return OPEN_WORD

    @property
    def money_label(self) -> str:
        return MONEY_LABEL

    @property
    def party_actions(self) -> tuple[str, ...]:
        """►►► **Was die GEGENPARTEI an diesem Vorgang darf.** ◄◄◄

        Es folgt aus ``quoted_by`` und ist keine zweite Angabe: **wer den Preis nennt,
        offeriert; wer ihn empfängt, nimmt an oder lehnt ab.** Bei einer Ausgabe darf sie
        darum ``quote``, bei einer Einnahme ``agree`` – unseren Preis zu überschreiben
        wäre dort keine Antwort, sondern eine Gegenofferte, und die ist ein neuer Vorgang.

        Absagen darf sie immer: das ist die eine Antwort, die in beide Richtungen dieselbe
        Bedeutung hat.
        """
        return (("quote", "decline") if self.quoted_by == BY_PARTY
                else ("agree", "decline"))

    def label_of(self, stage: str) -> str:
        """Wie diese Stufe heisst. Die beiden **Ausgänge** gehören beiden Richtungen
        gleich – sie sind keine Stufen, aber sie brauchen ein Wort."""
        if stage == CANCELLED:
            return "Storniert"
        if stage == DONE:
            return "Erledigt"
        return self.stage_labels.get(stage, stage)


#: ►►► **Die eine Liste.** Eine dritte Richtung gibt es nicht – Geld kommt oder geht.
DIRECTIONS: dict[str, Direction] = {
    IN: Direction(
        key=IN,
        label="Einnahme",
        hint="Einnahme – wir stellen Rechnung, Geld kommt herein.",
        stage_labels={OFFER: "Angebot", AGREED: "Auftrag"},
        # Wir **bieten** an; die Gegenpartei fragt nicht bei uns an.
        ask_verb="Anbieten",
        # **Wir** nennen den Preis – das Angebot geht mit ihm hinaus.
        quoted_by=BY_US,
        # Und wir nummerieren: kein Eingabefeld.
        reference=None,
    ),
    OUT: Direction(
        key=OUT,
        label="Ausgabe",
        hint="Ausgabe – wir bekommen Rechnung, Geld geht hinaus.",
        stage_labels={OFFER: "Anfrage", AGREED: "Auftrag"},
        # Wir **fragen** an; die Gegenpartei bietet uns an.
        ask_verb="Anfragen",
        quoted_by=BY_PARTY,
        # Seine Rechnung trägt **seine** Nummer – sie steht auf seinem Papier.
        reference=PARTY_REFERENCE,
    ),
}


def of(direction: Optional[str]) -> Direction:
    """Der Vorgang zu einer Richtung. Unbekannt → **Ausgabe**, nicht ein Fehler.

    Hier wird gelesen, nicht geschrieben: ein Wert, den es nicht geben dürfte, darf keine
    Auftrags-Anzeige zerlegen. Geschrieben wird ausschliesslich über ``assert_direction``,
    und die weist ab.
    """
    return DIRECTIONS.get(direction or "", DIRECTIONS[OUT])


def assert_direction(direction: Any) -> str:
    """Die Schreibprüfung. Ohne sie wäre ``of`` eine stille Umgehung der Liste."""
    if direction in DIRECTIONS:
        return str(direction)
    raise ValueError(
        f"«{direction}» ist keine Richtung. Erlaubt: "
        + ", ".join(f"{d.label} ({k})" for k, d in DIRECTIONS.items()) + "."
    )


def assert_kind(kind: Any) -> str:
    """Die Schreibprüfung für eine Geld-Zeile."""
    if kind in KINDS:
        return str(kind)
    raise ValueError(f"«{kind}» ist keine Art einer Geld-Zeile. Erlaubt: "
                     + ", ".join(KINDS) + ".")


# ---------------------------------------------------------------------------
# ►►► DER BETRAG — eine Stelle, an der aus Eingabe eine Zahl wird ◄◄◄
# ---------------------------------------------------------------------------

#: Die Obergrenze. Nicht, weil es teurer nichts gäbe, sondern weil ein Tippfehler
#: («100000» statt «1000.00») sonst als Zusage im Log stünde.
MAX_AMOUNT = Decimal("99999999.99")


def amount(value: Any, code: str, *, allow_negative: bool = False) -> Optional[Decimal]:
    """Aus einer Eingabe ein Betrag – oder ``None``, wenn nichts dasteht.

    **Über ``Decimal`` und nie über ``float``**: wo es auf den Rappen ankommt, ist
    ``0.1 + 0.2`` kein Argument. Die Eingabe darf ein String sein (das ist sie im
    Browser), ein Komma wird als Dezimaltrennzeichen gelesen – wer «12,50» tippt, meint
    zwölf Franken fünfzig und nicht einen Fehler.

    ``allow_negative`` steht nur an den **Geld-Zeilen**: eine Gutschrift ist eine
    negative Forderung, eine Erstattung eine negative Zahlung. Eine negative **Zusage**
    gibt es dagegen nicht – das wäre ein Vorgang in die andere Richtung, und der hat
    seine eigene Richtung.
    """
    if value in (None, ""):
        return None
    try:
        found = Decimal(str(value).strip().replace("'", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError(f"«{value}» ist kein Betrag.")
    # **Gerundet auf die kleinste Einheit DIESER Währung**, nicht fest auf zwei
    # Stellen: ein fester Schnitt bei ``0.01`` verlöre bei einer dreistelligen
    # Währung (KWD) still eine Stelle – und zwar in der Richtung, in der ein Betrag
    # kleiner wird, ohne dass es jemand sieht.
    found = _round(found, code)
    if not allow_negative and found < 0:
        raise ValueError("Ein zugesagter Betrag ist nicht negativ – "
                         "die Richtung sagt, wohin das Geld fliesst.")
    if abs(found) > MAX_AMOUNT:
        raise ValueError(f"Der Betrag ist zu gross (max. {MAX_AMOUNT}).")
    return found


# ---------------------------------------------------------------------------
# ►►► DIE MEHRWERTSTEUER — der Satz gehört der POSITION ◄◄◄
# ---------------------------------------------------------------------------
#
# Eine Rechnung ohne Steuersatz und Steuerbetrag ist keine (MWSTG Art. 26 Abs. 2 Bst. f).
# Und der Satz hängt an der **Sache**, nicht am Beleg: sechs Wellen zu 8.1 % und eine
# Lieferung ins Ausland zu 0 % stehen auf demselben Papier.
#
# ## Die eine Regel, aus der alles folgt
#
# ►►► **Ein Positionspreis ist NETTO. Jeder Betrag ist BRUTTO.** ◄◄◄
#
# So denkt und rechnet man einen Preis (netto je Stück), und so schuldet man Geld (brutto).
# Damit bleibt ``balance`` unverändert: *offen*, *gefordert* und *gezahlt* sind weiterhin
# dasselbe Mass, und Netto und Steuer sind **Ableitungen** – null Spalten.
#
# ## Gerundet wird je SATZ auf der SUMME
#
# Nicht je Position und dann addiert: bei zwölf Zeilen zu 8.1 % weicht die Summe der
# gerundeten Einzelbeträge um Rappen von der gerundeten Summe ab, und eine MWST-Abrechnung
# kennt keine Rappen-Toleranz. Das ist die Rundungsregel der ESTV und zugleich die einzige,
# die zweimal gerechnet dasselbe ergibt.

#: **Die Schweizer Sätze** – ein Katalog, keine freie Zahl: ein getippter Satz ist ein
#: Satz, den es nicht gibt, und er fällt erst bei der Abrechnung auf. Ändert der
#: Gesetzgeber sie, ist es **eine Zeile hier** – die eingefrorenen Belege behalten ihren.
VAT_RATES: tuple[tuple[str, str], ...] = (
    ("8.10", "Normalsatz"),
    ("2.60", "Reduziert"),
    ("3.80", "Beherbergung"),
    ("0.00", "Ohne (Export · Reverse Charge)"),
)

#: Womit eine neue Position beginnt. Der Normalfall ist der Normalsatz.
DEFAULT_VAT = "8.10"

#: Wie das Feld heisst – ein Wort für beide Richtungen.
VAT_LABEL = "MWST"
#: Das Datum, an dem die Leistung erbracht wurde (MWSTG Art. 26 Abs. 2 Bst. c).
#:
#: Es ist **nicht** das Rechnungsdatum, und der Unterschied zählt: bei einem Satzwechsel
#: oder über den Jahreswechsel entscheidet **es**, welcher Satz gilt. Vorbelegt mit dem
#: Rechnungsdatum, weil beide meistens zusammenfallen.
SERVICE_DATE_LABEL = "Leistungsdatum"


def assert_vat(value: Any) -> str:
    """Die Schreibprüfung für einen Steuersatz. Unbekannt ist ein **Fehler**, kein Default.

    Beim **Lesen** ist das anders (``vat_of``): ein alter Beleg trägt einen Satz, den der
    Katalog vielleicht nicht mehr führt, und eine Anzeige darf daran nicht zerbrechen.
    """
    # **Ein unlesbarer Wert ist derselbe Fehler wie ein unbekannter** – und er bekommt
    # denselben Satz. Ohne das Auffangen kam aus «acht Prozent» ein `InvalidOperation`
    # aus der Tiefe der `decimal`-Bibliothek: technisch eine Ablehnung, fachlich eine
    # Sackgasse ohne Erklärung, und an der Tür ein 500 statt eines 400.
    try:
        text = f"{Decimal(str(value)):.2f}" if value not in (None, "") else DEFAULT_VAT
    except InvalidOperation:
        text = str(value)
    if text not in dict(VAT_RATES):
        raise ValueError(
            f"«{value}» ist kein Steuersatz. Erlaubt: "
            + ", ".join(f"{r} % ({name})" for r, name in VAT_RATES) + "."
        )
    return text


def vat_of(value: Any) -> Decimal:
    """Ein Satz als Zahl – tolerant gelesen. Unlesbar heisst **0 %**, nicht «kaputt»."""
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _round(value: Decimal, code: str) -> Decimal:
    """►►► **Auf die kleinste Einheit DIESER Währung**, kaufmännisch. ◄◄◄

    Sie hiess einmal ``_rappen`` und rundete fest auf ``0.01`` – das ist bei fast jeder
    Währung richtig und bei **JPY** (null Stellen) und **KWD** (drei) still falsch.
    Gerundet wird darum in ``domain/currency`` (``round_to``, kaufmännisch); hier steht
    nur der Name, unter dem dieses Modul danach fragt. Zwei Rundungen wären ein Rappen
    Differenz zwischen Anzeige und Buchung, den niemand erklären kann.
    """
    return cur.round_to(value, code)


def line_net(line: dict[str, Any], code: str) -> Decimal:
    """Der **Netto**-Betrag einer Position: Menge × Einzelpreis. Ohne Preis: null."""
    price = amount(line.get("price"), code, allow_negative=True)
    if price is None:
        return _round(Decimal(0), code)
    return _round(price * Decimal(int(line.get("quantity") or 0)), code)


def vat_split(lines: list[dict[str, Any]], code: str) -> list[dict[str, str]]:
    """►►► **Die Aufteilung je Steuersatz** – gerundet auf der Summe, nicht je Zeile. ◄◄◄

    Zurück kommt je vorkommendem Satz eine Zeile ``{rate, net, tax}`` als **String** – wo
    es auf den Rappen ankommt, wird nicht durch ``float`` gerechnet, auch nicht auf dem
    Weg durch JSON. Sortiert nach Satz, damit zwei Läufe dieselbe Reihenfolge ergeben.
    """
    zero = _round(Decimal(0), code)
    buckets: dict[str, Decimal] = {}
    for line in lines or []:
        rate = f"{vat_of(line.get('vat')):.2f}"
        buckets[rate] = buckets.get(rate, zero) + line_net(line, code)
    return [
        {"rate": rate, "net": cur.money(net, code),
         "tax": cur.money(_round(net * vat_of(rate) / Decimal(100), code), code)}
        for rate, net in sorted(buckets.items(), key=lambda kv: Decimal(kv[0]), reverse=True)
    ]


def gross_of(lines: list[dict[str, Any]], code: str) -> Decimal:
    """Die **Brutto**-Summe der Positionen – Netto plus Steuer, je Satz gerundet."""
    return sum((Decimal(row["net"]) + Decimal(row["tax"])
                for row in vat_split(lines, code)), _round(Decimal(0), code))


def split_for(gross: Decimal, lines: list[dict[str, Any]],
              code: str) -> list[dict[str, str]]:
    """►►► **Die Aufteilung EINER Rechnung** – auch wenn sie nur ein Teil ist. ◄◄◄

    Eine **Anzahlung** ist zum Satz der zugrunde liegenden Leistung zu versteuern; bei
    gemischten Sätzen also **anteilig** über alle. Genau das tut diese Funktion: sie
    verteilt den geforderten Brutto-Betrag im Verhältnis der Positionen und rechnet die
    Steuer je Satz zurück.

    **Der letzte Anteil bekommt den Rest.** Sonst fehlt oder überschiesst ein Rappen, und
    die Summe der Zeilen wäre nicht der Betrag der Rechnung – ein Beleg, der sich selbst
    widerspricht.

    Ohne Positionen (eine **Ausgabe**: die Steuer steht auf *seiner* Rechnung) gibt es
    hier nichts zu verteilen; dann nennt der Aufrufer den Satz, und ``split_at`` rechnet.
    """
    zero = _round(Decimal(0), code)
    rows = vat_split(lines, code)
    total = sum((Decimal(r["net"]) + Decimal(r["tax"]) for r in rows), zero)
    if not rows or total == 0:
        return []
    out: list[dict[str, str]] = []
    used = zero
    for i, row in enumerate(rows):
        share = Decimal(row["net"]) + Decimal(row["tax"])
        part = (gross - used if i == len(rows) - 1
                else _round(gross * share / total, code))
        used += part
        out.append(_at(part, row["rate"], code))
    return out


def split_at(gross: Decimal, rate: Any, code: str) -> list[dict[str, str]]:
    """Die Aufteilung eines Brutto-Betrags zu **einem** Satz – die Ausgabe-Seite."""
    return [_at(gross, f"{vat_of(rate):.2f}", code)]


def _at(gross: Decimal, rate: str, code: str) -> dict[str, str]:
    """Brutto **rückwärts** in Netto und Steuer: ``netto = brutto / (1 + satz)``."""
    net = _round(gross / (Decimal(1) + vat_of(rate) / Decimal(100)), code)
    return {"rate": rate, "net": cur.money(net, code),
            "tax": cur.money(gross - net, code)}


def totals(rows: list[dict[str, str]], code: str) -> dict[str, str]:
    """Netto · Steuer · Brutto einer Aufteilung – die drei Zahlen unter dem Strich."""
    zero = _round(Decimal(0), code)
    net = sum((Decimal(r["net"]) for r in rows), zero)
    tax = sum((Decimal(r["tax"]) for r in rows), zero)
    return {"net": cur.money(net, code), "tax": cur.money(tax, code),
            "gross": cur.money(net + tax, code)}


@dataclass(frozen=True)
class Balance:
    """**Die Rechnung dieses Vorgangs — vier Zahlen, null Spalten.**

    Alles ist abgeleitet. Eine gespeicherte Spalte «offener Betrag» wäre die zweite
    Wahrheit, und die eine vergessene Nachzieh-Stelle fällt erst auf, wenn jemand mahnt.

    ``uncharged`` ist die Zahl, die es ohne die Trennung von Forderung und Geld gar nicht
    geben könnte: *zugesagt − berechnet*. Sie ist der Vorgabewert der nächsten Rechnung
    und damit der Grund, warum eine Anzahlung keinen eigenen Modus braucht.

    Ein **negativer** offener Betrag ist kein Fehler, sondern eine Aussage: dann haben
    wir zu viel bekommen bzw. zu viel gezahlt.
    """

    agreed: Optional[Decimal]
    charged: Decimal
    paid: Decimal
    #: berechnet − bezahlt
    open: Decimal
    #: zugesagt − berechnet (``None``, solange nichts zugesagt ist)
    uncharged: Optional[Decimal]

    @property
    def next_charge(self) -> Optional[Decimal]:
        """**Was als nächstes zu fordern wäre** – und niemals ein negativer Vorschlag.

        ``uncharged`` darf negativ sein (es wurde mehr berechnet als zugesagt) – das ist
        eine gültige Aussage. Als **Vorgabe** in einem Eingabefeld ist sie es nicht: sie
        stand dort als «−250.00», und niemand will eine Rechnung über minus 250 stellen
        (Testnotiz #795). ``None`` heisst «nichts vorzuschlagen», nicht «null».

        Eine Gutschrift bleibt davon unberührt: negative Beträge sind **eingebbar**, sie
        werden nur nie **vorgeschlagen**.
        """
        if self.uncharged is None or self.uncharged <= 0:
            return None
        return self.uncharged

    @property
    def next_payment(self) -> Optional[Decimal]:
        """**Was als nächstes zu zahlen wäre** – dieselbe Regel wie ``next_charge``."""
        return self.open if self.open > 0 else None

    @property
    def settled(self) -> bool:
        """**Ist bezahlt, was zugesagt wurde?** Die eine Frage, die ``prepaid`` stellt.

        Gefragt wird nach der **Zusage**, nicht nach dem offenen Betrag: wer nichts
        berechnet hat, hat einen offenen Betrag von null – und das hiesse «bezahlt»,
        obwohl nie jemand etwas gefordert hat. Dieselbe Zahl, eine ganz andere Aussage.
        """
        return self.paid >= (self.agreed or Decimal("0"))


def balance(agreed: Optional[Decimal],
            entries: list[tuple[str, Decimal]]) -> Balance:
    """Zusage und Geld-Zeilen zu vier Zahlen. **Die eine Rechenstelle.**

    ``entries`` ist eine Liste ``(Art, Betrag)`` – dieselbe Form, in der die Zeilen in
    der Datenbank stehen. Diese Funktion kennt keine Datenbank; sie rechnet, und der
    Dienst liest.
    """
    charged = sum((a for k, a in entries if k == CHARGE), Decimal("0"))
    paid = sum((a for k, a in entries if k == PAYMENT), Decimal("0"))
    return Balance(
        agreed=agreed,
        charged=charged,
        paid=paid,
        open=charged - paid,
        uncharged=None if agreed is None else agreed - charged,
    )
