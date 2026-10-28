"""**Der Beleg — Geld mit einer zweiten Partei, als Dokument gedacht.**

Der Fachkern des Prozessschrittmoduls «Zahlung» (``domain/modules.Beleg``): keine
Datenbank, kein Dienst.

## Warum es das gibt

Der kleinste gemeinsame Nenner von Einkauf, Verkauf, eingekaufter Spedition, Miete, Lohn,
Gebühr und Vorauszahlung ist **nicht die Ware**, sondern **Geld mit einer zweiten
Partei**. Die Karte ist darum ein Beleg, in der Ordnung, die ein Beleg seit Jahrhunderten
hat:

    Belegkopf → Positionen → Konditionen → Angebote → Fordern · Begleichen

Sie **wächst**: dieselben Zeilen eine Stufe weiter, nicht ein zweiter Beleg daneben.

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
# ►►► DIE STUFEN — DREI, weil drei Dinge unumkehrbar sind ◄◄◄
# ---------------------------------------------------------------------------
#
# **nichts zugesagt · zugesagt · berechnet.** ``DONE`` und ``CANCELLED`` sind **Ausgänge,
# keine Stufen** – man kommt dort an, statt hindurchzugehen. Und das **Geld** ist eine
# Zeile, keine vierte Stufe: eine Zahlung macht aus einer Rechnung keine andere, sie ist
# reversibel, und sie darf **vor** der Erfüllung stehen (Vorauszahlung) wie danach.
#
# **«Berechnet» ist eine Stufe, kein Zustand**: eine Rechnung zu stellen ist eine
# **Handlung mit unumkehrbarem Ergebnis** – eine Nummer ist vergeben, die Steuer steht
# fest, ein Papier existiert. Dieselbe Art Schwelle wie die Zusage. Der Beleg **ist** die
# Rechnung; «berechnet» ist der Moment, in dem er zu einer wird.

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
# Ein Beleg ist kein Formular, das eine Seite ausfüllt: jemand fragt, der andere nennt
# einen Preis, einer sagt zu. Je angefragter Partei eine Zeile – eine **Tabelle**, nicht
# eine Liste an einem Feld: eine Angebotszeile hat einen Zustand, ein Datum, einen Betrag
# und zwei Fristen, und das ist eine Sache, keine Eigenschaft.
#
# ``CHOSEN`` entsteht **nicht durch Tippen**, sondern dadurch, dass bei dieser Zeile
# zugesagt wurde – ein Zustand ist eine Folge.
ASKED, QUOTED, DECLINED, CHOSEN = "angefragt", "offeriert", "abgelehnt", "gewaehlt"

# ---------------------------------------------------------------------------
# ►►► DIE GELD-ZEILEN — die Forderung ist keine davon ◄◄◄
# ---------------------------------------------------------------------------
#
# Die **Forderung** ist der **Beleg selbst** (Nummer, Datum, Fälligkeit, Betrag, Steuer) –
# eine Rechnung je Modul ist damit die Struktur. Eine Geld-Zeile ist eine Zahlung (negativ =
# Erstattung), eine Ausbuchung oder ein Trinkgeld (``ENTRY_KINDS``); «falsch erfasst» ist ihre
# Gegenbuchung (``reverses_id``), eine Minderung der Forderung ein eigener Beleg
# (``corrects_id``).

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
SUPPLIER = "Von"
CUSTOMER = "An"
SUPPLIER_HINT = "Leistungserbringer: wer die Leistung erbringt und den Beleg stellt."
CUSTOMER_HINT = "Leistungsempfänger: wer die Leistung bezieht und bezahlt."

#: ►►► **Rechnungs- und Lieferadresse sind ZWEI Angaben – auf JEDER Seite, IMMER.** ◄◄◄
#: Steht nur eine Anschrift da, steht sie unter beiden (die Auskunft «an dieselbe»); steht
#: keine da, gibt es keine Beschriftung. Nur die zweite Beschriftung hängt an der Rolle:
#: beim Leistungserbringer geht die Ware ab (**Versand**), beim Empfänger kommt sie an
#: (**Lieferung**).
BILLING_LABEL = "Rechnung"
SHIPPING_LABEL = "Lieferung"
SHIPPING_FROM_LABEL = "Versand"

#: Welche unserer Gesellschaften den Beleg stellt – vorgewählt, hier steht die Korrektur.
ISSUER_LABEL = "Unsere Gesellschaft"

#: Was man an der Schwelle tut: die **Offerte** annehmen – der Auftrag ist das Ergebnis
#:. **Ein** Wort, weil es in beiden Richtungen dasselbe tut.
AGREE_VERB = "Offerte annehmen"
#: **Ein Wort für den Storno – in jeder Stufe.** Was er bewirkt, folgt aus der Stufe: vor
#: der Zusage zieht er das Angebot zurück, danach den Auftrag, nach der Rechnung entsteht
#: die Gutschrift von selbst.
UNDO = "Stornieren"

# ---------------------------------------------------------------------------
# ►►► JEDE ZAHL IST EINE MENGE — das Vorzeichen sagt der BELEG, einmal ◄◄◄
# ---------------------------------------------------------------------------
#
# **Der Betrag ist eine MENGE.** Wohin das Geld fliesst, sagen die **Richtung** und ob
# der Beleg **mindert** (``corrects_id``); darum stimmen alle Leser, die «grösser als null?»
# fragen, auch an einer Gutschrift. Was ein Mensch tippt, ist nie negativ – die eine
# Ausnahme, die Gegenbuchung einer Geld-Zeile, setzt das System.

#: Wie der Beleg heisst, der **fordert** – und wie der, der **mindert**.
INVOICE_NOUN = "Rechnung"
CREDIT_NOUN = "Gutschrift"
#: Was man mit ihm tut: **wir** stellen ihn aus ↔ wir schreiben einen **fremden** ab.
#: Zusammengesetzt aus **zwei Bits**; die Fuge ist ein Leerzeichen vor einem Infinitiv –
#: in allen vier Fällen richtiges Deutsch, anders als eine gerechnete Beugung.
ISSUE_VERB = "stellen"
RECORD_VERB = "erfassen"

#: Was auf das Konto kommt ↔ was zurückgeht. Es hängt an **einem** Bit – daran, ob der
#: Beleg mindert –, nicht an der Richtung: eine Lieferantenrechnung zu bezahlen ist eine
#: **Zahlung**, auch wenn das Geld hinausgeht.
PAYMENT_NOUN = "Zahlung"
REFUND_NOUN = "Erstattung"

#: **Die drei Momente, die der Beleg erzählt** – Partizipien in einem Satz («vor 3 Tagen
#: storniert», die Form steht in ``lib/when.happened``), darum klein und nicht dasselbe wie
#: die Beschriftung einer Stufe (``label_of``).
SENT_WORD = "offeriert"
TAKEN_WORD = "angenommen"
CANCELLED_WORD = "storniert"


def charge_word(*, collects: bool, minus: bool) -> str:
    """**Wie die Forderung entsteht** – aus zwei Bits, nicht aus einer Tabelle mit vieren.

    *«Rechnung stellen»* · *«Gutschrift stellen»* · *«Rechnung erfassen»* · *«Gutschrift
    erfassen»*. Das ist zugleich die Stelle, an der eine Gutschrift **sichtbar** wird: der
    Belegkopf nennt bewusst keine Belegart, also sagt es das Wort auf dem
    Knopf – dort, wo man handelt.
    """
    return (f"{CREDIT_NOUN if minus else INVOICE_NOUN} "
            f"{ISSUE_VERB if collects else RECORD_VERB}")


def payment_word(*, minus: bool) -> str:
    """**Zahlung ↔ Erstattung erfassen.** Ein Bit: mindert dieser Beleg?

    **Erfasst** wird beides – das System bucht eine Zeile, es überweist nichts.
    """
    return f"{REFUND_NOUN if minus else PAYMENT_NOUN} {RECORD_VERB}"


def inbound(*, collects: bool, minus: bool) -> bool:
    """►►► **Kommt das Geld zu UNS?** – die eine Ableitung aus Richtung und Minderung. ◄◄◄

    Sie ist **nicht** dasselbe wie ``collects``: wer den Beleg ausstellt, bleibt bei einer
    Gutschrift derselbe (wir schreiben unserem Kunden gut), nur fliesst das Geld
    andersherum. Also zwei Fragen, zwei Antworten – und diese hier beantwortet:

    * ob ein **Zahlungsdienst** hier etwas zu tun hat (er **zieht ein**, er überweist
      nicht in unserem Namen),
    * ob ein **Einzahlungsschein** Sinn ergibt (er trägt unsere Bankverbindung).

    Ein ``!=`` über zwei Bits ist das exklusive Oder, und damit stimmen alle vier Fälle
    ohne eine Fallunterscheidung.
    """
    return collects != minus


#: Die dritte Handlung am Geld: sie **auslösen**. «Erfassen» heisst *aufschreiben, was
#: geschehen ist*; hier geschieht es, und gebucht wird erst, wenn der Dienst es meldet.
PAY_ONLINE_WORD = "Jetzt bezahlen"
#: Dasselbe rückwärts – zurück auf die Karte, über den Dienst, der sie belastet hat.
REFUND_ONLINE_WORD = "Online erstatten"

#: ►►► **Die Abschnitte der Karte** – in dieser Reihenfolge. «Fordern» und «Begleichen» sind
#: EIN Abschnitt «Rechnung» (Rechnung, Zahlungen, Saldo): es ist eine Frage – was ist mit
#: dem Geld? –, und zwei Fächer zeigten dieselbe Zahl zweimal.
PARTIES_TITLE = "Parteien"
TERMS_TITLE = "Konditionen"
INVOICE_TITLE = "Rechnung"
DOCS_TITLE = "Dokumente"

#: ►►► **Zwei Fragen, zwei Angaben** (§9.15e). ◄◄◄
#:
#: * **Was ist zu tun?** («Härten auf 58 HRC») – eine Eigenschaft des **Moduls**: der Satz
#:   lautet für jeden Lieferanten gleich. Er ist darum **eine** Angabe am Modul und
#:   **freiwillig**: *was* es ist, sagt der Beleg über seine Positionen
#:   und deren Spezifikation – der Satz ergänzt nur, was ein Mensch weiss. **Leer heisst
#:   «gemäss Spezifikation»**, also eine vollständige Aussage und keine fehlende Angabe.
#: * **Wie bestellen?** (seine Artikelnummer, sein Shop-Link) – eine Eigenschaft der
#:   **Paarung** Modul × Partner, denn derselbe Lieferant führt je Teil eine andere Nummer.
#:   Sie bleibt **Pflicht**, gibt es aber nur, **wo wir bestellen** (``party_ref``).
#:
#: Damit steht bei einem Verkauf nur noch: *wem bieten wir an.* Was der Kunde bekommt,
#: sagen die Positionen; wann und wie geliefert wird, ist Sache des Bewegen-Moduls.
TASK = "Was ist zu tun?"
#: Mehr ist kein Arbeitsauftrag mehr, sondern ein Pflichtenheft – und das gehört an die
#: Spezifikation des Artikels, nicht auf einen Beleg.
MAX_TASK = 400

ORDER_REF = "Wie bestellen?"
ORDER_REF_HINT = "Seine Artikelnummer oder der Link zu seinem Shop"

#: Die Nummer, unter der die **Gegenpartei** diesen Geldfluss führt. Das Feld gibt es nur,
#: wo die Nummer von aussen kommt – eine, die **wir** vergeben, tippt niemand ab.
PARTY_REFERENCE = "Rechnungsnummer"

#: ►►► **Die Überschriften des Belegs.** ◄◄◄ Eine fehlt mit Absicht: über den Konditionen
#: stand «Konditionen», und die Zeilen darunter (Zahlungsfrist, Lieferfrist,
#: Lieferbedingung) sagen selbst, was sie sind.
#:
#: «Angebote» trägt unsere hinaus bzw. ihre herein; der Abschnitt **ist** ein
#: Schritt – sein Punkt vor der Überschrift sagt, wo der Beleg steht. *Wann offeriert
#: wurde* steht an ihm, *wann zugesagt wurde* an der Zeile mit dem Zuschlag.
GOODS_TITLE = "Positionen"
QUOTES_TITLE = "Angebote"

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

#: ►►► **Die beiden Zoll-Angaben – so, wie sie am Artikel heissen**. ◄◄◄
#:
#: Sie stehen hier, weil ``ask_problem`` sie **nennen** muss, wenn sie fehlen: «Ohne
#: Zolltarifnummer …» ist eine Auskunft, «Ohne hs_code …» eine Fehlermeldung an den
#: Entwickler. Auf dem Beleg steht die **kurze** Form daneben (`Zolltarif` · `Ursprung`) –
#: in einer Positionszeile hat der volle Name keinen Platz, und dort sagt der Wert selbst,
#: was er ist.
HS_CODE_LABEL = "Zolltarifnummer"
ORIGIN_LABEL = "Ursprungsland"
WEIGHT_LABEL = "Gewicht"
FREE_TERM_LABEL = "Individuell"


def prepaid(due_days: Optional[int]) -> bool:
    """►►► **Wartet dieses Modul auf das Geld?** – die eine Lesestelle. ◄◄◄

    Keine Einstellung, sondern die Bedeutung der vereinbarten Zahlungsfrist: wer in null
    Tagen zahlbar stellt, liefert nicht vorher. ``None`` heisst «keine Frist vereinbart»
    und damit **nicht** Vorauszahlung – ohne Angabe hat niemand über den Zeitpunkt
    gesprochen, und eine erfundene Sperre wäre schlimmer als keine.
    """
    return due_days == PREPAID_DAYS


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


def assert_method(value: Any, *, card: bool = False) -> Optional[str]:
    """Eine **von Hand** erfasste Zahlungsart – oder ``None``.

    **Die Karte, mit der UNS jemand bezahlt, wird abgewiesen**: sie meldet der
    Zahlungsdienst, und ein Mensch, der sie wählt, behauptet eine Buchung ohne Beleg. Wo
    **wir** zahlen (``card=True``), ist es unsere Firmenkarte – die erfasst man von Hand.
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
# **Storno** (``UNDO``): dieser Vorgang gilt nicht – nach der Rechnung entsteht die
# Gutschrift über die ganze Rechnung von selbst. **Korrektur**: die Leistung wurde gemindert –
# ein eigener Beleg in einem eigenen Modul, mit ``corrects_id`` auf die Rechnung, die er
# mindert, dort, wo der Vorfall passiert (Retoure → Retourenauftrag).

