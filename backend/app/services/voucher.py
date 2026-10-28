"""**Der Beleg als Dienst** — Angebotsspiegel, Positionen, Rechnung, Geld.

Drei Formregeln: **ein Verb steht an EINER Stelle** (``VERBS``: Stufe · Stammdaten · wer
darf · Funktion); **der Angebotsspiegel ist eine Tabelle** (``voucher_quotes``); **die
Position gibt es in EINER Form**, eingefroren durch die Stufe (``sync_lines``). *Mit wem*,
*was vereinbart ist* und *welche Frist gilt* sind Ableitungen aus der gewählten
Angebotszeile.

**Der Kern**: lesen, die Ableitungen, die Anlage und die Rahmen-Schnittstellen. Darüber, in
dieser Richtung und ohne Rückweg: ``voucher_head`` (Belegkopf, Anschrift, Positionen) →
``voucher_money`` (Geld-Zeilen, Erstattung, QR, anstehende Papiere) → ``voucher_actions``
(Verben, ``can``, ``apply``) → ``voucher_view`` (die Antwort an die Karte).
"""

from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Iterator, Optional

from fastapi import HTTPException
from sqlalchemy import event, func
from sqlalchemy.orm import Session

from ..core import clock
from ..domain import currency as cur
from ..domain import modules
from ..domain import voucher as vo
from ..models import (
    Instance, InstanceUnit, Order, OrderUnit, ProcessEvent, ProcessStep,
    UserProfile, Voucher, VoucherDocument, VoucherEntry, VoucherLine, VoucherQuote,
)
from ..models.process_event import KIND_START, KIND_STEP
from . import sites
# Wer ohnehin alles sieht – Personal hat keine verengte Sicht (die eine Stelle).
from .people import STAFF_ROLES


# ---------------------------------------------------------------------------
# ►► LESEN
# ---------------------------------------------------------------------------

def of_step(db: Session, step_id: int) -> Optional[Voucher]:
    """Der aktive Beleg eines Moduls – oder ``None``. **Die eine Lesestelle.**"""
    return (
        db.query(Voucher)
        .filter(Voucher.step_id == step_id, Voucher.is_active.is_(True))
        .first()
    )


def hold(db: Session, row: Voucher) -> Voucher:
    """►►► **Die eine Sperre am Beleg** – ``SELECT … FOR UPDATE``, danach frisch gelesen. ◄◄◄

    Wer handelt oder bucht, wartet hier auf den, der es gerade tut, und sieht danach dessen
    Ergebnis: zweimal «Rechnung stellen» ist eine Rechnung und ein 409. Gesperrt wird VOR
    dem Tor (``assert_allowed``), sonst prüften beide denselben alten Stand.
    """
    db.flush()
    forget(db)
    return (db.query(Voucher).filter(Voucher.id == row.id)
            .with_for_update().populate_existing().one())


#: Wo ein Lesevorgang seine Antworten hält (``Session.info``).
_READS = "voucher.reads"


@contextmanager
def reading(db: Session) -> Iterator[None]:
    """►►► **Ein Lesevorgang – was er über einen Beleg liest, liest er einmal.** ◄◄◄

    Die Antwort an die Karte (``embed_data``) und die Listen über viele Belege fragen
    dieselben Zeilen dutzendfach: Angebotsspiegel, Geld-Zeilen, Positionen, Dokumente, den
    Aussteller, die Anschrift der Partei. Innerhalb dieses Blocks liest ``once`` jede davon
    einmal und reicht sie durch. **Jedes Schreiben verwirft das Gemerkte** (``flush``,
    Rücksprung, ``forget`` nach einem direkten ``INSERT``) – ein Lesevorgang, der schreibt,
    sieht nie einen alten Stand.
    """
    outer = _READS in db.info
    if not outer:
        db.info[_READS] = {}
    try:
        yield
    finally:
        if not outer:
            db.info.pop(_READS, None)


def forget(db: Session) -> None:
    """Was der laufende Lesevorgang gemerkt hat, gilt nicht mehr (nach einem Schreiben)."""
    memo = db.info.get(_READS)
    if memo:
        memo.clear()


@event.listens_for(Session, "after_flush")
def _flushed(db: Session, _context: Any) -> None:
    forget(db)


@event.listens_for(Session, "after_soft_rollback")
def _rolled_back(db: Session, _previous: Any) -> None:
    forget(db)


def once(db: Session, key: tuple, read: Callable[[], Any]) -> Any:
    """Die eine Stelle, an der ein Lesevorgang sich eine Antwort merkt (``reading``)."""
    memo = db.info.get(_READS)
    if memo is None:
        return read()
    if key not in memo:
        memo[key] = read()
    return memo[key]


