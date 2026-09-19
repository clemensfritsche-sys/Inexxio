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
# ►►► DIE STUFEN — DREI, weil drei Dinge unumkehrbar sind ◄◄◄
# ---------------------------------------------------------------------------
#
# **nichts zugesagt · zugesagt · berechnet.** ``DONE`` und ``CANCELLED`` sind **Ausgänge,
# keine Stufen** – man kommt dort an, statt hindurchzugehen. Und das **Geld** ist eine
# Zeile, keine vierte Stufe: eine Zahlung macht aus einer Rechnung keine andere, sie ist
# reversibel, und sie darf **vor** der Erfüllung stehen (Vorauszahlung) wie danach.
#
# ►►► **Warum die dritte Stufe keine Wiederholung eines alten Fehlers ist.** ◄◄◄
#
# Hier standen einmal zwei, und «Abgeschlossen» war als dritte zu Recht entfallen: das war
# ein **Zustand** in einer Reihe von **Schritten** – man tut nichts, um ihn zu erreichen.
# Eine Rechnung zu stellen ist das Gegenteil: eine **Handlung mit einem unumkehrbaren
# Ergebnis** – eine Nummer ist vergeben, die Steuer steht fest, ein Papier existiert.
# Dieselbe Art Schwelle wie die Zusage.
#
# **Und sie ersetzt eine Zeile**: die Forderung war bis hierher ein Datensatz *im* Beleg,
# mit Betrag, Nummer, Datum, Fälligkeit und Steuer – also eine Kopie des Belegs, der sie
# enthielt. Jetzt **ist** der Beleg die Rechnung, und «berechnet» ist der Moment, in dem
# er zu einer wird.

OFFER = "offer"
AGREED = "agreed"
#: **Die Rechnung steht** – Nummer, Betrag, Steuer und Fälligkeit sind eingefroren.
BILLED = "billed"
DONE = "done"
CANCELLED = "cancelled"

STAGES: tuple[str, ...] = (OFFER, AGREED, BILLED)

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
# ►►► DIE GELD-ZEILEN — nur noch EINE Art: die ZAHLUNG ◄◄◄
# ---------------------------------------------------------------------------
#
# Hier standen zwei (``CHARGE`` · ``PAYMENT``), und die erste war die **Forderung**. Sie
# ist keine Zeile mehr, sondern der **Beleg selbst** – mit Nummer, Datum, Fälligkeit,
# Betrag und eingefrorener Steuer. Damit kann es sie nicht zweimal geben, und «eine
# Rechnung je Modul» ist keine Regel mehr, die jemand durchsetzt, sondern die Struktur.
#
# Übrig bleibt die **Zahlung**: eine Zeile Geld am Beleg, negativ = Erstattung. Ein
# ``kind`` daneben wäre ein Feld mit genau einem Wert.
#
# ►►► **Und damit gibt es keine Gegenbuchung mehr** – die Korrektur ist ein **eigener
# Beleg** in einem eigenen Modul (``corrects_id``), dort, wo der Vorfall passiert. ◄◄◄

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

