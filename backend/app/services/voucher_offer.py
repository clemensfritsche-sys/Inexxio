"""►►► **Die Handlungen bis zur Zusage: Kopf, Positionen, Anfrage, Angebot, Zusage.** ◄◄◄

Währung, Aussteller, Lieferbedingung, Konditionen, Partei und Anschrift, Eigentum, Preis,
Anfragen, Angebot, Ablehnen, Zusagen, Zurückziehen. Eingetragen in ``voucher_actions.VERBS``;
ob ein Verb geht, entscheidet dort ``can``.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from ..core import clock
from ..domain import currency as cur
from ..domain import incoterms as inc
from ..domain import modules
from ..domain import voucher as vo
from ..models import (
    Order, OrderUnit, ProcessStep,
    UserProfile, Voucher, VoucherQuote,
)
from . import address_book, sites
from .voucher import (
    addressee_of, fingerprint, lines_of, parties_on,
    priced_dicts, quotes_of,
)
from .voucher_head import (
    account_for, business_possible, destination, fit_to_address, freeze, incoterm_place_of,
    preset_prices, recipient_business, services_of, sync_lines,
)
from ..domain.errors import Conflict, Invalid
from .voucher_input import assert_terms, days_of, int_of, checked_party, target_quote, text_of, weight_of, amount_of
from .voucher_rules import assert_ask, assert_ownership_chosen


def _reject_fixed(step: ProcessStep, data: dict[str, Any]) -> None:
    """Eine Vorgabe des Moduls (``Beleg.presets_of``) ändert man am Modul, nicht am Beleg."""
    fixed = modules.Beleg.presets_of(step.config)
    for key in data:
        if key in fixed and data[key] != fixed[key]:
            raise Conflict(f"«{modules.Beleg.PRESET_LABELS.get(key, key)}» gibt das Modul vor – "
                        f"geändert wird es dort, für jeden künftigen Auftrag.")


def currency(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**In welcher Währung wird gehandelt?** – eine je Beleg, nicht je Zeile.

    **Umgerechnet wird nichts** – den Kurs braucht erst die Buchhaltung. Eine Fremdwährung
    gibt es, wo wir den Preis nennen, nur mit einer Lieferadresse im Ausland (``can``).
    """
    try:
        code = cur.assert_code(data.get("currency"))
    except ValueError as e:
        raise Invalid(str(e))
    # **Ein vorgegebener Preis steht in der Hauswährung** – umgerechnet wird nichts.
    if code != row.currency and preset_prices(db, row, step):
        raise Invalid(f"Die Preise sind im Modul in {row.currency} vorgegeben – die Währung bleibt.")
    row.currency = code