def entries_of(db: Session, row: Voucher) -> list[VoucherEntry]:
    """**Die Geld-Zeilen** (Zahlung · Ausbuchung · Trinkgeld), älteste zuerst – nur die
    gültigen. Die Forderung ist keine davon: sie ist der Beleg selbst (``billed_on`` & Co.)."""
    return list(once(db, ("entries", row.id), lambda: (
        db.query(VoucherEntry)
        .filter(VoucherEntry.voucher_id == row.id, VoucherEntry.is_active.is_(True))
        .order_by(VoucherEntry.booked_on, VoucherEntry.id)
        .all())))


def quotes_of(db: Session, row: Voucher) -> list[VoucherQuote]:
    """Der Angebotsspiegel – in der Reihenfolge, in der angefragt wurde."""
    return list(once(db, ("quotes", row.id), lambda: (
        db.query(VoucherQuote)
        .filter(VoucherQuote.voucher_id == row.id, VoucherQuote.is_active.is_(True))
        .order_by(VoucherQuote.id)
        .all())))


def documents_of(db: Session, row: Voucher, kind: Optional[str] = None
                 ) -> list[VoucherDocument]:
    """**Die Dokumente, so wie sie hinausgingen** – älteste zuerst."""
    rows = once(db, ("documents", row.id), lambda: (
        db.query(VoucherDocument)
        .filter(VoucherDocument.voucher_id == row.id, VoucherDocument.is_active.is_(True))
        .order_by(VoucherDocument.id)
        .all()))
    return [d for d in rows if kind is None or d.kind == kind]


def lines_of(db: Session, row: Voucher) -> list[VoucherLine]:
    """Die Positionen – in ihrer Reihenfolge auf dem Papier."""
    return list(once(db, ("lines", row.id), lambda: (
        db.query(VoucherLine)
        .filter(VoucherLine.voucher_id == row.id, VoucherLine.is_active.is_(True))
        .order_by(VoucherLine.position, VoucherLine.id)
        .all())))


# ---------------------------------------------------------------------------
# ►►► DIE DREI ABLEITUNGEN — keine Spalten ◄◄◄
# ---------------------------------------------------------------------------
#
# *mit wem* · *was vereinbart ist* · *welche Zahlungsfrist* stehen an der gewählten
# Angebotszeile. Als Spalten daneben könnte derselbe Beleg zwei Dinge sagen; **als
# Ableitung kann der Widerspruch gar nicht entstehen.**

def chosen_quote(db: Session, row: Voucher) -> Optional[VoucherQuote]:
    """**Die Angebotszeile, bei der zugesagt wurde** – oder ``None``.

    Sie ist die Antwort auf *mit wem · zu welchem Betrag · zu welchen Fristen*. Der
    Zustand ``gewaehlt`` entsteht nicht durch Tippen, sondern dadurch, dass ``_agree``
    hier zugesagt hat – ein Zustand ist eine Folge.
    """
    return next((q for q in quotes_of(db, row) if q.state == vo.CHOSEN), None)


def party_of(db: Session, row: Voucher) -> Optional[int]:
    """**Mit wem** – die Objektnummer der gewählten Gegenpartei."""
    q = chosen_quote(db, row)
    return q.party_id if q is not None else None


def addressee_of(db: Session, row: Voucher) -> Optional[int]:
    """**An wen geht dieser Beleg – jetzt, nicht erst mit der Zusage.**

    Die gebundene Partei, sonst der eine Angefragte, sonst der eine Gewählte, sonst der eine
    Zugelassene – **genau einer, sonst keiner** (an mehrere ist es ein Rundschreiben ohne
    einen Adressaten). Ob jemand gebunden ist, fragt ``party_of``.
    """
    chosen = party_of(db, row)
    if chosen is not None:
        return chosen
    rows = quotes_of(db, row)
    if rows:
        return rows[0].party_id if len(rows) == 1 else None
    picked = parties_on(row)
    if picked:
        return picked[0] if len(picked) == 1 else None
    # **Nennt die Definition genau einen, ist er es** – auch bevor etwas hinausging: die
    # Anschrift entscheidet Steuersatz, Ort und Währung schon beim Schreiben.
    _order, step = where_of(db, row)
    allowed = modules.Beleg.parties_allowed(step.config) if step is not None else []
    return allowed[0] if len(allowed) == 1 else None


def possible_parties(db: Session, row: Voucher, step: ProcessStep) -> list[int]:
    """**Wer an diesem Beleg als Gegenpartei vorkommen KANN** – die zugelassenen, die
    gewählten und die angefragten, in dieser Reihenfolge, ohne Dubletten (für die Anschriften
    im Belegkopf und die Suche nach der Rechnung, die eine Gutschrift mindert)."""
    out: list[int] = []
    for number in (list(modules.Beleg.parties_allowed(step.config))
                   + parties_on(row)
                   + [q.party_id for q in quotes_of(db, row)]):
        if number is not None and number not in out:
            out.append(int(number))
    return out