#: ►►► **Rechnungs- und Lieferadresse sind ZWEI Angaben – auf JEDER Seite, IMMER**
#: (Testnotizen #952/#975). ◄◄◄
#:
#: *«Mir gefällt das ziemlich gut mit Rechnungsadresse, Lieferadresse usw. Ich möchte, dass
#: du das auch auf dem Leistungserbringer machst – also standardmässig immer bei
#: Informationen ausweisen, global etablieren, auch wenn sie zweimal das Gleiche anzeigt.
#: Eine Logik für alles, Komplexität und If/Else verringern.»*
#:
#: Bis hierher standen die Beschriftungen **nur, wo sich die beiden unterscheiden**, und
#: **nur** auf der Gegenseite. Das waren zwei Bedingungen für eine Frage, die ein Beleg
#: immer gleich beantwortet: *wohin die Rechnung, wohin die Ware.* Steht nur eine Anschrift
#: da, ist die Antwort «an dieselbe» – und die auszusprechen ist keine Doppelung, sondern
#: die Auskunft; sie wegzulassen hiess, den Leser raten zu lassen, welche der beiden Fragen
#: die eine Zeile beantwortet.
#:
#: Erfunden wird weiterhin nichts: die zweite Zeile entsteht aus Angaben, die am Benutzer
#: stehen (Rechnungsadresse ≠ Hauptadresse). Wo **gar keine** Anschrift dasteht, gibt es
#: auch keine Beschriftung – dort sagt die Seite, dass sie fehlt.
#:
#: *Die physische Lieferung selbst bleibt Sache des Bewegen-Moduls – hier steht die
#: **Anschrift auf dem Beleg**, nicht der Transport.*
#:
#: ►►► **Und die zweite Beschriftung hängt an der ROLLE** (Testnotiz #979). ◄◄◄
#:
#: *«Beim Leistungserbringer wäre es evtl. besser/richtiger zu sagen Absendeadresse oder
#: so? Etabliere hier korrektes.»* – Richtig gesehen: «Lieferadresse» heisst *wohin
#: geliefert wird*, und beim **Leistungserbringer** stand damit an seiner eigenen Adresse,
#: man möge ihm dorthin liefern – während er derjenige ist, der liefert. Von seiner Seite
#: aus ist es die Adresse, von der die Ware **abgeht**: im Handel, in der Logistik und im
#: Zoll heisst sie **Versandadresse** (der Versender ist die Gegenrolle des Empfängers).
#:
#: **Nur diese eine Beschriftung ist rollenabhängig**, und das ist Absicht: die
#: «Rechnungsadresse» beantwortet auf beiden Seiten dieselbe Frage – *welche Anschrift
#: gilt in Rechnungssachen* (wohin sie geht ↔ von wo sie kommt) –, und sie steht so auch
#: auf jedem gedruckten Beleg. Ein zweites Wort dafür wäre eine Unterscheidung ohne
#: Unterschied.
BILLING_LABEL = "Rechnungsadresse"
SHIPPING_LABEL = "Lieferadresse"
SHIPPING_FROM_LABEL = "Versandadresse"

#: Welche unserer Gesellschaften den Beleg stellt – vorgewählt, hier steht die Korrektur.
ISSUER_LABEL = "Unsere Gesellschaft"
#: ►►► **Die Nummer steht NEBEN dem Namen** (Testnotiz #940) – und braucht darum keine
#: eigene Beschriftung mehr: «Name Nummer» ist die Form, in der dieses Haus einen
#: Datensatz nennt (#933). Die frühere eigene Zeile mit dem Mikro-Label «Nr.» ist
#: ersatzlos entfallen; sie stand vier Zeilen unter dem Namen, zu dem sie gehört.

#: Was man an der Schwelle tut: das **Angebot** annehmen – der Auftrag ist das Ergebnis.
#: ►►► **«Offerte annehmen»** (Testnotiz #966). ◄◄◄ *«Einheitliches Wording.»* – Der Beleg
#: heisst in dieser Richtung «Offerte» (``stage_labels``), und der Knopf nahm bis hierher
#: ein «Angebot» an, das auf dem Papier nirgends steht. Es ist **ein** Wort, weil es in
#: beiden Richtungen dasselbe tut; wie der Beleg heisst, sagt die Stufe.
AGREE_VERB = "Offerte annehmen"
#: Was man tut, wenn nichts mehr davorsteht. Ein *Vorgang* ist dieser Beleg – das Wort
#: verwechselt sich mit nichts, «Auftrag erledigt» meinte den ERP-Datensatz.
FINISH_VERB = "Vorgang abschliessen"
#: Die eine Gegenhandlung.
UNDO = "Auftrag stornieren"
#: ►►► **Und im Angebot heisst es anders** (Testnotiz #957). ◄◄◄ Vor der Zusage ist kein
#: Auftrag da, den man stornieren könnte – hinausgegangen ist ein Angebot. Das Wort hängt
#: damit an der **Stufe**, nicht an der Richtung: in beiden Richtungen bricht man denselben
#: Vorgang ab, und ein Wert je Richtung wäre einer, den man falsch setzen kann.
UNDO_AT = {OFFER: "Vorgang abbrechen", AGREED: UNDO, BILLED: UNDO}


def undo_word(stage: str) -> str:
    """Wie die Gegenhandlung in **dieser** Stufe heisst – die eine Auflösung."""
    return UNDO_AT.get(stage, UNDO)

