"""**Die Forderung als dritte Achse — und die Reihenfolge, die es nicht gibt.**

Ware · Forderung · Geld sind drei **unabhängige** Achsen (PROCESS_CORE §9.11). Jedes
Zahlungs-Szenario ist eine andere *Folge* derselben drei Grundhandlungen; wer eine Folge
festschreibt, bekommt für jede Abweichung ein ``if``.

Die Regeln, die hier bewacht werden:

1. **Es gibt keine vorgeschriebene Reihenfolge.** Vorauszahlung und Zahlungsziel erzeugen
   dieselben Zeilentypen – nur in anderer Reihenfolge, und ohne einen Modus dazwischen.
2. **Eine Gutschrift ist eine negative Rechnung**, keine Zahlung.
3. **Die Fälligkeit gehört der Rechnung**, nicht dem Beleg – zwei Rechnungen, zwei
   Fälligkeiten.
4. **Die Nummer** ist ``<Auftragsnummer>-<laufend>``; wer sie vergibt, sagt der ``Flow``.
5. **Der Shop braucht keinen eigenen Endpunkt** – ein Kauf ist eine Auftragsfreigabe plus
   die Handlungen, die es schon gibt.

Gefahren über die **echten** Dienstpfade gegen echtes PostgreSQL.
"""

import datetime
import os
import pathlib
import uuid

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _db():
    """Eine Sitzung gegen echtes PostgreSQL – oder ein Skip **mit Grund**."""
    import sys
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    try:
        from app.core.database import Base, SessionLocal, engine
        import app.main as main
        Base.metadata.create_all(engine)
        main._ensure_columns()
        return SessionLocal()
    except Exception as exc:  # pragma: no cover - reine Umgebungsfrage
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regeln wirklich laufen.")


def _code_of(module) -> str:
    """Der **Code** eines Moduls in Kleinschreibung – ohne Kommentare und Docstrings.

    Ein Quelltext-Wächter, der die Prosa mitliest, schlägt an, sobald jemand den Fehler
    *beschreibt*, den er verhindern soll. Genau das ist hier passiert: «weder Vorkasse
    noch Rechnung abbilden» steht als Begründung im Code, warum es **keine** Vorkasse-
    Einstellung gibt.
    """
    import ast
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    # ``ast.unparse`` gibt den Baum ohne Kommentare zurück; Docstrings sind Ausdrücke und
    # werden hier gezielt entfernt, damit auch sie nicht mitgelesen werden.
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body.pop(0)
            if not body:
                body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(tree)).lower()


def _user(db, name: str, role: str):
    from app.models import UserProfile
    from app.services import objects as obj
    user = UserProfile(firebase_uid=f"inv-{uuid.uuid4()}",
                       email=f"{uuid.uuid4()}@example.test", company_name=name,
                       role=role, object_id=obj.next_object_id(db))
    db.add(user)
    db.flush()
    return user


def _scene(db, *, quantity=1, amount=1000, days=None, direction="sell"):
    """Ein Auftrag mit einem Handels-Modul, bis zur **Zusage** gefahren.

    Ab dort gibt es etwas zu fordern – vorher nicht, und das ist keine Einstellung,
    sondern die Bedeutung der Schwelle.
    """
    from app.models import Article, ProcessStep
    from app.services import article_process as tpl, objects as obj, process as proc
    from app.services import purchase as svc

    staff = _user(db, "Personal", "employee")
    party = _user(db, "Meier AG", "supplier" if direction == "buy" else "customer")
    config = ({"instruction": "liefern",
               "suppliers": [{"supplier": party.object_id, "ref": "M-1"}]}
              if direction == "buy" else {})
    art = Article(object_id=obj.next_object_id(db), name=f"Teil {uuid.uuid4().hex[:6]}",
                  unit="stk", serialization="batch")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, [{
        "module_type": "beschaffen" if direction == "buy" else "verkauf",
        "config": config}])
    db.flush()
    order = proc.release(db, lines=[{"article_object_id": art.object_id,
                                     "quantity": quantity, "origin": "neu", "units": []}],
                         steps=[], actor_id=None)
    db.flush()
    step = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position).first())
    svc.apply(db, order=order, step=step, action="ask",
              payload={"suppliers": [party.object_id]}, actor=staff)
    if days is not None:
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"supplier": party.object_id, "amount": amount,
                           "lead_days": 3, "payment_days": days}, actor=staff)
    svc.apply(db, order=order, step=step, action="order",
              payload={"supplier": party.object_id, "amount": amount}, actor=staff)
    db.flush()
    return order, step, staff, svc.of_step(db, step.id)


