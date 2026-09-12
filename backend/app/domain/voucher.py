"""**Der Beleg — Geld mit einer zweiten Partei, als Dokument gedacht.**

Der Fachkern des Prozessschrittmoduls «Zahlung» (``domain/modules.Beleg``). Er steht
**vollständig für sich**: keine Datenbank, kein Dienst – und **kein Import** aus
``domain/deal``. Das ist dieselbe Regel, die schon einmal etwas wert war: als
«Beschaffen» und «Verkauf» gelöscht wurden, war am Geldvorgang keine Zeile zu ändern.
Hier gilt sie in die andere Richtung – wird das alte Zahlungsmodul gelöscht, ist hier
keine Zeile zu ändern.

## Warum es das gibt — und warum neu

Der kleinste gemeinsame Nenner von Einkauf, Verkauf, eingekaufter Spedition, Miete, Lohn,
Gebühr und Vorauszahlung ist **nicht die Ware**, sondern **Geld mit einer zweiten
Partei**. Das war die Einsicht des Vorgängers, und sie gilt unverändert.

Neu ist die **Form**. Der Vorgänger entstand als Modulkarte und wurde über mehrere Runden
zu einem Beleg umgeformt; hier ist er von der ersten Zeile an einer:

    Belegkopf → Positionen → Konditionen → Rückläufe → Rechnung & Zahlung → Chronik

Das ist die Ordnung, die ein Beleg seit Jahrhunderten hat, und sie **wächst**: dieselben
Zeilen eine Stufe weiter, nicht ein zweiter Beleg neben dem ersten.

## Die eine Regel, die es robust macht

**Dieses Modul bewegt keine Stücke.** Ein Durchläufer (``Im Prozess`` → ``Im Prozess``),
kein Ausgang, kein Ortswechsel, kein neuer Status. Daraus folgt die Robustheit ohne eine
einzige Prüfung: **keine andere Regel im System muss von ihm wissen.** Was physisch
geschieht, sagen die Nachbarn – bewegt wird mit «Bewegen», ausgesondert mit «Aussondern».

## Drei Achsen, keine Reihenfolge

**Ware · Forderung · Geld** sind unabhängig, und jedes Szenario ist eine andere *Folge*
derselben Grundhandlungen – Zahlungsziel, Vorauszahlung, Anzahlung mit Schlussrechnung,
Gutschrift, Erstattung. Für keines gibt es einen Modus: wer eine Folge festschreibt,
bekommt für jede Abweichung ein ``if``.

## Eine bewusste, befristete Doppelung

Der Steuerkatalog und die Betrags-Mathematik stehen auch in ``domain/deal.py``. Ein
gemeinsames drittes Modul wäre ein Umbau an Code, der gelöscht werden soll – und würde
die beiden genau dann koppeln, wenn sie unabhängig sein müssen. **Ein Wächter vergleicht
die Kataloge**, solange es beide gibt (``test_voucher_module``); er stirbt mit dem alten
Modul, und danach gibt es wieder genau eine Fassung.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from . import currency as cur

# ---------------------------------------------------------------------------
# ►►► DIE RICHTUNG — das eine Feld, aus dem alles Übrige folgt ◄◄◄
# ---------------------------------------------------------------------------

#: **Geld kommt herein** – wir stellen Rechnung.
IN = "in"
#: **Geld geht hinaus** – wir bekommen Rechnung.
OUT = "out"

# ---------------------------------------------------------------------------
# ►►► DIE STUFEN — ZWEI, weil zwei Dinge unumkehrbar sind ◄◄◄
# ---------------------------------------------------------------------------
#
# **nichts zugesagt · zugesagt.** ``DONE`` und ``CANCELLED`` sind **Ausgänge, keine
# Stufen** – man kommt dort an, statt hindurchzugehen. Und das **Geld** ist eine Zeile,
# keine dritte Stufe: eine Zahlung macht aus einem Angebot keine Zusage, sie ist
# reversibel, und sie darf **vor** der Erfüllung stehen (Vorauszahlung) wie danach.

OFFER = "offer"
AGREED = "agreed"
DONE = "done"
CANCELLED = "cancelled"

STAGES: tuple[str, ...] = (OFFER, AGREED)

#: **Ab hier ist eine zweite Partei gebunden.** Davor darf man frei ändern; ab hier ist
#: eine Änderung ein Storno – draussen liegt eine Zusage, die jemand gelesen hat.
BINDING = AGREED

# ---------------------------------------------------------------------------
# ►►► DER ANGEBOTSSPIEGEL — der Vorgang hat ZWEI Parteien ◄◄◄
# ---------------------------------------------------------------------------
#
# Ein Beleg ist kein Formular, das eine Seite ausfüllt: jemand fragt, der andere nennt
# einen Preis, einer sagt zu. Je angefragter Partei eine Zeile – eine **Tabelle**, nicht
# eine Liste an einem Feld: eine Angebotszeile hat einen Zustand, ein Datum, einen Betrag
# und zwei Fristen, und das ist eine Sache, keine Eigenschaft.
#
# ``CHOSEN`` entsteht **nicht durch Tippen**, sondern dadurch, dass bei dieser Zeile
# zugesagt wurde – ein Zustand ist eine Folge.
ASKED, QUOTED, DECLINED, CHOSEN = "angefragt", "offeriert", "abgelehnt", "gewaehlt"

QUOTE_STATES: tuple[str, ...] = (ASKED, QUOTED, DECLINED, CHOSEN)

# ---------------------------------------------------------------------------
# ►►► DIE GELD-ZEILEN — zwei Arten, ein Vorzeichen ◄◄◄
# ---------------------------------------------------------------------------
#
# ``CHARGE``   die **Forderung** (Rechnung). Negativ = Gutschrift.
# ``PAYMENT``  das **Geld**. Negativ = Erstattung.
#
# Zwei Arten und nicht zwei Tabellen: beide sind «eine Zeile Geld an diesem Beleg». Und
# zwei Arten und nicht eine: ohne die Unterscheidung liesse sich «wie viel hat er wirklich
# gezahlt» nicht beantworten, und eine Gutschrift sähe aus wie eine offene Rechnung.

CHARGE = "charge"
PAYMENT = "payment"

KINDS: tuple[str, ...] = (CHARGE, PAYMENT)

# ---------------------------------------------------------------------------
# ►►► WER DEN PREIS NENNT ◄◄◄
# ---------------------------------------------------------------------------
#
# * **Ausgabe**: wir fragen an, **er** nennt den Preis, wir wählen aus.
# * **Einnahme**: **wir** nennen den Preis, er nimmt an oder lehnt ab.
#
# Daraus folgt die ganze Abfolge ohne eine Verzweigung: wer nennt, füllt **vor** dem
# Hinausgehen, und wer nicht nennt, ändert den fremden Preis nicht.

#: **Wir** nennen den Preis (Einnahme).
BY_US = "us"
#: **Die Gegenpartei** nennt ihn (Ausgabe).
BY_PARTY = "party"

# ---------------------------------------------------------------------------
# ►►► DIE WÖRTER — was in beiden Richtungen gleich heisst, ist eine KONSTANTE ◄◄◄
# ---------------------------------------------------------------------------
#
# Als Feld je Richtung wären es Werte, die jemand einzeln falsch setzen kann. Als
# Konstante sind sie eine Aussage.

#: Der andere im Geschäft – in beiden Richtungen, und **Singular = Plural**: damit gibt es
#: keine Beugung, die jemand rechnen könnte («Kundeen» war genau das).
PARTY = "Partner"

#: ►►► **Auf dem Beleg heissen die beiden anders – die Begriffe des MWSTG.** ◄◄◄
#:
#: «Partner» beantwortet «wer ist der andere?». Ein **Beleg** stellt eine zweite Frage:
#: *wer schuldet wem etwas?* – und darauf gibt es zwei Antworten, die auf keiner Rechnung
#: gleich heissen dürfen. «Lieferant/Kunde» ist zu eng (Miete, Lohn, Gebühr haben keinen
#: Lieferanten), «Rechnungssteller» ist auf einer Offerte falsch. Die Begriffe des MWSTG
#: passen für *jede* Leistung und **wörtlich** zum Reverse-Charge-Pflichtsatz.
SUPPLIER = "Leistungserbringer"
CUSTOMER = "Leistungsempfänger"
SUPPLIER_HINT = "Wer die Leistung erbringt und den Beleg stellt."
CUSTOMER_HINT = "Wer die Leistung bezieht und bezahlt."

#: Welche unserer Gesellschaften den Beleg stellt – vorgewählt, hier steht die Korrektur.
ISSUER_LABEL = "Unsere Gesellschaft"
#: Die Nummer im Belegkopf. «Objektnummer» ist ein Systembegriff, «Benutzernummer» falsch,
#: sobald die Partei ein Unternehmen ist – und wessen Nummer es ist, sagt der Block darüber.
PARTY_NUMBER_LABEL = "Nr."

#: Was man an der Schwelle tut: das **Angebot** annehmen – der Auftrag ist das Ergebnis.
AGREE_VERB = "Angebot annehmen"
#: Was man tut, wenn nichts mehr davorsteht. Ein *Vorgang* ist dieser Beleg – das Wort
#: verwechselt sich mit nichts, «Auftrag erledigt» meinte den ERP-Datensatz.
FINISH_VERB = "Vorgang abschliessen"
#: Die eine Gegenhandlung.
UNDO = "Auftrag stornieren"

#: **Erfasst** wird beides – das System bucht eine Zeile, es überweist nichts.
CHARGE_WORD = "Rechnung erfassen"
PAYMENT_WORD = "Zahlung erfassen"
#: Und die dritte Handlung am Geld: sie **auslösen**. «Erfassen» heisst *aufschreiben, was
#: geschehen ist*; hier geschieht es, und gebucht wird erst, wenn der Dienst es meldet.
PAY_ONLINE_WORD = "Jetzt bezahlen"
OPEN_WORD = "Offen"
MONEY_LABEL = "Rechnung & Zahlung"

#: **Was bei ihm zu tun ist** – seine Artikelnummer, sein Shop-Link oder ein Satz. Eine
#: Eigenschaft der **Paarung** Modul × Partner: derselbe Lieferant führt je Teil eine
#: andere Nummer.
TASK = "Was ist zu tun?"
TASK_HINT = "Artikelnummer, Link oder Beschreibung"

#: Die Nummer, unter der die **Gegenpartei** diesen Geldfluss führt. Das Feld gibt es nur,
#: wo die Nummer von aussen kommt – eine, die **wir** vergeben, tippt niemand ab.
PARTY_REFERENCE = "Zahlungsreferenz des Partners"

#: ►►► **Die Überschriften des Belegs.** ◄◄◄ Eine fehlt mit Absicht: über den Konditionen
#: stand «Konditionen», und die Zeilen darunter (Zahlungsfrist, Lieferfrist,
#: Lieferbedingung) sagen selbst, was sie sind (Testnotiz #926).
GOODS_TITLE = "Positionen"
QUOTES_TITLE = "Rückläufe"
HISTORY_TITLE = "Chronik"

# ---------------------------------------------------------------------------
# ►►► DIE BEIDEN FRISTEN — eine Zahl, und die üblichen Werte haben Namen ◄◄◄
# ---------------------------------------------------------------------------
#
# Eine Frist ist **eine Zahl in Tagen**. Sie hat aber zwei, drei übliche Werte, und die
# trägt man nicht als Zahl im Kopf: «Vorauszahlung» ist ein Geschäftsbegriff, «0» eine
# Ziffer, die man erklären muss.
#
# **«Vorauszahlung» IST der Wert 0** – kein Schalter daneben. Damit die Null genau eine
# Bedeutung hat, ist sie **nicht tippbar**: die freie Eingabe beginnt bei 1.

#: Zahlbar in null Tagen ab der Zusage – **das ist die Vorauszahlung**.
PREPAID_DAYS = 0

PAYMENT_TERMS: tuple[tuple[int, str], ...] = ((PREPAID_DAYS, "Vorauszahlung"),
                                              (30, "30 Tage"))
#: Die übliche Lieferfrist, die keine ist: eine Software ist sofort da.
LEAD_TERMS: tuple[tuple[int, str], ...] = ((0, "Sofort"),)

#: Ab hier beginnt die freie Eingabe. **Nicht bei 0** – die hat einen Namen.
FREE_MIN = 1

PAYMENT_TERM_LABEL = "Zahlungsfrist"
LEAD_TERM_LABEL = "Lieferfrist"
FREE_TERM_LABEL = "Individuell"


def prepaid(due_days: Optional[int]) -> bool:
    """►►► **Wartet dieses Modul auf das Geld?** – die eine Lesestelle. ◄◄◄

    Keine Einstellung, sondern die Bedeutung der vereinbarten Zahlungsfrist: wer in null
    Tagen zahlbar stellt, liefert nicht vorher. ``None`` heisst «keine Frist vereinbart»
    und damit **nicht** Vorauszahlung – ohne Angabe hat niemand über den Zeitpunkt
    gesprochen, und eine erfundene Sperre wäre schlimmer als keine.
    """
    return due_days == PREPAID_DAYS


def term_name(days: Optional[int], terms: tuple[tuple[int, str], ...]) -> Optional[str]:
    """Wie diese Frist **heisst** – gelesen aus derselben Liste, aus der man sie wählt.

    Ein Wert, den keine Liste kennt, ist die freie Eingabe und hat keinen Namen; der
    Aufrufer schreibt dann «x Tage».
    """
    return dict(terms).get(days) if days is not None else None


# ---------------------------------------------------------------------------
# ►►► WIE BEZAHLT WURDE — drei Wege, und nur zwei tippt ein Mensch ◄◄◄
# ---------------------------------------------------------------------------
#
# Bar · Überweisung · Karte sind **eine Angabe an der Zahlung**, kein zweites Modell:
# gebucht wird in jedem Fall dieselbe Zeile. **Die Karte tippt niemand ab** – sie entsteht
# beim Zahlungsdienst und kommt über den Webhook; ein Mensch, der sie von Hand wählt,
# behauptet eine Buchung, für die es keinen Beleg gibt.
CASH = "cash"
TRANSFER = "transfer"
CARD = "card"

METHODS: tuple[tuple[str, str], ...] = (
    (CASH, "Bar"),
    (TRANSFER, "Überweisung"),
    (CARD, "Karte"),
)

#: Was ein **Mensch** erfassen darf.
MANUAL_METHODS: tuple[str, ...] = (CASH, TRANSFER)

METHOD_LABEL = "Zahlungsart"


def method_name(key: Optional[str]) -> Optional[str]:
    """Das Wort zur Zahlungsart – **eine** Auflösung, oder ``None`` für Altbestand."""
    return dict(METHODS).get(key or "")


def assert_method(value: Any) -> Optional[str]:
    """Eine **von Hand** erfasste Zahlungsart – oder ``None``.

    Die Karte wird **abgewiesen**, nicht bloss ignoriert: ein Feld, das die Oberfläche
    nicht anbietet, der Dienst aber annimmt, wäre die Hintertür zu einer Buchung, die
    behauptet, ein Zahlungsdienst habe sie gemeldet.
    """
    if value in (None, ""):
        return None
    key = str(value)
    if key not in MANUAL_METHODS:
        raise ValueError(
            f"«{key}» lässt sich nicht von Hand erfassen – "
            f"möglich sind {', '.join(dict(METHODS)[m] for m in MANUAL_METHODS)}.")
    return key


# ---------------------------------------------------------------------------
# ►►► STORNO ODER GUTSCHRIFT — dieselbe Gegenbuchung, zwei Lagen ◄◄◄
# ---------------------------------------------------------------------------
#
# * **unbezahlt** → *Stornorechnung*: die Forderung war falsch, sie wird zurückgenommen.
# * **bezahlt**  → *Gutschrift*: die Forderung war richtig, das Geschäft ändert sich –
#   danach ist der offene Betrag negativ, also folgt die **Erstattung**.
#
# Ein zweites Verb wäre eine zweite Regel für eine Buchung, die gleich aussieht; ein
# einziges Wort wäre an der Hälfte der Belege falsch.
STORNO_WORD = "Stornieren"
CREDIT_WORD = "Gutschrift"
REFUND_WORD = "Erstattung erfassen"
REFUND_ONLINE_WORD = "Online erstatten"
#: Die dritte Bezahlart an einer offenen Rechnung: **Angaben**, keine Buchung.
TRANSFER_WORD = "Überweisen"


def reverse_word(paid: Decimal) -> str:
    """**Wie die Gegenbuchung an DIESER Rechnung heisst** – die eine Lesestelle."""
    return CREDIT_WORD if paid > 0 else STORNO_WORD


@dataclass(frozen=True)
class Direction:
    """**Ein Beleg in EINER Richtung** – alles, was die beiden unterscheidet.

    Acht Felder und **keine Eigenschaft**: was in beiden Richtungen gleich lautet, steht
    als Konstante über dieser Klasse. Der Vorgänger trug dieselben Wörter als acht
    Properties, die alle eine Konstante zurückgaben – acht Stellen, an denen jemand eine
    Verzweigung hätte einbauen können.

    Es steht als **Daten** da und nicht als ``if``, weil eine Verzweigung sich vermehrt:
    die erste ist eine Beschriftung, die zweite eine Regel, und ab der dritten gibt es
    zwei Vorgänge, die nur noch so tun, als wären sie einer.
    """

    key: str
    #: Wie der Vorgang heisst – «Einnahme» · «Ausgabe». Bewusst **nicht** «Verkauf ↔
    #: Einkauf»: Miete, Lohn und Gebühr sind keine Käufe, und ein Wert, der «Verkauf»
    #: heisst, wäre enger als das Modul.
    label: str
    #: Ein Satz, der sagt, was passiert. Er steht im Editor neben der Wahl.
    hint: str
    #: **Die beiden Stufen, wie sie in dieser Richtung heissen.**
    stage_labels: dict[str, str]
    #: **Wie man auf den Partner zugeht** – anfragen ↔ anbieten.
    ask_verb: str
    #: ►►► **Wer den Preis nennt** – ``BY_US`` ↔ ``BY_PARTY``. ◄◄◄
    quoted_by: str
    #: **Wie die Nummer einer Geld-Zeile entsteht.** ``None`` heisst «wir nummerieren» –
    #: dann gibt es kein Eingabefeld, weder an der Rechnung noch an der Zahlung.
    reference: Optional[str]
    #: ►►► **Kassieren wir hier – oder zahlen wir?** ◄◄◄ Ein Zahlungsdienst **zieht ein**;
    #: er überweist nicht in unserem Namen. Daraus folgt zugleich, wer auf dem Beleg der
    #: Leistungserbringer ist.
    collects: bool

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
        # Die **Auftragsbestätigung IST diese Stufe**: sie hat Datum, Nummer, bestätigte
        # Positionen mit Preis und Satz und beide Fristen. Eine eigene Stufe wäre ein
        # **Zustand** in einer Reihe von **Schritten**, den man nicht *tut*.
        stage_labels={OFFER: "Offerte", AGREED: "Auftragsbestätigung"},
        ask_verb="Anbieten",
        quoted_by=BY_US,
        reference=None,
        collects=True,
    ),
    OUT: Direction(
        key=OUT,
        label="Ausgabe",
        hint="Ausgabe – wir bekommen Rechnung, Geld geht hinaus.",
        stage_labels={OFFER: "Anfrage", AGREED: "Bestellung"},
        ask_verb="Anfragen",
        quoted_by=BY_PARTY,
        # Seine Rechnung trägt **seine** Nummer – sie steht auf seinem Papier.
        reference=PARTY_REFERENCE,
        collects=False,
    ),
}


def of(direction: Optional[str]) -> Direction:
    """Die Richtung zu einem Wert. Unbekannt → **Ausgabe**, nicht ein Fehler.

    Hier wird gelesen, nicht geschrieben: ein Wert, den es nicht geben dürfte, darf keine
    Auftrags-Anzeige zerlegen. Geschrieben wird über ``assert_direction``.
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
    ``0.1 + 0.2`` kein Argument. Ein Komma wird als Dezimaltrennzeichen gelesen – wer
    «12,50» tippt, meint zwölf Franken fünfzig und keinen Fehler.

    ``allow_negative`` steht nur an den **Geld-Zeilen**: eine Gutschrift ist eine negative
    Forderung, eine Erstattung eine negative Zahlung. Eine negative **Zusage** gibt es
    nicht – das wäre ein Vorgang in die andere Richtung, und der hat seine eigene.
    """
    if value in (None, ""):
        return None
    try:
        found = Decimal(str(value).strip().replace("'", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError(f"«{value}» ist kein Betrag.")
    # **Gerundet auf die kleinste Einheit DIESER Währung**, nicht fest auf zwei Stellen:
    # ein fester Schnitt bei ``0.01`` verlöre bei einer dreistelligen Währung (KWD) still
    # eine Stelle – in der Richtung, in der ein Betrag kleiner wird, ohne dass es jemand
    # sieht.
    found = _round(found, code)
    if not allow_negative and found < 0:
        raise ValueError("Ein zugesagter Betrag ist nicht negativ – "
                         "die Richtung sagt, wohin das Geld fliesst.")
    if abs(found) > MAX_AMOUNT:
        raise ValueError(f"Der Betrag ist zu gross (max. {MAX_AMOUNT}).")
    return found


def _round(value: Decimal, code: str) -> Decimal:
    """**Auf die kleinste Einheit DIESER Währung**, kaufmännisch (``domain/currency``).

    Fest auf ``0.01`` gerundet wäre bei **JPY** (null Stellen) und **KWD** (drei) still
    falsch; und ``quantize`` ohne Angabe rundet **statistisch** – eine Anzeige, die anders
    rundet als die Buchung, ist ein Rappen Differenz, den niemand erklären kann.
    """
    return cur.round_to(value, code)


# ---------------------------------------------------------------------------
# ►►► DIE MEHRWERTSTEUER — der Satz gehört der POSITION ◄◄◄
# ---------------------------------------------------------------------------
#
# Eine Rechnung ohne Steuersatz und Steuerbetrag ist keine (MWSTG Art. 26 Abs. 2 Bst. f).
# Und der Satz hängt an der **Sache**, nicht am Beleg: sechs Wellen zu 8.1 % und eine
# Ausfuhr zu 0 % stehen auf demselben Papier.
#
# ►►► **Ein Positionspreis ist NETTO. Jeder Betrag ist BRUTTO.** ◄◄◄
#
# So denkt man einen Preis und so schuldet man Geld. Damit bleibt ``balance`` unberührt –
# Netto und Steuer sind **Ableitungen**, null Spalten.
#
# **Gerundet wird je Satz auf der SUMME**, nicht je Position und dann addiert: bei zwölf
# Zeilen weicht die Summe der gerundeten Einzelbeträge um Rappen ab, und eine
# MWST-Abrechnung kennt keine Toleranz.


@dataclass(frozen=True)
class VatRate:
    """Ein Steuersatz des Katalogs – Schlüssel, Zahl, Name und sein Pflichtsatz."""

    key: str
    #: Als **String** mit zwei Nachkommastellen, so wie gerechnet und verglichen wird.
    rate: str
    label: str
    #: Der Satz, der bei diesem Tatbestand auf dem Beleg **stehen muss** – sonst ``None``.
    note: Optional[str] = None


#: **Die Schweizer Sätze** – ein Katalog, keine freie Zahl: ein getippter Satz ist einer,
#: den es nicht gibt, und er fällt erst bei der Abrechnung auf.
#:
#: ►►► **Der Nullsatz trägt ZWEI Tatbestände.** ◄◄◄ *Export* und *Reverse Charge* sind
#: zwei Rechtsgründe mit zwei Pflichtsätzen, und beide ergeben 0 %. Darum ist der
#: **Schlüssel** der gespeicherte Wert und nicht die Zahl – ein Beleg, der nur «0 %» sagt,
#: nennt den Grund nicht, und genau den braucht der Empfänger für seine Abrechnung.
VAT_RATES: tuple[VatRate, ...] = (
    VatRate("normal", "8.10", "Normalsatz"),
    VatRate("reduced", "2.60", "Reduziert"),
    VatRate("lodging", "3.80", "Beherbergung"),
    VatRate("export", "0.00", "Export",
            "Steuerfreie Ausfuhrlieferung"),
    VatRate("reverse", "0.00", "Reverse Charge",
            "Steuerschuldnerschaft des Leistungsempfängers"),
)

_BY_KEY: dict[str, VatRate] = {v.key: v for v in VAT_RATES}

#: Womit eine neue Position beginnt. Der Normalfall ist der Normalsatz.
DEFAULT_VAT = "normal"

VAT_LABEL = "MWST"
#: Das Datum, an dem die Leistung erbracht wurde (MWSTG Art. 26 Abs. 2 Bst. c). **Nicht**
#: das Rechnungsdatum: über den Jahreswechsel entscheidet es die Steuerperiode.
SERVICE_DATE_LABEL = "Leistungsdatum"


def vat_entry(value: Any) -> Optional[VatRate]:
    """Die Katalogzeile zu einem Wert – **tolerant**, denn Belege sind eingefroren.

    Drei Wege hinein: der **Schlüssel** (so wird geschrieben), eine **Zahl** («8.10» – so
    steht es in Altbestand; sie trifft die erste Zeile mit diesem Satz), alles andere →
    ``None``, und der Aufrufer zeigt den Rohwert statt zu raten.

    **Die eine benannte Annahme:** ein altes «0.00» wird **Export** – beide Nullsätze
    hiessen einmal gleich, also lässt sich nicht mehr feststellen, welcher gemeint war,
    und Export ist der häufigere.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text in _BY_KEY:
        return _BY_KEY[text]
    try:
        num = f"{Decimal(text):.2f}"
    except InvalidOperation:
        return None
    return next((v for v in VAT_RATES if v.rate == num), None)


