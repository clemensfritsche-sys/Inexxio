"""**Das Zahlungsmodul – jeder entschiedene Fall einmal von vorn bis hinten.**

Die Entscheide stehen im Entscheid-Dokument «Zahlungsmodul – Ziel, Muster, Plan» und im
Mockup; hier wird jeder über die **echten** Dienstpfade gegen PostgreSQL gespielt:
Verkauf mit Dokumenten und Eigentum, Storno in jeder Stufe, Stücke weg, zu wenig / zu viel
bezahlt, falsch erfasst, Mahnung, abgelaufen und überholt, alle abgesagt, Export mit
Nachweis, Dienstleistung ins Ausland, Lieferantenrechnung mit Abweichung, Vorauszahlung,
Teilbetrag, Gutschrift, die Seite der Partei – und die Regel, dass es keine Sackgasse gibt.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.runner import session


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DIE SZENE
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db():
    s = session()
    _house(s)
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _house(db):
    from app.models import CompanySettings
    from app.services import objects as obj, sites
    house = sites.find_operator(db)
    if house is None:
        house = CompanySettings(is_operator=True, is_own=True,
                                object_id=obj.next_object_id(db))
        db.add(house)
    house.company_name = house.company_name or "Inexxio"
    house.legal_form = house.legal_form or "AG"
    house.street = house.street or "Industriestrasse"
    house.street_nr = house.street_nr or "12"
    house.zip_code = house.zip_code or "9430"
    house.city = house.city or "St. Margrethen"
    house.country = house.country or "CH"
    house.vat_number = house.vat_number or "CHE-100.200.300 MWST"
    house.email = house.email or "rechnung@inexxio.test"
    house.phone = house.phone or "+41 71 744 00 00"
    house.iban = house.iban or "CH9300762011623852957"
    db.flush()
    return house


def _person(db, name="Muster AG", *, country="CH", firm=True, own=False):
    from app.models import CompanySettings, UserProfile
    from app.services import address_book, objects as obj, sites
    company = None
    if own:
        company = sites.find_operator(db)
    elif firm:
        company = CompanySettings(object_id=obj.next_object_id(db, "organization"),
                                  company_name=f"{name} {uuid.uuid4().hex[:4]}",
                                  legal_form="AG", email="", country=country)
        db.add(company)
        db.flush()
    user = UserProfile(firebase_uid=f"t-{uuid.uuid4()}",
                       email=f"{uuid.uuid4().hex[:8]}@example.test",
                       first_name="Anna", last_name="Keller",
                       company_object_id=company.object_id if company else None,
                       role="user", object_id=obj.next_object_id(db))
    db.add(user)
    db.flush()
    account = "business" if (company is not None and not own) else "private"
    city = "Altstätten" if country == "CH" else "München"
    address_book.add(db, user, {"account": account, "street1": "Feldstrasse 8",
                                "zip": "9450", "city": city, "country": country}, None)
    db.flush()
    return user


def _article(db, *, service=False, steps=(), capture=True):
    """Ein Artikel – sein Erzeugungsprozess IST der Prozess des Auftrags."""
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=f"Kranhaken {uuid.uuid4().hex[:4]}",
                  unit="stk", serialization="batch", hs_code="848210", origin_country="CH",
                  weight_kg=Decimal("2.5"), is_service=service)
    db.add(art)
    db.flush()
    lead = [{"module_type": "datenerfassung",
             "config": {"points": [{"label": "Sichtprüfung", "type": "bool"}]}}] if capture else []
    tpl.create_steps(db, art, [*lead, *steps])
    db.flush()
    return art


def _scene(db, *, direction="in", party=None, quantity=3, service=False, config=None,
           first=False):
    """Ein Auftrag mit einem Zahlungsmodul nach einer Datenerfassung (oder am Anfang)."""
    from app.models import ProcessStep
    from app.services import process as proc, voucher as svc
    who = party if party is not None else _person(db)
    cfg = {"direction": direction, "parties": [{"party": who.object_id, "ref": "Art. 1"}],
           **(config or {})}
    beleg = {"module_type": "beleg", "config": cfg}
    # ``first``: das Zahlungsmodul steht vorne – die Stücke stehen gleich davor.
    art = _article(db, service=service, steps=[beleg], capture=not first)
    order = proc.release(db, lines=[{"article_object_id": art.object_id,
                                     "quantity": quantity, "origin": "neu", "units": []}],
                         steps=[], actor_id=None)
    db.flush()
    steps = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
             .order_by(ProcessStep.position).all())
    step = next(s for s in steps if s.module_type == "beleg")
    row = svc.of_step(db, step.id)
    return order, step, row, who


def _do(db, order, step, action, actor=None, **payload):
    from app.services import voucher as svc
    row = svc.apply(db, order=order, step=step, action=action, payload=payload, actor=actor)
    db.flush()
    return row


def _ready(db, order, step, row, *, price="320.00", incoterm="FCA", payment_days=30,
           lead_days=5):
    from app.services import voucher as svc
    lines = svc.sync_lines(db, row, order, step)
    _do(db, order, step, "price", lines=[{"id": ln.id, "price": price} for ln in lines])
    if incoterm:
        _do(db, order, step, "incoterm", incoterm=incoterm)
    _do(db, order, step, "terms", payment_days=payment_days, lead_days=lead_days)


def _sold(db, **kw):
    """Angeboten und angenommen – der Normalfall vor der Rechnung."""
    order, step, row, who = _scene(db, first=True, **kw)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    return order, step, row, who


def _billed(db, **kw):
    order, step, row, who = _sold(db, **kw)
    _do(db, order, step, "bill")
    return order, step, row, who


def _staff(db):
    from app.models import UserProfile
    from app.services import objects as obj
    u = UserProfile(firebase_uid=f"s-{uuid.uuid4()}", email=f"{uuid.uuid4().hex[:6]}@x.test",
                    first_name="Clemens", last_name="Fritsche", role="admin",
                    object_id=obj.next_object_id(db))
    db.add(u)
    db.flush()
    return u


# ═══════════════════════════════════════════════════════════════════════════════
# ►► VERKAUF
# ═══════════════════════════════════════════════════════════════════════════════

def test_sale_from_offer_to_done(db):
    """Anbieten → Annehmen → Rechnung → Zahlung: Dokumente, Stücke, Eigentum, erledigt."""
    from app.models import InstanceUnit, OrderUnit, ProcessEvent
    from app.domain import voucher as vo
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    assert svc.situation(db, row, order=order, step=step)["label"] == "Entwurf"
    _do(db, order, step, "ask")
    assert row.unit_ids and len(row.unit_ids) == 3, "Mit dem Anbieten frieren die Stücke ein."
    offers = svc.documents_of(db, row, vo.OFFER_DOC)
    assert len(offers) == 1 and "Offerte" in offers[0].html and "AGB" in offers[0].html
    assert "vom 01.01.2026" in offers[0].html, "Das Dokument nennt das Datum der AGB."
    assert svc.situation(db, row, order=order, step=step)["key"] == "sent"
    _do(db, order, step, "agree", party=who.object_id)
    assert row.stage == vo.AGREED and row.head, "Mit der Zusage friert der Kopf ein."
    assert row.incoterm_place == _house(db).city, "FCA: der Ort ist unsere Versandadresse."
    assert svc.documents_of(db, row, vo.CONFIRM_DOC), "Die Auftragsbestätigung ging hinaus."
    passed = db.query(ProcessEvent).filter(ProcessEvent.step_id == step.id,
                                           ProcessEvent.kind == "step").count()
    assert passed == 3, "Mit der Zusage ziehen die Stücke von selbst weiter."
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(row.unit_ids)).all()
    assert all(u.owner_object_id == who.company.object_id for u in units), (
        "Das Eigentum geht an die Partei – an die Firma, an die verrechnet wird.")
    # Gezeigt wird es an der Einzelinstanz, neben dem Ort – nicht im Prozessbild.
    from app.models import Instance
    from app.routers.instances import instance_units
    inst = db.query(Instance).filter(Instance.id == units[0].instance_id).first()
    page = instance_units(inst.object_id, status=None, limit=60, offset=0, db=db, _=None)
    seen = {u.owner.object_id for u in page.units if u.owner}
    assert seen == {who.company.object_id}, "Die Einzelinstanz sagt, wem sie gehört."
    _do(db, order, step, "bill")
    assert row.number == f"{order.object_id}-1" and row.amount == Decimal("1037.76")
    inv = svc.documents_of(db, row, vo.INVOICE_DOC)
    assert inv and "Zahlteil" in inv[0].html, "Die Rechnung trägt den Schweizer Zahlteil."
    _do(db, order, step, "pay", amount="1037.76", method="transfer")
    assert svc.is_done(db, row), "Saldo null ist erledigt – ohne Knopf."
    assert svc.situation(db, row, order=order, step=step)["key"] == "done"
    assert svc.documents_of(db, row, vo.RECEIPT_DOC), "Die Quittung ging hinaus."
    assert not db.query(OrderUnit).filter(OrderUnit.order_id == order.id,
                                          OrderUnit.current_step_id == step.id,
                                          OrderUnit.released_at.is_(None)).count()


def test_documents_are_mailed_into_the_history(db):
    """Jedes Dokument steht als Mail im Verlauf der Person – mit dem Link der Partei."""
    from app.models import Message, MessageParty
    from app.domain import voucher as vo
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask", actor=_staff(db))
    doc = svc.documents_of(db, row, vo.OFFER_DOC)[0]
    msg = db.query(Message).filter(Message.id == doc.message_id).first()
    assert msg is not None and msg.subject.startswith("Ihre Offerte")
    assert f"/beleg?t={doc.token}" in msg.html, "Die Mail trägt den Link zum Online-Beleg."
    assert db.query(MessageParty).filter(MessageParty.message_id == msg.id,
                                         MessageParty.person_object_id == who.object_id
                                         ).count()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► STORNO
# ═══════════════════════════════════════════════════════════════════════════════

def test_frozen_head_takes_todays_labels(db):
    """Eingefroren ist die Anschrift, nicht ihre Beschriftung: ein bestätigter Beleg zeigt
    die heutigen Wörter, auch wenn der Kopf andere gespeichert hat."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.domain import voucher as vo
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    head = dict(row.head)
    head["ours"] = {**head["ours"], "address_label": "Alt", "shipping_label": "Alt"}
    row.head = head
    flag_modified(row, "head")
    seen = svc.document_head(db, row, won=True)
    assert (seen["supplier"]["address_label"], seen["supplier"]["shipping_label"]) == (
        vo.BILLING_LABEL, vo.SHIPPING_FROM_LABEL)
    assert seen["customer"]["shipping_label"] == vo.SHIPPING_LABEL