def parties_on(row: Voucher) -> list[int]:
    """**Wen dieser Beleg betrifft – die Wahl am Beleg**, wo die Definition niemanden
    nennt. Leer ist der Normalfall; die eine Lesestelle (``row.parties`` ist ``NOT NULL``)."""
    return [int(n) for n in row.parties]


def agreed_amount(db: Session, row: Voucher) -> Optional[Decimal]:
    """**Was vereinbart ist** – der Betrag der gewählten Zeile."""
    q = chosen_quote(db, row)
    return q.amount if q is not None else None


def due_days_of(db: Session, row: Voucher) -> Optional[int]:
    """**Die Zahlungsfrist** – aus ihr kommen Fälligkeit und Vorauszahlung: die der
    gewählten Angebotszeile, vor der Zusage der Entwurf am Beleg (zwei Zeitpunkte, nicht
    zwei Wahrheiten)."""
    q = chosen_quote(db, row)
    return q.payment_days if q is not None else row.payment_days


def lead_days_of(db: Session, row: Voucher) -> Optional[int]:
    """**Die Lieferfrist** – dieselbe Regel wie ``due_days_of``: Zusage, sonst Entwurf."""
    q = chosen_quote(db, row)
    return q.lead_days if q is not None else row.lead_days


def credited(row: Voucher) -> Optional[Decimal]:
    """►►► **Was ein Storno nach der Rechnung gutgeschrieben hat** – der ganze Betrag. ◄◄◄

    Keine Spalte: storniert *und* gestellt heisst, die Gutschrift über die ganze Rechnung
    ist entstanden (``_revoke``). Danach schuldet niemand mehr etwas – ausser dem, was
    schon geflossen ist und zurückgeht.
    """
    return row.amount if (row.stage == vo.CANCELLED and row.billed_on is not None) else None


def balance_of(db: Session, row: Voucher) -> vo.Balance:
    """Der Saldo dieses Belegs – gerechnet in ``domain/voucher``, gelesen hier.

    **Berechnet ist, was auf der Rechnung steht** (``row.amount``): es gibt eine Rechnung
    je Beleg, und sie ist der Beleg. Dazu jede Geld-Zeile mit ihrer Art.
    """
    return vo.balance(agreed_amount(db, row), row.amount,
                      [(e.kind, e.amount) for e in entries_of(db, row)],
                      credited=credited(row))


# ---------------------------------------------------------------------------
# ►►► DIE RECHNUNG — sie IST der Beleg ◄►◄
# ---------------------------------------------------------------------------

def is_billed(row: Voucher) -> bool:
    """**Steht die Rechnung?** – die eine Frage, und sie hat kein eigenes Ja/Nein.

    ``billed_on`` ist das Rechnungsdatum; dass es dasteht, *ist* die Antwort. Ein Feld
    «gestellt?» daneben wäre die zweite Aussage über dieselbe Sache.
    """
    return row.billed_on is not None


def corrects(db: Session, row: Voucher) -> Optional[Voucher]:
    """**Welchen Beleg mindert dieser hier?** – oder ``None``.

    Der Verweis darf über Auftragsgrenzen zeigen: die Gutschrift gehört dorthin, wo die
    Ware zurückkommt, nicht in den Auftrag, der sie geliefert hat.
    """
    if row.corrects_id is None:
        return None
    return db.query(Voucher).filter(Voucher.id == row.corrects_id).first()


def minus(row: Voucher) -> bool:
    """**Mindert dieser Beleg?** – die eine Lesestelle, und sie fragt kein eigenes Feld.

    Dass ein Verweis dasteht, *ist* die Antwort (``corrects_id``) – ein Flag «ist
    Gutschrift» daneben wäre die zweite Wahrheit, und die eine vergessene Nachzieh-Stelle
    fällt erst auf, wenn ein Beleg das Falsche behauptet.
    """
    return row.corrects_id is not None


def inbound(row: Voucher) -> bool:
    """►►► **Kommt das Geld zu UNS?** ◄◄◄ Richtung **und** Minderung, an einer Stelle.

    Daran hängen die drei Dinge, die eine Gutschrift wirklich anders machen: der
    **Zahlungsdienst** (er zieht ein), der **Einzahlungsschein** (er trägt unsere
    Bankverbindung) und das Wort am Geld-Knopf. Nicht daran hängt, wer den Beleg
    **ausstellt** – das bleibt ``collects``.
    """
    return vo.inbound(collects=vo.of(row.direction).collects, minus=minus(row))


