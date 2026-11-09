"""►►► **Die Handlungen ab der Zusage: Rechnung, Geld, Papiere.** ◄◄◄

Rechnen (``_bill``), Lieferantenrechnung annehmen (``_accept``), Korrektur
(``correction_problem`` ↔ ``_assert_correction``), Geld-Zeilen (Zahlung, Ausbuchung, Trinkgeld,
«falsch erfasst?» – ``reversible``), Mahnung, Ausfuhrnachweis, Papiere freigeben, Stornieren.
Eingetragen in ``voucher_actions.VERBS``; ob ein Verb geht, entscheidet dort ``can``.
"""

from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.orm import Session
from ..core import clock
from ..domain import voucher as vo
from ..models import (
    Order, ProcessStep,
    UserProfile, Voucher, VoucherEntry,
)
from .voucher import (
    agreed_amount, balance_of, days_after, documents_of, due_days_of, entries_of, inbound,
    is_billed, lines_of, minus, next_reminder, party_of, priced_dicts, service_day,
)
from .voucher_money import (
    book, papers_due,
)
from ..domain.errors import Conflict, Invalid
from .voucher_input import _day, _iban, _int, _our_number, _text, amount_of


def reversible(db: Session, row: Voucher) -> list[VoucherEntry]:
    """►►► **Welche Geld-Zeilen sich als «falsch erfasst» gegenbuchen lassen.** ◄◄◄ Von Hand
    erfasste (eine Karten-Zeile meldet der Dienst – sie geht über «zurück auf die Karte»),
    die nicht selbst eine Gegenbuchung sind und noch nicht gegengebucht wurden."""
    rows = entries_of(db, row)
    undone = {e.reverses_id for e in rows if e.reverses_id is not None}
    return [e for e in rows if e.reverses_id is None and e.id not in undone
            and e.method != vo.CARD]


