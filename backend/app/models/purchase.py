from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import BigInteger, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Purchase(Base, TimestampMixin):
    """Der **Beleg** eines Beschaffungs-Moduls: was bestellt wird, bei wem, wie weit.

    **Keine eigene Objektnummer.** Er läuft unter der Auftragsnummer – dasselbe Muster
    wie jede andere Fachzeile des Prozesses (Erfassung, Ereignis). Eine zweite Nummer
    wäre ein zweiter Datensatz für denselben Vorgang, und der Feed hätte eine Zeile mehr,
    die niemand sucht.

    **Die Stufen gehören diesem Beleg, nicht dem Stück.** Eine Einzelinstanz ist von der
    Anfrage bis zum Wareneingang durchgehend ``Im Prozess``; sie wartet, sie ändert sich
    nicht. Wer den Bestellzustand an den Zustand des Stücks hängte, hätte Zustände
    erfunden, die keine Aussage über das Material sind.

    ``quotes`` ist die **Anfrage** – eine Zeile je angefragtem Lieferanten:
    ``{"supplier": <Objektnr>, "amount": "84.00", "lead_days": 5, "state": "offeriert"}``.
    Als JSONB und nicht als Tabelle, aus demselben Grund wie ``instances.reservations``:
    es ist eine Liste **an** diesem Beleg, keine eigene Sache. Beträge stehen als
    **String** – wo es auf den Rappen ankommt, wird nicht durch ``float`` gerechnet.

    ``supplier_id``/``amount`` sind die **getroffene Wahl** (die bestellte Zeile). Sie
    stehen als Spalten und nicht nur in ``quotes``, weil sie das sind, was den Beleg
    ausmacht: eine Bestellung hat genau einen Lieferanten und genau eine Summe, und
    danach fragt jede Auswertung.

    ``ordered_lines`` ist, **was** bestellt wurde – abgeleitet aus dem Prozess und mit der
    Bestellung eingefroren (siehe unten). Ein ``article_id`` gibt es nicht: der Beleg kann
    zwei Artikel führen, und welche es sind, sagen die Einzelinstanzen, die vor dem Modul
    stehen.

    ``reference`` ist, was der Lieferant zurückgibt – Bestellnummer, Link,
    Sendungsnummer. **Ein** Feld, weil es **eine** Frage ist: «woran erkennt er den
    Vorgang?». Drei Felder für drei Bestellarten wären dieselbe Angabe dreimal.
    """

    __tablename__ = "purchases"
    __table_args__ = (
        # **Ein Beleg je Modul** – die Regel in der Datenbank, nicht nur im Dienst:
        # ``instantiate_for_order`` ist idempotent, zwei gleichzeitige Freigaben sind es
        # nicht, und ein Index prüft je Anweisung.
        Index("uq_purchases_step", "step_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    #: Das Modul, zu dem dieser Beleg gehört. Bei mehreren Positionen teilen sich
    #: mehrere Belege denselben Schritt – jede Beschaffung schreitet eigenständig fort.
    step_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    #: ``anfrage`` · ``bestellung`` · ``wareneingang`` · ``storniert``
    #: (``domain/modules.Beschaffen.STAGES``).
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="anfrage")

    #: Der **gewählte** Lieferant – ``NULL``, solange nicht bestellt ist.
    supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    #: Bestellsumme **netto**, für die ganze Menge. Der Stückpreis ist Summe ÷ Menge –
    #: eine abgeleitete Zahl gehört nicht als zweite Spalte daneben.
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CHF")

    #: Bestellnummer beim Lieferanten, Link, Sendungsnummer – was er zurückgibt.
    reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

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
