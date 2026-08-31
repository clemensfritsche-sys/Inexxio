"""**Die Forderung an einem Beleg — eine Schreibstelle, dieselbe Bauart wie das Geld.**

``record``    die **eine** Stelle, an der eine Rechnung entsteht. Idempotent über die
              Nummer – am selben Beleg dieselbe Rechnung, an einem anderen ein Irrtum mit
              Nennung des Auftrags (wörtlich dieselbe Form wie ``payments.record``; zwei
              Formulierungen wären zwei Massstäbe).
``next_number`` wie unsere Nummer lautet – ``<Auftragsnummer>-<laufend>``.
``display``   wie sie nach aussen aussieht: das ``-1`` der ersten fällt weg.
``charged``   die Summe der Forderungen. Gutschriften zählen negativ, weil sie **negative
              Rechnungen** sind – keine eigene Art, kein Sonderfall.

**Ware und Geld bleiben entkoppelt** (PROCESS_CORE §9.11): eine Gutschrift ohne Rücknahme
ist Kulanz, eine Rücknahme ohne Gutschrift ist Garantie. Dieses Modul weiss darum nichts
über Einzelinstanzen – es kennt einen Beleg und Beträge.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain import money, procurement
from ..models import Invoice, Order, Purchase

#: Was zwischen Auftragsnummer und laufender Zahl steht. Dieselbe Trennung wie bei der
#: Einzelinstanz – und aus demselben Grund an **einer** Stelle: wer sie zweimal
#: hinschreibt, hat beim nächsten Format zwei Wahrheiten.
SEP = "-"

#: Die laufende Zahl der **ersten** Rechnung. Sie ist eine Lesehilfe und fällt nach aussen
#: weg (``display``) – gespeichert bleibt sie, sonst wäre die zweite Rechnung eines
#: Auftrags nicht mehr von der ersten zu unterscheiden.
FIRST = 1


def _bad(exc: ValueError) -> HTTPException:
    """Eine Regel des Kerns in die Sprache der API übersetzen. Der Satz bleibt derselbe."""
    return HTTPException(status_code=400, detail=str(exc))


def _elsewhere(db: Session, number: str, seen: Invoice) -> HTTPException:
    """**Diese Nummer ist schon vergeben — und zwar dort.**

    Wörtlich dieselbe Form wie ``payments._elsewhere``: der Satz nennt den **Auftrag**,
    nicht nur die Nummer. «Ist bereits vergeben» liesse den Menschen suchen, und genau
    dieses Suchen soll eine Fehlermeldung abnehmen.
    """
    order_no = (
        db.query(Order.object_id)
        .join(Purchase, Purchase.order_id == Order.id)
        .filter(Purchase.id == seen.purchase_id)
        .scalar()
    )
    where = f"am Auftrag {order_no}" if order_no else "an einem anderen Beleg"
    return HTTPException(
        status_code=409,
        detail=f"Die Rechnungsnummer «{number}» gibt es bereits {where}. Eine Nummer "
               f"gehört zu genau einer Rechnung – bitte eine andere angeben.",
    )


def of_purchase(db: Session, purchase: Purchase) -> list[Invoice]:
    """Die Rechnungen eines Belegs – älteste zuerst, damit die Liste eine Geschichte ist."""
    return (
        db.query(Invoice)
        .filter(Invoice.purchase_id == purchase.id, Invoice.is_active.is_(True))
        .order_by(Invoice.issued_on, Invoice.id)
        .all()
    )


def charged(db: Session, purchase: Purchase) -> Decimal:
    """**Was an diesem Beleg gefordert wird** – gerechnet, nie gespeichert."""
    total = (
        db.query(func.coalesce(func.sum(Invoice.amount), 0))
        .filter(Invoice.purchase_id == purchase.id, Invoice.is_active.is_(True))
        .scalar()
    )
    return Decimal(str(total or 0))


def next_number(db: Session, purchase: Purchase) -> Optional[str]:
    """►►► **Unsere Rechnungsnummer: ``<Auftragsnummer>-<laufend>``.** ◄◄◄

    ``None``, wo die Gegenpartei nummeriert (``THEIR_NUMBER``) – dort ist die Nummer eine
    **Eingabe**, und eine erfundene Vorgabe wäre eine Behauptung über ein fremdes Dokument.

    Kumulierend über **alle** Rechnungen des Belegs, auch die stornierten: eine einmal
    vergebene Nummer wird nicht neu ausgegeben. Das ist dieselbe Regel wie beim Suffix der
    Einzelinstanz und aus demselben Grund – eine wiederverwendete Nummer wäre zwei
    Dokumente mit einem Namen.
    """
    if procurement.of(purchase.direction).invoice_number != procurement.OWN_NUMBER:
        return None
    order_no = (
        db.query(Order.object_id).filter(Order.id == purchase.order_id).scalar()
    )
    if order_no is None:
        return None
    used = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.purchase_id == purchase.id)
        .scalar()
    ) or 0
    return f"{order_no}{SEP}{used + FIRST}"


def display(number: Optional[str]) -> str:
    """**Wie die Nummer nach aussen aussieht:** ohne das ``-1`` der ersten Rechnung.

    Die laufende Zahl ist eine Lesehilfe; bei genau einer Rechnung sagt sie nichts, was
    die Auftragsnummer nicht schon sagt. Ab der zweiten steht sie da – sonst trügen zwei
    Rechnungen desselben Auftrags denselben Namen.

    **Eine Stelle, ein Format.** Wer die Nummer irgendwo selbst zurechtschneidet, hat
    beim nächsten Format zwei Fassungen.
    """
    text = (number or "").strip()
    return text[: -len(f"{SEP}{FIRST}")] if text.endswith(f"{SEP}{FIRST}") else text


def record(db: Session, *, purchase: Purchase, amount: Any,
           number: Optional[str] = None, issued_on: Optional[date] = None,
           due_on: Optional[date] = None, note: Optional[str] = None) -> Invoice:
    """►►► **Die eine Stelle, an der eine Forderung entsteht.** ◄◄◄

    Der Betrag darf **negativ** sein – das ist die Gutschrift. Keine eigene Art, kein
    zweiter Weg: dieselbe Zeile, dasselbe Feld, ein anderes Vorzeichen.

    **Idempotent über die Nummer, am selben Beleg** – und an einem anderen ein Irrtum, der
    genannt wird. Dieselbe Regel wie bei ``payments.record`` und aus demselben Grund: ein
    stiller Nicht-Effekt ist schlimmer als ein Fehler.

    Was hier **nicht** passiert: die Stufe des Belegs ändern. Eine Rechnung macht aus
    einem Angebot keine Zusage – und sie macht aus einer nicht gelieferten Ware keine
    gelieferte. Ware, Forderung und Geld sind drei Achsen (``domain/money``).
    """
    try:
        value = money.parse(amount, field="Betrag", signed=True)
    except ValueError as exc:
        raise _bad(exc)

    ref = (number or "").strip() or None
    if ref is not None:
        seen = (
            db.query(Invoice)
            .filter(Invoice.number == ref, Invoice.is_active.is_(True))
            .first()
        )
        if seen is not None:
            if seen.purchase_id != purchase.id:
                raise _elsewhere(db, ref, seen)
            return seen

    row = Invoice(
        purchase_id=purchase.id, number=ref, amount=value,
        currency=purchase.currency or "CHF",
        issued_on=issued_on or date.today(), due_on=due_on,
        note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def payment_days(purchase: Purchase) -> Optional[int]:
    """Die vereinbarte Zahlungsfrist – aus der **gewählten** Angebotszeile.

    Sie steht dort und nicht als Spalte am Beleg, weil sie zum Angebot gehört: zwei
    Gegenparteien dürfen verschiedene Fristen nennen, und welche gilt, entscheidet sich mit
    der Zusage. Eine Spalte daneben wäre eine Kopie, die bei einem Wechsel der Wahl
    stehenbliebe.

    Sie ist jetzt eine **Vorgabe** für die Fälligkeit der nächsten Rechnung, nicht mehr
    deren Quelle: gültig ist, was an der Rechnung steht.
    """
    for quote in purchase.quotes or []:
        if quote.get("state") == procurement.CHOSEN:
            days = quote.get("payment_days")
            return int(days) if days not in (None, "") else None
    return None


def default_due(purchase: Purchase, *, issued: Optional[date] = None) -> Optional[date]:
    """**Vorgabe für die Fälligkeit:** Rechnungsdatum + vereinbarte Frist.

    ``None`` heisst «steht nicht fest», und das ist eine ehrliche Antwort: ohne Frist gibt
    es keine Dauer. Ein geratenes Datum wäre schlimmer als keines – daraus würde gemahnt.
    """
    days = payment_days(purchase)
    return None if days is None else (issued or date.today()) + timedelta(days=days)


def due_on(db: Session, purchase: Purchase) -> Optional[date]:
    """**Wann wird an diesem Beleg als Nächstes etwas fällig?**

    Die **früheste** Fälligkeit unter den offenen Rechnungen. Vorher war es eine Ableitung
    aus dem Zusagedatum – die konnte nur den Fall «eine Rechnung» und wurde bei einer
    Anzahlung stillschweigend falsch.
    """
    dates = [row.due_on for row in of_purchase(db, purchase)
             if row.due_on is not None and row.amount > 0]
    return min(dates) if dates else None


def is_overdue(db: Session, purchase: Purchase, *, today: Optional[date] = None) -> bool:
    """**Überfällig?** Eine Fälligkeit ist verstrichen, und es ist noch etwas offen.

    Beides zusammen, sonst nicht: ein bezahlter Beleg wird nicht überfällig, nur weil das
    Datum vergeht, und einer ohne Fälligkeit wird es nie – dort ist nichts vereinbart, was
    verstreichen könnte.
    """
    from . import payments
    when = due_on(db, purchase)
    if when is None:
        return False
    return when < (today or date.today()) and payments.balance(db, purchase).open > 0


def entries(db: Session, purchase: Purchase) -> list[dict[str, Any]]:
    """Die Rechnungen als Auskunft – für die Karte, in der Reihenfolge ihres Entstehens."""
    return [
        {
            "id": row.id,
            "number": row.number,
            "number_label": display(row.number),
            "amount": float(row.amount),
            "issued_on": row.issued_on.isoformat() if row.issued_on else None,
            "due_on": row.due_on.isoformat() if row.due_on else None,
            "note": row.note,
        }
        for row in of_purchase(db, purchase)
    ]
