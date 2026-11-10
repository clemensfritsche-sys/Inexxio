"""**Der Beleg — Geld mit einer zweiten Partei, als Dokument gedacht.**

Der Fachkern des Prozessschrittmoduls «Zahlung» (``domain/modules.Beleg``): keine
Datenbank, kein Dienst. Einkauf, Verkauf, Spedition, Miete, Lohn, Gebühr und
Vorauszahlung sind alle **Geld mit einer zweiten Partei**; die Karte hat die Ordnung eines
Belegs (Kopf → Positionen → Konditionen → Angebote → Fordern · Begleichen) und wächst
Stufe um Stufe, statt einen zweiten Beleg daneben zu stellen.

**Dieses Modul bewegt keine Stücke** (Durchläufer, kein Ausgang, kein Ortswechsel) – darum
muss keine andere Regel von ihm wissen. **Ware · Forderung · Geld** sind unabhängige Achsen;
jedes Szenario ist eine andere Folge derselben Handlungen, keines ein Modus.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from . import currency as cur
from . import number

# ---------------------------------------------------------------------------
# ►►► DIE RICHTUNG — das eine Feld, aus dem alles Übrige folgt ◄◄◄
# ---------------------------------------------------------------------------

#: **Geld kommt herein** – wir stellen Rechnung.
IN = "in"
#: **Geld geht hinaus** – wir bekommen Rechnung.
OUT = "out"

# ---------------------------------------------------------------------------
# ►►► DIE STUFEN — DREI, weil drei Dinge unumkehrbar sind ◄◄◄
# ---------------------------------------------------------------------------
#
# **nichts zugesagt · zugesagt · berechnet.** ``DONE`` und ``CANCELLED`` sind Ausgänge,
# keine Stufen; das Geld ist eine Zeile, keine Stufe (reversibel, auch vor der Erfüllung).
# «Berechnet» ist unumkehrbar: Nummer vergeben, Steuer fest, Papier existiert.

OFFER = "offer"
AGREED = "agreed"
#: **Die Rechnung steht** – Nummer, Betrag, Steuer und Fälligkeit sind eingefroren.
BILLED = "billed"
DONE = "done"
CANCELLED = "cancelled"

STAGES: tuple[str, ...] = (OFFER, AGREED, BILLED)

# ---------------------------------------------------------------------------
# ►►► DER ANGEBOTSSPIEGEL — der Vorgang hat ZWEI Parteien ◄◄◄
# ---------------------------------------------------------------------------
#
# Je angefragter Partei eine Zeile (Zustand, Datum, Betrag, Fristen). ``CHOSEN`` entsteht
# durch die Zusage an dieser Zeile, nie durch Tippen.
ASKED, QUOTED, DECLINED, CHOSEN = "angefragt", "offeriert", "abgelehnt", "gewaehlt"

# ---------------------------------------------------------------------------
# ►►► DIE GELD-ZEILEN — die Forderung ist keine davon ◄◄◄
# ---------------------------------------------------------------------------
#
# Die Forderung ist der Beleg selbst (eine Rechnung je Modul). Geld-Zeilen: Zahlung (negativ =
# Erstattung), Ausbuchung, Trinkgeld (``ENTRY_KINDS``); «falsch erfasst» ist ihre Gegenbuchung
# (``reverses_id``), eine Minderung der Forderung ein eigener Beleg (``corrects_id``).

# ---------------------------------------------------------------------------
# ►►► WER DEN PREIS NENNT ◄◄◄
# ---------------------------------------------------------------------------
#
# Ausgabe: wir fragen an, er nennt den Preis. Einnahme: wir nennen ihn, er nimmt an oder
# lehnt ab. Wer nennt, füllt vor dem Hinausgehen; wer nicht nennt, ändert den Preis nicht.

#: **Wir** nennen den Preis (Einnahme).
BY_US = "us"
#: **Die Gegenpartei** nennt ihn (Ausgabe).
BY_PARTY = "party"

# ---------------------------------------------------------------------------
# ►►► DIE WÖRTER — was in beiden Richtungen gleich heisst, ist eine KONSTANTE ◄◄◄
# ---------------------------------------------------------------------------

#: Der andere im Geschäft – in beiden Richtungen; Singular = Plural, also keine Beugung.
PARTY = "Partner"

#: ►►► **Auf dem Beleg heissen die beiden nach dem MWSTG** ◄◄◄ – passend für jede Leistung
#: (auch Miete, Lohn, Gebühr) und wörtlich zum Reverse-Charge-Pflichtsatz.
SUPPLIER = "Von"
CUSTOMER = "An"
SUPPLIER_HINT = "Leistungserbringer: wer die Leistung erbringt und den Beleg stellt."
CUSTOMER_HINT = "Leistungsempfänger: wer die Leistung bezieht und bezahlt."

#: ►►► **Rechnungs- und Lieferadresse sind ZWEI Angaben – auf JEDER Seite.** ◄◄◄ Eine
#: Anschrift steht unter beiden, keine ohne Beschriftung. Beim Leistungserbringer heisst die
#: zweite **Versand**, beim Empfänger **Lieferung**.
BILLING_LABEL = "Rechnung"
SHIPPING_LABEL = "Lieferung"
SHIPPING_FROM_LABEL = "Versand"

#: Welche unserer Gesellschaften den Beleg stellt – vorgewählt, hier steht die Korrektur.
ISSUER_LABEL = "Unsere Gesellschaft"

#: **Ein Wort für den Storno – in jeder Stufe.** Vor der Zusage zieht er das Angebot zurück,
#: danach den Auftrag, nach der Rechnung entsteht die Gutschrift von selbst.
UNDO = "Stornieren"

# ---------------------------------------------------------------------------
# ►►► JEDE ZAHL IST EINE MENGE — das Vorzeichen sagt der BELEG, einmal ◄◄◄
# ---------------------------------------------------------------------------
#
# Wohin das Geld fliesst, sagen Richtung und Minderung (``corrects_id``). Was ein Mensch
# tippt, ist nie negativ; einzige Ausnahme ist die Gegenbuchung, die das System setzt.

#: Wie der Beleg heisst, der **fordert** – und wie der, der **mindert**.
INVOICE_NOUN = "Rechnung"
CREDIT_NOUN = "Gutschrift"
#: Wir stellen ihn aus ↔ wir erfassen einen fremden – zwei Bits, in allen vier Fällen Deutsch.
ISSUE_VERB = "stellen"
RECORD_VERB = "erfassen"

#: Zahlung ↔ Erstattung hängt daran, ob der Beleg mindert, nicht an der Richtung.
PAYMENT_NOUN = "Zahlung"
REFUND_NOUN = "Erstattung"

#: **Die drei Momente, die der Beleg erzählt** – Partizipien («vor 3 Tagen storniert»,
#: ``lib/when.happened``), nicht dasselbe wie die Beschriftung einer Stufe (``label_of``).
SENT_WORD = "offeriert"
TAKEN_WORD = "angenommen"
CANCELLED_WORD = "storniert"


def charge_word(*, collects: bool, minus: bool) -> str:
    """**Wie die Forderung entsteht** – «Rechnung stellen» … «Gutschrift erfassen».

    Der Belegkopf nennt keine Belegart; eine Gutschrift wird am Wort des Knopfs sichtbar.
    """
    return (f"{CREDIT_NOUN if minus else INVOICE_NOUN} "
            f"{ISSUE_VERB if collects else RECORD_VERB}")


def payment_word(*, minus: bool) -> str:
    """**Zahlung ↔ Erstattung erfassen.** Erfasst wird beides – das System überweist nichts."""
    return f"{REFUND_NOUN if minus else PAYMENT_NOUN} {RECORD_VERB}"


def inbound(*, collects: bool, minus: bool) -> bool:
    """►►► **Kommt das Geld zu UNS?** – die eine Ableitung aus Richtung und Minderung. ◄◄◄

    Nicht dasselbe wie ``collects`` (bei einer Gutschrift bleibt der Aussteller, das Geld
    fliesst andersherum). Sagt, ob ein Zahlungsdienst einzieht und ob ein Einzahlungsschein
    mit unserer Bankverbindung Sinn ergibt.
    """
    return collects != minus


#: Die Zahlung auslösen – gebucht wird erst, wenn der Dienst es meldet.
PAY_ONLINE_WORD = "Jetzt bezahlen"
#: Dasselbe rückwärts – zurück auf die Karte, über den Dienst, der sie belastet hat.
REFUND_ONLINE_WORD = "Online erstatten"

#: ►►► **Die Abschnitte der Karte** – in dieser Reihenfolge; Fordern und Begleichen sind EIN
#: Abschnitt «Rechnung» (Rechnung, Zahlungen, Saldo).
PARTIES_TITLE = "Parteien"
TERMS_TITLE = "Konditionen"
INVOICE_TITLE = "Rechnung"
DOCS_TITLE = "Dokumente"

#: ►►► **Zwei Fragen, zwei Angaben** (§9.15e). ◄◄◄
#:
#: * **Was ist zu tun?** – eine freiwillige Angabe am **Modul**; leer heisst «gemäss
#:   Spezifikation».
#: * **Wie bestellen?** – je Paarung Modul × Partner, Pflicht, nur wo **wir** bestellen
#:   (``party_ref``).
TASK = "Was ist zu tun?"
#: Mehr wäre ein Pflichtenheft – das gehört an die Spezifikation des Artikels.
MAX_TASK = 400

ORDER_REF = "Wie bestellen?"
ORDER_REF_HINT = "Seine Artikelnummer oder der Link zu seinem Shop"

#: Die Nummer, unter der die **Gegenpartei** diesen Geldfluss führt – nur wo sie von aussen
#: kommt.
PARTY_REFERENCE = "Rechnungsnummer"

#: ►►► **Die Überschriften des Belegs.** ◄◄◄ Über den Konditionen steht keine – die Zeilen
#: sagen selbst, was sie sind. Der Abschnitt «Angebote» ist ein Schritt (Punkt vor der
#: Überschrift).
GOODS_TITLE = "Positionen"
QUOTES_TITLE = "Angebote"

# ---------------------------------------------------------------------------
# ►►► DIE BEIDEN FRISTEN — eine Zahl, und die üblichen Werte haben Namen ◄◄◄
# ---------------------------------------------------------------------------
#
# **«Vorauszahlung» IST der Wert 0** – kein Schalter daneben; die freie Eingabe beginnt
# darum bei 1.

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

#: ►►► **Die Zoll-Angaben, wie sie am Artikel heissen** ◄◄◄ – ``ask_problem`` nennt sie,
#: wenn sie fehlen; auf dem Beleg steht die kurze Form (`Zolltarif` · `Ursprung`).
HS_CODE_LABEL = "Zolltarifnummer"
ORIGIN_LABEL = "Ursprungsland"
WEIGHT_LABEL = "Gewicht"
FREE_TERM_LABEL = "Individuell"


def prepaid(due_days: Optional[int]) -> bool:
    """►►► **Wartet dieses Modul auf das Geld?** – die eine Lesestelle. ◄◄◄

    Wer in null Tagen zahlbar stellt, liefert nicht vorher. ``None`` (keine Frist
    vereinbart) ist **nicht** Vorauszahlung.
    """
    return due_days == PREPAID_DAYS


# ---------------------------------------------------------------------------
# ►►► WIE BEZAHLT WURDE — drei Wege, und nur zwei tippt ein Mensch ◄◄◄
# ---------------------------------------------------------------------------
#
# Eine Angabe an der Zahlung, gebucht wird dieselbe Zeile. **Die Karte tippt niemand ab** –
# sie kommt über den Webhook des Zahlungsdienstes.
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


def assert_method(value: Any, *, card: bool = False) -> Optional[str]:
    """Eine **von Hand** erfasste Zahlungsart – oder ``None``.

    Die Karte, mit der **uns** jemand bezahlt, meldet nur der Zahlungsdienst; wo **wir**
    zahlen (``card=True``), ist es unsere Firmenkarte und wird von Hand erfasst.
    """
    if value in (None, ""):
        return None
    key = str(value)
    allowed = MANUAL_METHODS + ((CARD,) if card else ())
    if key not in allowed:
        raise ValueError(
            f"«{key}» lässt sich nicht von Hand erfassen – "
            f"möglich sind {', '.join(dict(METHODS)[m] for m in allowed)}.")
    return key


# ---------------------------------------------------------------------------
# ►►► STORNO ODER KORREKTUR — zwei Sachverhalte, zwei Wege ◄◄◄
# ---------------------------------------------------------------------------
#
# **Storno** (``UNDO``): der Vorgang gilt nicht (nach der Rechnung: Gutschrift über alles).
# **Korrektur**: ein eigener Beleg in eigenem Modul mit ``corrects_id``, dort, wo der Vorfall
# passiert (Retoure → Retourenauftrag).

#: **Der Verweis auf den geminderten Beleg** – Pflicht auf dem Papier (MWSTG Art. 26),
#: abgeleitet aus ``corrects_id``.
CORRECTS_LABEL = "Korrektur zu"
CORRECTS_HINT = ("Welche Rechnung dieser Beleg mindert – sie darf in einem anderen "
                 "Auftrag stehen: die Gutschrift gehört dorthin, wo die Ware zurückkommt.")

#: ►►► **Die Arten einer Geld-Zeile.** ◄◄◄ **Zahlung** (negativ = Erstattung),
#: **Ausbuchung** (Entgeltsminderung mit Grund, MWSTG Art. 41), **Trinkgeld** (zu viel
#: bezahlt und behalten, MWSTG Art. 24). Gelöscht wird keine (``reverses_id``).
PAYMENT = "payment"
WRITEOFF = "writeoff"
TIP = "tip"
ENTRY_KINDS: tuple[str, ...] = (PAYMENT, WRITEOFF, TIP)

#: **Warum ausgebucht wird** – rechtlich dieselbe Entgeltsminderung, das Wort sagt, was
#: geschah.
WRITE_OFF_REASONS: tuple[tuple[str, str], ...] = (
    ("rounding", "Rundung"),
    ("bank", "Bankspesen"),
    ("discount", "Skonto"),
    ("goodwill", "Kulanz"),
    ("loss", "Uneinbringlich"),
)
WRITE_OFF_WORD = "Ausbuchen"
REFUND_WORD = "Erstatten"
TIP_WORD = "Als Trinkgeld behalten"
REVERSE_WORD = "falsch erfasst?"
#: Nur das Wort an der Leiste hängt daran («Zu wenig bezahlt»); ausbuchen darf man jeden Rest.
SMALL_REST = Decimal("1.00")


def reason_label(key: Optional[str]) -> Optional[str]:
    """Das Wort zu einem Grund – ``None`` ohne Grund."""
    return dict(WRITE_OFF_REASONS).get(key or "")


def assert_reason(value: Any) -> str:
    """Ein Grund aus der Liste – sonst ein Fehler mit der Liste."""
    if value in dict(WRITE_OFF_REASONS):
        return str(value)
    raise ValueError("Ausbuchen braucht einen Grund: "
                     + ", ".join(label for _, label in WRITE_OFF_REASONS) + ".")


# ---------------------------------------------------------------------------
# ►►► GÜLTIGKEIT, EIGENTUM, DOKUMENTE, MAHNUNG ◄◄◄
# ---------------------------------------------------------------------------

#: **Wie lange eine Offerte gilt** – in Tagen ab «Anbieten»; danach ist «Annehmen» gesperrt.
VALID_DAYS = 30
VALID_LABEL = "Gültig"

#: ►►► **Wem die Stücke danach gehören** – Pflichtwahl ohne Vorbelegung. ◄◄◄ Gespeichert wird
#: nur die Wahl; das Eigentum ist eine Ableitung (``services/voucher.sold_units``), gelesen am
#: Ziel: «an die Partei» → *Verkauft*, sonst *Freigegeben*.
TO_PARTY = "party"
TO_US = "us"
OWNERSHIP: tuple[tuple[str, str], ...] = (
    (TO_PARTY, "geht an die Partei"),
    (TO_US, "geht an uns"),
)
OWNERSHIP_LABEL = "Eigentum"


def assert_days(key: str, value: Any) -> Optional[int]:
    """►► **Eine Frist in Tagen** (``payment_days`` · ``lead_days`` · ``valid_days``) – die EINE
    Regel für die Vorgabe am Modul und den Wert am Beleg: 0 bis 365, eine Offerte gilt mindestens
    einen Tag. Leer heisst «nicht gesetzt». ◄◄"""
    if value in (None, ""):
        return None
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"«{value}» ist keine Anzahl Tage.")
    if not 0 <= days <= 365:
        raise ValueError("Eine Frist liegt zwischen 0 und 365 Tagen.")
    if key == "valid_days" and days == 0:
        raise ValueError("Eine Offerte gilt mindestens einen Tag.")
    return days


def assert_ownership(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if value in dict(OWNERSHIP):
        return str(value)
    raise ValueError("Eigentum: " + ", ".join(label for _, label in OWNERSHIP) + ".")


#: ►►► **Die Dokumente, die hinausgehen** – je Art ihr Wort auf dem Papier. ◄◄◄ Eingefroren
#: bei jedem Versand (``services/a4``); nur, wo **wir** den Beleg stellen.
OFFER_DOC, CONFIRM_DOC, INVOICE_DOC = "offer", "confirmation", "invoice"
RECEIPT_DOC, STORNO_DOC, CREDIT_DOC, REMINDER_DOC = "receipt", "storno", "credit", "reminder"
DOCUMENTS: dict[str, str] = {
    OFFER_DOC: "Offerte",
    CONFIRM_DOC: "Auftragsbestätigung",
    INVOICE_DOC: "Rechnung",
    RECEIPT_DOC: "Quittung",
    STORNO_DOC: "Stornierung",
    CREDIT_DOC: "Gutschrift",
    REMINDER_DOC: "Mahnung",
}

#: ►►► **Die Mahnstufen** – drei, je zehn Tage Abstand, nichts geht von selbst. ◄◄◄ Die
#: Stufe ist die Zahl der gesendeten Mahnungen (Papiere im Feld ``voucher.doc``), keine Spalte.
REMIND_DAYS = 10
REMIND_LEVELS: tuple[str, ...] = ("Zahlungserinnerung", "2. Mahnung", "Letzte Mahnung")


def remind_word(level: int) -> str:
    """Wie die Mahnung der Stufe ``level`` (1–3) heisst."""
    return REMIND_LEVELS[max(1, min(level, len(REMIND_LEVELS))) - 1]


def document_word(kind: str, level: Optional[int] = None) -> str:
    """**Das Wort eines Papiers** – «Rechnung», bei einer Mahnung die ihrer Stufe."""
    if kind == REMINDER_DOC:
        return remind_word(level or 1)
    return DOCUMENTS.get(kind, "Beleg")

# ---------------------------------------------------------------------------
# ►►► DER ZUSTAND EINER FORDERUNG — abgeleitet, nie gespeichert
# ---------------------------------------------------------------------------
#
# Aus Rechnungsbetrag und Offenem, in den Tönen done · pending · danger. Eine Überzahlung ist
# ein negativer offener Betrag; verrechnet wird sie nie von selbst.

#: **Rundungstoleranz** – darunter gilt eine Forderung als beglichen (liegengebliebene Rappen
#: aus dem Ausland). Eine fachliche Entscheidung, darum hier und nicht in der Oberfläche.
SETTLED_TOLERANCE = Decimal("0.05")

#: Die Zustände einer Rechnung – Schlüssel, Wort, Ton.
INVOICE_STATES: dict[str, tuple[str, str]] = {
    "settled": ("Beglichen", "done"),
    "partial": ("Teilweise bezahlt", "pending"),
    "overdue": ("Überfällig", "danger"),
    "overpaid": ("Überzahlt", "danger"),
    "open": ("Offen", "pending"),
}


def invoice_state(total: Decimal, remaining: Decimal, *,
                  overdue: bool = False) -> dict[str, str]:
    """**Wie steht diese Rechnung?** – Schlüssel, Wort und Ampelton aus zwei Zahlen.

    ``total`` ist ihr Betrag, ``remaining`` was offen ist. Negativ heisst überzahlt (jede
    Zahl ist eine Menge); «Teilweise bezahlt» unterscheidet eine Anzahlung von nichts.
    """
    if abs(remaining) <= SETTLED_TOLERANCE:
        return _state("settled")
    if remaining < 0:
        return _state("overpaid")
    if overdue:
        return _state("overdue")
    if remaining + SETTLED_TOLERANCE < total:
        return _state("partial")
    return _state("open")


def _state(key: str) -> dict[str, str]:
    label, tone = INVOICE_STATES[key]
    return {"state": key, "state_label": label, "state_tone": tone}


@dataclass(frozen=True)
class Direction:
    """**Ein Beleg in EINER Richtung** – alles, was die beiden unterscheidet.

    Als Daten, nicht als ``if``; was in beiden Richtungen gleich lautet, ist eine Konstante.
    """

    key: str
    #: «Einnahme» · «Ausgabe» – bewusst nicht «Verkauf ↔ Einkauf» (Miete, Lohn, Gebühr).
    label: str
    #: Ein Satz, der sagt, was passiert. Er steht im Editor neben der Wahl.
    hint: str
    #: **Die beiden Stufen, wie sie in dieser Richtung heissen.**
    stage_labels: dict[str, str]
    #: **Wie man auf den Partner zugeht** – anfragen ↔ anbieten.
    ask_verb: str
    #: ►►► **Kassieren wir hier – oder zahlen wir?** ◄◄◄ Das eine Bit der Richtung: daraus
    #: folgen, wer den Preis nennt, wer den Beleg stellt (Leistungserbringer), wessen Nummer
    #: die Rechnung trägt und ob es die Frage «wie bestelle ich bei ihm?» gibt.
    collects: bool

    @property
    def quoted_by(self) -> str:
        """►►► **Wer den Preis nennt** – ``BY_US``, wo wir kassieren, sonst ``BY_PARTY``. ◄◄◄"""
        return BY_US if self.collects else BY_PARTY

    @property
    def reference(self) -> Optional[str]:
        """Wessen Nummer die Rechnung trägt – ``None`` = unsere, kein Feld; wo wir zahlen,
        die **seine** (sie steht auf seinem Papier, ``PARTY_REFERENCE``)."""
        return None if self.collects else PARTY_REFERENCE

    @property
    def party_ref(self) -> bool:
        """►►► **Gibt es die Frage «wie bestelle ich bei ihm?»** ◄◄◄ Nur, wo **wir** bestellen
        (``ORDER_REF``) – wo wir liefern, gibt es nichts zu bestellen."""
        return not self.collects

    def label_of(self, stage: str) -> str:
        """Wie diese Stufe heisst; die beiden Ausgänge heissen in beiden Richtungen gleich."""
        if stage == CANCELLED:
            return "Storniert"
        if stage == DONE:
            return "Erledigt"
        return self.stage_labels.get(stage, stage)

    # Der Kopf nennt keine Belegart; ``label_of`` dient Fehlermeldungen über die Stufe.


#: ►►► **Die eine Liste.** Eine dritte Richtung gibt es nicht – Geld kommt oder geht.
DIRECTIONS: dict[str, Direction] = {
    IN: Direction(
        key=IN,
        label="Einnahme",
        hint="Einnahme – wir stellen Rechnung, Geld kommt herein.",
        # Die Auftragsbestätigung IST die Stufe «zugesagt».
        stage_labels={OFFER: "Offerte", AGREED: "Auftragsbestätigung",
                      BILLED: "Rechnung"},
        ask_verb="Anbieten",
        collects=True,
    ),
    OUT: Direction(
        key=OUT,
        label="Ausgabe",
        hint="Ausgabe – wir bekommen Rechnung, Geld geht hinaus.",
        stage_labels={OFFER: "Anfrage", AGREED: "Bestellung",
                      # **Seine Rechnung** – sie entsteht bei ihm, wir schreiben sie ab.
                      BILLED: "Rechnung"},
        ask_verb="Anfragen",
        collects=False,
    ),
}


def of(direction: Optional[str]) -> Direction:
    """Die Richtung zu einem Wert. Unbekannt → **Ausgabe**, nicht ein Fehler.

    Lesen zerlegt keine Anzeige; geschrieben wird über ``assert_direction``.
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