def assert_vat(value: Any) -> str:
    """Die Schreibprüfung. Unbekannt ist ein **Fehler**, kein Default.

    Zurück kommt der **Schlüssel** der Katalogzeile. Eine Zahl wird dabei umgesetzt: wer
    «8.10» schickt, meint den Normalsatz. Beim **Lesen** ist das anders (``vat_of``) – ein
    alter Beleg trägt einen Satz, den der Katalog vielleicht nicht mehr führt, und eine
    Anzeige darf daran nicht zerbrechen.
    """
    if value in (None, ""):
        return DEFAULT_VAT
    entry = vat_entry(value)
    if entry is None:
        # Ein **unlesbarer** Wert ist derselbe Fehler wie ein unbekannter und bekommt
        # denselben Satz: ohne das Auffangen käme aus «acht Prozent» ein
        # ``InvalidOperation`` aus der Tiefe von ``decimal`` – an der Tür ein 500 statt
        # eines 400, also eine Ablehnung ohne Erklärung.
        raise ValueError(
            f"«{value}» ist kein Steuersatz. Erlaubt: "
            + ", ".join(f"{v.label} ({v.rate} %)" for v in VAT_RATES) + "."
        )
    return entry.key


def vat_of(value: Any) -> Decimal:
    """Ein Satz als Zahl – tolerant. Unlesbar heisst **0 %**, nicht «kaputt»."""
    entry = vat_entry(value)
    if entry is not None:
        return Decimal(entry.rate)
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def vat_label(value: Any) -> str:
    """Wie dieser Satz **heisst**. Unbekanntes zeigt sich als Prozentzahl, nicht als Name."""
    entry = vat_entry(value)
    return entry.label if entry is not None else f"{vat_of(value):.2f} %"