# ---------------------------------------------------------------------------
# §1 – es gibt keine Reihenfolge
# ---------------------------------------------------------------------------

def test_the_deal_has_no_prescribed_order():
    """►►► **Vorauszahlung und Zahlungsziel sind DERSELBE Vorgang, anders sortiert.** ◄◄◄

    Das ist die Kernaussage der dritten Achse. Beide Szenarien erzeugen dieselben
    Zeilentypen – eine Rechnung, eine Zahlung, eine Lieferung –, und zwischen ihnen liegt
    **kein** Schalter, kein Modus und keine Einstellung. Wer zuerst Geld sehen will,
    stellt zuerst die Rechnung.

    Bug-Form: irgendwo entsteht ein Modus «Vorkasse ja/nein». Dann ist die Reihenfolge
    eine Einstellung, und ab der zweiten Einstellung hat man eine Verzweigungs-Landschaft
    statt einer Regel.
    """
    from decimal import Decimal
    from app.domain import money
    from app.services import payments, process as proc, purchase as svc
    db = _db()
    try:
        # ── Fall A: Vorauszahlung – fordern, kassieren, dann liefern ──────────────
        order_a, step_a, staff, doc_a = _scene(db, amount=300)
        svc.apply(db, order=order_a, step=step_a, action=svc.INVOICE, payload={},
                  actor=staff)
        svc.apply(db, order=order_a, step=step_a, action=svc.PAY,
                  payload={"amount": 300, "method": money.TRANSFER,
                           "reference": f"VZ-{uuid.uuid4().hex[:8]}"}, actor=staff)
        assert payments.balance(db, doc_a).settled, "Vorausbezahlt heisst offen null."
        work = proc.step_work(db, order_a, step_a)
        proc.confirm_step(db, order=order_a, step_id=step_a.id, actor_id=None, values={},
                          instance_object_id=work[0]["instance_object_id"],
                          verification="scan")
        db.flush()

        # ── Fall B: Zahlungsziel – liefern, fordern, kassieren ────────────────────
        order_b, step_b, staff_b, doc_b = _scene(db, amount=300)
        work = proc.step_work(db, order_b, step_b)
        proc.confirm_step(db, order=order_b, step_id=step_b.id, actor_id=None, values={},
                          instance_object_id=work[0]["instance_object_id"],
                          verification="scan")
        db.flush()
        svc.apply(db, order=order_b, step=step_b, action=svc.INVOICE, payload={},
                  actor=staff_b)
        svc.apply(db, order=order_b, step=step_b, action=svc.PAY,
                  payload={"amount": 300, "method": money.TRANSFER,
                           "reference": f"ZZ-{uuid.uuid4().hex[:8]}"}, actor=staff_b)

        # **Dasselbe Ergebnis, dieselben Zeilentypen** – nur anders sortiert.
        for doc in (doc_a, doc_b):
            state = payments.balance(db, doc)
            assert state.charged == Decimal("300.00")
            assert state.paid == Decimal("300.00")
            assert state.settled

        # Und nirgends steht ein Modus, der die Reihenfolge festlegt.
        #
        # **Geprüft wird der CODE, nicht die Prosa.** Der erste Anlauf las die
        # Docstrings mit und schlug an, weil dort *erklärt* wird, warum es keine Vorkasse-
        # Einstellung gibt – ein Wächter, der anschlägt, weil jemand den Fehler
        # beschreibt, prüft die falsche Sache (dieselbe Falle wie in der Runde #755–#766).
        for module in (payments, svc):
            src = _code_of(module)
            for word in ("vorkasse", "prepay", "payment_mode", "invoice_mode"):
                assert word not in src, (
                    f"«{word}» steht im Code von {module.__name__} – die Reihenfolge ist "
                    f"eine Einstellung geworden."
                )
    finally:
        db.rollback(); db.close()


