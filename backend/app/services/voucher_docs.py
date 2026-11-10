"""►►► **Die Dokumente eines Belegs – so wie sie hinausgehen.** ◄◄◄

Bei jedem Schritt, den die Partei sehen soll (Offerte, Auftragsbestätigung, Rechnung,
Quittung, Stornierung, Gutschrift, Mahnung), entsteht **ein Dokument**: das Papier aus der
einen Vorlage (``services/a4``), eingefroren in der Ablage (Pflichtfeld ``voucher.doc``,
10 Jahre; was es ist, steht in ``facts``), mit **einem gewöhnlichen Link** an die Partei
(``document_links`` – derselbe wie für jedes gesendete Dokument, Seite ``/dokument``) und **eine
Mail** über das Postfach der Gesellschaft. Die Mail steht im Verlauf der Person wie jede andere.

Nur, wo **wir** den Beleg stellen (``Direction.collects``): eine Lieferantenrechnung schreibt
niemand für den Lieferanten.

Ohne verbundenes Postfach wird die Mail **nur erfasst** – wie jede andere Mail des Hauses
(``docs/gmail-setup.md``); das Dokument und sein Link gibt es trotzdem.
"""

import logging
import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from decimal import Decimal
from html import escape
from typing import Any, Iterator, Optional

from sqlalchemy.orm import Session

from ..core import clock
from ..domain import communication as dc
from ..domain import currency as cur
from ..domain import incoterms as inc
from ..domain import voucher as vo
from ..models import Document, DocumentLink, DocumentRef, Message, Order, UserProfile, Voucher
from . import address, a4, legal, mail_layout, sites
from . import voucher as vs
from . import voucher_actions as va
from . import voucher_head as vh
from . import voucher_money as vm
from ..domain.errors import Conflict
from ..domain import policy

log = logging.getLogger(__name__)

#: Eine Anschrift im Inland trägt kein Land – wie auf jedem Schweizer Brief.
HOME_LINES = ("CH", "Schweiz")

#: Die Stationen, die die Partei sieht – in der Mail quer, auf der Seite als Weg.
STATIONS = ("Offerte", "Auftragsbestätigung", "Rechnung", "Bezahlt")
#: Wo eine Mail auf dem Weg steht – je Dokumentart.
AT = {vo.OFFER_DOC: 0, vo.CONFIRM_DOC: 1, vo.INVOICE_DOC: 2, vo.RECEIPT_DOC: 3}

#: ►►► **Die Sätze der Mails** – immer derselbe kurze Text je Art; das Papier sagt den Rest.
#: Der Storno nennt keinen Grund (der bleibt intern). ◄◄◄
LEADS = {
    vo.OFFER_DOC: ("Ihre Offerte", "Herzlichen Dank für Ihr Interesse. Gerne unterbreiten wir "
                   "Ihnen unsere Offerte – alle Einzelheiten finden Sie online. Haben Sie Fragen, "
                   "sind wir gerne für Sie da."),
    vo.CONFIRM_DOC: ("Ihre Auftragsbestätigung", "Herzlichen Dank für Ihren Auftrag – wir "
                     "freuen uns sehr darüber. Gerne bestätigen wir Ihnen die Bestellung, wie "
                     "besprochen."),
    vo.INVOICE_DOC: ("Ihre Rechnung", "Wir hoffen, Sie sind mit unserer Leistung zufrieden. Gerne "
                     "senden wir Ihnen die Rechnung{due} – bequem mit Karte oder mit der "
                     "QR-Rechnung."),
    vo.RECEIPT_DOC: ("Ihre Quittung", "Ihre Zahlung ist bei uns eingegangen – herzlichen Dank. "
                     "Es war uns eine Freude, für Sie zu arbeiten."),
    vo.STORNO_DOC: ("Ihre Stornierung", "Wir bestätigen Ihnen die Stornierung. Es ist nichts "
                    "mehr geschuldet. Haben Sie Fragen, sind wir gerne für Sie da."),
    vo.CREDIT_DOC: ("Ihre Gutschrift", "Gerne senden wir Ihnen die Gutschrift. Was Sie bereits "
                    "bezahlt haben, erstatten wir Ihnen. Haben Sie Fragen, sind wir gerne für "
                    "Sie da."),
}
REMINDER_LEADS = (
    "Im Alltag geht schnell einmal etwas unter. Unsere Rechnung {number} war am {due} fällig – "
    "dürfen wir Sie freundlich bitten, den offenen Betrag in den nächsten 10 Tagen zu "
    "begleichen? Hat sich Ihre Zahlung mit dieser Erinnerung gekreuzt, betrachten Sie sie "
    "bitte als gegenstandslos.",
    "Unsere Rechnung {number} vom {billed} ist trotz unserer Erinnerung noch offen. Wir bitten "
    "Sie, den offenen Betrag innert 10 Tagen zu begleichen. Haben Sie Fragen zur Rechnung, "
    "melden Sie sich bitte – wir finden gemeinsam eine Lösung.",
    "Unsere Rechnung {number} ist trotz zweier Mahnungen noch offen. Wir bitten Sie, den "
    "offenen Betrag innert 10 Tagen zu begleichen. Danach müssten wir die Betreibung einleiten "
    "– das möchten wir Ihnen und uns gerne ersparen.",
)