# ---------------------------------------------------------------------------
# ►►► DER BETRAG — eine Stelle, an der aus Eingabe eine Zahl wird ◄◄◄
# ---------------------------------------------------------------------------

#: Die Obergrenze – gegen Tippfehler («100000» statt «1000.00»), die sonst als Zusage im Log
#: stünden.
MAX_AMOUNT = Decimal("99999999.99")


def amount(value: Any, code: str, *, allow_negative: bool = False) -> Optional[Decimal]:
    """Aus einer Eingabe ein Betrag – oder ``None``, wenn nichts dasteht.

    Gelesen über ``domain/number`` (Apostroph, Leerzeichen, Komma oder Punkt). ``allow_negative``
    nur an Geld-Zeilen – eine negative Zusage gibt es nicht.
    """
    try:
        found = number.decimal(value)
    except ValueError:
        raise ValueError(f"«{value}» ist kein Betrag.")
    if found is None:
        return None
    # Gerundet auf die kleinste Einheit DIESER Währung (KWD hat drei Stellen).
    found = cur.round_to(found, code)
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
# Satz und Steuerbetrag sind Pflicht (MWSTG Art. 26 Abs. 2 Bst. f); verschiedene Sätze stehen
# auf demselben Papier. ►►► **Ein Positionspreis ist NETTO, jeder Betrag BRUTTO.** ◄◄◄ Netto
# und Steuer sind Ableitungen. **Gerundet wird je Satz auf der SUMME**, nicht je Position.