def test_a_down_payment_is_two_invoices_not_a_new_mechanism():
    """**Anzahlung + Schlussrechnung** – zwei Zeilen, kein zweiter Mechanismus.

    Genau das konnte die alte Formel nicht: sie las die **Zusage** als Forderung, und eine
    Zusage hat nur einen Betrag und nur eine Fälligkeit.

    Bug-Form: die zweite Rechnung überschreibt die erste, oder ``uncharged`` zählt falsch.
    """
    from decimal import Decimal
    from app.services import invoices, payments, purchase as svc
    db = _db()
    try:
        order, step, staff, doc = _scene(db, amount=1000, days=30)
        assert payments.balance(db, doc).uncharged == Decimal("1000.00")

        svc.apply(db, order=order, step=step, action=svc.INVOICE,
                  payload={"amount": 300, "note_text": "Anzahlung 30 %"}, actor=staff)
        state = payments.balance(db, doc)
        assert state.charged == Decimal("300.00")
        assert state.open == Decimal("300.00"), "Gefordert sind 300, nicht 1000."
        assert state.uncharged == Decimal("700.00"), (
            "«zugesagt, noch nicht berechnet» stimmt nicht – die Zahl, die es vor der "
            "dritten Achse gar nicht geben konnte."
        )

        # Die zweite Rechnung nimmt **den Rest** als Vorgabe – ein Klick.
        svc.apply(db, order=order, step=step, action=svc.INVOICE, payload={}, actor=staff)
        state = payments.balance(db, doc)
        assert state.charged == Decimal("1000.00")
        assert state.uncharged == Decimal("0.00")
        rows = invoices.of_purchase(db, doc)
        assert len(rows) == 2, "Die zweite Rechnung hat die erste überschrieben."
        assert [float(r.amount) for r in rows] == [300.0, 700.0]
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §2 – die Nummer
# ---------------------------------------------------------------------------

def test_the_number_is_the_order_number_and_the_first_suffix_is_silent():
    """►►► **``<Auftragsnummer>-<laufend>``, und das ``-1`` fällt nach aussen weg.** ◄◄◄

    Dieselbe Regel wie beim Suffix der Einzelinstanz (kumulierend, **nicht** aus
    ``object_id_seq``): eine Rechnung ist zum Auftrag, was die Einzelinstanz zur Instanz
    ist – sie braucht einen Namen, aber keine eigene Objektidentität.

    Die laufende Zahl ist eine **Lesehilfe**: bei genau einer Rechnung sagt sie nichts, was
    die Auftragsnummer nicht schon sagt. Ab der zweiten steht sie da – sonst trügen zwei
    Rechnungen desselben Auftrags denselben Namen.

    Bug-Formen: (a) die Nummer wird nicht gespeichert, nur angezeigt (dann sind zwei
    Rechnungen ununterscheidbar); (b) das ``-2`` fällt auch weg; (c) eine stornierte
    Rechnung gibt ihre Nummer wieder frei.
    """
    from app.models import Invoice
    from app.services import invoices, purchase as svc
    db = _db()
    try:
        order, step, staff, doc = _scene(db, amount=900)
        svc.apply(db, order=order, step=step, action=svc.INVOICE,
                  payload={"amount": 400}, actor=staff)
        svc.apply(db, order=order, step=step, action=svc.INVOICE,
                  payload={"amount": 500}, actor=staff)
        rows = invoices.of_purchase(db, doc)

        # (a) **Gespeichert** wird mit Suffix – sonst wären beide gleich.
        assert [r.number for r in rows] == [f"{order.object_id}-1",
                                            f"{order.object_id}-2"], (
            "Die laufende Zahl wird nicht gespeichert – zwei Rechnungen eines Auftrags "
            "sind dann nicht mehr zu unterscheiden."
        )
        # (b) **Angezeigt** ohne das erste, mit dem zweiten.
        assert invoices.display(rows[0].number) == str(order.object_id)
        assert invoices.display(rows[1].number) == f"{order.object_id}-2", (
            "Auch das -2 fällt weg – dann heissen beide Rechnungen gleich."
        )

        # (c) Eine zurückgenommene Nummer wird **nicht** neu vergeben.
        rows[1].is_active = False
        db.flush()
        assert invoices.next_number(db, doc) == f"{order.object_id}-3", (
            "Eine stornierte Rechnung gibt ihre Nummer wieder frei – dann gäbe es zwei "
            "Dokumente mit einem Namen."
        )
        assert db.query(Invoice).filter(Invoice.purchase_id == doc.id).count() == 2
    finally:
        db.rollback(); db.close()


