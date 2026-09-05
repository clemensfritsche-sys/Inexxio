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

from sqlalchemy import (
    BigInteger, Date, ForeignKey, Index, Integer, Numeric, String, text,
)
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

    #: ►►► **In welcher Währung?** – ISO 4217, drei Zeichen (``domain/currency``). ◄◄◄
    #:
    #: **Eine Währung je Vorgang, nicht je Zeile.** Zwei Positionen in verschiedenen
    #: Währungen auf einem Papier gibt es nicht – das wären zwei Belege.
    #:
    #: Sie steht **am Vorgang** und nicht nur am Unternehmen: die Vorgabe kommt von dort,
    #: aber ein laufender Vorgang muss auch dann noch sagen können, worin er lautet, wenn
    #: die Gesellschaft ihre Hauswährung wechselt. Eingefroren mit der **Zusage** – ab
    #: dort ist eine zweite Partei gebunden.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CHF")

    #: ``offer`` · ``agreed`` · ``done`` · ``cancelled`` (``domain/deal``).
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="offer")

    #: **Mit wem** – die Objektnummer der Gegenpartei. ``NULL``, solange niemand gewählt
    #: ist; die Zusage verlangt sie.
    party_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    #: **Was vereinbart ist.** Nicht «was gefordert» und nicht «was gezahlt» – das sind
    #: die Zeilen. Mit der Zusage ist dieser Wert gebunden: draussen liegt eine Zusage,
    #: die jemand gelesen hat.
    #: ►►► **Vier Nachkommastellen, nicht zwei** (Migration 128). ◄◄◄ Nicht, weil hier
    #: je so gerechnet würde – gerundet wird **je Währung** (``domain/currency.quantum``)
    #: –, sondern weil eine Spalte mit zwei Stellen einem dreistelligen Betrag (KWD)
    #: still die letzte abschneidet. Vier deckt jede ISO-4217-Währung ab.
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    #: **Zahlungsfrist in Tagen.** Vorgabe für die Fälligkeit einer neuen Rechnung –
    #: eine Rechnung trägt ihre eigene (``DealEntry.due_on``), weil zwei Rechnungen zu
    #: zwei Zeitpunkten fällig sind.
    due_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ►►► **``reference`` und ``note`` sind entfallen** (Testnotiz #812). ◄◄◄
    #
    # «Ich checke nicht, warum hier dieses Referenz-Eingabefeld ist» – zu Recht: es
    # beantwortete keine Frage, die jemand hat, und die Rechnungsnummer erzeugt der Dienst
    # längst selbst (``<Auftragsnummer>[-n]``). Damit hatte auch die Handlung ``note``
    # keinen Aufrufer mehr; beide sind mitgegangen.
    #
    # Die **Spalten** bleiben nach der Zwei-Deploy-Regel vorerst in der Datenbank stehen –
    # hier haben sie kein Mapping mehr (``docs/backlog.md``).

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

    ►►► **Storniert wird durch eine GEGENBUCHUNG, nie durch Löschen.** ◄◄◄

    Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen – wer die Zeile
    verschwinden lässt, behauptet, sie sei nie passiert (Testnotizen #823/#824). Eine
    Stornierung ist darum eine zweite Zeile: dieselbe Art, der negative Betrag,
    ``reverses_id`` auf die stornierte. Beide bleiben stehen, die Summe stimmt von selbst.

    Das ist **keine neue Mechanik**: eine Gutschrift ist längst eine negative Rechnung –
    eine Stornierung ist genau das, über den vollen Betrag.
    """

    __tablename__ = "deal_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    #: ``charge`` · ``payment`` (``domain/deal.KINDS``).
    kind: Mapped[str] = mapped_column(String(10), nullable=False)

    #: **Darf negativ sein** – das ist die Gutschrift bzw. die Erstattung.
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

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

    #: ►►► **Welche Zeile diese hier storniert** – oder ``None``. ◄◄◄
    #:
    #: Eine Stornierung ist eine **Gegenbuchung**, kein Löschen (Testnotizen #823/#824):
    #: dieselbe Art, der negative Betrag, und hier der Verweis auf die stornierte Zeile.
    #: Beide bleiben stehen, die Summe stimmt von selbst, und ein Beleg, der einmal
    #: draussen war, verschwindet nicht rückwirkend aus dem Nachweis.
    #:
    #: Zugleich ist es die **Sperre**: eine Zeile mit ``reverses_id`` lässt sich nicht
    #: stornieren, und eine, zu der es schon eine Gegenzeile gibt, ebenso wenig – sonst
    #: entstünde eine Kette aus Vorzeichen, in der niemand mehr sagen kann, was gilt.
    reverses_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("deal_entries.id", ondelete="SET NULL"), nullable=True, index=True)

    #: ►►► **Welche RECHNUNG diese Zahlung begleicht** – nur bei ``kind = payment``. ◄◄◄
    #:
    #: «Wenn ich eine Rechnung ausstelle, dann wird eine Zahlung auf genau diese Rechnung
    #: referenziert. Ich soll nicht eine Zahlung für zwei verschiedene Rechnungen erfassen
    #: können – dann lieber die zwei stornieren und eine daraus machen» (Testnotiz #858).
    #:
    #: **Eine Zahlung gehört zu genau einer Forderung.** Das ist die einfachere Regel und
    #: nicht die ärmere: der Weg für «eine Überweisung über zwei Rechnungen» ist eine
    #: **Stornorechnung und eine gemeinsame neue** – ein Vorgang, den es längst gibt, mit
    #: einem Beleg, den man vorzeigen kann. Die Alternative wäre eine Aufteilungstabelle
    #: (Ausziffern) für eine Zahl, die daneben ohnehin als Summe steht.
    #:
    #: ``balance`` bleibt davon **unberührt**: es rechnet weiter über die Summen. Diese
    #: Spalte beantwortet «worauf», nicht «wie viel» – zwei Fragen, ein Feld je Frage.
    #:
    #: ``None`` ist regulär und heisst «nicht zugeordnet»: so stehen die Zahlungen da, die
    #: es vor dieser Regel schon gab. Gelesen wird tolerant, geschrieben streng.
    charge_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("deal_entries.id", ondelete="SET NULL"), nullable=True, index=True)

    #: ►►► **Die Steuer-Aufteilung dieses Belegs – EINGEFROREN.** ◄◄◄
    #:
    #: ``[{"rate": "8.10", "net": "60.00", "tax": "4.86"}]`` – je vorkommendem Satz eine
    #: Zeile, Beträge als **String** (wo es auf den Rappen ankommt, wird nicht durch
    #: ``float`` gerechnet). Die Summe aus ``net`` und ``tax`` ist ``amount``.
    #:
    #: **Warum gespeichert und nicht gerechnet:** ein gebuchter Beleg behält seine
    #: Steuerangabe. Aus den Positionen nachgerechnet änderte sich die Steuer einer
    #: längst gestellten Rechnung, sobald jemand eine Position anfasst – eine rückwirkend
    #: geänderte Steuerangabe, und genau das darf es nicht geben (MWSTG Art. 26).
    #:
    #: ``None`` bei einer **Zahlung**: Geld trägt keine Steuer, es begleicht sie.
    vat: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)

    #: ►►► **Wann die Leistung erbracht wurde** (MWSTG Art. 26 Abs. 2 Bst. c). ◄◄◄
    #:
    #: **Nicht** das Rechnungsdatum, und der Unterschied zählt: bei einem Satzwechsel oder
    #: über den Jahreswechsel entscheidet **es**, welcher Satz gilt. Vorbelegt mit
    #: ``booked_on``, weil beide meistens zusammenfallen – ``None`` heisst «wie gebucht».
    service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