# ---------------------------------------------------------------------------
# ►►► DIE POSITIONEN — eine Form, und die Stufe friert sie ein ◄◄◄
# ---------------------------------------------------------------------------

def process_lines(db: Session, order: Order) -> list[tuple[int, int]]:
    """**Was steht im Auftrag?** – je Artikel eine Zeile ``(article_id, Stück)``.

    Derselbe Weg, aus dem der Prozess überall rechnet: offene Zugehörigkeit →
    Einzelinstanz → Instanz → Artikel. Sortiert, damit die Reihenfolge nicht von der
    Datenbank abhängt.

    **Über den ganzen Auftrag und nicht über den einzelnen Schritt.** Ein Angebot
    entsteht, *bevor* die Stücke am Modul ankommen – ein Beleg am Ende der Kette hätte
    sonst bis zuletzt eine leere Zeile. Und es ist fachlich richtig: dieselben sechs
    Wellen sind es, für die ich das Härten einkaufe und die ich danach verkaufe.
    """
    rows = (
        db.query(Instance.article_id, func.count(OrderUnit.id))
        .join(InstanceUnit, InstanceUnit.instance_id == Instance.id)
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
        .group_by(Instance.article_id)
        .all()
    )
    return sorted(((int(a), int(n)) for a, n in rows), key=lambda r: r[0])


def serials_of(db: Session, row: Voucher) -> dict[int, list[int]]:
    """►►► **Die Seriennummern je Artikel** – die Nummern der Instanzen, um die es geht. ◄◄◄

    Auf jedem Dokument steht neben dem Artikel, **welches** Stück es ist: die Instanznummer
    (bei einer Charge die Charge). Die Stücke sind die, über die der Beleg spricht – ab dem
    ersten Hinausgehen eingefroren (``unit_ids``), davor die offenen im Auftrag. Eine
    Ableitung, keine Spalte.
    """
    q = (db.query(Instance.article_id, Instance.object_id)
         .join(InstanceUnit, InstanceUnit.instance_id == Instance.id))
    if row.unit_ids is not None:
        if not row.unit_ids:
            return {}
        q = q.filter(InstanceUnit.id.in_([int(u) for u in row.unit_ids]))
    else:
        q = (q.join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
             .filter(OrderUnit.order_id == row.order_id, OrderUnit.released_at.is_(None)))
    out: dict[int, set[int]] = {}
    for article, number in q.all():
        if article is not None and number is not None:
            out.setdefault(int(article), set()).add(int(number))
    return {a: sorted(n) for a, n in out.items()}


def frozen_lines(row: Voucher) -> bool:
    """►►► **Folgen die Positionen noch dem Prozess?** ◄◄◄ Nur bis zum ersten Hinausgehen:
    ab dann spricht der Beleg über die Stücke, die damals da waren (``unit_ids``), und ab
    der Zusage ohnehin nie wieder."""
    return row.stage != vo.OFFER or row.unit_ids is not None


def units_problem(db: Session, row: Voucher, order: Order,
                  step: ProcessStep) -> Optional[str]:
    """►►► **Passen die Stücke noch zum Beleg?** – der Satz, oder ``None``. ◄◄◄

    Der Beleg spricht über die Stücke, die beim ersten Hinausgehen da waren
    (``unit_ids``). Hat eines davon den Auftrag verlassen, **ohne** dieses Modul passiert
    zu haben (eine Abweichung hat es gegriffen, es wurde ausgesondert), ist das Versprechen
    an die Partei hinfällig: es bleibt nur «Stornieren» – in jeder Stufe gleich. Ein Stück,
    das schon passiert ist, hält nichts auf.
    """
    if not row.unit_ids or row.stage == vo.CANCELLED:
        return None
    return once(db, ("units", row.id), lambda: _units_gone(db, row, order, step))


def _units_gone(db: Session, row: Voucher, order: Order, step: ProcessStep) -> Optional[str]:
    """Der Satz zu ``units_problem`` – gelesen aus offener Zugehörigkeit und Log."""
    frozen = {int(u) for u in row.unit_ids}
    here = {int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
        OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
        OrderUnit.instance_unit_id.in_(frozen)).all()}
    passed = {int(i) for (i,) in db.query(ProcessEvent.instance_unit_id).filter(
        ProcessEvent.order_id == order.id, ProcessEvent.step_id == step.id,
        ProcessEvent.kind == KIND_STEP,
        ProcessEvent.instance_unit_id.in_(frozen)).all()}
    gone = frozen - here - passed
    if not gone:
        return None
    word = {vo.OFFER: "angebotenen", vo.AGREED: "zugesagten"}.get(row.stage, "verrechneten")
    verb = "hat" if len(gone) == 1 else "haben"
    return (f"{len(gone)} der {len(frozen)} {word} Stücke {verb} den Auftrag verlassen – "
            f"es bleibt nur «{vo.UNDO}»")


