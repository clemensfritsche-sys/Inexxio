"""**Geld — die geschlossenen Listen und die eine Rechnung.**

Hier steht, was eine Zeile Geld sein kann und wie man aus einem Beleg und seinen Zeilen
den offenen Betrag bekommt. Keine Datenbank, kein Dienst – dieselbe Trennung wie bei
``statuses`` und ``procurement``.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

#: **Geld ist geflossen.** Positiv = es kam an, negativ = es ging zurück (Erstattung).
PAYMENT = "payment"

#: **Die Forderung wird gemindert**, ohne dass Geld fliesst: Gutschrift, Kulanz, Abzug.
CREDIT = "credit"

KINDS: tuple[str, ...] = (PAYMENT, CREDIT)

KIND_LABELS: dict[str, str] = {PAYMENT: "Zahlung", CREDIT: "Gutschrift"}

#: **Wie gezahlt wurde.** Eine geschlossene Liste, weil ein Freitext hier bedeutete, dass
#: «Bank», «Überweisung» und «Bank-Überweisung» drei Wege wären.
#:
#: ``transfer``  Überweisung – der B2B-Normalfall. Ein Mensch trägt sie ein.
#: ``card``      Karte über den Zahlungsdienst. Der Webhook trägt sie ein.
#: ``cash``      Bar oder am Schalter.
TRANSFER, CARD, CASH = "transfer", "card", "cash"

METHODS: tuple[str, ...] = (TRANSFER, CARD, CASH)

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

    Eine Ableitung, kein gespeicherter Zustand: ``open`` ist die Differenz, und sie kann
    **negativ** sein. Das ist kein Fehler, sondern eine Aussage – wir schulden dann der
    Gegenpartei Geld (eine Gutschrift steht aus, oder es wurde zu viel überwiesen).
    """

    #: Was zugesagt wurde (die Belegsumme). ``None``, solange nichts zugesagt ist.
    total: Optional[Decimal]
    #: Summe der ``credit``-Zeilen – was gar nicht mehr geschuldet wird.
    credited: Decimal
    #: Summe der ``payment``-Zeilen – was tatsächlich geflossen ist (netto, Erstattungen
    #: zählen negativ).
    paid: Decimal

    @property
    def open(self) -> Decimal:
        """**Belegsumme − Gutschriften − Zahlungen.** Die eine Formel, jeder Fall darin."""
        return (self.total or Decimal("0")) - self.credited - self.paid

    @property
    def settled(self) -> bool:
        """Ist nichts mehr offen? Genau dann, wenn die Differenz null ist."""
        return self.open == Decimal("0")


def parse(value: Any, *, field: str, signed: bool = False) -> Decimal:
    """Ein Betrag – **als Decimal**, nie als ``float``.

    Er reist als String durch JSONB und aus der Numeric-Spalte heraus; wo es auf den
    Rappen ankommt, ist eine Fliesskommazahl der Anfang eines Rundungsfehlers, den niemand
    mehr findet.

    ``signed`` erlaubt negative Werte. Sie sind an genau einer Stelle richtig – bei der
    **Erstattung** – und überall sonst ein Tippfehler, der als Gutschrift durchginge.
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


def assert_kind(kind: Any) -> str:
    if kind in KINDS:
        return str(kind)
    raise ValueError(f"«{kind}» ist keine Art. Erlaubt: " + ", ".join(KINDS) + ".")


def assert_method(method: Any, *, kind: str) -> Optional[str]:
    """Der Weg – Pflicht bei einer Zahlung, **verboten** bei einer Gutschrift.

    Bei einer Gutschrift fliesst kein Geld; ein Weg daneben wäre eine Angabe über etwas,
    das nicht stattgefunden hat – dieselbe Regel wie ``Status.stock`` an einem Zustand,
    den kein Stück trägt.
    """
    if kind == CREDIT:
        if method:
            raise ValueError(
                "Eine Gutschrift hat keinen Zahlweg – es fliesst dabei kein Geld."
            )
        return None
    if method in METHODS:
        return str(method)
    raise ValueError(
        f"«{method}» ist kein Zahlweg. Erlaubt: " + ", ".join(METHODS) + "."
    )
