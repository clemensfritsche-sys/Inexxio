"""**Der Beleg als Dienst** — Angebotsspiegel, Positionen, Forderungen, Zahlungen.

Drei Formregeln (``docs/history/2026-09-neuaufbau-zahlungsmodul.md``):

1. ►►► **Ein Verb wird an EINER Stelle deklariert.** ◄◄◄ ``VERBS`` sagt je Verb: *in
   welcher Stufe · welche Stammdaten · wer darf · welche Funktion*.

2. ►►► **Der Angebotsspiegel ist eine Tabelle** (``voucher_quotes``) – eine Zeile ändert
   man an Ort, und «woran ist dieser Betrachter beteiligt» ist eine ``WHERE``-Zeile.

3. ►►► **Die Position gibt es in EINER Form.** ◄◄◄ Eingefroren wird durch die **Stufe**:
   solange ``offer``, zieht ``sync_lines`` aus dem Prozess nach.

*Mit wem*, *was vereinbart ist* und *welche Zahlungsfrist* sind **Ableitungen** aus der
gewählten Angebotszeile – derselbe Beleg kann darum nicht zwei Dinge sagen.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Optional

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..core.config import payment_service_ready
from ..domain import currency as cur
from ..domain import incoterms as inc
from ..domain import modules
from ..domain import uid as uid_fmt
from ..domain import voucher as vo
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderUnit, ProcessEvent, ProcessStep,
    UserProfile, Voucher, VoucherDocument, VoucherEntry, VoucherLine, VoucherQuote,
)
from ..models.process_event import KIND_START, KIND_STEP
from . import address, address_book, people, qrbill, sites
# Wer ohnehin alles sieht – Personal hat keine verengte Sicht (die eine Stelle).
from .people import STAFF_ROLES


# ---------------------------------------------------------------------------
# ►►► DIE VERBEN — EINE Deklaration je Verb ◄◄◄
# ---------------------------------------------------------------------------
#
# Die vier Fragen über ein Verb stehen in **einer Zeile** («eine Sache, eine Stelle»):
#
# ``stages``  in welchen Stufen ist es erlaubt?
# ``needs``   welche Stammdaten müssen dafür da sein? (kumulativ, siehe ``REQUIRED_FOR``)
# ``party``   darf die **Gegenpartei** es? – und zwar als Regel, nicht als Liste je
#             Richtung: «wer den Preis empfängt, nimmt an oder lehnt ab».
# ``run``     welche Funktion führt es aus? ``None`` = eigener Weg (``pay_online``
#             **löst** eine Zahlung aus und bucht nichts – gebucht wird, wenn der
#             Zahlungsdienst es meldet).

#: Wer die Gegenpartei sein darf – vier Regeln, keine Liste je Richtung.
NEVER = "never"
ALWAYS = "always"
#: Nur, wo **sie** den Preis nennt (Ausgabe): dann offeriert sie.
IF_THEY_PRICE = "they"
#: Nur, wo **wir** ihn nennen (Einnahme): dann nimmt sie an. Unseren Preis zu
#: überschreiben wäre keine Antwort, sondern eine Gegenofferte – und die ist ein neuer
#: Beleg.
IF_WE_PRICE = "we"


@dataclass(frozen=True)
class Verb:
    """**Eine Handlung am Beleg** – alles über sie in einer Zeile."""

    stages: tuple[str, ...]
    run: Optional[Callable[..., None]] = None
    needs: tuple[str, ...] = ()
    party: str = NEVER

    def allows(self, flow: vo.Direction) -> bool:
        """Darf die **Gegenpartei** dieses Verb – bei dieser Richtung?"""
        if self.party == ALWAYS:
            return True
        if self.party == IF_THEY_PRICE:
            return flow.quoted_by == vo.BY_PARTY
        if self.party == IF_WE_PRICE:
            return flow.quoted_by == vo.BY_US
        return False


# ---------------------------------------------------------------------------
# ►►► WAS DIESES MODUL AN STAMMDATEN BRAUCHT ◄◄◄
# ---------------------------------------------------------------------------
#
# *«Wenn das Modul zu wenig Angaben hat, um seinen Prozess abzuwickeln, dann muss es Alarm
# schlagen.»* – **Das ist kein neuer Mechanismus, es ist ``StepNeed`` für Stammdaten**:
# eine Zeile (wo sie hingehört · was fehlt · warum), **kein** Zustand und **kein**
# Pausenwert. Durchgesetzt über ``can``: fehlt etwas, führt ``can`` das Verb nicht – der
# Knopf ist gar nicht da –, und ``assert_allowed`` weist an derselben Liste ab.
#
# **Gestaffelt und kumulativ**: eine Anfrage braucht weniger als eine Rechnung. Stünde
# alles vor der ersten Handlung, hielte eine Angabe das Modul an, die erst in drei
# Schritten zählt – und man müsste sie erfinden, um weiterzukommen.
#
# ``(seite, feld, beschriftung, grund)`` – ``seite`` ist ``us`` oder ``party``.
REQUIRED_FOR: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "ask": (
        ("us", "name", "Firma und Rechtsform",
         "Ein Beleg nennt die Rechtsperson, die ihn stellt."),
        ("us", "address", "Anschrift",
         "Ohne Sitz ist der Aussteller nicht bestimmbar."),
        ("us", "contact", "E-Mail oder Telefon",
         "Ohne Kontaktweg landet jede Rückfrage im Telefonbuch."),
    ),
    # **Die Gegenpartei steht erst mit der ZUSAGE fest.** Beim Anfragen ist sie noch nicht
    # gewählt, und das ist der Sinn der Stufe: man fragt mehrere.
    "agree": (
        ("party", "name", "Name",
         "Ein Beleg braucht einen Adressaten."),
        ("party", "address", "Anschrift",
         "Eine Zusage bindet eine Rechtsperson – die braucht einen Sitz."),
        ("us", "uid", "UID / MWST-Nummer",
         "Ohne sie kann dem Empfänger der Vorsteuerabzug verweigert werden "
         "(MWSTG Art. 26)."),
    ),
    "bill": (
        ("us", "iban", "IBAN",
         "Auf eine Rechnung gehört, wohin überwiesen wird."),
        ("party", "uid", "UID / MWST-Nummer",
         "Beim Reverse Charge schuldet der Leistungsempfänger die Steuer – ohne seine "
         "Nummer trägt das Verfahren nicht."),
    ),
}


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


def entries_of(db: Session, row: Voucher) -> list[VoucherEntry]:
    """**Die Zahlungen**, älteste zuerst – nur die gültigen.

    Es gibt nur noch eine Art Geld-Zeile: die Forderung ist der **Beleg selbst**
    (``billed_on`` & Co.). Eine alte ``charge``-Zeile ist von Migration 138 auf inaktiv
    gesetzt worden – ohne das zählte sie hier als Geldeingang.
    """
    return (
        db.query(VoucherEntry)
        .filter(VoucherEntry.voucher_id == row.id, VoucherEntry.is_active.is_(True))
        .order_by(VoucherEntry.booked_on, VoucherEntry.id)
        .all()
    )


def quotes_of(db: Session, row: Voucher) -> list[VoucherQuote]:
    """Der Angebotsspiegel – in der Reihenfolge, in der angefragt wurde."""
    return (
        db.query(VoucherQuote)
        .filter(VoucherQuote.voucher_id == row.id, VoucherQuote.is_active.is_(True))
        .order_by(VoucherQuote.id)
        .all()
    )


def documents_of(db: Session, row: Voucher, kind: Optional[str] = None
                 ) -> list[VoucherDocument]:
    """**Die Dokumente, so wie sie hinausgingen** – älteste zuerst."""
    q = db.query(VoucherDocument).filter(VoucherDocument.voucher_id == row.id,
                                         VoucherDocument.is_active.is_(True))
    if kind is not None:
        q = q.filter(VoucherDocument.kind == kind)
    return q.order_by(VoucherDocument.id).all()


def lines_of(db: Session, row: Voucher) -> list[VoucherLine]:
    """Die Positionen – in ihrer Reihenfolge auf dem Papier."""
    return (
        db.query(VoucherLine)
        .filter(VoucherLine.voucher_id == row.id, VoucherLine.is_active.is_(True))
        .order_by(VoucherLine.position, VoucherLine.id)
        .all()
    )


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
    """►►► **An wen geht dieser Beleg – jetzt, nicht erst mit der Zusage** (#939). ◄◄◄

    ``party_of`` beantwortet «mit wem wurde abgeschlossen» und ist vor der Zusage ``None``.
    Für den **Belegkopf** ist das zu wenig: eine Offerte ist adressiert, sobald sie an
    genau einen hinausgeht – und stand dort niemand, meldete der Kopf «Anschrift fehlt»,
    obwohl oben ein Leistungsempfänger angefragt war.

    **Genau einer, sonst keiner.** Werden mehrere angefragt, ist es ein Rundschreiben und
    es gibt keinen einen Adressaten – eine geratene Auswahl wäre schlimmer als die leere
    Zeile. Die **Vollständigkeitsprüfung** (``gaps``) fragt weiterhin ``party_of``: sie
    entscheidet, ob jemand **gebunden** ist, und das tut erst die Zusage.
    """
    chosen = party_of(db, row)
    if chosen is not None:
        return chosen
    rows = quotes_of(db, row)
    if rows:
        return rows[0].party_id if len(rows) == 1 else None
    # ►►► **Auch die blosse Wahl adressiert schon** (Testnotiz #1000). ◄◄◄ Wer gewählt,
    # aber noch nicht angefragt ist, steht auf dem Beleg – sonst sagte der Kopf «Anschrift
    # fehlt» über jemanden, den man eine Zeile höher ausgewählt hat. Dieselbe Regel wie
    # oben: genau einer, sonst keiner.
    picked = parties_on(row)
    if picked:
        return picked[0] if len(picked) == 1 else None
    # **Nennt die Definition genau einen, ist er es** – auch bevor etwas hinausging: die
    # Anschrift entscheidet Steuersatz, Ort und Währung schon beim Schreiben.
    step = db.query(ProcessStep).filter(ProcessStep.id == row.step_id).first()
    allowed = modules.Beleg.parties_allowed(step.config) if step is not None else []
    return allowed[0] if len(allowed) == 1 else None


def _possible_parties(db: Session, row: Voucher, step: ProcessStep) -> list[int]:
    """►►► **Wer an diesem Beleg als Gegenpartei vorkommen KANN** (Testnotiz #962). ◄◄◄

    Die **zugelassenen** aus der Definition und die **angefragten** aus dem Spiegel – in
    dieser Reihenfolge, ohne Dubletten. Zwei Quellen, eine Liste: eine zugelassene Partei
    ist noch keine angefragte, und eine frei gewählte steht in keiner Definition.

    Gebraucht wird sie für die **Anschriften** im Belegkopf. Nur die Angefragten zu nennen
    war zu eng – im Offertenschritt ist noch niemand angefragt, und genau dort will man
    sehen, an wen man gleich schreibt.
    """
    out: list[int] = []
    for number in (list(modules.Beleg.parties_allowed(step.config))
                   + parties_on(row)
                   + [q.party_id for q in quotes_of(db, row)]):
        if number is not None and number not in out:
            out.append(int(number))
    return out


def parties_on(row: Voucher) -> list[int]:
    """►►► **Wen dieser Beleg betrifft – die Wahl zur Laufzeit** (Testnotiz #1000). ◄◄◄

    Die dritte Quelle neben Definition und Angebotsspiegel, und die einzige, die ein
    Mensch **an diesem Beleg** setzt: wo die Vorlage niemanden nennt, steht hier, wen er
    meint. **Leer ist der Normalfall**, nicht ein Fehler.

    Die eine Lesestelle – ``row.parties`` ist ``NOT NULL``, aber ein Altbestand aus der
    Zeit vor Migration 136 kann über das Spalten-Netz gekommen sein; tolerant gelesen
    kostet das eine Zeile und erspart eine Ausnahme an drei Stellen.
    """
    return [int(n) for n in (row.parties or []) if n is not None]


def agreed_amount(db: Session, row: Voucher) -> Optional[Decimal]:
    """**Was vereinbart ist** – der Betrag der gewählten Zeile."""
    q = chosen_quote(db, row)
    return q.amount if q is not None else None


def due_days_of(db: Session, row: Voucher) -> Optional[int]:
    """**Die Zahlungsfrist** – aus ihr kommen Fälligkeit und Vorauszahlung.

    ►►► **Die Vereinbarung, sonst der Entwurf** (Testnotiz #985). ◄◄◄ Steht ein Zuschlag,
    gilt die Frist **seiner** Zeile – ab dort ist eine zweite Partei gebunden. Davor gilt,
    was auf dem Beleg steht (``vouchers.payment_days``): die Zeile, die sie tragen würde,
    gibt es noch gar nicht.

    Zwei Wahrheiten sind es nicht – es sind zwei **Zeitpunkte**, und die Reihenfolge hier
    ist die Regel dazu.
    """
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
                      [(e.kind or vo.PAYMENT, e.amount) for e in entries_of(db, row)],
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


def sync_lines(db: Session, row: Voucher, order: Order,
               step: Optional[ProcessStep] = None) -> list[VoucherLine]:
    """►►► **Die Positionen aus dem Prozess nachziehen — nur bis zum ersten Hinausgehen.** ◄◄◄

    Das ist der ganze Einfrier-Mechanismus: solange nichts hinausgegangen ist, sind
    Artikel und Mengen das, was im Auftrag steht; danach nie wieder (``frozen_lines``).
    Verlässt danach ein Stück den Auftrag, passt der Beleg nicht mehr – das sagt
    ``units_problem``, und es bleibt nur «Stornieren».

    **Was ein Mensch eingetragen hat, überlebt** (Preis, Satz, Leistung, Teilbetrag, Zoll):
    nachgezogen werden Artikel und Menge. Eine neue Zeile bekommt die **Leistung aus dem
    Modul** vorbelegt («Was ist zu tun?»).

    **Zwei gleichzeitige Anzeigen legen dieselbe Zeile nicht zweimal an** (Cleanup B-37):
    ``ON CONFLICT DO NOTHING`` gegen ``uq_voucher_lines_article``.

    Danach passen Steuersatz und Währung zur Anschrift (``_fit``) – solange der Beleg
    noch geschrieben wird.
    """
    rows = lines_of(db, row)
    if frozen_lines(row):
        if row.stage == vo.OFFER:
            _fit(db, row, rows)
        return rows
    counts = dict(process_lines(db, order))
    order_index = {a: i for i, a in enumerate(counts)}
    known = {r.article_id for r in rows if r.article_id is not None}
    missing = [a for a in counts if a not in known]
    if missing:
        task = modules.Beleg.instruction_of(step.config) if step is not None else ""
        db.execute(
            pg_insert(VoucherLine)
            .values([{"voucher_id": row.id, "article_id": a, "quantity": counts[a],
                      "vat": vo.DEFAULT_VAT, "position": order_index[a],
                      "text": task or None} for a in missing])
            .on_conflict_do_nothing(index_elements=["voucher_id", "article_id"],
                                    index_where=text("is_active"))
        )
        rows = lines_of(db, row)
    by_article = {r.article_id: r for r in rows if r.article_id is not None}
    free = [r for r in rows if r.article_id is None]
    for article, n in counts.items():
        found = by_article.get(article)
        if found is not None:
            found.quantity = n
            found.position = order_index[article]
    for article, found in list(by_article.items()):
        if article not in counts:
            # **Soft-Delete wie überall im Haus** – ein Beleg, der einmal eine Zeile
            # trug, soll sie nicht spurlos verlieren.
            found.is_active = False
            by_article.pop(article)
    for i, found in enumerate(free):
        found.position = len(counts) + i
    db.flush()
    rows = lines_of(db, row)
    _fit(db, row, rows)
    return rows


def services_of(db: Session, rows: list[VoucherLine]) -> dict[int, bool]:
    """**Ware oder Dienstleistung** je Artikel – eine Abfrage für alle Zeilen."""
    ids = [ln.article_id for ln in rows if ln.article_id is not None]
    if not ids:
        return {}
    return {a.id: bool(a.is_service)
            for a in db.query(Article).filter(Article.id.in_(ids)).all()}


def _fit(db: Session, row: Voucher, rows: list[VoucherLine]) -> None:
    """►►► **Steuersatz und Währung folgen der Anschrift** – solange geschrieben wird. ◄◄◄

    Steht ein Satz, den die Anschrift nicht zulässt (Ausland: nur Export bzw. Reverse
    Charge; Inland: kein Nullsatz), wird er der erste zulässige – bewusst ohne Rückfrage:
    der Satz ist hier keine Wahl, sondern eine Folge. Eine **Fremdwährung** gibt es nur mit
    einer Lieferadresse im Ausland; sonst gilt die Hauswährung.

    Nur, wo **wir** den Preis nennen (Einnahme): bei einer Ausgabe steht die Steuer auf
    *seinem* Papier.
    """
    if vo.of(row.direction).quoted_by != vo.BY_US:
        return
    delivery, seat = destination(db, row)
    kinds = services_of(db, rows)
    changed = False
    for ln in rows:
        allowed = vo.vat_choices(service=kinds.get(ln.article_id or 0, False),
                                 delivery_country=delivery, seat_country=seat)
        if ln.vat not in allowed:
            ln.vat = allowed[0]
            changed = True
    if not vo.abroad(delivery) and row.currency != house_currency(db):
        row.currency = house_currency(db)
        changed = True
    if changed:
        db.flush()


def destination(db: Session, row: Voucher) -> tuple[Optional[str], Optional[str]]:
    """►►► **Wohin geht die Leistung?** – (Land der Lieferadresse, Land des Sitzes) des
    Leistungsempfängers. ◄◄◄

    Bei einer Ausgabe sind **wir** der Empfänger. Ohne Adressaten (noch niemand gewählt
    oder mehrere angefragt) gibt es kein Land – und damit kein Ausland.
    """
    if not vo.of(row.direction).collects:
        ours = dict((row.head or {}).get("ours") or _ours(db, row))
        return ours.get("country"), ours.get("country")
    number = party_of(db, row) or addressee_of(db, row)
    who = billing_of(db, row, number) if number is not None else {}
    seat = (who.get("address") or {}).get("country")
    delivery = (who.get("delivery") or {}).get("country") or seat
    return delivery, seat


def has_goods(db: Session, row: Voucher) -> bool:
    """Trägt der Beleg **Ware**? Ohne Ware gibt es keine Lieferbedingung und keinen Zoll."""
    rows = lines_of(db, row)
    kinds = services_of(db, rows)
    return any(not kinds.get(ln.article_id or 0, False) for ln in rows) or not rows


def is_export(db: Session, row: Voucher) -> bool:
    """►►► **Ist das eine Ausfuhr?** – Einnahme, Ware, Lieferadresse im Ausland. ◄◄◄ Dann
    gilt 0 % Export, Zolltarif, Ursprung und Gewicht sind Pflicht, und erledigt ist der
    Beleg erst mit dem Ausfuhrnachweis."""
    if not vo.of(row.direction).collects or minus(row):
        return False
    delivery, _seat = destination(db, row)
    return vo.abroad(delivery) and has_goods(db, row)


def incoterm_place_of(db: Session, row: Voucher) -> Optional[str]:
    """►►► **Der benannte Ort – abgeleitet, nicht getippt.** ◄◄◄

    E/F-Klauseln (EXW, FCA, FAS, FOB): die Versandadresse des Leistungserbringers.
    C/D-Klauseln: die Lieferadresse des Empfängers. Nach der Zusage steht er eingefroren
    am Beleg (``incoterm_place``)."""
    if not row.incoterm:
        return None
    if row.stage != vo.OFFER and row.incoterm_place:
        return row.incoterm_place
    head = document_head(db, row, won=True)
    side = head["supplier"] if inc.place_at_ours(row.incoterm) else head["customer"]
    return side.get("ship_city") or side.get("city") or None


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
    return row.stage == vo.OFFER and until is not None and date.today() > until


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


def is_done(db: Session, row: Voucher) -> bool:
    """►►► **Erledigt** – eine Ableitung, kein Knopf: gestellt, Saldo null und, bei einer
    Ausfuhr, der Nachweis da. ◄◄◄"""
    if row.stage != vo.BILLED:
        return False
    if is_export(db, row) and not row.export_number:
        return False
    return balance_of(db, row).even


def reminders(db: Session, row: Voucher) -> list[VoucherDocument]:
    """Die gesendeten Mahnungen – ihre Zahl IST die Mahnstufe."""
    return documents_of(db, row, vo.REMINDER_DOC)


def overdue(db: Session, row: Voucher) -> bool:
    """**Überfällig** – fällig, und es ist noch etwas offen."""
    return bool(row.stage == vo.BILLED and row.due_on and row.due_on < date.today()
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
    after = (sent[-1].created_at.date() + timedelta(days=vo.REMIND_DAYS) if sent
             else (row.due_on or date.today()) + timedelta(days=1))
    return len(sent) + 1, after


def ownership_of(row: Voucher) -> Optional[str]:
    """Die Wahl «geht an die Partei · an uns» – ``None``, solange niemand gewählt hat
    (auch ein Wert, den es nicht mehr gibt, gilt als ungewählt)."""
    return row.ownership if row.ownership in dict(vo.OWNERSHIP) else None


def ownership_problem(row: Voucher) -> Optional[str]:
    """►►► **Ohne Wahl des Eigentums geht kein Beleg hinaus und keiner wird zugesagt.** ◄◄◄
    Zwei Formen einer Regel: dieser Satz am gesperrten Knopf, ``_assert_ownership_chosen``
    als Tor."""
    if ownership_of(row) is None:
        return (f"Ohne Wahl beim {vo.OWNERSHIP_LABEL} ist offen, wem die Stücke danach "
                f"gehören – «" + "» oder «".join(l for _, l in vo.OWNERSHIP) + "».")
    return None


def _assert_ownership_chosen(row: Voucher) -> None:
    problem = ownership_problem(row)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


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
    from ..models import ProcessEvent
    from ..models.process_event import KIND_STEP
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


# ---------------------------------------------------------------------------
# ►►► DIE LEISTE — Stand, wer dran ist, die eine Handlung (oder warum keine) ◄◄◄
# ---------------------------------------------------------------------------

def _state(key: str, label: str, tone: str, text: str, *,
           when: Optional[date] = None, word: Optional[str] = None,
           primary: Optional[str] = None) -> dict[str, Any]:
    """Eine Zeile der Leiste. ``when``/``word`` («fällig» + Datum) setzt die Oberfläche
    über ``lib/when`` – ein Datum schreibt nur sie."""
    return {"key": key, "label": label, "tone": tone, "text": text,
            "date": when, "date_word": word, "primary": primary}


def situation(db: Session, row: Voucher, *, order: Order,
              step: ProcessStep) -> dict[str, Any]:
    """►►► **Wie steht der Beleg – in einem Satz, mit der einen nächsten Handlung.** ◄◄◄

    Die Leiste der Karte ist **nie leer**: Stand, wer dran ist, und die Handlung, die jetzt
    ansteht (``primary``) – leer nur bei *Erledigt* und *Storniert*. Ein Wächter prüft das
    für jeden Zustand (keine Sackgasse).
    """
    flow = vo.of(row.direction)
    party = "Der Kunde" if flow.collects else "Der Lieferant"
    problem = units_problem(db, row, order, step)
    if row.stage == vo.CANCELLED:
        return _cancelled_state(db, row)
    if problem:
        return _state("locked", "Die Stücke passen nicht mehr", "danger", problem,
                      primary="revoke")
    if row.stage == vo.OFFER:
        return _offer_state(db, row, flow)
    if row.stage == vo.AGREED:
        if vo.CONFIRM_DOC in papers_due(db, row):
            return _paper_state(vo.CONFIRM_DOC)
        verb = vo.charge_word(collects=flow.collects, minus=minus(row))
        if not flow.collects:
            return _state("agreed", "Bestellt", "pending",
                          "Sie sind dran: Rechnung erfassen, sobald sie da ist",
                          primary="bill")
        lead = ("Vorauszahlung – die Stücke warten auf das Geld · "
                if vo.prepaid(due_days_of(db, row)) else "")
        return _state("agreed", "Zugesagt", "pending",
                      f"{lead}Sie sind dran: {verb}", primary="bill")
    return _billed_state(db, row, flow, party)


def _paper_state(kind: str) -> dict[str, Any]:
    """**Ein Papier steht an** – die Auftragsbestätigung nach der Zusage, die Quittung nach
    dem Geld. Hinaus geht es mit der Freigabe (``release``)."""
    word = vo.DOCUMENTS.get(kind, kind)
    return _state("paper", f"{word} steht an", "pending",
                  f"Sie sind dran: {word} prüfen und freigeben", primary="release")


def _cancelled_state(db: Session, row: Voucher) -> dict[str, Any]:
    money = balance_of(db, row)
    if money.open < -vo.SETTLED_TOLERANCE:
        return _state("cancelled", "Storniert", "danger",
                      f"{_money(-money.open, row.currency)} gehören dem "
                      f"{'Kunden' if vo.of(row.direction).collects else 'Lieferanten'} – "
                      f"Sie sind dran: erstatten", primary="refund")
    if credited(row) is not None and vo.of(row.direction).collects:
        text = "Gutschrift über die ganze Rechnung, von selbst"
    elif row.cancel_note:
        text = f"Grund: {row.cancel_note}"
    elif row.agreed_on is not None:
        text = "nach der Zusage – es ist nichts geschuldet"
    else:
        text = "das Angebot gilt nicht mehr"
    return _state("cancelled", "Storniert", "neutral", text)


def _offer_state(db: Session, row: Voucher, flow: vo.Direction) -> dict[str, Any]:
    quotes = quotes_of(db, row)
    if not quotes:
        if minus(row):
            target = corrects(db, row)
            text = (f"mindert Rechnung {target.number}" if target is not None
                    else "zuerst die Rechnung wählen, die sie mindert")
            return _state("draft", "Gutschrift – Entwurf", "pending", text, primary="ask")
        return _state("draft", "Entwurf", "pending", "Sie sind dran", primary="ask")
    if all_declined(db, row):
        return _state("declined", "Alle haben abgesagt", "danger",
                      "Sie sind dran: anderen Partner wählen oder stornieren",
                      primary="party")
    if expired(db, row):
        days = (date.today() - valid_until(db, row)).days
        return _state("expired", "Offerte abgelaufen", "danger",
                      f"seit {days} {'Tag' if days == 1 else 'Tagen'} – Sie sind dran",
                      primary="ask")
    if changed_since_offer(db, row):
        return _state("changed", "Geändert", "pending",
                      "die gesendete Offerte ist überholt – Sie sind dran: erneut anbieten",
                      primary="ask")
    open_rows = [q for q in quotes if q.state != vo.DECLINED]
    many = len(open_rows) > 1
    if flow.collects:
        who = "die Kunden antworten · Die Kunden sind dran" if many else \
            "jetzt antwortet der Kunde · Der Kunde ist dran"
        return _state("sent", "Angeboten", "pending", who,
                      when=valid_until(db, row), word="gültig bis")
    who = "die Lieferanten antworten · Die Lieferanten sind dran" if many else \
        "der Lieferant antwortet · Der Lieferant ist dran"
    return _state("sent", "Angefragt", "pending", who)


def _billed_state(db: Session, row: Voucher, flow: vo.Direction,
                  party: str) -> dict[str, Any]:
    money = balance_of(db, row)
    gap = deviation(db, row)
    if gap is not None:
        sign = "+" if gap > 0 else "−"
        return _state("deviation", "Rechnung weicht ab", "danger",
                      f"{sign}{_money(abs(gap), row.currency)} zur Zusage – Sie sind dran",
                      primary="accept")
    export_open = is_export(db, row) and not row.export_number
    if money.even:
        if export_open:
            return _state("proof", "Bezahlt", "pending",
                          "Ausfuhrnachweis fehlt – erst damit erledigt", primary="export")
        if vo.RECEIPT_DOC in papers_due(db, row):
            return _paper_state(vo.RECEIPT_DOC)
        return _state("done", "Erledigt", "done", _done_text(db, row))
    if money.open < -vo.SETTLED_TOLERANCE:
        whose = ("dem Kunden" if flow.collects else "uns") if not minus(row) else "uns"
        verb = "gehören" if whose == "dem Kunden" else "stehen"
        rest = f"{_money(-money.open, row.currency)} {verb} {whose}" + (
            "" if whose == "dem Kunden" else " zu")
        return _state("overpaid", "Zu viel bezahlt", "danger", rest, primary="refund")
    proof = " · Ausfuhrnachweis fehlt" if export_open else ""
    if overdue(db, row):
        return _overdue_state(db, row, proof)
    if money.paid > 0 and money.open < vo.SMALL_REST:
        return _state("short", "Zu wenig bezahlt", "pending",
                      f"es fehlen {_money(money.open, row.currency)} – offen lassen oder "
                      f"ausbuchen", primary="writeoff")
    if minus(row):
        return _state("open", "Gutschrift gestellt", "pending",
                      f"wir erstatten {_money(money.open, row.currency)}{proof}",
                      when=row.due_on, word="bis", primary="pay")
    if not flow.collects:
        label = "Teilweise bezahlt" if money.paid > 0 else "Rechnung erfasst"
        return _state("open", label, "pending", f"Sie sind dran: bezahlen{proof}",
                      when=row.due_on, word="fällig", primary="pay")
    label = "Teilweise bezahlt" if money.paid > 0 else "Rechnung gestellt"
    return _state("open", label, "pending", f"{party} ist dran{proof}",
                  when=row.due_on, word="fällig", primary="pay")


def _overdue_state(db: Session, row: Voucher, proof: str) -> dict[str, Any]:
    nxt = next_reminder(db, row)
    sent = reminders(db, row)
    days = (date.today() - row.due_on).days if row.due_on else 0
    if nxt is not None and nxt[1] <= date.today():
        return _state("overdue", "Überfällig", "danger",
                      f"seit {days} {'Tag' if days == 1 else 'Tagen'} – die "
                      f"{vo.remind_word(nxt[0])} ist fällig{proof}", primary="remind")
    if nxt is not None:
        return _state("overdue", "Überfällig", "danger",
                      f"{vo.remind_word(len(sent))} gesendet – nächste Stufe{proof}",
                      when=nxt[1], word="ab", primary="pay")
    return _state("overdue", "Überfällig", "danger",
                  f"{vo.REMIND_LEVELS[-1]} gesendet – Sie sind dran{proof}", primary="pay")


def _done_text(db: Session, row: Voucher) -> str:
    """Was zuletzt geschah, als der Saldo null wurde – ein Satz statt einer Liste."""
    rows = entries_of(db, row)
    last = rows[-1] if rows else None
    if last is None:
        return "nichts mehr zu tun"
    amount = _money(abs(last.amount), row.currency)
    if last.kind == vo.WRITEOFF:
        return f"{amount} ausgebucht ({vo.reason_label(last.reason) or ''})".replace(" ()", "")
    if last.kind == vo.TIP:
        return f"{amount} als Trinkgeld behalten"
    if last.amount < 0 or minus(row):
        return f"{amount} erstattet"
    if last.method == vo.CARD:
        return "mit Karte bezahlt – nichts mehr zu tun"
    return "bezahlt – nichts mehr zu tun"


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


def embed_lines(db: Session, row: Voucher) -> list[dict[str, Any]]:
    """Die Positionen **mit Namen und Zoll-Angaben** – das, was die Gegenpartei liest.

    ►►► **Zoll: der Artikel belegt vor, der Beleg trägt den Wert.** ◄◄◄ Die
    Zolltarifnummer ist eine Eigenschaft der **Sache**; welche auf *diesem* Beleg steht,
    ist eine Aussage **dieses Geschäfts** – dieselbe Beziehung wie beim Preis. Steht in
    der Zeile ein Wert, gilt er; sonst der des Artikels. **Zurückgeschrieben wird
    nichts** – ein Beleg korrigiert keine Stammdaten.

    **Der Satz reist als Schlüssel, mit Zahl und Name daneben**: seit *Export* und
    *Reverse Charge* zwei Katalogzeilen sind, ist «0.00» mehrdeutig – und eine Anzeige,
    die «normal %» schreibt, weil sie den Schlüssel für eine Zahl hält, ist genau der
    Fehler, den eine zweite Auflösung im Browser produziert.

    Eine Abfrage für alle Zeilen, nicht eine je Zeile.
    """
    rows = lines_of(db, row)
    ids = [ln.article_id for ln in rows if ln.article_id is not None]
    found = {a.id: a for a in db.query(Article).filter(Article.id.in_(ids)).all()} \
        if ids else {}
    frozen = (row.head or {}).get("names") or {}
    delivery, seat = destination(db, row)
    out: list[dict[str, Any]] = []
    for ln in rows:
        art = found.get(ln.article_id) if ln.article_id is not None else None
        service = bool(art.is_service) if art else False
        weight = ln.weight_kg if ln.weight_kg is not None else (
            art.weight_kg if art else None)
        net = vo.line_net({"quantity": ln.quantity, "price": ln.price, "part": ln.part},
                          row.currency)
        out.append({
            # **Die Leistung** (Untertitel) und **Ware oder Dienstleistung** – die eine
            # Angabe am Artikel, aus der Steuersatz und Lieferbedingung folgen.
            "text": ln.text,
            "is_service": service,
            "kind_label": "Dienstleistung" if service else "Ware",
            # **Teilbetrag** – ``None`` heisst Vollbetrag; der Betrag der Zeile ist netto.
            "part": _money(ln.part, row.currency),
            "full": _money(vo.line_net({"quantity": ln.quantity, "price": ln.price},
                                       row.currency) if ln.price is not None else None,
                           row.currency),
            "net": _money(net, row.currency) if ln.price is not None else None,
            "weight_kg": f"{weight:.3f}".rstrip("0").rstrip(".") if weight is not None
            else None,
            # **Was an dieser Position wählbar ist** – die Anschrift entscheidet.
            "vat_choices": list(vo.vat_choices(service=service, delivery_country=delivery,
                                               seat_country=seat)),
            "id": ln.id,
            "article_id": ln.article_id,
            "article_object_id": art.object_id if art else None,
            # **Nach der Zusage der Name von damals** (``_freeze_lines``).
            "article_name": (frozen.get(str(ln.article_id))
                             or (art.name if art else "")),
            "quantity": ln.quantity,
            "hs_code": ln.hs_code or (art.hs_code if art else None) or None,
            "origin_country": (ln.origin_country
                               or (art.origin_country if art else None) or None),
            # ►►► **Ein Betrag verlässt den Dienst in der Stelligkeit seiner Währung**
            # (Testnotiz #931). ◄◄◄ Die Spalte ist `NUMERIC(18, 4)` – gross genug für
            # jede Währung –, und `str()` schreibt ihre volle Skala aus: «30.0000».
            # Das ist keine Anzeigefrage der Oberfläche: dieselbe Zahl steht gleich im
            # Eingabefeld, und wer sie dort liest, tippt vier Nachkommastellen weiter.
            # Gerundet wird darum **hier**, an der einen Stelle, an der ein Betrag das
            # Haus verlässt – und mit der Stelligkeit der Währung, nie fest auf zwei
            # (JPY hat null, KWD drei).
            "price": _money(ln.price, row.currency),
            "vat": vo.assert_vat(ln.vat),
            "vat_rate": str(vo.vat_of(ln.vat)),
            "vat_label": vo.vat_label(ln.vat),
            "vat_note": vo.vat_note(ln.vat),
        })
    return out


# ---------------------------------------------------------------------------
# ►► ANLAGE — mit der Freigabe, idempotent
# ---------------------------------------------------------------------------

def house_currency(db: Session) -> str:
    """**Die Währung des Hauses** – die des Betreibers, tolerant gelesen.

    Gibt es (noch) keinen Betreiber, gilt ``currency.DEFAULT``: ein harter Fehler beim
    Freigeben eines Auftrags wäre die falsche Antwort auf eine fehlende Stammdatenzeile.
    """
    operator = sites.find_operator(db)
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


def _has(side: dict[str, Any], field: str) -> bool:
    """Steht diese Angabe wirklich da? **Leer ist nicht vorhanden.**"""
    if field == "contact":
        return bool(side.get("email") or side.get("phone"))
    return bool(side.get(field))


def gaps(db: Session, row: Voucher, *, action: str,
         party_id: Optional[int] = None) -> list[dict[str, Any]]:
    """►►► **Welche Angaben fehlen, um DIESE Handlung zu tun?** ◄◄◄

    Je Lücke eine Zeile mit dem **Datensatz** (klickbar), dem **Feld** und einem Satz, der
    sagt, **warum dieser Beleg sie braucht**. Was daraus folgt, entscheidet ein Mensch –
    wie bei ``StepNeed``: hingehen und eintragen.

    **Gestaffelt und kumulativ** (``Verb.needs``): ``charge`` verlangt auch, was ``ask``
    und ``agree`` verlangen. Eine Rechnung ohne Adressaten gibt es nicht, nur weil man
    schon zugesagt hat.

    **Zwei Sonderfälle, beide benannt:** die **IBAN** verlangt nur, wer einzieht (auf
    einer Lieferantenrechnung steht *seine* Bankverbindung); die **UID des Empfängers**
    verlangt nur ein Beleg, der *Reverse Charge* trägt – im Inland ist sie nicht
    vorgeschrieben, und ein Pflichtfeld, das meistens leer bleiben darf, ist keines.
    """
    # **Geprüft wird die Partei, um die es GEHT.** Beim Zuschlag steht sie in der
    # Nutzlast, nicht am Beleg – die Zusage prüfte sich sonst gegen eine leere Gegenseite
    # und wäre nie möglich. Und wo noch gar keine feststeht, wird die Gegenseite nicht
    # geprüft: beim Anfragen gibt es sie noch nicht, und der Knopf muss trotzdem da sein.
    look = party_id if party_id is not None else party_of(db, row)
    head = _head_for(db, row, look)
    flow = vo.of(row.direction)
    us, party = ((head["supplier"], head["customer"]) if flow.collects
                 else (head["customer"], head["supplier"]))
    sides = {"us": us, "party": party}
    known = look is not None
    # **Reverse Charge steht an der POSITION** – und nur eine gebuchte Zeile verlangt die
    # Nummer; vor der Zusage gibt es noch nichts, wofür sie zählte.
    reverse = any(ln.vat == "reverse" for ln in lines_of(db, row))
    out: list[dict[str, Any]] = []
    for stage in VERBS[action].needs if action in VERBS else ():
        for side, field, label, why in REQUIRED_FOR[stage]:
            if field == "iban" and not flow.collects:
                continue
            if side == "party" and not known:
                continue
            if field == "uid" and side == "party" and not reverse:
                continue
            if field == "iban":
                # **Die IBAN der Gesellschaft, die den Beleg stellt** – nicht die des
                # Betreibers: überwiesen wird an den Aussteller.
                if getattr(issuer_company(db, row), "iban", None):
                    continue
                out.append(_gap(sides["us"], label, why))
                continue
            if not _has(sides[side], field):
                out.append(_gap(sides[side], label, why))
    return out


def _head_for(db: Session, row: Voucher, party_id: Optional[int]) -> dict[str, Any]:
    """Der Belegkopf, wie er **mit dieser Partei** aussähe – ohne den Beleg zu ändern.

    Dieselbe Ableitung wie ``document_head``; ein zweiter Kopf-Aufbau daneben wäre die
    zweite Wahrheit, die beim nächsten Feld auseinanderläuft.
    """
    return document_head(db, row, won=True, party_id=party_id)


def next_action(db: Session, row: Voucher) -> str:
    """**Welche Handlung steht an dieser Stufe an?** – die, deren Lücken zählen.

    Eine Liste aller Lücken über alle Stufen wäre eine Mängelliste statt einer Auskunft:
    sie nennte Angaben, die erst in drei Schritten gebraucht werden, und niemand wüsste,
    welche gerade im Weg steht.
    """
    return "bill" if row.stage != vo.OFFER else "ask"


def _gap(side: dict[str, Any], label: str, why: str) -> dict[str, Any]:
    """Eine Lücke als Zeile – **wo** sie hingehört, **was** fehlt, **warum**."""
    return {
        "record_object_id": side.get("object_id"),
        "record_label": side.get("name") or side.get("label") or "",
        "field_label": label,
        "why": why,
    }


def where_of(db: Session, row: Voucher) -> tuple[Order, ProcessStep]:
    """Auftrag und Modul eines Belegs – für die Regeln, die nach den Stücken fragen."""
    order = db.query(Order).filter(Order.id == row.order_id).first()
    step = db.query(ProcessStep).filter(ProcessStep.id == row.step_id).first()
    return order, step


#: **Verben, die nur die Geld-Zeilen betreffen** – sie bleiben nach dem Storno, denn eine
#: Anzahlung muss zurückgehen können.
MONEY_VERBS = ("pay", "refund", "reverse", "pay_online", "refund_online")


def can(db: Session, row: Voucher, viewer: Optional[UserProfile]) -> list[str]:
    """►►► **Was darf DIESER Betrachter an DIESEM Beleg tun?** ◄◄◄

    Stufe **mal** Lage **mal** Rolle **mal** Vollständigkeit, an einer Stelle – dieselbe
    Antwort reist mit (``can`` im Embed) und weist in ``assert_allowed`` ab. **Auskunft und
    Tor**, nie zwei Massstäbe.
    """
    flow = vo.of(row.direction)
    out = [k for k, v in VERBS.items() if row.stage in v.stages]
    order, step = where_of(db, row)
    # ►►► **Passen die Stücke nicht mehr, bleibt nur «Stornieren»** – in jeder Stufe. ◄◄◄
    if order is not None and step is not None and units_problem(db, row, order, step):
        out = [a for a in out if a == "revoke"]
    money = balance_of(db, row)
    quotes = quotes_of(db, row)
    billed = is_billed(row)
    drop: set[str] = set()
    if row.stage == vo.OFFER:
        if not quotes:
            drop |= {"revoke", "decline"}
        if not (quotes or parties_on(row)):
            drop.add("unask")
        # **Annehmen geht nur, solange die Offerte gilt** – und nur die aktuelle Fassung.
        if expired(db, row) or changed_since_offer(db, row) \
                or not any(q.state in (vo.QUOTED, vo.CHOSEN) for q in quotes):
            drop.add("agree")
        # **Einen fremden Preis erfasst nur, wo die Gegenpartei ihn nennt.**
        if flow.quoted_by == vo.BY_US or not quotes:
            drop.add("quote")
        # **Fremdwährung nur ins Ausland** – wo wir den Preis nennen.
        if flow.quoted_by == vo.BY_US and not vo.abroad(destination(db, row)[0]):
            drop.add("currency")
    if not billed:
        drop |= {"pay", "pay_online", "writeoff", "tip", "remind", "export", "accept"}
    if deviation(db, row) is None:
        drop.add("accept")
    else:
        # **Bezahlt wird erst nach dem Entscheid über die Abweichung.**
        drop |= {"pay", "pay_online", "writeoff", "tip"}
    if money.open <= vo.SETTLED_TOLERANCE:
        drop |= {"pay", "pay_online", "writeoff"}
    if money.open >= -vo.SETTLED_TOLERANCE:
        drop |= {"refund", "tip"}
    if not (flow.collects and not minus(row)):
        drop.add("tip")
    if row.stage == vo.CANCELLED:
        drop |= {"writeoff", "tip", "remind", "export"}
    if next_reminder(db, row) is None or next_reminder(db, row)[1] > date.today():
        drop.add("remind")
    if not (billed and is_export(db, row) and not row.export_number):
        drop.add("export")
    if not reversible(db, row):
        drop.add("reverse")
    if not papers_due(db, row):
        drop.add("release")
    # ►►► **Online bezahlen**: nur wo das Geld **zu uns** fliesst, mit eingerichtetem
    # Dienst und offenem Betrag. **Zurück auf die Karte** nur, wo eine Karten-Zahlung
    # dasteht, die man zurückgeben kann.
    if not (inbound(row) and payment_service_ready()):
        drop.add("pay_online")
    # **Wer schuldet zurück?** An einer Gutschrift ist ihr offener Betrag, was wir
    # erstatten; an einer Rechnung das Zuviel.
    owe_back = (money.open > vo.SETTLED_TOLERANCE if minus(row)
                else money.open < -vo.SETTLED_TOLERANCE)
    if not (owe_back and payment_service_ready() and refundable(db, row)):
        drop.add("refund_online")
    out = [a for a in out if a not in drop]
    if viewer is not None and viewer.role not in STAFF_ROLES:
        # Die Gegenpartei darf nur, was ihre Rolle im Beleg hergibt – und nur, solange sie
        # tatsächlich angefragt ist.
        if not any(q.party_id == viewer.object_id for q in quotes):
            return []
        return [a for a in out if VERBS[a].allows(flow)]
    # ►►► **Was Angaben braucht, die es nicht gibt, steht hier nicht.** ◄◄◄ Die Lücken
    # speisen ``can`` – die Vollständigkeit ist damit **keine zweite Regel**.
    return [a for a in out if not (VERBS[a].needs and gaps(db, row, action=a))]


def reversible(db: Session, row: Voucher) -> list[VoucherEntry]:
    """►►► **Welche Geld-Zeilen sich als «falsch erfasst» gegenbuchen lassen.** ◄◄◄ Von Hand
    erfasste (eine Karten-Zeile meldet der Dienst – sie geht über «zurück auf die Karte»),
    die nicht selbst eine Gegenbuchung sind und noch nicht gegengebucht wurden."""
    rows = entries_of(db, row)
    undone = {e.reverses_id for e in rows if e.reverses_id is not None}
    return [e for e in rows if e.reverses_id is None and e.id not in undone
            and e.method != vo.CARD]


def assert_allowed(db: Session, row: Voucher, action: str,
                   viewer: Optional[UserProfile],
                   party_id: Optional[int] = None) -> None:
    """►►► **Das Tor zu ``can`` – zwei Formen einer Regel, ein Namensstamm.** ◄◄◄

    Sie liest **dieselbe** Liste: ein zweiter, milderer Massstab wäre ein Knopf, der
    bereitsteht und dann scheitert, oder eine Tür, die etwas durchlässt, das niemand
    anbietet. Öffentlich, weil nicht jedes Verb durch ``apply`` läuft.
    """
    if action in can(db, row, viewer):
        return
    # **«Geht nicht» ohne «woran es liegt» ist eine Sackgasse mit Ausrufezeichen.** Es gibt
    # zwei Gründe, und sie verlangen verschiedene Handlungen: die **Stufe** (zu früh oder
    # zu spät) und eine **fehlende Angabe** (hingehen und eintragen).
    missing = (gaps(db, row, action=action, party_id=party_id)
               if action in VERBS and VERBS[action].needs else [])
    if missing:
        first = missing[0]
        raise HTTPException(
            status_code=400,
            detail=(f"Dafür fehlt {first['field_label']} bei «{first['record_label']}». "
                    f"{first['why']}"
                    + (f" (und {len(missing) - 1} weitere Angabe"
                       f"{'n' if len(missing) > 2 else ''})" if len(missing) > 1 else "")),
        )
    flow = vo.of(row.direction)
    # ►►► **Und der Satz nennt den RICHTIGEN Grund** (gemessen bei #1057). ◄◄◄ Er sprach
    # immer von der Stufe – auch dort, wo sie stimmte und allein der **Zugang** fehlte: ein
    # Lieferant, der die Währung ändern wollte, las «geht hier nicht: der Beleg steht auf
    # ‹Anfrage›», und genau dort stand er ja. Eine Begründung, die nicht stimmt, schickt
    # jemanden in die falsche Richtung.
    if (action in VERBS and not VERBS[action].allows(flow)
            and viewer is not None and viewer.role not in STAFF_ROLES):
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» ist an diesem Beleg nicht Ihre Handlung – darüber "
                    f"entscheidet die andere Seite."),
        )
    raise HTTPException(
        status_code=409,
        detail=(f"«{action}» geht hier nicht: der Beleg steht auf "
                f"«{flow.label_of(row.stage)}»."),
    )


# ---------------------------------------------------------------------------
# ►► DIE HANDLUNGEN
# ---------------------------------------------------------------------------

def apply(db: Session, *, order: Order, step: ProcessStep, action: str,
          payload: dict[str, Any], actor: Optional[UserProfile] = None) -> Voucher:
    """**Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle.

    Danach räumt der Beleg selbst nach (``_after``): ein Dokument geht hinaus, wo die
    Partei eine neue Stufe zu sehen bekommt, und die Stücke ziehen weiter, sobald sie
    dürfen. Beides ist keine Handlung, die jemand vergessen könnte.
    """
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404,
                            detail="Zu diesem Modul gibt es keinen Beleg.")
    if action not in VERBS:
        raise HTTPException(status_code=400,
                            detail=f"«{action}» ist keine Handlung an einem Beleg.")
    # **Die Nutzlast weiss, um wen es geht** – beim Zuschlag steht die Gegenpartei dort,
    # und die Vollständigkeitsprüfung muss sie kennen, bevor ``_agree`` sie setzt.
    assert_allowed(db, row, action, actor, _int(payload.get("party")))
    run = VERBS[action].run
    if run is None:
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» ändert den Beleg nicht – diese Handlung hat ihren "
                    f"eigenen Weg."))
    run(db, order=order, step=step, row=row, data=payload, actor=actor)
    db.flush()
    _after(db, order=order, step=step, row=row, actor=actor)
    return row


def _after(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
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


def _fixed(step: ProcessStep) -> dict[str, Any]:
    """**Was die Moduldefinition vorgibt** – es steht im Beleg fest (``Beleg.presets``)."""
    return modules.Beleg.presets_of(step.config)


def _reject_fixed(step: ProcessStep, data: dict[str, Any]) -> None:
    """Eine Vorgabe des Moduls ändert man am Modul, nicht am Beleg."""
    fixed = _fixed(step)
    for key in data:
        if key in fixed and data[key] != fixed[key]:
            raise HTTPException(
                status_code=409,
                detail=(f"«{modules.Beleg.PRESET_LABELS.get(key, key)}» gibt das Modul vor – "
                        f"geändert wird es dort, für jeden künftigen Auftrag."))


def _currency(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**In welcher Währung wird gehandelt?** – eine je Beleg, nicht je Zeile.

    **Umgerechnet wird nichts** – den Kurs braucht erst die Buchhaltung. Eine Fremdwährung
    gibt es, wo wir den Preis nennen, nur mit einer Lieferadresse im Ausland (``can``).
    """
    try:
        row.currency = cur.assert_code(data.get("currency"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _issuer(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Wer stellt diesen Beleg?** – nur eine unserer Gesellschaften."""
    value = _int(data.get("issuer"))
    if value is not None:
        sites.require_own(db, value)
    row.issuer_company_id = value


def _incoterm(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferbedingung** – nur die Klausel. **Der Ort ist kein Feld**: er folgt aus
    der Klausel und den Anschriften (``incoterm_place_of``)."""
    _reject_fixed(step, {"incoterm": data.get("incoterm")})
    try:
        row.incoterm = inc.assert_incoterm(data.get("incoterm"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    row.incoterm_place = None


def _terms(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Fristen und die Gültigkeit** – sofort geschrieben, geprüft erst beim
    Hinausgehen. Nur gesendete Felder wirken; was das Modul vorgibt, steht fest."""
    _reject_fixed(step, {k: data[k] for k in ("payment_days", "lead_days", "valid_days")
                         if k in data})
    if "payment_days" in data:
        row.payment_days = _days(data.get("payment_days"))
    if "lead_days" in data:
        row.lead_days = _days(data.get("lead_days"))
    if "valid_days" in data:
        days = _days(data.get("valid_days"))
        if days == 0:
            raise HTTPException(status_code=400,
                                detail="Eine Offerte gilt mindestens einen Tag.")
        row.valid_days = days


def _add_party(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
               data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Die Gegenpartei WÄHLEN** – wählen ist nicht anbieten (Testnotiz #1000). ◄◄◄

    Festgehalten wird nur, wen der Beleg betrifft; hinaus geht er erst mit «Anbieten».
    Geprüft wird die Wahl selbst (``_party``). Doppelt gewählt ist einmal gewählt.
    """
    flow = vo.of(row.direction)
    number = _party(db, step=step, value=data.get("party"), flow=flow)
    if number is None:
        raise HTTPException(
            status_code=400,
            detail=f"Ohne Objektnummer gibt es keinen {vo.PARTY}, den man wählen könnte.")
    if number not in parties_on(row):
        row.parties = [*parties_on(row), number]
    db.flush()


def _address(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **An wen und wohin** – geschäftlich oder privat, Rechnungs- und Lieferadresse. ◄◄◄

    Aus dem Adressbuch **des Adressaten**, vorbelegt mit seinen Standards. Nur gesendete
    Felder wirken, ``null`` heisst «die Vorgabe». Eine fremde Anschrift wird abgewiesen.
    """
    number = addressee_of(db, row)
    u = (db.query(UserProfile).filter(UserProfile.object_id == number).first()
         if number is not None else None)
    if u is None:
        raise HTTPException(status_code=400, detail=(
            f"An wen der Beleg geht, steht noch nicht fest – gewählt wird, sobald genau "
            f"ein {vo.PARTY} dasteht."))
    if "bill_to_company" in data:
        wanted = data.get("bill_to_company")
        if wanted and not business_possible(u):
            raise HTTPException(status_code=400, detail=(
                f"«{u.display_name}» handelt hier privat – eine eigene Gesellschaft ist nie "
                f"Gegenpartei, und ohne Firma gibt es kein Geschäftskonto."))
        if wanted != row.bill_to_company:
            # **Ein anderes Konto, andere Anschriften** – es gelten die Standards des neuen.
            row.billing_address_id = None
            row.delivery_address_id = None
        row.bill_to_company = wanted
    account = account_for(u, row)
    for key, col, kind in (("billing_address", "billing_address_id", "billing"),
                           ("delivery_address", "delivery_address_id", "delivery")):
        if key not in data:
            continue
        aid = _int(data.get(key))
        hit = address_book.pick(db, u.id, aid, kind, account) if aid is not None else None
        if aid is not None and (hit is None or hit.id != aid):
            raise HTTPException(status_code=400, detail=(
                f"Anschrift {aid} steht nicht im "
                f"{'Geschäftskonto' if account == address_book.BUSINESS else 'Privatkonto'} "
                f"von «{u.display_name}»."))
        setattr(row, col, aid)
    _fit(db, row, lines_of(db, row))


def _ownership(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
               data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Wem die Stücke danach gehören** – frei wählbar bis zur Zusage, keine
    Prüfung: eine Angabe des Menschen, die im Log steht, wenn die Stücke passieren. ◄◄◄"""
    _reject_fixed(step, {"ownership": data.get("ownership")})
    try:
        row.ownership = vo.assert_ownership(data.get("ownership"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _price(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Die Positionen schreiben — gespeichert, nicht abgeschickt.** ◄◄◄

    **Die Menge kommt nie aus der Nutzlast** – sie ist die Zahl der Einzelinstanzen.
    **Preis, Satz und Teilbetrag nur, wo WIR den Preis nennen**; die Leistung und die
    Zoll-Angaben in beiden Richtungen – sie beschreiben die Sache, nicht das Angebot.
    **Der Satz ist eine Folge der Anschrift**: angeboten wird nur, was dort gilt.
    """
    flow = vo.of(row.direction)
    rows = {ln.id: ln for ln in sync_lines(db, row, order, step)}
    delivery, seat = destination(db, row)
    kinds = services_of(db, list(rows.values()))
    for raw in data.get("lines") or []:
        found = rows.get(_int(raw.get("id")))
        if found is None:
            continue
        if flow.quoted_by == vo.BY_US:
            if "price" in raw:
                found.price = _amount(raw.get("price"), row.currency, allow_negative=True)
            if "part" in raw:
                found.part = _amount(raw.get("part"), row.currency)
            if "vat" in raw:
                try:
                    key = vo.assert_vat(raw.get("vat") or vo.DEFAULT_VAT)
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                allowed = vo.vat_choices(service=kinds.get(found.article_id or 0, False),
                                         delivery_country=delivery, seat_country=seat)
                if key not in allowed:
                    raise HTTPException(status_code=400, detail=(
                        f"«{vo.vat_label(key)}» gilt hier nicht – die Anschrift lässt "
                        + ", ".join(vo.vat_label(k) for k in allowed) + " zu."))
                found.vat = key
        if "text" in raw:
            found.text = _text(raw.get("text"), 300)
        if "hs_code" in raw:
            found.hs_code = _text(raw.get("hs_code"), 12)
        if "origin_country" in raw:
            found.origin_country = _text(raw.get("origin_country"), 60)
        if "weight_kg" in raw:
            found.weight_kg = _weight(raw.get("weight_kg"))
    db.flush()


def _ask(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Anbieten bzw. anfragen – und «Erneut anbieten» ist dieselbe Handlung.** ◄◄◄

    **Ohne Angabe sind es alle zugelassenen**, sonst wen der Beleg trägt. Wer abgesagt hat,
    wird nicht wieder angeschrieben.

    **Wer den Preis nennt, schickt ihn mit**: bei einer Einnahme ist der Betrag die
    Brutto-Summe der Positionen, und die Fristen kommen vom Beleg. Ein erneutes Anbieten
    erneuert Betrag, Fristen und Datum – die Frist der Gültigkeit beginnt neu, und die
    vorige Fassung ist überholt.

    **Mit dem ersten Hinausgehen frieren die Stücke ein** (``unit_ids``): ab hier spricht
    der Beleg über genau diese.
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    allowed = modules.Beleg.parties_allowed(step.config)
    wanted = list(data.get("parties") or []) or allowed or parties_on(row)
    _assert_ask(db, row, step, wanted)
    if row.unit_ids is None:
        row.unit_ids = sorted(
            int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
                OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None)).all())
    lead, days = row.lead_days, row.payment_days
    priced = priced_dicts(db, row) if flow.quoted_by == vo.BY_US else []
    amount = vo.gross_of(priced, row.currency) if priced else None
    existing = {q.party_id: q for q in quotes_of(db, row)}
    sent: list[int] = []
    for value in wanted:
        number = _party(db, step=step, value=value, flow=flow)
        if number is None or number in sent:
            continue
        q = existing.get(number)
        if q is not None and q.state == vo.DECLINED:
            continue
        if q is None:
            q = VoucherQuote(voucher_id=row.id, party_id=number)
            db.add(q)
        elif flow.quoted_by != vo.BY_US:
            continue
        q.state = vo.QUOTED if priced else vo.ASKED
        q.amount = amount
        q.lead_days, q.payment_days = lead, days
        q.sent_on = date.today()
        sent.append(number)
    db.flush()
    if flow.quoted_by == vo.BY_US:
        row.offered_hash = fingerprint(db, row)
        if flow.collects:
            for number in sent:
                voucher_docs.issue(db, row=row, kind=vo.OFFER_DOC, actor=actor,
                                   party_id=number)


def _quote(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Offerte der Gegenpartei erfassen** – Betrag, Fristen, ihre Referenz (bei
    einem Online-Kauf die Bestellnummer) und der Link zur Bestellung. Eine Gegenpartei trifft
    ausschliesslich ihre eigene Zeile."""
    line = _target(db, row, data, actor)
    if "amount" in data:
        line.amount = _amount(data.get("amount"), row.currency)
    if "lead_days" in data:
        line.lead_days = _days(data.get("lead_days"))
    if "payment_days" in data:
        line.payment_days = _days(data.get("payment_days"))
    if "reference" in data:
        line.reference = _text(data.get("reference"), 120)
    if "link" in data:
        line.link = _text(data.get("link"), 500)
    if line.amount is None:
        raise HTTPException(status_code=400,
                            detail="Ohne Betrag ist es keine Offerte.")
    _assert_terms(line.lead_days, line.payment_days)
    line.state = vo.QUOTED
    line.sent_on = line.sent_on or date.today()


def _decline(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine Angebotszeile **absagen** – in beide Richtungen dasselbe. Abgesagt ist
    abgesagt: der Preis fällt mit ihr weg."""
    line = _target(db, row, data, actor)
    line.state = vo.DECLINED
    line.amount = None
    line.lead_days = None
    line.payment_days = None


def _agree(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Den Zuschlag geben** – ab hier ist eine zweite Partei gebunden. ◄◄◄

    Die gewählte Zeile geht auf ``gewaehlt``, und damit steht alles fest. **Bei einer
    Einnahme gilt, was angeboten wurde** – der Betrag der Zeile, nicht eine neue Rechnung
    (ein geänderter Beleg muss zuerst erneut angeboten werden, ``can``). Bei einer
    **Ausgabe** darf die Nutzlast nachverhandeln.

    Der Belegkopf friert ein, der Ort der Lieferbedingung auch; danach ziehen die Stücke
    von selbst weiter (``_after``), und die Auftragsbestätigung geht hinaus.
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    number = _party(db, step=step, value=data.get("party"), flow=flow)
    if number is None:
        raise HTTPException(status_code=400,
                            detail=f"Ohne {vo.PARTY} gibt es keine Zusage.")
    line = next((q for q in quotes_of(db, row) if q.party_id == number), None)
    if line is None:
        raise HTTPException(
            status_code=400,
            detail=(f"{vo.PARTY} {number} ist hier nicht angefragt – zugesagt wird an "
                    f"einer Zeile des Angebotsspiegels."))
    if line.state == vo.DECLINED:
        raise HTTPException(
            status_code=409,
            detail=(f"{vo.PARTY} {number} hat abgesagt. Wer doch will, bekommt zuerst "
                    f"wieder ein Angebot."))
    if flow.quoted_by != vo.BY_US:
        if "amount" in data:
            line.amount = _amount(data.get("amount"), row.currency)
        if "lead_days" in data:
            line.lead_days = _days(data.get("lead_days"))
        if "payment_days" in data:
            line.payment_days = _days(data.get("payment_days"))
    if line.amount is None:
        raise HTTPException(status_code=400,
                            detail="Ohne Betrag gibt es keine Zusage.")
    _assert_terms(line.lead_days, line.payment_days)
    _assert_ownership_chosen(row)
    if row.unit_ids is None:
        row.unit_ids = sorted(
            int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
                OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None)).all())
    for other in quotes_of(db, row):
        if other.id != line.id and other.state == vo.CHOSEN:
            other.state = vo.QUOTED
    # **Der Kopf friert ein – VOR dem Stufenwechsel gelesen**, damit ``billing_of`` noch
    # ableitet statt eine leere Kopie zurückzugeben.
    row.head = freeze(db, row, number)
    line.state = vo.CHOSEN
    row.incoterm_place = incoterm_place_of(db, row)
    row.stage = vo.AGREED
    row.agreed_on = date.today()
    db.flush()
    if vo.CONFIRM_DOC in AUTO_RELEASE and vo.CONFIRM_DOC in papers_due(db, row):
        voucher_docs.issue(db, row=row, kind=vo.CONFIRM_DOC, actor=actor)


def _unask(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Eine Anfrage zurückziehen bzw. eine Wahl zurücknehmen** (#951, #1000). ◄◄◄

    Dieselbe Handlung für beide Fälle: *diesen Partner von diesem Beleg wegnehmen*.
    Soft-Delete wie überall; nur vor der Zusage.
    """
    number = _int(data.get("party"))
    if number is not None and number in parties_on(row):
        row.parties = [n for n in parties_on(row) if n != number]
        for q in quotes_of(db, row):
            if q.party_id == number:
                q.is_active = False
        db.flush()
        return
    _target(db, row, data, actor).is_active = False
    db.flush()


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
        row.credit_number = _our_number(db, order)
    seen = flow.collects and bool(documents_of(db, row))
    row.stage = vo.CANCELLED
    row.cancelled_on = date.today()
    db.flush()
    if seen:
        voucher_docs.issue(db, row=row, kind=vo.CREDIT_DOC if billed else vo.STORNO_DOC,
                           actor=actor)


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
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne Preis gibt es nichts zu berechnen – bei einer "
                        f"{flow.label} nennen wir ihn."))
        gross = vo.gross_of(priced, row.currency)
        split = vo.split_for(gross, priced, row.currency)
    else:
        gross = _amount(data.get("amount"), row.currency) or agreed_amount(db, row)
        if gross is None:
            raise HTTPException(status_code=400, detail="Ohne Betrag ist es keine Rechnung.")
        try:
            split = vo.split_at(gross, data.get("vat") or vo.DEFAULT_VAT, row.currency)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        _record_original(db, row, data, split)
    if gross == 0:
        raise HTTPException(status_code=400,
                            detail="Eine Rechnung über null ist keine.")
    if flow.reference is not None and not row.number:
        number = _text(data.get("reference"), 120)
        if not number:
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne {flow.reference} lässt sich diese Rechnung nicht "
                        f"zuordnen – sie steht auf seinem Papier."))
        row.number = number
    elif not row.number:
        row.number = _our_number(db, order)
    booked = _day(data.get("billed_on")) or date.today()
    row.billed_on = booked
    row.due_on = _due(booked, due_days_of(db, row))
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
    original = _module_document(db, row, data, "voucher.original", (
        "Ohne die Rechnung als Dokument geht es nicht – sie ist der Beleg, aufbewahrt zehn "
        "Jahre."))
    taxed = any(Decimal(r.get("tax") or "0") != 0 for r in split)
    uid = _text(data.get("party_uid"), 40)
    if taxed and not uid:
        raise HTTPException(status_code=400, detail=(
            "Ohne MWST-Nummer des Lieferanten gibt es keinen Vorsteuerabzug "
            "(MWSTG Art. 28) – sie steht auf seiner Rechnung."))
    row.original_id = original
    row.party_uid = uid


def _accept(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferantenrechnung so annehmen, wie sie ist** – mit Grund. Die Differenz
    bleibt als Zeile stehen; jetzt wird bezahlt."""
    note = _text(data.get("note"), 200)
    if not note:
        raise HTTPException(status_code=400, detail=(
            "Eine Abweichung nimmt man mit Grund an – er bleibt als Nachweis stehen."))
    row.deviation_note = note


def _correct(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Welchen Beleg mindert dieser hier?** ◄◄◄ Der Verweis darf über Auftragsgrenzen
    zeigen – die Gutschrift gehört dorthin, wo die Ware zurückkommt. Drei Ablehnungen: sich
    selbst · keine Rechnung · ein Kreis."""
    value = _int(data.get("corrects"))
    if value is None:
        row.corrects_id = None
        return
    target = db.query(Voucher).filter(Voucher.id == value,
                                      Voucher.is_active.is_(True)).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Diesen Beleg gibt es nicht.")
    if target.id == row.id:
        raise HTTPException(status_code=400, detail="Ein Beleg korrigiert nicht sich selbst.")
    if not is_billed(target):
        raise HTTPException(
            status_code=400,
            detail=("Dieser Beleg trägt noch keine Rechnung – es gibt nichts zu "
                    "korrigieren."))
    if target.direction != row.direction:
        raise HTTPException(
            status_code=400,
            detail=(f"Eine {vo.of(row.direction).label} korrigiert keine "
                    f"{vo.of(target.direction).label}: das Geld flösse in die andere "
                    f"Richtung."))
    seen = {row.id}
    walk: Optional[Voucher] = target
    while walk is not None:
        if walk.id in seen:
            raise HTTPException(
                status_code=400,
                detail=(f"«{walk.number or walk.id}» führt im Kreis zurück auf diesen "
                        f"Beleg – eine Kette aus Korrekturen muss irgendwo enden."))
        seen.add(walk.id)
        walk = corrects(db, walk)
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
    """**Die eine Stelle, an der eine Geld-Zeile entsteht** (von Hand). Eine Referenz
    gehört zu genau einer Zahlung – zweimal dieselbe ist ein Irrtum mit Namen."""
    data = data or {}
    reference = _text(data.get("reference"), 120)
    if reference and db.query(VoucherEntry).filter(
            VoucherEntry.reference == reference, VoucherEntry.is_active.is_(True)).first():
        raise HTTPException(status_code=409, detail=(
            f"Die Referenz «{reference}» ist schon gebucht – zweimal dieselbe Zahlung gibt "
            f"es nicht."))
    entry = VoucherEntry(
        voucher_id=row.id, amount=amount, kind=kind,
        booked_on=_day(data.get("booked_on")) or date.today(),
        reference=reference,
        note=_text(data.get("note"), 200), method=method, reason=reason,
        reverses_id=reverses, iban=_iban(data.get("iban")),
    )
    db.add(entry)
    db.flush()
    return entry


def _method(row: Voucher, value: Any) -> Optional[str]:
    """**Wie bezahlt wurde** – von Hand bar oder per Überweisung; **mit Karte nur, wo WIR
    zahlen** (die Firmenkarte). Eine Karte, die uns bezahlt, meldet der Zahlungsdienst."""
    try:
        return vo.assert_method(value, card=not inbound(row))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _pay(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Zahlung erfassen** – vorbelegt mit dem Offenen. Positiv: wer überzahlt, tut
    das mit einem grösseren Betrag; zurück geht es mit «Erstatten»."""
    given = _amount(data.get("amount"), row.currency)
    value = given if given is not None else balance_of(db, row).next_payment
    if value is None or value <= 0:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Zahlung.")
    method = _method(row, data.get("method"))
    # **Eine Erstattung per Überweisung braucht das Konto, wohin** – es kommt über den
    # gewöhnlichen Verlauf und wird hier eingetragen (keine Anfrage, kein Formular).
    if minus(row) and method == vo.TRANSFER and not _iban(data.get("iban")):
        raise HTTPException(status_code=400, detail=(
            "Zuerst die IBAN eintragen – wohin die Erstattung geht."))
    _entry(db, row, amount=value, data=data, method=method)


def _refund(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Erstatten** – das Geld geht dorthin zurück, woher es kam (bar, an die IBAN).
    Vorbelegt mit dem, was zu viel ist. Auf die Karte geht es über den Zahlungsdienst."""
    owed = -balance_of(db, row).open
    given = _amount(data.get("amount"), row.currency)
    value = given if given is not None else owed
    if value is None or value <= 0:
        raise HTTPException(status_code=400, detail="Hier ist nichts zu erstatten.")
    method = _method(row, data.get("method"))
    if method == vo.TRANSFER and not _iban(data.get("iban")):
        raise HTTPException(status_code=400, detail=(
            "Eine Überweisung braucht die IBAN – sie kommt über den gewöhnlichen Verlauf "
            "und wird hier eingetragen."))
    _entry(db, row, amount=-value, data=data, method=method)


def _writeoff(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Ausbuchen** – der Rest, mit Grund. Rechtlich immer eine Entgeltsminderung:
    Netto und MWST werden anteilig korrigiert (MWSTG Art. 41). Kein Geld fliesst. ◄◄◄"""
    try:
        reason = vo.assert_reason(data.get("reason"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _entry(db, row, amount=balance_of(db, row).open, kind=vo.WRITEOFF, data=data,
           reason=reason)


def _tip(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Als Trinkgeld behalten** – was zu viel kam, bleibt bei der Firma: es ist
    Entgelt, mit MWST zum Satz der Rechnung (MWSTG Art. 24). ◄◄◄"""
    _entry(db, row, amount=-balance_of(db, row).open, kind=vo.TIP, data=data)


def _reverse(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**«Falsch erfasst?»** – die Gegenbuchung genau dieser Zeile, für einen Tippfehler.
    Gelöscht wird nichts; beide Zeilen bleiben stehen."""
    wanted = _int(data.get("entry"))
    found = next((e for e in reversible(db, row) if e.id == wanted), None)
    if found is None:
        raise HTTPException(status_code=409, detail=(
            "Diese Zeile lässt sich nicht gegenbuchen – sie ist schon gegengebucht, ist "
            "selbst eine Gegenbuchung oder kam vom Zahlungsdienst."))
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
        raise HTTPException(status_code=409, detail="Hier ist keine Mahnung fällig.")
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
        raise HTTPException(status_code=400, detail=message)
    photo = _module_document(db, row, data, "voucher.export", message)
    row.export_number, row.export_photo_id = number, photo


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


def _release(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Ein anstehendes Papier freigeben** – es entsteht und geht hinaus (``voucher_docs``)."""
    from . import voucher_docs
    kind = _text(data.get("kind"), 16)
    if kind not in papers_due(db, row):
        raise HTTPException(status_code=409, detail=(
            f"«{vo.DOCUMENTS.get(kind or '', kind or '–')}» steht hier nicht an."))
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
        raise HTTPException(status_code=400, detail=message)
    documents.set_field(db, document_object_id=doc.object_id, object_id=order.object_id,
                        part=part, field=field, actor=None)
    return doc.object_id


def _weight(value: Any) -> Optional[Decimal]:
    """Ein Gewicht in kg – oder ``None``. Nie negativ."""
    if value in (None, ""):
        return None
    try:
        found = Decimal(str(value).strip().replace("'", "").replace(",", "."))
    except Exception:
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Gewicht.")
    if found < 0 or found > Decimal("999999"):
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Gewicht.")
    return found.quantize(Decimal("0.001"))


def _iban(value: Any) -> Optional[str]:
    """Eine IBAN in Normalform (ohne Leerzeichen, gross) – oder ``None``."""
    text = "".join(str(value or "").split()).upper()
    if not text:
        return None
    if not (15 <= len(text) <= 34 and text[:2].isalpha() and text[2:4].isdigit()):
        raise HTTPException(status_code=400, detail=f"«{value}» ist keine IBAN.")
    return text


#: ►►► **DIE EINE TABELLE.** ◄◄◄ Wer ein Verb hinzufügt, schreibt eine Zeile und hat damit
#: Stufe, Stammdaten, Zugang und Wirkung erklärt. Die Lage (abgelaufen, Stücke weg,
#: überzahlt …) prüft ``can`` – an derselben Stelle für Knopf und Tür.
VERBS: dict[str, Verb] = {
    # **Vor der Zusage** – hier wird der Beleg geschrieben. Die Währung gehört dem, der
    # den Preis nennt (Testnotiz #1057).
    "currency": Verb(stages=(vo.OFFER,), run=_currency, party=IF_THEY_PRICE),
    "issuer": Verb(stages=(vo.OFFER,), run=_issuer),
    "incoterm": Verb(stages=(vo.OFFER,), run=_incoterm),
    "terms": Verb(stages=(vo.OFFER,), run=_terms),
    "price": Verb(stages=(vo.OFFER,), run=_price),
    "party": Verb(stages=(vo.OFFER,), run=_add_party),
    "address": Verb(stages=(vo.OFFER,), run=_address),
    "ownership": Verb(stages=(vo.OFFER,), run=_ownership),
    "correct": Verb(stages=(vo.OFFER,), run=_correct),
    "ask": Verb(stages=(vo.OFFER,), run=_ask, needs=("ask",)),
    "unask": Verb(stages=(vo.OFFER,), run=_unask),
    "quote": Verb(stages=(vo.OFFER,), run=_quote, needs=("ask",), party=IF_THEY_PRICE),
    "decline": Verb(stages=(vo.OFFER,), run=_decline, party=ALWAYS),
    "agree": Verb(stages=(vo.OFFER,), run=_agree, needs=("ask", "agree"),
                  party=IF_WE_PRICE),
    # **Stornieren** – ein Wort in jeder Stufe (vor der Zusage erst, wenn etwas
    # hinausging, ``can``).
    "revoke": Verb(stages=(vo.OFFER, vo.AGREED, vo.BILLED), run=_revoke),
    # **DIE Rechnung** – eine Schwelle von ``agreed`` nach ``billed``.
    "bill": Verb(stages=(vo.AGREED,), run=_bill, needs=("ask", "agree", "bill")),
    "accept": Verb(stages=(vo.BILLED,), run=_accept),
    # **Das Geld** – auch nach dem Storno muss es zurückgehen können.
    "pay": Verb(stages=(vo.BILLED,), run=_pay),
    "refund": Verb(stages=(vo.BILLED, vo.CANCELLED), run=_refund),
    "writeoff": Verb(stages=(vo.BILLED,), run=_writeoff),
    "tip": Verb(stages=(vo.BILLED,), run=_tip),
    "reverse": Verb(stages=(vo.BILLED, vo.CANCELLED), run=_reverse),
    "remind": Verb(stages=(vo.BILLED,), run=_remind),
    "export": Verb(stages=(vo.BILLED,), run=_export),
    # **Ein anstehendes Papier freigeben** (Auftragsbestätigung, Quittung – ``papers_due``).
    "release": Verb(stages=(vo.AGREED, vo.BILLED), run=_release),
    # ``run=None``: **sie ändern den Beleg nicht.** Gebucht wird erst, wenn der
    # Zahlungsdienst es meldet. Eigener Weg, **dieselbe Tür** (``assert_allowed``).
    "pay_online": Verb(stages=(vo.BILLED,), party=ALWAYS),
    "refund_online": Verb(stages=(vo.BILLED, vo.CANCELLED)),
}


def _target(db: Session, row: Voucher, data: dict[str, Any],
            actor: Optional[UserProfile]) -> VoucherQuote:
    """**Welche Angebotszeile ist gemeint?**

    Eine **Gegenpartei** trifft ausschliesslich ihre eigene – gelesen aus dem angemeldeten
    Benutzer, nie aus der Nutzlast: sonst entschiede die Nutzlast, wessen Preis geändert
    wird. Personal nennt die Partei.
    """
    internal = actor is None or actor.role in STAFF_ROLES
    number = _int(data.get("party")) if internal else (
        actor.object_id if actor else None)
    rows = quotes_of(db, row)
    if number is None and internal and len(rows) == 1:
        # Steht genau eine Zeile da, ist sie gemeint – danach zu fragen wäre eine Frage
        # mit genau einer richtigen Antwort.
        return rows[0]
    found = next((q for q in rows if q.party_id == number), None)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail=f"{vo.PARTY} {number} ist an diesem Beleg nicht angefragt.")
    return found


# ---------------------------------------------------------------------------
# ►► DIE ZAHLUNGEN — was auf die eine Rechnung dieses Belegs geflossen ist
# ---------------------------------------------------------------------------
#
# **Keine Zuordnung**: die Rechnung *ist* der Beleg, zu dem die Zahlung gehört. Die
# Aufteilung über mehrere Rechnungen liegt über Modulgrenzen (offene-Posten-Liste,
# ``docs/backlog.md``).

def refunded_on(db: Session, row: Voucher, entry: VoucherEntry) -> Decimal:
    """►►► **Was von DIESER Karten-Zahlung schon zurückgegangen ist.** ◄◄◄

    Gelesen werden die Karten-Zeilen, die der Webhook zu ihr gebucht hat – ihre Referenz
    ist die der Zahlung mit dem Zusatz ``:refund`` (``stripe_pay._refunds``). **Über alle
    Belege**: eine Erstattung aus einer Gutschrift steht an der Gutschrift, nicht an der
    Rechnung, und mindert die Zahlung trotzdem.
    """
    if not entry.reference:
        return Decimal("0")
    mark = f"{entry.reference}:refund"
    rows = (db.query(VoucherEntry)
            .filter(VoucherEntry.is_active.is_(True),
                    (VoucherEntry.reference == mark)
                    | VoucherEntry.reference.like(f"{mark}:%"))
            .all())
    return sum((abs(e.amount) for e in rows), Decimal("0"))


def refundable_amount(db: Session, row: Voucher, entry: VoucherEntry) -> Decimal:
    """**Wie viel von dieser Zahlung noch zurückgegeben werden kann** – nie unter null."""
    rest = entry.amount - refunded_on(db, row, entry)
    return rest if rest > 0 else Decimal("0")


def refundable(db: Session, row: Voucher) -> list[VoucherEntry]:
    """**Die Karten-Zahlungen, die man zurückgeben kann** – jüngste zuerst.

    Nur eine **Karte** (bar und per Überweisung erstattet ein Mensch), nur eine
    **positive**, und nur, solange etwas übrig ist (Testnotiz #1018). ►►► **An einer
    Gutschrift sind es die Karten-Zahlungen der Rechnung, die sie mindert** – das Geld geht
    dorthin zurück, woher es kam. ◄◄◄ Und nur, wo das Geld zu uns kam (``inbound`` der
    Rechnung).
    """
    source = corrects(db, row) if minus(row) else row
    if source is None or not inbound(source):
        return []
    return [e for e in reversed(entries_of(db, source))
            if e.method == vo.CARD and e.amount > 0
            and e.reference and refundable_amount(db, source, e) > 0]


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
    row = (
        db.query(VoucherEntry)
        .filter(VoucherEntry.reference == reference, VoucherEntry.is_active.is_(True))
        .first()
    )
    return (db.query(Voucher).filter(Voucher.id == row.voucher_id).first()
            if row is not None else None)


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

    *Ein ``charge_id`` gab es hier einmal: worauf die Zahlung geht. Die Frage hat genau
    eine Antwort – der Beleg, an dem die Zeile hängt –, und eine Frage mit genau einer
    Antwort stellt man nicht.*
    """
    if reference:
        seen = (
            db.query(VoucherEntry)
            .filter(VoucherEntry.reference == reference,
                    VoucherEntry.is_active.is_(True))
            .first()
        )
        if seen is not None:
            if seen.voucher_id != row.id:
                raise HTTPException(
                    status_code=409,
                    detail=(f"Die Referenz «{reference}» hängt bereits an einem anderen "
                            f"Beleg. Zweimal dieselbe Zahlung gibt es nicht."))
            return seen
    entry = VoucherEntry(
        voucher_id=row.id, amount=amount,
        booked_on=date.today(), reference=reference, note=note, method=method,
    )
    db.add(entry)
    db.flush()
    # **Dasselbe danach wie bei einer erfassten Zahlung** – Quittung, Stücke weiter.
    order, step = where_of(db, row)
    if order is not None and step is not None:
        _after(db, order=order, step=step, row=row, actor=None)
    return entry


def correctable(db: Session, row: Voucher, step: ProcessStep, *,
                search: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """►►► **Welche Rechnungen lassen sich mit diesem Beleg korrigieren?** ◄◄◄

    Gesucht wird über **alle Aufträge** – das ist der Kern dieser Runde: die Gutschrift
    gehört dorthin, wo die Ware zurückkommt, nicht in den Auftrag, der sie geliefert hat.

    Vier Bedingungen, und jede folgt aus der Sache: es muss eine **Rechnung** geben
    (``billed_on``), sie muss in **dieselbe Richtung** zeigen (sonst flösse das Geld
    andersherum), sie darf nicht **selbst** eine Korrektur sein (eine Kette aus
    Korrekturen von Korrekturen ist keine Auskunft mehr) und sie muss **denselben
    Partner** betreffen – man mindert keine fremde Forderung.

    **Gefragt wird nach den MÖGLICHEN Parteien** (``_possible_parties``: zugelassen ∪
    gewählt ∪ angefragt), nicht nach dem Vertragspartner: ein Korrekturbeleg steht in der
    Stufe «Angebot», wenn man ihn zuordnet – dort gibt es noch keine Zusage, und
    ``party_of`` wäre ``None``. Die **Zielbelege** dagegen tragen eine: sie sind gestellt.

    Der Partner eines Ziels ist eine **Ableitung** (die gewählte Angebotszeile), also
    lässt er sich nicht in der Datenbank filtern; gelesen wird darum eine grosszügige
    Seite und danach gefiltert. Bei einer Handvoll Belegen je Partner kostet das nichts.

    ►►► **``search`` sucht die Rechnungsnummer** (Testnotiz #1050). ◄◄◄ Dieselbe Bedingung
    wie jede Referenz-Suche im Haus – ein Teilstring, nicht eine fertige Liste. Gesucht
    wird in der **Datenbank**, nicht nachträglich im Python: sonst filterte man die Seite,
    die man ohnehin schon gekappt hat, und der gesuchte Beleg wäre genau der, der nicht
    mehr darin steht.

    *Eine **Kamera** gibt es dafür nicht: eine Rechnung zieht keine Objektnummer, es kann
    für sie gar kein Etikett geben – dieselbe Regel wie bei der Einzelinstanz.*
    """
    wanted = set(_possible_parties(db, row, step))
    if not wanted:
        return []
    q = (
        db.query(Voucher)
        .filter(Voucher.is_active.is_(True),
                Voucher.direction == row.direction,
                Voucher.billed_on.isnot(None),
                Voucher.corrects_id.is_(None),
                Voucher.id != row.id)
    )
    text = (search or "").strip()
    if text:
        q = q.filter(Voucher.number.ilike(f"%{text}%"))
    rows = q.order_by(Voucher.billed_on.desc(), Voucher.id.desc()).limit(limit * 5).all()
    found = [r for r in rows if party_of(db, r) in wanted][:limit]
    numbers = {
        o.id: o.object_id
        for o in db.query(Order).filter(Order.id.in_([r.order_id for r in found] or [0]))
    }
    return [
        {
            "id": r.id,
            "number": r.number,
            "billed_on": r.billed_on,
            "amount": _money(r.amount, r.currency),
            "currency": r.currency,
            "order_object_id": numbers.get(r.order_id),
        }
        for r in found
    ]


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
    return (f"«{flow.label}» wartet auf die {noun}: {_money(money.paid, row.currency)} "
            f"von {_money(money.agreed, row.currency)} {row.currency} – "
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


# ---------------------------------------------------------------------------
# ►► DER BELEGKOPF — beide Parteien, wie das Gesetz sie nennt
# ---------------------------------------------------------------------------

def issuer_company(db: Session, row: Voucher):
    """**Unsere Seite des Belegs** – die eingefrorene Gesellschaft.

    **Eine Lesestelle**, damit Belegkopf, Lückenprüfung und Einzahlungsschein nicht drei
    Antworten geben. Der **Betreiber** bleibt der Rückfall: ein Beleg ohne Aussteller wäre
    schlimmer als einer mit dem Betreiber.
    """
    return sites.by_object_id(db, row.issuer_company_id) or sites.find_operator(db)


def account_for(u: UserProfile, row: Voucher) -> str:
    """►►► **Aus welchem Konto der Beleg seine Anschriften nimmt.** ◄◄◄

    Wer ein **Geschäftskonto** hat (einer Firma zugeordnet ist), bestellt vorbelegt für
    die Firma – ausser der Beleg sagt «an die Person» (``bill_to_company is False``)."""
    if business_possible(u) and row.bill_to_company is not False:
        return address_book.BUSINESS
    return address_book.PRIVATE


def business_possible(u: UserProfile) -> bool:
    """►►► **Kann diese Person hier geschäftlich handeln?** ◄◄◄ Nur mit einer Firma – und
    **nie für eine unserer eigenen Gesellschaften**: die eigene Gesellschaft kann nie
    Gegenpartei sein, niemand stellt sich selbst eine Rechnung. Ein Mitarbeiter handelt
    hier also privat (Spesen sind kein Sonderfall)."""
    firm = u.company
    return firm is not None and not bool(getattr(firm, "is_own", False))


def billing_of(db: Session, row: Voucher,
               party_id: Optional[int] = None) -> dict[str, Any]:
    """**Was auf dem Beleg über den Leistungsempfänger steht** – Name, Anschriften,
    Kontakt, UID.

    ►►► **Es bestellt immer eine PERSON.** ◄◄◄ Ist sie einer Firma zugeordnet, ist die
    Firma der **Rechnungsempfänger** («Muster AG, z. H. Hans Muster») – ausser der Beleg
    sagt «an die Person» (``row.bill_to_company is False``). Die **Anschriften** kommen
    aus **dem Konto**, an das die Rechnung geht (``account_for``): gewählt am Beleg, sonst
    der Standard des Kontos – eine Firma trägt bei uns keine.

    ►►► **Nach der Zusage ist es eine Kopie, keine Ableitung** (``row.head``). ◄◄◄ Für die
    gebundene Partei kommt zurück, was bei der Bestätigung dastand – zieht jemand um oder
    firmiert um, ändert das keine bestätigte Offerte und keine Rechnung, auch nicht den
    Einzahlungsschein und nicht die Vorbelegung der Bezahlkarte.
    """
    number = party_id if party_id is not None else party_of(db, row)
    frozen = row.head or {}
    if frozen and number in (None, frozen.get("party")):
        return dict(frozen.get("billing") or {})
    empty: dict[str, Any] = {"name": None, "email": None, "address": None}
    if number is None:
        return empty
    u = db.query(UserProfile).filter(UserProfile.object_id == number).first()
    if u is None:
        return empty
    account = account_for(u, row)
    firm = u.company if account == address_book.BUSINESS else None
    billed = address_book.pick(db, u.id, row.billing_address_id, "billing", account)
    shipped = address_book.pick(db, u.id, row.delivery_address_id, "delivery", account)
    return {
        "party": number,
        "name": sites.legal_name(firm) if firm is not None else people.name(u),
        # **Auf dem Beleg steht die Rechtsperson, nicht ihr Vertreter** – Firma zuerst,
        # die Person als «z. H.» darunter (``people.billing_name``).
        "lines": people.billing_name(u, firm=firm is not None),
        # **Die Rechnungs-E-Mail steht an der Rechnungsadresse des Geschäftskontos** –
        # leer, und privat immer, gilt die der Person.
        "email": (billed.email if billed is not None else None) or u.email,
        "phone": u.phone,
        "uid": _uid(firm),
        "address": {
            "line1": billed.street1, "line2": billed.street2, "city": billed.city,
            "postal_code": billed.zip, "country": billed.country,
        } if billed is not None else None,
        "shipping": address_book.lines(shipped),
        # **Wohin die Ware geht, als Ort** – für den Steuersatz (Ausland?) und den Ort der
        # Lieferbedingung. Ohne eigene Lieferadresse ist es die Rechnungsadresse.
        "delivery": _place(shipped or billed),
        # Die Firma, an die verrechnet wird (``None`` = an die Person).
        "company_object_id": getattr(firm, "object_id", None) if firm is not None else None,
        "billing_address_id": billed.id if billed is not None else None,
        "delivery_address_id": shipped.id if shipped is not None else None,
        "bill_to_company": firm is not None,
    }


def _ours(db: Session, row: Voucher) -> dict[str, Any]:
    """**Unsere Seite des Belegkopfs** – live, bis die Zusage sie einfriert."""
    flow = vo.of(row.direction)
    company = issuer_company(db, row)
    seat = address.of_company(company) if company is not None else None
    return {
        "ours": True,
        "object_id": getattr(company, "object_id", None),
        # **Der Name trägt die Rechtsform** – «Inexxio» ist keine Rechtsperson, «Inexxio
        # AG» ist eine, und auf einem Beleg steht die, die haftet.
        "name": sites.legal_name(company),
        # Eine Adresse ohne Ort ist keine: ``of_company`` liefert immer ein Gerüst,
        # ``has_content`` fragt, ob wirklich etwas drinsteht. **Wer liefert, versendet**
        # – daraus folgt die Beschriftung der zweiten Anschrift (#979).
        **_addresses(address.lines(seat) if address.has_content(seat) else [],
                     [], sends=flow.collects),
        "uid": _uid(company),
        "email": getattr(company, "email", None),
        "phone": getattr(company, "phone", None),
        # **Der Sitz als Ort** – woher die Ware abgeht (Lieferbedingung) und ob wir im
        # Inland sind.
        "city": (seat or {}).get("city") or None,
        "ship_city": (seat or {}).get("city") or None,
        "country": (seat or {}).get("country") or None,
    }


def _place(a) -> Optional[dict[str, Any]]:
    """Eine Anschrift aus dem Adressbuch als Ort – Ort, PLZ, Land."""
    if a is None:
        return None
    return {"city": a.city or None, "zip": a.zip or None, "country": a.country or None}


def _uid(company) -> Optional[str]:
    """►►► **Die Nummer einer Firma, wie sie auf dem Beleg steht** – auf BEIDEN Seiten. ◄◄◄

    Die MWST-Nummer zuerst (eine Schweizer heisst «CHE-123.456.789 MWST»), sonst die UID;
    gegliedert über ``domain/uid.display``. Vorher stand unsere Seite roh, die des
    Partners gegliedert und ohne Zusatz – dieselbe Angabe zweimal anders auf einem Papier.
    """
    if company is None:
        return None
    vat = uid_fmt.display(company.vat_number)
    if vat:
        return f"{vat} MWST" if vat.startswith("CHE-") else vat
    return uid_fmt.display(company.uid_number) or None


def _creditor(db: Session, row: Voucher) -> dict[str, Any]:
    """**Wer das Geld bekommt** – Name und Anschrift für den Einzahlungsschein.

    Die Anschrift ist die der Gesellschaft (``address.of_company``, die eine Stelle);
    Strasse und Nummer stehen darin zusammen – wie beim Zahlenden.
    """
    company = issuer_company(db, row)
    seat = address.of_company(company)
    return {
        "name": sites.legal_name(company) or "",
        "street": seat["street1"] if seat["street1"] != address.DASH else None,
        "zip": seat["zip"] or None,
        "city": seat["city"] or None,
        "country": seat["country"],
    }


def freeze(db: Session, row: Voucher, party: int) -> dict[str, Any]:
    """►►► **Der Belegkopf, wie er bei der Bestätigung dasteht** – zum Einfrieren. ◄◄◄

    Beide Parteien (``ours`` · ``billing``) und der Zahlungsempfänger des Einzahlungs-
    scheins (``creditor``). **Nicht** dabei ist die IBAN: sie sagt, wohin *heute* gezahlt
    wird, und ein eingefrorenes altes Konto schickte das Geld an eine geschlossene Bank.
    """
    return {"party": party, "ours": _ours(db, row), "creditor": _creditor(db, row),
            "billing": billing_of(db, row, party), "names": _freeze_lines(db, row)}


def _freeze_lines(db: Session, row: Voucher) -> dict[str, str]:
    """►►► **Auch die Positionen sagen nach der Zusage, was bei ihr dastand.** ◄◄◄

    Artikel und Menge frieren durch die Stufe ein (``sync_lines``), Preis und Satz stehen
    an der Zeile. Zwei Angaben las der Beleg aber **live vom Artikel**: die Zoll-Angaben,
    wo die Zeile keine eigenen trug, und den **Namen**. Ein umbenannter Artikel oder eine
    nachgetragene Zolltarifnummer hätte damit eine bestätigte Offerte geändert. Die
    Zoll-Angaben werden darum in die Zeile geschrieben, der Name in den Kopf (je Artikel).
    """
    names: dict[str, str] = {}
    for ln, shown in zip(lines_of(db, row), embed_lines(db, row)):
        ln.hs_code = shown["hs_code"]
        ln.origin_country = shown["origin_country"]
        if ln.article_id is not None:
            names[str(ln.article_id)] = shown["article_name"]
    db.flush()
    return names


def document_head(db: Session, row: Voucher, *, won: bool,
                  party_id: Optional[int] = None,
                  internal: bool = False) -> dict[str, Any]:
    """►►► **Wer stellt den Beleg, und wer bekommt ihn** (MWSTG Art. 26). ◄◄◄

    Eine Rechnung ist erst eine, wenn sie **beide Seiten** nennt: Name mit Rechtsform, Ort,
    Kontaktweg und die **UID mit dem Zusatz MWST** dessen, der sie stellt – ohne ihn kann
    dem Empfänger der Vorsteuerabzug verweigert werden.

    **Welche Seite welche Rolle hat, sagt die Richtung** – über die Angabe, die es schon
    gibt (``collects``): wo das Geld zu uns fliesst, sind **wir** der Leistungserbringer.
    Ein zweites Feld «wer fakturiert» wäre dieselbe Aussage ein zweites Mal.

    **Was fehlt, wird nicht erfunden**: eine Seite ohne Anschrift trägt eine leere Liste,
    eine ohne UID ``None`` – die Oberfläche sagt dann klein, was fehlt. Eine erfundene
    Zeile wäre auf einem Beleg schlimmer als eine leere.

    **Und die Gegenseite hängt an ``won``** – wie jede andere Angabe über sie: wer nicht
    den Zuschlag hat, sieht **uns** (das steht auf jeder Rechnung, die wir stellen) und
    eine **leere** Gegenseite.

    ►►► **Jede Seite sagt selbst, ob sie unsere ist** (``ours``). ◄◄◄ Welcher der beiden
    Blöcke die **Gegenpartei** ist, wechselt mit der Richtung – die Oberfläche muss das
    aber wissen, um beim Umschalten des Empfängers den richtigen Block zu tauschen. Ein
    Vergleich auf «Leistungserbringer» wäre ein Spiegel über die API-Grenze, der beim
    ersten Umbenennen still falsch wird; ``ours`` **ist** die Struktur.
    """
    flow = vo.of(row.direction)
    # **Der Adressat, nicht der Vertragspartner** (#939): steht genau einer an, ist er es
    # längst – erst die Zusage bindet ihn.
    look = party_id if party_id is not None else addressee_of(db, row)
    # **Nach der Zusage ist unsere Seite eine Kopie** (``freeze``) – wie die Gegenseite.
    ours = dict((row.head or {}).get("ours") or _ours(db, row))
    theirs = their_side(db, row, look if won else None, internal=internal)
    supplier, customer = (ours, theirs) if flow.collects else (theirs, ours)
    return {
        "supplier": {"label": vo.SUPPLIER, "hint": vo.SUPPLIER_HINT,
                     **_labelled(supplier, sends=True)},
        "customer": {"label": vo.CUSTOMER, "hint": vo.CUSTOMER_HINT,
                     **_labelled(customer, sends=False)},
    }


def _labelled(side: dict[str, Any], *, sends: bool) -> dict[str, Any]:
    """**Beschriftungen sind Darstellung, keine Angabe** – eingefroren wird die Anschrift,
    die Beschriftung kommt immer frisch aus ``_addresses`` (sonst trüge ein bestätigter
    Beleg die Wörter von damals)."""
    if not side.get("address"):
        return side
    fresh = _addresses(side["address"], side.get("shipping") or [], sends=sends)
    return {**side, "address_label": fresh["address_label"],
            "shipping_label": fresh["shipping_label"]}


def _addresses(billed: list[str], shipped: list[str], *, sends: bool) -> dict[str, Any]:
    """►►► **Die Anschriften einer Belegseite – beide, immer, beschriftet** (#975). ◄◄◄

    *«Standardmässig immer bei Informationen ausweisen, global etablieren, auch wenn sie
    zweimal das Gleiche anzeigt. Eine Logik für alles, Komplexität und If/Else
    verringern.»*

    Ein Beleg stellt zwei Fragen – *wohin die Rechnung, wohin die Ware* –, und er stellt sie
    auf **jeder** Seite gleich. Also **eine** Regel für beide Seiten: gibt es nur eine
    Anschrift, steht sie unter beiden
    Beschriftungen – das ist die Auskunft «an dieselbe», nicht eine Doppelung. Und wo **gar
    keine** dasteht, gibt es auch keine Beschriftung: die Seite sagt dann, dass sie fehlt.

    Erfunden wird nichts – ``shipped`` entsteht nur aus Angaben, die wirklich da sind.

    ►►► **Und die zweite Beschriftung sagt die RICHTUNG** (Testnotiz #979). ◄◄◄ ``sends``
    heisst «diese Seite ist der Leistungserbringer»: bei ihr geht die Ware **ab**, also
    ist es die *Versandadresse*; beim Empfänger kommt sie **an**, also die *Lieferadresse*.
    """
    if not billed:
        return {"address": [], "shipping": [],
                "address_label": None, "shipping_label": None}
    return {
        "address": billed,
        "shipping": shipped or billed,
        "address_label": vo.BILLING_LABEL,
        "shipping_label": vo.SHIPPING_FROM_LABEL if sends else vo.SHIPPING_LABEL,
    }


def their_side(db: Session, row: Voucher, party_id: Optional[int], *,
               internal: bool = False) -> dict[str, Any]:
    """**Die Gegenseite des Belegkopfs** – als eine Stelle, weil es zwei Leser gibt.

    Der Belegkopf zeigt **einen** Empfänger; sind mehrere angefragt, braucht die
    Oberfläche dieselbe Seite je Angefragtem (``recipients``). Zweimal gebaut liefen die
    beiden beim nächsten Feld auseinander.

    ``party_id is None`` heisst «dieser Betrachter darf sie nicht sehen» – dann ist die
    Seite leer, nicht erfunden.

    **Welche Rolle sie hat, steht in der Richtung** (#979): die Gegenpartei ist genau dann
    der Leistungserbringer, wenn das Geld **nicht** zu uns fliesst.

    ►►► **Und am Adressaten steht, was noch wählbar ist** (``choice``) – Firma oder
    Person, welche Rechnungs- und welche Lieferadresse. Nur für das Personal, nur vor der
    Zusage: danach ist der Kopf eingefroren.
    """
    sends = not vo.of(row.direction).collects
    who = billing_of(db, row, party_id) if party_id is not None else {}
    seat = who.get("address") or {}
    lines = who.get("lines") or []
    return {
        "ours": False,
        "object_id": party_id,
        "name": (lines or [""])[0],
        "attn": lines[1] if len(lines) > 1 else None,
        # **Dieselbe Auflösung wie bei uns** (#975) – zwei Seiten, eine Regel.
        **_addresses(address.lines(address.make(
            street1=seat.get("line1") or "", street2=seat.get("line2") or "",
            zip=seat.get("postal_code") or "", city=seat.get("city") or "",
            country=seat.get("country"),
        )) if seat else [], who.get("shipping") or [], sends=sends),
        "uid": who.get("uid"),
        "email": who.get("email"),
        "phone": who.get("phone"),
        "city": seat.get("city") or None,
        "ship_city": (who.get("delivery") or {}).get("city") or seat.get("city") or None,
        "country": seat.get("country") or None,
        "choice": (choices_of(db, row, party_id, who)
                   if internal and party_id is not None else None),
    }


def choices_of(db: Session, row: Voucher, party_id: int,
               who: dict[str, Any]) -> Optional[dict[str, Any]]:
    """►►► **An wen und wohin – was am Adressaten noch wählbar ist.** ◄◄◄

    ``None``, wo nichts zu wählen ist: nach der Zusage (eingefroren), und an jedem
    anderen als **dem** Adressaten (die Wahl am Beleg gilt ihm). Die Möglichkeiten sind
    sein Adressbuch – eine fremde Anschrift kann man hier nicht wählen.
    """
    if row.stage != vo.OFFER or row.head or party_id != addressee_of(db, row):
        return None
    u = db.query(UserProfile).filter(UserProfile.object_id == party_id).first()
    if u is None:
        return None
    return {
        "company": sites.legal_name(u.company) if business_possible(u) else None,
        "person": people.name(u),
        "bill_to_company": bool(who.get("bill_to_company")),
        "billing_address_id": who.get("billing_address_id"),
        "delivery_address_id": who.get("delivery_address_id"),
        # **Die Anschriften des Kontos, an das die Rechnung geht** – eine aus dem anderen
        # Konto schickte die Rechnung der Firma an die Wohnung.
        "options": [{"id": a.id, "label": address_book.label(a)}
                    for a in address_book.of(db, u, account_for(u, row))],
    }


def transfer_info(db: Session, row: Voucher) -> dict[str, Any]:
    """►►► **Wie man diese Rechnung überweist.** ◄◄◄

    Die dritte Bezahlart ist **keine Buchung**, sondern eine **Auskunft**: «Jetzt bezahlen»
    löst etwas aus, «Zahlung erfassen» schreibt etwas auf – die Überweisung braucht
    *Angaben*, damit der Zahlende sie selbst auslöst.

    **Bankverbindung im Klartext UND als QR** – nicht entweder-oder: der Code spart das
    Abtippen, der Klartext ist der Weg, wenn die Kamera nicht mitspielt. Wo es keinen QR
    geben kann (fremde Währung, keine CH-IBAN), steht der **Grund** statt einer leeren
    Fläche.
    """
    # **Überwiesen wird an den Aussteller**, nicht an den Betreiber: eine zweite Lesart
    # wäre ein QR-Code, der auf ein anderes Konto zeigt als der Beleg darüber.
    company = issuer_company(db, row)
    # **Die IBAN ist die von heute** – wohin gezahlt wird, friert nicht ein (``freeze``).
    iban = getattr(company, "iban", None)
    # **Die Rechnung IST der Beleg** – es gibt eine.
    number = row.number or str(row.id)
    amount = balance_of(db, row).open
    # **Name und Anschrift des Empfängers stehen auf dem Beleg** – also die eingefrorenen.
    creditor = dict((row.head or {}).get("creditor") or _creditor(db, row))
    who = billing_of(db, row)
    seat = who.get("address") or {}
    debtor = {
        "name": who.get("name") or "",
        "street": seat.get("line1"), "street_nr": "",
        "zip": seat.get("postal_code"), "city": seat.get("city"),
        "country": seat.get("country"),
    }
    trouble = qrbill.problem(iban=iban, currency=row.currency, amount=amount)
    code = None if trouble else qrbill.svg(qrbill.payload(
        iban=iban or "", creditor=creditor, amount=amount,
        currency=row.currency, debtor=debtor, number=number))
    return {
        "iban": iban, "creditor": creditor["name"],
        "reference": qrbill.reference(number),
        "amount": _money(amount, row.currency), "currency": row.currency,
        "invoice": number, "qr": code, "problem": trouble,
    }


# ---------------------------------------------------------------------------
# ►► DIE GEGENPARTEI
# ---------------------------------------------------------------------------

def _party(db: Session, *, step: ProcessStep, value: Any,
           flow: vo.Direction) -> Optional[int]:
    """Die gewählte Gegenpartei prüfen – gegen die Freigabe und gegen die Wirklichkeit.

    **Leer heisst frei, aber nicht «irgendwer»**: wo die Definition niemanden nennt, muss
    es die Objektnummer trotzdem geben. Eine Auswahl, die der Dienst danach abwiese, wäre
    keine.
    """
    if value in (None, "", 0):
        return None
    number = _int(value)
    if number is None:
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine Objektnummer.")
    allowed = modules.Beleg.parties_allowed(step.config)
    if allowed and number not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(f"{vo.PARTY} {number} ist an diesem Modul nicht zugelassen. Erlaubt: "
                    + ", ".join(str(n) for n in allowed) + "."))
    found = (
        db.query(UserProfile)
        .filter(UserProfile.object_id == number, UserProfile.is_active.is_(True))
        .first()
    )
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=f"{number} ist kein Datensatz, mit dem man handeln kann.")
    return number


# ---------------------------------------------------------------------------
# ►► KLEINE HELFER — jeder mit genau einer Aufgabe
# ---------------------------------------------------------------------------

def _int(value: Any) -> Optional[int]:
    """Eine Zahl aus der Nutzlast – **tolerant**, denn hier wird nur nachgesehen."""
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _amount(value: Any, code: str, *, allow_negative: bool = False) -> Optional[Decimal]:
    try:
        return vo.amount(value, code, allow_negative=allow_negative)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _days(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        found = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine Anzahl Tage.")
    if not 0 <= found <= 365:
        raise HTTPException(status_code=400,
                            detail="Eine Frist liegt zwischen 0 und 365 Tagen.")
    return found


def ask_problem(db: Session, row: Voucher, step: ProcessStep,
                parties: Optional[list[int]] = None,
                lines: Optional[list[dict[str, Any]]] = None) -> Optional[str]:
    """►►► **Was fehlt noch, damit dieser Beleg HINAUSGEHEN kann?** ◄◄◄ – oder ``None``.

    *«Diese Meldung erscheint nicht an der Stelle des Geschehens. Besser wäre, der
    Submit-Button ist deaktiviert, bis alles vollständig ist – und beim Hover erklärt er
    warum.»* (Testnotiz #1046)

    Die Prüfung gab es längst, nur **erst beim Klick**: `_ask` wies ab, und der Satz landete
    als rote Zeile am Kopf des Auftrags – weit weg von der Position, die er nennt. Jetzt ist
    er eine **Ableitung**, die mitreist (``VoucherEmbed.ask_problem``), und derselbe Satz
    ist das Tor: ``_assert_ask`` wirft ihn. **Zwei Formen einer Regel, ein Namensstamm** –
    nie zwei Massstäbe.

    *Warum hier ein gesperrter Knopf richtig ist, obwohl «ein Knopf, der nie etwas tun kann,
    ist kein Angebot» die Hausregel ist (#950): dieser hier **kann** – sobald die Angaben
    stehen. Dieselbe Form wie «Freigeben» am Auftragsentwurf, der seit jeher gesperrt
    dasteht und im Hover sagt, was fehlt.*

    **Was auf dem Beleg steht, ist Pflicht** (#964): Preis je Position, die beiden
    **Zoll**-Angaben, die **Lieferbedingung** und die beiden **Fristen**. Gelesen wird
    dabei der Wert, der auf dem Beleg **steht** (``embed_lines``: die Zeile, wo sie etwas
    trägt, sonst der Artikel) – die rohe Spalte zu prüfen hiesse, eine Angabe zu
    verlangen, die sichtbar längst dasteht.

    **Der Satz nennt die Position**, nicht nur das Feld: «Ohne Zolltarifnummer …» über
    einem Beleg mit zwölf Zeilen ist eine Sackgasse mit Ausrufezeichen.

    ``parties``/``lines`` sind die Angaben, die der Aufrufer ohnehin hat – ``_ask`` kennt
    die genannten Parteien, die Antwort kennt die Positionen. Ohne sie werden sie gelesen.
    """
    flow = vo.of(row.direction)
    # **Ohne Gegenpartei gibt es nichts anzufragen** – zwei Quellen, dieselben wie in
    # ``_ask``: was die Definition zulässt und wen der Beleg selbst schon trägt (#1000).
    if parties is None:
        parties = modules.Beleg.parties_allowed(step.config) or parties_on(row)
    if not parties:
        return (f"Ohne {vo.PARTY} gibt es nichts anzufragen – dieses Modul lässt "
                f"jeden zu, also muss hier stehen, wen es betrifft.")
    # ►►► **Alles, was fehlt, auf einmal** (Chrome-Test) ◄◄◄ – vorher nannte der Satz nur
    # den ersten Punkt, und man fand den nächsten erst nach dem Beheben des ersten.
    found: list[str] = []
    priced = flow.quoted_by == vo.BY_US
    # ►►► **Zoll nur bei einer Ausfuhr** – Tarif, Ursprung und Gewicht braucht der Zoll,
    # im Inland niemand. ◄◄◄
    export = is_export(db, row)
    for ln in (lines if lines is not None else embed_lines(db, row)):
        what = f"Position «{ln['article_name'] or ln['id']}»"
        if priced and ln["price"] is None:
            found.append(f"{what}: ohne Preis gibt es nichts anzubieten.")
        if not export or ln.get("is_service"):
            continue
        gaps = [label for key, label in (("hs_code", vo.HS_CODE_LABEL),
                                         ("origin_country", vo.ORIGIN_LABEL),
                                         ("weight_kg", vo.WEIGHT_LABEL))
                if not str(ln.get(key) or "").strip()]
        if gaps:
            found.append(f"{what}: {' · '.join(f'«{g}»' for g in gaps)} fehlt – eine "
                         f"Ausfuhr braucht es. Am Artikel hinterlegt, steht es auf jedem "
                         f"Beleg von selbst; hier eingetragen, gilt es für diesen Beleg.")
    # **Eine Lieferbedingung gibt es nur bei Ware** – eine Dienstleistung reist nicht.
    if not row.incoterm and has_goods(db, row):
        found.append(f"Ohne {inc.LABEL} ist nicht vereinbart, wer Fracht, Versicherung "
                     f"und Zoll trägt – und genau darüber wird sonst gestritten.")
    if priced:
        if not priced_dicts(db, row) and not any("Preis" in f for f in found):
            found.append(f"Ohne Preis gibt es nichts anzubieten – bei einer {flow.label} "
                         f"nennen wir ihn, nicht der {vo.PARTY}.")
        found.append(terms_problem(row.lead_days, row.payment_days) or "")
    # **Zuletzt das Eigentum** – bewusst gewählt, ohne Vorbelegung.
    found.append(ownership_problem(row) or "")
    found = [f for f in found if f]
    if len(found) < 2:
        return found[0] if found else None
    return "\n".join(f"– {f}" for f in found)


def _assert_ask(db: Session, row: Voucher, step: ProcessStep,
                parties: list[int]) -> None:
    """Das Tor zu ``ask_problem`` – **derselbe Satz**, nur geworfen."""
    problem = ask_problem(db, row, step, parties=parties)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


def terms_problem(lead: Optional[int], days: Optional[int]) -> Optional[str]:
    """►►► **Ein Angebot nennt beide Fristen.** ◄◄◄ – der Satz, oder ``None``.

    Sie sind kein Beiwerk: aus der **Lieferfrist** kommt der Termin, aus der
    **Zahlungsfrist** die Fälligkeit jeder Rechnung – und, wenn sie null ist, die
    Vorauszahlung. Fehlt eine, hat niemand über den Zeitpunkt gesprochen.

    **Null ist ein gültiger Wert und hat einen Namen** («Sofort» · «Vorauszahlung»): darum
    steht die Prüfung auf ``is None`` und nicht auf ``not value``.

    **Zwei Formen, ein Namensstamm**: ``_assert_terms`` wirft ihn an einer Angebotszeile,
    ``ask_problem`` trägt ihn an den gesperrten Knopf (#1046).
    """
    for value, label in ((lead, vo.LEAD_TERM_LABEL), (days, vo.PAYMENT_TERM_LABEL)):
        if value is None:
            return (f"Ohne {label} ist es kein Angebot – aus ihr folgt der Termin "
                    f"bzw. die Fälligkeit. «{vo.LEAD_TERMS[0][1]}» und "
                    f"«{vo.PAYMENT_TERMS[0][1]}» sind gültige Antworten (0 Tage).")
    return None


def _assert_terms(lead: Optional[int], days: Optional[int]) -> None:
    """Das Tor zu ``terms_problem`` – derselbe Satz, nur geworfen."""
    problem = terms_problem(lead, days)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


def _day(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Datum.")


def _text(value: Any, limit: int) -> Optional[str]:
    found = str(value or "").strip()
    if len(found) > limit:
        raise HTTPException(status_code=400,
                            detail=f"Der Text ist zu lang (max. {limit} Zeichen).")
    return found or None


def _due(booked: date, days: Optional[int]) -> Optional[date]:
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
    return _due(row.agreed_on, q.lead_days)


def _our_number(db: Session, order: Order) -> str:
    """``<Auftragsnummer>-<laufend>`` – **immer mit Suffix**, ab ``-1``.

    Dieselbe Regel wie die Nummer einer Einzelinstanz. Gezählt wird über den **Auftrag**
    (zwei Module vergäben sonst dieselbe Nummer zweimal) und **nur, was WIR nummerieren** –
    sonst verbraucht eine erfasste Lieferantenrechnung die Zählung. Auch stornierte Zeilen
    zählen mit: eine einmal vergebene Nummer wird nicht erneut vergeben.

    *Die bewusste Grenze: kein Unique-Index darüber. Bei einem Einkauf steht dort die
    Nummer der Gegenpartei, und zwei Lieferanten dürfen beide eine «2026-001» schicken.*
    """
    used = (
        db.query(func.count(Voucher.id))
        .filter(Voucher.order_id == order.id, Voucher.direction == vo.IN,
                Voucher.number.isnot(None))
        .scalar()
    ) or 0
    return f"{order.object_id}-{used + 1}"


def _money(value: Optional[Decimal], code: str) -> Optional[str]:
    """Ein Betrag als String – mit den Nachkommastellen **dieser** Währung."""
    return None if value is None else cur.money(value, code)


# ---------------------------------------------------------------------------
# ►► DIE ANTWORT
# ---------------------------------------------------------------------------

def embed_data(db: Session, *, order: Order, step: ProcessStep,
               viewer: Optional[UserProfile] = None) -> Optional[dict[str, Any]]:
    """Der Beleg, wie die Karte ihn braucht – oder ``None``.

    **Alles, was die Oberfläche zum Zeichnen braucht, reist mit**: Wörter, Stufen, die
    Leiste (``state``), Verben, Zahlen und was man tun darf. Sie fragt damit nie nach der
    Richtung und nie nach dem Modultyp.

    **Eine Gegenpartei sieht nur ihren Teil** – gefiltert wird hier, beim Aufbau der
    Antwort. Wer **nicht den Zuschlag** hat, sieht weder Namen noch Preis der übrigen.

    ►►► **Hier laufen die Positionen nach** (``sync_lines``) – der einzige Schreibvorgang
    auf einem Lesepfad, idempotent und durch einen Unique-Index abgesichert. ◄◄◄
    """
    row = of_step(db, step.id)
    if row is None:
        return None
    flow = vo.of(row.direction)
    sync_lines(db, row, order, step)
    entries = entries_of(db, row)
    money = balance_of(db, row)
    chosen = chosen_quote(db, row)
    internal = viewer is None or viewer.role in STAFF_ROLES
    party = chosen.party_id if chosen is not None else None
    won = internal or (party is not None and viewer is not None
                       and party == viewer.object_id)
    allowed = can(db, row, viewer)
    billed = is_billed(row)
    late = overdue(db, row)
    state = (vo.invoice_state(money.charged, money.open, overdue=late) if billed else None)
    refund_ids = ({e.id for e in refundable(db, row)}
                  if "refund_online" in allowed else set())
    undoable = {e.id for e in reversible(db, row)} if "reverse" in allowed else set()
    priced = [ln for ln in priced_dicts(db, row) if vo.line_net(ln, row.currency) != 0]
    split = vo.vat_split(priced, row.currency)
    sums = vo.totals(split, row.currency)
    lines = embed_lines(db, row)
    target = corrects(db, row) if won else None
    fixed = modules.Beleg.presets_of(step.config)
    nxt = next_reminder(db, row)
    quotes = quotes_of(db, row)
    return {
        "direction": row.direction,
        "label": flow.label,
        "party_word": vo.PARTY,
        # **«Anbieten» ↔ «Erneut anbieten»** – dieselbe Handlung; das Wort sagt, ob schon
        # etwas hinausging.
        "ask_verb": (f"Erneut {flow.ask_verb.lower()}" if quotes and flow.collects
                     else flow.ask_verb),
        "we_quote": flow.quoted_by == vo.BY_US,
        "ref_label": flow.reference,
        "minus": minus(row),
        # ─── Die Abschnitte ──────────────────────────────────────────────────────
        "parties_title": vo.PARTIES_TITLE,
        "goods_title": vo.GOODS_TITLE,
        "terms_title": vo.TERMS_TITLE,
        "quotes_title": vo.QUOTES_TITLE,
        "invoice_title": vo.INVOICE_TITLE,
        "docs_title": vo.DOCS_TITLE,
        # ─── Die Leiste ──────────────────────────────────────────────────────────
        "state": situation(db, row, order=order, step=step) if internal else None,
        "locked": (units_problem(db, row, order, step) if internal else None),
        # ─── Steuer ──────────────────────────────────────────────────────────────
        "vat_rates": [{"key": v.key, "rate": v.rate, "label": v.label, "note": v.note}
                      for v in vo.VAT_RATES],
        "vat_rate": vo.DEFAULT_VAT,
        "vat_label": vo.VAT_LABEL,
        "service_date_label": vo.SERVICE_DATE_LABEL,
        "net": sums["net"] if won else None,
        "tax": sums["tax"] if won else None,
        "vat_split": split if won else [],
        "export": is_export(db, row),
        # ─── Lieferbedingung: die Klausel; der Ort folgt aus den Anschriften ─────
        "incoterm": row.incoterm,
        "incoterm_place": incoterm_place_of(db, row),
        "incoterm_text": inc.sentence(row.incoterm, incoterm_place_of(db, row)),
        "incoterm_label": inc.LABEL,
        "incoterm_place_label": inc.PLACE_LABEL,
        "incoterms": [{"key": t.key, "label": t.label, "hint": t.hint}
                      for t in inc.INCOTERMS],
        "incoterm_needed": has_goods(db, row),
        # ─── Währung und Aussteller ──────────────────────────────────────────────
        "currency": row.currency,
        "currency_label": cur.label(row.currency),
        "currency_decimals": cur.minor_units(row.currency),
        "currencies": [{"code": c, "label": cur.label(c)} for c in cur.CURRENCIES],
        "issuer": getattr(issuer_company(db, row), "object_id", None),
        "issuer_label": vo.ISSUER_LABEL,
        "issuers": [{"object_id": c.object_id, "name": sites.legal_name(c)}
                    for c in sites.selectable_companies(db)] if internal else [],
        # ─── Wörter der Handlungen ───────────────────────────────────────────────
        "charge_word": vo.charge_word(collects=flow.collects, minus=minus(row)),
        "payment_word": vo.payment_word(minus=minus(row)),
        "sent_word": vo.SENT_WORD,
        "taken_word": vo.TAKEN_WORD,
        "cancelled_word": vo.CANCELLED_WORD,
        "pay_online_word": vo.PAY_ONLINE_WORD,
        "refund_online_word": vo.REFUND_ONLINE_WORD,
        "refund_word": vo.REFUND_WORD,
        "tip_word": vo.TIP_WORD,
        "write_off_word": vo.WRITE_OFF_WORD,
        "write_off_reasons": [{"key": k, "label": v} for k, v in vo.WRITE_OFF_REASONS],
        "reverse_word": vo.REVERSE_WORD,
        "remind_word": vo.remind_word(nxt[0]) if nxt else None,
        "remind_from": nxt[1] if nxt else None,
        "undo": vo.UNDO if "revoke" in allowed else None,
        "stage": row.stage,
        "stages": _stages(db, row, flow),
        "can": allowed,
        # **Was ein Papier hinausgibt, zeigt die Karte vorher** (Vorschau → Freigeben).
        "paper_verbs": list(PAPER_VERBS) if (internal and flow.collects) else [],
        "paper_due": (papers_due(db, row) or [None])[0] if internal else None,
        # ─── Fristen, Gültigkeit, Eigentum ───────────────────────────────────────
        "prepaid": vo.prepaid(due_days_of(db, row)),
        "payment_terms": [{"days": d, "label": name} for d, name in vo.PAYMENT_TERMS],
        "lead_terms": [{"days": d, "label": name} for d, name in vo.LEAD_TERMS],
        "term_free_min": vo.FREE_MIN,
        "term_free_label": vo.FREE_TERM_LABEL,
        "payment_term_label": vo.PAYMENT_TERM_LABEL,
        "lead_term_label": vo.LEAD_TERM_LABEL,
        "valid_days": valid_days_of(row) if flow.quoted_by == vo.BY_US else None,
        "valid_label": vo.VALID_LABEL,
        "valid_until": valid_until(db, row),
        "expired": expired(db, row),
        "changed": changed_since_offer(db, row),
        # **Was das Modul vorgibt, steht fest** – je Feld der Grund im Hover.
        "fixed": sorted(fixed),
        "fixed_hint": "Im Modul vorgegeben – wird übernommen, hier nicht änderbar",
        "ownership": ownership_of(row),
        "ownership_label": vo.OWNERSHIP_LABEL,
        "ownership_options": [{"key": k, "label": v} for k, v in vo.OWNERSHIP],
        # ─── Der Beleg selbst ────────────────────────────────────────────────────
        "allowed": (_named(db, modules.Beleg.parties_allowed(step.config))
                    if internal else []),
        "quotes": _quotes(db, row, step, viewer=viewer, internal=internal),
        "recipients": ([their_side(db, row, n, internal=True)
                        for n in _possible_parties(db, row, step)]
                       if internal else []),
        "lines": lines,
        "ask_problem": (ask_problem(db, row, step, lines=lines)
                        if "ask" in allowed or row.stage == vo.OFFER else None),
        **document_head(db, row, won=won, internal=internal),
        "gaps": (gaps(db, row, action=next_action(db, row)) if internal else []),
        "party_object_id": party if won else None,
        "party_name": (_named(db, [party])[0]["name"] if party and won else None),
        "amount": _money(chosen.amount, row.currency) if (chosen and won) else None,
        "due_days": due_days_of(db, row) if won else None,
        "lead_days": lead_days_of(db, row) if won else None,
        "agreed_on": row.agreed_on if won else None,
        "cancelled_on": row.cancelled_on if won else None,
        "cancel_note": row.cancel_note if internal else None,
        "due_date": delivery_date(db, row) if won else None,
        # ─── Die Rechnung und das Geld ───────────────────────────────────────────
        "invoice": ({
            "number": row.number,
            "billed_on": row.billed_on,
            "due_on": row.due_on,
            "amount": _money(row.amount, row.currency),
            "vat": list(row.vat or []),
            "service_date": row.service_date,
            "overdue": late,
            **(state or {}),
        } if (billed and won) else None),
        "credit_number": row.credit_number if won else None,
        "corrects": ({
            "id": target.id,
            "number": target.number,
            "billed_on": target.billed_on,
            "amount": _money(target.amount, target.currency),
        } if target is not None else None),
        "corrects_label": vo.CORRECTS_LABEL,
        "corrects_hint": vo.CORRECTS_HINT,
        "corrects_suggested": (suggested_corrections(db, row, order)
                               if internal and row.stage == vo.OFFER else []),
        "party_uid": row.party_uid if won else None,
        "original": row.original_id if won else None,
        "deviation": _money(deviation(db, row), row.currency) if won else None,
        "deviation_note": row.deviation_note if won else None,
        "export_number": row.export_number if won else None,
        "export_photo": row.export_photo_id if won else None,
        "charged": _money(money.charged, row.currency) if won else None,
        "credited": _money(money.credited, row.currency) if won else None,
        "paid": _money(money.paid, row.currency) if won else None,
        "written_off": _money(money.written_off, row.currency) if won else None,
        "tips": _money(money.tips, row.currency) if won else None,
        "open": _money(money.open, row.currency) if won else None,
        "open_state": state["state"] if (state and won) else None,
        "open_state_label": state["state_label"] if (state and won) else None,
        "open_state_tone": state["state_tone"] if (state and won) else None,
        "next_payment": _money(money.next_payment, row.currency) if won else None,
        "settled": money.settled if won else False,
        "done": is_done(db, row),
        "ways": (_ways(allowed, inbound=inbound(row), minus=minus(row))
                 if (billed and won) else []),
        "method_label": vo.METHOD_LABEL,
        "entries": [
            {
                "id": e.id, "amount": _money(e.amount, row.currency),
                "booked_on": e.booked_on,
                "reference": e.reference, "note": e.note,
                "booked_at": e.created_at,
                "method": e.method,
                "method_label": vo.method_name(e.method),
                "kind": e.kind or vo.PAYMENT,
                "reason": e.reason,
                "reason_label": vo.reason_label(e.reason),
                "reverses_id": e.reverses_id,
                "iban": e.iban,
                "refundable": e.id in refund_ids,
                "reversible": e.id in undoable,
            }
            for e in (entries if won else [])
        ],
        # ─── Die Dokumente, so wie sie hinausgingen ──────────────────────────────
        "documents": ([_document_out(d) for d in documents_of(db, row)] if won else []),
    }


def public_link(token: str) -> str:
    """**Der Link der Partei** – die Seite, die das Dokument zeigt (ohne Anmeldung)."""
    from ..core.config import get_settings
    return f"{get_settings().frontend_base_url.rstrip('/')}/beleg?t={token}"


def _document_out(d: VoucherDocument) -> dict[str, Any]:
    """Ein Dokument in der Liste der Karte – Art, Wort, Nummer, Zeitpunkt, Link."""
    word = (vo.remind_word(d.level or 1) if d.kind == vo.REMINDER_DOC
            else vo.DOCUMENTS.get(d.kind, d.kind))
    return {"id": d.id, "kind": d.kind, "label": word, "number": d.number,
            "sent_at": d.created_at, "url": public_link(d.token)}


def suggested_corrections(db: Session, row: Voucher, order: Order) -> list[dict[str, Any]]:
    """►►► **Welche Rechnung mindert diese Gutschrift? – vorgeschlagen aus dem Log.** ◄◄◄

    Die Rechnungen, über die **diese Stücke** liefen: ein Zahlungsmodul in einem anderen
    Auftrag, das sie passiert haben, mit gestellter Rechnung in derselben Richtung. Ist es
    eine, steht sie als Vorschlag da; sind es mehrere (Verkauf, Service …), wählt der
    Mensch. Nur vorgeschlagen, nie gesetzt: ob ein Beleg mindert, entscheidet ein Mensch.
    """
    if row.corrects_id is not None:
        return []
    units = [int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
        OrderUnit.order_id == order.id).all()]
    if not units:
        return []
    steps = {int(s) for (s,) in db.query(ProcessEvent.step_id).filter(
        ProcessEvent.instance_unit_id.in_(units), ProcessEvent.kind == KIND_STEP,
        ProcessEvent.order_id != order.id, ProcessEvent.step_id.isnot(None)).all()}
    if not steps:
        return []
    found = (db.query(Voucher)
             .filter(Voucher.step_id.in_(steps), Voucher.is_active.is_(True),
                     Voucher.direction == row.direction, Voucher.billed_on.isnot(None),
                     Voucher.corrects_id.is_(None))
             .order_by(Voucher.billed_on.desc(), Voucher.id.desc()).limit(10).all())
    numbers = {o.id: o.object_id for o in db.query(Order).filter(
        Order.id.in_([v.order_id for v in found] or [0]))}
    return [{"id": v.id, "number": v.number, "billed_on": v.billed_on,
             "amount": _money(v.amount, v.currency), "currency": v.currency,
             "order_object_id": numbers.get(v.order_id)} for v in found]


def _ways(allowed: list[str], *, inbound: bool, minus: bool) -> list[dict[str, Any]]:
    """►►► **Die Wege zum Geld – EINE Frage mit mehreren Antworten.** ◄◄◄

    Bar · Überweisung · Karte. **Jeder Weg sagt selbst, was er auslöst**: bar und
    Überweisung enden in einer Buchung (``pay``), die Überweisung ist zusätzlich eine
    Auskunft (Bankverbindung, QR) dort, wo das Geld zu uns kommt; die Karte führt aus
    (``pay_online``) – oder, wo wir zahlen, ist es unsere Firmenkarte (``pay``).
    """
    books = "pay" in allowed
    word = vo.payment_word(minus=minus)
    out: list[dict[str, Any]] = []

    def way(key: str, action: Optional[str], verb: Optional[str],
            info: bool = False) -> dict[str, Any]:
        return {"key": key, "label": vo.method_name(key) or key,
                "action": action, "verb": verb, "info": info}

    if books:
        out.append(way(vo.CASH, "pay", word))
    if books or inbound:
        out.append(way(vo.TRANSFER, "pay" if books else None,
                       word if books else None, info=inbound))
    if "pay_online" in allowed:
        out.append(way(vo.CARD, "pay_online", vo.PAY_ONLINE_WORD))
    elif books and not inbound:
        out.append(way(vo.CARD, "pay", word))
    if "refund_online" in allowed:
        out.append(way(vo.CARD, "refund_online", "Auf Karte zurückerstatten"))
    return out


def _quotes(db: Session, row: Voucher, step: ProcessStep, *,
            viewer: Optional[UserProfile], internal: bool) -> list[dict[str, Any]]:
    """Der Angebotsspiegel – **für die Gegenpartei nur ihre eigene Zeile**.

    Wer nicht den Zuschlag hat, sieht weder Namen noch Preis der übrigen: gefiltert wird
    beim Aufbau der Antwort, nicht in der Oberfläche.

    **Die Bestellangabe reist mit ihrer Zeile** (``config.parties[].ref``): sie sagt, wie
    man bei genau diesem hier bestellt, und steht darum bei ihm – nicht als eine Angabe am
    Beleg, die man bei jedem Vorgang neu abschreibt.

    ►►► **Und der MOMENT reist mit, nicht nur der Tag** (Testnotizen #968/#969). ◄◄◄

    *«Kann hier noch eine kleine Info dazu, wann offeriert wurde – im Format ‹vor xx Tagen
    offeriert›, und beim Hovern das genaue Datum und Uhrzeit.»*

    Die Uhrzeit steht **schon da** und brauchte keine Spalte: ``created_at`` einer
    Angebotszeile *ist* der Moment, in dem sie hinausging – ``_ask`` legt sie genau dort an
    und nirgends sonst. Und ``updated_at`` der **gewählten** Zeile ist der Moment des
    Zuschlags: ``_agree`` setzt ``CHOSEN`` in einem Zug mit der Stufe, und danach fasst
    kein Verb sie mehr an (``quote``/``decline`` verlangen beide, dass sie es nicht ist).

    ``sent_on`` bleibt daneben: es ist das **Datum auf dem Papier** – ein Beleg trägt einen
    Tag, keine Uhrzeit. Der Moment ist die Auskunft darüber, wann es passierte.
    """
    rows = quotes_of(db, row)
    if not internal:
        own = viewer.object_id if viewer else None
        rows = [q for q in rows if q.party_id == own]
    # **Derselbe Name wie im Kopf** (Chrome-Test): vorher stand vor dem Anbieten die Firma,
    # danach die Person – zwei Namen für eine Partei. Jetzt Firma zuerst, «z. H.» darunter.
    named = {q.party_id: (billing_of(db, row, q.party_id).get("lines") or [""])
             for q in rows}
    return [
        {
            "id": q.id,
            "party_object_id": q.party_id,
            "party_name": named[q.party_id][0],
            "party_attn": named[q.party_id][1] if len(named[q.party_id]) > 1 else None,
            "ref": modules.Beleg.ref_for(step.config, q.party_id),
            "amount": _money(q.amount, row.currency),
            "lead_days": q.lead_days,
            "payment_days": q.payment_days,
            "state": q.state or vo.ASKED,
            "reference": q.reference,
            "link": q.link,
            "sent_on": q.sent_on,
            "sent_at": q.created_at,
            # **Nur an der gewählten Zeile** – an jeder anderen wäre ``updated_at`` der
            # Moment irgendeiner Änderung und würde einen Zuschlag behaupten, den es
            # dort nie gab.
            "agreed_at": q.updated_at if q.state == vo.CHOSEN else None,
        }
        for q in rows
    ]


def _stages(db: Session, row: Voucher, flow: vo.Direction) -> list[dict[str, Any]]:
    """►►► **Der Weg oben auf der Karte – vier Stationen.** ◄◄◄

    Offerte (bzw. Anfrage) · Zusage · Rechnung · Erledigt. Ein Storno ist keine Station: die
    gegangene Kette bleibt stehen, keine ist aktiv.
    """
    keys = [vo.OFFER, vo.AGREED, vo.BILLED, vo.DONE]
    labels = {vo.OFFER: flow.label_of(vo.OFFER), vo.AGREED: "Zusage",
              vo.BILLED: vo.CREDIT_NOUN if minus(row) else vo.INVOICE_NOUN,
              vo.DONE: "Erledigt"}
    if is_done(db, row):
        reached = 4
    elif row.stage == vo.CANCELLED:
        reached = 2 if row.billed_on is not None else (1 if row.agreed_on else 0)
    else:
        reached = keys.index(row.stage)
    return [{"key": k, "label": labels[k], "verb": None, "done": i < reached,
             "active": row.stage != vo.CANCELLED and i == reached}
            for i, k in enumerate(keys)]


def _named(db: Session, numbers: list[Optional[int]]) -> list[dict[str, Any]]:
    """Objektnummern auf ihren Anzeigenamen – **eine** Abfrage, nicht eine je Zeile."""
    wanted = [n for n in numbers if n]
    if not wanted:
        return []
    rows = {
        u.object_id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.object_id.in_(wanted)).all()
    }
    return [{"object_id": n, "name": rows.get(n, str(n))} for n in wanted]