@dataclass(frozen=True)
class VatRate:
    """Ein Steuersatz des Katalogs – Schlüssel, Zahl, Name und sein Pflichtsatz."""

    key: str
    #: Als **String** mit zwei Nachkommastellen, so wie gerechnet und verglichen wird.
    rate: str
    label: str
    #: Der Satz, der bei diesem Tatbestand auf dem Beleg **stehen muss** – sonst ``None``.
    note: Optional[str] = None


#: **Die Schweizer Sätze** – ein Katalog, keine freie Zahl. ►►► **Der Nullsatz trägt ZWEI
#: Tatbestände** ◄◄◄ (Export, Reverse Charge) mit je eigenem Pflichtsatz – gespeichert wird
#: darum der Schlüssel, nicht die Zahl.
VAT_RATES: tuple[VatRate, ...] = (
    VatRate("normal", "8.10", "Normalsatz"),
    VatRate("reduced", "2.60", "Reduziert"),
    VatRate("lodging", "3.80", "Beherbergung"),
    VatRate("export", "0.00", "Export",
            "Steuerfreie Ausfuhrlieferung"),
    VatRate("reverse", "0.00", "Reverse Charge",
            "Steuerschuldnerschaft des Leistungsempfängers"),
    VatRate("outside", "0.00", "Nicht im Inland steuerbar",
            "Ort der Dienstleistung im Ausland (MWSTG Art. 8 Abs. 1) – nicht im Inland steuerbar"),
)