#: ►►► **«Rechnung STELLEN» ↔ «Rechnung ERFASSEN» — zwei Vorgänge, zwei Wörter.** ◄◄◄
#:
#: Bis hierher hiess beides «Rechnung erfassen», und das ist kein Geschmack, sondern eine
#: Verwechslung: bei einer **Einnahme** entsteht der Beleg **hier** und geht hinaus; bei
#: einer **Ausgabe** schreiben wir ab, was der Lieferant uns geschickt hat. Ein Wort für
#: beides lässt den einen Fall wie den anderen aussehen – und ausgerechnet der, in dem
#: eine Rechnungsnummer vergeben wird, klang nach Abtippen.
#:
#: Es ist damit die eine Angabe der Richtung an dieser Stelle (``Direction.charge_verb``);
#: **erfasst** wird die Zahlung weiterhin in beiden Richtungen – das System bucht eine
#: Zeile, es überweist nichts.
CHARGE_ISSUE = "Rechnung stellen"
CHARGE_RECORD = "Rechnung erfassen"
PAYMENT_WORD = "Zahlung erfassen"
#: Und die dritte Handlung am Geld: sie **auslösen**. «Erfassen» heisst *aufschreiben, was
#: geschehen ist*; hier geschieht es, und gebucht wird erst, wenn der Dienst es meldet.
PAY_ONLINE_WORD = "Jetzt bezahlen"
#: ►►► **«Offen» steht nicht mehr an der Saldo-Zeile** (Testnotiz #997). ◄◄◄ Hier stand
#: dafür ein eigenes Wort (``OPEN_WORD``); den Zustand trägt jetzt die **Farbe** des
#: Betrags, und wo ein Wort gebraucht wird (Hover, Guthaben), kommt es aus
#: ``CHARGE_STATES`` – dieselbe Liste, die auch die einzelne Forderung benennt. Zwei
#: Literale für dasselbe Wort waren die Stelle, an der eines beim Umbenennen stehenbleibt.

#: ►►► **ZWEI Fächer statt einer Liste aus Knöpfen.** ◄◄◄
#:
#: *«Zu komplex, zu unstrukturiert, zu wirr, zu viele Optionen, die sich gegeneinander
#: stören.»* – Gezählt: an einer Rechnung standen bis zu sechs gleich aussehende Knöpfe,
#: und sie bedeuteten **drei** verschiedene Dinge (eine Buchung · eine Korrektur · eine
#: blosse Auskunft). Dazu standen **zwei Rollen** in einer Zeile: «Rechnung erfassen» ist
#: unsere Handlung, «Jetzt bezahlen» die des Zahlenden.
#:
#: Es sind aber nur **zwei Fragen**, und jede gehört genau einer Seite:
#:
#: * **Fordern** – *was schuldet uns jemand?* Gehört uns: stellen, stornieren, gutschreiben.
#: * **Begleichen** – *wie kommt das Geld hierher?* Gehört dem Zahlenden: bar · Überweisung
#:   · Karte.
#:
#: Dazwischen steht die Zeile «Offen». Wer welches Fach bedienen darf, weiss ``can``
#: längst – es wurde bloss nicht dargestellt. Der frühere gemeinsame Titel
#: («Rechnung & Zahlung») ist damit entfallen: er fasste zwei Fragen zu einer Überschrift
#: zusammen, und genau daraus kam die Unordnung.
CLAIM_TITLE = "Fordern"
SETTLE_TITLE = "Begleichen"