def _day(d: Optional[date]) -> str:
    """Ein Tag, wie er auf dem Papier steht – «24.10.2026»."""
    return clock.day(d)


def _money(value: Optional[Decimal], code: str) -> str:
    """Ein Betrag auf dem Papier – mit Tausender-Apostroph, in der Stelligkeit der Währung."""
    if value is None:
        return ""
    text = cur.money(value, code)
    whole, _, frac = text.partition(".")
    sign = "−" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return sign + "'".join(groups) + (f".{frac}" if frac else "")


def _days_word(days: Optional[int], *, lead: bool) -> str:
    if days is None:
        return "–"
    names = dict(vo.LEAD_TERMS if lead else vo.PAYMENT_TERMS)
    if days in names:
        return names[days]
    return f"{days} Tage ab Bestellung" if lead else f"{days} Tage netto"


# ---------------------------------------------------------------------------
# Das Papier
# ---------------------------------------------------------------------------

def build(db: Session, *, row: Voucher, kind: str, party: int,
          actor: Optional[UserProfile] = None, level: Optional[int] = None) -> a4.Doc:
    """►►► **Was auf dem Papier steht** – aus dem Beleg, an einer Stelle. ◄◄◄"""
    order = db.query(Order).filter(Order.id == row.order_id).first()
    head = vh.document_head(db, row, won=True, party_id=party)
    ours, theirs = (head["supplier"], head["customer"])
    company = vh.issuer_company(db, row)
    seat = address.of_company(company) if company is not None else {}
    sender = " · ".join(x for x in (sites.legal_name(company) or "", seat.get("street1") or "",
                                    " ".join(y for y in (seat.get("zip"), seat.get("city"))
                                             if y), ours.get("uid") or "") if x and x != "—")
    to = [theirs.get("name") or "", theirs.get("attn") or "",
          *[x for x in (theirs.get("address") or []) if x not in HOME_LINES]]
    word = vo.document_word(kind, level)
    doc = a4.Doc(
        word=word, number=_number(row, kind, order), to=to,
        facts=_facts(db, row, kind, party, actor, theirs),
        currency=row.currency, sender=sender,
        terms_of=legal.text_of(db, company, legal.AGB),
    )
    if kind == vo.REMINDER_DOC:
        _reminder(db, row, doc, level or 1)
    else:
        _lines(db, row, kind, doc)
        doc.terms = _terms(db, row, theirs)
        doc.after = _after(db, row, kind, party)
    if kind in (vo.INVOICE_DOC, vo.REMINDER_DOC):
        doc.payslip = _payslip(db, row, theirs)
    return doc


