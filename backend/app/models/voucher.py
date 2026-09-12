"""**Der Beleg und was zu ihm gehört** – die Tabellen des Moduls «Zahlung».

Vier Tabellen, und drei davon sind der Grund für den Neuaufbau: beim Vorgänger standen
der **Angebotsspiegel** und die **Positionen** als JSONB an der Kopfzeile, die Positionen
sogar in drei verschiedenen Formen (abgeleitet · je Angebot kopiert · eingefroren).

Hier ist jede Sache eine Zeile:

=================  ==========================================================
``vouchers``       der Beleg selbst – je Modul einer
``voucher_quotes`` der Angebotsspiegel – je angefragter Partei eine Zeile
``voucher_lines``  die Positionen – **eine** Form, nicht drei
``voucher_entries``Forderungen **und** Zahlungen
=================  ==========================================================

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

    #: ``offer`` · ``agreed`` · ``done`` · ``cancelled`` (``domain/voucher``).
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
    """**Eine Zeile Geld** – eine Forderung oder eine Zahlung.

    ``kind`` sagt, welche Achse: ``charge`` ist die **Forderung** (Rechnung, negativ =
    Gutschrift), ``payment`` das **Geld** (negativ = Erstattung).

    ►►► **Storniert wird durch eine GEGENBUCHUNG, nie durch Löschen.** ◄◄◄

    Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen – wer die Zeile verschwinden
    lässt, behauptet, sie sei nie passiert. Eine Stornierung ist darum eine zweite Zeile:
    dieselbe Art, der negative Betrag, ``reverses_id`` auf die stornierte. Das ist **keine
    neue Mechanik** – eine Gutschrift ist längst eine negative Rechnung.
    """

    __tablename__ = "voucher_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    voucher_id: Mapped[int] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True, nullable=False)

    #: ``charge`` · ``payment`` (``domain/voucher.KINDS``).
    kind: Mapped[str] = mapped_column(String(10), nullable=False)

    #: **Darf negativ sein** – das ist die Gutschrift bzw. die Erstattung.
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    #: Wann die Zeile gilt – Rechnungsdatum bzw. Valuta.
    booked_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Nur bei einer Forderung**: wann sie fällig ist. Je Rechnung eine eigene, weil eine
    #: Anzahlung und eine Schlussrechnung zu zwei Zeitpunkten fällig sind.
    due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Die Nummer dieser Zeile.** Wer sie vergibt, sagt die Richtung: bei einer
    #: **Einnahme** nummerieren wir (``<Auftragsnummer>-<laufend>``), bei einer **Ausgabe**
    #: erfassen wir seine. Eine Zahlung trägt hier ihren Zahlungszweck bzw. die Referenz
    #: des Zahlungsdienstes.
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    #: **Welche Zeile diese hier storniert** – und zugleich die **Sperre**: eine Zeile mit
    #: ``reverses_id`` lässt sich nicht stornieren, und eine, zu der es schon eine
    #: Gegenzeile gibt, ebenso wenig – sonst entstünde eine Kette aus Vorzeichen, in der
    #: niemand mehr sagen kann, was gilt.
    reverses_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voucher_entries.id", ondelete="SET NULL"), nullable=True, index=True)

    #: **Welche RECHNUNG diese Zahlung begleicht** – nur bei ``kind = payment``. Eine
    #: Zahlung gehört zu genau einer Forderung; der Weg für «eine Überweisung über zwei
    #: Rechnungen» ist eine **Stornorechnung und eine gemeinsame neue**. ``balance`` bleibt
    #: davon unberührt – es rechnet über die Summen; diese Spalte beantwortet «worauf»,
    #: nicht «wie viel».
    charge_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voucher_entries.id", ondelete="SET NULL"), nullable=True, index=True)

    #: **WIE bezahlt wurde** – bar · Überweisung · Karte. Nur bei ``kind = payment``.
    #: **Kein zweites Modell**: gebucht wird in jedem Fall dieselbe Zeile – bei der einen
    #: ruft ein Mensch, bei der anderen der Webhook.
    method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    #: **Die Steuer-Aufteilung dieses Belegs – EINGEFROREN.**
    #:
    #: ``[{"vat": "normal", "rate": "8.10", "net": "60.00", "tax": "4.86"}]``. Aus den
    #: Positionen nachgerechnet änderte sich die Steuer einer längst gestellten Rechnung,
    #: sobald jemand eine Position anfasst – eine rückwirkend geänderte Steuerangabe, und
    #: genau das darf es nicht geben (MWSTG Art. 26).
    #:
    #: Hier **JSONB und nicht eine Tabelle**, und das ist kein Widerspruch zu den Zeilen
    #: oben: dies ist ein eingefrorener **Rechenstand**, keine Sache mit Zustand und
    #: Lebenslauf. ``None`` bei einer Zahlung – Geld trägt keine Steuer, es begleicht sie.
    vat: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)

    #: **Wann die Leistung erbracht wurde** (MWSTG Art. 26 Abs. 2 Bst. c) – **nicht** das
    #: Rechnungsdatum: über den Jahreswechsel entscheidet es die Steuerperiode. Abgeleitet
    #: aus dem Prozess (der Tag, an dem die Stücke das Modul erreicht haben).
    service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