_BY_KEY: dict[str, VatRate] = {v.key: v for v in VAT_RATES}

#: Womit eine neue Position beginnt. Der Normalfall ist der Normalsatz.
DEFAULT_VAT = "normal"

VAT_LABEL = "MWST"
#: Wann die Leistung erbracht wurde (MWSTG Art. 26 Abs. 2 Bst. c) – entscheidet die
#: Steuerperiode, nicht das Rechnungsdatum.
SERVICE_DATE_LABEL = "Leistungsdatum"


#: ►►► **Das Inland der Schweizer MWST** – die Schweiz und Liechtenstein (MWSTG Art. 3). ◄◄◄
HOME_COUNTRIES: frozenset[str] = frozenset({"CH", "LI"})
#: Was im Inland wählbar ist; im Ausland steht der Satz fest (Export bzw. Reverse Charge).
DOMESTIC_VAT: tuple[str, ...] = ("normal", "reduced", "lodging")
EXPORT_VAT = "export"
REVERSE_VAT = "reverse"
OUTSIDE_VAT = "outside"


def abroad(country: Optional[str]) -> bool:
    """Liegt diese Anschrift **ausserhalb** des MWST-Inlands? Ohne Land: nein – eine
    unbekannte Anschrift macht niemanden zum Exporteur."""
    code = (country or "").strip().upper()
    return bool(code) and code not in HOME_COUNTRIES