def test_storno_after_the_invoice_credits_it_fully(db):
    """Nach der Rechnung entsteht die Gutschrift über die ganze Rechnung von selbst; was
    schon bezahlt ist, geht zurück."""
    from app.domain import voucher as vo
    from app.services import voucher as svc
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="500.00", method="cash")
    _do(db, order, step, "revoke", note="Kulanz")
    assert row.stage == vo.CANCELLED and row.credit_number == f"{order.object_id}-2"
    assert svc.balance_of(db, row).open == Decimal("-500.00")
    assert svc.documents_of(db, row, vo.CREDIT_DOC), "Die Partei bekommt die Gutschrift."
    assert "refund" in svc.can(db, row, None)
    assert svc.situation(db, row, order=order, step=step)["primary"] == "refund"
    _do(db, order, step, "refund", method="cash")
    assert svc.balance_of(db, row).open == 0
    assert svc.situation(db, row, order=order, step=step)["primary"] is None


def test_storno_before_the_offer_went_out_is_not_offered(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    assert "revoke" not in svc.can(db, row, None), "Vor dem ersten Hinausgehen: nichts zu stornieren."


def test_when_units_leave_only_storno_remains(db):
    """Variante C: passt der Beleg nicht mehr zu den Stücken, bleibt nur «Stornieren»."""
    from datetime import datetime, timezone
    from app.models import OrderUnit
    from app.services import voucher as svc
    order, step, row, who = _scene(db)       # Datenerfassung davor: Stücke noch nicht da
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    gone = db.query(OrderUnit).filter(OrderUnit.order_id == order.id).first()
    gone.released_at = datetime.now(timezone.utc)
    db.flush()
    assert svc.can(db, row, None) == ["revoke"]
    state = svc.situation(db, row, order=order, step=step)
    assert state["key"] == "locked" and "1 der 3" in state["text"]


# ═══════════════════════════════════════════════════════════════════════════════
# ►► ZU WENIG, ZU VIEL, FALSCH ERFASST
# ═══════════════════════════════════════════════════════════════════════════════

def test_write_off_settles_the_rest_not_doubles_it(db):
    """Der alte Fehler: aus 0.42 offen wurden 0.84. Jetzt: Ausbuchen mit Grund → null."""
    from app.services import voucher as svc
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="1037.34", method="transfer")
    assert svc.balance_of(db, row).open == Decimal("0.42")
    assert svc.situation(db, row, order=order, step=step)["key"] == "short"
    with pytest.raises(Exception):
        _do(db, order, step, "writeoff")                      # ohne Grund
    _do(db, order, step, "writeoff", reason="rounding")
    assert svc.balance_of(db, row).open == 0 and svc.is_done(db, row)
    assert "ausgebucht (Rundung)" in svc.situation(db, row, order=order, step=step)["text"]