# ---------------------------------------------------------------------------
# ►►► WIE ES UM DEN BELEG STEHT — lauter Ableitungen ◄◄◄
# ---------------------------------------------------------------------------

def valid_days_of(row: Voucher) -> int:
    """Wie lange die Offerte gilt – der Entwurf, sonst die Vorgabe."""
    return row.valid_days if row.valid_days is not None else vo.VALID_DAYS


def offered_on(db: Session, row: Voucher) -> Optional[date]:
    """**Wann zuletzt angeboten wurde** – der jüngste Versand im Angebotsspiegel."""
    days = [q.sent_on for q in quotes_of(db, row) if q.sent_on is not None]
    return max(days) if days else None


def valid_until(db: Session, row: Voucher) -> Optional[date]:
    """Bis wann die Offerte gilt – ``Anbieten`` + Gültigkeit. Nur, wo **wir** anbieten."""
    if vo.of(row.direction).quoted_by != vo.BY_US:
        return None
    sent = offered_on(db, row)
    return sent + timedelta(days=valid_days_of(row)) if sent is not None else None


def expired(db: Session, row: Voucher) -> bool:
    """►►► **Ist die Offerte abgelaufen?** ◄◄◄ Dann ist «Annehmen» gesperrt, und «Erneut
    anbieten» beginnt die Frist neu – in derselben Handlung wie «Anbieten»."""
    until = valid_until(db, row)
    return row.stage == vo.OFFER and until is not None and clock.today() > until