def test_who_numbers_the_invoice_is_a_declaration_not_a_branch():
    """**Beim Verkauf nummerieren wir, beim Einkauf erfassen wir seine.**

    Der eine echte Unterschied zwischen Ausgangs- und Eingangsrechnung – und er steht als
    Wert im ``Flow`` (``invoice_number``), nicht als ``if direction ==``.

    Bug-Form: der Einkauf bekommt eine erfundene Vorgabe. Das wäre eine Behauptung über
    ein fremdes Dokument – und auf der Rechnung des Lieferanten steht etwas anderes.
    """
    import pathlib
    from app.domain import procurement
    from app.services import invoices
    db = _db()
    try:
        _, _, _, sell = _scene(db, amount=100, direction="sell")
        _, _, _, buy = _scene(db, amount=100, direction="buy")
        assert invoices.next_number(db, sell) is not None, "Beim Verkauf nummerieren wir."
        assert invoices.next_number(db, buy) is None, (
            "Beim Einkauf wird eine Nummer erfunden – dort nummeriert die Gegenpartei."
        )
        assert procurement.FLOWS[procurement.SELL].invoice_number == procurement.OWN_NUMBER
        assert procurement.FLOWS[procurement.BUY].invoice_number == procurement.THEIR_NUMBER

        src = pathlib.Path(invoices.__file__).read_text(encoding="utf-8")
        for forbidden in ("direction ==", "== procurement.SELL", "== procurement.BUY"):
            assert forbidden not in src, (
                f"«{forbidden}» steht in services/invoices – die Richtung ist eine "
                f"Verzweigung geworden statt einer Angabe im Flow."
            )
    finally:
        db.rollback(); db.close()


def test_the_same_number_at_another_document_is_named_not_swallowed():
    """**Eine Nummer gehört zu genau einer Rechnung im Haus** – dieselbe Regel wie beim
    Zahlungs-Verweis, und dieselbe Form: 409 mit dem Auftrag, an dem sie schon hängt.

    Bug-Form: die fremde Zeile wird zurückgegeben. Dann bucht der zweite Beleg nichts und
    meldet nichts – ein stiller Nicht-Effekt.
    """
    from fastapi import HTTPException
    from app.models import Invoice
    from app.services import invoices
    db = _db()
    try:
        number = f"R-{uuid.uuid4().hex[:10]}"
        order_a, _, _, doc_a = _scene(db, amount=100)
        _, _, _, doc_b = _scene(db, amount=100)
        invoices.record(db, purchase=doc_a, amount=100, number=number)

        with pytest.raises(HTTPException) as caught:
            invoices.record(db, purchase=doc_b, amount=100, number=number)
        assert caught.value.status_code == 409
        assert str(order_a.object_id) in caught.value.detail, caught.value.detail
        assert db.query(Invoice).filter(Invoice.purchase_id == doc_b.id).count() == 0

        # Am **eigenen** Beleg bleibt es idempotent.
        again = invoices.record(db, purchase=doc_a, amount=100, number=number)
        assert again.purchase_id == doc_a.id
        assert db.query(Invoice).filter(Invoice.purchase_id == doc_a.id).count() == 1
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §3 – der Shop
# ---------------------------------------------------------------------------