def _number(row: Voucher, kind: str, order: Optional[Order]) -> str:
    """Die Nummer auf dem Papier: bis zur Rechnung die des Auftrags, danach die Rechnung;
    eine Gutschrift aus einem Storno trägt ihre eigene."""
    if kind == vo.CREDIT_DOC and row.credit_number:
        return row.credit_number
    if kind in (vo.INVOICE_DOC, vo.RECEIPT_DOC, vo.REMINDER_DOC, vo.CREDIT_DOC) and row.number:
        return row.number
    return str(order.object_id) if order is not None else str(row.id)


def _facts(db: Session, row: Voucher, kind: str, party: int,
           actor: Optional[UserProfile], theirs: dict[str, Any]) -> list[tuple[str, str]]:
    order = db.query(Order).filter(Order.id == row.order_id).first()
    facts = [("Nummer", escape(_number(row, kind, order))), ("Datum", _day(clock.today()))]
    if kind == vo.OFFER_DOC and vs.valid_until(db, row):
        facts.append(("Gültig bis", _day(vs.valid_until(db, row))))
    if row.agreed_on and kind != vo.OFFER_DOC:
        facts.append(("Bestellt", _day(row.agreed_on)))
    if row.billed_on and kind in (vo.INVOICE_DOC, vo.RECEIPT_DOC, vo.REMINDER_DOC,
                                  vo.CREDIT_DOC):
        facts.append(("Leistungsdatum", _day(row.service_date)))
        if row.due_on and kind != vo.CREDIT_DOC:
            facts.append(("Zahlbar bis", _day(row.due_on)))
    target = vs.corrects(db, row)
    if kind == vo.CREDIT_DOC and (target is not None or row.billed_on):
        ref = target if target is not None else row
        facts.append(("Zu Rechnung", f"{escape(ref.number or '')} vom {_day(ref.billed_on)}"))
    who = actor.display_name if policy.is_staff(actor) else None
    if who:
        facts.append(("Ihr Kontakt", escape(who)))
    if theirs.get("uid"):
        facts.append(("Ihre UID", escape(theirs["uid"])))
    if kind == vo.RECEIPT_DOC:
        facts.append(("Status", '<span class="ok">bezahlt</span>'))
    if kind in (vo.STORNO_DOC,) or (kind == vo.CREDIT_DOC and row.stage == vo.CANCELLED):
        facts.append(("Status", '<span class="bad">storniert</span>'))
    return facts


def _lines(db: Session, row: Voucher, kind: str, doc: a4.Doc) -> None:
    """Positionen, Summe und Steuer – eine Position mit null steht nicht darauf."""
    code = row.currency
    serials = vs.serials_of(db, row)
    for ln in vh.embed_lines(db, row):
        if ln["price"] is None:
            continue
        full = vo.line_net({"quantity": ln["quantity"], "price": ln["price"]}, code)
        net = vo.line_net({"quantity": ln["quantity"], "price": ln["price"],
                           "part": ln["part"]}, code)
        if net == 0:
            continue
        sub = [escape(ln["text"])] if ln.get("text") else []
        if ln.get("article_object_id"):
            sub.append(f"Art. {ln['article_object_id']}")
        # **Welches Stück** – die Seriennummer (Instanznummer) steht auf jedem Dokument.
        numbers = serials.get(ln.get("article_id")) or []
        if numbers:
            word = "Seriennummer" if len(numbers) == 1 else "Seriennummern"
            sub.append(f"{word} {', '.join(str(n) for n in numbers)}")
        if ln["part"] is not None:
            sub.append(f'<span class="part">Teilbetrag {_money(net, code)} von '
                       f'{_money(full, code)}</span>')
        doc.lines.append(a4.Line(
            qty=str(ln["quantity"]), name=ln["article_name"] or "", sub=" · ".join(sub),
            price=_money(Decimal(ln["price"]), code), amount=_money(net, code)))
    if kind == vo.CREDIT_DOC and row.stage == vo.CANCELLED:
        # **Der Storno schreibt nur gut, was Gutschriften nicht schon minderten.**
        rows = vs.storno_split(db, row)
    elif row.billed_on and kind not in (vo.OFFER_DOC, vo.CONFIRM_DOC):
        rows = list(row.vat or [])
    else:
        rows = vo.vat_split(
            [x for x in vs.priced_dicts(db, row) if vo.line_net(x, code) != 0], code)
    totals = vo.totals(rows, code)
    doc.sums = [("Netto", _money(Decimal(totals["net"]), code))] + [
        (f"MWST {vo.vat_label(r.get('vat'))} {Decimal(r.get('rate') or 0):.1f} % auf "
         f"{_money(Decimal(r['net']), code)}", _money(Decimal(r["tax"]), code)) for r in rows]
    doc.notes = [r["note"] for r in rows if r.get("note")]
    doc.total = _money(Decimal(totals["gross"]), code)


