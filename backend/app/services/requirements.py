"""►►► **Was ein Modul an Dokumenten erwartet – abgeleitet, nie gespeichert.** ◄◄◄

Eine **Anforderung** ist ein Satz mit Lücken plus die Felder, die gebraucht werden – je
Modultyp einmal (``SENTENCES``). Die Lücken füllt das Modul aus seinen eigenen Angaben
(Partei, Bestellung, Betrag). Offen ist eine Anforderung, solange ihr Pflichtfeld leer ist;
eine Tabelle «offene Anforderungen» gibt es nicht.

Heute fordern an: das Zahlungsmodul (Lieferantenrechnung bei einer Ausgabe,
Ausfuhrnachweis bei einem Export) und die Zeiterfassung (Nachweis einer Absenz). Eine
offene Anforderung zählt ins «zu tun» des Datensatzes, an dem sie steht.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..domain import voucher as vo
from ..models import Order, UserProfile, Voucher
from . import access, documents, people, records, timekeeping


@dataclass(frozen=True)
class Requirement:
    """Ein Dokument, auf das ein Modul wartet."""

    key: str                      # «voucher.original:<step>» – stabil, für die Zuordnung
    label: str                    # «Lieferantenrechnung fehlt»
    sentence: str                 # der Satz der Anforderung, Lücken gefüllt
    fields: tuple[str, ...]       # was die KI ablesen soll
    object_id: int                # wo es erscheint (Auftrag, Person)
    part: Optional[str]           # welcher Teil (``step:<id>``, ``time:<id>``)
    field: str                    # welches Pflichtfeld es füllt
    party_object_id: Optional[int] = None
    expected: dict = field(default_factory=dict)   # was der Code vergleicht (Betrag …)


#: ►►► **Die Sätze – je Modultyp einmal.** ◄◄◄ ``{…}`` sind die Lücken.
SENTENCES = {
    "voucher.original": (
        "Lieferantenrechnung",
        "Die Rechnung von {party} zur Bestellung {reference} über rund {currency} {amount} – "
        "mit Rechnungsnummer, Rechnungsdatum, MWST-Nummer, Gesamtbetrag und Fälligkeit.",
        ("Rechnungsnummer", "Rechnungsdatum", "MWST-Nummer", "Gesamtbetrag", "Fälligkeit")),
    "voucher.export": (
        "Ausfuhrnachweis",
        "Die Veranlagungsverfügung Ausfuhr des Zolls zur Rechnung {number} an {party} – mit der "
        "Nummer der Veranlagungsverfügung und dem Datum.",
        ("Nummer der Veranlagungsverfügung", "Datum")),
    "time.proof": (
        "Nachweis",
        "{proof} von {party} für die Absenz «{art}» ab {day}.",
        ("Datum", "Gültig von", "Gültig bis")),
}


#: ►►► **Unter welchem Namen ein abgelesener Wert ins Modul geht** – die Felder der Maske
#: (``bill``: ``reference`` · ``billed_on`` · ``party_uid`` · ``amount``; ``export``:
#: ``reference``). Abgelesen wird nach der Beschriftung, vorbelegt nach dem Schlüssel.
FIELD_KEYS = {
    "Rechnungsnummer": "reference", "Rechnungsdatum": "billed_on", "MWST-Nummer": "party_uid",
    "Gesamtbetrag": "amount", "Fälligkeit": "due_on",
    "Nummer der Veranlagungsverfügung": "reference", "Datum": "date",
    "Gültig von": "from", "Gültig bis": "to",
}


def _money(value: Optional[Decimal]) -> str:
    if value is None:
        return "–"
    whole, _, cents = f"{value:.2f}".partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return "’".join([whole, *groups]) + "." + cents


def of_vouchers(db: Session) -> list[Requirement]:
    """Was die Zahlungsmodule erwarten – Lieferantenrechnung, Ausfuhrnachweis."""
    from . import voucher as vs
    out: list[Requirement] = []
    rows = (db.query(Voucher).filter(Voucher.is_active.is_(True),
                                     Voucher.stage.in_((vo.AGREED, vo.BILLED))).all())
    orders = {o.id: o for o in db.query(Order).filter(
        Order.id.in_({r.order_id for r in rows})).all()} if rows else {}
    for row in rows:
        order = orders.get(row.order_id)
        if order is None:
            continue
        part = f"step:{row.step_id}"
        party = vs.party_of(db, row)
        name = records.labels(db, [party]).get(party) if party else None
        party_name = name.name if name else "der Partei"
        if (not vo.of(row.direction).collects and row.stage == vo.AGREED
                and documents.field_document(db, order.object_id, "voucher.original", part) is None):
            quote = vs.chosen_quote(db, row)
            amount = vs.agreed_amount(db, row)
            art, text, fields = SENTENCES["voucher.original"]
            out.append(Requirement(
                key=f"voucher.original:{row.step_id}", label=f"{art} fehlt",
                sentence=text.format(party=party_name, reference=(quote.reference if quote and
                                     quote.reference else "–"), currency=row.currency,
                                     amount=_money(amount)),
                fields=fields, object_id=order.object_id, part=part, field="voucher.original",
                party_object_id=party, expected={"amount": str(amount) if amount else None}))
        if (row.stage == vo.BILLED and not row.export_number and vs.is_export(db, row)
                and documents.field_document(db, order.object_id, "voucher.export", part) is None):
            art, text, fields = SENTENCES["voucher.export"]
            out.append(Requirement(
                key=f"voucher.export:{row.step_id}", label=f"{art} fehlt",
                sentence=text.format(number=row.number or "–", party=party_name),
                fields=fields, object_id=order.object_id, part=part, field="voucher.export",
                party_object_id=party))
    return out


def _proofs(db: Session, viewer: UserProfile) -> list[Requirement]:
    from ..domain import timekeeping as tk
    out: list[Requirement] = []
    persons = db.query(UserProfile).filter(UserProfile.role.in_(people.STAFF_ROLES)).all()
    today = timekeeping.local(timekeeping.now_utc()).date()
    for person in persons:
        if not timekeeping.may_see(viewer, person):
            continue
        book = timekeeping.load(db, person)
        for a in timekeeping.absences(book):
            due = timekeeping.proof_due(book, a)
            if due is None or a.proof_url or due > today:
                continue
            kind = tk.ART_BY_KEY[a.art]
            art, text, fields = SENTENCES["time.proof"]
            out.append(Requirement(
                key=f"time.proof:{a.id}", label=f"{kind.proof} fehlt",
                sentence=text.format(proof=kind.proof, party=person.display_name or "",
                                     art=kind.label, day=tk.dmy(a.day)),
                fields=fields, object_id=person.object_id, part=f"time:{a.id}",
                field="time.proof", party_object_id=person.object_id))
    return out


def open_for(db: Session, viewer: UserProfile) -> list[Requirement]:
    """►►► **Alle offenen Anforderungen, die ``viewer`` sehen darf.** ◄◄◄ Die Zeiterfassung
    nur der Person selbst und dem Admin – dieselbe Regel wie überall (``access``)."""
    if not access.is_staff(viewer):
        return []
    return of_vouchers(db) + _proofs(db, viewer)


def by_key(db: Session, viewer: UserProfile, key: str) -> Optional[Requirement]:
    return next((r for r in open_for(db, viewer) if r.key == key), None)