def fingerprint(db: Session, row: Voucher) -> str:
    """**Was eine Offerte ausmacht, als eine Zahl** – Positionen, Preise, Sätze, Leistung,
    Teilbeträge, Fristen, Gültigkeit, Lieferbedingung, Währung und Anschriften."""
    import hashlib
    import json
    data = {
        "lines": [[ln.article_id, ln.quantity, str(ln.price), ln.vat, ln.text, str(ln.part)]
                  for ln in lines_of(db, row)],
        "terms": [row.lead_days, row.payment_days, valid_days_of(row), row.incoterm,
                  row.currency, row.issuer_company_id],
        "to": [row.bill_to_company, row.billing_address_id, row.delivery_address_id,
               row.ownership],
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def changed_since_offer(db: Session, row: Voucher) -> bool:
    """►►► **Weicht der Beleg von dem ab, was hinausging?** ◄◄◄ Dann ist die gesendete
    Offerte überholt – angenommen werden kann nur die aktuelle Fassung."""
    return (row.stage == vo.OFFER and row.offered_hash is not None
            and vo.of(row.direction).quoted_by == vo.BY_US
            and fingerprint(db, row) != row.offered_hash)


def all_declined(db: Session, row: Voucher) -> bool:
    """**Alle haben abgesagt** – es steht niemand mehr da, mit dem es weitergeht."""
    rows = quotes_of(db, row)
    return row.stage == vo.OFFER and bool(rows) and all(q.state == vo.DECLINED for q in rows)


def deviation(db: Session, row: Voucher) -> Optional[Decimal]:
    """►►► **Weicht die Lieferantenrechnung von der Zusage ab?** – der Unterschied. ◄◄◄
    Nur bei einer Ausgabe, nur bis jemand entschieden hat (``deviation_note``)."""
    if vo.of(row.direction).collects or not is_billed(row) or row.deviation_note:
        return None
    agreed = agreed_amount(db, row)
    if agreed is None or row.amount is None:
        return None
    diff = row.amount - agreed
    return diff if abs(diff) > vo.SETTLED_TOLERANCE else None


def reminders(db: Session, row: Voucher) -> list[VoucherDocument]:
    """Die gesendeten Mahnungen – ihre Zahl IST die Mahnstufe."""
    return documents_of(db, row, vo.REMINDER_DOC)


def overdue(db: Session, row: Voucher) -> bool:
    """**Überfällig** – fällig, und es ist noch etwas offen."""
    return bool(row.stage == vo.BILLED and row.due_on and row.due_on < clock.today()
                and balance_of(db, row).open > vo.SETTLED_TOLERANCE)


def next_reminder(db: Session, row: Voucher) -> Optional[tuple[int, date]]:
    """►►► **Welche Mahnstufe als Nächste kommt, und ab wann** – oder ``None``. ◄◄◄

    Nur bei einer Rechnung, die **wir** stellen und die überfällig ist; höchstens drei
    Stufen, zehn Tage Abstand. Nichts geht von selbst – das System sagt, wann.
    """
    if not (vo.of(row.direction).collects and not minus(row) and overdue(db, row)):
        return None
    sent = reminders(db, row)
    if len(sent) >= len(vo.REMIND_LEVELS):
        return None
    after = (sent[-1].created_at.astimezone(clock.ZONE).date() + timedelta(days=vo.REMIND_DAYS) if sent
             else (row.due_on or clock.today()) + timedelta(days=1))
    return len(sent) + 1, after


def ownership_of(row: Voucher) -> Optional[str]:
    """Die Wahl «geht an die Partei · an uns» – ``None``, solange niemand gewählt hat
    (auch ein Wert, den es nicht mehr gibt, gilt als ungewählt)."""
    return row.ownership if row.ownership in dict(vo.OWNERSHIP) else None


def sold_units(db: Session, unit_ids: list[int]) -> set[int]:
    """►►► **Welche dieser Stücke gehören einer anderen Partei?** – eine Ableitung. ◄◄◄

    Massgebend ist je Stück das **jüngste nicht stornierte Zahlungsmodul, das es passiert
    hat** (der Log, ``kind = step``): steht dort «geht an die Partei», ist es verkauft;
    sonst – «an uns» oder gar kein Zahlungsmodul – gehört es uns. Ein Storno wirkt damit
    von selbst, ohne dass etwas zurückgesetzt wird; eine Retoure «an uns» hebt einen
    Verkauf auf, eine stornierte Retoure lässt ihn wieder gelten.

    Gelesen wird sie an genau einer Stelle: am Ziel des Auftrags (``process._finish``).
    """
    if not unit_ids:
        return set()
    rows = (
        db.query(ProcessEvent.instance_unit_id, Voucher.ownership)
        .join(Voucher, Voucher.step_id == ProcessEvent.step_id)
        .filter(ProcessEvent.instance_unit_id.in_(unit_ids),
                ProcessEvent.kind == KIND_STEP,
                Voucher.is_active.is_(True),
                Voucher.stage != vo.CANCELLED)
        .order_by(ProcessEvent.instance_unit_id, ProcessEvent.id.desc())
        .all()
    )
    latest: dict[int, Optional[str]] = {}
    for unit_id, how in rows:
        latest.setdefault(int(unit_id), how)
    return {u for u, how in latest.items() if how == vo.TO_PARTY}


def passable(db: Session, row: Voucher) -> bool:
    """►►► **Dürfen die Stücke dieses Modul jetzt passieren?** ◄◄◄ Ab der Zusage – bei
    einer Vorauszahlung erst, wenn das Geld da ist. Nie, solange die Stücke nicht mehr
    zum Beleg passen oder er storniert ist."""
    if row.stage not in (vo.AGREED, vo.BILLED):
        return False
    if vo.prepaid(due_days_of(db, row)):
        return balance_of(db, row).settled
    return True


def line_dicts(db: Session, row: Voucher) -> list[dict[str, Any]]:
    """Die Positionen in der Form, in der ``domain/voucher`` rechnet.

    Die Mathematik kennt keine Datenbank: sie bekommt ``{quantity, price, vat}`` und gibt
    Netto, Steuer und Brutto zurück. Diese Übersetzung steht **einmal**.
    """
    return [{"quantity": ln.quantity,
             "price": str(ln.price) if ln.price is not None else None,
             "part": str(ln.part) if ln.part is not None else None,
             "vat": ln.vat}
            for ln in lines_of(db, row)]


def priced_dicts(db: Session, row: Voucher) -> list[dict[str, Any]]:
    """Nur die Positionen, die wirklich einen Preis tragen.

    Bei einer **Ausgabe** gibt es keine – dort nennt die Gegenpartei eine Summe, und die
    Steuer steht auf *ihrer* Rechnung. Der Unterschied ist damit eine **Zahl**, keine
    Fallunterscheidung nach Richtung.
    """
    return [ln for ln in line_dicts(db, row) if ln["price"] is not None]


# ---------------------------------------------------------------------------
# ►► ANLAGE — mit der Freigabe, idempotent
# ---------------------------------------------------------------------------

def house_currency(db: Session) -> str:
    """**Die Währung des Hauses** – die des Betreibers, tolerant gelesen.

    Gibt es (noch) keinen Betreiber, gilt ``currency.DEFAULT``: ein harter Fehler beim
    Freigeben eines Auftrags wäre die falsche Antwort auf eine fehlende Stammdatenzeile.
    """
    operator = once(db, ("operator",), lambda: sites.find_operator(db))
    try:
        return cur.assert_code(getattr(operator, "currency", None))
    except ValueError:
        return cur.DEFAULT


def issuer_of(db: Session, actor_id: Optional[int]) -> Optional[int]:
    """**Welche unserer Gesellschaften stellt den Beleg?** – die des Freigebenden.

    ``None`` heisst «der Betreiber» – der Rückfall bleibt, er ist nur nicht die Regel.
    """
    if actor_id is None:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == actor_id).first()
    return getattr(u, "company_object_id", None)


