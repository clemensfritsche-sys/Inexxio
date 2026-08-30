"""**Das Geld an einem Beleg — eine Schreibstelle, drei Ableitungen.**

``record``   die **eine** Stelle, an der eine Zahlung entsteht. Überweisung und Karte
             gehen beide hier durch: bei der einen ruft ein Mensch den Endpunkt, bei der
             anderen der Webhook. Zwei Schreibwege wären zwei Stellen, an denen dieselbe
             Regel steht – und die zweite bekäme den nächsten Fix nicht mit.
``balance``  Belegsumme − Gutschriften − Zahlungen. **Es gibt keine Forderungs-Spalte**;
             eine wäre die zweite Wahrheit, die bei jeder Zahlung, jeder Gutschrift und
             jeder Mengenklärung nachgezogen werden müsste.
``due_on``   Zusagedatum + Zahlungsfrist. Auch eine Ableitung – ein Termin, den jemand
             tippt, ist bei der ersten Verschiebung falsch (dieselbe Regel wie beim
             Liefertermin, Testnotiz #745).

**Ware und Geld bleiben entkoppelt** (PROCESS_CORE §9.10): eine Gutschrift ohne Rücknahme
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
from ..models import Payment, Purchase


def _bad(exc: ValueError) -> HTTPException:
    """Eine Regel des Kerns in die Sprache der API übersetzen. Der Satz bleibt derselbe."""
    return HTTPException(status_code=400, detail=str(exc))


def record(db: Session, *, purchase: Purchase, amount: Any, kind: str = money.PAYMENT,
           method: Optional[str] = None, reference: Optional[str] = None,
           paid_at: Optional[date] = None, note: Optional[str] = None) -> Payment:
    """►►► **Die eine Stelle, an der Geld gebucht wird.** ◄◄◄

    **Idempotent über die Referenz.** Dieselbe Referenz ist dieselbe Zahlung – der
    Zahlungsdienst stellt seine Meldungen mehrfach zu (das ist zugesichert, nicht die
    Ausnahme), und ein Mensch erfasst denselben Kontoauszug auch schon mal zweimal. Statt
    einer Fehlermeldung kommt die **bereits gebuchte Zeile** zurück: der Aufrufer hat
    bekommen, was er wollte, und muss keinen Sonderfall behandeln.

    Der Betrag darf **negativ** sein – eine Erstattung ist eine Zahlung rückwärts. Eine
    eigene Art dafür hiesse, dasselbe zweimal zu erklären.

    Was hier **nicht** passiert: die Stufe des Belegs ändern. Geld und Ware sind zwei
    Ebenen; eine Zahlung macht aus einem Angebot keine Zusage, und eine ausbleibende
    Zahlung macht aus einer Lieferung keine Nicht-Lieferung. Wer beides koppelte, könnte
    weder Vorkasse noch Rechnung abbilden.
    """
    try:
        kind = money.assert_kind(kind)
        value = money.parse(amount, field="Betrag", signed=True)
        method = money.assert_method(method, kind=kind)
    except ValueError as exc:
        raise _bad(exc)

    ref = (reference or "").strip() or None
    if ref is not None:
        seen = (
            db.query(Payment)
            .filter(Payment.reference == ref, Payment.is_active.is_(True))
            .first()
        )
        if seen is not None:
            return seen

    row = Payment(
        purchase_id=purchase.id, kind=kind, amount=value,
        currency=purchase.currency or "CHF", method=method, reference=ref,
        paid_at=paid_at or date.today(), note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def of_purchase(db: Session, purchase: Purchase) -> list[Payment]:
    """Die Zeilen eines Belegs – älteste zuerst, damit die Liste eine Geschichte erzählt."""
    return (
        db.query(Payment)
        .filter(Payment.purchase_id == purchase.id, Payment.is_active.is_(True))
        .order_by(Payment.paid_at, Payment.id)
        .all()
    )


def balance(db: Session, purchase: Purchase) -> money.Balance:
    """**Was ist an diesem Beleg noch offen?** – gerechnet, nie gespeichert.

    Zwei Summen in **einer** Abfrage: eine je Art. Bei einem Beleg ohne jede Zeile sind
    beide null, und ``open`` ist schlicht die Belegsumme – ohne dass dieser Fall irgendwo
    als solcher steht.
    """
    rows = (
        db.query(Payment.kind, func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.purchase_id == purchase.id, Payment.is_active.is_(True))
        .group_by(Payment.kind)
        .all()
    )
    sums = {str(k): Decimal(str(v)) for k, v in rows}
    return money.Balance(
        total=Decimal(str(purchase.amount)) if purchase.amount is not None else None,
        credited=sums.get(money.CREDIT, Decimal("0")),
        paid=sums.get(money.PAYMENT, Decimal("0")),
    )


def payment_days(purchase: Purchase) -> Optional[int]:
    """Die vereinbarte Zahlungsfrist – aus der **gewählten** Angebotszeile.

    Sie steht dort und nicht als Spalte am Beleg, weil sie zum Angebot gehört: zwei
    Lieferanten dürfen verschiedene Fristen nennen, und welche gilt, entscheidet sich mit
    der Zusage. Eine Spalte daneben wäre eine Kopie, die bei einem Wechsel der Wahl
    stehenbliebe.
    """
    for quote in purchase.quotes or []:
        if quote.get("state") == procurement.CHOSEN:
            days = quote.get("payment_days")
            return int(days) if days not in (None, "") else None
    return None


def due_on(purchase: Purchase) -> Optional[date]:
    """**Wann ist das Geld fällig?** Zusagedatum + Frist – oder ``None``.

    ``None`` heisst «steht nicht fest», und das ist eine ehrliche Antwort: ohne Zusage
    gibt es keinen Beginn, ohne Frist keine Dauer. Ein geratenes Datum wäre schlimmer als
    keines – daraus würde gemahnt.
    """
    days = payment_days(purchase)
    if days is None or purchase.committed_on is None:
        return None
    return purchase.committed_on + timedelta(days=days)


def is_overdue(db: Session, purchase: Purchase, *, today: Optional[date] = None) -> bool:
    """**Überfällig?** Fällig, und es ist noch etwas offen. Beides zusammen, sonst nicht.

    Ein Beleg, der bezahlt ist, wird nicht überfällig, nur weil das Datum vergeht; und
    einer ohne Fälligkeit wird es nie – dort ist nichts vereinbart, was verstreichen
    könnte.
    """
    when = due_on(purchase)
    if when is None:
        return False
    return when < (today or date.today()) and balance(db, purchase).open > 0


def entries(db: Session, purchase: Purchase) -> list[dict[str, Any]]:
    """Die Zeilen als Auskunft – für die Karte, in der Reihenfolge ihres Entstehens."""
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "kind_label": money.KIND_LABELS.get(row.kind, row.kind),
            "amount": float(row.amount),
            "method": row.method,
            "method_label": money.METHOD_LABELS.get(row.method or "", ""),
            "reference": row.reference,
            "paid_at": row.paid_at.isoformat() if row.paid_at else None,
            "note": row.note,
        }
        for row in of_purchase(db, purchase)
    ]


def assert_payable(purchase: Purchase) -> None:
    """**Darf an diesem Beleg überhaupt Geld gebucht werden?**

    Erst ab der Zusage: vorher gibt es keine Summe, und eine Zahlung auf ein Angebot, das
    niemand angenommen hat, wäre Geld ohne Grundlage. Ein Storno ist dagegen **kein**
    Hindernis – eine Erstattung nach einer Stornierung ist genau der Normalfall.
    """
    if purchase.amount is None or procurement.normalize(purchase.stage) == \
            procurement.STAGES[0]:
        flow = procurement.of(purchase.direction)
        raise HTTPException(
            status_code=409,
            detail=(f"Der Beleg steht erst auf «{flow.label_of(procurement.STAGES[0])}» – "
                    f"ohne zugesagte Summe gibt es nichts zu bezahlen."),
        )
