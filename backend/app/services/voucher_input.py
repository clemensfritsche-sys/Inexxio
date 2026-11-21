"""►►► **Was eine Handlung am Beleg hereinbekommt – gelesen an EINER Stelle.** ◄◄◄

Zahl (``int_of``), Betrag (``amount_of``), Frist (``days_of``), Tag (``day_of``), Text
(``text_of``), Gewicht (``weight_of``), IBAN (``iban_of``), die gemeinte Angebotszeile
(``target_quote``) und die Gegenpartei (``checked_party``); dazu die Regel der Konditionen in
ihren zwei Formen (``terms_problem`` ↔ ``assert_terms``) und die eigene Rechnungsnummer
(``our_number``). Öffentlich, weil die Verben in ``voucher_offer`` und ``voucher_billing`` sie
lesen.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..domain import number
from ..domain import modules
from ..domain import voucher as vo
from ..models import (
    Order, ProcessStep,
    UserProfile, Voucher, VoucherQuote,
)
from .voucher import (
    quotes_of,
)
from ..domain.errors import Invalid, NotFound
from ..domain import policy


def weight_of(value: Any) -> Optional[Decimal]:
    """Ein Gewicht in kg – oder ``None``. Nie negativ."""
    try:
        found = number.decimal(value)
    except ValueError:
        raise Invalid(f"«{value}» ist kein Gewicht.")
    if found is None:
        return None
    if found < 0 or found > Decimal("999999"):
        raise Invalid(f"«{value}» ist kein Gewicht.")
    return found.quantize(Decimal("0.001"))


def iban_of(value: Any) -> Optional[str]:
    """Eine IBAN in Normalform (ohne Leerzeichen, gross) – oder ``None``."""
    text = "".join(str(value or "").split()).upper()
    if not text:
        return None
    if not (15 <= len(text) <= 34 and text[:2].isalpha() and text[2:4].isdigit()):
        raise Invalid(f"«{value}» ist keine IBAN.")
    return text


def target_quote(db: Session, row: Voucher, data: dict[str, Any],
            actor: Optional[UserProfile]) -> VoucherQuote:
    """**Welche Angebotszeile ist gemeint?**

    Eine **Gegenpartei** trifft ausschliesslich ihre eigene – gelesen aus dem angemeldeten
    Benutzer, nie aus der Nutzlast: sonst entschiede die Nutzlast, wessen Preis geändert
    wird. Personal nennt die Partei.
    """
    internal = policy.inside(actor)
    number = int_of(data.get("party")) if internal else (
        actor.object_id if actor else None)
    rows = quotes_of(db, row)
    if number is None and internal and len(rows) == 1:
        # Steht genau eine Zeile da, ist sie gemeint.
        return rows[0]
    found = next((q for q in rows if q.party_id == number), None)
    if found is None:
        raise NotFound(f"{vo.PARTY} {number} ist an diesem Beleg nicht angefragt.")
    return found


def checked_party(db: Session, *, step: ProcessStep, value: Any,
           flow: vo.Direction) -> Optional[int]:
    """Die gewählte Gegenpartei prüfen – gegen die Freigabe und gegen die Wirklichkeit.

    **Leer heisst frei, aber nicht «irgendwer»**: die Objektnummer muss es geben.
    """
    if value in (None, "", 0):
        return None
    number = int_of(value)
    if number is None:
        raise Invalid(f"«{value}» ist keine Objektnummer.")
    allowed = modules.Beleg.parties_allowed(step.config)
    if allowed and number not in allowed:
        raise Invalid(f"{vo.PARTY} {number} ist an diesem Modul nicht zugelassen. Erlaubt: "
                    + ", ".join(str(n) for n in allowed) + ".", field="party")
    assert_party(db, number)
    return number


def party_problem(db: Session, party: int) -> Optional[str]:
    """►►► **Ein Partner ist immer eine Person** – sonst der Satz, warum nicht. ◄◄◄ Eine Firma
    ist ihre Identität (Name, Rechtsform, UID); handeln tut eine Person, die zu ihr gehört –
    bei einem Shop ohne Menschen eine Person, die nach ihrer Rolle heisst. Zwei Formen einer
    Regel mit ``assert_party``."""
    from . import sites
    if db.query(UserProfile.id).filter(UserProfile.object_id == party).first():
        return None
    firm = sites.by_object_id(db, party)
    if firm is not None:
        return (f"«{sites.legal_name(firm)}» ({party}) ist eine Firma – {vo.PARTY} ist immer "
                f"eine Person (die Firma steht an ihr; ein Shop ohne Menschen bekommt eine "
                f"Person nach ihrer Rolle, z. B. «Bestellung»).")
    return f"{party} ist keine Person – {vo.PARTY} ist immer eine Person."


def assert_party(db: Session, party: int) -> None:
    why = party_problem(db, party)
    if why:
        raise Invalid(why, field="party")


def step_party_problems(db: Session, steps: list[dict[str, Any]]) -> list[str]:
    """Die zugelassenen Partner eines Zahlungsmoduls (Artikel-Vorlage, Auftrag) – je falschem
    ein Satz. Dieselbe Regel wie ``party_problem``, geprüft schon beim Modellieren."""
    out: list[str] = []
    for step in steps:
        if step.get("module_type") != modules.BELEG:
            continue
        for party in modules.Beleg.parties_allowed(step.get("config")):
            why = party_problem(db, party)
            if why:
                out.append(why)
    return out


def int_of(value: Any) -> Optional[int]:
    """Eine Zahl aus der Nutzlast – **tolerant**, denn hier wird nur nachgesehen."""
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def amount_of(value: Any, code: str, *, allow_negative: bool = False) -> Optional[Decimal]:
    """Ein Betrag aus der Nutzlast (``vo.amount``) – unlesbar ist ein 400 mit Satz."""
    try:
        return vo.amount(value, code, allow_negative=allow_negative)
    except ValueError as e:
        raise Invalid(str(e))


def days_of(key: str, value: Any) -> Optional[int]:
    """Eine Frist – die Regel steht EINMAL in ``domain/voucher.assert_days``."""
    try:
        return vo.assert_days(key, value)
    except ValueError as e:
        raise Invalid(str(e))


def terms_problem(lead: Optional[int], days: Optional[int]) -> Optional[str]:
    """►►► **Ein Angebot nennt beide Fristen.** ◄◄◄ – der Satz, oder ``None``.

    Aus der **Lieferfrist** kommt der Termin, aus der **Zahlungsfrist** die Fälligkeit (null
    = Vorauszahlung). **Null ist gültig**, darum ``is None``.

    **Zwei Formen, ein Namensstamm**: ``assert_terms`` wirft ihn an einer Angebotszeile,
    ``ask_problem`` trägt ihn an den gesperrten Knopf.
    """
    for value, label in ((lead, vo.LEAD_TERM_LABEL), (days, vo.PAYMENT_TERM_LABEL)):
        if value is None:
            return (f"Ohne {label} ist es kein Angebot – aus ihr folgt der Termin "
                    f"bzw. die Fälligkeit. «{vo.LEAD_TERMS[0][1]}» und "
                    f"«{vo.PAYMENT_TERMS[0][1]}» sind gültige Antworten (0 Tage).")
    return None


def assert_terms(lead: Optional[int], days: Optional[int]) -> None:
    """Das Tor zu ``terms_problem`` – derselbe Satz, nur geworfen."""
    problem = terms_problem(lead, days)
    if problem:
        raise Invalid(problem)


def day_of(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise Invalid(f"«{value}» ist kein Datum.")


def text_of(value: Any, limit: int) -> Optional[str]:
    found = str(value or "").strip()
    if len(found) > limit:
        raise Invalid(f"Der Text ist zu lang (max. {limit} Zeichen).")
    return found or None


def our_number(db: Session, row: Voucher) -> str:
    """►►► **Unsere nächste Nummer im Auftrag** – ``<Auftragsnummer>-<laufend>``, ab ``-1``. ◄◄◄

    Rechnungen **und** Gutschriften ziehen aus derselben Zählung (eine Gutschrift ist ein
    eigenes Dokument mit eigener Nummer, MWSTG Art. 26); stornierte zählen mit, eine Nummer
    wird nie zweimal vergeben. Gezählt wird unter der Sperre des Auftrags – zwei Module, die
    gleichzeitig stellen, bekommen zwei Nummern. Nur, was **wir** nummerieren: eine erfasste
    Lieferantenrechnung trägt die Nummer der Gegenpartei.
    """
    order = (db.query(Order).filter(Order.id == row.order_id)
             .with_for_update().one())
    used = (
        db.query(func.count(Voucher.number) + func.count(Voucher.credit_number))
        .filter(Voucher.order_id == order.id, Voucher.direction == vo.IN)
        .scalar()
    ) or 0
    return f"{order.object_id}-{used + 1}"
