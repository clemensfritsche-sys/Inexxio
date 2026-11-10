"""►►► **Die Handlungen ab der Zusage: Rechnung, Geld, Papiere.** ◄◄◄

Rechnen (``bill``), Lieferantenrechnung annehmen (``accept``), Korrektur
(``correction_problem`` ↔ ``_assert_correction``), Geld-Zeilen (Zahlung, Ausbuchung, Trinkgeld,
«falsch erfasst?» – ``reversible``), Mahnung, Ausfuhrnachweis, Papiere freigeben, Stornieren.
Eingetragen in ``voucher_actions.VERBS``; ob ein Verb geht, entscheidet dort ``can``.
"""

from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session
from ..core import clock
from ..domain import currency as cur
from ..domain import voucher as vo
from ..models import (
    Order, ProcessStep,
    UserProfile, Voucher, VoucherEntry,
)
from .voucher import (
    agreed_amount, balance_of, corrects, credit_room, days_after, documents_of, due_days_of,
    entries_of, inbound, is_billed, lines_of, minus, next_reminder, party_of, priced_dicts,
    service_day,
)
from .voucher_money import (
    book, papers_due,
)
from ..domain.errors import Conflict, Invalid
from .voucher_input import day_of, iban_of, int_of, our_number, text_of, amount_of


def reversible(db: Session, row: Voucher) -> list[VoucherEntry]:
    """►►► **Welche Geld-Zeilen sich als «falsch erfasst» gegenbuchen lassen.** ◄◄◄ Von Hand
    erfasste (eine Karten-Zeile meldet der Dienst – sie geht über «zurück auf die Karte»),
    die nicht selbst eine Gegenbuchung sind und noch nicht gegengebucht wurden."""
    rows = entries_of(db, row)
    undone = {e.reverses_id for e in rows if e.reverses_id is not None}
    return [e for e in rows if e.reverses_id is None and e.id not in undone
            and e.method != vo.CARD]