#: **Der Verweis auf den Beleg, den dieser hier mindert.** Er steht auf dem Papier
#: (MWSTG Art. 26: die Leistung und das Entgelt müssen eindeutig bestimmbar sein) und ist
#: eine **Ableitung** aus ``corrects_id`` – kein zweites Feld, das jemand abtippt.
CORRECTS_LABEL = "Korrektur zu"
CORRECTS_HINT = ("Welche Rechnung dieser Beleg mindert – sie darf in einem anderen "
                 "Auftrag stehen: die Gutschrift gehört dorthin, wo die Ware zurückkommt.")

#: ►►► **Die Arten einer Geld-Zeile.** ◄◄◄ Eine **Zahlung** (negativ = Erstattung), eine
#: **Ausbuchung** (kein Geld, eine Entgeltsminderung mit Grund – MWST anteilig korrigiert,
#: MWSTG Art. 41) oder ein **Trinkgeld** (zu viel bezahlt und behalten: Entgelt mit MWST zum
#: Satz der Rechnung, MWSTG Art. 24). Gelöscht wird keine – «falsch erfasst» ist eine
#: Gegenbuchung derselben Art (``reverses_id``).
PAYMENT = "payment"
WRITEOFF = "writeoff"
TIP = "tip"
ENTRY_KINDS: tuple[str, ...] = (PAYMENT, WRITEOFF, TIP)