def vat_choices(*, service: bool, delivery_country: Optional[str],
                seat_country: Optional[str], business: bool = True) -> tuple[str, ...]:
    """►►► **Welche Sätze an einer Position wählbar sind – die Adresse entscheidet.** ◄◄◄

    **Ware** folgt der Lieferadresse (Ausland: Export, fest), eine **Dienstleistung** dem Sitz
    bzw. Wohnort des Empfängers (MWSTG Art. 8 Abs. 1, für Firmen UND Private). Ausland: eine
    Firma (``business``) rechnet die Steuer selbst ab – Reverse Charge, mit ihrer MWST-Nr.; eine
    Privatperson nicht – «nicht im Inland steuerbar», ohne Nummer. Im Inland: die drei Sätze.
    """
    if service:
        if not abroad(seat_country):
            return DOMESTIC_VAT
        return (REVERSE_VAT,) if business else (OUTSIDE_VAT,)
    return (EXPORT_VAT,) if abroad(delivery_country) else DOMESTIC_VAT


def vat_entry(value: Any) -> Optional[VatRate]:
    """Die Katalogzeile zu einem Wert – **tolerant**, denn Belege sind eingefroren.

    Schlüssel, oder eine Zahl («8.10», Altbestand: die erste Zeile mit diesem Satz – ein
    altes «0.00» wird darum Export), sonst ``None``.
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

    Zurück kommt der **Schlüssel**; eine Zahl wird umgesetzt. Gelesen wird tolerant
    (``vat_of``).
    """
    if value in (None, ""):
        return DEFAULT_VAT
    entry = vat_entry(value)
    if entry is None:
        # Unlesbar ist derselbe Fehler wie unbekannt – ein 400 mit Satz, kein 500.
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
    """Der **Netto**-Betrag einer Position: Menge × Einzelpreis. Ohne Preis: null.

    ►►► **Mit Teilbetrag gilt der Teilbetrag** (``part``, netto) – null heisst «nicht auf
    dieser Rechnung».
    """
    part = amount(line.get("part"), code, allow_negative=True)
    if part is not None:
        return part
    price = amount(line.get("price"), code, allow_negative=True)
    if price is None:
        return cur.round_to(Decimal(0), code)
    return cur.round_to(price * Decimal(int(line.get("quantity") or 0)), code)