def _revoke(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
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
    row.cancel_note = _text(data.get("note"), 200)
    billed = is_billed(row)
    if billed and flow.collects and not row.credit_number:
        row.credit_number = _our_number(db, row)
    told = _told(db, row) if flow.collects else []
    row.stage = vo.CANCELLED
    row.cancelled_on = clock.today()
    db.flush()
    for party in told:
        voucher_docs.issue(db, row=row, kind=vo.CREDIT_DOC if billed else vo.STORNO_DOC,
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


def _bill(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
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
    if flow.quoted_by == vo.BY_US:
        priced = [ln for ln in priced_dicts(db, row)
                  if vo.line_net(ln, row.currency) != 0]
        if not priced:
            raise Invalid(f"Ohne Preis gibt es nichts zu berechnen – bei einer "
                        f"{flow.label} nennen wir ihn.")
        gross = vo.gross_of(priced, row.currency)
        split = vo.vat_split(priced, row.currency)
    else:
        given = amount_of(data.get("amount"), row.currency)
        gross = given if given is not None else agreed_amount(db, row)
        if gross is None:
            raise Invalid("Ohne Betrag ist es keine Rechnung.")
        try:
            split = vo.split_at(gross, data.get("vat") or vo.DEFAULT_VAT, row.currency)
        except ValueError as e:
            raise Invalid(str(e))
        _record_original(db, row, data, split)
    if gross == 0:
        raise Invalid("Eine Rechnung über null ist keine.")
    if flow.reference is not None and not row.number:
        number = _text(data.get("reference"), 120)
        if not number:
            raise Invalid(f"Ohne {flow.reference} lässt sich diese Rechnung nicht "
                        f"zuordnen – sie steht auf seinem Papier.")
        row.number = number
    elif not row.number:
        row.number = _our_number(db, row)
    booked = _day(data.get("billed_on")) or clock.today()
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


def _record_original(db: Session, row: Voucher, data: dict[str, Any],
                     split: list[dict[str, str]]) -> None:
    """►►► **Die Lieferantenrechnung, wie sie auf dem Papier steht.** ◄◄◄ Das Dokument ist
    Pflicht (Feld ``voucher.original``); die MWST-Nummer, sobald Steuer darauf steht (ohne
    sie kein Vorsteuerabzug)."""
    _module_document(db, row, data, "voucher.original", (
        "Ohne die Rechnung als Dokument geht es nicht – sie ist der Beleg, aufbewahrt zehn "
        "Jahre."))
    taxed = any(Decimal(r.get("tax") or "0") != 0 for r in split)
    uid = _text(data.get("party_uid"), 40)
    if taxed and not uid:
        raise Invalid("Ohne MWST-Nummer des Lieferanten gibt es keinen Vorsteuerabzug "
            "(MWSTG Art. 28) – sie steht auf seiner Rechnung.")
    row.party_uid = uid


def _accept(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferantenrechnung so annehmen, wie sie ist** – mit Grund. Die Differenz
    bleibt als Zeile stehen; jetzt wird bezahlt."""
    note = _text(data.get("note"), 200)
    if not note:
        raise Invalid("Eine Abweichung nimmt man mit Grund an – er bleibt als Nachweis stehen.")
    row.deviation_note = note


def correction_problem(db: Session, row: Voucher,
                       target: Optional[Voucher]) -> Optional[str]:
    """►►► **Kann ``row`` diesen Beleg mindern?** – der Satz, oder ``None``. ◄◄◄

    Gemindert wird eine gestellte **Rechnung** in derselben Richtung – nie der Beleg selbst
    und nie eine Gutschrift (damit kann keine Kette und kein Kreis entstehen). Zwei Formen
    einer Regel: ``_assert_correction`` ist das Tor, ``correctable`` filtert mit ihr.
    """
    if target is None:
        return "Diesen Beleg gibt es nicht."
    if target.id == row.id:
        return "Ein Beleg korrigiert nicht sich selbst."
    if minus(target):
        return (f"«{target.number or target.id}» ist selbst eine Gutschrift – gemindert wird "
                f"die Rechnung, nicht ihre Korrektur.")
    if not is_billed(target):
        return "Dieser Beleg trägt noch keine Rechnung – es gibt nichts zu korrigieren."
    if target.direction != row.direction:
        return (f"Eine {vo.of(row.direction).label} korrigiert keine "
                f"{vo.of(target.direction).label}: das Geld flösse in die andere Richtung.")
    return None


def _assert_correction(db: Session, row: Voucher, target: Optional[Voucher]) -> None:
    """Das Tor zu ``correction_problem`` – derselbe Satz, nur geworfen."""
    problem = correction_problem(db, row, target)
    if problem:
        raise Invalid(problem)


def _correct(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Welche Rechnung mindert dieser Beleg?** Der Verweis darf über Auftragsgrenzen zeigen
    – die Gutschrift gehört dorthin, wo die Ware zurückkommt (``correction_problem``)."""
    value = _int(data.get("corrects"))
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
        booked_on=_day(data.get("booked_on")) or clock.today(),
        reference=_text(data.get("reference"), 120),
        note=_text(data.get("note"), 200), method=method, reason=reason,
        reverses_id=reverses, iban=_iban(data.get("iban")),
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


def _pay(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
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
    if minus(row) and method == vo.TRANSFER and not _iban(data.get("iban")):
        raise Invalid("Zuerst die IBAN eintragen – wohin die Erstattung geht.")
    _entry(db, row, amount=value, data=data, method=method)


def _refund(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Erstatten** – das Geld geht dorthin zurück, woher es kam (bar, an die IBAN).
    Vorbelegt mit dem, was zu viel ist. Auf die Karte geht es über den Zahlungsdienst."""
    owed = -balance_of(db, row).open
    given = amount_of(data.get("amount"), row.currency)
    value = given if given is not None else owed
    if value is None or value <= 0:
        raise Invalid("Hier ist nichts zu erstatten.")
    method = _method(row, data.get("method"))
    if method == vo.TRANSFER and not _iban(data.get("iban")):
        raise Invalid("Eine Überweisung braucht die IBAN – sie kommt über den gewöhnlichen Verlauf "
            "und wird hier eingetragen.")
    _entry(db, row, amount=-value, data=data, method=method)


def _writeoff(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Ausbuchen** – der Rest als eigene Zeile mit Grund; kein Geld fliesst. Rechtlich eine
    Entgeltsminderung (MWSTG Art. 41) – ihre Steuer rechnet erst die Buchhaltung."""
    try:
        reason = vo.assert_reason(data.get("reason"))
    except ValueError as e:
        raise Invalid(str(e))
    _entry(db, row, amount=balance_of(db, row).open, kind=vo.WRITEOFF, data=data,
           reason=reason)


def _tip(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Als Trinkgeld behalten** – was zu viel kam, bleibt als eigene Zeile stehen. Es ist
    Entgelt (MWSTG Art. 24) – seine Steuer rechnet erst die Buchhaltung."""
    _entry(db, row, amount=-balance_of(db, row).open, kind=vo.TIP, data=data)


def _reverse(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**«Falsch erfasst?»** – die Gegenbuchung genau dieser Zeile, für einen Tippfehler.
    Gelöscht wird nichts; beide Zeilen bleiben stehen."""
    wanted = _int(data.get("entry"))
    found = next((e for e in reversible(db, row) if e.id == wanted), None)
    if found is None:
        raise Conflict("Diese Zeile lässt sich nicht gegenbuchen – sie ist schon gegengebucht, ist "
            "selbst eine Gegenbuchung oder kam vom Zahlungsdienst.")
    _entry(db, row, amount=-found.amount, kind=found.kind, method=found.method,
           reason=found.reason, reverses=found.id,
           data={"note": vo.REVERSE_WORD.rstrip("?")})


def _remind(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Mahnen** – die nächste Stufe, als Dokument mit Mail. Nichts geht von selbst;
    ``can`` lässt es erst zu, wenn die Stufe fällig ist (zehn Tage Abstand). ◄◄◄"""
    from . import voucher_docs
    step_no, _when = next_reminder(db, row) or (None, None)
    if step_no is None:
        raise Conflict("Hier ist keine Mahnung fällig.")
    voucher_docs.issue(db, row=row, kind=vo.REMINDER_DOC, actor=actor, level=step_no)


def _export(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Den Ausfuhrnachweis erfassen** – Nummer der Veranlagungsverfügung und das Dokument
    (PDF oder Bild, hochgeladen). Ohne ihn gilt der Nullsatz nicht; erledigt ist der Beleg
    erst damit."""
    message = ("Der Ausfuhrnachweis braucht die Nummer der Veranlagungsverfügung und das "
               "Dokument dazu.")
    number = _text(data.get("reference"), 60)
    if not number:
        raise Invalid(message)
    _module_document(db, row, data, "voucher.export", message)
    row.export_number = number


def _release(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Ein anstehendes Papier freigeben** – es entsteht und geht hinaus (``voucher_docs``)."""
    from . import voucher_docs
    kind = _text(data.get("kind"), 16)
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
    chosen = _int(data.get("original"))
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