def instantiate_for_order(db: Session, order: Order,
                          *, actor_id: Optional[int] = None) -> None:
    """Jedes Beleg-Modul dieses Auftrags bekommt seinen Beleg.

    **Bei der Freigabe und nicht beim Erreichen**: mit wem und worüber gehandelt wird,
    steht in der Definition, und ein Angebot einzuholen dauert – wer erst beim Erreichen
    anfragt, wartet die Frist ab, nachdem alles andere fertig ist.

    Idempotent (der partielle Unique-Index trägt); ohne ein solches Modul ein No-op.
    """
    rows = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id,
                ProcessStep.module_type == modules.BELEG)
        .all()
    )
    for step in rows:
        if of_step(db, step.id) is not None:
            continue
        # **Was das Modul vorgibt, steht im Beleg fest** – das Modul ist Master.
        fixed = modules.Beleg.presets_of(step.config)
        db.add(Voucher(
            order_id=order.id, step_id=step.id,
            direction=vo.assert_direction(
                modules.get(step.module_type).direction_of(step.config)),
            # Die Währung kommt vom Betreiber, nicht aus einem Feld: der Normalfall ist
            # die Hauswährung, und ihn zu tippen wäre eine Eingabe mit genau einer
            # richtigen Antwort.
            currency=house_currency(db),
            issuer_company_id=issuer_of(db, actor_id),
            stage=vo.OFFER,
            payment_days=fixed.get("payment_days"),
            lead_days=fixed.get("lead_days"),
            valid_days=fixed.get("valid_days"),
            incoterm=fixed.get("incoterm"),
            ownership=fixed.get("ownership"),
        ))
    if rows:
        db.flush()


# ---------------------------------------------------------------------------
# ►► WER SIEHT WAS — und wer darf was
# ---------------------------------------------------------------------------

def mine(db: Session, viewer: Optional[UserProfile]) -> Optional[list[Voucher]]:
    """**Woran ist dieser Betrachter beteiligt?** ``None`` = an allem.

    Beteiligt ist, wer **angefragt** wurde – seine Zeile steht im Angebotsspiegel. Seit
    der eine Tabelle ist, ist das eine gewöhnliche ``JOIN``-Bedingung statt einer
    JSONB-Containment-Abfrage.

    **Personal bekommt ``None``** – wer ohnehin ins ERP darf, braucht keine verengte
    Sicht. **Sonst fragt diese Funktion nicht nach der Rolle**: jeder darf Gegenpartei
    sein – die Rolle sagt, was jemand *für uns* tut, nicht ob wir mit ihm Geld austauschen.
    """
    if viewer is None or viewer.role in STAFF_ROLES:
        return None
    if viewer.object_id is None:
        return []
    return (
        db.query(Voucher)
        .join(VoucherQuote, VoucherQuote.voucher_id == Voucher.id)
        .filter(VoucherQuote.party_id == viewer.object_id,
                VoucherQuote.is_active.is_(True))
        .all()
    )


def where_of(db: Session, row: Voucher) -> tuple[Order, ProcessStep]:
    """Auftrag und Modul eines Belegs – für die Regeln, die nach den Stücken fragen."""
    return once(db, ("where", row.id), lambda: (
        db.query(Order).filter(Order.id == row.order_id).first(),
        db.query(ProcessStep).filter(ProcessStep.id == row.step_id).first()))


# ---------------------------------------------------------------------------
# ►► DIE DREI BERÜHRUNGSPUNKTE MIT DEM RAHMEN — je eine Zeile, no-op ohne dieses Modul
# ---------------------------------------------------------------------------

#: ►►► **Die Stücke passieren dieses Modul von selbst** – es gibt keinen Knopf dafür. ◄◄◄
PASSES_ITSELF = ("Die Stücke ziehen von selbst weiter – mit der Zusage, bei einer "
                 "Vorauszahlung mit dem Geld.")


def completion_problem(db: Session, *, step: ProcessStep) -> Optional[str]:
    """►►► **Warum es an diesem Modul keinen «Bestätigen»-Knopf gibt** – oder ``None``. ◄◄◄

    Ein Zahlungsmodul bestätigt niemand von Hand: die Stücke ziehen von selbst weiter
    (``advance``), sobald sie dürfen. Für jedes andere Modul ``None``.
    """
    return PASSES_ITSELF if of_step(db, step.id) is not None else None