def vat_note(value: Any) -> Optional[str]:
    """Der **Pflichtsatz** dieses Tatbestands – ``None``, wo keiner verlangt ist."""
    entry = vat_entry(value)
    return entry.note if entry is not None else None


def line_net(line: dict[str, Any], code: str) -> Decimal:
    """Der **Netto**-Betrag einer Position: Menge × Einzelpreis. Ohne Preis: null."""
    price = amount(line.get("price"), code, allow_negative=True)
    if price is None:
        return _round(Decimal(0), code)
    return _round(price * Decimal(int(line.get("quantity") or 0)), code)


def vat_split(lines: list[dict[str, Any]], code: str) -> list[dict[str, str]]:
    """►►► **Die Aufteilung je Steuersatz** – gerundet auf der Summe, nicht je Zeile. ◄◄◄

    Zurück kommt je vorkommendem Satz eine Zeile ``{vat, rate, label, note, net, tax}``
    als **String** – wo es auf den Rappen ankommt, wird nicht durch ``float`` gerechnet,
    auch nicht auf dem Weg durch JSON.

    **Gruppiert wird nach KATALOGZEILE, nicht nach Zahl** – sonst fielen *Export* und
    *Reverse Charge* zu einer Zeile zusammen (beide 0 %), und der Beleg nennte nur einen
    der beiden Rechtsgründe.
    """
    zero = _round(Decimal(0), code)
    buckets: dict[str, Decimal] = {}
    for line in lines or []:
        entry = vat_entry(line.get("vat"))
        key = entry.key if entry is not None else f"{vat_of(line.get('vat')):.2f}"
        buckets[key] = buckets.get(key, zero) + line_net(line, code)
    order = {v.key: i for i, v in enumerate(VAT_RATES)}
    return [
        _row(key, net, code)
        for key, net in sorted(buckets.items(),
                               key=lambda kv: (-vat_of(kv[0]), order.get(kv[0], 99)))
    ]