def test_a_shop_checkout_needs_no_new_endpoint():
    """►►► **Ein Shop-Kauf ist eine Auftragsfreigabe plus drei bestehende Handlungen.** ◄◄◄

    Das ist der Beweis für «der Onlineshop greift nahtlos an»: Freigabe → ``ask`` →
    ``order`` → ``invoice`` → Zahlung. Kein Endpunkt, den es nur für den Shop gibt, keine
    Reservierung, kein ``CheckoutIntent`` – und **kein zweiter Weg**, der beim nächsten
    Fehlerfix vergessen wird.

    **Ohne Reservierung**: sind die Stücke im Moment der Freigabe weg, meldet sie es – wie
    bei jedem anderen Auftrag auch.

    Bug-Form: irgendwo entsteht ein Shop-eigener Pfad. Dann gibt es zwei Wege zu einem
    Verkauf, und der zweite kennt die Regeln des ersten nicht.
    """
    from decimal import Decimal
    from app.domain import money
    from app.services import invoices, payments, purchase as svc
    db = _db()
    try:
        order, step, staff, doc = _scene(db, amount=59.9, days=0)
        # Der Shop kennt seinen Preis; die Zusage ist der Klick auf «kaufen».
        svc.apply(db, order=order, step=step, action=svc.INVOICE, payload={}, actor=staff)
        state = payments.balance(db, doc)
        assert state.open == Decimal("59.90")
        assert invoices.of_purchase(db, doc)[0].number == f"{order.object_id}-1"

        # Und die Zahlung kommt über denselben Weg wie jede andere.
        svc.apply(db, order=order, step=step, action=svc.PAY,
                  payload={"amount": 59.9, "method": money.TRANSFER,
                           "reference": f"SHOP-{uuid.uuid4().hex[:8]}"}, actor=staff)
        assert payments.balance(db, doc).settled

        # **Kein Shop-eigener Endpunkt** – geprüft an der Liste der Handlungen.
        assert set(svc.ACTIONS) | {svc.BUY, svc.PAY, svc.INVOICE} == {
            "ask", "quote", "decline", "order", "note", "revoke", "clarified",
            "buy", "pay", "invoice"}, (
            "Die Liste der Handlungen ist gewachsen – wofür? Ein Shop braucht keine."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §4 – die Vorgaben
# ---------------------------------------------------------------------------

def test_the_defaults_make_the_normal_case_one_click():
    """**Die Automatik steckt in den Vorgaben, nicht in einem Modus.**

    Betrag = zugesagt − berechnet, Fälligkeit = heute + vereinbarte Frist, Nummer nach der
    Regel. Damit ist der Normalfall ein Klick – und jede Abweichung eine Eingabe statt
    eines zweiten Wegs.

    Bug-Form: die Vorgaben fehlen. Dann muss ein Mensch bei jeder Rechnung drei Felder
    füllen, und die Zahl, die er tippt, weicht irgendwann von der ab, die das System kennt.
    """
    from decimal import Decimal
    from app.services import invoices, purchase as svc
    db = _db()
    try:
        order, step, staff, doc = _scene(db, amount=480, days=14)
        svc.apply(db, order=order, step=step, action=svc.INVOICE, payload={}, actor=staff)
        row = invoices.of_purchase(db, doc)[0]
        assert row.amount == Decimal("480.00"), "Der Betrag ist nicht vorbelegt."
        assert row.issued_on == datetime.date.today()
        assert row.due_on == datetime.date.today() + datetime.timedelta(days=14), (
            "Die Fälligkeit folgt nicht aus der vereinbarten Frist."
        )
        assert row.number == f"{order.object_id}-1"

        # Und eine **Abweichung** ist eine Eingabe, kein zweiter Weg.
        svc.apply(db, order=order, step=step, action=svc.INVOICE,
                  payload={"amount": 20, "due_on": "2027-01-31",
                           "note_text": "Nachbelastung"}, actor=staff)
        extra = invoices.of_purchase(db, doc)[1]
        assert extra.amount == Decimal("20.00")
        assert extra.due_on == datetime.date(2027, 1, 31)
        assert extra.note == "Nachbelastung"
    finally:
        db.rollback(); db.close()


def test_nothing_is_chargeable_before_something_was_promised():
    """**Ohne Zusage keine Forderung** – dasselbe Tor wie beim Geld.

    Eine Rechnung auf ein Angebot, das niemand angenommen hat, wäre eine Forderung ohne
    Grundlage. Ein Storno ist dagegen **kein** Hindernis: eine Schlussrechnung nach einer
    teilweise erbrachten Leistung ist der Normalfall.

    Bug-Form: die Forderung hängt an einer Stufe. Dann wäre Vorauszahlung unmöglich – oder
    sie bräuchte einen zweiten Weg.
    """
    from fastapi import HTTPException
    from app.models import Article, ProcessStep
    from app.services import (article_process as tpl, objects as obj, process as proc,
                              purchase as svc)
    db = _db()
    try:
        staff = _user(db, "Personal", "employee")
        kunde = _user(db, "Meier AG", "customer")
        art = Article(object_id=obj.next_object_id(db), name="Welle Z", unit="stk",
                      serialization="batch")
        db.add(art)
        db.flush()
        tpl.create_steps(db, art, [{"module_type": "verkauf", "config": {}}])
        db.flush()
        order = proc.release(db, lines=[{"article_object_id": art.object_id,
                                         "quantity": 1, "origin": "neu", "units": []}],
                             steps=[], actor_id=None)
        db.flush()
        step = db.query(ProcessStep).filter(ProcessStep.order_id == order.id).first()
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"suppliers": [kunde.object_id]}, actor=staff)
        row = svc.of_step(db, step.id)
        assert svc.INVOICE not in svc._can(db, row, staff)
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=step, action=svc.INVOICE, payload={},
                      actor=staff)
        assert err.value.status_code == 409

        # Nach einem **Storno** geht es weiterhin – dort ist eine Schlussrechnung normal.
        order2, step2, staff2, doc2 = _scene(db, amount=200)
        svc.apply(db, order=order2, step=step2, action="revoke", payload={}, actor=staff2)
        row2 = svc.of_step(db, step2.id)
        assert svc.INVOICE in svc._can(db, row2, staff2), (
            "Nach einem Storno lässt sich nichts mehr fordern – das ist eine Sackgasse."
        )
    finally:
        db.rollback(); db.close()