def pass_problem(db: Session, *, step: ProcessStep) -> Optional[str]:
    """**Warum die Stücke noch nicht weiter dürfen** – oder ``None``. Die Auskunft zu
    ``passable``, mit dem Grund im Satz."""
    row = of_step(db, step.id)
    if row is None or passable(db, row):
        return None
    flow = vo.of(row.direction)
    if row.stage == vo.OFFER:
        return (f"«{flow.label}»: noch nicht zugesagt – die Stücke warten auf die "
                f"Zusage.")
    if row.stage == vo.CANCELLED:
        return (f"«{flow.label}» ist storniert. Die Stücke stehen still, bis ein "
                f"Abweichungsauftrag sie weiterführt.")
    money = balance_of(db, row)
    noun = vo.REFUND_NOUN if minus(row) else vo.PAYMENT_NOUN
    return (f"«{flow.label}» wartet auf die {noun}: {amount_text(money.paid, row.currency)} "
            f"von {amount_text(money.agreed, row.currency)} {row.currency} – "
            f"{vo.PAYMENT_TERMS[0][1]}, erst das Geld, dann weiter.")


def assert_completable(db: Session, *, step: ProcessStep, auto: bool = False) -> None:
    """**Die Tür** – gerufen von ``process.confirm_step``. Von Hand gibt es sie an einem
    Zahlungsmodul nicht; von selbst nur, wenn die Stücke dürfen."""
    if of_step(db, step.id) is None:
        return
    why = pass_problem(db, step=step) if auto else PASSES_ITSELF
    if why:
        raise HTTPException(status_code=409, detail=why)


def service_day(db: Session, step: ProcessStep) -> Optional[date]:
    """►►► **Wann wurde die Leistung erbracht?** – aus dem Prozess, nicht getippt. ◄◄◄

    Der Tag, an dem die Stücke **das Modul davor** verlassen haben, also bei diesem hier
    angekommen sind. **Das Rechnungsdatum ist es nicht**: eine zwei Wochen später
    geschriebene Rechnung verschöbe die Steuerperiode (MWSTG Art. 26 Bst. c).

    Gelesen wird darum das Ereignis des **Vorgängers**, nicht das eigene – ein ``step`` an
    *diesem* Modul heisst «hier fertig». Steht dieses Modul am Anfang, ist die Ankunft der
    **Start** des Auftrags. ``None`` heisst «hier ist noch nichts angekommen».
    """
    before = (
        db.query(ProcessStep.id)
        .filter(ProcessStep.order_id == step.order_id,
                ProcessStep.position < step.position)
        .order_by(ProcessStep.position.desc())
        .first()
    )
    q = db.query(ProcessEvent.created_at).filter(ProcessEvent.order_id == step.order_id)
    q = (q.filter(ProcessEvent.step_id == before[0], ProcessEvent.kind == KIND_STEP)
         if before else
         q.filter(ProcessEvent.kind == KIND_START, ProcessEvent.step_id.is_(None)))
    found = q.order_by(ProcessEvent.id.desc()).first()
    return found[0].date() if found and found[0] else None


def days_after(booked: date, days: Optional[int]) -> Optional[date]:
    """Fälligkeit = Rechnungsdatum + Frist. **Ohne Frist keine Fälligkeit** – ein
    erfundenes Datum wäre schlimmer als keines."""
    return None if days is None else booked + timedelta(days=days)


def delivery_date(db: Session, row: Voucher) -> Optional[date]:
    """**Wann er liefern wollte** – Zusagedatum + Lieferfrist der gewählten Zeile.

    Dieselbe Form wie die Fälligkeit: eine Frist ist eine Vereinbarung, ein Datum ihre
    Folge. **Ohne Lieferfrist kein Termin** – ein erfundener wäre schlimmer als keiner.
    """
    q = chosen_quote(db, row)
    if row.agreed_on is None or q is None:
        return None
    return days_after(row.agreed_on, q.lead_days)


def amount_text(value: Optional[Decimal], code: str) -> Optional[str]:
    """Ein Betrag als String – mit den Nachkommastellen **dieser** Währung."""
    return None if value is None else cur.money(value, code)


def public_link(token: str) -> str:
    """**Der Link der Partei** – die Seite, die das Dokument zeigt (ohne Anmeldung)."""
    from ..core.config import get_settings
    return f"{get_settings().frontend_base_url.rstrip('/')}/beleg?t={token}"


def named(db: Session, numbers: list[Optional[int]]) -> list[dict[str, Any]]:
    """Objektnummern auf ihren Anzeigenamen – **eine** Abfrage, nicht eine je Zeile."""
    wanted = [n for n in numbers if n]
    if not wanted:
        return []
    rows = {
        u.object_id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.object_id.in_(wanted)).all()
    }
    return [{"object_id": n, "name": rows.get(n, str(n))} for n in wanted]