def test_overpaid_refund_or_tip(db):
    from app.domain import voucher as vo
    from app.services import voucher as svc
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="1091.84", method="cash")
    assert svc.balance_of(db, row).open == Decimal("-54.08")
    assert {"refund", "tip"} <= set(svc.can(db, row, None))
    _do(db, order, step, "tip")
    assert svc.is_done(db, row)
    tip = svc.entries_of(db, row)[-1]
    assert tip.kind == vo.TIP and tip.amount == Decimal("54.08")


def test_wrongly_recorded_payment_is_reversed_not_deleted(db):
    from app.services import voucher as svc
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="100.00", method="cash")
    first = svc.entries_of(db, row)[0]
    _do(db, order, step, "reverse", entry=first.id)
    rows = svc.entries_of(db, row)
    assert len(rows) == 2 and rows[1].reverses_id == first.id
    assert svc.balance_of(db, row).paid == 0
    assert "reverse" not in svc.can(db, row, None), "Eine Gegenbuchung bucht man nicht gegen."


def test_the_same_reference_is_booked_only_once(db):
    from fastapi import HTTPException
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="10.00", method="transfer", reference="RF18 0000")
    with pytest.raises(HTTPException):
        _do(db, order, step, "pay", amount="10.00", method="transfer", reference="RF18 0000")


