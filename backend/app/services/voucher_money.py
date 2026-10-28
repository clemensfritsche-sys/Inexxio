"""►►► **Das Geld am Beleg** – Geld-Zeilen schreiben, Erstattungen, die Tür des
Zahlungsdienstes, die Überweisung (QR) und die Papiere, die danach anstehen. ◄◄◄

Liest Kern und Belegkopf; was nach einer Handlung oder Zahlung von selbst geschieht, steht in
``follow_up``.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import clock
from ..domain import voucher as vo
from ..models import (
    Order, ProcessStep,
    UserProfile, Voucher, VoucherDocument, VoucherEntry,
)
from . import qrbill
from .voucher import (
    amount_text, balance_of, corrects, documents_of, entries_of, hold, inbound,
    is_billed, minus, party_of, where_of,
)
from .voucher_head import (
    billing_of, creditor_of, is_done, issuer_company,
)


# ---------------------------------------------------------------------------
# ►► WAS NACH JEDER HANDLUNG VON SELBST GESCHIEHT
# ---------------------------------------------------------------------------

def follow_up(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              actor: Optional[UserProfile]) -> None:
    """►►► **Was nach jeder Handlung von selbst geschieht** – an EINER Stelle. ◄◄◄

    * **Die Quittung**: wird der Saldo einer Rechnung, die wir stellen, null, steht sie an
      (``papers_due``) – hinaus geht sie mit der Freigabe, von selbst nur, wo ``AUTO_RELEASE``
      sie nennt.
    * **Die Stücke ziehen weiter**, sobald sie dürfen (``passable``) – mit der Zusage, bei
      einer Vorauszahlung mit dem Geld (``process.advance_payments``).

    Gerufen auch vom Zahlungsdienst (``record_payment``), damit eine Kartenzahlung
    dasselbe auslöst wie eine erfasste.
    """
    from . import process as process_svc
    from . import voucher_docs
    if vo.RECEIPT_DOC in AUTO_RELEASE and vo.RECEIPT_DOC in papers_due(db, row):
        voucher_docs.issue(db, row=row, kind=vo.RECEIPT_DOC, actor=actor)
    process_svc.advance_payments(db, order=order,
                                 actor_id=actor.id if actor is not None else None)
    db.flush()


# ---------------------------------------------------------------------------
# ►► DIE EINE SCHREIBSTELLE EINER GELD-ZEILE
# ---------------------------------------------------------------------------

def booked_as(db: Session, reference: str) -> Optional[VoucherEntry]:
    """Die gültige Geld-Zeile mit dieser Referenz – oder ``None``."""
    return (db.query(VoucherEntry)
            .filter(VoucherEntry.reference == reference, VoucherEntry.is_active.is_(True))
            .first())


def reference_problem(db: Session, row: Voucher, reference: Optional[str]) -> Optional[str]:
    """►►► **Eine Referenz gehört zu genau einer Zahlung im Haus** – der Satz, oder ``None``."""
    seen = booked_as(db, reference) if reference else None
    if seen is None:
        return None
    where = "an einem anderen Beleg" if seen.voucher_id != row.id else "schon"
    return (f"Die Referenz «{reference}» ist {where} gebucht – zweimal dieselbe Zahlung "
            f"gibt es nicht.")


def book(db: Session, row: Voucher, entry: VoucherEntry) -> None:
    """►►► **Die eine Stelle, an der eine Geld-Zeile in die Datenbank geht.** ◄◄◄ Die
    Referenz prüft ``reference_problem``; trifft eine gleichzeitige Buchung denselben
    Unique-Index, kommt derselbe Satz als 409 statt eines Absturzes."""
    problem = reference_problem(db, row, entry.reference)
    if problem:
        raise HTTPException(status_code=409, detail=problem)
    try:
        with db.begin_nested():
            db.add(entry)
    except IntegrityError:
        raise HTTPException(status_code=409, detail=(
            reference_problem(db, row, entry.reference)
            or f"Die Referenz «{entry.reference}» ist schon gebucht."))


# ---------------------------------------------------------------------------
# ►► DIE PAPIERE, DIE ANSTEHEN
# ---------------------------------------------------------------------------

#: ►►► **Papiere, die ohne Freigabe hinausgehen.** ◄◄◄ Heute keines: jedes Papier sieht ein
#: Mensch, bevor es geht (Vorschau → Freigeben). Wer eines automatisieren will, nennt es hier –
#: die Bedingung, WANN es ansteht, bleibt dieselbe (``papers_due``).
AUTO_RELEASE: tuple[str, ...] = ()

#: Die Verben, die ein Papier hinausgeben – die Karte zeigt es vorher (``voucher_docs.preview``).
PAPER_VERBS = ("ask", "agree", "bill", "revoke", "remind", "release")


def papers_due(db: Session, row: Voucher) -> list[str]:
    """►►► **Welches Papier jetzt ansteht** – abgeleitet, nie gespeichert. ◄◄◄

    * **Auftragsbestätigung**: zugesagt, und es ging noch keine hinaus.
    * **Quittung**: eine Rechnung, die wir stellen, ist mit Geld beglichen, und es ging noch
      keine hinaus.

    Nur, wo wir den Beleg stellen und eine Partei feststeht."""
    if not vo.of(row.direction).collects or row.stage not in (vo.AGREED, vo.BILLED):
        return []
    if party_of(db, row) is None:
        return []
    out = []
    if row.agreed_on is not None and not documents_of(db, row, vo.CONFIRM_DOC):
        out.append(vo.CONFIRM_DOC)
    if (is_billed(row) and row.stage == vo.BILLED and not minus(row) and is_done(db, row)
            and balance_of(db, row).paid > 0 and not documents_of(db, row, vo.RECEIPT_DOC)):
        out.append(vo.RECEIPT_DOC)
    return out


def paper_candidates(db: Session) -> list[tuple[Voucher, int]]:
    """►►► **Welche Belege überhaupt ein Papier anstehen haben KÖNNTEN** – in SQL vorgefiltert:
    wir stellen sie, zugesagt oder gestellt, und es fehlt die Auftragsbestätigung bzw. (gestellt)
    die Quittung. Ob es wirklich ansteht, sagt ``papers_due`` – die Regel steht nur dort. ◄◄◄"""
    def missing(kind: str):
        return ~(db.query(VoucherDocument.id)
                 .filter(VoucherDocument.voucher_id == Voucher.id,
                         VoucherDocument.kind == kind, VoucherDocument.is_active.is_(True))
                 .exists())
    rows = (db.query(Voucher, Order.object_id).join(Order, Order.id == Voucher.order_id)
            .filter(Voucher.is_active.is_(True), Voucher.direction == vo.IN,
                    Voucher.stage.in_((vo.AGREED, vo.BILLED)),
                    missing(vo.CONFIRM_DOC)
                    | ((Voucher.stage == vo.BILLED) & missing(vo.RECEIPT_DOC)))
            .all())
    return [(r, int(oid)) for r, oid in rows]


# ---------------------------------------------------------------------------
# ►► DIE ZAHLUNGEN — was auf die eine Rechnung dieses Belegs geflossen ist
# ---------------------------------------------------------------------------
#
# **Keine Zuordnung**: die Rechnung *ist* der Beleg, zu dem die Zahlung gehört. Die
# Aufteilung über mehrere Rechnungen liegt über Modulgrenzen (offene-Posten-Liste,
# ``docs/backlog.md``).

def refund_reference(payment: str, refund: str) -> str:
    """**Die Referenz einer Erstattung** – die der Zahlung, ``:refund:`` und die Id der
    Erstattung beim Dienst. Je Erstattung eine Zeile, idempotent über diese Referenz."""
    return f"{payment}:refund:{refund}"


def refunded_on(db: Session, entry: VoucherEntry) -> Decimal:
    """►►► **Was von DIESER Karten-Zahlung schon zurückgegangen ist.** ◄◄◄ Die Zeilen, deren
    Referenz mit ``refund_reference(<Zahlung>, …)`` beginnt – über alle Belege: eine
    Erstattung aus einer Gutschrift steht an der Gutschrift und mindert die Zahlung trotzdem."""
    if not entry.reference:
        return Decimal("0")
    rows = (db.query(VoucherEntry)
            .filter(VoucherEntry.is_active.is_(True),
                    VoucherEntry.reference.startswith(refund_reference(entry.reference, ""),
                                                      autoescape=True))
            .all())
    return sum((abs(e.amount) for e in rows), Decimal("0"))


def refundable_amount(db: Session, entry: VoucherEntry) -> Decimal:
    """**Wie viel von dieser Zahlung noch zurückgegeben werden kann** – nie unter null."""
    rest = entry.amount - refunded_on(db, entry)
    return rest if rest > 0 else Decimal("0")


def refundable(db: Session, row: Voucher) -> list[VoucherEntry]:
    """**Die Karten-Zahlungen, die man zurückgeben kann** – jüngste zuerst.

    Nur eine **positive Karten-Zahlung** (bar und per Überweisung erstattet ein Mensch),
    solange etwas übrig ist, und nur, wo das Geld zu uns kam. An einer Gutschrift sind es
    die Karten-Zahlungen der Rechnung, die sie mindert – das Geld geht dorthin zurück,
    woher es kam.
    """
    source = corrects(db, row) if minus(row) else row
    if source is None or not inbound(source):
        return []
    return [e for e in reversed(entries_of(db, source))
            if e.method == vo.CARD and e.amount > 0
            and e.reference and refundable_amount(db, e) > 0]


def card_payment(db: Session, row: Voucher,
                 entry_id: Optional[int]) -> VoucherEntry:
    """**Welche Karten-Zahlung ist gemeint?** – oder ein Satz, warum keine.

    Zwei Formen einer Regel: ``can`` beantwortet **ob** es etwas zu erstatten gibt und
    zeigt darum den Knopf, diese Funktion **welche** und ist das Tor.
    """
    rows = refundable(db, row)
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=("Hier ist keine Karten-Zahlung offen, die sich erstatten liesse – es "
                    "gibt keine Karte, auf die es zurückgehen kann. Bar oder per "
                    "Überweisung erstattet man mit «Erstatten»."))
    if entry_id in (None, ""):
        return rows[0]
    found = next((e for e in rows if e.id == entry_id), None)
    if found is None:
        raise HTTPException(
            status_code=409,
            detail=("Diese Zahlung lässt sich nicht (mehr) über den Zahlungsdienst "
                    "erstatten – sie ist bereits zurückgegeben, gehört zu einem anderen "
                    "Beleg oder kam nicht per Karte."))
    return found


def of_reference(db: Session, reference: str) -> Optional[Voucher]:
    """**Zu welchem Beleg gehört diese Zahlungsreferenz?** – der Rückweg einer Erstattung."""
    found = booked_as(db, reference) if reference else None
    return (db.query(Voucher).filter(Voucher.id == found.voucher_id).first()
            if found is not None else None)


def record_payment(db: Session, *, row: Voucher, amount: Decimal,
                   reference: Optional[str] = None,
                   note: Optional[str] = None,
                   method: Optional[str] = None) -> VoucherEntry:
    """**Eine Zeile Geld** – die Tür des Zahlungsdienstes.

    Ein Zahlungsdienst ruft nicht ``apply``: er hat keinen angemeldeten Benutzer, keine
    Stufe und keine Meinung darüber, was jemand darf. Er meldet **eine Tatsache**.

    ►►► **Idempotent über die Referenz.** ◄◄◄ Ein Dienst stellt dieselbe Meldung mehrfach
    zu – das ist kein Fehler, das ist sein Auslieferungsversprechen. Und eine Referenz
    gehört zu genau **einer** Zahlung im Haus: taucht sie an einem *anderen* Beleg auf,
    ist das ein Irrtum und kein Duplikat – er wird **genannt**, denn ein stiller
    Nicht-Effekt ist schlimmer als ein Fehler.

    Gesperrt wird der Beleg zuerst (``hold``): zwei gleichzeitige Zustellungen derselben
    Meldung buchen eine Zeile, die zweite findet sie.
    """
    hold(db, row)
    seen = booked_as(db, reference) if reference else None
    if seen is not None and seen.voucher_id == row.id:
        return seen
    entry = VoucherEntry(
        voucher_id=row.id, amount=amount,
        booked_on=clock.today(), reference=reference, note=note, method=method,
    )
    book(db, row, entry)
    # **Dasselbe danach wie bei einer erfassten Zahlung** – Quittung, Stücke weiter.
    order, step = where_of(db, row)
    if order is not None and step is not None:
        follow_up(db, order=order, step=step, row=row, actor=None)
    return entry


# ---------------------------------------------------------------------------
# ►► DIE ÜBERWEISUNG — QR-Rechnung und Auskunft
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Transfer:
    """►►► **Die Überweisung an uns** – was Einzahlungsschein und Auskunft gleich lesen. ◄◄◄"""

    iban: Optional[str]
    creditor: dict[str, Any]
    debtor: dict[str, Any]
    amount: Decimal
    number: str
    reference: str
    #: Warum es keinen QR gibt – oder ``None`` (``qrbill.problem``).
    problem: Optional[str]
    qr: Optional[str]


def transfer_of(db: Session, row: Voucher) -> Transfer:
    """►►► **Die eine Ableitung der QR-Daten** – an den Aussteller, über den offenen Betrag. ◄◄◄

    Die **IBAN ist die von heute** (wohin gezahlt wird, friert nicht ein, ``freeze``), Name
    und Anschrift des Empfängers sind die eingefrorenen, der Zahlende kommt aus
    ``billing_of``. Wo es keinen QR geben kann, steht der Grund statt einer leeren Fläche.
    """
    iban = getattr(issuer_company(db, row), "iban", None)
    number = row.number or str(row.id)
    amount = balance_of(db, row).open
    creditor = dict((row.head or {}).get("creditor") or creditor_of(db, row))
    who = billing_of(db, row)
    seat = who.get("address") or {}
    debtor = {"name": who.get("name") or "", "street": seat.get("line1"), "street_nr": "",
              "zip": seat.get("postal_code"), "city": seat.get("city"),
              "country": seat.get("country")}
    trouble = qrbill.problem(iban=iban, currency=row.currency, amount=amount,
                             creditor=creditor)
    code = None if trouble else qrbill.svg(qrbill.payload(
        iban=iban or "", creditor=creditor, amount=amount,
        currency=row.currency, debtor=debtor, number=number))
    return Transfer(iban=iban, creditor=creditor, debtor=debtor, amount=amount,
                    number=number, reference=qrbill.reference(number), problem=trouble,
                    qr=code)


def transfer_info(db: Session, row: Voucher) -> dict[str, Any]:
    """**Wie man diese Rechnung überweist** – Bankverbindung im Klartext UND als QR.

    Nur an einer gestellten Rechnung, deren Geld **zu uns** kommt (``inbound``): an einer
    Lieferantenrechnung stünde sonst unsere eigene Bankverbindung.
    """
    if not (is_billed(row) and inbound(row)):
        raise HTTPException(status_code=404, detail=(
            "Zu diesem Beleg gibt es nichts zu überweisen – es steht keine Rechnung, deren "
            "Geld zu uns kommt."))
    t = transfer_of(db, row)
    return {
        "iban": t.iban, "creditor": t.creditor["name"], "reference": t.reference,
        "amount": amount_text(t.amount, row.currency), "currency": row.currency,
        "invoice": t.number, "qr": t.qr, "problem": t.problem,
    }
