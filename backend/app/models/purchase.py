from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import BigInteger, Date, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Purchase(Base, TimestampMixin):
    """Der **Beleg** eines Handelsvorgangs: was gehandelt wird, mit wem, wie weit.

    **Er trägt eine Richtung** (``direction``, ``domain/procurement``). Einkauf und
    Verkauf sind dasselbe Geschäft aus zwei Blickwinkeln – jemand fragt, jemand nennt einen
    Preis, jemand sagt zu, jemand erfüllt. Dieselben drei Stufen, dieselbe Schwelle,
    derselbe Storno; verschieden sind die Wörter, die Gegenpartei und die Hand, die den
    Preis einträgt. Zwei Tabellen wären zwei Orte für dieselbe Regel.

    **Keine eigene Objektnummer.** Er läuft unter der Auftragsnummer – dasselbe Muster
    wie jede andere Fachzeile des Prozesses (Erfassung, Ereignis). Eine zweite Nummer
    wäre ein zweiter Datensatz für denselben Vorgang, und der Feed hätte eine Zeile mehr,
    die niemand sucht.

    **Die Stufen gehören diesem Beleg, nicht dem Stück.** Eine Einzelinstanz ist von der
    Anfrage bis zum Wareneingang durchgehend ``Im Prozess``; sie wartet, sie ändert sich
    nicht. Wer den Bestellzustand an den Zustand des Stücks hängte, hätte Zustände
    erfunden, die keine Aussage über das Material sind.

    ``quotes`` ist die **Anfrage** – eine Zeile je Gegenpartei:
    ``{"supplier": <Objektnr>, "amount": "84.00", "lead_days": 5, "payment_days": 30,
    "state": "offeriert"}``. Als JSONB und nicht als Tabelle, aus demselben Grund wie
    ``instances.reservations``: es ist eine Liste **an** diesem Beleg, keine eigene Sache.
    Beträge stehen als **String** – wo es auf den Rappen ankommt, wird nicht durch
    ``float`` gerechnet.

    Der Schlüssel heisst weiterhin ``supplier``, obwohl dort beim Verkauf ein **Kunde**
    steht. Das ist Absicht: es ist eine Objektnummer in einem JSONB-Wert, den laufende
    Aufträge bereits tragen, und eine Umschrift wäre ein Risiko ohne einen einzigen neuen
    Leser. Wie die Gegenpartei **heisst**, sagt der ``Flow`` (``party_word``) – dort, wo
    es einen Unterschied macht: im Satz, den ein Mensch liest.

    ``supplier_id``/``amount`` sind die **getroffene Wahl** (die bestellte Zeile). Sie
    stehen als Spalten und nicht nur in ``quotes``, weil sie das sind, was den Beleg
    ausmacht: eine Bestellung hat genau einen Lieferanten und genau eine Summe, und
    danach fragt jede Auswertung.

    ``ordered_lines`` ist, **was** bestellt wurde – abgeleitet aus dem Prozess und mit der
    Bestellung eingefroren (siehe unten). Ein ``article_id`` gibt es nicht: der Beleg kann
    zwei Artikel führen, und welche es sind, sagen die Einzelinstanzen, die vor dem Modul
    stehen.

    ``tracking`` ist die **Sendungsnummer** – und sonst nichts.

    Das Feld hiess einmal ``reference`` und sammelte drei Dinge: Bestellnummer beim
    Lieferanten, Shop-Link und Sendungsnummer. Das waren aber **zwei Fragen zu zwei
    Zeitpunkten**: *wie bestelle ich bei ihm* ist eine Eigenschaft der Paarung
    Modul × Lieferant und steht seither in der Definition
    (``Beschaffen.suppliers_of`` → ``ref``); *wo ist die Sendung* entsteht erst **nach**
    der Bestellung und kommt vom Lieferanten – er darf sie darum selbst eintragen.
    ``reference`` wird nicht mehr geschrieben und im Folge-Deploy gedroppt.
    """

    __tablename__ = "purchases"
    __table_args__ = (
        # **Ein Beleg je Modul** – die Regel in der Datenbank, nicht nur im Dienst:
        # ``instantiate_for_order`` ist idempotent, zwei gleichzeitige Freigaben sind es
        # nicht, und ein Index prüft je Anweisung.
        # **Ein AKTIVER Beleg je Modul.** Partiell, weil ein zurückgenommener weiterhin
        # als Zeile steht (Soft-Delete) – ein voller Unique-Index liesse danach keinen
        # neuen mehr zu, und «eingekauft ↔ doch selbst ↔ dann doch eingekauft» wäre eine
        # Sackgasse. Migration 119.
        Index("uq_purchases_step", "step_id", unique=True,
              postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    #: Das Modul, zu dem dieser Beleg gehört. Bei mehreren Positionen teilen sich
    #: mehrere Belege denselben Schritt – jede Beschaffung schreitet eigenständig fort.
    step_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    #: ``offer`` · ``commitment`` · ``fulfilment`` · ``cancelled``
    #: (``domain/procurement.STAGES``). **Neutral**, weil dieselben drei Stufen in beide
    #: Richtungen gelten; wie sie heissen, sagt der ``Flow``.
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="offer")

    #: ►►► **Kaufen oder verkaufen?** ◄◄◄ ``buy`` · ``sell`` (``domain/procurement``).
    #:
    #: Die eine Angabe, aus der jede Beschriftung, die Gegenpartei-Rolle und das Vorzeichen
    #: des Geldes folgen. Sie steht am **Beleg** und nicht am Modul, weil sie den Vorgang
    #: beschreibt – und weil ein laufender Auftrag seinen Prozess eingefroren trägt: käme
    #: sie aus dem Modultyp, änderte ein künftiger Umbau die Bedeutung alter Belege.
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="buy",
                                           server_default="buy")

    #: Die **gewählte** Gegenpartei – ``NULL``, solange nichts zugesagt ist.
    supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    #: Bestellsumme **netto**, für die ganze Menge. Der Stückpreis ist Summe ÷ Menge –
    #: eine abgeleitete Zahl gehört nicht als zweite Spalte daneben.
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CHF")

    #: **Die Sendungsnummer** – die eine Angabe, die erst nach der Bestellung entsteht.
    tracking: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    #: **Wann zugesagt wurde** – der Tag, an dem der Beleg die Schwelle überschritten hat.
    #:
    #: Ab hier läuft die Zahlungsfrist, und daraus folgt die Fälligkeit
    #: (``payments.due_on``). Sie steht als eigene Angabe, weil sie sonst nirgends steht:
    #: ``created_at`` ist die Anlage des Belegs (oft Wochen früher), und ``updated_at``
    #: verschiebt sich bei jeder Sendungsnummer. Ein Datum, das sich bewegt, taugt nicht
    #: als Beginn einer Frist.
    committed_on: Mapped[Optional[object]] = mapped_column(Date, nullable=True)

    #: Eine Zeile je angefragtem Lieferanten – siehe Klassen-Docstring.
    quotes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]")

    #: **Die Zeilen des Belegs – und sie sind die einzige Aussage über Was und Wieviel.**
    #:
    #: ``[{"article": <interner Schlüssel>, "quantity": 4}, …]``. ``NULL``, solange nichts
    #: bestellt ist: dann SIND die Zeilen, was vor dem Modul steht (``purchase.
    #: process_lines`` – Einzelinstanz → Instanz → Artikel). Ein Artikelfeld daneben wäre
    #: eine zweite Aussage über dieselbe Sache, und die getippte gewönne auch dann, wenn
    #: sie falsch ist.
    #:
    #: **Mehrere Zeilen sind der Normalfall, kein Sonderfall**: stehen Stücke zweier
    #: Artikel vor dem Modul, ist das EINE Bestellung mit zwei Positionen – wie im echten
    #: Leben. Darum eine Liste und nicht ein Artikel mit einer Menge.
    #:
    #: Mit der Bestellung frieren sie **ein**: dort ist eine zweite Partei gebunden.
    #: Verliert der Beleg danach seine Grundlage (ein Stück wird ausgesondert, eine
    #: Abweichung greift), vergleicht ``services/purchase`` diese Zeilen mit den heutigen:
    #: vor der Bestellung zieht er still nach, ab ihr **meldet** er und wartet auf die
    #: Bestätigung des Menschen. Ohne den Vermerk wüsste niemand, dass es einmal fünf waren.
    ordered_lines: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSONB, nullable=True)