def revoke(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Stornieren** – ein Wort in jeder Stufe; was es bewirkt, folgt aus ihr. ◄◄◄

    * vor der Zusage: das Angebot gilt nicht mehr;
    * nach der Zusage: der Auftrag gilt nicht mehr – es ist nichts geschuldet;
    * **nach der Rechnung: die Gutschrift über die ganze Rechnung entsteht von selbst**
      (eigene Nummer, Bezug auf die Rechnung). Was schon bezahlt ist, geht zurück
      («Erstatten» bleibt möglich).

    Hat die Partei schon etwas gesehen, bekommt sie Bescheid – eine allgemeine Mail, ohne
    den Grund (der bleibt intern, ``cancel_note``). Die Stücke führt ein ganz gewöhnlicher
    Abweichungsauftrag weiter.
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    row.cancel_note = text_of(data.get("note"), 200)
    # **Eine Gutschrift entsteht nur aus einer Rechnung, die wir stellen** – über das, was
    # Gutschriften nicht schon gemindert haben. Wer eine Gutschrift storniert, bekommt eine
    # Stornierung, keine Gutschrift auf die Gutschrift (und keine neue Nummer).
    credit = (is_billed(row) and flow.collects and not minus(row)
              and credit_room(db, row) > vo.SETTLED_TOLERANCE)
    if credit and not row.credit_number:
        row.credit_number = our_number(db, row)
    told = _told(db, row) if flow.collects else []
    row.stage = vo.CANCELLED
    row.cancelled_on = clock.today()
    db.flush()
    for party in told:
        voucher_docs.issue(db, row=row, kind=vo.CREDIT_DOC if credit else vo.STORNO_DOC,
                           actor=actor, party_id=party)


def _told(db: Session, row: Voucher) -> list[int]:
    """**Wer vom Storno erfährt** – die gebundene Partei, sonst jede, die ein Papier bekam."""
    bound = party_of(db, row)
    if bound is not None:
        return [bound]
    out: list[int] = []
    for d in documents_of(db, row):
        if d.party_id is not None and d.party_id not in out:
            out.append(d.party_id)
    return out


def bill(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
          data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Die Rechnung stellen bzw. erfassen — und damit IST der Beleg eine.** ◄◄◄

    **Wo WIR den Preis nennen**, ist die Summe der Positionen die Rechnung (Teilbeträge
    eingeschlossen; eine Position mit null steht nicht darauf). Die Nummer vergeben wir.

    **Wo die Gegenpartei ihn nennt**, schreiben wir ihre Rechnung ab – so, wie sie auf
    dem Papier steht: Betrag, Satz, **Rechnungsnummer**, **Rechnungsdatum** und **ihre
    MWST-Nummer** (ohne sie kein Vorsteuerabzug, MWSTG Art. 28). Das **Foto** der Rechnung
    ist Pflicht – es ist der Beleg. Weicht der Betrag von der Zusage ab, steht die
    Differenz als Zeile, und bezahlt wird erst nach dem Entscheid (``accept``).
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    gross, split = _our_sum(db, row, flow) if flow.collects else _their_sum(db, row, data)
    if gross == 0:
        raise Invalid("Eine Rechnung über null ist keine.")
    if minus(row):
        # **Nie mehr gutschreiben, als die Rechnung trägt** – geprüft mit dem Betrag, der jetzt
        # feststeht (die Rechnung kann inzwischen storniert oder gemindert sein).
        _assert_correction(db, row, corrects(db, row), amount=gross)
    # **Unsere Rechnung trägt unsere Nummer und den Tag, an dem sie gestellt wird** – nie ein
    # anderes Datum (sonst fiele sie in eine schon abgerechnete MWST-Periode). Eine
    # Lieferantenrechnung trägt Nummer und Datum ihres Papiers.
    if flow.collects:
        row.number = row.number or our_number(db, row)
        booked = clock.today()
    else:
        row.number = row.number or _their_number(data, flow)
        booked = day_of(data.get("billed_on")) or clock.today()
    row.billed_on = booked
    row.due_on = days_after(booked, due_days_of(db, row))
    row.amount = gross
    row.vat = split
    # **Das Leistungsdatum kommt aus dem PROZESS** – der Tag, an dem die Stücke dieses
    # Modul erreicht haben (MWSTG Art. 26 Bst. c).
    row.service_date = service_day(db, step) or booked
    row.stage = vo.BILLED
    db.flush()
    if flow.collects:
        voucher_docs.issue(db, row=row,
                           kind=vo.CREDIT_DOC if minus(row) else vo.INVOICE_DOC, actor=actor)


def _our_sum(db: Session, row: Voucher, flow: vo.Direction) -> tuple[Decimal, list]:
    """**Unsere Rechnung** – die Summe der Positionen (Teilbeträge eingeschlossen; eine
    Position mit null steht nicht darauf) und ihre Steuer je Satz."""
    priced = [ln for ln in priced_dicts(db, row) if vo.line_net(ln, row.currency) != 0]
    if not priced:
        raise Invalid(f"Ohne Preis gibt es nichts zu berechnen – bei einer "
                      f"{flow.label} nennen wir ihn.")
    return vo.gross_of(priced, row.currency), vo.vat_split(priced, row.currency)


def _their_sum(db: Session, row: Voucher, data: dict[str, Any]) -> tuple[Decimal, list]:
    """**Seine Rechnung, abgeschrieben** – Betrag (sonst die Zusage) und Satz, dazu das
    Dokument und seine MWST-Nummer (``_record_original``)."""
    given = amount_of(data.get("amount"), row.currency)
    gross = given if given is not None else agreed_amount(db, row)
    if gross is None:
        raise Invalid("Ohne Betrag ist es keine Rechnung.")
    try:
        split = vo.split_at(gross, data.get("vat") or vo.DEFAULT_VAT, row.currency)
    except ValueError as e:
        raise Invalid(str(e))
    _record_original(db, row, data, split)
    return gross, split


def _their_number(data: dict[str, Any], flow: vo.Direction) -> str:
    """**Seine Rechnungsnummer** – Pflicht, sie steht auf seinem Papier."""
    number = text_of(data.get("reference"), 120)
    if not number:
        raise Invalid(f"Ohne {flow.reference} lässt sich diese Rechnung nicht "
                      f"zuordnen – sie steht auf seinem Papier.")
    return number


def _record_original(db: Session, row: Voucher, data: dict[str, Any],
                     split: list[dict[str, str]]) -> None:
    """►►► **Die Lieferantenrechnung, wie sie auf dem Papier steht.** ◄◄◄ Das Dokument ist
    Pflicht (Feld ``voucher.original``); die MWST-Nummer, sobald Steuer darauf steht (ohne
    sie kein Vorsteuerabzug)."""
    _module_document(db, row, data, "voucher.original", (
        "Ohne die Rechnung als Dokument geht es nicht – sie ist der Beleg, aufbewahrt zehn "
        "Jahre."))
    taxed = any(Decimal(r.get("tax") or "0") != 0 for r in split)
    uid = text_of(data.get("party_uid"), 40)
    if taxed and not uid:
        raise Invalid("Ohne MWST-Nummer des Lieferanten gibt es keinen Vorsteuerabzug "
            "(MWSTG Art. 28) – sie steht auf seiner Rechnung.")
    row.party_uid = uid


def accept(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferantenrechnung so annehmen, wie sie ist** – mit Grund. Die Differenz
    bleibt als Zeile stehen; jetzt wird bezahlt."""
    note = text_of(data.get("note"), 200)
    if not note:
        raise Invalid("Eine Abweichung nimmt man mit Grund an – er bleibt als Nachweis stehen.")
    row.deviation_note = note


def correction_problem(db: Session, row: Voucher, target: Optional[Voucher], *,
                       amount: Optional[Decimal] = None) -> Optional[str]:
    """►►► **Kann ``row`` diesen Beleg mindern?** – der Satz, oder ``None``. ◄◄◄

    Gemindert wird eine gestellte, nicht stornierte **Rechnung** in derselben Richtung – nie der
    Beleg selbst und nie eine Gutschrift (damit kann keine Kette und kein Kreis entstehen).
    **Gutschriften und Storno zusammen nie mehr als die Rechnung** (``credit_room``): mit
    ``amount`` (beim Stellen) darf die Gutschrift den Rest nicht übersteigen. Zwei Formen einer
    Regel: ``_assert_correction`` ist das Tor, ``correctable`` filtert mit ihr.
    """
    if target is None:
        return "Diesen Beleg gibt es nicht."
    if target.id == row.id:
        return "Ein Beleg korrigiert nicht sich selbst."
    name = target.number or target.id
    if minus(target):
        return (f"«{name}» ist selbst eine Gutschrift – gemindert wird "
                f"die Rechnung, nicht ihre Korrektur.")
    if not is_billed(target):
        return "Dieser Beleg trägt noch keine Rechnung – es gibt nichts zu korrigieren."
    if target.direction != row.direction:
        return (f"Eine {vo.of(row.direction).label} korrigiert keine "
                f"{vo.of(target.direction).label}: das Geld flösse in die andere Richtung.")
    if target.stage == vo.CANCELLED:
        return (f"«{name}» ist storniert – die Gutschrift über die Rechnung ist mit dem "
                f"Storno schon entstanden.")
    room = credit_room(db, target, without=row)
    if room <= vo.SETTLED_TOLERANCE:
        return (f"«{name}» ist schon ganz gutgeschrieben – mehr als die Rechnung lässt "
                f"sich nicht mindern.")
    if amount is not None and amount > room + vo.SETTLED_TOLERANCE:
        return (f"Die Gutschrift über {cur.money(amount, row.currency)} übersteigt, was von "
                f"«{name}» noch gutgeschrieben werden kann: "
                f"{cur.money(room, target.currency)} {target.currency}.")
    return None


def credit_problem(db: Session, row: Voucher) -> Optional[str]:
    """**Darf diese Gutschrift jetzt gestellt werden?** – ``correction_problem`` mit dem
    zugesagten Betrag; ``None`` an jedem Beleg, der nicht mindert. ``can`` nimmt damit
    «Gutschrift stellen» weg, ``bill`` prüft mit dem Betrag der Rechnung."""
    if not minus(row):
        return None
    return correction_problem(db, row, corrects(db, row), amount=agreed_amount(db, row))


def _assert_correction(db: Session, row: Voucher, target: Optional[Voucher], *,
                       amount: Optional[Decimal] = None) -> None:
    """Das Tor zu ``correction_problem`` – derselbe Satz, nur geworfen."""
    problem = correction_problem(db, row, target, amount=amount)
    if problem:
        raise Invalid(problem)


def correct(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Welche Rechnung mindert dieser Beleg?** Der Verweis darf über Auftragsgrenzen zeigen
    – die Gutschrift gehört dorthin, wo die Ware zurückkommt (``correction_problem``)."""
    value = int_of(data.get("corrects"))
    if value is None:
        row.corrects_id = None
        return
    target = db.query(Voucher).filter(Voucher.id == value).first()
    _assert_correction(db, row, target)
    row.corrects_id = target.id
    # **Vorbelegt ist der Rechnungsbetrag** – je Position der Preis der korrigierten
    # Rechnung, wo dieselbe Ware wieder dasteht. Ein Limit gibt es nicht.
    prices = {ln.article_id: ln for ln in lines_of(db, target)}
    for ln in lines_of(db, row):
        src = prices.get(ln.article_id)
        if src is not None and ln.price is None:
            ln.price, ln.vat = src.price, src.vat


def _entry(db: Session, row: Voucher, *, amount: Decimal, kind: str = vo.PAYMENT,
           data: Optional[dict[str, Any]] = None, method: Optional[str] = None,
           reason: Optional[str] = None, reverses: Optional[int] = None) -> VoucherEntry:
    """**Eine Geld-Zeile von Hand** – geschrieben über ``book``."""
    data = data or {}
    entry = VoucherEntry(
        voucher_id=row.id, amount=amount, kind=kind,
        booked_on=day_of(data.get("booked_on")) or clock.today(),
        reference=text_of(data.get("reference"), 120),
        note=text_of(data.get("note"), 200), method=method, reason=reason,
        reverses_id=reverses, iban=iban_of(data.get("iban")),
    )
    book(db, row, entry)
    return entry


def _method(row: Voucher, value: Any) -> Optional[str]:
    """**Wie bezahlt wurde** – von Hand bar oder per Überweisung; **mit Karte nur, wo WIR
    zahlen** (die Firmenkarte). Eine Karte, die uns bezahlt, meldet der Zahlungsdienst."""
    try:
        return vo.assert_method(value, card=not inbound(row))
    except ValueError as e:
        raise Invalid(str(e))


def pay(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Zahlung erfassen** – vorbelegt mit dem Offenen. Positiv: wer überzahlt, tut
    das mit einem grösseren Betrag; zurück geht es mit «Erstatten»."""
    given = amount_of(data.get("amount"), row.currency)
    value = given if given is not None else balance_of(db, row).next_payment
    if value is None or value <= 0:
        raise Invalid("Ohne Betrag keine Zahlung.")
    method = _method(row, data.get("method"))
    # **Eine Erstattung per Überweisung braucht das Konto, wohin** – es kommt über den
    # gewöhnlichen Verlauf und wird hier eingetragen (keine Anfrage, kein Formular).
    if minus(row) and method == vo.TRANSFER and not iban_of(data.get("iban")):
        raise Invalid("Zuerst die IBAN eintragen – wohin die Erstattung geht.")
    _entry(db, row, amount=value, data=data, method=method)


def refund(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Erstatten** – das Geld geht dorthin zurück, woher es kam (bar, an die IBAN).
    Vorbelegt mit dem, was zu viel ist. Auf die Karte geht es über den Zahlungsdienst."""
    owed = -balance_of(db, row).open
    given = amount_of(data.get("amount"), row.currency)
    value = given if given is not None else owed
    if value is None or value <= 0:
        raise Invalid("Hier ist nichts zu erstatten.")
    method = _method(row, data.get("method"))
    if method == vo.TRANSFER and not iban_of(data.get("iban")):
        raise Invalid("Eine Überweisung braucht die IBAN – sie kommt über den gewöhnlichen Verlauf "
            "und wird hier eingetragen.")
    _entry(db, row, amount=-value, data=data, method=method)


def writeoff(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Ausbuchen** – der Rest als eigene Zeile mit Grund; kein Geld fliesst. Rechtlich eine
    Entgeltsminderung (MWSTG Art. 41) – ihre Steuer rechnet erst die Buchhaltung."""
    try:
        reason = vo.assert_reason(data.get("reason"))
    except ValueError as e:
        raise Invalid(str(e))
    _entry(db, row, amount=balance_of(db, row).open, kind=vo.WRITEOFF, data=data,
           reason=reason)


def tip(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Als Trinkgeld behalten** – was zu viel kam, bleibt als eigene Zeile stehen. Es ist
    Entgelt (MWSTG Art. 24) – seine Steuer rechnet erst die Buchhaltung."""
    _entry(db, row, amount=-balance_of(db, row).open, kind=vo.TIP, data=data)


def reverse(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**«Falsch erfasst?»** – die Gegenbuchung genau dieser Zeile, für einen Tippfehler.
    Gelöscht wird nichts; beide Zeilen bleiben stehen."""
    wanted = int_of(data.get("entry"))
    found = next((e for e in reversible(db, row) if e.id == wanted), None)
    if found is None:
        raise Conflict("Diese Zeile lässt sich nicht gegenbuchen – sie ist schon gegengebucht, ist "
            "selbst eine Gegenbuchung oder kam vom Zahlungsdienst.")
    _entry(db, row, amount=-found.amount, kind=found.kind, method=found.method,
           reason=found.reason, reverses=found.id,
           data={"note": vo.REVERSE_WORD.rstrip("?")})


def remind(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Mahnen** – die nächste Stufe, als Dokument mit Mail. Nichts geht von selbst;
    ``can`` lässt es erst zu, wenn die Stufe fällig ist (zehn Tage Abstand). ◄◄◄"""
    from . import voucher_docs
    step_no, _when = next_reminder(db, row) or (None, None)
    if step_no is None:
        raise Conflict("Hier ist keine Mahnung fällig.")
    voucher_docs.issue(db, row=row, kind=vo.REMINDER_DOC, actor=actor, level=step_no)


def export(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Den Ausfuhrnachweis erfassen** – Nummer der Veranlagungsverfügung und das Dokument
    (PDF oder Bild, hochgeladen). Ohne ihn gilt der Nullsatz nicht; erledigt ist der Beleg
    erst damit."""
    message = ("Der Ausfuhrnachweis braucht die Nummer der Veranlagungsverfügung und das "
               "Dokument dazu.")
    number = text_of(data.get("reference"), 60)
    if not number:
        raise Invalid(message)
    _module_document(db, row, data, "voucher.export", message)
    row.export_number = number


def release(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Ein anstehendes Papier freigeben** – es entsteht und geht hinaus (``voucher_docs``)."""
    from . import voucher_docs
    kind = text_of(data.get("kind"), 16)
    if kind not in papers_due(db, row):
        raise Conflict(f"«{vo.DOCUMENTS.get(kind or '', kind or '–')}» steht hier nicht an.")
    voucher_docs.issue(db, row=row, kind=kind, actor=actor)


def _module_document(db: Session, row: Voucher, data: dict[str, Any], field: str,
                     message: str) -> int:
    """►►► **Ein Dokument in einem Feld des Moduls** – gewählt (``data.original``, eine
    Dokumentnummer) oder schon im Feld. Es kommt ins Pflichtfeld (``documents.set_field``):
    änderbar, nie leer, nie löschbar, solange es dort steht. ◄◄◄"""
    from ..models import Document
    from . import documents
    chosen = int_of(data.get("original"))
    order = db.query(Order).filter(Order.id == row.order_id).first()
    part = f"step:{row.step_id}"
    if chosen is None:
        found = documents.field_document(db, order.object_id, field, part)
        chosen = found.object_id if found is not None else None
    doc = (db.query(Document).filter(Document.object_id == chosen,
                                     Document.deleted_at.is_(None)).first()
           if chosen is not None else None)
    if doc is None:
        raise Invalid(message)
    documents.set_field(db, document_object_id=doc.object_id, object_id=order.object_id,
                        part=part, field=field, actor=None)
    return doc.object_id