def _terms(db: Session, row: Voucher, theirs: dict[str, Any]) -> list[tuple[str, str]]:
    from ..domain import loop as dl
    from . import loop
    out = [("Zahlungsfrist", _days_word(vs.due_days_of(db, row), lead=False)),
           ("Lieferfrist", _days_word(vs.lead_days_of(db, row), lead=True))]
    # **Die Offerte nennt die Wiederholung** – wer zusagt, sagt zur Schlaufe zu (Wiederkehr O16).
    order = db.query(Order).filter(Order.id == row.order_id).first()
    repeat = loop.settings(db, order) if order is not None else None
    if repeat is not None:
        out.append(("Wiederholung", escape(dl.sentence(repeat))))
    if row.incoterm and vh.has_goods(db, row):
        place = vh.incoterm_place_of(db, row)
        out.append(("Lieferbedingung",
                    f"{inc.sentence(row.incoterm, place)} (Incoterms 2020)"))
        ship = [x for x in (theirs.get("shipping") or []) if x not in HOME_LINES]
        if ship:
            out.append(("Lieferung an", ", ".join(ship)))
    return out


def _after(db: Session, row: Voucher, kind: str, party: int) -> str:
    """Was nach den Konditionen steht – je Art ein Satz oder die Zahlungen."""
    if kind == vo.CONFIRM_DOC and row.agreed_on:
        who = vs.named(db, [party])[0]["name"] if party else ""
        return (f'<p class="after">Angenommen am {_day(row.agreed_on)}'
                + (f" durch {escape(who)}" if who else "") + ".</p>")
    if kind == vo.STORNO_DOC:
        return f'<p class="after"><b>Storniert am {_day(row.cancelled_on or clock.today())}.</b></p>'
    if kind == vo.CREDIT_DOC and row.stage == vo.CANCELLED:
        before = vs.credits_of(db, row)
        what = ("die ganze Rechnung" if before <= 0 else
                f"den Rest der Rechnung (abzüglich {_money(before, row.currency)} aus "
                f"früheren Gutschriften)")
        return (f'<p class="after"><b>Gutschrift über {what} {escape(row.number or "")}'
                f'</b> – storniert am {_day(row.cancelled_on or clock.today())}.</p>')
    if kind == vo.RECEIPT_DOC:
        code = row.currency
        rows = "".join(
            f'<span>{_day(e.booked_on)}</span><span>{escape(_entry_text(e))}</span>'
            f'<span class="num" style="text-align:right">{_money(e.amount, code)}</span>'
            for e in vs.entries_of(db, row))
        return (f'<div class="pays num"><span class="lbl" style="grid-column:1/-1;'
                f'margin-bottom:4px">Zahlungen</span>{rows}<span></span><span style="font-weight:'
                f'600">Offen</span><span style="text-align:right;font-weight:600">'
                f'{_money(vs.balance_of(db, row).open, code)}</span></div>')
    return ""


def _entry_text(e) -> str:
    if e.kind == vo.WRITEOFF:
        return f"Ausgebucht – {vo.reason_label(e.reason) or ''}".strip(" –")
    if e.kind == vo.TIP:
        return "Trinkgeld"
    return " · ".join(x for x in (vo.method_name(e.method) or "Zahlung",
                                  e.reference or "") if x)


def _reminder(db: Session, row: Voucher, doc: a4.Doc, level: int) -> None:
    code = row.currency
    money = vs.balance_of(db, row)
    doc.letter = f"<p>{escape(_reminder_text(row, level, row.number or ''))}</p>"
    doc.sums = [("Rechnung", _money(money.charged, code)),
                ("Bereits bezahlt", _money(money.paid + money.written_off, code))]
    doc.total_label = "Offen"
    doc.total = _money(money.open, code)