# ═══════════════════════════════════════════════════════════════════════════════
# ►► MAHNUNG
# ═══════════════════════════════════════════════════════════════════════════════

def test_reminders_three_steps_ten_days_apart(db):
    from app.domain import voucher as vo
    from app.services import voucher as svc
    order, step, row, who = _billed(db)
    assert "remind" not in svc.can(db, row, None), "Vor der Fälligkeit wird nicht gemahnt."
    row.due_on = date.today() - timedelta(days=15)
    db.flush()
    assert svc.situation(db, row, order=order, step=step)["primary"] == "remind"
    _do(db, order, step, "remind")
    assert svc.documents_of(db, row, vo.REMINDER_DOC)[0].level == 1
    assert "remind" not in svc.can(db, row, None), "Die nächste Stufe erst nach zehn Tagen."
    state = svc.situation(db, row, order=order, step=step)
    assert state["date"] == date.today() + timedelta(days=10)


# ═══════════════════════════════════════════════════════════════════════════════
# ►► ANGEBOT: ABGELAUFEN, ÜBERHOLT, ALLE ABGESAGT
# ═══════════════════════════════════════════════════════════════════════════════

def test_expired_offer_blocks_accepting_and_offers_again(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    for q in svc.quotes_of(db, row):
        q.sent_on = date.today() - timedelta(days=31)
    db.flush()
    assert svc.expired(db, row) and "agree" not in svc.can(db, row, None)
    assert svc.situation(db, row, order=order, step=step)["primary"] == "ask"
    _do(db, order, step, "ask")
    assert not svc.expired(db, row) and "agree" in svc.can(db, row, None)


def test_a_changed_offer_must_go_out_again(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    lines = svc.lines_of(db, row)
    _do(db, order, step, "price", lines=[{"id": lines[0].id, "price": "300.00"}])
    assert svc.changed_since_offer(db, row) and "agree" not in svc.can(db, row, None)
    _do(db, order, step, "ask")
    assert "agree" in svc.can(db, row, None)


def test_all_declined_offers_choosing_another_partner(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "decline", party=who.object_id)
    state = svc.situation(db, row, order=order, step=step)
    assert state["key"] == "declined" and state["primary"] == "party"


# ═══════════════════════════════════════════════════════════════════════════════
# ►► ADRESSE: STEUER, ORT, ZOLL, WÄHRUNG
# ═══════════════════════════════════════════════════════════════════════════════

def test_export_fixes_the_rate_and_waits_for_the_proof(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True, party=_person(db, country="DE"))
    _ready(db, order, step, row, incoterm="DAP")
    assert all(ln.vat == "export" for ln in svc.lines_of(db, row)), "Ausland: 0 % Export, fest."
    assert "currency" in svc.can(db, row, None), "Fremdwährung nur ins Ausland."
    assert svc.incoterm_place_of(db, row) == "München", "DAP: der Ort ist die Lieferadresse."
    _do(db, order, step, "currency", currency="EUR")
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    _do(db, order, step, "bill")
    _do(db, order, step, "pay", amount=str(row.amount), method="transfer")
    assert not svc.is_done(db, row), "Erledigt erst mit dem Ausfuhrnachweis."
    assert svc.situation(db, row, order=order, step=step)["primary"] == "export"
    from app.models import Attachment
    att = Attachment(token=uuid.uuid4().hex, filename="x.webp", mime="image/webp", data=b"x")
    db.add(att)
    db.flush()
    _do(db, order, step, "export", reference="26CH12345", original=att.id)
    assert svc.is_done(db, row)


def test_domestic_has_no_customs_and_no_foreign_currency(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    assert "currency" not in svc.can(db, row, None)
    assert svc.ask_problem(db, row, step) is None


def test_service_abroad_is_reverse_charge_without_incoterm(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True, party=_person(db, country="DE"),
                                   service=True)
    _ready(db, order, step, row, incoterm=None)
    assert all(ln.vat == "reverse" for ln in svc.lines_of(db, row))
    assert not svc.has_goods(db, row) and svc.ask_problem(db, row, step) is None


def test_our_own_company_is_never_the_counterparty(db):
    from fastapi import HTTPException
    from app.services import voucher as svc
    worker = _person(db, own=True)
    order, step, row, who = _scene(db, first=True, party=worker)
    assert not svc.business_possible(worker)
    with pytest.raises(HTTPException):
        _do(db, order, step, "address", bill_to_company=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ►► EINKAUF: LIEFERANTENRECHNUNG MIT ABWEICHUNG
# ═══════════════════════════════════════════════════════════════════════════════

def test_supplier_invoice_needs_photo_and_a_decision_on_deviation(db):
    from fastapi import HTTPException
    from app.models import Attachment
    from app.services import voucher as svc
    order, step, row, who = _scene(db, direction="out", first=True)
    _do(db, order, step, "incoterm", incoterm="EXW")
    _do(db, order, step, "ask")
    _do(db, order, step, "quote", party=who.object_id, amount="427.00", lead_days=5,
        payment_days=30, reference="AMZ-1", link="https://example.test/o/1")
    _do(db, order, step, "agree", party=who.object_id)
    with pytest.raises(HTTPException):
        _do(db, order, step, "bill", amount="450.00", reference="R-77")
    att = Attachment(token=uuid.uuid4().hex, filename="r.webp", mime="image/webp", data=b"x")
    db.add(att)
    db.flush()
    _do(db, order, step, "bill", amount="450.00", reference="R-77", original=att.id,
        party_uid="CHE-111.222.333 MWST", vat="normal")
    assert svc.deviation(db, row) == Decimal("23.00")
    assert "pay" not in svc.can(db, row, None), "Bezahlt wird erst nach dem Entscheid."
    _do(db, order, step, "accept", note="Fracht nachträglich")
    _do(db, order, step, "pay", amount="450.00", method="card")
    assert svc.is_done(db, row)


# ═══════════════════════════════════════════════════════════════════════════════
# ►► VORAUSZAHLUNG, TEILBETRAG, EIGENTUM, VORGABEN
# ═══════════════════════════════════════════════════════════════════════════════

def test_prepaid_units_wait_for_the_money(db):
    from app.models import ProcessEvent
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row, payment_days=0)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    count = lambda: db.query(ProcessEvent).filter(ProcessEvent.step_id == step.id,  # noqa: E731
                                                  ProcessEvent.kind == "step").count()
    assert count() == 0, "Vorauszahlung: die Stücke warten auf das Geld."
    _do(db, order, step, "bill")
    _do(db, order, step, "pay", amount=str(row.amount), method="transfer")
    assert count() == 3


def test_partial_amount_and_zero_lines(db):
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    line = svc.lines_of(db, row)[0]
    _do(db, order, step, "price", lines=[{"id": line.id, "part": "500.00"}])
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    _do(db, order, step, "bill")
    assert row.amount == Decimal("540.50"), "Nur der Teilbetrag wird verrechnet."


def test_ownership_keep_leaves_the_owner(db):
    from app.models import InstanceUnit
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ownership", ownership="keep")
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(row.unit_ids)).all()
    assert all(u.owner_object_id is None for u in units)


def test_module_presets_are_fixed(db):
    from fastapi import HTTPException
    order, step, row, who = _scene(db, first=True, config={"payment_days": 10})
    assert row.payment_days == 10
    with pytest.raises(HTTPException):
        _do(db, order, step, "terms", payment_days=30)


def test_manual_confirm_of_a_payment_module_is_refused(db):
    from fastapi import HTTPException
    from app.services import process as proc
    order, step, row, who = _scene(db, first=True)
    with pytest.raises(HTTPException) as exc:
        proc.confirm_step(db, order=order, step_id=step.id, values={}, actor_id=None)
    assert "von selbst" in exc.value.detail


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DIE SEITE DER PARTEI
# ═══════════════════════════════════════════════════════════════════════════════

def test_public_page_accepts_only_the_current_offer(db):
    from app.domain import voucher as vo
    from app.services import voucher as svc, voucher_docs as docs
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    old = svc.documents_of(db, row, vo.OFFER_DOC)[-1]
    view = docs.public_view(db, old)
    assert view["actions"] == ["agree", "decline"] and view["word"] == "Offerte"
    lines = svc.lines_of(db, row)
    _do(db, order, step, "price", lines=[{"id": lines[0].id, "price": "300.00"}])
    _do(db, order, step, "ask")
    stale = docs.public_view(db, old)
    assert stale["note"]["kind"] == "outdated" and not stale["actions"]
    new = svc.documents_of(db, row, vo.OFFER_DOC)[-1]
    docs.public_act(db, new, "agree")
    assert row.stage == vo.AGREED
    after = docs.public_view(db, new)
    assert after["word"] == "Auftragsbestätigung" and after["stations"][1]["state"] == "active"
    # Der Empfänger steht wie im ERP: Firma, darunter genau ein «z. H.».
    paper = svc.documents_of(db, row, vo.CONFIRM_DOC)[-1].html
    assert "z. H. " in paper
    assert "z. H. z. H." not in paper


def test_the_other_party_sees_the_offer_closed_like_a_storno(db):
    """#1227: Geht der Zuschlag an eine andere Partei, ist der Vorgang für diese zu Ende –
    dieselbe Anzeige wie ein Storno, kein Fortschritt der anderen, keine Handlung."""
    from app.domain import voucher as vo
    from app.services import voucher as svc, voucher_docs as docs
    a, b = _person(db, "Alpha"), _person(db, "Beta")
    order, step, row, _ = _scene(db, first=True, party=a, config={
        "parties": [{"party": a.object_id}, {"party": b.object_id}]})
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    offers = {d.party_id: d for d in svc.documents_of(db, row, vo.OFFER_DOC)}
    assert set(offers) == {a.object_id, b.object_id}
    docs.public_act(db, offers[a.object_id], "agree")
    lost = docs.public_view(db, offers[b.object_id])
    assert lost["note"]["kind"] == "cancelled" and not lost["actions"]
    assert all(s["state"] != "active" for s in lost["stations"]), "Kein Fortschritt der anderen."
    won = docs.public_view(db, svc.documents_of(db, row, vo.CONFIRM_DOC)[-1])
    assert won["note"] is None and won["stations"][1]["state"] == "active"


def test_public_page_says_when_the_offer_expired(db):
    from app.domain import voucher as vo
    from app.services import voucher as svc, voucher_docs as docs
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    for q in svc.quotes_of(db, row):
        q.sent_on = date.today() - timedelta(days=40)
    db.flush()
    view = docs.public_view(db, svc.documents_of(db, row, vo.OFFER_DOC)[-1])
    assert view["note"]["kind"] == "expired" and "agree" not in view["actions"]


# ═══════════════════════════════════════════════════════════════════════════════
# ►► KEINE SACKGASSE
# ═══════════════════════════════════════════════════════════════════════════════

def test_every_state_has_a_next_step_or_is_an_end(db):
    """Die Leiste ist nie leer: jeder Zustand hat eine nächste Handlung (oder «Stornieren»)
    – leer nur bei Erledigt und Storniert ohne offenen Betrag."""
    from app.schemas.voucher import VoucherState
    from app.services import voucher as svc

    def check(order, step, row):
        state = svc.situation(db, row, order=order, step=step)
        allowed = svc.can(db, row, None)
        # Die Leiste geht so über die API, wie sie gerechnet ist – auch mit Datum.
        assert VoucherState.model_validate(state).date == state.get("date")
        if state["key"] in ("done", "cancelled") and state["primary"] is None:
            return
        assert state["primary"] in allowed or "revoke" in allowed or (
            state["key"] == "sent"), f"Sackgasse: {state}"

    o, s, r, w = _scene(db, first=True)
    check(o, s, r)
    _ready(db, o, s, r)
    check(o, s, r)
    _do(db, o, s, "ask")
    check(o, s, r)
    _do(db, o, s, "agree", party=w.object_id)
    check(o, s, r)
    _do(db, o, s, "bill")
    check(o, s, r)
    _do(db, o, s, "pay", amount="1000.00", method="cash")
    check(o, s, r)
    _do(db, o, s, "revoke")
    check(o, s, r)
