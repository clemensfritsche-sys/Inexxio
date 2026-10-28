"""►►► **Der Beleg, wie die Karte ihn zeigt** – ``embed_data`` in Abschnitten, die Leiste
(``situation``), Angebotsspiegel, Stufen, Wege zum Geld, die Suche nach der Rechnung, die
eine Gutschrift mindert (``correctable``). ◄◄◄

Nur lesen; die eine Ausnahme ist ``sync_lines`` am Anfang von ``embed_data``.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..core import clock
from ..domain import currency as cur
from ..domain import incoterms as inc
from ..domain import modules
from ..domain import voucher as vo
from ..models import (
    Order, OrderUnit, ProcessEvent, ProcessStep,
    UserProfile, Voucher, VoucherDocument, VoucherEntry, VoucherQuote,
)
from ..models.process_event import KIND_STEP
from . import sites
# Wer ohnehin alles sieht – Personal hat keine verengte Sicht (die eine Stelle).
from .people import STAFF_ROLES
from .voucher import (
    all_declined, amount_text, balance_of, changed_since_offer, chosen_quote, corrects,
    credited, delivery_date, deviation, documents_of, due_days_of, entries_of, expired,
    inbound, is_billed, lead_days_of, minus, named, next_reminder, of_step, overdue,
    ownership_of, party_of, possible_parties, priced_dicts, public_link, quotes_of,
    reading, reminders, units_problem, valid_days_of, valid_until,
)
from .voucher_head import (
    billing_of, document_head, embed_lines, has_goods, incoterm_place_of, is_done,
    is_export, issuer_company, sync_lines, their_side,
)
from .voucher_money import (
    PAPER_VERBS, papers_due, refundable,
)
from .voucher_actions import (
    ask_problem, can, correction_problem, gaps, next_action, reversible,
)


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
    word = vo.document_word(kind)
    return _state("paper", f"{word} steht an", "pending",
                  f"Sie sind dran: {word} prüfen und freigeben", primary="release")


def _cancelled_state(db: Session, row: Voucher) -> dict[str, Any]:
    money = balance_of(db, row)
    if money.open < -vo.SETTLED_TOLERANCE:
        return _state("cancelled", "Storniert", "danger",
                      f"{amount_text(-money.open, row.currency)} gehören dem "
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
        days = (clock.today() - valid_until(db, row)).days
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
                      f"{sign}{amount_text(abs(gap), row.currency)} zur Zusage – Sie sind dran",
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
        rest = f"{amount_text(-money.open, row.currency)} {verb} {whose}" + (
            "" if whose == "dem Kunden" else " zu")
        return _state("overpaid", "Zu viel bezahlt", "danger", rest, primary="refund")
    proof = " · Ausfuhrnachweis fehlt" if export_open else ""
    if overdue(db, row):
        return _overdue_state(db, row, proof)
    if money.paid > 0 and money.open < vo.SMALL_REST:
        return _state("short", "Zu wenig bezahlt", "pending",
                      f"es fehlen {amount_text(money.open, row.currency)} – offen lassen oder "
                      f"ausbuchen", primary="writeoff")
    if minus(row):
        return _state("open", "Gutschrift gestellt", "pending",
                      f"wir erstatten {amount_text(money.open, row.currency)}{proof}",
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
    days = (clock.today() - row.due_on).days if row.due_on else 0
    if nxt is not None and nxt[1] <= clock.today():
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
    amount = amount_text(abs(last.amount), row.currency)
    if last.kind == vo.WRITEOFF:
        return f"{amount} ausgebucht ({vo.reason_label(last.reason) or ''})".replace(" ()", "")
    if last.kind == vo.TIP:
        return f"{amount} als Trinkgeld behalten"
    if last.amount < 0 or minus(row):
        return f"{amount} erstattet"
    if last.method == vo.CARD:
        return "mit Karte bezahlt – nichts mehr zu tun"
    return "bezahlt – nichts mehr zu tun"


def correctable(db: Session, row: Voucher, step: ProcessStep, *,
                search: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """►►► **Welche Rechnungen lassen sich mit diesem Beleg korrigieren?** ◄◄◄

    Gesucht wird über **alle Aufträge** (die Gutschrift gehört dorthin, wo die Ware
    zurückkommt), nach der Rechnungsnummer (``search``, ein Teilstring, in der Datenbank).
    Was erscheint, lässt ``correction_problem`` zu – dieselbe Regel wie das Tor – und es
    betrifft einen der **möglichen** Partner dieses Belegs (``possible_parties``: vor der
    Zusage gibt es noch keinen gebundenen).
    """
    wanted = set(possible_parties(db, row, step))
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
    found = [r for r in rows if party_of(db, r) in wanted
             and correction_problem(db, row, r) is None][:limit]
    numbers = {
        o.id: o.object_id
        for o in db.query(Order).filter(Order.id.in_([r.order_id for r in found] or [0]))
    }
    return [
        {
            "id": r.id,
            "number": r.number,
            "billed_on": r.billed_on,
            "amount": amount_text(r.amount, r.currency),
            "currency": r.currency,
            "order_object_id": numbers.get(r.order_id),
        }
        for r in found
    ]


# ---------------------------------------------------------------------------
# ►► DIE ANTWORT
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _View:
    """**Wer schaut auf welchen Beleg** – einmal bestimmt, an jeden Abschnitt durchgereicht."""

    db: Session
    row: Voucher
    order: Order
    step: ProcessStep
    viewer: Optional[UserProfile]
    flow: vo.Direction
    #: Personal (oder kein Betrachter): sieht alles.
    internal: bool
    #: Darf Zahlen und Gegenseite sehen – Personal oder die Partei mit dem Zuschlag.
    won: bool
    chosen: Optional[VoucherQuote]
    allowed: list[str]


def embed_data(db: Session, *, order: Order, step: ProcessStep,
               viewer: Optional[UserProfile] = None) -> Optional[dict[str, Any]]:
    """►►► **Der Beleg, wie die Karte ihn braucht** – oder ``None``. ◄◄◄

    Alles, was die Oberfläche zum Zeichnen braucht, reist mit (Wörter, Stufen, Leiste,
    Verben, Zahlen, was man tun darf); sie fragt nie nach Richtung oder Modultyp. **Eine
    Gegenpartei sieht nur ihren Teil** – gefiltert wird beim Aufbau (``_View.won``).

    Die Positionen laufen vorher nach (``sync_lines``, der einzige Schreibvorgang auf diesem
    Lesepfad); danach liest ein Lesevorgang (``reading``) jede Zeile einmal.
    """
    row = of_step(db, step.id)
    if row is None:
        return None
    sync_lines(db, row, order, step)
    with reading(db):
        internal = viewer is None or viewer.role in STAFF_ROLES
        chosen = chosen_quote(db, row)
        won = internal or (chosen is not None and viewer is not None
                           and chosen.party_id == viewer.object_id)
        v = _View(db=db, row=row, order=order, step=step, viewer=viewer,
                  flow=vo.of(row.direction), internal=internal, won=won, chosen=chosen,
                  allowed=can(db, row, viewer))
        return {**_embed_words(v), **_embed_bar(v), **_embed_goods(v), **_embed_terms(v),
                **_embed_parties(v), **_embed_invoice(v), **_embed_money(v),
                "documents": ([_document_out(d) for d in documents_of(db, row)]
                              if won else [])}


def _embed_words(v: _View) -> dict[str, Any]:
    """**Die Wörter** – Abschnitte, Kataloge und Beschriftungen, aus ``domain/voucher``."""
    flow, row = v.flow, v.row
    return {
        "direction": row.direction, "label": flow.label, "party_word": vo.PARTY,
        "we_quote": flow.quoted_by == vo.BY_US, "ref_label": flow.reference,
        "minus": minus(row),
        "parties_title": vo.PARTIES_TITLE, "goods_title": vo.GOODS_TITLE,
        "terms_title": vo.TERMS_TITLE, "quotes_title": vo.QUOTES_TITLE,
        "invoice_title": vo.INVOICE_TITLE, "docs_title": vo.DOCS_TITLE,
        "vat_rates": [{"key": r.key, "rate": r.rate, "label": r.label, "note": r.note}
                      for r in vo.VAT_RATES],
        "vat_rate": vo.DEFAULT_VAT, "vat_label": vo.VAT_LABEL,
        "service_date_label": vo.SERVICE_DATE_LABEL,
        "incoterm_label": inc.LABEL, "incoterm_place_label": inc.PLACE_LABEL,
        "incoterms": [{"key": t.key, "label": t.label, "hint": t.hint}
                      for t in inc.INCOTERMS],
        "currencies": [{"code": c, "label": cur.label(c)} for c in cur.CURRENCIES],
        "issuer_label": vo.ISSUER_LABEL,
        "charge_word": vo.charge_word(collects=flow.collects, minus=minus(row)),
        "payment_word": vo.payment_word(minus=minus(row)),
        "sent_word": vo.SENT_WORD, "taken_word": vo.TAKEN_WORD,
        "cancelled_word": vo.CANCELLED_WORD, "pay_online_word": vo.PAY_ONLINE_WORD,
        "refund_online_word": vo.REFUND_ONLINE_WORD, "refund_word": vo.REFUND_WORD,
        "tip_word": vo.TIP_WORD, "write_off_word": vo.WRITE_OFF_WORD,
        "write_off_reasons": [{"key": k, "label": t} for k, t in vo.WRITE_OFF_REASONS],
        "reverse_word": vo.REVERSE_WORD, "method_label": vo.METHOD_LABEL,
        "payment_terms": [{"days": d, "label": name} for d, name in vo.PAYMENT_TERMS],
        "lead_terms": [{"days": d, "label": name} for d, name in vo.LEAD_TERMS],
        "term_free_min": vo.FREE_MIN, "term_free_label": vo.FREE_TERM_LABEL,
        "payment_term_label": vo.PAYMENT_TERM_LABEL, "lead_term_label": vo.LEAD_TERM_LABEL,
        "valid_label": vo.VALID_LABEL,
        "fixed_hint": "Im Modul vorgegeben – wird übernommen, hier nicht änderbar",
        "ownership_label": vo.OWNERSHIP_LABEL,
        "ownership_options": [{"key": k, "label": t} for k, t in vo.OWNERSHIP],
        "corrects_label": vo.CORRECTS_LABEL, "corrects_hint": vo.CORRECTS_HINT,
    }


def _embed_bar(v: _View) -> dict[str, Any]:
    """**Die Leiste und die Handlungen** – Stand, Stufen, ``can``, was ansteht."""
    db, row, flow = v.db, v.row, v.flow
    nxt = next_reminder(db, row)
    return {
        # **«Anbieten» ↔ «Erneut anbieten»** – dieselbe Handlung; das Wort sagt, ob schon
        # etwas hinausging.
        "ask_verb": (f"Erneut {flow.ask_verb.lower()}"
                     if quotes_of(db, row) and flow.collects else flow.ask_verb),
        "state": situation(db, row, order=v.order, step=v.step) if v.internal else None,
        "locked": units_problem(db, row, v.order, v.step) if v.internal else None,
        "remind_word": vo.remind_word(nxt[0]) if nxt else None,
        "remind_from": nxt[1] if nxt else None,
        "undo": vo.UNDO if "revoke" in v.allowed else None,
        "stage": row.stage,
        "stages": _stages(db, row, flow),
        "can": v.allowed,
        # **Was ein Papier hinausgibt, zeigt die Karte vorher** (Vorschau → Freigeben).
        "paper_verbs": list(PAPER_VERBS) if (v.internal and flow.collects) else [],
        "paper_due": (papers_due(db, row) or [None])[0] if v.internal else None,
        "gaps": gaps(db, row, action=next_action(row)) if v.internal else [],
    }


def _embed_goods(v: _View) -> dict[str, Any]:
    """**Positionen, Steuer, Lieferbedingung, Währung, Aussteller.**"""
    db, row = v.db, v.row
    priced = [ln for ln in priced_dicts(db, row) if vo.line_net(ln, row.currency) != 0]
    split = vo.vat_split(priced, row.currency)
    sums = vo.totals(split, row.currency)
    lines = embed_lines(db, row)
    place = incoterm_place_of(db, row)
    return {
        "lines": lines,
        "ask_problem": (ask_problem(db, row, v.step, lines=lines)
                        if "ask" in v.allowed or row.stage == vo.OFFER else None),
        "net": sums["net"] if v.won else None,
        "tax": sums["tax"] if v.won else None,
        #: Brutto unserer Positionen – gerechnet hier, nie im Browser.
        "total": sums["gross"] if (v.won and split) else None,
        "vat_split": split if v.won else [],
        "export": is_export(db, row),
        "incoterm": row.incoterm,
        "incoterm_place": place,
        "incoterm_text": inc.sentence(row.incoterm, place),
        "incoterm_needed": has_goods(db, row),
        "currency": row.currency,
        "currency_label": cur.label(row.currency),
        "currency_decimals": cur.minor_units(row.currency),
        "issuer": getattr(issuer_company(db, row), "object_id", None),
        "issuers": ([{"object_id": c.object_id, "name": sites.legal_name(c)}
                     for c in sites.selectable_companies(db)] if v.internal else []),
    }


def _embed_terms(v: _View) -> dict[str, Any]:
    """**Fristen, Gültigkeit, Eigentum** – und was das Modul davon vorgibt."""
    db, row, won = v.db, v.row, v.won
    return {
        "prepaid": vo.prepaid(due_days_of(db, row)),
        "valid_days": valid_days_of(row) if v.flow.quoted_by == vo.BY_US else None,
        "valid_until": valid_until(db, row),
        "expired": expired(db, row),
        "changed": changed_since_offer(db, row),
        "fixed": sorted(modules.Beleg.presets_of(v.step.config)),
        "ownership": ownership_of(row),
        "due_days": due_days_of(db, row) if won else None,
        "lead_days": lead_days_of(db, row) if won else None,
        "agreed_on": row.agreed_on if won else None,
        "cancelled_on": row.cancelled_on if won else None,
        "cancel_note": row.cancel_note if v.internal else None,
        "due_date": delivery_date(db, row) if won else None,
    }


def _embed_parties(v: _View) -> dict[str, Any]:
    """**Die Parteien** – Belegkopf, Angebotsspiegel, mögliche Empfänger."""
    db, row, step = v.db, v.row, v.step
    party = v.chosen.party_id if v.chosen is not None else None
    return {
        **document_head(db, row, won=v.won, internal=v.internal),
        "allowed": (named(db, modules.Beleg.parties_allowed(step.config))
                    if v.internal else []),
        "quotes": _quotes(db, row, step, viewer=v.viewer, internal=v.internal),
        "recipients": ([their_side(db, row, n, internal=True)
                        for n in possible_parties(db, row, step)] if v.internal else []),
        "party_object_id": party if v.won else None,
        "party_name": named(db, [party])[0]["name"] if party and v.won else None,
        "amount": (amount_text(v.chosen.amount, row.currency)
                   if (v.chosen is not None and v.won) else None),
    }


def _embed_invoice(v: _View) -> dict[str, Any]:
    """**Die Rechnung** – Nummer, Daten, Bezug, Lieferantenrechnung, Ausfuhrnachweis."""
    db, row, won = v.db, v.row, v.won
    target = corrects(db, row) if won else None
    return {
        "invoice": ({
            "number": row.number, "billed_on": row.billed_on, "due_on": row.due_on,
            "amount": amount_text(row.amount, row.currency), "vat": list(row.vat or []),
            "net": vo.totals(list(row.vat), row.currency)["net"] if row.vat else None,
            "service_date": row.service_date, "overdue": overdue(db, row),
            **_invoice_state(db, row),
        } if (is_billed(row) and won) else None),
        "credit_number": row.credit_number if won else None,
        "corrects": ({"id": target.id, "number": target.number,
                      "billed_on": target.billed_on,
                      "amount": amount_text(target.amount, target.currency)}
                     if target is not None else None),
        "corrects_suggested": (suggested_corrections(db, row, v.order)
                               if v.internal and row.stage == vo.OFFER else []),
        "party_uid": row.party_uid if won else None,
        "original": ((row.original_id or _field_doc(db, row, v.order, "voucher.original"))
                     if won else None),
        "deviation": amount_text(deviation(db, row), row.currency) if won else None,
        "deviation_note": row.deviation_note if won else None,
        "export_number": row.export_number if won else None,
        "export_photo": ((row.export_photo_id
                          or _field_doc(db, row, v.order, "voucher.export"))
                         if won else None),
    }


def _invoice_state(db: Session, row: Voucher) -> dict[str, str]:
    """Wie steht die gestellte Rechnung – Schlüssel, Wort, Ton (``vo.invoice_state``)."""
    if not is_billed(row):
        return {}
    money = balance_of(db, row)
    return vo.invoice_state(money.charged, money.open, overdue=overdue(db, row))


def _embed_money(v: _View) -> dict[str, Any]:
    """**Das Geld** – Saldo, Zustand, Wege, Geld-Zeilen."""
    db, row, won, allowed = v.db, v.row, v.won, v.allowed
    money = balance_of(db, row)
    state = _invoice_state(db, row) if won else {}
    refund_ids = ({e.id for e in refundable(db, row)}
                  if "refund_online" in allowed else set())
    undoable = {e.id for e in reversible(db, row)} if "reverse" in allowed else set()
    shown = (lambda value: amount_text(value, row.currency) if won else None)
    return {
        "charged": shown(money.charged), "credited": shown(money.credited),
        "paid": shown(money.paid), "written_off": shown(money.written_off),
        "tips": shown(money.tips), "open": shown(money.open),
        "open_state": state.get("state"), "open_state_label": state.get("state_label"),
        "open_state_tone": state.get("state_tone"),
        "next_payment": shown(money.next_payment),
        "settled": money.settled if won else False,
        "done": is_done(db, row),
        "ways": (_ways(allowed, inbound=inbound(row), minus=minus(row))
                 if (is_billed(row) and won) else []),
        "entries": [_entry_out(e, row, refundable=e.id in refund_ids,
                               reversible=e.id in undoable)
                    for e in (entries_of(db, row) if won else [])],
    }


def _entry_out(e: VoucherEntry, row: Voucher, *, refundable: bool,
               reversible: bool) -> dict[str, Any]:
    """Eine Geld-Zeile, wie die Karte sie zeigt."""
    return {
        "id": e.id, "amount": amount_text(e.amount, row.currency), "booked_on": e.booked_on,
        "reference": e.reference, "note": e.note, "booked_at": e.created_at,
        "method": e.method, "method_label": vo.method_name(e.method), "kind": e.kind,
        "reason": e.reason, "reason_label": vo.reason_label(e.reason),
        "reverses_id": e.reverses_id, "iban": e.iban,
        "refundable": refundable, "reversible": reversible,
    }


def _document_out(d: VoucherDocument) -> dict[str, Any]:
    """Ein Dokument in der Liste der Karte – Art, Wort, Nummer, Zeitpunkt, Link."""
    word = vo.document_word(d.kind, d.level)
    return {"id": d.id, "kind": d.kind, "label": word, "number": d.number,
            "sent_at": d.created_at, "url": public_link(d.token)}


def _field_doc(db: Session, row: Voucher, order: Order, field: str) -> Optional[int]:
    """Das Dokument, das schon im Feld des Moduls steht (vor dem Buchen) – die Maske übernimmt
    es, statt danach zu fragen."""
    from . import documents
    found = documents.field_document(db, order.object_id, field, f"step:{row.step_id}")
    return found.object_id if found is not None else None


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
             "amount": amount_text(v.amount, v.currency), "currency": v.currency,
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

    **Der Moment reist mit**: ``created_at`` einer Zeile ist der Versand, ``updated_at``
    der gewählten der Zuschlag (danach fasst sie kein Verb mehr an); ``sent_on`` ist der Tag
    auf dem Papier.
    """
    rows = quotes_of(db, row)
    if not internal:
        own = viewer.object_id if viewer else None
        rows = [q for q in rows if q.party_id == own]
    # **Derselbe Name wie im Kopf** – Firma zuerst, «z. H.» darunter.
    named = {q.party_id: (billing_of(db, row, q.party_id).get("lines") or [""])
             for q in rows}
    return [
        {
            "id": q.id,
            "party_object_id": q.party_id,
            "party_name": named[q.party_id][0],
            "party_attn": named[q.party_id][1] if len(named[q.party_id]) > 1 else None,
            "ref": modules.Beleg.ref_for(step.config, q.party_id),
            "amount": amount_text(q.amount, row.currency),
            "lead_days": q.lead_days,
            "payment_days": q.payment_days,
            "state": q.state,
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
