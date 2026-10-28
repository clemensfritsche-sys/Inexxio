"""**Das Zahlungsmodul – jeder entschiedene Fall einmal von vorn bis hinten.**

Die Entscheide stehen im Entscheid-Dokument «Zahlungsmodul – Ziel, Muster, Plan» und im
Mockup; hier wird jeder über die **echten** Dienstpfade gegen PostgreSQL gespielt:
Verkauf mit Dokumenten und Eigentum, Storno in jeder Stufe, Stücke weg, zu wenig / zu viel
bezahlt, falsch erfasst, Mahnung, abgelaufen und überholt, alle abgesagt, Export mit
Nachweis, Dienstleistung ins Ausland, Lieferantenrechnung mit Abweichung, Vorauszahlung,
Teilbetrag, Gutschrift, die Seite der Partei – und die Regel, dass es keine Sackgasse gibt.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from tests.runner import session
from app.core import clock
from app.services import voucher_docs


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
                                object_id=obj.next_object_id(db, "organization"))
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
    _legal_documents(db, house)
    return house


def _legal_documents(db, company):
    """AGB und Datenschutz sind Dokumente der Gesellschaft (``services/legal``) – aus der
    Vorlage, wie die Übernahme beim Start sie anlegt."""
    from app.services import documents, legal
    for kind, field in legal.FIELD_OF.items():
        if legal.document_of(db, company, kind) is None:
            found = legal.template(kind)
            doc = legal._file_template(db, company, kind, found, found[0], None)
            documents.set_field(db, document_object_id=doc.object_id,
                                object_id=company.object_id, part=None, field=field, actor=None)


def _file(db, raw=b"x", mime="image/webp", filename="r.webp"):
    """Ein freigegebenes Dokument – wie es ein Feld des Moduls verlangt."""
    import uuid as _uuid
    from app.services import documents
    doc, _ = documents.file(db, raw=raw + _uuid.uuid4().hex.encode(), filename=filename,
                            mime=mime, art="Rechnung", name="Test", source="file", refs=[],
                            actor=None)
    return doc


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
                       role="user", object_id=obj.next_object_id(db, "user"))
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
    art = Article(object_id=obj.next_object_id(db, "article"), name=f"Kranhaken {uuid.uuid4().hex[:4]}",
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
           first=False, after=False):
    """Ein Auftrag mit einem Zahlungsmodul nach einer Datenerfassung (oder am Anfang)."""
    from app.models import ProcessStep
    from app.services import process as proc, voucher as svc
    who = party if party is not None else _person(db)
    # Eigentum ist Pflicht – im Modul vorgegeben, ausser der Test wählt es selbst (``None``).
    cfg = {"direction": direction, "parties": [{"party": who.object_id, "ref": "Art. 1"}],
           "ownership": "party" if direction == "in" else "us", **(config or {})}
    if cfg.get("ownership") is None:
        cfg.pop("ownership")
    beleg = {"module_type": "beleg", "config": cfg}
    # ``first``: das Zahlungsmodul steht vorne – die Stücke stehen gleich davor.
    tail = [{"module_type": "datenerfassung",
             "config": {"points": [{"label": "OK", "type": "bool"}]}}] if after else []
    art = _article(db, service=service, steps=[beleg, *tail], capture=not first)
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
    from app.services import voucher_actions
    row = voucher_actions.apply(db, order=order, step=step, action=action, payload=payload, actor=actor)
    db.flush()
    return row


def _ready(db, order, step, row, *, price="320.00", incoterm="FCA", payment_days=30,
           lead_days=5):
    from app.services import voucher_head
    lines = voucher_head.sync_lines(db, row, order, step)
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
    _do(db, order, step, "release", kind="confirmation")
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
                    object_id=obj.next_object_id(db, "user"))
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
    from app.services import voucher as svc, voucher_actions, voucher_head, voucher_money, voucher_view
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    assert voucher_view.situation(db, row, order=order, step=step)["label"] == "Entwurf"
    _do(db, order, step, "ask")
    assert row.unit_ids and len(row.unit_ids) == 3, "Mit dem Anbieten frieren die Stücke ein."
    offers = svc.documents_of(db, row, vo.OFFER_DOC)
    paper = voucher_docs.paper_of(db, offers[0])
    assert len(offers) == 1 and "Offerte" in paper and "AGB" in paper
    assert "vom 01.01.2026" in paper, "Das Dokument nennt das Datum der AGB."
    assert voucher_view.situation(db, row, order=order, step=step)["key"] == "sent"
    _do(db, order, step, "agree", party=who.object_id)
    assert row.stage == vo.AGREED and row.head, "Mit der Zusage friert der Kopf ein."
    assert row.incoterm_place == _house(db).city, "FCA: der Ort ist unsere Versandadresse."
    assert not svc.documents_of(db, row, vo.CONFIRM_DOC), "Kein Papier ohne Freigabe."
    assert voucher_view.situation(db, row, order=order, step=step)["primary"] == "release"
    assert voucher_money.papers_due(db, row) == [vo.CONFIRM_DOC] and "release" in voucher_actions.can(db, row, None)
    shown = voucher_docs.preview(db, order=order, step=step, action="release",
                                 payload={"kind": "confirmation"}, actor=None)
    assert [p["word"] for p in shown] == ["Auftragsbestätigung"] and "AGB" in shown[0]["html"]
    assert not svc.documents_of(db, svc.of_step(db, step.id), vo.CONFIRM_DOC), (
        "Die Vorschau gibt nichts hinaus.")
    row = svc.of_step(db, step.id)
    _do(db, order, step, "release", kind="confirmation")
    assert svc.documents_of(db, row, vo.CONFIRM_DOC), "Mit der Freigabe ging sie hinaus."
    assert "release" not in voucher_actions.can(db, row, None), "Ein Papier geht einmal hinaus."
    passed = db.query(ProcessEvent).filter(ProcessEvent.step_id == step.id,
                                           ProcessEvent.kind == "step").count()
    assert passed == 3, "Mit der Zusage ziehen die Stücke von selbst weiter."
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(row.unit_ids)).all()
    from app.domain import statuses as st
    db.expire_all()
    assert all(u.status == st.VERKAUFT for u in units), (
        "Am Ziel wird, was an die Partei ging, «Verkauft» – auch noch unbezahlt.")
    _do(db, order, step, "bill")
    assert row.number == f"{order.object_id}-1" and row.amount == Decimal("1037.76")
    inv = svc.documents_of(db, row, vo.INVOICE_DOC)
    assert inv and "Zahlteil" in voucher_docs.paper_of(db, inv[0]), "Die Rechnung trägt den Schweizer Zahlteil."
    _do(db, order, step, "pay", amount="1037.76", method="transfer")
    assert voucher_head.is_done(db, row), "Saldo null ist erledigt – ohne Knopf."
    assert voucher_view.situation(db, row, order=order, step=step)["key"] == "paper"
    assert not svc.documents_of(db, row, vo.RECEIPT_DOC), "Die Quittung wartet auf die Freigabe."
    _do(db, order, step, "release", kind="receipt")
    assert svc.documents_of(db, row, vo.RECEIPT_DOC), "Die Quittung ging hinaus."
    assert voucher_view.situation(db, row, order=order, step=step)["key"] == "done"
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
    from app.services import voucher_head
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    head = dict(row.head)
    head["ours"] = {**head["ours"], "address_label": "Alt", "shipping_label": "Alt"}
    row.head = head
    flag_modified(row, "head")
    seen = voucher_head.document_head(db, row, won=True)
    assert (seen["supplier"]["address_label"], seen["supplier"]["shipping_label"]) == (
        vo.BILLING_LABEL, vo.SHIPPING_FROM_LABEL)
    assert seen["customer"]["shipping_label"] == vo.SHIPPING_LABEL


def test_storno_after_the_invoice_credits_it_fully(db):
    """Nach der Rechnung entsteht die Gutschrift über die ganze Rechnung von selbst; was
    schon bezahlt ist, geht zurück."""
    from app.domain import voucher as vo
    from app.services import voucher as svc, voucher_actions, voucher_view
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="500.00", method="cash")
    _do(db, order, step, "revoke", note="Kulanz")
    assert row.stage == vo.CANCELLED and row.credit_number == f"{order.object_id}-2"
    assert svc.balance_of(db, row).open == Decimal("-500.00")
    assert svc.documents_of(db, row, vo.CREDIT_DOC), "Die Partei bekommt die Gutschrift."
    assert "refund" in voucher_actions.can(db, row, None)
    assert voucher_view.situation(db, row, order=order, step=step)["primary"] == "refund"
    _do(db, order, step, "refund", method="cash")
    assert svc.balance_of(db, row).open == 0
    assert voucher_view.situation(db, row, order=order, step=step)["primary"] is None


def test_storno_before_the_offer_went_out_is_not_offered(db):
    from app.services import voucher_actions
    order, step, row, who = _scene(db, first=True)
    assert "revoke" not in voucher_actions.can(db, row, None), "Vor dem ersten Hinausgehen: nichts zu stornieren."


def test_when_units_leave_only_storno_remains(db):
    """Variante C: passt der Beleg nicht mehr zu den Stücken, bleibt nur «Stornieren»."""
    from datetime import datetime, timezone
    from app.models import OrderUnit
    from app.services import voucher_actions, voucher_view
    order, step, row, who = _scene(db)       # Datenerfassung davor: Stücke noch nicht da
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    gone = db.query(OrderUnit).filter(OrderUnit.order_id == order.id).first()
    gone.released_at = datetime.now(timezone.utc)
    db.flush()
    assert voucher_actions.can(db, row, None) == ["revoke"]
    state = voucher_view.situation(db, row, order=order, step=step)
    assert state["key"] == "locked" and "1 der 3" in state["text"]


# ═══════════════════════════════════════════════════════════════════════════════
# ►► ZU WENIG, ZU VIEL, FALSCH ERFASST
# ═══════════════════════════════════════════════════════════════════════════════

def test_write_off_settles_the_rest_not_doubles_it(db):
    """Der alte Fehler: aus 0.42 offen wurden 0.84. Jetzt: Ausbuchen mit Grund → null."""
    from app.services import voucher as svc, voucher_head, voucher_view
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="1037.34", method="transfer")
    assert svc.balance_of(db, row).open == Decimal("0.42")
    assert voucher_view.situation(db, row, order=order, step=step)["key"] == "short"
    with pytest.raises(Exception):
        _do(db, order, step, "writeoff")                      # ohne Grund
    _do(db, order, step, "writeoff", reason="rounding")
    assert svc.balance_of(db, row).open == 0 and voucher_head.is_done(db, row)
    _do(db, order, step, "release", kind="receipt")
    assert "ausgebucht (Rundung)" in voucher_view.situation(db, row, order=order, step=step)["text"]


def test_overpaid_refund_or_tip(db):
    from app.domain import voucher as vo
    from app.services import voucher as svc, voucher_actions, voucher_head
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="1091.84", method="cash")
    assert svc.balance_of(db, row).open == Decimal("-54.08")
    assert {"refund", "tip"} <= set(voucher_actions.can(db, row, None))
    _do(db, order, step, "tip")
    assert voucher_head.is_done(db, row)
    tip = svc.entries_of(db, row)[-1]
    assert tip.kind == vo.TIP and tip.amount == Decimal("54.08")


def test_wrongly_recorded_payment_is_reversed_not_deleted(db):
    from app.services import voucher as svc, voucher_actions
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="100.00", method="cash")
    first = svc.entries_of(db, row)[0]
    _do(db, order, step, "reverse", entry=first.id)
    rows = svc.entries_of(db, row)
    assert len(rows) == 2 and rows[1].reverses_id == first.id
    assert svc.balance_of(db, row).paid == 0
    assert "reverse" not in voucher_actions.can(db, row, None), "Eine Gegenbuchung bucht man nicht gegen."


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
    from app.services import voucher as svc, voucher_actions, voucher_view
    order, step, row, who = _billed(db)
    assert "remind" not in voucher_actions.can(db, row, None), "Vor der Fälligkeit wird nicht gemahnt."
    row.due_on = clock.today() - timedelta(days=15)
    db.flush()
    assert voucher_view.situation(db, row, order=order, step=step)["primary"] == "remind"
    _do(db, order, step, "remind")
    assert svc.documents_of(db, row, vo.REMINDER_DOC)[0].level == 1
    assert "remind" not in voucher_actions.can(db, row, None), "Die nächste Stufe erst nach zehn Tagen."
    state = voucher_view.situation(db, row, order=order, step=step)
    assert state["date"] == clock.today() + timedelta(days=10)


# ═══════════════════════════════════════════════════════════════════════════════
# ►► ANGEBOT: ABGELAUFEN, ÜBERHOLT, ALLE ABGESAGT
# ═══════════════════════════════════════════════════════════════════════════════

def test_expired_offer_blocks_accepting_and_offers_again(db):
    from app.services import voucher as svc, voucher_actions, voucher_view
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    for q in svc.quotes_of(db, row):
        q.sent_on = clock.today() - timedelta(days=31)
    db.flush()
    assert svc.expired(db, row) and "agree" not in voucher_actions.can(db, row, None)
    assert voucher_view.situation(db, row, order=order, step=step)["primary"] == "ask"
    _do(db, order, step, "ask")
    assert not svc.expired(db, row) and "agree" in voucher_actions.can(db, row, None)


def test_a_changed_offer_must_go_out_again(db):
    from app.services import voucher as svc, voucher_actions
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    lines = svc.lines_of(db, row)
    _do(db, order, step, "price", lines=[{"id": lines[0].id, "price": "300.00"}])
    assert svc.changed_since_offer(db, row) and "agree" not in voucher_actions.can(db, row, None)
    _do(db, order, step, "ask")
    assert "agree" in voucher_actions.can(db, row, None)


def test_all_declined_offers_choosing_another_partner(db):
    from app.services import voucher_view
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "decline", party=who.object_id)
    state = voucher_view.situation(db, row, order=order, step=step)
    assert state["key"] == "declined" and state["primary"] == "party"


# ═══════════════════════════════════════════════════════════════════════════════
# ►► ADRESSE: STEUER, ORT, ZOLL, WÄHRUNG
# ═══════════════════════════════════════════════════════════════════════════════

def test_export_fixes_the_rate_and_waits_for_the_proof(db):
    from app.services import voucher as svc, voucher_actions, voucher_head, voucher_view
    order, step, row, who = _scene(db, first=True, party=_person(db, country="DE"))
    _ready(db, order, step, row, incoterm="DAP")
    assert all(ln.vat == "export" for ln in svc.lines_of(db, row)), "Ausland: 0 % Export, fest."
    assert "currency" in voucher_actions.can(db, row, None), "Fremdwährung nur ins Ausland."
    assert voucher_head.incoterm_place_of(db, row) == "München", "DAP: der Ort ist die Lieferadresse."
    _do(db, order, step, "currency", currency="EUR")
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    _do(db, order, step, "bill")
    _do(db, order, step, "pay", amount=str(row.amount), method="transfer")
    assert not voucher_head.is_done(db, row), "Erledigt erst mit dem Ausfuhrnachweis."
    assert voucher_view.situation(db, row, order=order, step=step)["primary"] == "export"
    _do(db, order, step, "export", reference="26CH12345", original=_file(db).object_id)
    assert voucher_head.is_done(db, row)


def test_domestic_has_no_customs_and_no_foreign_currency(db):
    from app.services import voucher_actions
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    assert "currency" not in voucher_actions.can(db, row, None)
    assert voucher_actions.ask_problem(db, row, step) is None


def test_service_abroad_is_reverse_charge_without_incoterm(db):
    from app.services import voucher as svc, voucher_actions, voucher_head
    order, step, row, who = _scene(db, first=True, party=_person(db, country="DE"),
                                   service=True)
    _ready(db, order, step, row, incoterm=None)
    assert all(ln.vat == "reverse" for ln in svc.lines_of(db, row))
    assert not voucher_head.has_goods(db, row) and voucher_actions.ask_problem(db, row, step) is None


def test_our_own_company_is_never_the_counterparty(db):
    from fastapi import HTTPException
    from app.services import voucher_head
    worker = _person(db, own=True)
    order, step, row, who = _scene(db, first=True, party=worker)
    assert not voucher_head.business_possible(worker)
    with pytest.raises(HTTPException):
        _do(db, order, step, "address", bill_to_company=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ►► EINKAUF: LIEFERANTENRECHNUNG MIT ABWEICHUNG
# ═══════════════════════════════════════════════════════════════════════════════

def test_supplier_invoice_needs_photo_and_a_decision_on_deviation(db):
    from fastapi import HTTPException
    from app.services import voucher as svc, voucher_actions, voucher_head
    order, step, row, who = _scene(db, direction="out", first=True)
    _do(db, order, step, "incoterm", incoterm="EXW")
    _do(db, order, step, "ask")
    _do(db, order, step, "quote", party=who.object_id, amount="427.00", lead_days=5,
        payment_days=30, reference="AMZ-1", link="https://example.test/o/1")
    _do(db, order, step, "agree", party=who.object_id)
    with pytest.raises(HTTPException):
        _do(db, order, step, "bill", amount="450.00", reference="R-77")
    _do(db, order, step, "bill", amount="450.00", reference="R-77", original=_file(db).object_id,
        party_uid="CHE-111.222.333 MWST", vat="normal")
    assert svc.deviation(db, row) == Decimal("23.00")
    assert "pay" not in voucher_actions.can(db, row, None), "Bezahlt wird erst nach dem Entscheid."
    _do(db, order, step, "accept", note="Fracht nachträglich")
    _do(db, order, step, "pay", amount="450.00", method="card")
    assert voucher_head.is_done(db, row)


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


# ═══════════════════════════════════════════════════════════════════════════════
# ►► EIGENTUM: bewusst gewählt, abgeleitet, am Ziel «Verkauft» oder «Freigegeben»
# ═══════════════════════════════════════════════════════════════════════════════

def _units(db, ids):
    from app.models import InstanceUnit
    db.expire_all()
    return db.query(InstanceUnit).filter(InstanceUnit.id.in_(ids)).all()


def _again(db, units, steps):
    """Ein neuer Auftrag, der genau diese Stücke greift (Retoure, Reparatur)."""
    from app.models import Article, Instance
    from app.services import instances as inst_svc, process as proc
    inst = db.query(Instance).filter(Instance.id == units[0].instance_id).first()
    art = db.query(Article).filter(Article.id == inst.article_id).first()
    picks = [{"number": inst_svc.unit_number(inst, u), "from_order": None} for u in units]
    order = proc.release(db, lines=[{"article_object_id": art.object_id,
                                     "quantity": len(units), "origin": "lager",
                                     "units": picks}], steps=steps, actor_id=None)
    db.flush()
    return order


def _run_capture(db, order):
    """Die Endkontrolle bestätigen – die Stücke gehen ans Ziel."""
    from app.models import Instance, OrderUnit, ProcessStep
    from app.services import process as proc
    step = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id,
                                         ProcessStep.module_type == "datenerfassung")
            .order_by(ProcessStep.position.desc()).first())
    members = db.query(OrderUnit).filter(OrderUnit.order_id == order.id,
                                         OrderUnit.released_at.is_(None)).all()
    from app.models import InstanceUnit
    units = db.query(InstanceUnit).filter(
        InstanceUnit.id.in_([m.instance_unit_id for m in members])).all()
    from tests.support import per_unit
    for iid in {u.instance_id for u in units}:
        inst = db.query(Instance).filter(Instance.id == iid).first()
        proc.confirm_step(db, order=order, step_id=step.id,
                          values=per_unit(db, order=order, step=step,
                                          instance_object_id=inst.object_id),
                          instance_object_id=inst.object_id, verification="manual",
                          actor_id=None)
    db.flush()


def test_ownership_must_be_chosen_and_has_two_options(db):
    """Ohne Wahl kein Anbieten und keine Zusage; «bleibt» gibt es nicht mehr."""
    from fastapi import HTTPException
    from app.domain import voucher as vo
    from app.services import voucher_actions
    order, step, row, who = _scene(db, first=True, config={"ownership": None})
    _ready(db, order, step, row)
    assert "Eigentum" in (voucher_actions.ask_problem(db, row, step) or "")
    with pytest.raises(HTTPException):
        _do(db, order, step, "ask")
    with pytest.raises(HTTPException):
        _do(db, order, step, "ownership", ownership="keep")
    assert [k for k, _ in vo.OWNERSHIP] == [vo.TO_PARTY, vo.TO_US]
    _do(db, order, step, "ownership", ownership=vo.TO_PARTY)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    with pytest.raises(HTTPException):
        _do(db, order, step, "ownership", ownership=vo.TO_US)  # eingefroren mit der Zusage


def test_storno_while_the_pieces_still_run_leaves_them_ours(db):
    """Storno, bevor die Stücke am Ziel sind: kein Zurücksetzen nötig – sie werden frei."""
    from app.domain import statuses as st
    order, step, row, who = _scene(db, first=True, after=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    _do(db, order, step, "revoke")
    _run_capture(db, order)
    assert {u.status for u in _units(db, row.unit_ids)} == {st.FREIGEGEBEN}


def test_sold_keeps_its_place_and_a_purchase_stays_ours(db):
    from app.domain import statuses as st
    from app.models import InstanceUnit
    from app.services import places
    order, step, row, who = _scene(db, first=True, after=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    units = _units(db, row.unit_ids)
    places.place(db, units=units, target=who.object_id)
    db.flush()
    _run_capture(db, order)
    units = _units(db, row.unit_ids)
    assert {u.status for u in units} == {st.VERKAUFT}
    assert all(u.place_object_id == who.object_id for u in units), (
        "«Verkauft» behält seinen Ort – nur Verschrottet verliert ihn.")
    o2, s2, r2, w2 = _scene(db, direction="out", first=True)
    _do(db, o2, s2, "incoterm", incoterm="EXW")
    _do(db, o2, s2, "ask")
    _do(db, o2, s2, "quote", party=w2.object_id, amount="100.00", lead_days=5, payment_days=30)
    _do(db, o2, s2, "agree", party=w2.object_id)
    assert {u.status for u in db.query(InstanceUnit).filter(
        InstanceUnit.id.in_(r2.unit_ids))} == {st.FREIGEGEBEN}, "Einkauf «an uns» bleibt Bestand."


def test_return_repair_and_cancelled_return(db):
    """Reparatur ohne Zahlung: bleibt verkauft. Retoure «an uns»: wieder Bestand. Wird die
    Retoure storniert, gilt wieder der Verkauf – alles aus derselben Ableitung."""
    from app.domain import statuses as st
    from app.models import ProcessStep
    from app.services import voucher as svc
    order, step, row, who = _sold(db)
    units = _units(db, row.unit_ids)
    assert {u.status for u in units} == {st.VERKAUFT}
    fix = _again(db, units, [{"module_type": "datenerfassung",
                              "config": {"points": [{"label": "OK", "type": "bool"}]}}])
    _run_capture(db, fix)
    assert {u.status for u in _units(db, row.unit_ids)} == {st.VERKAUFT}, (
        "Eine Reparatur ohne Zahlungsmodul ändert nichts am Eigentum.")
    back = _again(db, _units(db, row.unit_ids), [
        {"module_type": "beleg", "config": {"direction": "out", "ownership": "us",
                                            "parties": [{"party": who.object_id, "ref": "Retoure"}]}},
        {"module_type": "datenerfassung",
         "config": {"points": [{"label": "OK", "type": "bool"}]}}])
    bstep = db.query(ProcessStep).filter(ProcessStep.order_id == back.id,
                                         ProcessStep.module_type == "beleg").first()
    _do(db, back, bstep, "incoterm", incoterm="EXW")
    _do(db, back, bstep, "ask")
    _do(db, back, bstep, "quote", party=who.object_id, amount="900.00", lead_days=1,
        payment_days=30)
    _do(db, back, bstep, "agree", party=who.object_id)
    assert svc.sold_units(db, row.unit_ids) == set(), "Die Retoure «an uns» hebt den Verkauf auf."
    _do(db, back, bstep, "revoke")
    assert svc.sold_units(db, row.unit_ids) == set(row.unit_ids), (
        "Eine stornierte Retoure zählt nicht – es gilt wieder der Verkauf.")
    _run_capture(db, back)
    assert {u.status for u in _units(db, row.unit_ids)} == {st.VERKAUFT}


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
    from app.services import voucher_docs as docs, voucher as svc
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
    assert after["stations"][1]["state"] == "active" and not after["actions"]
    _do(db, order, step, "release", kind="confirmation")
    after = docs.public_view(db, new)
    assert after["word"] == "Auftragsbestätigung", "Ein alter Link zeigt das neueste Papier."
    # Der Empfänger steht wie im ERP: Firma, darunter genau ein «z. H.».
    paper = voucher_docs.paper_of(db, svc.documents_of(db, row, vo.CONFIRM_DOC)[-1])
    assert "z. H. " in paper
    assert "z. H. z. H." not in paper


def test_the_other_party_sees_the_offer_closed_like_a_storno(db):
    """#1227: Geht der Zuschlag an eine andere Partei, ist der Vorgang für diese zu Ende –
    dieselbe Anzeige wie ein Storno, kein Fortschritt der anderen, keine Handlung."""
    from app.domain import voucher as vo
    from app.services import voucher_docs as docs, voucher as svc
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
    _do(db, order, step, "release", kind="confirmation")
    won = docs.public_view(db, svc.documents_of(db, row, vo.CONFIRM_DOC)[-1])
    assert won["note"] is None and won["stations"][1]["state"] == "active"


def test_public_page_says_when_the_offer_expired(db):
    from app.domain import voucher as vo
    from app.services import voucher_docs as docs, voucher as svc
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    for q in svc.quotes_of(db, row):
        q.sent_on = clock.today() - timedelta(days=40)
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
    from app.services import voucher_actions, voucher_view

    def check(order, step, row):
        state = voucher_view.situation(db, row, order=order, step=step)
        allowed = voucher_actions.can(db, row, None)
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


# ═══════════════════════════════════════════════════════════════════════════════
# ►► CHROME-TEST (Oktober 2026)
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_offer_button_names_everything_that_is_missing(db):
    """Der Hover nennt ALLES, was fehlt – nicht nur den ersten Punkt.

    Bug-Form: der Satz endet beim ersten Fund (Preis), Fristen und Eigentum fehlen."""
    from app.services import voucher_actions, voucher_head
    order, step, row, _who = _scene(db, first=True, config={"ownership": None})
    voucher_head.sync_lines(db, row, order, step)
    problem = voucher_actions.ask_problem(db, row, step) or ""
    for word in ("Preis", "Lieferbedingung", "Lieferfrist", "Eigentum"):
        assert word in problem, f"«{word}» fehlt im Grund: {problem!r}"
    assert problem.count("\n") >= 3, "Die Gründe stehen nicht untereinander."


def test_documents_name_the_serial_number(db):
    """Jedes Dokument nennt die Seriennummer (Instanznummer) der Stücke einer Position.

    Bug-Form: nur Artikel und Artikelnummer stehen darauf."""
    from app.domain import voucher as vo
    from app.models import Instance, InstanceUnit
    from app.services import voucher as svc
    order, step, row, _who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    numbers = sorted({i.object_id for i in db.query(Instance).join(
        InstanceUnit, InstanceUnit.instance_id == Instance.id).filter(
        InstanceUnit.id.in_(row.unit_ids)).all()})
    assert numbers, "Ohne Stücke gibt es nichts zu prüfen."
    html = voucher_docs.paper_of(db, svc.documents_of(db, row, vo.OFFER_DOC)[0])
    assert "Seriennummer" in html and all(str(n) in html for n in numbers), (
        "Die Offerte nennt die Seriennummer nicht.")


def test_a_quote_names_the_party_as_the_head_does(db):
    """Vor und nach dem Anbieten derselbe Name: Firma zuerst, die Person als «z. H.».

    Bug-Form: vor dem Anbieten «Muster AG», danach «Anna Keller»."""
    from app.services import voucher_view
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    staff = _staff(db)
    seen = voucher_view.embed_data(db, order=order, step=step, viewer=staff)
    quote = seen["quotes"][0]
    assert quote["party_name"].startswith("Muster AG"), quote
    assert quote["party_attn"] == "z. H. Anna Keller", quote


def test_the_export_proof_takes_a_pdf(db):
    """Der Ausfuhrnachweis ist ein Dokument – ein PDF bleibt ein PDF.

    Bug-Formen: (a) ein PDF wird als «kein Bild» abgewiesen; (b) es wird umkodiert;
    (c) der Nachweis steht nicht im Pflichtfeld des Moduls."""
    from app.services import documents, voucher_head
    order, step, row, who = _scene(db, first=True, party=_person(db, country="DE"))
    _ready(db, order, step, row, incoterm="DAP")
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    _do(db, order, step, "bill")
    _do(db, order, step, "pay", amount=str(row.amount), method="transfer")
    doc = _file(db, raw=b"%PDF-1.7\n%test\n", mime="application/pdf", filename="v.pdf")
    assert doc.mime == "application/pdf", "(a)"
    assert documents.raw_of(db, doc).startswith(b"%PDF-1.7\n%test\n"), "(b)"
    _do(db, order, step, "export", reference="26CH12345", original=doc.object_id)
    assert voucher_head.is_done(db, row)
    found = documents.field_document(db, order.object_id, "voucher.export", f"step:{step.id}")
    assert found is not None and found.object_id == doc.object_id, "(c)"


# ═══════════════════════════════════════════════════════════════════════════════
# ►► NUMMERN, SPERREN, TORE – die Tiefenanalyse vom Oktober 2026
# ═══════════════════════════════════════════════════════════════════════════════

def _two_sales(db):
    """Ein Auftrag mit ZWEI Einnahme-Modulen hintereinander – dieselbe Partei."""
    from app.models import ProcessStep
    from app.services import process as proc, voucher as svc
    who = _person(db)
    cfg = {"direction": "in", "parties": [{"party": who.object_id}], "ownership": "party"}
    art = _article(db, steps=[{"module_type": "beleg", "config": dict(cfg)},
                              {"module_type": "beleg", "config": dict(cfg)}], capture=False)
    order = proc.release(db, lines=[{"article_object_id": art.object_id, "quantity": 2,
                                     "origin": "neu", "units": []}], steps=[], actor_id=None)
    db.flush()
    steps = [s for s in db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
             .order_by(ProcessStep.position).all() if s.module_type == "beleg"]
    return order, steps, [svc.of_step(db, s.id) for s in steps], who


def test_invoice_and_credit_never_share_a_number(db):
    """Rechnung und Gutschrift sind je ein eigenes Dokument mit eigener Nummer
    (MWSTG Art. 26): A stellen, A stornieren (Gutschrift), B stellen → drei Nummern.

    Bug-Form: die Gutschrift zählt nicht mit – B bekommt die Nummer der Gutschrift."""
    from app.domain import voucher as vo
    from app.services import voucher_docs as docs, voucher as svc
    order, (sa, sb), (a, b), who = _two_sales(db)
    for step, row in ((sa, a), (sb, b)):
        _ready(db, order, step, row)
        _do(db, order, step, "ask")
        _do(db, order, step, "agree", party=who.object_id)
    _do(db, order, sa, "bill")
    _do(db, order, sa, "revoke")
    _do(db, order, sb, "bill")
    numbers = [a.number, a.credit_number, b.number]
    assert numbers == [f"{order.object_id}-{n}" for n in (1, 2, 3)], numbers
    credit = docs.paper_of(db, svc.documents_of(db, a, vo.CREDIT_DOC)[-1])
    assert a.credit_number in credit, "Die Gutschrift trägt ihre eigene Nummer."
    assert f"{a.number} vom {a.billed_on:%d.%m.%Y}" in credit, (
        "Die Gutschrift nennt die Originalrechnung mit Nummer und Datum.")


def test_a_second_bill_waits_for_the_first_and_is_refused():
    """Zweimal «Rechnung stellen» gleichzeitig ist EINE Rechnung und ein 409 – die zweite
    Sitzung wartet an der Sperre des Belegs (``hold``) und sieht danach die Rechnung.

    Gefahren mit zwei echten Sitzungen; die Szene muss dafür festgeschrieben sein.
    Bug-Form: ohne Sperre prüfen beide denselben alten Stand – zwei Rechnungen."""
    import threading
    import time
    from fastapi import HTTPException
    from app.core.database import SessionLocal
    from app.domain import voucher as vo
    from app.models import Order, ProcessStep, Voucher
    from app.services import voucher as svc, voucher_actions
    s = session()
    _house(s)
    order, step, row, _who = _sold(s)
    s.commit()
    oid, sid, vid = order.id, step.id, row.id
    s.close()

    first, second = SessionLocal(), SessionLocal()
    seen: list[object] = []

    def bill(db):
        return voucher_actions.apply(db, order=db.get(Order, oid), step=db.get(ProcessStep, sid),
                         action="bill", payload={})

    def other():
        try:
            bill(second)
            second.commit()
            seen.append("billed")
        except HTTPException as exc:
            seen.append(exc.status_code)
            second.rollback()
        except Exception as exc:                      # noqa: BLE001 – genau das prüfen wir
            seen.append(f"{type(exc).__name__}: {exc}")
            second.rollback()

    try:
        bill(first)
        runner = threading.Thread(target=other)
        runner.start()
        time.sleep(0.5)                               # die zweite wartet jetzt an der Sperre
        first.commit()
        runner.join(timeout=30)
        papers = svc.documents_of(first, first.get(Voucher, vid), vo.INVOICE_DOC)
    finally:
        first.close()
        second.close()
    assert seen == [409], f"Die zweite Rechnung ging durch oder scheiterte anders: {seen}"
    assert len(papers) == 1, f"{len(papers)} Rechnungen stehen am Beleg."


def test_a_racing_reference_is_a_sentence_not_a_crash(db, monkeypatch):
    """Trifft eine gleichzeitige Buchung den Unique-Index der Referenz, kommt ein 409 mit
    Satz – kein ``IntegrityError`` (an der Tür ein 500). Das Rennen wird nachgestellt,
    indem die Vorab-Prüfung nichts sieht."""
    from fastapi import HTTPException
    from app.services import voucher as svc, voucher_money
    order, step, row, who = _billed(db)
    _do(db, order, step, "pay", amount="100.00", method="transfer", reference="ZW-1")
    monkeypatch.setattr(voucher_money, "reference_problem", lambda *a, **k: None)
    with pytest.raises(HTTPException) as exc:
        _do(db, order, step, "pay", amount="100.00", method="transfer", reference="ZW-1")
    assert exc.value.status_code == 409 and "ZW-1" in exc.value.detail
    assert svc.balance_of(db, row).paid == Decimal("100.00"), "Die Sitzung bleibt brauchbar."


def test_a_supplier_invoice_over_zero_is_refused(db):
    """«0» ist ein Betrag, kein leeres Feld: eine Lieferantenrechnung über null wird
    abgewiesen, statt still die Zusage zu verrechnen."""
    from fastapi import HTTPException
    from app.services import voucher as svc
    order, step, row, who = _scene(db, direction="out", first=True)
    _do(db, order, step, "incoterm", incoterm="EXW")
    _do(db, order, step, "ask")
    _do(db, order, step, "quote", party=who.object_id, amount="427.00", lead_days=5,
        payment_days=30)
    _do(db, order, step, "agree", party=who.object_id)
    with pytest.raises(HTTPException) as exc:
        _do(db, order, step, "bill", amount="0", reference="R-0",
            original=_file(db).object_id, vat="normal")
    assert exc.value.status_code == 400 and "null" in exc.value.detail
    assert not svc.is_billed(row)


def test_a_storno_reaches_every_party_that_got_an_offer(db):
    """Vor der Zusage an mehrere angeboten, dann storniert: jede Partei, die ein Papier
    bekam, bekommt die Stornierung – nicht keine, weil es «den einen» Adressaten nicht gibt."""
    from app.domain import voucher as vo
    from app.services import voucher as svc
    a, b = _person(db, "Alpha"), _person(db, "Beta")
    order, step, row, _ = _scene(db, first=True, party=a, config={
        "parties": [{"party": a.object_id}, {"party": b.object_id}]})
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "revoke")
    told = sorted(d.party_id for d in svc.documents_of(db, row, vo.STORNO_DOC))
    assert told == sorted([a.object_id, b.object_id]), told


def test_the_qr_bill_names_the_issuer_and_only_complete_addresses(db):
    """Der Zahlteil: der Zahlende nur mit Name, PLZ, Ort und Land; fehlt dem Aussteller
    die Anschrift, nennt der Satz ihn; eine Ausgabe hat keine Überweisung an uns."""
    from fastapi import HTTPException
    from app.services import qrbill, voucher_money
    creditor = {"name": "Inexxio AG", "street": "Weg 1", "zip": "9430", "city": "St. M.",
                "country": "CH"}
    half = {"name": "Anna", "street": "Feld 8", "zip": "", "city": "Altstätten",
            "country": "CH"}
    text = qrbill.payload(iban="CH9300762011623852957", creditor=creditor,
                          amount=Decimal("10.00"), currency="CHF", debtor=half, number="1-1")
    assert "Anna" not in text, "Eine halbe Anschrift des Zahlenden steht im Code."
    trouble = qrbill.problem(iban="CH9300762011623852957", currency="CHF",
                             amount=Decimal("10.00"), creditor={**creditor, "city": ""})
    assert trouble and "«Inexxio AG»" in trouble, trouble
    order, step, row, who = _scene(db, direction="out", first=True)
    _do(db, order, step, "incoterm", incoterm="EXW")
    _do(db, order, step, "ask")
    _do(db, order, step, "quote", party=who.object_id, amount="50.00", lead_days=5,
        payment_days=30)
    _do(db, order, step, "agree", party=who.object_id)
    _do(db, order, step, "bill", amount="50.00", reference="R-9",
        original=_file(db).object_id, party_uid="CHE-111.222.333 MWST", vat="normal")
    with pytest.raises(HTTPException) as exc:
        voucher_money.transfer_info(db, row)
    assert exc.value.status_code == 404, "Eine Lieferantenrechnung zeigt unser Konto."


def test_the_party_cannot_accept_what_we_could_not_confirm(db):
    """Die Lücken gelten für jede Rolle: fehlt UNSERE UID, sieht die Partei auf ihrer Seite
    kein «Annehmen», und die Tür weist sie mit dem Feldnamen ab (400)."""
    from fastapi import HTTPException
    from app.domain import voucher as vo
    from app.services import voucher_docs as docs, voucher as svc
    house = _house(db)
    house.vat_number, house.uid_number = None, None
    db.flush()
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    offer = svc.documents_of(db, row, vo.OFFER_DOC)[-1]
    assert "agree" not in docs.public_view(db, offer)["actions"]
    with pytest.raises(HTTPException) as exc:
        _do(db, order, step, "agree", actor=docs.party_user(db, offer), party=who.object_id)
    assert exc.value.status_code == 400 and "UID" in exc.value.detail
    assert row.stage == vo.OFFER


def test_a_refund_the_service_did_not_make_is_not_booked(db):
    """Gebucht wird je Erstattung, wie der Dienst sie führt – eine gescheiterte nicht."""
    from app.services import stripe_pay

    class _Refund:
        @staticmethod
        def list(**kw):
            class _L:
                def auto_paging_iter(self):
                    return iter([{"id": "re_a", "amount": 500, "status": "failed"},
                                 {"id": "re_b", "amount": 700, "status": "succeeded",
                                  "metadata": {"voucher_id": "7"}}])
            assert kw.get("payment_intent") == "pi_x"
            return _L()

    class _Api:
        Refund = _Refund

    rows = stripe_pay._refunds(_Api, "pi_x", "CHF")
    assert rows == [("pi_x:refund:re_b", Decimal("7.00"), {"voucher_id": "7"})], rows


def _queries(db, run) -> int:
    """Wie viele Abfragen ``run`` an die Datenbank schickt."""
    from sqlalchemy import event
    seen = [0]

    def hit(*_a, **_k):
        seen[0] += 1
    conn = db.connection()
    event.listen(conn, "before_cursor_execute", hit)
    try:
        run()
    finally:
        event.remove(conn, "before_cursor_execute", hit)
    return seen[0]


def test_the_card_reads_each_row_once(db):
    """Die Antwort an die Karte liest Angebotsspiegel, Geld-Zeilen, Positionen und Kopf
    einmal (``reading``) – gemessen an einem gestellten Beleg: 68 Abfragen vorher, 21
    danach. Die Grenze hält den Stand fest, mit etwas Luft."""
    from app.services import voucher_view
    order, step, row, who = _billed(db)
    staff = _staff(db)
    db.flush()
    db.expire_all()
    n = _queries(db, lambda: voucher_view.embed_data(db, order=order, step=step, viewer=staff))
    assert n <= 30, f"Die Karte braucht {n} Abfragen."


def test_a_read_that_writes_never_sees_an_old_state(db):
    """Jedes Schreiben verwirft, was der Lesevorgang sich gemerkt hat – auch ein Schreiben
    mitten in ihm."""
    from app.domain import voucher as vo
    from app.models import VoucherQuote
    from app.services import voucher as svc
    order, step, row, who = _scene(db, first=True)
    other = _person(db, "Gamma")
    with svc.reading(db):
        before = len(svc.quotes_of(db, row))
        db.add(VoucherQuote(voucher_id=row.id, party_id=other.object_id, state=vo.ASKED))
        db.flush()
        assert len(svc.quotes_of(db, row)) == before + 1
