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
#: Was man tut, wenn nichts mehr davorsteht.
FINISH_VERB = "Auftrag erledigt"
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

#: Die Nummer der Gegenpartei an ihrer Rechnung – nur, wo **sie** die Rechnung stellt.
PARTY_CHARGE_REFERENCE = "Belegnummer des Partners"
#: Die Referenz einer Zahlung – in **beiden** Richtungen von aussen.
PAYMENT_REFERENCE = "Zahlungsreferenz"


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
    #: **Wie die Nummer einer Forderung entsteht.** ``None`` heisst «wir nummerieren» –
    #: dann gibt es kein Eingabefeld (#840). Sonst der Name des Feldes.
    charge_reference: Optional[str]

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
        charge_reference=None,
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
        charge_reference=PARTY_CHARGE_REFERENCE,
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


def amount(value: Any, *, allow_negative: bool = False) -> Optional[Decimal]:
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
    found = found.quantize(Decimal("0.01"))
    if not allow_negative and found < 0:
        raise ValueError("Ein zugesagter Betrag ist nicht negativ – "
                         "die Richtung sagt, wohin das Geld fliesst.")
    if abs(found) > MAX_AMOUNT:
        raise ValueError(f"Der Betrag ist zu gross (max. {MAX_AMOUNT}).")
    return found


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