def _row(key: str, net: Decimal, code: str) -> dict[str, str]:
    """Eine Zeile der Aufteilung – aus Schlüssel und Netto, samt ihrer Auskunft."""
    tax = _round(net * vat_of(key) / Decimal(100), code)
    return _describe(key, {"net": cur.money(net, code), "tax": cur.money(tax, code)})


def _describe(key: str, row: dict[str, str]) -> dict[str, str]:
    """Schlüssel · Zahl · Name · Pflichtsatz an eine Zeile schreiben.

    **Die Auskunft reist mit der Zeile**, statt dass der Empfänger sie nachschlägt: eine
    gebuchte Zeile ist eingefroren, und wer ihren Namen erst zur Anzeige nachschlägt,
    ändert die Vergangenheit, sobald der Katalog sich ändert.
    """
    out = {"vat": key, "rate": f"{vat_of(key):.2f}", "label": vat_label(key), **row}
    note = vat_note(key)
    if note:
        out["note"] = note
    return out


def gross_of(lines: list[dict[str, Any]], code: str) -> Decimal:
    """Die **Brutto**-Summe der Positionen – Netto plus Steuer, je Satz gerundet."""
    return sum((Decimal(row["net"]) + Decimal(row["tax"])
                for row in vat_split(lines, code)), _round(Decimal(0), code))


