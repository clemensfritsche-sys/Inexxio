"""**Der Beleg und was zu ihm gehört** – die Tabellen des Moduls «Zahlung».

Vier Tabellen – jede Sache eine Zeile:

=================  ==========================================================
``vouchers``       der Beleg selbst – je Modul einer, **und er IST die Rechnung**
``voucher_quotes`` der Angebotsspiegel – je angefragter Partei eine Zeile
``voucher_lines``  die Positionen – **eine** Form, nicht drei
``voucher_entries``die Zahlungen darauf
=================  ==========================================================

►►► **Die Forderung ist keine Zeile, sondern der Beleg selbst.** ◄◄◄ Betrag, Nummer,
Datum, Fälligkeit und Steuer stehen am Beleg – damit kann es sie nicht zweimal geben:
«eine Rechnung je Modul» ist keine Regel, die eine Funktion zählt, sondern die
**Struktur**. Eine **Korrektur** ist ein eigener Beleg (``corrects_id``), der über
Auftragsgrenzen zeigen darf – sie gehört dorthin, wo die Ware zurückkommt.

## Was hier NICHT steht, und warum

*Mit wem*, *was vereinbart ist* und *welche Zahlungsfrist* sind **Ableitungen** aus der
Angebotszeile im Zustand ``gewaehlt`` – keine Spalten am Beleg. Daneben gespeichert
könnte derselbe Beleg zwei Dinge sagen; als Ableitung kann der Widerspruch **nicht
entstehen**. (``vouchers.amount`` ist der **Rechnungsbetrag**, eingefroren mit ``bill``.)
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
        # **Unsere Nummern genau einmal** (Rechnung und Gutschrift, Migration 164); eine
        # Lieferantenrechnung trägt die Nummer der Gegenpartei und fällt nicht darunter.
        Index("uq_vouchers_our_number", "number", unique=True,
              postgresql_where=text("direction = 'in' AND number IS NOT NULL")),
        Index("uq_vouchers_credit_number", "credit_number", unique=True,
              postgresql_where=text("credit_number IS NOT NULL")),
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

    #: ►►► **Wen dieser Beleg betrifft — wo die Definition niemanden nennt**. ◄◄◄
    #:
    #: ``config.parties`` am Modul ist eine **Vorlage**: sie sagt, wer in Frage kommt, und
    #: gilt für jeden künftigen Auftrag. Lässt sie **jeden** zu (leer), braucht die Wahl
    #: einen eigenen Ort mit eigenem Verb (``party``) – ``ask`` geht nur mit einem
    #: **vollständigen** Beleg hinaus.
    #:
    #: Eine Liste von **Objektnummern**, genau so, wie sie in ``config.parties`` steht:
    #: keine Eigenschaften, keine Zustände. Was hinausgegangen ist, bleibt eine **Zeile**
    #: (``voucher_quotes``).
    #:
    #: **Immer neu zuweisen, nie an Ort ändern**: ein mutierter JSONB-Wert fällt still aus
    #: dem ``UPDATE``.
    parties: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))

    #: ►►► **Die beiden Fristen als ENTWURF** – was auf dem Beleg steht, bevor er
    #: hinausgeht. ◄◄◄
    #:
    #: Jeder änderbare Wert des Belegs wird sofort geschrieben (Verb ``terms``), keiner
    #: lebt nur im Browser.
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
    # ►►► DIE RECHNUNG — der Beleg IST sie ◄◄◄
    # -----------------------------------------------------------------------
    #
    # Damit kann es sie nicht zweimal geben,
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

    # **Gestellt ist draussen**: ``billed_on`` sagt es, ein «versendet» gibt es nicht.

    #: **Der Rechnungsbetrag, brutto** – eingefroren mit dem Stellen. Eine Menge, nie
    #: negativ: dass ein Beleg mindert, sagt ``corrects_id``.
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

    #: ►►► **Welche Rechnung dieser Beleg MINDERT** – gesetzt heisst «Gutschrift». ◄◄◄
    #: Auf dem Papier steht «Korrektur zu <Nummer>» (MWSTG Art. 26). Der Verweis darf über
    #: Auftragsgrenzen zeigen: die Gutschrift gehört dorthin, wo die Ware zurückkommt.
    corrects_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True, index=True)

    # ─── An wen und wohin – gewählt bis zur Zusage, danach eingefroren ─────────────
    #: ►►► **Rechnung an die Firma oder an die Person?** ◄◄◄ ``NULL`` =
    #: die Vorgabe: an die Firma, wenn die Person einer zugeordnet ist. Es bestellt immer
    #: eine Person; die Firma ist höchstens der Rechnungsempfänger «im Namen von».
    bill_to_company: Mapped[Optional[bool]] = mapped_column(nullable=True)
    #: **Welche Anschriften aus dem Adressbuch des Adressaten** – ``NULL`` = sein
    #: Standard. Gilt nur, solange die Anschrift ihm gehört (``address_book.pick``).
    billing_address_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    delivery_address_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    #: ►►► **Der Belegkopf, EINGEFROREN mit der Zusage.** ◄◄◄
    #: ``{"party": 100000123, "ours": {...}, "billing": {...}}`` – beide Parteien, wie sie
    #: bei der Bestätigung dastanden: Name mit Rechtsform, «z. H.», UID, Anschriften,
    #: Kontaktweg. Ein Beleg behält, was auf ihm stand – zieht jemand um, firmiert um oder
    #: entfernt eine Anschrift, ändert das keine bestätigte Offerte und keine Rechnung.
    #: ``NULL`` vor der Zusage: dort ist der Kopf eine Ableitung und darf sich bewegen.
    head: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # ─── Gültigkeit, Eigentum, Stücke, Dokumente ─────────────────────────
    #: **Wie lange die Offerte gilt, in Tagen** – gezählt ab «Anbieten». ``NULL`` = die
    #: Vorgabe (``domain/voucher.VALID_DAYS``). Danach ist sie abgelaufen, «Annehmen» ist
    #: gesperrt, und «Erneut anbieten» beginnt die Frist neu.
    valid_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    #: **Wem die Stücke danach gehören** – ``party`` · ``us``, bewusst gewählt; ``NULL`` =
    #: noch nicht gewählt (Pflicht vor Anbieten und Zusage). Wem ein Stück gehört, ist eine
    #: Ableitung daraus (``services/voucher.sold_units``), gelesen am Ziel des Auftrags.
    ownership: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    #: ►►► **Über welche Stücke dieser Beleg spricht** – eingefroren beim ersten
    #: Hinausgehen (``ask``). ◄◄◄ Verlässt eines davon den Auftrag, ohne das Modul passiert
    #: zu haben, passt der Beleg nicht mehr zu den Stücken: dann bleibt nur «Stornieren»
    #: (``services/voucher.units_problem``). ``NULL`` = noch nichts hinausgegangen.
    unit_ids: Mapped[Optional[list[int]]] = mapped_column(JSONB, nullable=True)
    #: **Was hinausging – als Fingerabdruck** (Positionen, Preise, Fristen, Lieferbedingung,
    #: Anschriften). Weicht der Beleg davon ab, ist die gesendete Offerte überholt: angenommen
    #: werden kann nur die aktuelle Fassung, also zuerst «Erneut anbieten».
    offered_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    #: Der Grund eines Stornos – **nur intern**; die Mail an die Partei nennt keinen.
    cancel_note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    #: **Die Nummer der Gutschrift**, die ein Storno nach der Rechnung von selbst erzeugt
    #: (über den ganzen Rechnungsbetrag). Eine eigene Nummer – die Serie bleibt lückenlos.
    credit_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    #: **Ausgabe: die MWST-Nummer auf der Lieferantenrechnung** (MWSTG Art. 28 – ohne sie
    #: kein Vorsteuerabzug).
    party_uid: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    #: **Ausgabe: die Lieferantenrechnung** – die Nummer ihres Dokuments (Pflichtfeld
    #: ``voucher.original``), Pflicht beim Erfassen, aufbewahrt wie der Beleg.
    original_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    #: **Ausgabe: die Rechnung weicht von der Zusage ab, und sie wurde SO angenommen** –
    #: mit diesem Grund. Solange eine Abweichung ohne Grund dasteht, wird nicht bezahlt.
    deviation_note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    #: **Der Ausfuhrnachweis** (Export): Nummer der Veranlagungsverfügung und die Nummer
    #: ihres Dokuments (Pflichtfeld ``voucher.export``).
    #: Ohne ihn gilt der Nullsatz nicht – erledigt ist der Beleg erst damit.
    export_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    export_photo_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class VoucherQuote(Base, TimestampMixin):
    """**Eine Angebotszeile** – je angefragter Gegenpartei eine.

    ►►► **Eine Tabelle, keine Liste an einem Feld.** ◄◄◄

    Sie hat einen Zustand, ein Datum, einen Betrag und zwei Fristen – das ist eine Sache,
    keine Eigenschaft. Als Tabelle ändert man eine Zeile an Ort, und «woran ist dieser
    Betrachter beteiligt?» ist eine gewöhnliche ``WHERE``-Bedingung.

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

    #: Wann die Zeile hinausging – das Datum auf dem Papier.
    sent_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    #: **Seine Nummer für diesen Vorgang** («Ihre Referenz», bei einem Online-Kauf die
    #: Bestellnummer) und der **Link** zur Bestellung – nur, wo die Gegenpartei den Preis
    #: nennt.
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class VoucherLine(Base, TimestampMixin):
    """**Eine Position** – und es gibt sie genau in dieser einen Form.

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

    #: **Die Leistung** – der Untertitel unter dem Artikel («Geprüft und zertifiziert»).
    #: Vorbelegt aus dem Modul, änderbar bis zum Hinausgehen.
    text: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    #: ►►► **Ein Teilbetrag, netto** – ``NULL`` heisst «Vollbetrag». ◄◄◄ Jedes Zahlungsmodul
    #: steht für sich: was ein anderes schon verrechnet hat, weiss es nicht. ``0`` heisst
    #: «steht nicht auf dieser Rechnung».
    part: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    #: **Gewicht je Stück** (Export) – der Artikel belegt vor, wie beim Zoll.
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)

    #: Die Reihenfolge auf dem Papier. Ohne sie stünden die Zeilen in der Reihenfolge, in
    #: der die Datenbank sie gerade liefert – und die ist keine.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VoucherEntry(Base, TimestampMixin):
    """**Eine Geld-Zeile am Beleg** – Zahlung (negativ = Erstattung), Ausbuchung oder
    Trinkgeld (``kind``). Die Forderung ist keine davon: sie ist der Beleg selbst.

    **Gelöscht wird nichts** – eine Erstattung ist eine neue Zeile, «falsch erfasst» eine
    Gegenbuchung (``reverses_id``).
    """

    __tablename__ = "voucher_entries"
    __table_args__ = (
        # ►►► **Dieselbe Zahlung gibt es nur einmal** – die Regel in der Datenbank. ◄◄◄
        # Ein Zahlungsdienst stellt dieselbe Meldung mehrfach zu; zwei gleichzeitige
        # Zustellungen prüft keine Abfrage davor. Partiell: ohne Referenz (bar) gilt sie
        # nicht, und eine gegengebuchte Zeile bleibt stehen.
        Index("uq_voucher_entries_reference", "reference", unique=True,
              postgresql_where=text("is_active AND reference IS NOT NULL")),
    )

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

    #: ►►► **Was diese Zeile ist** – ``payment`` · ``writeoff`` · ``tip``. ◄◄◄ Eine Zahlung
    #: (negativ = Erstattung), eine **Ausbuchung** (Entgeltsminderung ohne Geld, mit Grund)
    #: oder ein **Trinkgeld** (zu viel bezahlt und behalten – Entgelt mit MWST).
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="payment",
                                      server_default="payment")
    #: Der Grund einer Ausbuchung (``domain/voucher.WRITE_OFF_REASONS``).
    reason: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    #: **«Falsch erfasst»** – die Zeile, die diese hier aufhebt. Gelöscht wird nichts.
    reverses_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("voucher_entries.id", ondelete="SET NULL"), nullable=True)
    #: Die IBAN, von der das Geld kam bzw. an die es zurückging (Überweisung).
    iban: Mapped[Optional[str]] = mapped_column(String(34), nullable=True)


class VoucherDocument(Base, TimestampMixin):
    """►►► **Ein Dokument, so wie es hinausging** – eingefroren, unveränderlich. ◄◄◄

    Offerte, Auftragsbestätigung, Rechnung, Quittung, Stornierung, Gutschrift, Mahnung: bei
    jedem Versand wird das Papier als HTML abgelegt (``services/document``). Der Online-Beleg
    und der Download zeigen genau diese Fassung (10 Jahre, OR 958f). Der **Token** ist der
    unerratbare Link für die Partei – je Dokument einer.
    """

    __tablename__ = "voucher_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    voucher_id: Mapped[int] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True, nullable=False)
    #: ``offer`` · ``confirmation`` · ``invoice`` · ``receipt`` · ``storno`` · ``credit`` ·
    #: ``reminder`` (``domain/voucher.DOCUMENTS``).
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Die Mahnstufe (1–3) – nur bei ``reminder``.
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    #: Die Nummer, die auf dem Papier steht.
    number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    #: An wen es ging – die Objektnummer der Person.
    party_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    #: **Das Papier ist ein Dokument** (``documents.id``, Feld ``voucher.doc``) – die eine
    #: Ablage. Hier steht nur noch, wie es hinausging (Link, Partei, Mail).
    document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id"), nullable=True, index=True)

    #: Das Datum der AGB, die angehängt sind («2026-01-01»).
    agb: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    #: Die Mail, mit der es hinausging (``messages.id``).
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

