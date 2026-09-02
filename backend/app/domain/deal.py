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
# ►►► DIE STUFEN — drei, weil drei Dinge unumkehrbar sind ◄◄◄
# ---------------------------------------------------------------------------
#
# nichts zugesagt · zugesagt · erledigt. «Preis steht» ist keine vierte – das ist der
# *Inhalt* der ersten Stufe. Und die **Zahlung** ist auch keine: sie steht als eigene
# Zeile daneben, ist reversibel (Teilzahlung, Erstattung) und darf in **jeder** Stufe
# passieren, auch nach einem Storno.

OFFER = "offer"
AGREED = "agreed"
DONE = "done"
CANCELLED = "cancelled"

STAGES: tuple[str, ...] = (OFFER, AGREED, DONE)

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
    #: Wie die Gegenpartei im Satz heisst («Kunde 100000001 ist nicht zugelassen»).
    party_word: str
    #: Der Plural – als **eigener Wert**, nicht als angehängtes «en». «Kunde» + «en»
    #: ergäbe «Kundeen»; deutsche Plurale sind nicht ableitbar.
    party_plural: str
    #: Die drei Stufen, wie sie in dieser Richtung heissen.
    stage_labels: dict[str, str]
    #: **Was man an der aktiven Stufe tut, um sie zu verlassen** – das Wort auf dem
    #: Knopf. Getrennt von der Beschriftung, weil der Zustand daneben steht
    #: («Zusagen» ↔ «Zugesagt»). Die letzte Stufe trägt keines: dort ist man angekommen.
    stage_verbs: dict[str, str]
    #: Wie der Storno heisst.
    undo: str
    #: Die beiden Geld-Zeilen, in der Sprache dieser Richtung.
    charge_word: str
    payment_word: str
    #: Das Wort für den offenen Betrag aus **unserer** Sicht.
    open_word: str

    def label_of(self, stage: str) -> str:
        """Wie diese Stufe heisst. Der Storno gehört beiden Richtungen gleich."""
        if stage == CANCELLED:
            return "Storniert"
        return self.stage_labels.get(stage, stage)


#: ►►► **Die eine Liste.** Eine dritte Richtung gibt es nicht – Geld kommt oder geht.
DIRECTIONS: dict[str, Direction] = {
    IN: Direction(
        key=IN,
        label="Einnahme",
        hint="Wir stellen Rechnung – Geld kommt herein.",
        party_word="Kunde",
        party_plural="Kunden",
        stage_labels={OFFER: "Angebot", AGREED: "Zusage", DONE: "Abgeschlossen"},
        stage_verbs={OFFER: "Zusagen", AGREED: "Abschliessen"},
        undo="Zusage stornieren",
        charge_word="Rechnung stellen",
        payment_word="Zahlungseingang",
        open_word="Offen",
    ),
    OUT: Direction(
        key=OUT,
        label="Ausgabe",
        hint="Wir bekommen Rechnung – Geld geht hinaus.",
        party_word="Lieferant",
        party_plural="Lieferanten",
        stage_labels={OFFER: "Anfrage", AGREED: "Beauftragt", DONE: "Abgeschlossen"},
        stage_verbs={OFFER: "Beauftragen", AGREED: "Abschliessen"},
        undo="Auftrag stornieren",
        charge_word="Rechnung erfassen",
        payment_word="Zahlung",
        open_word="Offen",
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