def split_for(gross: Decimal, lines: list[dict[str, Any]],
              code: str) -> list[dict[str, str]]:
    """►►► **Die Aufteilung EINER Rechnung** – auch wenn sie nur ein Teil ist. ◄◄◄

    Eine **Anzahlung** ist zum Satz der zugrunde liegenden Leistung zu versteuern; bei
    gemischten Sätzen also **anteilig** über alle. **Der letzte Anteil bekommt den Rest** –
    sonst fehlt oder überschiesst ein Rappen, und die Summe der Zeilen wäre nicht der
    Betrag der Rechnung: ein Beleg, der sich selbst widerspricht.
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
        out.append(_at(part, row["vat"], code))
    return out


def split_at(gross: Decimal, rate: Any, code: str) -> list[dict[str, str]]:
    """Die Aufteilung eines Brutto-Betrags zu **einem** Satz – die Ausgabe-Seite."""
    entry = vat_entry(rate)
    return [_at(gross, entry.key if entry is not None else f"{vat_of(rate):.2f}", code)]


def _at(gross: Decimal, key: str, code: str) -> dict[str, str]:
    """Brutto **rückwärts** in Netto und Steuer: ``netto = brutto / (1 + satz)``."""
    net = _round(gross / (Decimal(1) + vat_of(key) / Decimal(100)), code)
    return _describe(key, {"net": cur.money(net, code),
                           "tax": cur.money(gross - net, code)})


def totals(rows: list[dict[str, str]], code: str) -> dict[str, str]:
    """Netto · Steuer · Brutto einer Aufteilung – die drei Zahlen unter dem Strich."""
    zero = _round(Decimal(0), code)
    net = sum((Decimal(r["net"]) for r in rows), zero)
    tax = sum((Decimal(r["tax"]) for r in rows), zero)
    return {"net": cur.money(net, code), "tax": cur.money(tax, code),
            "gross": cur.money(net + tax, code)}


@dataclass(frozen=True)
class Balance:
    """**Die Rechnung dieses Belegs — vier Zahlen, null Spalten.**

    Alles abgeleitet. Eine gespeicherte Spalte «offener Betrag» wäre die zweite Wahrheit,
    und die eine vergessene Nachzieh-Stelle fällt erst auf, wenn jemand mahnt.

    ``uncharged`` ist die Zahl, die es ohne die Trennung von Forderung und Geld gar nicht
    geben könnte: *zugesagt − berechnet*.

    Ein **negativer** offener Betrag ist kein Fehler, sondern eine Aussage: dann haben wir
    zu viel bekommen bzw. zu viel gezahlt.
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

        ``uncharged`` darf negativ sein (es wurde mehr berechnet als zugesagt); als
        **Vorgabe** in einem Eingabefeld ist es das nicht – niemand will eine Rechnung
        über minus 250 stellen. Eingebbar bleiben negative Beträge (Gutschrift), sie
        werden nur nie vorgeschlagen.
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
        obwohl nie jemand etwas gefordert hat.
        """
        return self.paid >= (self.agreed or Decimal("0"))


def balance(agreed: Optional[Decimal],
            entries: list[tuple[str, Decimal]]) -> Balance:
    """Zusage und Geld-Zeilen zu vier Zahlen. **Die eine Rechenstelle.**

    ``entries`` ist eine Liste ``(Art, Betrag)`` – dieselbe Form, in der die Zeilen in der
    Datenbank stehen. Diese Funktion kennt keine Datenbank; sie rechnet, und der Dienst
    liest.
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