#: **Warum ausgebucht wird** – rechtlich ist jeder Grund dieselbe Entgeltsminderung; das
#: Wort sagt dem Menschen und der Buchhaltung, was geschah.
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
#: **Klein heisst: offen lassen oder ausbuchen** – nur das Wort an der Leiste hängt daran
#: («Zu wenig bezahlt» statt «Teilweise bezahlt»); ausbuchen darf man jeden Rest.
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

#: **Wie lange eine Offerte gilt** – in Tagen ab «Anbieten». Danach ist sie abgelaufen:
#: «Annehmen» ist gesperrt, «Erneut anbieten» beginnt die Frist neu.
VALID_DAYS = 30
VALID_LABEL = "Gültig"

#: ►►► **Wem die Stücke danach gehören** – eine bewusste Wahl am Beleg, ohne Vorbelegung. ◄◄◄
#: Gespeichert wird nur die Wahl; wem ein Stück gehört, ist eine **Ableitung** (das jüngste
#: nicht stornierte Zahlungsmodul, das es passiert hat – ``services/voucher.sold_units``),
#: gelesen am Ziel des Auftrags: «an die Partei» → *Verkauft*, sonst *Freigegeben*.
TO_PARTY = "party"
TO_US = "us"
OWNERSHIP: tuple[tuple[str, str], ...] = (
    (TO_PARTY, "geht an die Partei"),
    (TO_US, "geht an uns"),
)
OWNERSHIP_LABEL = "Eigentum"