def test_a_manual_payment_cannot_claim_to_be_a_card():
    """**Die Menschentür ist enger als die Tabelle** (Testnotiz #782).

    Eine Kartenzahlung entsteht beim Zahlungsdienst und kommt über den Webhook. Wer sie von
    Hand erfassen könnte, öffnete eine zweite Quelle für dieselbe Buchung – die eine aus
    der Wirklichkeit, die andere aus einer Erinnerung.

    **Zwei Formen einer Regel, ein Namensstamm**: ``METHODS`` sagt, was es gibt (der
    Webhook schreibt hier durch), ``MANUAL_METHODS`` was man eintragen darf.

    Bug-Form: die Verengung steht nur in der Oberfläche. Dann ist sie eine Bitte.
    """
    from fastapi import HTTPException
    from app.domain import money
    from app.services import payments, purchase as svc
    db = _db()
    try:
        assert money.CARD in money.METHODS and money.CARD not in money.MANUAL_METHODS
        order, step, staff, doc = _scene(db, amount=100)
        svc.apply(db, order=order, step=step, action=svc.INVOICE, payload={}, actor=staff)
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=step, action=svc.PAY,
                      payload={"amount": 100, "method": money.CARD}, actor=staff)
        assert err.value.status_code == 400
        assert "zahlweg" in err.value.detail.lower(), err.value.detail

        # Der **Webhook** schreibt sie weiterhin – über dieselbe Funktion, ohne Verengung.
        row = payments.record(db, purchase=doc, amount=100, method=money.ONLINE,
                              reference=f"pi_{uuid.uuid4().hex[:12]}")
        assert row.method == money.CARD
    finally:
        db.rollback(); db.close()