def _payslip(db: Session, row: Voucher, theirs: dict[str, Any]) -> Optional[a4.Payslip]:
    """►►► **Der Schweizer Zahlteil** – aus denselben QR-Daten wie die Auskunft
    (``voucher.transfer_of``), nur wo er gelten kann. ◄◄◄"""
    if not vs.inbound(row):
        return None
    t = vm.transfer_of(db, row)
    if t.problem:
        return None
    iban = t.iban or ""
    return a4.Payslip(
        iban=" ".join(iban[i:i + 4] for i in range(0, len(iban), 4)),
        creditor=[t.creditor.get("name") or "", t.creditor.get("street") or "",
                  " ".join(x for x in (t.creditor.get("zip"), t.creditor.get("city")) if x)],
        debtor=[x for x in (theirs.get("name"), *(theirs.get("address") or []))
                if x and x not in HOME_LINES],
        reference=" ".join(t.reference[i:i + 4] for i in range(0, len(t.reference), 4)),
        currency=row.currency, amount=_money(t.amount, row.currency).replace("'", " "),
        info=f"Rechnung {t.number}", qr_svg=t.qr)


# ---------------------------------------------------------------------------
# Ausgeben: einfrieren und mailen
# ---------------------------------------------------------------------------

#: ►► **Leise ausgeben** – das Papier entsteht als Dokument, eine Mail nicht. ◄◄ Für die
#: Wiederholung (``services/loop._carry_agreement``): das System führt Anbieten und Zusagen aus,
#: aber hinaus geht nichts von selbst (Projektakte Wiederkehr O1).
_QUIET: ContextVar[bool] = ContextVar("voucher_docs_quiet", default=False)


@contextmanager
def quietly() -> Iterator[None]:
    token = _QUIET.set(True)
    try:
        yield
    finally:
        _QUIET.reset(token)


def issue(db: Session, *, row: Voucher, kind: str, actor: Optional[UserProfile] = None,
          party_id: Optional[int] = None, level: Optional[int] = None
          ) -> Optional[vs.Paper]:
    """►►► **Ein Dokument hinausgeben** – Papier einfrieren, Link, Mail. ◄◄◄ Nur, wo wir den
    Beleg stellen; ohne Adressaten (mehrere angefragt, niemand gewählt) gibt es keinen."""
    if not vo.of(row.direction).collects:
        return None
    party = party_id or vs.party_of(db, row) or vs.addressee_of(db, row)
    if party is None:
        return None
    doc = build(db, row=row, kind=kind, party=party, actor=actor, level=level)
    paper = _file(db, row=row, kind=kind, level=level, doc=doc, party=party, actor=actor)
    link = DocumentLink(token=secrets.token_urlsafe(24), document_id=paper.id,
                        person_object_id=party)
    db.add(link)
    db.flush()
    msg = None if _QUIET.get() else _mail(db, row=row, token=link.token, doc=doc, kind=kind,
                                          party=party, actor=actor, level=level)
    link.message_id = msg.id if msg is not None else None
    db.flush()
    return vs.paper_of_link(link, paper)


def _reminder_text(row: Voucher, level: Optional[int], number: str) -> str:
    """**Der Satz einer Mahnung** – derselbe auf dem Papier und in der Mail."""
    return REMINDER_LEADS[min(level or 1, len(REMINDER_LEADS)) - 1].format(
        number=number, due=_day(row.due_on), billed=_day(row.billed_on))


