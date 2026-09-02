"""**Der Geldvorgang und seine Zeilen** – die Tabellen des Moduls «Zahlung».

Zwei Tabellen, und die zweite ist der Grund, warum es keinen Modus braucht: ``deals``
trägt die **Zusage** (was vereinbart ist), ``deal_entries`` die **Forderungen** und die
**Zahlungen**. Weil beide Achsen getrennt sind, sind Vorauszahlung, Anzahlung,
Teilzahlung, Gutschrift und Erstattung dieselbe Mechanik in anderer Reihenfolge.

**Ohne Bezug zu ``purchases``/``invoices``/``payments``.** Das ist Absicht: dieses Modul
soll bestehen bleiben, wenn die Module «Beschaffen» und «Verkauf» eines Tages ersatzlos
gelöscht werden.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from typing import Any

from sqlalchemy import BigInteger, Date, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Deal(Base, TimestampMixin):
    """**Was mit einer zweiten Partei vereinbart ist** – je Modul einer.

    **Keine eigene Objektnummer.** Er läuft unter der Auftragsnummer – dasselbe Muster
    wie jede andere Fachzeile des Prozesses. Eine zweite Nummer wäre ein zweiter
    Datensatz für denselben Vorgang, und der Feed hätte eine Zeile mehr, die niemand
    sucht.

    **Die Stufen gehören diesem Vorgang, nicht dem Stück.** Eine Einzelinstanz ist vom
    Angebot bis zum Abschluss durchgehend ``Im Prozess``: sie wartet, sie ändert sich
    nicht. Ein Zustand «bestellt» an ihr wäre einer, der nichts über das Material
    aussagt – und den Statusliste, FIFO und Bestand beantworten müssten.

    **Die Richtung steht am Vorgang, nicht am Modultyp.** Ein laufender Auftrag trägt
    seinen Prozess eingefroren, und dieser Vorgang soll auch dann noch sagen können, was
    er war, wenn sein Modul längst anders eingestellt ist.
    """

    __tablename__ = "deals"
    __table_args__ = (
        # **Ein AKTIVER Vorgang je Modul** – die Regel in der Datenbank, nicht nur im
        # Dienst: ``ensure`` ist idempotent, zwei gleichzeitige Freigaben sind es nicht.
        # Partiell, weil ein zurückgenommener weiterhin als Zeile steht (Soft-Delete);
        # ein voller Index liesse danach keinen neuen mehr zu.
        Index("uq_deals_step", "step_id", unique=True,
              postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    #: Das Modul, zu dem dieser Vorgang gehört.
    step_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    #: ``in`` · ``out`` (``domain/deal``). Eingefroren bei der Anlage aus der
    #: Konfiguration des Schritts.
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="out")

    #: ``offer`` · ``agreed`` · ``done`` · ``cancelled`` (``domain/deal``).
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="offer")

    #: **Mit wem** – die Objektnummer der Gegenpartei. ``NULL``, solange niemand gewählt
    #: ist; die Zusage verlangt sie.
    party_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    #: **Was vereinbart ist.** Nicht «was gefordert» und nicht «was gezahlt» – das sind
    #: die Zeilen. Mit der Zusage ist dieser Wert gebunden: draussen liegt eine Zusage,
    #: die jemand gelesen hat.
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    #: **Zahlungsfrist in Tagen.** Vorgabe für die Fälligkeit einer neuen Rechnung –
    #: eine Rechnung trägt ihre eigene (``DealEntry.due_on``), weil zwei Rechnungen zu
    #: zwei Zeitpunkten fällig sind.
    due_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    #: **Ihre Nummer** – die Bestell- bzw. Auftragsnummer der Gegenpartei. Frei, weil es
    #: bei jedem anders aussieht.
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    #: Was nur ein Mensch weiss («Abholung ab 14 Uhr», «Rabatt telefonisch vereinbart»).
    note: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)

    #: Wann zugesagt wurde – der Anker, ab dem eine Zahlungsfrist läuft.
    agreed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: ►►► **Der Angebotsspiegel** – je zugelassener Gegenpartei eine Zeile. ◄◄◄
    #:
    #: ``[{"party": <Objektnr>, "amount": "84.00", "lead_days": 5, "payment_days": 30,
    #: "state": "offeriert"}]``
    #:
    #: Als **JSONB und nicht als Tabelle**, aus demselben Grund wie überall im Haus: es
    #: ist eine Liste **an** diesem Vorgang, keine eigene Sache. Beträge stehen als
    #: **String** – wo es auf den Rappen ankommt, wird nicht durch ``float`` gerechnet.
    #:
    #: Er ist zugleich die Antwort auf «woran ist dieser Betrachter beteiligt?»
    #: (``deal.mine``): eine Gegenpartei ist dort beteiligt, wo sie **angefragt** wurde.
    #: Gefiltert wird in der Datenbank (JSONB-Containment), nicht im Python.
    quotes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]",
    )

    #: **Was gehandelt wird** – abgeleitet aus dem Prozess und mit der Zusage eingefroren.
    #:
    #: ``[{"article": <Objektnr>, "quantity": 6}]``. Davor gibt es sie gar nicht: die
    #: Zeilen **sind** der Prozess und ziehen von selbst nach. Ab der Zusage ist eine
    #: zweite Partei gebunden, und was zugesagt wurde, ändert sich nicht mehr dadurch,
    #: dass der Auftrag später Stücke verliert.
    #:
    #: Ein ``article_id`` gibt es nicht: ein Vorgang kann zwei Artikel führen, und welche
    #: es sind, sagen die Einzelinstanzen.
    agreed_lines: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSONB, nullable=True,
    )


class DealEntry(Base, TimestampMixin):
    """**Eine Zeile Geld** – eine Forderung oder eine Zahlung.

    ``kind`` sagt, welche Achse: ``charge`` ist die **Forderung** (Rechnung, negativ =
    Gutschrift), ``payment`` das **Geld** (negativ = Erstattung).

    **Zwei Arten und nicht zwei Tabellen**: beide sind «eine Zeile Geld an diesem
    Vorgang», beide tragen Betrag, Datum, Nummer und Notiz. **Und zwei Arten und nicht
    eine**: ohne die Unterscheidung liesse sich «wie viel hat er wirklich gezahlt» nicht
    mehr beantworten, und eine Gutschrift sähe aus wie eine offene Rechnung.

    **Korrigiert wird durch Stornieren der Zeile** (``is_active = False``), nicht durch
    Überschreiben: was einmal gebucht war, bleibt lesbar. Wer eine echte Gegenbuchung
    will, erfasst eine negative Zeile – beides ist möglich, und beides ist ehrlich.
    """

    __tablename__ = "deal_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    #: ``charge`` · ``payment`` (``domain/deal.KINDS``).
    kind: Mapped[str] = mapped_column(String(10), nullable=False)

    #: **Darf negativ sein** – das ist die Gutschrift bzw. die Erstattung.
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    #: Wann die Zeile gilt – Rechnungsdatum bzw. Valuta.
    booked_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Nur bei einer Forderung**: wann sie fällig ist. Je Rechnung eine eigene, weil
    #: eine Anzahlung und eine Schlussrechnung zu zwei Zeitpunkten fällig sind.
    due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    #: **Die Nummer dieser Zeile.** Wer sie vergibt, sagt die Richtung: bei einer
    #: **Einnahme** nummerieren wir (``<Auftragsnummer>-<laufend>``), bei einer
    #: **Ausgabe** erfassen wir seine. Eine Zahlung trägt hier ihren Zahlungszweck bzw.
    #: die Referenz des Zahlungsdienstes.
    reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
