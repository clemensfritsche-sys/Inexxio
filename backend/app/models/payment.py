from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Payment(Base, TimestampMixin):
    """**Eine Zeile Geld an einem Beleg** – und mehr braucht es dafür nicht.

    ## Es gibt keine Forderungs-Tabelle

    *Offen* ist eine **Subtraktion**: Belegsumme − Gutschriften − Zahlungen
    (``services/payments.balance``). *Fällig* ist eine **Addition**: Zusagedatum +
    Zahlungsfrist. *Überfällig* ist beides zusammen. Drei Ableitungen, null Spalten – und
    damit gibt es keine Zahl, die stillschweigend von der Wirklichkeit abweichen kann.

    Eine Spalte «offener Betrag» wäre die zweite Wahrheit: sie müsste bei jeder Zahlung,
    jeder Gutschrift und jeder Mengenklärung nachgezogen werden, und die eine vergessene
    Stelle fällt erst auf, wenn jemand mahnt.

    ## Der Weg des Geldes ist ein FELD, kein Modell

    Überweisung und Karte sind **derselbe** Datensatz: Datum · Betrag · Weg · Referenz.
    Geschrieben werden beide durch dieselbe Funktion (``payments.record``) – bei der
    Überweisung von einem Menschen, bei der Karte vom Stripe-Webhook. Ein Provider-Rahmen
    mit zwei Implementierungen wäre eine Abstraktion über einer Zeile.

    Genau das war im Vorgängersystem anders: dort war Stripe **Quelle der Wahrheit** und
    das ERP der Spiegel – mit ``stripe_*``-Spalten an vier Tabellen, einem Webhook, der
    Aufträge erzeugte, und einem Aufräumer für verlassene Warenkörbe. Hier nennt das ERP
    Betrag und Währung, und der Webhook schreibt **eine Zeile**.

    ## Zwei Arten, weil zwei Dinge Verschiedenes bedeuten

    ``payment``  Geld ist geflossen. Positiv = es kam an (bzw. wir haben gezahlt),
                 **negativ** = es ging zurück (Erstattung).
    ``credit``   Die **Forderung** wird gemindert, ohne dass Geld fliesst: Gutschrift nach
                 einer Retoure, Kulanz, ein nachträglicher Abzug.

    Ohne diese Unterscheidung liesse sich «wie viel hat der Kunde wirklich gezahlt» nicht
    mehr beantworten – und eine Retoure sähe aus wie eine offene Rechnung. Mit ihr geht
    jeder Fall in **einer** Formel auf: 1 400 zugesagt, 1 400 bezahlt, 2 Stück zurück
    (140 Gutschrift, 140 erstattet) → 1 400 − 140 − 1 260 = **0**.

    **Ware und Geld bleiben entkoppelt**, und das ist keine Nachlässigkeit: eine Gutschrift
    ohne Rücknahme ist Kulanz, eine Rücknahme ohne Gutschrift ist Garantie. Gekoppelt wäre
    weder das eine noch das andere abbildbar.
    """

    __tablename__ = "payments"
    __table_args__ = (
        # **Dieselbe Referenz ist dieselbe Zahlung.** Der Schutz gegen die doppelt
        # zugestellte Webhook-Meldung – und gegen den Menschen, der denselben
        # Zahlungseingang zweimal erfasst. Partiell: ohne Referenz (Barzahlung, Gutschrift)
        # gibt es nichts zu vergleichen, und ein voller Index liesse dann nur eine einzige
        # referenzlose Zeile im ganzen System zu.
        Index("uq_payments_reference", "reference", unique=True,
              postgresql_where=text("reference IS NOT NULL AND is_active")),
        Index("ix_payments_purchase", "purchase_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    #: Der Beleg, an dem diese Zeile hängt. **Keine eigene Objektnummer** – dasselbe Muster
    #: wie beim Beleg selbst: sie läuft unter der Auftragsnummer.
    purchase_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: ``payment`` · ``credit`` (``domain/money.KINDS``).
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="payment")

    #: Der Betrag. **Darf negativ sein** – eine Erstattung ist eine Zahlung rückwärts, und
    #: sie als eigene Art zu führen hiesse, dasselbe zweimal zu erklären.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CHF")

    #: **Wann das Geld geflossen ist** – nicht, wann jemand es erfasst hat. Die beiden
    #: fallen regelmässig auseinander (Kontoauszug vom Freitag, erfasst am Montag), und
    #: ``created_at`` beantwortet die zweite Frage bereits.
    paid_at: Mapped[Optional[object]] = mapped_column(Date, nullable=True)

    #: Wie gezahlt wurde (``domain/money.METHODS``) – leer bei einer Gutschrift, denn dort
    #: fliesst kein Geld. Die Angabe ist mehr als Statistik: eine mit Karte bezahlte
    #: Rechnung wird über denselben Weg erstattet, nicht per Überweisung.
    method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    #: Die Referenz: Zahlungszweck, Beleg-Nummer der Bank – oder die Stripe-Id. **Ein
    #: Feld, zwei Wege**: wer sie schreibt, ändert nichts an dem, was sie ist.
    reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    #: Ein Satz dazu, falls einer nötig ist («Kulanz», «Teilzahlung 1/3»).
    note: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