def _file(db: Session, *, row: Voucher, kind: str, level: Optional[int], doc: a4.Doc,
          party: int, actor: Optional[UserProfile]):
    """►►► **Das Papier ist ein Dokument** – in der einen Ablage, im Pflichtfeld
    ``voucher.doc`` des Zahlungsmoduls (nie löschbar, 10 Jahre) und bei der Partei. ◄◄◄"""
    from . import documents
    order = db.query(Order).filter(Order.id == row.order_id).first()
    person = db.query(UserProfile).filter(UserProfile.object_id == party).first()
    word = vo.document_word(kind, level)
    name = " · ".join(x for x in (doc.number, person.display_name if person else None) if x)
    refs = [documents.RefIn(object_id=order.object_id, part=f"step:{row.step_id}",
                            field="voucher.doc"),
            documents.RefIn(object_id=party)]
    paper, existed = documents.file(
        db, raw=a4.render(doc).encode("utf-8"), filename=f"{word} {doc.number}.html",
        mime="text/html", art=word, name=name or word, source="voucher", refs=refs,
        actor=actor if policy.is_staff(actor) else None,
        facts={"kind": kind, "number": doc.number, "level": level,
               "agb": doc.terms_of.key if doc.terms_of else None})
    if existed:
        documents.add_refs(db, paper, refs, None)
    return paper


def paper_of(db: Session, rec: vs.Paper) -> str:
    """**Das Papier, wie es hinausging** – aus seinem Dokument."""
    from . import documents
    doc = db.query(Document).filter(Document.id == rec.document_id).first()
    raw = documents.raw_of(db, doc)
    return raw.decode("utf-8", "replace") if raw is not None else ""


def _mail(db: Session, *, row: Voucher, token: str, doc: a4.Doc, kind: str,
          party: int, actor: Optional[UserProfile], level: Optional[int]) -> Optional[Message]:
    """**Die Mail zum Dokument** – über das Postfach der Gesellschaft, im Verlauf der Person
    (``outbox.deliver``, wie jede Mail des Hauses)."""
    from . import outbox
    company = vh.issuer_company(db, row)
    if company is None or not getattr(company, "object_id", None):
        return None
    person = db.query(UserProfile).filter(UserProfile.object_id == party).first()
    if person is None:
        return None
    channel = dc.company(company.object_id)
    if kind == vo.REMINDER_DOC:
        title = f"{vo.remind_word(level or 1)} zur Rechnung {doc.number}"
        lead = _reminder_text(row, level, doc.number)
        label = "Ihre Rechnung"
    else:
        label, lead = LEADS[kind]
        title = f"{label} {doc.number}"
        due = f", zahlbar bis {_day(row.due_on)}" if row.due_on else ""
        lead = lead.replace("{due}", due)
    body = f"{dc.greeting(person.display_name)}\n\n{lead}"
    paper = mail_layout.Paper(
        stations=list(STATIONS), at=AT.get(kind),
        rows=[(ln.qty, ln.name, ln.amount) for ln in doc.lines],
        total_label=f"{doc.total_label} {doc.currency}", total=doc.total,
        label=label, url=vs.public_link(token),
        tax=(doc.sums[1] if len(doc.sums) == 2 and kind != vo.REMINDER_DOC else None))
    return outbox.deliver(db, channel=channel, to=[party], subject=title, lead=body,
                          author=actor, extra=mail_layout.Extra(paper=paper))


def preview(db: Session, *, order: Order, step: Any, action: str, payload: dict[str, Any],
            actor: Optional[UserProfile]) -> list[dict[str, Any]]:
    """►►► **Vorschau: was diese Handlung hinausgäbe – ohne dass etwas geschieht.** ◄◄◄

    Dieselbe Handlung (``voucher_actions.apply``) läuft in einem Savepoint, die entstandenen Papiere
    werden gelesen, dann wird alles zurückgerollt – es gibt keine zweite Druckstelle, die vom
    echten Papier abweichen könnte. Mails gehen ohnehin erst nach dem Festschreiben."""
    row = vs.of_step(db, step.id)
    before = {d.id for d in vs.documents_of(db, row)}
    from . import attachments
    sp = db.begin_nested()
    try:
        with attachments.in_database():       # zurückgerollt: nichts in den Bucket
            va.apply(db, order=order, step=step, action=action, payload=payload, actor=actor)
            db.flush()
            return [{"word": vo.document_word(d.kind, d.level), "number": d.number,
                     "html": paper_of(db, d)}
                    for d in vs.documents_of(db, vs.of_step(db, step.id)) if d.id not in before]
    finally:
        sp.rollback()
        db.expire_all()