#: ►►► **EIN Feld stellte ZWEI Fragen – darum sind es jetzt zwei.** ◄◄◄
#:
#: *«Bei Einkaufsteilen ist es oft ‹gemäss Spezifikation›, aber wenn ein intern gefertigtes
#: Teil auswärts nachbearbeitet werden muss, soll dieses Feld dafür genutzt werden … bei
#: der Verkaufsabwicklung habe ich keine Ahnung, was ich dort reinschreiben soll. Es ist
#: ein Mussfeld – die Logik geht bei Verkaufsteilen nicht auf.»*
#:
#: Und das stimmt, weil die Pflichtangabe je Partner **zwei verschiedene Dinge** meinte:
#:
#: * **Was ist zu tun?** («Härten auf 58 HRC») – eine Eigenschaft des **Moduls**: der Satz
#:   lautet für jeden Lieferanten gleich, stand aber n-mal da. Er ist darum **eine** Angabe
#:   am Modul und **freiwillig**: *was* es ist, sagt der Beleg längst über seine Positionen
#:   und deren Spezifikation – der Satz ergänzt nur, was ein Mensch weiss. **Leer heisst
#:   «gemäss Spezifikation»**, also eine vollständige Aussage und keine fehlende Angabe.
#: * **Wie bestellen?** (seine Artikelnummer, sein Shop-Link) – eine Eigenschaft der
#:   **Paarung** Modul × Partner, denn derselbe Lieferant führt je Teil eine andere Nummer.
#:   Sie bleibt **Pflicht**, gibt es aber nur, **wo wir bestellen** (``party_ref``).
#:
#: Damit steht bei einem Verkauf nur noch: *wem bieten wir an.* Was der Kunde bekommt,
#: sagen die Positionen; wann und wie geliefert wird, ist Sache des Bewegen-Moduls.
TASK = "Was ist zu tun?"
TASK_HINT = "Ergänzung zu den Positionen – leer heisst «gemäss Spezifikation»"
#: Mehr ist kein Arbeitsauftrag mehr, sondern ein Pflichtenheft – und das gehört an die
#: Spezifikation des Artikels, nicht auf einen Beleg.
MAX_TASK = 400

ORDER_REF = "Wie bestellen?"
ORDER_REF_HINT = "Seine Artikelnummer oder der Link zu seinem Shop"

#: Die Nummer, unter der die **Gegenpartei** diesen Geldfluss führt. Das Feld gibt es nur,
#: wo die Nummer von aussen kommt – eine, die **wir** vergeben, tippt niemand ab.
PARTY_REFERENCE = "Zahlungsreferenz des Partners"

#: ►►► **Die Überschriften des Belegs.** ◄◄◄ Eine fehlt mit Absicht: über den Konditionen
#: stand «Konditionen», und die Zeilen darunter (Zahlungsfrist, Lieferfrist,
#: Lieferbedingung) sagen selbst, was sie sind (Testnotiz #926).
#:
#: **«Rückläufe» heisst jetzt «Angebote»** (#946): der Abschnitt trägt die Angebote –
#: unsere hinaus bzw. ihre herein –, und «Rücklauf» beschreibt davon höchstens die
#: Hälfte. Weglassen wäre das andere gewesen, aber der Abschnitt **ist** ein Schritt:
#: sein Punkt vor der Überschrift sagt, wo der Beleg steht.
GOODS_TITLE = "Positionen"
QUOTES_TITLE = "Angebote"
#: ►►► **Eine «Chronik» gibt es nicht mehr** (Testnotiz #970). ◄◄◄
#:
#: *«Die Chronik kann hier vollständig und gänzlich entfallen. Ich möchte die Information
#: dort darstellen, wo sie eigentlich angezeigt werden.»* – Und das ist richtig: sie zählte
#: **zwei Daten** auf, die beide einen eigenen Ort haben. *Wann offeriert wurde* gehört an
#: den Abschnitt «Angebote», *wann zugesagt wurde* an die Zeile, bei der zugesagt wurde.
#: Ein eigener Abschnitt darunter wiederholte sie in anderer Form – und ausgerechnet in
#: der ärmeren: als nacktes Datum statt als Aussage («vor 3 Tagen»).

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