def issuer(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Wer stellt diesen Beleg?** – nur eine unserer Gesellschaften."""
    value = int_of(data.get("issuer"))
    if value is not None:
        sites.require_own(db, value)
    row.issuer_company_id = value


def incoterm(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferbedingung** – nur die Klausel. **Der Ort ist kein Feld**: er folgt aus
    der Klausel und den Anschriften (``incoterm_place_of``)."""
    _reject_fixed(step, {"incoterm": data.get("incoterm")})
    try:
        row.incoterm = inc.assert_incoterm(data.get("incoterm"))
    except ValueError as e:
        raise Invalid(str(e))
    row.incoterm_place = None


def terms(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Fristen und die Gültigkeit** – sofort geschrieben, geprüft erst beim
    Hinausgehen. Nur gesendete Felder wirken; was das Modul vorgibt, steht fest."""
    _reject_fixed(step, {k: data[k] for k in ("payment_days", "lead_days", "valid_days")
                         if k in data})
    for key in ("payment_days", "lead_days", "valid_days"):
        if key in data:
            setattr(row, key, days_of(key, data.get(key)))


def add_party(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
               data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Gegenpartei wählen** – wählen ist nicht anbieten: festgehalten wird nur, wen
    der Beleg betrifft (geprüft von ``checked_party``); hinaus geht er erst mit «Anbieten»."""
    flow = vo.of(row.direction)
    number = checked_party(db, step=step, value=data.get("party"), flow=flow)
    if number is None:
        raise Invalid(f"Ohne Objektnummer gibt es keinen {vo.PARTY}, den man wählen könnte.")
    if number not in parties_on(row):
        row.parties = [*parties_on(row), number]
    db.flush()


def address(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **An wen und wohin** – geschäftlich oder privat, Rechnungs- und Lieferadresse. ◄◄◄

    Aus dem Adressbuch **des Adressaten**, vorbelegt mit seinen Standards. Nur gesendete
    Felder wirken, ``null`` heisst «die Vorgabe». Eine fremde Anschrift wird abgewiesen.
    """
    number = addressee_of(db, row)
    u = (db.query(UserProfile).filter(UserProfile.object_id == number).first()
         if number is not None else None)
    if u is None:
        raise Invalid(f"An wen der Beleg geht, steht noch nicht fest – gewählt wird, sobald genau "
            f"ein {vo.PARTY} dasteht.")
    if "bill_to_company" in data:
        wanted = data.get("bill_to_company")
        if wanted and not business_possible(u):
            raise Invalid(f"«{u.display_name}» handelt hier privat – eine eigene Gesellschaft ist nie "
                f"Gegenpartei, und ohne Firma gibt es kein Geschäftskonto.")
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
        aid = int_of(data.get(key))
        hit = address_book.pick(db, u.id, aid, kind, account) if aid is not None else None
        if aid is not None and (hit is None or hit.id != aid):
            raise Invalid(f"Anschrift {aid} steht nicht im "
                f"{'Geschäftskonto' if account == address_book.BUSINESS else 'Privatkonto'} "
                f"von «{u.display_name}».")
        setattr(row, col, aid)
    fit_to_address(db, row, lines_of(db, row))


def ownership(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
               data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Wem die Stücke danach gehören** – frei wählbar bis zur Zusage, keine
    Prüfung: eine Angabe des Menschen, die im Log steht, wenn die Stücke passieren. ◄◄◄"""
    _reject_fixed(step, {"ownership": data.get("ownership")})
    try:
        row.ownership = vo.assert_ownership(data.get("ownership"))
    except ValueError as e:
        raise Invalid(str(e))


def price(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
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
    fixed = preset_prices(db, row, step)
    for raw in data.get("lines") or []:
        found = rows.get(int_of(raw.get("id")))
        if found is None:
            continue
        if flow.quoted_by == vo.BY_US:
            if "price" in raw:
                price = amount_of(raw.get("price"), row.currency, allow_negative=True)
                # **Was das Modul vorgibt, ändert man am Modul** (wie ``_reject_fixed``).
                if found.article_id in fixed and price != fixed[found.article_id]:
                    raise Invalid("Dieser Preis ist im Modul vorgegeben – ändern lässt er sich dort, "
                        "nicht am Beleg.")
                found.price = price
            if "part" in raw:
                found.part = amount_of(raw.get("part"), row.currency)
            if "vat" in raw:
                try:
                    key = vo.assert_vat(raw.get("vat") or vo.DEFAULT_VAT)
                except ValueError as e:
                    raise Invalid(str(e))
                allowed = vo.vat_choices(service=kinds.get(found.article_id or 0, False),
                                         delivery_country=delivery, seat_country=seat,
                                         business=recipient_business(db, row))
                if key not in allowed:
                    raise Invalid(f"«{vo.vat_label(key)}» gilt hier nicht – die Anschrift lässt "
                        + ", ".join(vo.vat_label(k) for k in allowed) + " zu.")
                found.vat = key
        if "text" in raw:
            found.text = text_of(raw.get("text"), 300)
        if "hs_code" in raw:
            found.hs_code = text_of(raw.get("hs_code"), 12)
        if "origin_country" in raw:
            found.origin_country = text_of(raw.get("origin_country"), 60)
        if "weight_kg" in raw:
            found.weight_kg = weight_of(raw.get("weight_kg"))
    db.flush()


def ask(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
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
    assert_ask(db, row, step, wanted)
    _freeze_units(db, row, order)
    lead, days = row.lead_days, row.payment_days
    priced = priced_dicts(db, row) if flow.quoted_by == vo.BY_US else []
    amount = vo.gross_of(priced, row.currency) if priced else None
    existing = {q.party_id: q for q in quotes_of(db, row)}
    sent: list[int] = []
    for value in wanted:
        number = checked_party(db, step=step, value=value, flow=flow)
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
        q.sent_on = clock.today()
        sent.append(number)
    db.flush()
    # **Wo wir den Preis nennen, geht unsere Offerte hinaus** – und nur diese Fassung gilt.
    if flow.collects:
        row.offered_hash = fingerprint(db, row)
        for number in sent:
            voucher_docs.issue(db, row=row, kind=vo.OFFER_DOC, actor=actor, party_id=number)


def _freeze_units(db: Session, row: Voucher, order: Order) -> None:
    """**Mit dem ersten Hinausgehen frieren die Stücke ein** (``unit_ids``) – ab hier
    spricht der Beleg über genau die, die jetzt offen im Auftrag stehen."""
    if row.unit_ids is None:
        row.unit_ids = sorted(
            int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
                OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None)).all())


def quote(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Offerte der Gegenpartei erfassen** – Betrag, Fristen, ihre Referenz (bei
    einem Online-Kauf die Bestellnummer) und der Link zur Bestellung. Eine Gegenpartei trifft
    ausschliesslich ihre eigene Zeile."""
    line = target_quote(db, row, data, actor)
    if "amount" in data:
        line.amount = amount_of(data.get("amount"), row.currency)
    if "lead_days" in data:
        line.lead_days = days_of("lead_days", data.get("lead_days"))
    if "payment_days" in data:
        line.payment_days = days_of("payment_days", data.get("payment_days"))
    if "reference" in data:
        line.reference = text_of(data.get("reference"), 120)
    if "link" in data:
        line.link = text_of(data.get("link"), 500)
    if line.amount is None:
        raise Invalid("Ohne Betrag ist es keine Offerte.")
    assert_terms(line.lead_days, line.payment_days)
    line.state = vo.QUOTED
    line.sent_on = line.sent_on or clock.today()


def decline(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine Angebotszeile **absagen** – in beide Richtungen dasselbe. Abgesagt ist
    abgesagt: der Preis fällt mit ihr weg."""
    line = target_quote(db, row, data, actor)
    line.state = vo.DECLINED
    line.amount = None
    line.lead_days = None
    line.payment_days = None


def agree(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Den Zuschlag geben** – ab hier ist eine zweite Partei gebunden. ◄◄◄

    Die gewählte Zeile geht auf ``gewaehlt``, und damit steht alles fest. **Bei einer
    Einnahme gilt, was angeboten wurde** – der Betrag der Zeile, nicht eine neue Rechnung
    (ein geänderter Beleg muss zuerst erneut angeboten werden, ``can``). Bei einer
    **Ausgabe** darf die Nutzlast nachverhandeln.

    Der Belegkopf friert ein, der Ort der Lieferbedingung auch; danach ziehen die Stücke
    von selbst weiter (``follow_up``), und die Auftragsbestätigung steht an (``papers_due``) –
    hinaus geht sie mit der Freigabe.
    """
    flow = vo.of(row.direction)
    number = checked_party(db, step=step, value=data.get("party"), flow=flow)
    if number is None:
        raise Invalid(f"Ohne {vo.PARTY} gibt es keine Zusage.")
    line = next((q for q in quotes_of(db, row) if q.party_id == number), None)
    if line is None:
        raise Invalid(f"{vo.PARTY} {number} ist hier nicht angefragt – zugesagt wird an "
                    f"einer Zeile des Angebotsspiegels.")
    if line.state == vo.DECLINED:
        raise Conflict(f"{vo.PARTY} {number} hat abgesagt. Wer doch will, bekommt zuerst "
                    f"wieder ein Angebot.")
    if flow.quoted_by != vo.BY_US:
        if "amount" in data:
            line.amount = amount_of(data.get("amount"), row.currency)
        if "lead_days" in data:
            line.lead_days = days_of("lead_days", data.get("lead_days"))
        if "payment_days" in data:
            line.payment_days = days_of("payment_days", data.get("payment_days"))
    if line.amount is None:
        raise Invalid("Ohne Betrag gibt es keine Zusage.")
    assert_terms(line.lead_days, line.payment_days)
    assert_ownership_chosen(row)
    _freeze_units(db, row, order)
    for other in quotes_of(db, row):
        if other.id != line.id and other.state == vo.CHOSEN:
            other.state = vo.QUOTED
    # **Der Kopf friert ein – VOR dem Stufenwechsel gelesen**, damit ``billing_of`` noch
    # ableitet statt eine leere Kopie zurückzugeben.
    row.head = freeze(db, row, number)
    line.state = vo.CHOSEN
    row.incoterm_place = incoterm_place_of(db, row)
    row.stage = vo.AGREED
    row.agreed_on = clock.today()
    db.flush()


def unask(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Anfrage zurückziehen bzw. eine Wahl zurücknehmen** – diesen Partner von
    diesem Beleg wegnehmen (Soft-Delete), nur vor der Zusage."""
    number = int_of(data.get("party"))
    if number is not None and number in parties_on(row):
        row.parties = [n for n in parties_on(row) if n != number]
        for q in quotes_of(db, row):
            if q.party_id == number:
                q.is_active = False
        db.flush()
        return
    target_quote(db, row, data, actor).is_active = False
    db.flush()