# ---------------------------------------------------------------------------
# Die Seite der Partei – ein Papier über seinen Link, ohne Anmeldung (``/dokument``)
# ---------------------------------------------------------------------------

#: Die Stationen, wie die Partei sie liest – wer dran ist und was geschieht.
WAY = (("Sie", "Offerte", "Sie prüfen die Positionen und nehmen die Offerte an."),
       ("Wir", "Auftragsbestätigung", "Wir bestätigen Ihren Auftrag und liefern termingerecht."),
       ("Sie", "Rechnung", "Sie bezahlen bequem mit Karte oder mit der QR-Rechnung."),
       ("Erledigt", "Bezahlt", "Alles beglichen. Die Quittung bleibt hier abrufbar."))


def deal_of(db: Session, link: DocumentLink) -> Optional[tuple[Voucher, vs.Paper]]:
    """►► **Ist das Dokument hinter dem Link ein Papier eines Belegs?** – dann der Beleg und das
    Papier, sonst ``None``. Erkannt am Pflichtfeld ``voucher.doc`` (``step:<Modul>``), nicht an
    einer eigenen Tabelle: jedes Papier ist ein gewöhnliches Dokument mit gewöhnlichem Link. ◄◄"""
    ref = (db.query(DocumentRef)
           .filter(DocumentRef.document_id == link.document_id,
                   DocumentRef.field == "voucher.doc", DocumentRef.is_active.is_(True))
           .first())
    kind, _, step = (ref.part or "").partition(":") if ref is not None else ("", "", "")
    if kind != "step" or not step.isdigit():
        return None
    row = db.query(Voucher).filter(Voucher.step_id == int(step)).first()
    doc = db.query(Document).filter(Document.id == link.document_id).first()
    if row is None or doc is None:
        return None
    return row, vs.paper_of_link(link, doc)


def party_user(db: Session, rec: vs.Paper) -> Optional[UserProfile]:
    """**Wer den Link hat, handelt als die Partei, an die das Papier ging** – dieselben
    Verben wie im ERP, dieselbe Antwort von ``can``."""
    return (db.query(UserProfile).filter(UserProfile.object_id == rec.party_id).first()
            if rec.party_id is not None else None)


#: Was die Partei auf der Seite tun kann – und welches Verb des Belegs es ist.
PUBLIC_VERBS = {"agree": "agree", "reject": "decline"}


def public_view(db: Session, row: Voucher, rec: vs.Paper) -> dict[str, Any]:
    """►►► **Was die Seite zu einem Papier zeigt** – das eingefrorene Papier, der Weg, die
    Handlungen (aus ``can``, als die Partei) und, wo nötig, ein Satz. ◄◄◄

    **Ein überholter Link** (eine neuere Offerte an dieselbe Partei) zeigt sein Papier mit
    «nicht mehr gültig» und dem Link zur aktuellen Fassung – angenommen werden kann nur
    sie. Ist der Beleg weiter, zeigt ein alter Link das neueste Papier.
    """
    newest = [d for d in vs.documents_of(db, row)
              if d.party_id == rec.party_id and d.kind != vo.REMINDER_DOC]
    latest = newest[-1] if newest else rec
    note, shown = None, rec
    if latest.id != rec.id:
        if rec.kind == vo.OFFER_DOC and latest.kind == vo.OFFER_DOC:
            note = {"kind": "outdated", "title": "Diese Fassung ist nicht mehr gültig.",
                    "text": (f"Wir haben die Offerte am "
                             f"{_day(latest.created_at.astimezone(clock.ZONE).date())} "
                             f"überarbeitet. Angenommen werden kann nur die aktuelle Fassung."),
                    "link": vs.public_link(latest.token)}
        else:
            shown = latest
    viewer = party_user(db, rec)
    allowed = va.can(db, row, viewer) if viewer is not None else []
    actions: list[str] = []
    current = note is None and shown.id == latest.id
    if current and shown.kind == vo.OFFER_DOC:
        actions += [a for a, verb in PUBLIC_VERBS.items() if verb in allowed]
    if current and "pay_online" in allowed:
        actions.append("pay_online")
    if row.stage == vo.OFFER and vs.expired(db, row) and shown.kind == vo.OFFER_DOC:
        company = vh.issuer_company(db, row)
        phone = getattr(company, "phone", None)
        note = note or {"kind": "expired", "title": "Diese Offerte ist abgelaufen.",
                        "text": (f"Sie war {vs.valid_days_of(row)} Tage gültig. Gerne erneuern "
                                 f"wir sie für Sie – rufen Sie uns an"
                                 + (f" unter {phone}" if phone else "")
                                 + " oder antworten Sie auf unsere Mail."),
                        "link": None}
    gone = _gone_for(db, row, rec.party_id)
    if gone:
        note = {"kind": "cancelled", "title": gone[0], "text": gone[1], "link": None}
        actions = []
    paid = vh.is_done(db, row) and shown.kind in (vo.INVOICE_DOC, vo.RECEIPT_DOC)
    word = "Bezahlt" if paid else vo.document_word(shown.kind, shown.level)
    money = vs.balance_of(db, row)
    return {
        "token": shown.token, "kind": shown.kind, "word": word, "number": shown.number,
        "html": paper_of(db, shown), "note": note, "actions": actions,
        "stations": _stations(db, row, closed=bool(gone)),
        "open": cur.money(money.open, row.currency) if money.open > 0 else None,
        "currency": row.currency,
        "agb": shown.agb,
    }


