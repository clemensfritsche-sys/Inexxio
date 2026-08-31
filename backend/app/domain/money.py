"""**Geld — die geschlossenen Listen und die eine Rechnung.**

Hier steht, was eine Zeile Geld sein kann und wie man aus einem Beleg und seinen Zeilen
den offenen Betrag bekommt. Keine Datenbank, kein Dienst – dieselbe Trennung wie bei
``statuses`` und ``procurement``.

## Drei Achsen, keine Reihenfolge (PROCESS_CORE §9.11)

Ein Geschäft hat drei **unabhängige** Achsen: **Ware** (die Einzelinstanzen im Prozess),
**Forderung** (die Rechnung) und **Geld** (die Zahlung). Jedes Zahlungs-Szenario ist eine
andere *Folge* derselben drei Grundhandlungen:

===========================  ================================  ===================
Szenario                     Folge                             neuer Mechanismus
===========================  ================================  ===================
Rechnung mit Zahlungsziel    Ware → Forderung → Geld           keiner
Vorauszahlung                Forderung → Geld → Ware           keiner
Anzahlung + Schlussrechnung  Forderung → Geld → Ware → …       keiner
Nachnahme                    Ware → Forderung + Geld           keiner
Shop, sofort bezahlt         Forderung → Zahllink → Webhook    keiner
Retoure mit Gutschrift       Ware zurück → negative Forderung  keiner
Garantie (ohne Geld)         nur Ware                          keiner
Kulanz (ohne Rücknahme)      nur negative Forderung            keiner
===========================  ================================  ===================

**Wer eine Folge festschreibt, bekommt für jede Abweichung ein ``if``.** Das System hält
darum fest, was geschehen ist, und bietet den naheliegenden nächsten Schritt an – es
schreibt keine Reihenfolge vor. Es gibt keinen Modus «Vorkasse», keinen Schalter und
keine Einstellung: wer zuerst Geld sehen will, stellt zuerst die Rechnung.

## Eine Gutschrift ist eine negative RECHNUNG, keine Zahlung

Vorher war sie eine ``payment``-Zeile der Art ``credit`` – eine Zahlung, bei der kein Geld
fliesst. Dafür brauchte es eine eigene Regel («eine Gutschrift hat keinen Zahlweg»), und
``open`` musste drei Summen führen. Als negative Rechnung ist sie schlicht richtig, und
**beide Regeln entfallen**: es gibt keine ``kind``-Spalte mehr und keinen Sonderfall im
Zahlweg. Eine Erstattung bleibt, was sie ist – eine **negative Zahlung**.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

#: **Wie gezahlt wurde.** Eine geschlossene Liste, weil ein Freitext hier bedeutete, dass
#: «Bank», «Überweisung» und «Bank-Überweisung» drei Wege wären.
#:
#: ``transfer``  Überweisung – der B2B-Normalfall. Ein Mensch trägt sie ein.
#: ``card``      Karte über den Zahlungsdienst. **Der Webhook** trägt sie ein.
#: ``cash``      Bar oder am Schalter.
TRANSFER, CARD, CASH = "transfer", "card", "cash"

METHODS: tuple[str, ...] = (TRANSFER, CARD, CASH)

#: ►►► **Was ein MENSCH eintragen darf.** ◄◄◄
#:
#: Eine Kartenzahlung tippt niemand ab – sie entsteht beim Zahlungsdienst und kommt über
#: den Webhook (Testnotiz #782). Sie von Hand zu erfassen hiesse, eine zweite Quelle für
#: dieselbe Buchung zu öffnen; die eine käme aus der Wirklichkeit, die andere aus einer
#: Erinnerung.
#:
#: **Zwei Formen einer Regel, ein Namensstamm**: ``METHODS`` sagt, was es *gibt*
#: (``payments.record`` prüft dagegen – der Webhook schreibt hier durch),
#: ``MANUAL_METHODS`` sagt, was man *eintragen* darf (die Menschentür ``purchase._pay``
#: prüft dagegen, und die Oberfläche bietet genau diese an).
MANUAL_METHODS: tuple[str, ...] = (TRANSFER, CASH)

METHOD_LABELS: dict[str, str] = {
    TRANSFER: "Überweisung",
    CARD: "Karte",
    CASH: "Bar",
}

#: Der Weg, den **der Zahlungsdienst** schreibt. Er steht hier und nicht in
#: ``services/stripe_pay``, damit die Regel «erstattet wird auf dem Weg, auf dem gezahlt
#: wurde» ohne einen Blick in den Adapter formulierbar ist.
ONLINE = CARD


@dataclass(frozen=True)
class Balance:
    """**Was an einem Beleg noch offen ist** – und woraus sich das zusammensetzt.

    Eine Ableitung, kein gespeicherter Zustand. ``open`` kann **negativ** sein: das ist
    kein Fehler, sondern eine Aussage – wir schulden dann der Gegenpartei Geld (es wurde
    zu viel überwiesen, oder eine Gutschrift steht noch aus).

    **Die Formel liest jetzt die Forderung, nicht die Zusage.** Vorher stand dort
    ``purchase.amount`` – die **Zusage** als wäre sie die **Forderung**. Solange beides
    dasselbe ist, geht das gut; an Anzahlung, Teilrechnung und zwei Fälligkeiten bricht es,
    und zwar still.
    """

    #: Was zugesagt wurde (die Belegsumme). ``None``, solange nichts zugesagt ist.
    #: **Nicht** die Forderung – die steht in ``charged``.
    total: Optional[Decimal]
    #: Summe der Rechnungen – was **gefordert** wird. Gutschriften zählen negativ.
    charged: Decimal
    #: Summe der Zahlungen – was tatsächlich geflossen ist (Erstattungen zählen negativ).
    paid: Decimal

    @property
    def open(self) -> Decimal:
        """**Forderungen − Zahlungen.** Die eine Formel, jeder Fall darin."""
        return self.charged - self.paid

    @property
    def uncharged(self) -> Optional[Decimal]:
        """**Zugesagt, aber noch nicht berechnet.** ``None``, solange nichts zugesagt ist.

        Die Zahl, die es vorher gar nicht geben konnte – und die Vorgabe für die nächste
        Rechnung. Sie darf negativ werden (mehr berechnet als zugesagt); auch das ist eine
        Aussage und kein Fehler.
        """
        return None if self.total is None else self.total - self.charged

    @property
    def settled(self) -> bool:
        """Ist nichts mehr offen? Genau dann, wenn die Differenz null ist."""
        return self.open == Decimal("0")


def parse(value: Any, *, field: str, signed: bool = False) -> Decimal:
    """Ein Betrag – **als Decimal**, nie als ``float``.

    Er reist als String durch JSONB und aus der Numeric-Spalte heraus; wo es auf den
    Rappen ankommt, ist eine Fliesskommazahl der Anfang eines Rundungsfehlers, den niemand
    mehr findet.

    ``signed`` erlaubt negative Werte. Sie sind an zwei Stellen richtig – bei der
    **Erstattung** und bei der **Gutschrift** – und überall sonst ein Tippfehler.
    """
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"«{value}» ist kein Betrag ({field}).")
    if not signed and amount < 0:
        raise ValueError(f"Ein Betrag ist nicht negativ ({field}).")
    if amount == 0:
        raise ValueError(f"Ein Betrag von null ist keine Angabe ({field}).")
    return amount.quantize(Decimal("0.01"))


def assert_method(method: Any, *, manual: bool = False) -> str:
    """Der Weg einer Zahlung. ``manual`` verengt auf das, was ein Mensch eintragen darf.

    Die frühere Fassung nahm ein ``kind`` entgegen und verbot den Weg an einer Gutschrift.
    Diesen Fall gibt es nicht mehr: eine Gutschrift ist eine **Rechnung**, und eine
    Rechnung hat gar kein Feld dafür. Eine Regel weniger, statt einer Ausnahme mehr.
    """
    allowed = MANUAL_METHODS if manual else METHODS
    if method in allowed:
        return str(method)
    raise ValueError(
        f"«{method}» ist kein Zahlweg. Erlaubt: " + ", ".join(allowed) + "."
    )
