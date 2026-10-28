"""►►► **Die Dokumente eines Belegs – so wie sie hinausgehen.** ◄◄◄

Bei jedem Schritt, den die Partei sehen soll (Offerte, Auftragsbestätigung, Rechnung,
Quittung, Stornierung, Gutschrift, Mahnung), entsteht **ein Dokument**: das Papier aus der
einen Vorlage (``services/document``), **eingefroren** (``voucher_documents``, 10 Jahre), mit
einem unerratbaren Link für die Partei – und **eine Mail** über das Postfach der
Gesellschaft, mit diesem Link. Die Mail steht im Verlauf der Person wie jede andere.

Nur, wo **wir** den Beleg stellen (``Direction.collects``): eine Lieferantenrechnung schreibt
niemand für den Lieferanten.

Ohne verbundenes Postfach wird die Mail **nur erfasst** – wie jede andere Mail des Hauses
(``docs/gmail-setup.md``); das Dokument und sein Link gibt es trotzdem.
"""

import secrets
from datetime import date, datetime, timezone
from decimal import Decimal
from html import escape
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..domain import communication as dc
from ..domain import currency as cur
from ..domain import incoterms as inc
from ..domain import voucher as vo
from ..models import Message, Order, UserProfile, Voucher, VoucherDocument
from . import address, document, legal, mail_layout, qrbill, sites
from . import voucher as vs

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
    return d.strftime("%d.%m.%Y") if d else ""


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
          actor: Optional[UserProfile] = None, level: Optional[int] = None) -> document.Doc:
    """►►► **Was auf dem Papier steht** – aus dem Beleg, an einer Stelle. ◄◄◄"""
    order = db.query(Order).filter(Order.id == row.order_id).first()
    head = vs.document_head(db, row, won=True, party_id=party)
    ours, theirs = (head["supplier"], head["customer"])
    company = vs.issuer_company(db, row)
    seat = address.of_company(company) if company is not None else {}
    sender = " · ".join(x for x in (sites.legal_name(company) or "", seat.get("street1") or "",
                                    " ".join(y for y in (seat.get("zip"), seat.get("city"))
                                             if y), ours.get("uid") or "") if x and x != "—")
    to = [theirs.get("name") or "", theirs.get("attn") or "",
          *[x for x in (theirs.get("address") or []) if x not in HOME_LINES]]
    word = (vo.remind_word(level or 1) if kind == vo.REMINDER_DOC
            else vo.DOCUMENTS.get(kind, "Beleg"))
    doc = document.Doc(
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
    facts = [("Nummer", escape(_number(row, kind, order))), ("Datum", _day(date.today()))]
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
    who = actor.display_name if actor is not None and actor.role in vs.STAFF_ROLES else None
    if who:
        facts.append(("Ihr Kontakt", escape(who)))
    if theirs.get("uid"):
        facts.append(("Ihre UID", escape(theirs["uid"])))
    if kind == vo.RECEIPT_DOC:
        facts.append(("Status", '<span class="ok">bezahlt</span>'))
    if kind in (vo.STORNO_DOC,) or (kind == vo.CREDIT_DOC and row.stage == vo.CANCELLED):
        facts.append(("Status", '<span class="bad">storniert</span>'))
    return facts


def _lines(db: Session, row: Voucher, kind: str, doc: document.Doc) -> None:
    """Positionen, Summe und Steuer – eine Position mit null steht nicht darauf."""
    code = row.currency
    serials = vs.serials_of(db, row)
    for ln in vs.embed_lines(db, row):
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
        doc.lines.append(document.Line(
            qty=str(ln["quantity"]), name=ln["article_name"] or "", sub=" · ".join(sub),
            price=_money(Decimal(ln["price"]), code), amount=_money(net, code)))
    rows = list(row.vat or []) if (row.billed_on and kind != vo.OFFER_DOC
                                    and kind != vo.CONFIRM_DOC) else vo.vat_split(
        [x for x in vs.priced_dicts(db, row) if vo.line_net(x, code) != 0], code)
    totals = vo.totals(rows, code)
    doc.sums = [("Netto", _money(Decimal(totals["net"]), code))] + [
        (f"MWST {vo.vat_label(r.get('vat'))} {Decimal(r.get('rate') or 0):.1f} % auf "
         f"{_money(Decimal(r['net']), code)}", _money(Decimal(r["tax"]), code)) for r in rows]
    doc.notes = [r["note"] for r in rows if r.get("note")]
    doc.total = _money(Decimal(totals["gross"]), code)


def _terms(db: Session, row: Voucher, theirs: dict[str, Any]) -> list[tuple[str, str]]:
    out = [("Zahlungsfrist", _days_word(vs.due_days_of(db, row), lead=False)),
           ("Lieferfrist", _days_word(vs.lead_days_of(db, row), lead=True))]
    if row.incoterm and vs.has_goods(db, row):
        place = vs.incoterm_place_of(db, row)
        out.append(("Lieferbedingung",
                    f"{inc.sentence(row.incoterm, place)} (Incoterms 2020)"))
        ship = [x for x in (theirs.get("shipping") or []) if x not in HOME_LINES]
        if ship:
            out.append(("Lieferung an", ", ".join(ship)))
    return out


def _after(db: Session, row: Voucher, kind: str, party: int) -> str:
    """Was nach den Konditionen steht – je Art ein Satz oder die Zahlungen."""
    if kind == vo.CONFIRM_DOC and row.agreed_on:
        who = vs._named(db, [party])[0]["name"] if party else ""
        return (f'<p class="after">Angenommen am {_day(row.agreed_on)}'
                + (f" durch {escape(who)}" if who else "") + ".</p>")
    if kind == vo.STORNO_DOC:
        return f'<p class="after"><b>Storniert am {_day(row.cancelled_on or date.today())}.</b></p>'
    if kind == vo.CREDIT_DOC and row.stage == vo.CANCELLED:
        return (f'<p class="after"><b>Gutschrift über die ganze Rechnung {escape(row.number or "")}'
                f'</b> – storniert am {_day(row.cancelled_on or date.today())}.</p>')
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


def _reminder(db: Session, row: Voucher, doc: document.Doc, level: int) -> None:
    code = row.currency
    money = vs.balance_of(db, row)
    text = REMINDER_LEADS[min(level, 3) - 1].format(
        number=row.number or "", due=_day(row.due_on), billed=_day(row.billed_on))
    doc.letter = f"<p>{escape(text)}</p>"
    doc.sums = [("Rechnung", _money(money.charged, code)),
                ("Bereits bezahlt", _money(money.paid + money.written_off, code))]
    doc.total_label = "Offen"
    doc.total = _money(money.open, code)


def _payslip(db: Session, row: Voucher, theirs: dict[str, Any]) -> Optional[document.Payslip]:
    """►►► **Der Schweizer Zahlteil** – nur, wo er gelten kann (``qrbill.problem``). ◄◄◄"""
    company = vs.issuer_company(db, row)
    iban = getattr(company, "iban", None)
    amount = vs.balance_of(db, row).open
    if not vs.inbound(row) or amount <= 0 or qrbill.problem(
            iban=iban, currency=row.currency, amount=amount):
        return None
    creditor = dict((row.head or {}).get("creditor") or vs._creditor(db, row))
    who = vs.billing_of(db, row)
    seat = who.get("address") or {}
    debtor = {"name": who.get("name") or "", "street": seat.get("line1"), "street_nr": "",
              "zip": seat.get("postal_code"), "city": seat.get("city"),
              "country": seat.get("country")}
    number = row.number or str(row.id)
    ref = qrbill.reference(number)
    return document.Payslip(
        iban=" ".join(iban[i:i + 4] for i in range(0, len(iban), 4)) if iban else "",
        creditor=[creditor.get("name") or "", creditor.get("street") or "",
                  " ".join(x for x in (creditor.get("zip"), creditor.get("city")) if x)],
        debtor=[x for x in (theirs.get("name"), *(theirs.get("address") or []))
                if x and x not in HOME_LINES],
        reference=" ".join(ref[i:i + 4] for i in range(0, len(ref), 4)),
        currency=row.currency, amount=_money(amount, row.currency).replace("'", " "),
        info=f"Rechnung {number}",
        qr_svg=qrbill.svg(qrbill.payload(iban=iban or "", creditor=creditor, amount=amount,
                                         currency=row.currency, debtor=debtor,
                                         number=number)))


# ---------------------------------------------------------------------------
# Ausgeben: einfrieren und mailen
# ---------------------------------------------------------------------------

def issue(db: Session, *, row: Voucher, kind: str, actor: Optional[UserProfile] = None,
          party_id: Optional[int] = None, level: Optional[int] = None
          ) -> Optional[VoucherDocument]:
    """►►► **Ein Dokument hinausgeben** – Papier einfrieren, Link, Mail. ◄◄◄ Nur, wo wir den
    Beleg stellen; ohne Adressaten (mehrere angefragt, niemand gewählt) gibt es keinen."""
    if not vo.of(row.direction).collects:
        return None
    party = party_id or vs.party_of(db, row) or vs.addressee_of(db, row)
    if party is None:
        return None
    doc = build(db, row=row, kind=kind, party=party, actor=actor, level=level)
    paper = _file(db, row=row, kind=kind, level=level, doc=doc, party=party, actor=actor)
    rec = VoucherDocument(voucher_id=row.id, kind=kind, level=level, number=doc.number,
                          party_id=party, token=secrets.token_urlsafe(24),
                          document_id=paper.id,
                          agb=doc.terms_of.key if doc.terms_of else None)
    db.add(rec)
    db.flush()
    msg = _mail(db, row=row, rec=rec, doc=doc, kind=kind, party=party, actor=actor,
                level=level)
    rec.message_id = msg.id if msg is not None else None
    db.flush()
    return rec


def word_of(kind: str, level: Optional[int] = None) -> str:
    """Das Wort eines Papiers – «Rechnung», «1. Mahnung» …"""
    return (vo.remind_word(level or 1) if kind == vo.REMINDER_DOC
            else vo.DOCUMENTS.get(kind, "Beleg"))


def _file(db: Session, *, row: Voucher, kind: str, level: Optional[int], doc: document.Doc,
          party: int, actor: Optional[UserProfile]):
    """►►► **Das Papier ist ein Dokument** – in der einen Ablage, im Pflichtfeld
    ``voucher.doc`` des Zahlungsmoduls (nie löschbar, 10 Jahre) und bei der Partei. ◄◄◄"""
    from . import documents
    order = db.query(Order).filter(Order.id == row.order_id).first()
    person = db.query(UserProfile).filter(UserProfile.object_id == party).first()
    word = word_of(kind, level)
    name = " · ".join(x for x in (doc.number, person.display_name if person else None) if x)
    refs = [documents.RefIn(object_id=order.object_id, part=f"step:{row.step_id}",
                            field="voucher.doc"),
            documents.RefIn(object_id=party)]
    paper, existed = documents.file(
        db, raw=document.render(doc).encode("utf-8"), filename=f"{word} {doc.number}.html",
        mime="text/html", art=word, name=name or word, source="voucher", refs=refs,
        actor=actor if actor is not None and actor.role in vs.STAFF_ROLES else None,
        facts={"kind": kind, "number": doc.number})
    if existed:
        documents.add_refs(db, paper, refs, None)
    return paper


def paper_of(db: Session, rec: VoucherDocument) -> str:
    """**Das Papier, wie es hinausging** – aus seinem Dokument."""
    from ..models import Document
    from . import documents
    if rec.document_id is not None:
        raw = documents.raw_of(db, db.query(Document).filter(Document.id == rec.document_id).first())
        if raw is not None:
            return raw.decode("utf-8", "replace")
    return rec.html or ""


def _mail(db: Session, *, row: Voucher, rec: VoucherDocument, doc: document.Doc, kind: str,
          party: int, actor: Optional[UserProfile], level: Optional[int]) -> Optional[Message]:
    """**Die Mail zum Dokument** – über das Postfach der Gesellschaft, im Verlauf der Person.
    Ohne verbundenes Postfach wird sie nur erfasst (wie jede Mail des Hauses)."""
    from . import mailbox
    from .communication import write
    company = vs.issuer_company(db, row)
    if company is None or not getattr(company, "object_id", None):
        return None
    person = db.query(UserProfile).filter(UserProfile.object_id == party).first()
    if person is None:
        return None
    channel = dc.company(company.object_id)
    box = mailbox.active(db, channel) if mailbox.ready() else None
    live = box is not None and not box.problem
    if kind == vo.REMINDER_DOC:
        title = f"{vo.remind_word(level or 1)} zur Rechnung {doc.number}"
        lead = REMINDER_LEADS[min(level or 1, 3) - 1].format(
            number=doc.number, due=_day(row.due_on), billed=_day(row.billed_on))
        label = "Ihre Rechnung"
    else:
        label, lead = LEADS[kind]
        title = f"{label} {doc.number}"
        due = f", zahlbar bis {_day(row.due_on)}" if row.due_on else ""
        lead = lead.replace("{due}", due)
    body = f"{dc.greeting(person.display_name)}\n\n{lead}"
    firm = mail_layout.firm_of(company, box.address if box else (company.email or ""),
                               (box.picture or "") if box else "")
    paper = mail_layout.Paper(
        stations=list(STATIONS), at=AT.get(kind),
        rows=[(ln.qty, ln.name, ln.amount) for ln in doc.lines],
        total_label=f"{doc.total_label} {doc.currency}", total=doc.total,
        label=label, url=vs.public_link(rec.token),
        tax=(doc.sums[1] if len(doc.sums) == 2 and kind != vo.REMINDER_DOC else None))
    staff = actor is not None and actor.role in vs.STAFF_ROLES and actor.object_id
    signer = mail_layout.Signer(name=actor.display_name) if staff else None
    mail = mail_layout.compose(title, body, firm, signer,
                               extra=mail_layout.Extra(paper=paper))
    sender = (actor.object_id if staff else
              (box.owner_object_id if box is not None else company.object_id))
    msg = Message(sender_object_id=sender, channel=channel, subject=title, body=mail.body,
                  html=mail.html, at=datetime.now(timezone.utc),
                  created_by=actor.id if staff else None, outgoing=live)
    write(db, msg, {"to": [party], "cc": [], "bcc": [], "about": []})
    return msg


def preview(db: Session, *, order: Order, step: Any, action: str, payload: dict[str, Any],
            actor: Optional[UserProfile]) -> list[dict[str, Any]]:
    """►►► **Vorschau: was diese Handlung hinausgäbe – ohne dass etwas geschieht.** ◄◄◄

    Dieselbe Handlung (``voucher.apply``) läuft in einem Savepoint, die entstandenen Papiere
    werden gelesen, dann wird alles zurückgerollt – es gibt keine zweite Druckstelle, die vom
    echten Papier abweichen könnte. Mails gehen ohnehin erst nach dem Festschreiben."""
    row = vs.of_step(db, step.id)
    before = {d.id for d in vs.documents_of(db, row)}
    sp = db.begin_nested()
    try:
        vs.apply(db, order=order, step=step, action=action, payload=payload, actor=actor)
        db.flush()
        return [{"word": word_of(d.kind, d.level), "number": d.number, "html": paper_of(db, d)}
                for d in vs.documents_of(db, vs.of_step(db, step.id)) if d.id not in before]
    finally:
        sp.rollback()
        db.expire_all()


def send_pending(db: Session) -> None:
    """**Was gerade entstanden ist, geht gleich hinaus** – nach dem Festschreiben, über den
    gewöhnlichen Versand (``mailbox.send_due``). Scheitert er, holt der Abgleich nach."""
    from . import mailbox
    if not mailbox.ready():
        return
    try:
        mailbox.send_due(db)
    except Exception as exc:     # der Versand darf die Antwort nie zerlegen
        print(f"WARNING: voucher mail send failed: {exc!r}", flush=True)


# ---------------------------------------------------------------------------
# Die Seite der Partei – ein Dokument über seinen Link, ohne Anmeldung
# ---------------------------------------------------------------------------

#: Die Stationen, wie die Partei sie liest – wer dran ist und was geschieht.
WAY = (("Sie", "Offerte", "Sie prüfen die Positionen und nehmen die Offerte an."),
       ("Wir", "Auftragsbestätigung", "Wir bestätigen Ihren Auftrag und liefern termingerecht."),
       ("Sie", "Rechnung", "Sie bezahlen bequem mit Karte oder mit der QR-Rechnung."),
       ("Erledigt", "Bezahlt", "Alles beglichen. Die Quittung bleibt hier abrufbar."))


def by_token(db: Session, token: str) -> Optional[VoucherDocument]:
    """Das Dokument zu einem Link – oder ``None``."""
    if not token or len(token) > 64:
        return None
    return (db.query(VoucherDocument)
            .filter(VoucherDocument.token == token, VoucherDocument.is_active.is_(True))
            .first())


def party_user(db: Session, rec: VoucherDocument) -> Optional[UserProfile]:
    """**Wer den Link hat, handelt als die Partei, an die das Dokument ging** – dieselben
    Verben wie im ERP, dieselbe Antwort von ``can``."""
    return (db.query(UserProfile).filter(UserProfile.object_id == rec.party_id).first()
            if rec.party_id is not None else None)


def public_view(db: Session, rec: VoucherDocument) -> dict[str, Any]:
    """►►► **Was die Seite der Partei zeigt** – das eingefrorene Papier, der Weg, die
    Handlungen (aus ``can``, als die Partei) und, wo nötig, ein Satz. ◄◄◄

    **Ein überholter Link** (eine neuere Offerte an dieselbe Partei) zeigt sein Papier mit
    «nicht mehr gültig» und dem Link zur aktuellen Fassung – angenommen werden kann nur
    sie. Ist der Beleg weiter, zeigt ein alter Link das neueste Dokument.
    """
    row = db.query(Voucher).filter(Voucher.id == rec.voucher_id).first()
    newest = [d for d in vs.documents_of(db, row)
              if d.party_id == rec.party_id and d.kind != vo.REMINDER_DOC]
    latest = newest[-1] if newest else rec
    note, shown = None, rec
    if latest.id != rec.id:
        if rec.kind == vo.OFFER_DOC and latest.kind == vo.OFFER_DOC:
            note = {"kind": "outdated", "title": "Diese Fassung ist nicht mehr gültig.",
                    "text": (f"Wir haben die Offerte am {_day(latest.created_at.date())} "
                             f"überarbeitet. Angenommen werden kann nur die aktuelle Fassung."),
                    "link": vs.public_link(latest.token)}
        else:
            shown = latest
    viewer = party_user(db, rec)
    allowed = vs.can(db, row, viewer) if viewer is not None else []
    actions: list[str] = []
    current = note is None and shown.id == latest.id
    if current and shown.kind == vo.OFFER_DOC:
        actions += [a for a in ("agree", "decline") if a in allowed]
    if current and "pay_online" in allowed:
        actions.append("pay_online")
    if row.stage == vo.OFFER and vs.expired(db, row) and shown.kind == vo.OFFER_DOC:
        company = vs.issuer_company(db, row)
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
    word = (vo.remind_word(shown.level or 1) if shown.kind == vo.REMINDER_DOC
            else ("Bezahlt" if vs.is_done(db, row) and shown.kind in (
                vo.INVOICE_DOC, vo.RECEIPT_DOC) else vo.DOCUMENTS.get(shown.kind, "Beleg")))
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
    """►►► **Ist der Vorgang für diese Partei vorbei?** – EINE Regel für zwei Fälle (#1227). ◄◄◄

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
    if vs.is_done(db, row):
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


def public_act(db: Session, rec: VoucherDocument, action: str) -> None:
    """**Annehmen oder ablehnen – als die Partei**, über dieselbe Tür wie im ERP
    (``voucher.apply``). Nur am aktuellen Dokument; ``can`` entscheidet."""
    from fastapi import HTTPException
    from ..models import ProcessStep
    view = public_view(db, rec)
    if action not in view["actions"] or view["token"] != rec.token:
        raise HTTPException(status_code=409, detail=(
            "Das geht hier nicht mehr – laden Sie die Seite neu, sie zeigt den aktuellen Stand."))
    row = db.query(Voucher).filter(Voucher.id == rec.voucher_id).first()
    order = db.query(Order).filter(Order.id == row.order_id).first()
    step = db.query(ProcessStep).filter(ProcessStep.id == row.step_id).first()
    vs.apply(db, order=order, step=step, action=action,
             payload={"party": rec.party_id}, actor=party_user(db, rec))