def _gone_for(db: Session, row: Voucher, party: Optional[int]) -> Optional[tuple[str, str]]:
    """►►► **Ist der Vorgang für diese Partei vorbei?** – EINE Regel für zwei Fälle. ◄◄◄

    Storniert ist er für alle. Hat eine **andere** Partei den Zuschlag, ist er für diese
    ebenso zu Ende: sie sieht ihr Papier, aber nicht, wie es mit der anderen weitergeht –
    ihr Weg steht wie bei einem Storno.
    """
    if row.stage == vo.CANCELLED:
        return ("Storniert.", "Dieser Vorgang ist storniert.")
    winner = vs.party_of(db, row) if row.stage != vo.OFFER else None
    if winner is not None and party is not None and winner != party:
        return ("Nicht mehr offen.",
                "Dieser Vorgang ist für Sie abgeschlossen – er ging an eine andere Partei.")
    return None


def _stations(db: Session, row: Voucher, *, closed: bool = False) -> list[dict[str, Any]]:
    """Der Weg – erledigte Stationen, die aktuelle, die kommenden. Ist der Vorgang für den
    Betrachter vorbei (``_gone_for``), steht er still wie bei einem Storno."""
    if vh.is_done(db, row):
        at = 4
    elif row.stage == vo.BILLED:
        at = 2
    elif row.stage == vo.AGREED:
        at = 1
    else:
        at = 0
    if closed:
        at = -1
    return [{"who": w, "title": t, "text": x,
             "state": "done" if (at == 4 or i < at) else ("active" if i == at else "ahead")}
            for i, (w, t, x) in enumerate(WAY)]


def public_act(db: Session, row: Voucher, rec: vs.Paper, action: str) -> None:
    """**Annehmen oder ablehnen – als die Partei**, über dieselbe Tür wie im ERP
    (``voucher_actions.apply``). Nur am aktuellen Papier; ``can`` entscheidet."""
    from ..models import ProcessStep
    view = public_view(db, row, rec)
    if action not in view["actions"] or action not in PUBLIC_VERBS or view["token"] != rec.token:
        raise Conflict("Das geht hier nicht mehr – laden Sie die Seite neu, sie zeigt den aktuellen Stand.")
    order = db.query(Order).filter(Order.id == row.order_id).first()
    step = db.query(ProcessStep).filter(ProcessStep.id == row.step_id).first()
    va.apply(db, order=order, step=step, action=PUBLIC_VERBS[action],
             payload={"party": rec.party_id}, actor=party_user(db, rec))