def vat_split(lines: list[dict[str, Any]], code: str) -> list[dict[str, str]]:
    """►►► **Die Aufteilung je Steuersatz** – gerundet auf der Summe, nicht je Zeile. ◄◄◄

    Je Satz eine Zeile ``{vat, rate, label, note, net, tax}`` als **String**. Gruppiert nach
    Katalogzeile, nicht nach Zahl – Export und Reverse Charge bleiben getrennt.
    """
    zero = cur.round_to(Decimal(0), code)
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
    tax = cur.round_to(net * vat_of(key) / Decimal(100), code)
    return _describe(key, {"net": cur.money(net, code), "tax": cur.money(tax, code)})


def _describe(key: str, row: dict[str, str]) -> dict[str, str]:
    """Schlüssel · Zahl · Name · Pflichtsatz an eine Zeile schreiben – die Auskunft reist mit
    der eingefrorenen Zeile, statt später nachgeschlagen zu werden."""
    out = {"vat": key, "rate": f"{vat_of(key):.2f}", "label": vat_label(key), **row}
    note = vat_note(key)
    if note:
        out["note"] = note
    return out


def gross_of(lines: list[dict[str, Any]], code: str) -> Decimal:
    """Die **Brutto**-Summe der Positionen – Netto plus Steuer, je Satz gerundet."""
    return sum((Decimal(row["net"]) + Decimal(row["tax"])
                for row in vat_split(lines, code)), cur.round_to(Decimal(0), code))


