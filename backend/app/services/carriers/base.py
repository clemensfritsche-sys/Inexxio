"""**Der Frachtführer-Adapter — drei Fragen, kein Zustand** (PROCESS_CORE §15.5a).

Ein Adapter beantwortet, was **ausserhalb** des Systems passiert: was kostet ein
Transport, wie sieht sein Etikett aus, ist er angekommen. Er kennt **weder Auftrag noch
Modul noch Ort** – er bekommt zwei Anschriften und ein Paket.

**Er setzt nie einen Zustand.** Was er liefert, wird durch dieselbe Stelle geschrieben
wie ein im Portal getipptes Angebot (``awards.add_offer``); ein Adapter, der selbst
``angeboten`` schriebe, wäre der zweite Zyklus, den ADR 009 gerade verbietet. Das ist
auch der Grund, warum hier **keine** Vergabe vorkommt: die Naht ist bewusst schmal.

**Ohne Schlüssel gibt es den Adapter nicht.** ``available()`` ist die eine Antwort
darauf; einen Rückfall auf einen anderen Anbieter gibt es nicht – welcher Dritte fährt,
ist eine Entscheidung, und eine stille Ersatzwahl ist keine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Address:
    """Eine Anschrift, wie ein Frachtführer sie braucht.

    Sie kommt aus ``places.address_of`` – der **einen** Ableitung (verbotene Form V-6:
    zwei Ableitungen der Adressregel wären zwei Antworten auf dieselbe Sache).
    """

    name: str
    street: str
    zip: str
    city: str
    country: str          # ISO-2
    email: str = ""
    phone: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.street and self.zip and self.city and self.country)


@dataclass(frozen=True)
class Parcel:
    """Was transportiert wird – **abgeleitet**, nie eingegeben (K3).

    Masse in **cm**, Gewicht in **kg**. Beides ist eine Angabe des Systems und keine des
    Nutzers: sie steht am Artikel, und was eine Fuhre wiegt, ist die Summe über ihre
    Stücke. Eine Eingabe daneben wäre die zweite Wahrheit über dasselbe Paket.
    """

    weight_kg: Decimal
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal
    #: Gefahrgut – eine Eigenschaft des Artikels, die manche Anbieter ablehnen.
    hazmat: bool = False


@dataclass(frozen=True)
class CarrierOffer:
    """Ein Angebot eines Frachtführers.

    Es wird **nicht** hier gespeichert: der Aufrufer schreibt es über
    ``awards.add_offer`` – dieselbe Zeile wie ein von Hand eingetragenes Angebot. Genau
    das ist die Einsicht von ADR 009: **Rate-Shopping IST eine Ausschreibung.**
    """

    carrier: str
    service: str
    amount: Decimal
    currency: str
    #: Zugesagte Laufzeit in Tagen. ``None`` = nicht genannt – **nicht** «sofort».
    days: Optional[int] = None
    #: Wie der Anbieter dieses Angebot wiederfindet, wenn es gekauft wird.
    ref: str = ""


@dataclass(frozen=True)
class Quote:
    """Das Ergebnis eines Tarifabrufs.

    ``messages`` erklärt eine **leere** Liste (»Herkunftsland nicht unterstützt«,
    »Gefahrgut«). Ohne sie stünde da «keine Angebote», und niemand wüsste warum – und
    genau das ist der Unterschied zwischen einer Auskunft und einem Achselzucken.
    """

    offers: list[CarrierOffer] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    #: Manche Anbieter legen beim Abruf eine Sendung an, die der Kauf wiederfindet.
    shipment_ref: str = ""


@dataclass(frozen=True)
class Label:
    """Das gekaufte Etikett."""

    label_url: str
    tracking_number: str
    tracking_url: str = ""
    shipment_ref: str = ""


#: Was ein Frachtführer über eine **Sendung** sagen kann. Bewusst **drei** Werte: alles
#: Feinere (»im Zolllager«) ist Anzeige, keine Entscheidung.
#:
#: Und bewusst **andere Wörter** als die Vergabe-Zustände: hier geht es um die Sendung,
#: dort um den Vorgang. Eine unzustellbare Sendung macht die Vergabe **nicht**
#: automatisch «gescheitert» – das ist die Feststellung eines Menschen, mit Pflicht-Grund
#: (V6). Hiessen beide gleich, läse sich der Übergang wie eine Selbstverständlichkeit.
UNTERWEGS, ZUGESTELLT, UNZUSTELLBAR = "unterwegs", "zugestellt", "unzustellbar"


@dataclass(frozen=True)
class Tracking:
    state: str
    detail: str = ""

    @property
    def delivered(self) -> bool:
        return self.state == ZUGESTELLT


class Carrier(ABC):
    """Die Naht zu einem Frachtführer. Drei Fragen, mehr nicht."""

    key: str = "base"
    label: str = "Frachtführer"

    @abstractmethod
    def available(self) -> bool:
        """Ist dieser Anbieter einsatzbereit (Schlüssel vorhanden)?

        Nein heisst: **der Kanal ist nicht wählbar** – nicht «er scheitert später».
        """

    @abstractmethod
    def quote(self, sender: Address, receiver: Address, parcel: Parcel) -> Quote:
        """Tarife holen. Wirft bei einem echten Fehler des Anbieters (HTTP ≥ 400).

        Eine **leere** Angebotsliste ist kein Fehler – sie ist eine Antwort, und
        ``messages`` sagt warum.
        """

    @abstractmethod
    def buy(self, offer_ref: str, *, shipment_ref: str = "") -> Label:
        """Das gewählte Angebot kaufen → Etikett und Sendungsnummer."""

    @abstractmethod
    def track(self, tracking_number: str, *, carrier: str = "") -> Tracking:
        """Wo ist die Sendung? Die Antwort ist eine **Beobachtung**, kein Zustand."""