def assert_ownership(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if value in dict(OWNERSHIP):
        return str(value)
    raise ValueError("Eigentum: " + ", ".join(label for _, label in OWNERSHIP) + ".")


#: ►►► **Die Dokumente, die hinausgehen** – je Art ihr Wort auf dem Papier. ◄◄◄ Eingefroren
#: bei jedem Versand (``services/document``); nur, wo **wir** den Beleg stellen.
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
#: Stufe ist die Zahl der gesendeten Mahnungen (``voucher_documents``), keine Spalte.
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
# Eine Ableitung aus zwei Zahlen – Rechnungsbetrag und Offenes –, in den drei Tönen des
# Hauses (done · pending · danger). **Eine Überzahlung ist ein negativer offener Betrag**,
# kein eigenes Modell: zurück geht sie auf dem Weg, auf dem gezahlt wurde; verrechnet wird
# sie nie von selbst.

#: **Rundungstoleranz** – darunter gilt eine Forderung als beglichen.
#:
#: Bei einer Überweisung aus dem Ausland bleiben Rappen liegen; eine Rechnung, die wegen
#: drei Rappen für immer «offen» heisst, ist keine Auskunft, sondern eine Mahnliste voller
#: Geister. Die Zahl steht **hier** und nicht in der Oberfläche: sie ist eine fachliche
#: Entscheidung, keine Anzeigefrage – und wer mahnt, liest denselben Zustand.
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

    ``total`` ist ihr Betrag, ``remaining`` was von ihr offen ist.

    Der Beleg **ist** die Rechnung, also sind Betrag und Saldo dieselben zwei Zahlen:
    eine Frage, eine Antwort. Weil jede Zahl auf dem Beleg eine **Menge** ist
    (#1054–#1056), ist der Rest nur dann negativ, wenn **mehr geflossen** ist als
    gefordert – das ist genau «überzahlt».

    «Teilweise bezahlt» ist die Mitte: etwas ist eingegangen, aber nicht alles. Ohne sie
    sähe eine Rechnung, auf die eine Anzahlung eingegangen ist, genauso aus wie eine, auf
    die nichts eingegangen ist.
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

    Nur Felder, **keine Eigenschaft**: was in beiden Richtungen gleich lautet, steht als
    Konstante über dieser Klasse.

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
    #: ►►► **Gibt es hier die Frage «wie bestelle ich bei ihm?»** ◄◄◄ Nur, wo **wir**
    #: bestellen: beim Verkauf liefern wir, und eine Bestellangabe je Kunde wäre ein
    #: Pflichtfeld, das niemand ausfüllen kann (``ORDER_REF``).
    #:
    #: Es steht als **Eigenschaft der Richtung** und nicht als ``if`` im Dienst: so erbt
    #: jede künftige Richtung die Regel, und die Oberfläche fragt eine Angabe statt einen
    #: Schlüssel zu vergleichen.
    party_ref: bool

    def label_of(self, stage: str) -> str:
        """Wie diese Stufe heisst. Die beiden **Ausgänge** gehören beiden Richtungen
        gleich – sie sind keine Stufen, aber sie brauchen ein Wort."""
        if stage == CANCELLED:
            return "Storniert"
        if stage == DONE:
            return "Erledigt"
        return self.stage_labels.get(stage, stage)

    # **Eine Belegart nennt der Kopf nicht**; ``label_of`` gibt es, weil eine
    # **Fehlermeldung** über die Stufe die Stufe nennen darf.


#: ►►► **Die eine Liste.** Eine dritte Richtung gibt es nicht – Geld kommt oder geht.
DIRECTIONS: dict[str, Direction] = {
    IN: Direction(
        key=IN,
        label="Einnahme",
        hint="Einnahme – wir stellen Rechnung, Geld kommt herein.",
        # Die **Auftragsbestätigung IST diese Stufe**: sie hat Datum, Nummer, bestätigte
        # Positionen mit Preis und Satz und beide Fristen. Eine eigene Stufe wäre ein
        # **Zustand** in einer Reihe von **Schritten**, den man nicht *tut*.
        stage_labels={OFFER: "Offerte", AGREED: "Auftragsbestätigung",
                      BILLED: "Rechnung"},
        ask_verb="Anbieten",
        quoted_by=BY_US,
        reference=None,
        collects=True,
        # **Wir liefern** – es gibt nichts zu bestellen, also auch keine Bestellangabe.
        party_ref=False,
    ),
    OUT: Direction(
        key=OUT,
        label="Ausgabe",
        hint="Ausgabe – wir bekommen Rechnung, Geld geht hinaus.",
        stage_labels={OFFER: "Anfrage", AGREED: "Bestellung",
                      # **Seine Rechnung** – sie entsteht bei ihm, wir schreiben sie ab.
                      BILLED: "Rechnung"},
        ask_verb="Anfragen",
        quoted_by=BY_PARTY,
        # Seine Rechnung trägt **seine** Nummer – sie steht auf seinem Papier.
        reference=PARTY_REFERENCE,
        collects=False,
        # **Wir bestellen bei ihm** – und *wie*, führt er unter seiner eigenen Nummer.
        party_ref=True,
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


#: ►►► **Das Inland der Schweizer MWST** – die Schweiz und Liechtenstein (MWSTG Art. 3). ◄◄◄
HOME_COUNTRIES: frozenset[str] = frozenset({"CH", "LI"})
#: Was im Inland wählbar ist; im Ausland steht der Satz fest (Export bzw. Reverse Charge).
DOMESTIC_VAT: tuple[str, ...] = ("normal", "reduced", "lodging")
EXPORT_VAT = "export"
REVERSE_VAT = "reverse"


def abroad(country: Optional[str]) -> bool:
    """Liegt diese Anschrift **ausserhalb** des MWST-Inlands? Ohne Land: nein – eine
    unbekannte Anschrift macht niemanden zum Exporteur."""
    code = (country or "").strip().upper()
    return bool(code) and code not in HOME_COUNTRIES


def vat_choices(*, service: bool, delivery_country: Optional[str],
                seat_country: Optional[str]) -> tuple[str, ...]:
    """►►► **Welche Sätze an einer Position wählbar sind – die Adresse entscheidet.** ◄◄◄

    **Ware** folgt der **Lieferadresse**: im Ausland ist sie eine Ausfuhr, 0 % Export, fest.
    Eine **Dienstleistung** folgt dem **Sitz des Empfängers** (Empfängerortsprinzip, MWSTG
    Art. 8): im Ausland schuldet er die Steuer – Reverse Charge mit Pflichtvermerk, fest.
    Im Inland: Normal-, reduzierter oder Beherbergungssatz.
    """
    if service:
        return (REVERSE_VAT,) if abroad(seat_country) else DOMESTIC_VAT
    return (EXPORT_VAT,) if abroad(delivery_country) else DOMESTIC_VAT


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
    """Der **Netto**-Betrag einer Position: Menge × Einzelpreis. Ohne Preis: null.

    ►►► **Mit Teilbetrag gilt der Teilbetrag** (``part``, netto) – jedes Zahlungsmodul steht
    für sich und verrechnet, was dort steht; null heisst «nicht auf dieser Rechnung».
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

    Zurück kommt je vorkommendem Satz eine Zeile ``{vat, rate, label, note, net, tax}``
    als **String** – wo es auf den Rappen ankommt, wird nicht durch ``float`` gerechnet,
    auch nicht auf dem Weg durch JSON.

    **Gruppiert wird nach KATALOGZEILE, nicht nach Zahl** – sonst fielen *Export* und
    *Reverse Charge* zu einer Zeile zusammen (beide 0 %), und der Beleg nennte nur einen
    der beiden Rechtsgründe.
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

    ``open = berechnet − gutgeschrieben + Trinkgeld − bezahlt − ausgebucht``. Ein
    **negativer** offener Betrag ist eine Aussage: zu viel bekommen bzw. zu viel gezahlt.
    """

    agreed: Optional[Decimal]
    charged: Decimal
    #: Was ein Storno nach der Rechnung gutgeschrieben hat – null oder der ganze Betrag.
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
        """**Ist bezahlt, was zugesagt wurde?** – die Frage der Vorauszahlung.

        Gefragt wird nach der **Zusage**, nicht nach dem offenen Betrag: wer nichts
        berechnet hat, hat einen offenen Betrag von null – und das hiesse «bezahlt»,
        obwohl nie jemand etwas gefordert hat.
        """
        return self.paid + SETTLED_TOLERANCE >= (self.agreed or Decimal("0"))


def balance(agreed: Optional[Decimal], charged: Optional[Decimal],
            entries: list[tuple[str, Decimal]], *,
            credited: Optional[Decimal] = None) -> Balance:
    """Zusage, Rechnung und Geld-Zeilen zu einem Saldo. **Die eine Rechenstelle.**

    ``entries`` sind ``(art, betrag)`` – eine Gegenbuchung trägt dieselbe Art mit
    umgekehrtem Vorzeichen, die Summe stimmt damit ohne Sonderfall.
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