#: ►►► **Die beiden Zoll-Angaben – so, wie sie am Artikel heissen** (Testnotiz #964). ◄◄◄
#:
#: Sie stehen hier, weil ``_assert_complete`` sie **nennen** muss, wenn sie fehlen: «Ohne
#: Zolltarifnummer …» ist eine Auskunft, «Ohne hs_code …» eine Fehlermeldung an den
#: Entwickler. Auf dem Beleg steht die **kurze** Form daneben (`Zolltarif` · `Ursprung`) –
#: in einer Positionszeile hat der volle Name keinen Platz, und dort sagt der Wert selbst,
#: was er ist.
HS_CODE_LABEL = "Zolltarifnummer"
ORIGIN_LABEL = "Ursprungsland"
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
# ►►► STORNO ODER KORREKTUR — zwei Sachverhalte, zwei Wege ◄◄◄
# ---------------------------------------------------------------------------
#
# Hier standen zwei **Wörter für dieselbe Buchung** (``STORNO_WORD``/``CREDIT_WORD``),
# unterschieden durch eine Zahl: bezahlt ↔ unbezahlt. Das war die Stelle, an der zwei
# verschiedene Sachverhalte so taten, als wären sie einer:
#
# * **Storno** – *diese Rechnung war falsch, sie gilt nicht.* Derselbe Vorgang, kein
#   neues Geschäft. Das ist ``unbill``: solange der Beleg nicht hinausgegangen ist und
#   nichts darauf geflossen, wird er zurückgenommen – spurlos nach aussen.
# * **Korrektur** – *die Rechnung war richtig, die Leistung wurde gemindert.* Ein
#   **neuer** Geschäftsvorfall mit eigenem Datum, eigener Ware und eigener Steuerperiode:
#   ein **eigener Beleg in einem eigenen Modul**, mit ``corrects_id`` auf den, den er
#   mindert – und er steht dort, wo der Vorfall passiert (Retoure → Retourenauftrag).
#
# Damit entscheidet niemand mehr zwischen den beiden Wörtern: der **Zeitpunkt** tut es.
#
# *Nebenbei behoben: ``CREDIT_WORD`` stand zweimal in dieser Datei («Gutschrift» und, 130
# Zeilen weiter, «Guthaben»). Die zweite Zuweisung gewinnt beim Laden des Moduls – also
# hiess der Knopf seit #997 still «Guthaben». Ein Name, der zweimal vergeben wird, ist
# kein Tippfehler, sondern eine Stelle, an der zwei Bedeutungen denselben Platz haben.*
REFUND_ONLINE_WORD = "Online erstatten"

#: ►►► **Die drei Handlungen an der Rechnung.** ◄◄◄
#:
#: *stellen* → *versenden*, und dazwischen die Gegenhandlung. Sie ist dieselbe Anatomie
#: wie ``ask``/``unask``: **jede Zusage nach aussen hat ihre Gegenhandlung an derselben
#: Stelle** – und sie endet genau dort, wo der Beleg wirklich hinausgeht.
ISSUE_WORD = "Rechnung ist versendet"
UNBILL_WORD = "Rechnung zurücknehmen"
#: Was an einer zurückgenommenen Zeile steht – sie bleibt als Nachweis, dass die Nummer
#: vergeben **war**: eine Serie muss lückenlos *belegbar* sein, nicht lückenlos gezählt.
WITHDRAWN_NOTE = "zurückgenommen"

#: **Der Verweis auf den Beleg, den dieser hier mindert.** Er steht auf dem Papier
#: (MWSTG Art. 26: die Leistung und das Entgelt müssen eindeutig bestimmbar sein) und ist
#: eine **Ableitung** aus ``corrects_id`` – kein zweites Feld, das jemand abtippt.
CORRECTS_LABEL = "Korrektur zu"
CORRECTS_HINT = ("Welche Rechnung dieser Beleg mindert – sie darf in einem anderen "
                 "Auftrag stehen: die Gutschrift gehört dorthin, wo die Ware zurückkommt.")

#: **Die Kleinbetragstoleranz** – bis hierher darf ein Restsaldo als Differenz ausgebucht
#: werden.
#:
#: ►►► **Sie ist eine Erlaubnis, kein Automatismus.** ◄◄◄ Ausgebucht wird nichts von
#: selbst: das System **bietet** die Zeile an, ein Mensch bucht sie. Eine automatische
#: Ausbuchung wäre eine Forderung, die verschwindet, ohne dass jemand es entschieden hat –
#: und genau das ist der Unterschied zwischen einer Toleranz und einem Datenverlust.
#:
#: **Nicht zu verwechseln mit `SETTLED_TOLERANCE`**: die sagt, ab wann eine Rechnung
#: *beglichen heisst* (drei Rappen sind keine Mahnung wert); diese hier sagt, bis wohin
#: man die Differenz **wegbuchen darf**. Zwei Fragen, zwei Zahlen.
#:
#: ►►► **Gebucht wird sie als ZAHLUNG mit Vermerk.** ◄◄◄ Sie war eine negative Forderung –
#: und die gibt es nicht mehr, seit der Beleg selbst die Rechnung ist. Eine Zahlung ist
#: hier ohnehin definiert als *was den offenen Betrag mindert*, und der Vermerk sagt, dass
#: kein Geld geflossen ist. Ein dritter Zeilentyp für achtzig Rappen wäre ein Mechanismus
#: für einen Rundungsfehler.
WRITE_OFF_LIMIT = Decimal("1.00")
WRITE_OFF_WORD = "Differenz ausbuchen"
WRITE_OFF_NOTE = "Rundungsdifferenz"


