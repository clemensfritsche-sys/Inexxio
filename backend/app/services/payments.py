"""**Das Geld an einem Beleg — eine Schreibstelle, drei Ableitungen.**

``record``   die **eine** Stelle, an der eine Zahlung entsteht. Überweisung und Karte
             gehen beide hier durch: bei der einen ruft ein Mensch den Endpunkt, bei der
             anderen der Webhook. Zwei Schreibwege wären zwei Stellen, an denen dieselbe
             Regel steht – und die zweite bekäme den nächsten Fix nicht mit.
``balance``  **Forderungen − Zahlungen** (``services/invoices`` liefert die erste Summe).
             Es gibt keine Spalte «offener Betrag»; eine wäre die zweite Wahrheit, die bei
             jeder Buchung nachgezogen werden müsste.

**Die Fälligkeit steht nicht mehr hier** – sie gehört der Rechnung, nicht dem Beleg: eine
Zusage hat keine, eine Rechnung schon, und zwei Rechnungen haben zwei.

**Ware, Forderung und Geld bleiben entkoppelt** (PROCESS_CORE §9.11): eine Gutschrift ohne Rücknahme
ist Kulanz, eine Rücknahme ohne Gutschrift ist Garantie. Dieses Modul weiss darum nichts
über Einzelinstanzen – es kennt einen Beleg und Beträge.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain import money, procurement
from ..models import Order, Payment, Purchase


def _bad(exc: ValueError) -> HTTPException:
    """Eine Regel des Kerns in die Sprache der API übersetzen. Der Satz bleibt derselbe."""
    return HTTPException(status_code=400, detail=str(exc))


def _elsewhere(db: Session, ref: str, seen: Payment) -> HTTPException:
    """**Diese Referenz ist schon vergeben — und zwar dort.**

    Der Satz nennt den **Auftrag**, nicht nur die Referenz: «ist bereits gebucht» liesse
    den Menschen suchen, und genau dieses Suchen ist die Arbeit, die eine Fehlermeldung
    abnehmen soll. Der Beleg selbst hat keine eigene Objektnummer – er läuft unter der
    seines Auftrags –, also ist die Auftragsnummer die einzige, die es zu nennen gibt.

    Zu lesen gibt es hier nichts Fremdes: ``pay`` ist eine Handlung des **Personals**
    (``SUPPLIER_ACTIONS`` filtert sie weg), und Personal sieht jeden Auftrag ohnehin.
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
        detail=f"Die Referenz «{ref}» ist bereits {where} gebucht. Eine Referenz gehört "
               f"zu genau einer Zahlung – bitte eine andere angeben oder leer lassen.",
    )


def record(db: Session, *, purchase: Purchase, amount: Any,
           method: Optional[str] = None, reference: Optional[str] = None,
           paid_at: Optional[date] = None, note: Optional[str] = None,
           manual: bool = False) -> Payment:
    """►►► **Die eine Stelle, an der Geld gebucht wird.** ◄◄◄

    **Idempotent über die Referenz — am SELBEN Beleg.** Dieselbe Referenz ist dieselbe
    Zahlung: der Zahlungsdienst stellt seine Meldungen mehrfach zu (das ist zugesichert,
    nicht die Ausnahme), und ein Mensch erfasst denselben Kontoauszug auch schon mal
    zweimal. Statt einer Fehlermeldung kommt die **bereits gebuchte Zeile** zurück – der
    Aufrufer hat bekommen, was er wollte, und muss keinen Sonderfall behandeln.

    **An einem ANDEREN Beleg ist dieselbe Referenz dagegen ein Irrtum, und er wird
    genannt.** Eine Referenz identifiziert genau eine Zahlung im ganzen Haus – so ist der
    Unique-Index gebaut, und so sind die beiden echten Quellen: ein ``payment_intent`` ist
    global eindeutig, eine QR-Referenz ebenso. Ohne die Unterscheidung fand die Prüfung
    die **fremde** Zeile und gab sie zurück: der Aufrufer bekam ``200``, an *seinem* Beleg
    war nichts gebucht, der offene Betrag stand unverändert da – und nichts sagte, warum.
    Ein stiller Nicht-Effekt ist schlimmer als ein Fehler; wer wirklich zweimal buchen
    muss, unterscheidet die Referenzen oder lässt sie leer (dann greift die Idempotenz
    gar nicht).

    Der Betrag darf **negativ** sein – eine Erstattung ist eine Zahlung rückwärts. Eine
    eigene Art dafür hiesse, dasselbe zweimal zu erklären.

    Was hier **nicht** passiert: die Stufe des Belegs ändern. Geld und Ware sind zwei
    Ebenen; eine Zahlung macht aus einem Angebot keine Zusage, und eine ausbleibende
    Zahlung macht aus einer Lieferung keine Nicht-Lieferung. Wer beides koppelte, könnte
    weder Vorkasse noch Rechnung abbilden.
    """
    try:
        value = money.parse(amount, field="Betrag", signed=True)
        method = money.assert_method(method, manual=manual)
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
            if seen.purchase_id != purchase.id:
                raise _elsewhere(db, ref, seen)
            return seen

    row = Payment(
        purchase_id=purchase.id, amount=value,
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

    ``offen = Forderungen − Zahlungen``. Beide Summen sind Ableitungen; es gibt keine
    Spalte «offener Betrag», die bei jeder Buchung nachgezogen werden müsste.

    **Vorher stand hier die Zusage als Forderung** (``purchase.amount`` minus Zahlungen
    minus Gutschriften). Das ging genau so lange gut, wie zugesagt und berechnet dasselbe
    waren; an Anzahlung, Teilrechnung und zwei Fälligkeiten brach es still. ``total``
    reist trotzdem mit – als **Zusage**, aus der ``uncharged`` folgt («zugesagt, noch nicht
    berechnet»), und das ist zugleich die Vorgabe für die nächste Rechnung.
    """
    from . import invoices
    paid = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.purchase_id == purchase.id, Payment.is_active.is_(True))
        .scalar()
    )
    return money.Balance(
        total=Decimal(str(purchase.amount)) if purchase.amount is not None else None,
        charged=invoices.charged(db, purchase),
        paid=Decimal(str(paid or 0)),
    )


# ►►► **Fälligkeit gehört der RECHNUNG, nicht dem Beleg.** ◄◄◄
#
# Hier standen ``payment_days``, ``due_on`` und ``is_overdue`` – abgeleitet aus
# ``committed_on + Zahlungsfrist``. Das konnte genau den Fall «eine Rechnung»: eine Zusage
# hat keine Fälligkeit, eine Rechnung schon, und **zwei Rechnungen haben zwei**. Sie leben
# jetzt in ``services/invoices`` (``payment_days`` als **Vorgabe**, ``due_on`` als die
# früheste offene Fälligkeit). Ein Alias hier wäre ein zweiter Weg zu derselben Antwort.


def entries(db: Session, purchase: Purchase) -> list[dict[str, Any]]:
    """Die Zeilen als Auskunft – für die Karte, in der Reihenfolge ihres Entstehens."""
    return [
        {
            "id": row.id,
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