def split_at(gross: Decimal, rate: Any, code: str) -> list[dict[str, str]]:
    """Die Aufteilung eines Brutto-Betrags zu **einem** Satz – die Ausgabe-Seite."""
    entry = vat_entry(rate)
    return [_at(gross, entry.key if entry is not None else f"{vat_of(rate):.2f}", code)]


def _at(gross: Decimal, key: str, code: str) -> dict[str, str]:
    """Brutto **rückwärts** in Netto und Steuer: ``netto = brutto / (1 + satz)``."""
    net = cur.round_to(gross / (Decimal(1) + vat_of(key) / Decimal(100)), code)
    return _describe(key, {"net": cur.money(net, code),
                           "tax": cur.money(gross - net, code)})


def less(rows: list[dict[str, str]], taken: list[dict[str, str]],
         code: str) -> list[dict[str, str]]:
    """**Eine Aufteilung abzüglich anderer** – je Satz Netto und Steuer, nie unter null (der
    Rest einer Rechnung, die Gutschriften schon minderten)."""
    zero = cur.round_to(Decimal(0), code)
    gone: dict[str, tuple[Decimal, Decimal]] = {}
    for r in taken:
        net, tax = gone.get(r["vat"], (zero, zero))
        gone[r["vat"]] = (net + Decimal(r["net"]), tax + Decimal(r["tax"]))
    out = []
    for r in rows:
        net, tax = gone.get(r["vat"], (zero, zero))
        out.append(_describe(r["vat"], {
            "net": cur.money(max(Decimal(r["net"]) - net, zero), code),
            "tax": cur.money(max(Decimal(r["tax"]) - tax, zero), code)}))
    return out