# ---------------------------------------------------------------------------
# ►►► DER ZUSTAND EINER FORDERUNG — abgeleitet, nie gespeichert (Testnotiz #991)
# ---------------------------------------------------------------------------
#
# *«Bitte definiere die Zahlungsstatus-Semantik inkl. Überzahlung.»*
#
# **Es ist eine Ableitung aus zwei Zahlen** – dem Betrag der Rechnung und dem, was von ihr
# offen ist. Ein gespeichertes Zustandsfeld daneben wäre die zweite Wahrheit, und die eine
# vergessene Nachzieh-Stelle fällt erst auf, wenn jemand mahnt.
#
# **Und die Töne sind die drei des Hauses** (``status-flow.TONE``): *done* = erledigt ·
# *pending* = offen · *danger* = Problem. Eine vierte Farbe für Geld wäre eine zweite
# Farbsprache – und ein Zustand, den niemand sonst im ERP lesen kann.
#
# ►►► **Die Überzahlung ist ein GUTHABEN, und dafür braucht es nichts Neues.** ◄◄◄
#
# Wer zu viel bezahlt hat, hat einen **negativen offenen Betrag** – die Zahl steht bereits
# da, mit Vorzeichen und in derselben Spalte. Eine eigene Guthaben-Tabelle wäre ein zweites
# Modell für eine Zahl, die schon dasteht, und sie müsste bei jeder Buchung nachgezogen
# werden. Zurückgezahlt wird über den Weg, auf dem gezahlt wurde: eine gewöhnliche
# **negative Zahlung** (bar, Überweisung) bzw. ``refund_online`` (Karte) – beides gibt es
# längst. Verrechnet wird ein Guthaben **nicht automatisch**: welche Rechnung es mindern
# soll, weiss nur ein Mensch.

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

    ►►► **Eine Funktion, nicht zwei.** ◄◄◄ Hier standen ``charge_state`` (je Forderungs-
    Zeile) und ``balance_state`` (über den Saldo des Belegs) nebeneinander – zwei
    Ableitungen mit geteilten Wörtern und geteilter Toleranz, weil ein Beleg mehrere
    Forderungen tragen konnte und die Summe eine eigene Aussage war. Seit der Beleg **die**
    Rechnung ist, sind Betrag und Saldo dieselben zwei Zahlen: eine Frage, eine Antwort.
    Der frühere Saldo-Zustand «Guthaben» ist damit derselbe wie «Überzahlt».

    ►►► **Gerechnet wird mit dem VORZEICHEN, nicht mit «grösser null».** ◄◄◄ Ein
    **Korrekturbeleg** trägt einen negativen Betrag; bei ihm ist auch der offene Betrag
    negativ, und «offen < 0 heisst überzahlt» nennte jede unbeglichene Gutschrift
    «Überzahlt». Überzahlt ist, wo Rest und Betrag **verschiedene** Vorzeichen tragen –
    dann ist mehr geflossen als gefordert, in welche Richtung auch immer.

    «Teilweise bezahlt» ist die Mitte: gleiches Vorzeichen, aber weniger übrig als
    gefordert. Ohne sie sähe eine Rechnung, auf die eine Anzahlung eingegangen ist,
    genauso aus wie eine, auf die nichts eingegangen ist.
    """
    if abs(remaining) <= SETTLED_TOLERANCE:
        return _state("settled")
    if total != 0 and (remaining < 0) != (total < 0):
        return _state("overpaid")
    if overdue:
        return _state("overdue")
    if abs(remaining) + SETTLED_TOLERANCE < abs(total):
        return _state("partial")
    return _state("open")


def _state(key: str) -> dict[str, str]:
    label, tone = INVOICE_STATES[key]
    return {"state": key, "state_label": label, "state_tone": tone}


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
    #: ►►► **Wie die Forderung entsteht** – «Rechnung stellen» ↔ «Rechnung erfassen». ◄◄◄
    #: Im einen Fall entsteht der Beleg hier, im anderen schreiben wir einen fremden ab.
    #: Das ist der einzige der Geld-Wörter, der wirklich verschieden ist – die Zahlung
    #: wird in beiden Richtungen **erfasst**, und darum steht sie als Konstante daneben.
    charge_verb: str
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

    # ►►► **Eine Belegart nennt der Kopf NICHT** (Testnotizen #974/#977). ◄◄◄
    #
    # Hier stand ``document_label`` – «welche Belegart ist das?», mit den beiden Ausgängen
    # auf das Wort der Zusage-Stufe abgebildet, damit im Belegkopf nicht «Erledigt» steht.
    # Es war die Auslegung einer Ablehnung: #974 hiess *«ich möchte, dass diese Anzeige
    # verschwindet»*, und #977 hat es wiederholt. Die Angabe hat damit keinen Leser mehr,
    # und eine Auflösung ohne Leser ist die zweite Wahrheit, die beim nächsten Umbau
    # abweicht. ``label_of`` bleibt – eine **Fehlermeldung** über die Stufe muss die Stufe
    # nennen dürfen.


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
        # **Wir stellen sie** – sie entsteht hier, bekommt unsere Nummer und geht hinaus.
        charge_verb=CHARGE_ISSUE,
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
        # **Seine Rechnung schreiben wir ab** – der Beleg entsteht bei ihm.
        charge_verb=CHARGE_RECORD,
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


# ---------------------------------------------------------------------------
# ►►► DER BESTAND ZIEHT NACH — EINE Ableitung, zwei Leser ◄◄◄
# ---------------------------------------------------------------------------

def invoice_backfill_sql() -> tuple[str, ...]:
    """►►► **Wie ein alter Beleg zu seiner Rechnung kommt.** ◄◄◄

    Bis Migration ``138`` stand die Rechnung als **Zeile** im Beleg
    (``voucher_entries.kind = 'charge'``); danach ist der Beleg die Rechnung. Diese beiden
    Anweisungen sind der Weg von dort nach hier – und sie stehen **hier**, weil sie von
    **zwei** Stellen gebraucht werden:

    * der **Migration** – sie ist die Wahrheit;
    * dem **Lifespan-Netz** – die dev-Datenbank fährt kein ``alembic upgrade head``
      (Testnotiz #778), und dort zöge sonst das Spalten-Netz die acht Spalten leer nach,
      während die alten Forderungs-Zeilen stehenbleiben. **Der Dienst läse sie als
      Zahlungen**: jede alte Rechnung wäre ein Geldeingang, und der offene Betrag stünde
      im Minus.

    Zweimal ausgeschrieben wären es zwei Wahrheiten – dieselbe Bauart wie
    ``statuses.terminal_guard_sql``.

    **Zwei Ableitungen über dieselben Zeilen:** die **Summe** sagt, wie viel gefordert ist
    (ein Storno-Paar hebt sich auf, eine Gutschrift mindert); die **älteste geltende**
    Zeile – nicht selbst Gegenbuchung, und es gibt keine zu ihr – sagt, wie die Rechnung
    heisst und wann sie entstand. Den Betrag der ersten Zeile zu nehmen verfälschte jeden
    Beleg, an dem je korrigiert wurde.

    **Selbstbegrenzend und damit idempotent**: der erste Lauf setzt jede ``charge``-Zeile
    inaktiv, der zweite findet nichts mehr. Eine Reparatur mit einer gepflegten Liste
    veraltet (die Lehre aus Migration ``110``) – diese hier kann es nicht, weil sie ihre
    eigene Voraussetzung wegnimmt.

    ``issued_on`` bekommt das Rechnungsdatum: **was gebucht ist, gilt als hinausgegangen**
    – die vorsichtigere Annahme, sonst liesse sich eine längst versendete Rechnung
    zurücknehmen.
    """
    return (
        """
        WITH total AS (
            SELECT voucher_id, SUM(amount) AS amount
              FROM voucher_entries
             WHERE kind = 'charge' AND is_active
             GROUP BY voucher_id
        ), head AS (
            SELECT DISTINCT ON (e.voucher_id)
                   e.voucher_id, e.booked_on, e.due_on, e.reference, e.vat,
                   e.service_date
              FROM voucher_entries e
             WHERE e.kind = 'charge' AND e.is_active AND e.reverses_id IS NULL
               AND NOT EXISTS (SELECT 1 FROM voucher_entries r
                                WHERE r.reverses_id = e.id AND r.is_active)
             ORDER BY e.voucher_id, e.booked_on NULLS LAST, e.id
        )
        UPDATE vouchers v
           SET amount       = t.amount,
               billed_on    = h.booked_on,
               issued_on    = h.booked_on,
               due_on       = h.due_on,
               number       = h.reference,
               vat          = h.vat,
               service_date = h.service_date,
               stage        = CASE WHEN v.stage = 'agreed' THEN 'billed' ELSE v.stage END
          FROM total t
          JOIN head h ON h.voucher_id = t.voucher_id
         WHERE v.id = t.voucher_id
           AND v.amount IS NULL
        """,
        "UPDATE voucher_entries SET is_active = false WHERE kind = 'charge'",
    )


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

    # ►►► **``next_charge`` ist entfallen.** ◄◄◄ Es schlug vor, *was als nächstes zu
    # fordern wäre* – eine Zahl, die nur Sinn ergab, solange ein Beleg mehrere Rechnungen
    # tragen konnte. Es gibt eine, und was auf ihr steht, sagen die Positionen (wo **wir**
    # den Preis nennen) bzw. die Zusage (wo die Gegenpartei ihn nennt). Ein Vorschlag
    # daneben wäre eine dritte Quelle für dieselbe Zahl.

    @property
    def next_payment(self) -> Optional[Decimal]:
        """**Was als nächstes zu zahlen wäre** – und niemals ein negativer Vorschlag.

        Ein negativer offener Betrag ist eine gültige Aussage (wir schulden); als
        **Vorgabe** in einem Eingabefeld ist er es nicht. Eingebbar bleiben negative
        Beträge – das ist die Erstattung –, sie werden nur nie vorgeschlagen.
        """
        return self.open if self.open > 0 else None

    @property
    def write_off(self) -> Optional[Decimal]:
        """►►► **Der Restsaldo, den man als Differenz ausbuchen dürfte** – oder ``None``.

        *«Kleinbetragstoleranz: Restsaldo unter 1.00 CHF kann als Differenz ausgebucht
        werden. Nicht automatisch.»*

        Es ist **kein neuer Mechanismus**: ausgebucht wird über einen ganz gewöhnlichen
        Beleg mit Gegenvorzeichen und dem Grund «Rundungsdifferenz». Diese Zahl sagt nur,
        **ob** die Lage vorliegt und **wie viel** – damit die Oberfläche es anbieten kann,
        ohne die Regel ein zweites Mal zu rechnen.

        Über der Toleranz gibt es sie nicht: eine Forderung über zwanzig Franken bucht
        niemand «versehentlich» aus, und ein Feld, das es zuliesse, wäre die stille
        Abschreibung.

        Zurück kommt der Betrag, **wie er zu buchen ist** – also mit dem Gegenvorzeichen
        des Restsaldos. Eine Zahl, die man erst noch drehen muss, wäre die Stelle, an der
        ein Aufrufer sie einmal nicht dreht.
        """
        if self.open == 0 or abs(self.open) >= WRITE_OFF_LIMIT:
            return None
        return -self.open

    @property
    def settled(self) -> bool:
        """**Ist bezahlt, was zugesagt wurde?** Die eine Frage, die ``prepaid`` stellt.

        Gefragt wird nach der **Zusage**, nicht nach dem offenen Betrag: wer nichts
        berechnet hat, hat einen offenen Betrag von null – und das hiesse «bezahlt»,
        obwohl nie jemand etwas gefordert hat.
        """
        return self.paid >= (self.agreed or Decimal("0"))


def balance(agreed: Optional[Decimal], charged: Optional[Decimal],
            payments: list[Decimal]) -> Balance:
    """Zusage, Rechnung und Zahlungen zu vier Zahlen. **Die eine Rechenstelle.**

    ``charged`` ist der Betrag der **einen** Rechnung dieses Belegs (``None``, solange
    keine gestellt ist); ``payments`` sind die Zahlungen darauf. Diese Funktion kennt keine
    Datenbank; sie rechnet, und der Dienst liest.

    *Hier stand einmal eine Liste ``(Art, Betrag)`` und eine Summierung je Art – die Art
    gibt es nicht mehr: es gibt eine Rechnung und n Zahlungen.*
    """
    total = charged or Decimal("0")
    paid = sum(payments, Decimal("0"))
    return Balance(
        agreed=agreed,
        charged=total,
        paid=paid,
        open=total - paid,
        uncharged=None if agreed is None else agreed - total,
    )
