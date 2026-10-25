"""►►► **Die Zahlungen einer Person bzw. einer eigenen Gesellschaft – eine Ableitung.** ◄◄◄

Keine eigene Liste: jede Zeile ist ein Zahlungsmodul (``vouchers``), gelesen über die
Angebotszeile der Person bzw. die ausstellende Gesellschaft. **Neueste Nummer zuoberst,
ohne Datum.** Der Betrag sagt alles: ``+`` kommt zu uns, ``−`` geht von uns; der Ton sagt
den Stand (überfällig · ausstehend · bezahlt · storniert). Ein Klick öffnet den Auftrag –
Abkürzungs-Knöpfe gibt es nicht.

**Überfälliges zählt in die Zahl am Symbol der Person** (``services/todo``) – eine eigene
Mahnliste gibt es nicht; erinnert wird im Modul.
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..domain import currency as cur
from ..domain import voucher as vo
from ..models import Order, UserProfile, Voucher, VoucherQuote
from . import sites
from . import voucher as vs

#: Der Stand einer Zeile – Wort und Ton (``overdue`` rot · ``open`` schwarz · ``paid`` grün ·
#: ``void`` grau).
STATES: dict[str, str] = {"overdue": "überfällig", "open": "ausstehend", "paid": "bezahlt",
                          "void": "storniert"}


def kind_of(row: Voucher) -> str:
    """**Was diese Zeile ist** – das Wort des Papiers in seiner Stufe."""
    if vs.minus(row):
        return vo.CREDIT_NOUN
    flow = vo.of(row.direction)
    if row.stage == vo.OFFER:
        return flow.label_of(vo.OFFER)
    if row.stage == vo.AGREED or (row.stage == vo.CANCELLED and row.billed_on is None):
        return flow.label_of(vo.AGREED)
    return "Rechnung" if flow.collects else "Lieferantenrechnung"


def state_of(db: Session, row: Voucher) -> str:
    if row.stage == vo.CANCELLED:
        return "void"
    if vs.is_done(db, row):
        return "paid"
    return "overdue" if vs.overdue(db, row) else "open"


def _amount(db: Session, row: Voucher, party: Optional[int]) -> Optional[str]:
    """Der Betrag der Zeile – die Rechnung, sonst die Zusage, sonst das Angebot."""
    value = row.amount if row.billed_on is not None else vs.agreed_amount(db, row)
    if value is None:
        quotes = [q for q in vs.quotes_of(db, row)
                  if q.amount is not None and (party is None or q.party_id == party)]
        value = quotes[-1].amount if quotes else None
    return cur.money(value, row.currency) if value is not None else None


def row_of(db: Session, row: Voucher, order: Optional[Order],
           party: Optional[int]) -> dict[str, Any]:
    """Eine Zeile der Liste – Nummer · Art · Auftrag · Partei · Betrag ± · Stand."""
    inbound = vo.inbound(collects=vo.of(row.direction).collects, minus=vs.minus(row))
    who = party or vs.party_of(db, row) or vs.addressee_of(db, row)
    name = None
    if who is not None:
        u = db.query(UserProfile).filter(UserProfile.object_id == who).first()
        name = u.display_name if u is not None else None
    state = state_of(db, row)
    return {
        "voucher_id": row.id,
        "number": row.number or (str(order.object_id) if order is not None else str(row.id)),
        "kind": kind_of(row),
        "order_object_id": order.object_id if order is not None else None,
        "party_object_id": who,
        "party_name": name,
        "sign": "+" if inbound else "−",
        "amount": _amount(db, row, party),
        "currency": row.currency,
        "state": state,
        "state_label": STATES[state],
    }


def _sorted(db: Session, rows: list[Voucher], party: Optional[int]) -> list[dict[str, Any]]:
    orders = {o.id: o for o in db.query(Order).filter(
        Order.id.in_([r.order_id for r in rows] or [0])).all()}
    out = [row_of(db, r, orders.get(r.order_id), party) for r in rows]
    # **Neueste Nummer zuoberst** – Auftragsnummer, dann die laufende Nummer dahinter.
    def key(x: dict[str, Any]) -> tuple[int, int]:
        head, _, tail = str(x["number"]).partition("-")
        return (int(head) if head.isdigit() else 0, int(tail) if tail.isdigit() else 0)
    return sorted(out, key=key, reverse=True)


def of_person(db: Session, object_id: int) -> list[dict[str, Any]]:
    """Jede Zahlung, in der diese Person Partei ist – sie steht im Angebotsspiegel."""
    ids = {v for (v,) in db.query(VoucherQuote.voucher_id).filter(
        VoucherQuote.party_id == object_id, VoucherQuote.is_active.is_(True)).all()}
    rows = (db.query(Voucher).filter(Voucher.id.in_(ids or {0}),
                                     Voucher.is_active.is_(True)).all())
    return _sorted(db, rows, object_id)


def of_company(db: Session, object_id: int) -> list[dict[str, Any]]:
    """Alle Zahlungen, die im Namen dieser eigenen Gesellschaft laufen – mit der Partei je
    Zeile. Ohne Angabe am Beleg stellt ihn der Betreiber."""
    operator = sites.find_operator(db)
    q = db.query(Voucher).filter(Voucher.is_active.is_(True))
    if operator is not None and operator.object_id == object_id:
        q = q.filter((Voucher.issuer_company_id == object_id)
                     | Voucher.issuer_company_id.is_(None))
    else:
        q = q.filter(Voucher.issuer_company_id == object_id)
    rows = [r for r in q.all() if vs.quotes_of(db, r) or r.stage != vo.OFFER]
    return _sorted(db, rows, None)


def overdue_counts(db: Session) -> dict[int, int]:
    """**Überfällige Rechnungen je Person** – für die Zahl am Symbol."""
    out: dict[int, int] = {}
    rows = (db.query(Voucher).filter(Voucher.is_active.is_(True),
                                     Voucher.stage == vo.BILLED,
                                     Voucher.due_on.isnot(None)).all())
    for row in rows:
        if vs.overdue(db, row):
            who = vs.party_of(db, row)
            if who is not None:
                out[who] = out.get(who, 0) + 1
    return out