def totals(rows: list[dict[str, str]], code: str) -> dict[str, str]:
    """Netto · Steuer · Brutto einer Aufteilung – die drei Zahlen unter dem Strich."""
    zero = cur.round_to(Decimal(0), code)
    net = sum((Decimal(r["net"]) for r in rows), zero)
    tax = sum((Decimal(r["tax"]) for r in rows), zero)
    return {"net": cur.money(net, code), "tax": cur.money(tax, code),
            "gross": cur.money(net + tax, code)}


@dataclass(frozen=True)
class Balance:
    """**Die Rechnung dieses Belegs — lauter Ableitungen, null Spalten.**

    ``open = berechnet − gutgeschrieben + Trinkgeld − bezahlt − ausgebucht``; negativ heisst
    zu viel bekommen bzw. gezahlt.
    """

    agreed: Optional[Decimal]
    charged: Decimal
    #: Was ein Storno nach der Rechnung gutgeschrieben hat – null oder der Rest, den
    #: Gutschriften nicht schon minderten.
    credited: Decimal
    #: Zahlungen, Erstattungen abgezogen.
    paid: Decimal
    written_off: Decimal
    tips: Decimal
    open: Decimal

    @property
    def next_payment(self) -> Optional[Decimal]:
        """Was als Nächstes zu zahlen wäre – nie ein negativer Vorschlag."""
        return self.open if self.open > SETTLED_TOLERANCE else None

    @property
    def even(self) -> bool:
        """**Saldo null** – innerhalb der Rundungstoleranz."""
        return abs(self.open) <= SETTLED_TOLERANCE

    @property
    def settled(self) -> bool:
        """**Ist bezahlt, was zugesagt wurde?** – die Frage der Vorauszahlung; gemessen an der
        Zusage, nicht am offenen Betrag (ohne Rechnung wäre der null)."""
        return self.paid + SETTLED_TOLERANCE >= (self.agreed or Decimal("0"))


def balance(agreed: Optional[Decimal], charged: Optional[Decimal],
            entries: list[tuple[str, Decimal]], *,
            credited: Optional[Decimal] = None) -> Balance:
    """Zusage, Rechnung und Geld-Zeilen zu einem Saldo. **Die eine Rechenstelle.**

    ``entries`` sind ``(art, betrag)``; eine Gegenbuchung trägt dieselbe Art mit umgekehrtem
    Vorzeichen.
    """
    total = charged or Decimal("0")
    credit = credited or Decimal("0")
    sums = {k: Decimal("0") for k in ENTRY_KINDS}
    for kind, value in entries:
        sums[kind if kind in sums else PAYMENT] += value
    return Balance(
        agreed=agreed, charged=total, credited=credit,
        paid=sums[PAYMENT], written_off=sums[WRITEOFF], tips=sums[TIP],
        open=total - credit + sums[TIP] - sums[PAYMENT] - sums[WRITEOFF],
    )
