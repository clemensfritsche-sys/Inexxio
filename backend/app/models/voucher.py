"""**Der Beleg und was zu ihm gehört** – die Tabellen des Moduls «Zahlung».

Vier Tabellen, und drei davon sind der Grund für den Neuaufbau: beim Vorgänger standen
der **Angebotsspiegel** und die **Positionen** als JSONB an der Kopfzeile, die Positionen
sogar in drei verschiedenen Formen (abgeleitet · je Angebot kopiert · eingefroren).

Hier ist jede Sache eine Zeile:

=================  ==========================================================
``vouchers``       der Beleg selbst – je Modul einer, **und er IST die Rechnung**
``voucher_quotes`` der Angebotsspiegel – je angefragter Partei eine Zeile
``voucher_lines``  die Positionen – **eine** Form, nicht drei
``voucher_entries``die Zahlungen darauf
=================  ==========================================================

►►► **Die Forderung ist keine Zeile mehr.** ◄◄◄ Sie stand als ``voucher_entries`` mit
``kind = 'charge'`` **im** Beleg und trug Betrag, Nummer, Datum, Fälligkeit und Steuer –
also eine Kopie des Belegs, der sie enthielt. Jetzt steht sie am Beleg selbst, und damit
kann es sie nicht zweimal geben: «eine Rechnung je Modul» ist keine Regel mehr, die eine
Funktion zählt, sondern die **Struktur**. Eine **Korrektur** ist ein eigener Beleg
(``corrects_id``), der über Auftragsgrenzen zeigen darf – sie gehört dorthin, wo die Ware
zurückkommt.

**Ohne Bezug zu ``deals``.** Das ist Absicht: dieses Modul soll bestehen bleiben, wenn
das alte Zahlungsmodul eines Tages ersatzlos gelöscht wird.

## Was hier NICHT steht, und warum

Drei Spalten des Vorgängers sind ersatzlos entfallen, weil sie **Ableitungen** waren:

``party_id``   *mit wem* – das ist die Angebotszeile im Zustand ``gewaehlt``.
``amount``     *was vereinbart ist* – der Betrag **dieser** Zeile.
``due_days``   *die Zahlungsfrist* – die Frist **dieser** Zeile.

Am Vorgänger standen sie daneben und wurden beim Zuschlag hineinkopiert; damit konnte
derselbe Beleg zwei Dinge sagen, und eine eigene Regel (``_agree`` weist einen
abweichenden Betrag ab) musste das verhindern. Als Ableitung kann der Widerspruch **nicht
entstehen** – eine Regel weniger, und zwar konstruktiv.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger, Date, ForeignKey, Index, Integer, Numeric, String, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Voucher(Base, TimestampMixin):
    """**Der Beleg** – was mit einer zweiten Partei vereinbart ist, je Modul einer.

    **Keine eigene Objektnummer.** Er läuft unter der Auftragsnummer – dasselbe Muster
    wie jede andere Fachzeile des Prozesses. Eine zweite Nummer wäre ein zweiter
    Datensatz für denselben Vorgang, und der Feed hätte eine Zeile mehr, die niemand
    sucht.

    **Die Stufen gehören dem Beleg, nicht dem Stück.** Eine Einzelinstanz ist vom Angebot
    bis zum Abschluss durchgehend ``Im Prozess``: sie wartet, sie ändert sich nicht. Ein
    Zustand «bestellt» an ihr wäre einer, der nichts über das Material aussagt – und den
    Statusliste, FIFO und Bestand beantworten müssten.
    """

    __tablename__ = "vouchers"
    __table_args__ = (
        # **Ein AKTIVER Beleg je Modul** – die Regel in der Datenbank, nicht nur im
        # Dienst: ``ensure`` ist idempotent, zwei gleichzeitige Freigaben sind es nicht.
        # Partiell, weil ein zurückgenommener weiterhin als Zeile steht (Soft-Delete).
        Index("uq_vouchers_step", "step_id", unique=True,
              postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    #: Das Modul, zu dem dieser Beleg gehört.
    step_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    #: ``in`` · ``out`` (``domain/voucher``). Eingefroren bei der Anlage aus der
    #: Konfiguration des Schritts: ein laufender Auftrag trägt seinen Prozess eingefroren,
    #: und dieser Beleg soll auch dann noch sagen können, was er war.
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="out")

    #: **ISO 4217, drei Zeichen** (``domain/currency``) – **eine je Beleg, nicht je
    #: Zeile**: zwei Währungen auf einem Papier wären zwei Belege. Vorgabe ist die des
    #: Ausstellers; eingefroren mit der Zusage.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CHF")

    #: **WER stellt den Beleg** – die Objektnummer unserer Gesellschaft, gesetzt bei der
    #: Anlage aus der Gesellschaft des Freigebenden. Bei jeder Anzeige neu gelesen änderte
    #: ein Wechsel rückwirkend, wer einen alten Beleg gestellt hat. ``NULL`` ist regulär
    #: und heisst «der Betreiber».
    issuer_company_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    #: ``offer`` · ``agreed`` · ``billed`` · ``done`` · ``cancelled``
    #: (``domain/voucher``).
    #:
    #: ►►► **Sie ist zugleich der Einfrier-Schalter der Positionen.** ◄◄◄ Solange
    #: ``offer``, ziehen die Mengen aus dem Prozess nach; ab ``agreed`` nie wieder. Damit
    #: braucht es **keine** zweite Kopie der Zeilen und kein Feld je Zeile.
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="offer")

    #: Wann zugesagt wurde – der Anker, ab dem Zahlungsfrist und Lieferfrist laufen.
    agreed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    #: Wann storniert wurde. ``stage`` sagt **dass**, nicht **wann** – und ``updated_at``
    #: wandert bei jeder späteren Änderung mit; ein Storno, dessen Datum sich bewegt, ist
    #: kein Datum.
    cancelled_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Die Lieferbedingung** (Incoterms 2020). Sie gehört an den **Beleg**, nicht an das
    #: Bewegen-Modul: ein Incoterm ist eine **Vereinbarung** über Kosten und Risiko, kein
    #: physischer Vorgang – das Bewegen-Modul *führt aus*, was hier vereinbart wurde.
    incoterm: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    #: **Der benannte Ort** – ohne ihn ist die Klausel keine Vereinbarung: bei ``FCA``
    #: entscheidet genau er, wo das Risiko übergeht.
    incoterm_place: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    #: ►►► **Wen dieser Beleg betrifft — wo die Definition niemanden nennt** (#1000). ◄◄◄
    #:
    #: ``config.parties`` am Modul ist eine **Vorlage**: sie sagt, wer in Frage kommt, und
    #: gilt für jeden künftigen Auftrag. Lässt sie **jeden** zu (leer), muss die Wahl
    #: irgendwo hin – und bis hierher gab es dafür keinen Ort: der Klick im Feld löste
    #: sofort ``ask`` aus, und das geht nur mit einem **vollständigen** Beleg hinaus.
    #: Fehlte Preis, Frist oder Lieferbedingung, wies der Dienst zu Recht ab, und die
    #: getroffene Wahl war weg. Sie war damit die letzte Angabe des Belegs ohne eigenes
    #: Verb – dieselbe Lücke wie bei den Fristen (#985), nur eine Runde später.
    #:
    #: **Und es ist kein Rückfall in die Form des Vorgängers.** Dort stand der
    #: *Angebotsspiegel* als JSONB – eine **Entität** mit Betrag, Fristen, Zustand und
    #: Datum. Hier steht eine Liste von Objektnummern, genau so, wie sie eine Zeile höher
    #: in ``config.parties`` steht: keine Eigenschaften, keine Zustände, nichts, wonach
    #: jemand filtern müsste. Was hinausgegangen ist, bleibt eine **Zeile**
    #: (``voucher_quotes``) – das ist der Unterschied, um den es ging.
    #:
    #: **Immer neu zuweisen, nie an Ort ändern**: ein mutierter JSONB-Wert fällt still aus
    #: dem ``UPDATE``.
    parties: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))

    #: ►►► **Die beiden Fristen als ENTWURF** – was auf dem Beleg steht, bevor er
    #: hinausgeht (Testnotiz #985). ◄◄◄
    #:
    #: Sie lebten nur im Browser und reisten allein in der Nutzlast von ``ask`` mit: wer
    #: sie tippte und die Seite neu lud, hatte sie verloren. Das war **keine Eigenheit
    #: dieser zwei Felder**, sondern die einzige Stelle des Belegs ohne eigenes Verb –
    #: Währung, Aussteller, Lieferbedingung, Preis und Zoll werden längst sofort
    #: geschrieben.
    #:
    #: **Die Vereinbarung steht weiterhin an der Angebotszeile.** Das hier ist der
    #: Entwurf; ``lead_days_of``/``due_days_of`` lesen die gewählte Zeile und fallen
    #: darauf zurück. Zwei Wahrheiten sind es nicht – es sind zwei **Zeitpunkte**: was wir
    #: anbieten wollen, und was vereinbart wurde.
    #:
    #: **Null ist eine Angabe** («Sofort» · «Vorauszahlung»); ``NULL`` heisst «noch nichts
    #: gewählt».
    lead_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # -----------------------------------------------------------------------
    # ►►► DIE RECHNUNG — acht Angaben, die eine Ebene tiefer standen ◄◄◄
    # -----------------------------------------------------------------------
    #
    # Sie hingen an einer Zeile in ``voucher_entries`` (``kind = 'charge'``) – also an
    # einem Datensatz **im** Beleg, der Betrag, Nummer, Datum, Fälligkeit und Steuer noch
    # einmal trug. Eine Kopie des Belegs, der sie enthielt; dieselbe Fehlerform, die der
    # Neuaufbau bei den Positionen schon einmal beseitigt hat.
    #
    # ►►► **Jetzt IST der Beleg die Rechnung.** ◄◄◄ Damit kann es sie nicht zweimal geben,
    # und «eine Rechnung je Modul» ist keine Regel mehr, die eine Funktion zählt, sondern
    # die Struktur. Eine **Korrektur** ist ein eigener Beleg (``corrects_id``).

    #: **Das Rechnungsdatum.** ``NULL`` = es gibt noch keine Rechnung; das ist zugleich
    #: die Antwort auf «ist schon gestellt?», ohne ein zweites Ja/Nein daneben.
    billed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Die Fälligkeit** = Rechnungsdatum + vereinbarte Zahlungsfrist. Eingefroren, nicht
    #: gerechnet: eine nachträglich geänderte Frist verschöbe sonst die Fälligkeit einer
    #: längst gestellten Rechnung.
    due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Die Belegnummer.** Wer sie vergibt, sagt die Richtung: bei einer **Einnahme**
    #: nummerieren wir (``<Auftragsnummer>-<laufend>``), bei einer **Ausgabe** erfassen wir
    #: seine. Sie bleibt auch an einer zurückgenommenen Rechnung stehen – eine einmal
    #: vergebene Nummer wird nicht erneut vergeben.
    number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    #: ►►► **Wann die Rechnung hinausging.** ◄◄◄ ``NULL`` = sie liegt noch im Haus, und
    #: genau dann lässt sie sich zurücknehmen (``unbill``). Danach ist sie unveränderlich –
    #: ein Papier ist draussen, und was daran falsch ist, korrigiert ein eigener Beleg.
    #:
    #: **Die Spalte ist bewusst eine Spalte.** Die Hausregel lautet «der Moment braucht
    #: keine Spalte» – hier gibt ihn nichts anderes her, weil eine Zustellung (PDF,
    #: E-Mail) nicht gebaut ist. Sobald sie es ist, setzt **sie** das Datum.
    issued_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Der Rechnungsbetrag, brutto** – eingefroren mit dem Stellen. Bei einem
    #: **Korrekturbeleg** negativ: die Positionen tragen positive Preise (niemand tippt ein
    #: Minus), und das Vorzeichen setzt ``bill`` aus ``corrects_id``. Danach rechnet jede
    #: Zahl vorzeichenrichtig, ohne eine einzige Fallunterscheidung beim Lesen.
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    #: **Die Steuer-Aufteilung – EINGEFROREN**, nicht nachgerechnet.
    #: ``[{"vat": "normal", "rate": "8.10", "net": "60.00", "tax": "4.86"}]``
    #:
    #: Die Positionen stehen ab der Zusage ohnehin fest; die **Steuer** tut es nicht: eine
    #: künftige Änderung an der Rundungsregel oder am Katalog änderte sonst rückwirkend die
    #: Steuer einer längst gestellten Rechnung (MWSTG Art. 26). Ein Beleg behält, was auf
    #: ihm stand.
    vat: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)

    #: **Wann die Leistung erbracht wurde** (MWSTG Art. 26 Abs. 2 Bst. c) – **nicht** das
    #: Rechnungsdatum: über den Jahreswechsel entscheidet es die Steuerperiode. Abgeleitet
    #: aus dem Prozess und mit dem Stellen eingefroren.
    service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: ►►► **Welchen Beleg dieser hier MINDERT.** ◄◄◄
    #:
    #: Das ist die ganze Korrektur-Mechanik: kein Belegtyp, keine Gegenbuchung an einer
    #: Zeile, keine Summenregel. Ein Beleg mit gesetztem Verweis ist eine **Gutschrift** –
    #: sein Betrag ist negativ, seine Steuer gespiegelt, und auf dem Papier steht
    #: «Korrektur zu <Nummer>» (MWSTG Art. 26: die Leistung und das Entgelt müssen
    #: eindeutig bestimmbar sein).
    #:
    #: **Er darf über Auftragsgrenzen zeigen** – und das ist der Sinn: die Gutschrift
    #: gehört in den Auftrag, in dem die Ware zurückkommt, nicht in den, der sie geliefert
    #: hat. Dort entstehen ihre Positionen von selbst aus den zurückkommenden Stücken.
    corrects_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True, index=True)


class VoucherQuote(Base, TimestampMixin):
    """**Eine Angebotszeile** – je angefragter Gegenpartei eine.

    ►►► **Eine Tabelle, keine Liste an einem Feld.** ◄◄◄

    Sie hat einen Zustand, ein Datum, einen Betrag und zwei Fristen – das ist eine Sache,
    keine Eigenschaft. Beim Vorgänger stand sie als JSONB an der Kopfzeile, und daraus
    folgten drei Dinge, die es hier nicht mehr gibt: die ganze Liste musste bei jeder
    Änderung **neu gebaut** werden (ein mutierter JSONB-Wert fällt still aus dem
    ``UPDATE``), das Datum des Hinausgehens musste **nachträglich hineingeflickt** werden,
    und «woran ist dieser Betrachter beteiligt?» war eine JSONB-Containment-Abfrage statt
    einer gewöhnlichen ``WHERE``-Bedingung.

    **Der Zustand ist eine Folge, kein Tippen**: ``gewaehlt`` entsteht dadurch, dass bei
    dieser Zeile zugesagt wurde – und damit ist *diese* Zeile die Antwort auf «mit wem, zu
    welchem Betrag, zu welcher Frist».
    """

    __tablename__ = "voucher_quotes"
    __table_args__ = (
        # **Eine Zeile je Partei und Beleg.** Zweimal denselben anzufragen ist keine
        # zweite Anfrage, sondern dieselbe.
        Index("uq_voucher_quotes_party", "voucher_id", "party_id", unique=True,
              postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    voucher_id: Mapped[int] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True, nullable=False)

    #: Die Objektnummer der Gegenpartei.
    party_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    #: ``angefragt`` · ``offeriert`` · ``abgelehnt`` · ``gewaehlt``.
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="angefragt")

    #: **Der Betrag dieses Angebots**, brutto. Bei einer **Einnahme** ist er die
    #: Brutto-Summe unserer Positionen (wir nennen den Preis), bei einer **Ausgabe** die
    #: Summe, die *er* nennt. ``NULL`` = angefragt, noch nichts genannt.
    #:
    #: **Vier Nachkommastellen**, nicht zwei: nicht weil hier so gerechnet würde – gerundet
    #: wird je Währung –, sondern weil eine Spalte mit zwei Stellen einem dreistelligen
    #: Betrag (KWD) still die letzte abschneidet.
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    #: Die beiden Fristen dieses Angebots, in Tagen. **Null ist eine Angabe** – «Sofort»
    #: bzw. «Vorauszahlung»; ``NULL`` heisst «nicht vereinbart».
    lead_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    #: Wann die Zeile hinausging – die Chronik fragt «wann wurde offeriert».
    sent_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class VoucherLine(Base, TimestampMixin):
    """**Eine Position** – und es gibt sie genau in dieser einen Form.

    Beim Vorgänger existierte dieselbe Sache dreimal: abgeleitet aus dem Prozess, kopiert
    in jede Angebotszeile und eingefroren an der Kopfzeile – angefasst an 21 Stellen.

    ►►► **Eingefroren wird durch die STUFE, nicht durch eine Kopie.** ◄◄◄ Solange der
    Beleg auf ``offer`` steht, zieht ``sync_lines`` Artikel und Mengen aus dem Prozess
    nach; ab der Zusage nie wieder. Kein Feld je Zeile, keine zweite Tabelle, keine Kopie.

    **Die Positionen gehören dem BELEG, nicht der Angebotszeile.** Ein Beleg hat *einen*
    Satz Positionen mit *einem* Satz Preise – zwei Kunden zwei verschiedene Preise
    anzubieten sind zwei Angebote, also zwei Belege. Beim Vergleich mehrerer Lieferanten
    (der eigentliche Zweck des Spiegels) nennt ohnehin jeder eine **Summe**, und die steht
    an seiner Zeile.

    Eine Zeile **ohne Artikel** ist der Normalfall dort, wo es gar keine Stücke gibt
    (Miete, Lohn, Gebühr): Menge 1, Preis netto. Derselbe Mechanismus mit einer entarteten
    Zeile, kein zweiter Fall.
    """

    __tablename__ = "voucher_lines"
    __table_args__ = (
        # **Ein Artikel, eine Zeile.** ``sync_lines`` läuft bei jeder Anzeige des Belegs;
        # zwei gleichzeitige Aufrufe legten sonst dieselbe Position zweimal an, und die
        # Summe wäre doppelt. Partiell (Soft-Delete) und über ``article_id`` – ``NULL``
        # kollidiert in PostgreSQL nicht mit sich selbst, also bleiben mehrere **freie**
        # Zeilen (Miete, Lohn, Gebühr) erlaubt.
        Index("uq_voucher_lines_article", "voucher_id", "article_id", unique=True,
              postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    voucher_id: Mapped[int] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True, nullable=False)

    #: Der Artikel – ``NULL`` bei einer Zeile ohne Stücke. Die **interne Id**, wie überall
    #: im Prozess (``Instance.article_id``): eine zweite Adressierung derselben Sache wäre
    #: die Stelle, an der ein Join eines Tages ins Leere greift.
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True,
                                                      nullable=True)

    #: **Die Menge kommt aus dem Prozess**, nie aus der Nutzlast: sie ist die Zahl der
    #: Einzelinstanzen, die vor dem Modul stehen. Eine getippte Menge wäre die zweite
    #: Aussage über dieselbe Sache – und die getippte gewinnt, auch wenn sie falsch ist.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    #: **Der Einzelpreis, NETTO.** ``NULL`` heisst «noch kein Preis genannt» – das ist der
    #: Normalzustand einer Ausgabe, bei der die Gegenpartei eine Summe nennt.
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    #: Der Schlüssel der Katalogzeile (``domain/voucher.VAT_RATES``) – **nicht die Zahl**:
    #: *Export* und *Reverse Charge* ergeben beide 0 %, tragen aber verschiedene
    #: Pflichtsätze, und ein Beleg, der nur «0 %» sagt, nennt den Grund nicht.
    vat: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")

    #: **Zoll: Tarifnummer und Ursprungsland.** Der Artikel belegt vor, der Beleg trägt den
    #: Wert – dieselbe Beziehung wie beim Preis. ``NULL`` heisst «nimm die des Artikels»;
    #: als leerer String gespeichert wäre es die Behauptung, es gebe keine.
    #: **Zurückgeschrieben wird nichts** – ein Beleg korrigiert keine Stammdaten.
    hs_code: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    origin_country: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    #: Die Reihenfolge auf dem Papier. Ohne sie stünden die Zeilen in der Reihenfolge, in
    #: der die Datenbank sie gerade liefert – und die ist keine.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VoucherEntry(Base, TimestampMixin):
    """**Eine Zahlung** – eine Zeile Geld am Beleg. Negativ ist die Erstattung.

    ►►► **Hier standen einmal zwei Arten.** ◄◄◄ ``kind = 'charge'`` war die **Forderung**,
    also eine Rechnung als Datensatz *im* Beleg – mit Betrag, Nummer, Datum, Fälligkeit und
    Steuer, allesamt Angaben, die der Beleg selbst trug. Sie ist eine Ebene höher gewandert
    (``Voucher.billed_on`` & Co.), und damit ist dies die einzige verbliebene Art: ein
    ``kind`` daneben wäre ein Feld mit genau einem Wert.

    **Gelöscht wird nichts** – auch eine Erstattung ist eine neue Zeile mit negativem
    Betrag, nie eine Änderung an der alten: eine Zahlung ist die Aufzeichnung dessen, was
    auf dem Konto passiert ist, und ein Ereignis der Aussenwelt macht man nicht ungeschehen.

    *Die Spalten ``kind`` · ``due_on`` · ``vat`` · ``service_date`` · ``reverses_id`` ·
    ``charge_id`` stehen noch in der Datenbank (Zwei-Deploy-Regel, ``docs/backlog.md``) und
    werden von keiner Zeile Code mehr gelesen oder geschrieben.*
    """

    __tablename__ = "voucher_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    voucher_id: Mapped[int] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True, nullable=False)

    #: **Darf negativ sein** – das ist die Erstattung.
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    #: Wann das Geld geflossen ist (Valuta).
    booked_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: Der Zahlungszweck bzw. die Referenz des Zahlungsdienstes. **Idempotenz hängt an
    #: ihr**: dieselbe Referenz gehört zu genau einer Zahlung im Haus.
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    #: **WIE bezahlt wurde** – bar · Überweisung · Karte. **Kein zweites Modell**:
    #: gebucht wird in jedem Fall dieselbe Zeile – bei der einen ruft ein Mensch, bei der
    #: anderen der Webhook.
    method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)


# ---------------------------------------------------------------------------
# ►►► EINE AUFTEILUNGS-TABELLE GIBT ES NICHT MEHR ◄◄◄
# ---------------------------------------------------------------------------
#
# Hier stand ``VoucherAllocation``: *wie viel dieser Zahlung auf welchen Beleg geht*. Sie
# beantwortete eine Frage, die es **innerhalb eines Belegs** nicht mehr gibt – dort lebt
# genau eine Rechnung, also ist jede Zahlung dieses Moduls ihre.
#
# **Der Fall bleibt real**: eine Überweisung über 1'500 begleicht eine Rechnung über 1'000
# und eine über 500. Nach diesem Umbau liegen die beiden zwingend in **verschiedenen
# Modulen**, also ist es eine Zuordnung über Modulgrenzen – und das ist die
# **offene-Posten-Liste je Partner**, nicht eine Tabelle an einem Prozessschritt. Bis es
# sie gibt, erfasst man zwei Zahlungen, wo im Kontoauszug eine steht: eine Zeile mehr auf
# dem Bildschirm, keine falsche Zahl (``docs/backlog.md``).
#
# Die **Tabelle** bleibt stehen (Zwei-Deploy-Regel); kein Modell verweist mehr auf sie.
