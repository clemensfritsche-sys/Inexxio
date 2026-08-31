"""**Verkauf: Beschaffen in die andere Richtung — und das Geld daneben.**

Die Regeln, die dabei entstanden sind, gehören nicht diesem Modul, sondern dem Rahmen:

1. **Einkauf und Verkauf sind EIN Vorgang in zwei Richtungen.** Dieselben drei Stufen,
   dieselbe Schwelle, derselbe Storno, derselbe Dienst. Was sie unterscheidet, steht als
   Daten im ``Flow`` (``domain/procurement``) – nicht als ``if`` im Dienst.
2. **Der Verkauf ist ein AUSGANG** (``Module.terminal``): was geliefert ist, ist weg.
   Daraus folgt alles Weitere ohne eine Fallunterscheidung im Ablauf (§4.6).
3. **``Verkauft`` ist nicht endgültig.** Eine Retoure ist real: ein ganz gewöhnlicher
   Auftrag greift das Stück – **das Greifen IST die Rücknahme** –, und weil sein Start vom
   Regelstart abweicht, ist er **automatisch** eine dokumentierte Abweichung.
4. **Farbe und Abweichung sind zwei Fragen.** ``deviation_flags`` vergleicht mit
   ``START_BEFORE`` und nennt weder Farbe noch Status; ``Verkauft`` ist grün **und** löst
   eine Abweichung aus – wie ``Verbaut`` seit dem Verbrauchsmodul.
5. **Das Geld ist keine vierte Stufe.** Es läuft daneben (``services/payments``), und es
   fliesst auch noch, wenn längst geliefert oder storniert ist. *Offen* ist eine
   Subtraktion, *fällig* eine Addition – es gibt keine Forderungs-Spalte.

Geprüft über die **echten** Dienstpfade gegen echtes PostgreSQL.
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


def _user(db, name: str, role: str):
    from app.models import UserProfile
    from app.services import objects as obj
    user = UserProfile(
        firebase_uid=f"test-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.test",
        company_name=name, role=role, object_id=obj.next_object_id(db),
    )
    db.add(user)
    db.flush()
    return user


def _customer(db, name: str = "Meier AG"):
    return _user(db, name, "customer")


def _staff(db):
    return _user(db, "Personal", "employee")


def _article(db, name: str, *, steps=None, serialization: str = "batch"):
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization=serialization)
    db.add(art)
    db.flush()
    if steps:
        tpl.create_steps(db, art, steps)
        db.flush()
    return art


def _sell_step(customers=None):
    """Ein Verkaufs-Modul. **Ohne Konfiguration ist der Normalfall** – wer kauft, steht
    beim Modellieren nicht fest."""
    config: dict = {}
    if customers:
        config["suppliers"] = [{"supplier": c.object_id, "ref": f"K-{c.object_id}"}
                               for c in customers]
    return {"module_type": "verkauf", "config": config}


def _make(db, *, quantity: int, article, steps=None, units=None, origin="neu"):
    """Ein freigegebener Auftrag über diesen Artikel."""
    from app.models import ProcessStep
    from app.services import process as proc
    order = proc.release(
        db,
        lines=[{"article_object_id": article.object_id, "quantity": quantity,
                "origin": origin, "units": units or []}],
        steps=steps or [], actor_id=None,
    )
    db.flush()
    rows = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position).all())
    return order, rows


def _commit(db, order, step, customer, amount=1400):
    """Angebot → Zusage. Die zwei Handlungen, nach denen es etwas zu bezahlen gibt."""
    from app.services import purchase as svc
    staff = _staff(db)
    svc.apply(db, order=order, step=step, action="ask",
              payload={"suppliers": [customer.object_id]}, actor=staff)
    svc.apply(db, order=order, step=step, action="order",
              payload={"supplier": customer.object_id, "amount": amount}, actor=staff)
    db.flush()
    return staff


def _units_of(db, order):
    """Die Einzelinstanzen dieses Auftrags – **auch die abgegebenen**.

    Über die Zugehörigkeit, nicht über den heutigen Zustand: ein verkauftes Stück hat den
    Auftrag verlassen (``released_at`` gesetzt), und genau das will hier geprüft werden.
    """
    from app.models import InstanceUnit, OrderUnit
    return (
        db.query(InstanceUnit)
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .filter(OrderUnit.order_id == order.id)
        .order_by(InstanceUnit.id)
        .all()
    )


def _deliver(db, order, step):
    """Liefern, bis nichts mehr davorsteht – nach jedem Vorgang neu gefragt."""
    from app.services import process as proc
    while True:
        work = proc.step_work(db, order, step)
        if not work:
            return
        proc.confirm_step(db, order=order, step_id=step.id, actor_id=None, values={},
                          instance_object_id=work[0]["instance_object_id"],
                          verification="scan")
        db.flush()


# ---------------------------------------------------------------------------
# §1 – der Verkauf ist ein Ausgang
# ---------------------------------------------------------------------------

def test_a_sale_is_a_step_on_the_way_not_an_exit():
    """►►► **Verkaufen heisst Eigentum wechselt – nicht Ort wechselt.** ◄◄◄

    Der Verkauf war einmal ein **Ausgang** (``terminal``), und das war eine Notlüge: das
    Stück steht danach noch im Regal, bis jemand es hinausfährt. Weil ``terminal`` die
    Kette schloss, konnte hinter dem Verkauf kein **Bewegen** stehen – und damit
    scheiterte ausgerechnet der Normalfall «verkaufen und liefern».

    Was das Stück am Ende **ist**, sagt jetzt nicht mehr das Modul, sondern der Auftrag
    (``Module.rest_status_for`` → ``orders.end_status``). Das Ende schreibt denselben
    Wert, den der Prozess ohnehin meint: nichts zu überschreiben, keine Ausnahme.

    Bug-Formen: (a) der Verkauf ist wieder ein Ausgang; (b) er schreibt ``Verkauft`` an
    seinem eigenen Schritt – dann bricht die Statuskette beim nächsten Modul; (c) der
    Ruhezustand ist nicht deklariert, dann endet ein Verkaufsauftrag auf «Freigegeben».
    """
    from app.domain import chain, modules, statuses as st

    sale = modules.get("verkauf")
    assert not sale.terminal, (
        "Der Verkauf ist wieder ein Ausgang – dann lässt sich dahinter nicht mehr "
        "ausliefern, und genau das war der gemeldete Fall."
    )
    assert sale.status_after_for(None) == st.IM_PROZESS, (
        "Ein Durchläufer verändert das Stück nicht: der Zustand kommt am ENDE."
    )
    assert sale.rest_status_for(None) == st.VERKAUFT, (
        "Ohne deklarierten Ruhezustand endet ein Verkaufsauftrag auf «Freigegeben» – "
        "verkauft und im Lager zugleich."
    )
    # Und die Kette schliesst mit einem Bewegen dahinter – an **beiden**
    # Definitionsorten dieselbe Prüfung.
    chain.assert_closes([
        {"module_type": "verkauf", "status_before": st.IM_PROZESS,
         "status_after": st.IM_PROZESS},
        {"module_type": "bewegen", "status_before": st.IM_PROZESS,
         "status_after": st.IM_PROZESS},
    ])


def test_the_piece_leaves_as_sold_and_the_order_is_done():
    """Die ganze Szene: greifen → liefern → **Verkauft**, Auftrag abgeschlossen.

    Bug-Form: das Stück bleibt ``Im Prozess`` stehen, oder es passiert das Ende-Objekt
    und landet wieder auf ``Freigegeben``.
    """
    from app.domain import statuses as st
    from app.services import process as proc, purchase as svc
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle A", steps=[_sell_step()])
        order, rows = _make(db, quantity=3, article=art)

        row = svc.of_step(db, rows[0].id)
        assert row is not None, "Die Freigabe legt den Beleg an – der Verkauf ist sein Zweck."
        assert row.direction == "sell", "Die Richtung steht am Beleg, nicht am Modultyp."

        _commit(db, order, rows[0], kunde)
        _deliver(db, order, rows[0])

        # **Abgeschlossen heisst «den definierten Weg zu Ende gegangen»** – ein Ausgang
        # IST ein Ende, auch wenn das Ende-Objekt nie passiert wurde (§4.6).
        state = proc.order_status(db, order)
        assert state == st.ABGESCHLOSSEN, (
            f"Der Auftrag ist seinen Weg zu Ende gegangen, steht aber auf «{state}»."
        )
        left = {u.status for u in _units_of(db, order)}
        assert left == {st.VERKAUFT}, f"Die Stücke stehen auf {left} statt «verkauft»."
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §2 – der Zustand: grün, Historie, nicht endgültig
# ---------------------------------------------------------------------------

def test_sold_is_out_of_stock_but_still_selectable():
    """**Zwei Fragen, zwei Antworten**: «liegt es im Regal?» und «gibt es einen Weg zurück?».

    Bug-Form: beide über eine Eigenschaft beantwortet. Dann wäre ein verkauftes Stück
    entweder unerreichbar (keine Retoure möglich) oder es zählte zum Lagerbestand.
    """
    from app.domain import statuses as st

    assert st.stock_kind(st.VERKAUFT) == st.HISTORY, "Es liegt nicht mehr in unserem Regal."
    assert st.VERKAUFT not in st.IN_STOCK_UNIT_STATUSES, "FIFO darf es nicht vorschlagen."
    assert st.is_selectable(st.VERKAUFT), "Ohne das gäbe es keine Retoure."
    assert not st.is_terminal(st.VERKAUFT)
    # Grün, aus demselben Grund wie ``Verbaut``: es hat sein Ziel erreicht.
    assert next(s.tone for s in st.CATALOG if s.value == st.VERKAUFT) == "done"


def test_taking_back_a_sold_piece_is_automatically_a_deviation():
    """►►► **Das Greifen IST die Rücknahme** – und sie steht im Nachweis. ◄◄◄

    Es gibt keinen «Retoure annehmen»-Endpunkt: ein ganz gewöhnlicher Auftrag greift das
    Stück. Und weil sein Start vom **Regelstart** abweicht (``Freigegeben``), ist er
    automatisch eine Abweichung – ohne dass jemand ein Feld setzt.

    Bug-Form: die Regel fragt nach der **Farbe** oder nennt einen Status. ``Verkauft`` ist
    grün, also fiele die Retoure aus dem Nachweis – genau der Fall, der dokumentiert
    gehört.
    """
    from app.domain import statuses as st
    from app.models import Instance
    from app.services import instances as inst, process as proc
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle B", steps=[_sell_step()])
        order, rows = _make(db, quantity=2, article=art)
        _commit(db, order, rows[0], kunde)
        _deliver(db, order, rows[0])

        unit = _units_of(db, order)[0]
        assert unit.status == st.VERKAUFT

        # ►► **Ein ganz gewöhnlicher Auftrag** – kein Sondertyp, kein Retouren-Modul. ◄◄
        # Er prüft, was zurückkam, und lässt es ans Ende laufen: dort wird es wieder
        # `Freigegeben`. Genau so, wie man einen beliebigen anderen Auftrag baut.
        number = inst.unit_number(
            db.query(Instance).filter(Instance.id == unit.instance_id).first(), unit)
        back, back_steps = _make(
            db, quantity=1, article=art, origin="lager",
            units=[{"number": number, "from_order": None}],
            steps=[{"module_type": "datenerfassung",
                    "config": {"points": [{"key": "zustand", "label": "Zustand",
                                           "type": "text"}]}}])
        flags = proc.deviation_flags(db, [back.id])
        assert flags[back.id] is True, (
            "Ein Auftrag, der ein verkauftes Stück greift, ist keine Abweichung – dann "
            "fehlt der Zugriff auf Material, das nicht frei war, im Nachweis."
        )
    finally:
        db.rollback(); db.close()


def test_a_sold_piece_keeps_its_place_until_someone_moves_it():
    """►►► **Ort und Zustand sind zwei Fragen.** ◄◄◄

    Hier stand einmal «wer zur Historie zählt, verliert seinen Ort». Das war richtig,
    solange der einzige historische Zustand ein Stück meinte, das physisch verschwindet –
    und es wurde falsch, als der Verkauf dazukam: **ein verkauftes Stück steht noch im
    Regal, bis jemand es hinausfährt.** Genau dafür gibt es das Bewegen-Modul, und genau
    deshalb darf der Verkauf kein Ausgang sein.

    Bug-Form: ein Statuswechsel räumt wieder den Ort. Dann ist ein verkauftes Stück
    nirgends, obwohl es noch bei uns liegt – und die Kommissionierung findet es nicht.
    """
    from app.domain import statuses as st
    from app.models import Instance
    from app.services import objects as obj, places
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle C", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)

        # Ein Regal, auf das die Ware gelegt wird.
        shelf_art = _article(db, "Regal")
        shelf = Instance(object_id=obj.next_object_id(db), article_id=shelf_art.id,
                         kind="einzeln")
        db.add(shelf)
        db.flush()

        unit = _units_of(db, order)[0]
        places.place(db, units=[unit], target=shelf.object_id)
        db.flush()
        assert unit.place_object_id == shelf.object_id

        _commit(db, order, rows[0], kunde)
        _deliver(db, order, rows[0])
        db.refresh(unit)
        assert unit.status == st.VERKAUFT
        assert unit.place_object_id == shelf.object_id, (
            "Der Verkauf hat den Ort geräumt – das Stück liegt aber noch im Regal, bis "
            "es jemand hinausfährt. Wo es liegt, sagt das Bewegen-Modul."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §3 – dieselbe Maschine, andere Richtung
# ---------------------------------------------------------------------------

def test_both_directions_run_through_the_same_service():
    """**Ein Dienst, zwei Richtungen** – kein zweites ``sales.py``.

    Bug-Form: eine Verzweigung nach der Richtung im Dienst. Die erste ist eine
    Beschriftung, die zweite eine Regel, und ab der dritten gibt es zwei Belege, die nur
    noch so tun, als wären sie einer.
    """
    src = (BACKEND / "app" / "services" / "purchase.py").read_text(encoding="utf-8")
    for forbidden in ('direction == "sell"', "direction == 'sell'",
                      'direction == "buy"', "== procurement.SELL"):
        assert forbidden not in src, (
            f"Der Dienst verzweigt nach der Richtung ({forbidden}) – was sie unterscheidet, "
            f"gehört als Daten in den `Flow`."
        )
    assert not (BACKEND / "app" / "services" / "sales.py").exists(), (
        "Es gibt einen zweiten Verkaufs-Dienst – dieselbe Maschine ein zweites Mal."
    )


def test_the_words_come_from_the_flow_not_from_a_literal():
    """Die Stufen heissen je Richtung anders – und **nur** dort steht es geschrieben.

    Bug-Form: «Wareneingang» an einem Verkaufs-Beleg. Ein Name, bei dem Ware das Haus
    verlässt, ist kein Name, sondern ein Irrtum mit Bestand.
    """
    from app.domain import procurement as p

    buy, sell = p.of(p.BUY), p.of(p.SELL)
    assert [buy.label_of(s) for s in p.STAGES] == ["Anfrage", "Bestellung", "Wareneingang"]
    assert [sell.label_of(s) for s in p.STAGES] == ["Angebot", "Zusage", "Geliefert"]
    assert buy.party_role == "supplier" and sell.party_role == "customer"
    # Der Ausgang gehört beiden Richtungen gleich – ein Storno ist ein Storno.
    assert buy.label_of(p.CANCELLED) == sell.label_of(p.CANCELLED) == "Storniert"
    # Und die alten Werte bleiben lesbar (Migration 122 ist das erste Netz, dies das zweite).
    assert p.normalize("anfrage") == p.STAGES[0]
    assert p.normalize("wareneingang") == p.STAGES[-1]
    assert p.normalize("storniert") == p.CANCELLED


def test_anyone_may_buy_from_us_but_being_a_supplier_is_a_permission():
    """►►► **Jeder darf Kunde sein. «Lieferant» ist dagegen eine Zulassung.** ◄◄◄

    Die Rolle sagt, was jemand **für uns** tut – nicht, ob er **bei uns** kaufen darf. Ein
    Mitarbeiter, der eine Schraube kauft, ist ein Kunde; ein Lieferant, der etwas bestellt,
    auch. Es gibt keinen Grund, sie auszuschliessen (Testnotiz #779).

    Beim **Einkauf** ist es umgekehrt: dort ist «Lieferant» eine Beziehung, die wir
    vergeben, und die Rolle bleibt eine echte Bedingung.

    Der Unterschied steht als **Daten** im ``Flow`` (``party_roles`` – leer heisst frei),
    nicht als ``if role == 'customer'``. Und **dieselbe** Angabe lesen beide Seiten: die
    Auswahlliste (``/orders/party-options``) und die Prüfung im Dienst
    (``_assert_allowed``) – sonst böte die Liste an, was der Dienst danach abweist.

    Bug-Formen: (a) der Verkauf verlangt eine Rolle; (b) der Einkauf verlangt keine mehr;
    (c) Liste und Dienst lesen zwei verschiedene Angaben.
    """
    from fastapi import HTTPException
    from app.domain import procurement
    from app.services import purchase as svc
    db = _db()
    try:
        # (a) **An einen Lieferanten verkaufen geht** – er ist auch nur jemand.
        lieferant = _user(db, "Würth AG", "supplier")
        art = _article(db, "Welle D", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [lieferant.object_id]}, actor=staff)
        db.flush()
        assert svc.of_step(db, rows[0].id).quotes, (
            "An einen Lieferanten liess sich nicht verkaufen – die Rolle wurde als "
            "Bedingung gelesen, obwohl sie beim Verkauf keine ist."
        )

        # (b) Beim **Einkauf** bleibt sie eine: ein Kunde ist kein Lieferant.
        kunde = _customer(db, "Meier Privat")
        buy_art = _article(db, "Rohteil D", steps=[{
            "module_type": "einkauf",
            "config": {"instruction": "liefern",
                       "suppliers": [{"supplier": lieferant.object_id, "ref": "W-1"}]}}])
        buy_order, buy_rows = _make(db, quantity=1, article=buy_art)
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=buy_order, step=buy_rows[0], action="ask",
                      payload={"suppliers": [kunde.object_id]}, actor=staff)
        assert err.value.status_code == 400

        # (c) **Eine Angabe, zwei Leser.** Der Flow sagt es, und die Prüfung liest ihn.
        assert procurement.FLOWS[procurement.SELL].party_roles == ()
        assert procurement.FLOWS[procurement.BUY].party_roles == ("supplier",)
        import pathlib
        src = pathlib.Path(svc.__file__).read_text(encoding="utf-8")
        body = src.split("def _assert_allowed")[1].split("\ndef ")[0]
        assert "flow.party_roles" in body, (
            "Der Dienst liest die Angabe nicht – dann kann die Auswahlliste anbieten, "
            "was er danach abweist."
        )
    finally:
        db.rollback(); db.close()


def test_a_sale_never_writes_a_landed_cost():
    """**Was ein Kunde zahlt, ist kein Einstandspreis.**

    Bug-Form: ``landed_cost`` auch beim Verkauf. Dann stünde der eigene Verkaufspreis am
    Artikel, und damit würde danach kalkuliert – derselbe stille Datenfehler wie beim
    Frachttarif (§9.8), nur teurer.
    """
    from app.domain import modules
    from app.models import Article
    from app.services import purchase as svc
    db = _db()
    try:
        assert modules.get("verkauf").landed_cost is False
        kunde = _customer(db)
        art = _article(db, "Welle E", steps=[_sell_step()])
        order, rows = _make(db, quantity=2, article=art)
        _commit(db, order, rows[0], kunde, amount=900)
        _deliver(db, order, rows[0])
        db.refresh(art)
        assert db.query(Article).filter(Article.id == art.id).first().landed_unit_cost is None, (
            "Der Verkaufspreis ist am Artikel gelandet."
        )
        assert svc.of_step(db, rows[0].id) is not None
    finally:
        db.rollback(); db.close()


def test_a_partial_delivery_keeps_the_document_open():
    """Teillieferung ist **Teilabschluss** – kein eigener Mechanismus.

    Bug-Form: der Beleg rückt beim ersten bestätigten Stück auf «Geliefert». Dann stünde
    da «erfüllt», während die Hälfte noch im Haus liegt.
    """
    from app.domain import procurement
    from app.services import process as proc, purchase as svc
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle F", steps=[_sell_step()], serialization="unit")
        order, rows = _make(db, quantity=3, article=art)
        _commit(db, order, rows[0], kunde)

        work = proc.step_work(db, order, rows[0])
        assert len(work) == 3, "Einzelserialisierung: drei Vorgänge."
        proc.confirm_step(db, order=order, step_id=rows[0].id, actor_id=None, values={},
                          instance_object_id=work[0]["instance_object_id"],
                          verification="scan")
        db.flush()
        assert svc.stage_of(svc.of_step(db, rows[0].id)) == procurement.BINDING, (
            "Der Beleg gilt schon als geliefert, obwohl noch etwas davorsteht."
        )
        _deliver(db, order, rows[0])
        assert svc.stage_of(svc.of_step(db, rows[0].id)) == procurement.STAGES[-1]
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §4 – das Geld
# ---------------------------------------------------------------------------

def test_open_and_due_are_derivations_not_columns():
    """**Offen = Forderungen − Zahlungen.** Eine Formel, jeder Fall darin.

    Und **eine Gutschrift ist eine negative Rechnung**, keine Zahlung: dabei fliesst kein
    Geld. Vorher war sie eine ``payment``-Zeile der Art ``credit`` – mit einer eigenen
    Regel dafür und einer dritten Summe in der Formel.

    Bug-Formen: (a) eine Spalte «offener Betrag» – sie müsste bei jeder Buchung nachgezogen
    werden, und die eine vergessene Stelle fällt erst auf, wenn jemand mahnt; (b) die
    Formel liest wieder die **Zusage** statt der Forderung; (c) die Gutschrift ist wieder
    eine Zahlung.
    """
    from decimal import Decimal
    from app.domain import money
    from app.models import Invoice, Payment
    from app.services import invoices, payments, purchase as svc
    db = _db()
    try:
        # (a) Keine Spalte darf das Ergebnis vorwegnehmen.
        for model in (Payment, Invoice):
            assert not set(model.__table__.columns.keys()) & {
                "open", "balance", "outstanding", "paid", "charged"}, (
                f"An «{model.__tablename__}» steht eine gerechnete Grösse als Spalte."
            )
        # (c) Und es gibt keine Art mehr – eine Gutschrift ist ein Vorzeichen.
        assert "kind" not in Payment.__table__.columns.keys(), (
            "Die Art ist zurück. Eine Gutschrift ist eine negative RECHNUNG; als "
            "Zahlungs-Art brauchte sie eine eigene Regel («hat keinen Zahlweg»)."
        )

        kunde = _customer(db)
        art = _article(db, "Welle G", steps=[_sell_step()])
        order, rows = _make(db, quantity=20, article=art)
        _commit(db, order, rows[0], kunde, amount=1400)
        row = svc.of_step(db, rows[0].id)

        # (b) **Zugesagt ist nicht gefordert.** Vor der Rechnung ist nichts offen – und
        #     genau das konnte die alte Formel nicht sagen.
        assert payments.balance(db, row).open == Decimal("0.00"), (
            "Ohne Rechnung ist etwas offen – dann liest die Formel wieder die Zusage."
        )
        assert payments.balance(db, row).uncharged == Decimal("1400.00"), (
            "«zugesagt, noch nicht berechnet» stimmt nicht."
        )

        invoices.record(db, purchase=row, amount=1400, number="R-1")
        assert payments.balance(db, row).open == Decimal("1400.00")
        payments.record(db, purchase=row, amount=1400, method=money.TRANSFER,
                        reference="ZE-1")
        assert payments.balance(db, row).settled, "Voll bezahlt ist offen null."

        # Zwei Stück zurück: 140 gutgeschrieben (negative Rechnung), 140 erstattet
        # (negative Zahlung) → wieder null.
        invoices.record(db, purchase=row, amount=-140, number="R-2")
        assert payments.balance(db, row).open == Decimal("-140.00"), (
            "Nach der Gutschrift schulden WIR – ein negativer Betrag ist eine Aussage."
        )
        payments.record(db, purchase=row, amount=-140, method=money.TRANSFER,
                        reference="ZE-2")
        assert payments.balance(db, row).settled
    finally:
        db.rollback(); db.close()


def test_the_same_reference_is_the_same_payment():
    """**Idempotent über die Referenz** – der Schutz gegen die doppelte Zustellung.

    Der Zahlungsdienst stellt seine Meldungen mehrfach zu; das ist zugesichert, nicht die
    Ausnahme. Zurück kommt die **bereits gebuchte Zeile**, kein Fehler: der Aufrufer hat
    bekommen, was er wollte.

    Bug-Form: jede Meldung bucht. Dann steht der Kunde nach drei Zustellungen mit dem
    dreifachen Betrag im Guthaben.
    """
    from app.domain import money
    from app.models import Payment
    from app.services import payments, purchase as svc
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle H", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        _commit(db, order, rows[0], kunde, amount=99)
        row = svc.of_step(db, rows[0].id)

        first = payments.record(db, purchase=row, amount=99, method=money.CARD,
                                reference="pi_abc")
        again = payments.record(db, purchase=row, amount=99, method=money.CARD,
                                reference="pi_abc")
        assert first.id == again.id, "Dieselbe Referenz hat zweimal gebucht."
        assert db.query(Payment).filter(Payment.purchase_id == row.id).count() == 1
    finally:
        db.rollback(); db.close()


def test_the_same_reference_at_another_document_is_named_not_swallowed():
    """►►► **Dieselbe Referenz an einem ANDEREN Beleg ist ein Irrtum – und er wird
    genannt.** ◄◄◄

    Die Idempotenz oben schützt gegen die doppelte Zustellung **desselben** Vorgangs. Sie
    suchte die Referenz aber im ganzen Haus und gab zurück, was sie fand – auch die Zeile
    eines **fremden** Belegs. Der Aufrufer bekam ``200``, an *seinem* Beleg war nichts
    gebucht, der offene Betrag stand unverändert da, und nichts sagte, warum.

    Ein stiller Nicht-Effekt ist schlimmer als ein Fehler: die Zahl auf dem Bildschirm
    sieht aus wie eine Auskunft und ist keine. Eine Referenz gehört zu genau einer Zahlung
    im Haus – so ist der Unique-Index gebaut, und so sind die beiden echten Quellen
    (``payment_intent``, QR-Referenz). Also: **409 mit dem Auftrag**, an dem sie schon
    hängt, damit der Mensch nicht suchen muss.

    Bug-Form: die fremde Zeile wird zurückgegeben. Dann bucht der zweite Beleg nichts und
    meldet nichts.
    """
    from app.domain import money
    from app.models import Payment
    from app.services import payments, purchase as svc
    from fastapi import HTTPException
    db = _db()
    try:
        kunde = _customer(db)
        ref = f"ZE-{uuid.uuid4()}"

        first_order, first_rows = _make(
            db, quantity=1, article=_article(db, "Welle R1", steps=[_sell_step()]))
        _commit(db, first_order, first_rows[0], kunde, amount=99)
        first_doc = svc.of_step(db, first_rows[0].id)
        payments.record(db, purchase=first_doc, amount=99, method=money.TRANSFER,
                        reference=ref)

        second_order, second_rows = _make(
            db, quantity=1, article=_article(db, "Welle R2", steps=[_sell_step()]))
        _commit(db, second_order, second_rows[0], kunde, amount=250)
        second_doc = svc.of_step(db, second_rows[0].id)

        with pytest.raises(HTTPException) as caught:
            payments.record(db, purchase=second_doc, amount=250, method=money.TRANSFER,
                            reference=ref)
        assert caught.value.status_code == 409, "Eine Kollision ist kein Eingabefehler."
        # **Der Satz muss den fremden Auftrag nennen** – sonst bleibt das Suchen beim
        # Menschen, und genau das soll eine Fehlermeldung abnehmen.
        assert str(first_order.object_id) in caught.value.detail, caught.value.detail
        assert ref in caught.value.detail, caught.value.detail
        # Und der zweite Beleg hat **nichts** – weder die fremde Zeile noch eine eigene.
        assert db.query(Payment).filter(Payment.purchase_id == second_doc.id).count() == 0

        # Am **eigenen** Beleg bleibt es idempotent: die Regel ist nicht verschärft
        # worden, sie ist nur genau geworden.
        same = payments.record(db, purchase=first_doc, amount=99, method=money.TRANSFER,
                               reference=ref)
        assert same.purchase_id == first_doc.id
        assert db.query(Payment).filter(Payment.purchase_id == first_doc.id).count() == 1
    finally:
        db.rollback(); db.close()


def test_money_flows_beside_the_stages_even_after_a_cancellation():
    """►►► **Geld ist keine vierte Stufe.** ◄◄◄

    Es fliesst, sobald zugesagt ist – und auch noch, wenn längst geliefert **oder
    storniert** ist: eine Anzahlung auf eine stornierte Bestellung muss erstattet werden
    können.

    Bug-Form: ``pay`` in ``STAGE_ACTIONS``. Dann verschwindet es mit der letzten Stufe,
    und eine Erstattung nach einem Storno wäre eine Sackgasse – dieselbe Fehlerform, die
    Testnotiz #775 schon einmal aufgemacht hat, nur mit Geld statt mit einem Modul.
    """
    from app.services import payments, purchase as svc
    db = _db()
    try:
        assert svc.PAY not in svc.ACTIONS, (
            "«pay» steht unter den Beleg-Verben – dort hängt alles an einer Stufe."
        )
        assert svc.INVOICE not in svc.ACTIONS, (
            "«invoice» steht unter den Beleg-Verben – dort hängt alles an einer Stufe, "
            "und damit wäre die Reihenfolge Ware→Forderung vorgeschrieben."
        )
        for verbs in svc.STAGE_ACTIONS.values():
            assert svc.PAY not in verbs and svc.INVOICE not in verbs

        kunde = _customer(db)
        art = _article(db, "Welle I", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        staff = _commit(db, order, rows[0], kunde, amount=200)
        row = svc.of_step(db, rows[0].id)
        assert svc.PAY in svc._can(db, row, staff), "Nach der Zusage lässt sich zahlen."
        assert svc.INVOICE in svc._can(db, row, staff), (
            "Die Forderung läuft ebenso neben den Stufen – sie darf vor der Lieferung "
            "stehen (Vorauszahlung) und danach (Zahlungsziel)."
        )

        svc.apply(db, order=order, step=rows[0], action=svc.INVOICE,
                  payload={}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action=svc.PAY,
                  payload={"amount": 200, "method": "transfer",
                           "reference": "ZE-9"}, actor=staff)
        assert payments.balance(db, row).settled

        # Storniert – und danach immer noch erstattbar.
        svc.apply(db, order=order, step=rows[0], action="revoke", payload={}, actor=staff)
        row = svc.of_step(db, rows[0].id)
        assert svc.PAY in svc._can(db, row, staff), (
            "Nach einem Storno lässt sich nichts mehr erstatten – das ist eine Sackgasse."
        )
        svc.apply(db, order=order, step=rows[0], action=svc.PAY,
                  payload={"amount": -200, "method": "transfer",
                           "reference": "ZE-9R"}, actor=staff)
        assert payments.balance(db, row).paid == 0
    finally:
        db.rollback(); db.close()


def test_nothing_is_payable_before_something_was_promised():
    """**Ohne Zusage keine Zahlung** – Geld ohne Grundlage ist kein Zahlungseingang.

    Bug-Form: zahlen auf ein Angebot, das niemand angenommen hat. Dann stünde eine Summe
    als «bezahlt», die nie vereinbart war.
    """
    from fastapi import HTTPException
    from app.services import purchase as svc
    db = _db()
    try:
        art = _article(db, "Welle J", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        staff = _staff(db)
        row = svc.of_step(db, rows[0].id)
        assert svc.PAY not in svc._can(db, row, staff)
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=rows[0], action=svc.PAY,
                      payload={"amount": 10, "method": "transfer"}, actor=staff)
        assert err.value.status_code == 409
        assert "angebot" in err.value.detail.lower(), (
            f"Der Satz nennt die Stufe nicht: {err.value.detail}"
        )
    finally:
        db.rollback(); db.close()


def test_a_credit_is_a_negative_invoice_and_needs_no_rule_of_its_own():
    """►►► **Die Regel «eine Gutschrift hat keinen Zahlweg» ist ERSATZLOS weg.** ◄◄◄

    Sie war nötig, solange die Gutschrift eine **Zahlung** war, bei der kein Geld fliesst –
    ein Widerspruch, den eine Ausnahme zusammenhalten musste. Als **negative Rechnung** ist
    sie schlicht richtig: eine Rechnung hat gar kein Feld für einen Zahlweg, also gibt es
    nichts zu verbieten. Eine Regel weniger, statt einer Ausnahme mehr.

    Und die Aussage bleibt erhalten: «wie viel hat der Kunde wirklich gezahlt» ist die
    Summe der Zahlungen, «was schuldet er noch» die Differenz zu den Forderungen.

    Bug-Formen: (a) die Art ist zurück (dann braucht es die Ausnahme wieder); (b) die
    Rechnung bekommt einen Zahlweg (dann sieht eine Gutschrift wie eine Überweisung aus);
    (c) die Gutschrift zählt nicht in die Forderung.
    """
    from decimal import Decimal
    from app.domain import money
    from app.models import Invoice
    from app.services import invoices, payments, purchase as svc
    db = _db()
    try:
        # (a) + (b): weder eine Art noch ein Zahlweg – und keine Ausnahme, die das regelt.
        assert not hasattr(money, "CREDIT") and not hasattr(money, "KINDS"), (
            "Die Art ist zurück – dann ist die Gutschrift wieder eine Zahlung, bei der "
            "kein Geld fliesst, und die Ausnahme dafür muss auch zurück."
        )
        assert "method" not in Invoice.__table__.columns.keys(), (
            "Eine Rechnung hat einen Zahlweg bekommen – dann sieht eine Gutschrift wie "
            "eine Überweisung aus."
        )

        # (c) Und sie **wirkt**: sie mindert die Forderung, ohne dass Geld fliesst.
        kunde = _customer(db)
        art = _article(db, "Welle K", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        _commit(db, order, rows[0], kunde, amount=50)
        row = svc.of_step(db, rows[0].id)
        invoices.record(db, purchase=row, amount=50, number="RK-1")
        invoices.record(db, purchase=row, amount=-10, number="RK-2", note="Kulanz")
        state = payments.balance(db, row)
        assert state.charged == Decimal("40.00"), "Die Gutschrift mindert die Forderung."
        assert state.paid == Decimal("0"), "Dabei ist kein Geld geflossen."
        assert state.open == Decimal("40.00")
    finally:
        db.rollback(); db.close()


def test_the_due_date_belongs_to_the_invoice_not_to_the_deal():
    """►►► **Fällig ist die RECHNUNG, nicht der Beleg.** ◄◄◄

    Vorher war es eine Ableitung aus dem Zusagedatum plus Frist. Das konnte genau einen
    Fall: **eine** Rechnung. Eine Zusage hat gar keine Fälligkeit – eine Rechnung schon,
    und **zwei Rechnungen haben zwei** (Anzahlung + Schlussrechnung).

    Die Frist bleibt als **Vorgabe** (``invoices.default_due``); gültig ist, was an der
    Rechnung steht. Und ohne Frist gibt es keine Fälligkeit – ein geratenes Datum wäre
    schlimmer als keines: daraus würde gemahnt.

    Bug-Formen: (a) die Fälligkeit hängt wieder am Beleg; (b) ohne Frist wird eine
    erfunden; (c) bei zwei Rechnungen gilt die **späteste** statt der frühesten offenen.
    """
    from app.services import invoices, payments, purchase as svc
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle L", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [kunde.object_id]}, actor=staff)
        row = svc.of_step(db, rows[0].id)
        assert invoices.due_on(db, row) is None, "Ohne Rechnung gibt es keinen Beginn."

        # ►► **Und ohne Frist gibt es keine Dauer** – auch wenn zugesagt ist. ◄◄
        #
        # Das ist die zweite Hälfte, und sie ist die wichtigere: ein Beleg mit Zusage,
        # aber ohne vereinbarte Zahlungsfrist, hat **kein** Fälligkeitsdatum. Wer hier
        # null Tage einsetzt, macht ihn am Tag der Zusage überfällig – und daraus würde
        # gemahnt. Ohne diese Zeile lief die Bug-Form durch: der Test prüfte nur den
        # Fall, in dem ohnehin nichts zugesagt war.
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": kunde.object_id, "amount": 100}, actor=staff)
        row = svc.of_step(db, rows[0].id)
        assert row.committed_on is not None, "Die Zusage hält ihren Tag fest."
        assert invoices.payment_days(row) is None
        assert invoices.default_due(row) is None, (
            "Ohne vereinbarte Frist wird eine Fälligkeit erfunden – ein geratenes Datum "
            "ist schlimmer als keines."
        )
        svc.apply(db, order=order, step=rows[0], action=svc.INVOICE, payload={},
                  actor=staff)
        assert invoices.due_on(db, row) is None, (
            "Die Rechnung hat eine Fälligkeit bekommen, obwohl keine Frist vereinbart ist."
        )
        assert invoices.is_overdue(
            db, row, today=datetime.date.today() + datetime.timedelta(days=365)) is False, (
            "Ein Beleg ohne Frist wird überfällig – dort ist nichts vereinbart, was "
            "verstreichen könnte."
        )

        # Jetzt **mit** Frist – ein zweiter Auftrag, denn nach der Zusage ist der erste
        # gebunden und nimmt keine Offerte mehr entgegen (genau das ist die Schwelle).
        order2, rows2 = _make(db, quantity=1, article=art, steps=[_sell_step()])
        svc.apply(db, order=order2, step=rows2[0], action="ask",
                  payload={"suppliers": [kunde.object_id]}, actor=staff)
        svc.apply(db, order=order2, step=rows2[0], action="quote",
                  payload={"supplier": kunde.object_id, "amount": 100, "lead_days": 5,
                           "payment_days": 30}, actor=staff)
        svc.apply(db, order=order2, step=rows2[0], action="order",
                  payload={"supplier": kunde.object_id, "amount": 100}, actor=staff)
        order, rows = order2, rows2
        row = svc.of_step(db, rows[0].id)
        assert invoices.payment_days(row) == 30
        svc.apply(db, order=order, step=rows[0], action=svc.INVOICE, payload={},
                  actor=staff)
        assert invoices.due_on(db, row) == datetime.date.today() + datetime.timedelta(days=30)
        assert invoices.is_overdue(db, row) is False, "Heute + 30 ist nicht überfällig."
        # Ein Beleg, der bezahlt ist, wird nicht überfällig – auch wenn das Datum vergeht.
        assert invoices.is_overdue(
            db, row, today=datetime.date.today() + datetime.timedelta(days=60)) is True
        # ►► (c) **Die FRÜHESTE offene Fälligkeit zählt**, nicht die späteste. ◄◄
        #    Eine zweite Rechnung mit späterem Datum darf die erste nicht verdecken –
        #    sonst mahnte niemand für die Anzahlung, die längst überfällig ist.
        invoices.record(db, purchase=row, amount=1, number="R-spaet",
                        due_on=datetime.date.today() + datetime.timedelta(days=90))
        assert invoices.due_on(db, row) == datetime.date.today() + datetime.timedelta(days=30), (
            "Die spätere Rechnung hat die frühere verdeckt."
        )
        payments.record(db, purchase=row, amount=101, method="transfer", reference="Z-1")
        assert invoices.is_overdue(
            db, row, today=datetime.date.today() + datetime.timedelta(days=60)) is False
    finally:
        db.rollback(); db.close()


def test_the_gate_and_the_hint_are_the_same_table():
    """**``can`` ist Auskunft UND Tor** – auch für die Handlungen ohne Stufe.

    Bug-Form: ``can`` ist nur ein Anzeige-Hinweis. Dann laufen Knopf und Tür beim nächsten
    Verb auseinander – der Knopf verschwindet, die Tür bleibt offen (oder umgekehrt).
    """
    from fastapi import HTTPException
    from app.services import purchase as svc
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle M", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        staff = _staff(db)
        row = svc.of_step(db, rows[0].id)

        # An der ersten Stufe steht «pay» nicht in `can` – und `apply` weist es ab.
        assert svc.PAY not in svc._can(db, row, staff)
        with pytest.raises(HTTPException):
            svc.apply(db, order=order, step=rows[0], action=svc.PAY,
                      payload={"amount": 5, "method": "transfer"}, actor=staff)

        # Ohne eingerichteten Zahlungsdienst gibt es den Zahllink gar nicht.
        _commit(db, order, rows[0], kunde, amount=5)
        row = svc.of_step(db, rows[0].id)
        from app.services import stripe_pay
        assert not stripe_pay.available(), "Der Test läuft ohne Schlüssel."
        assert svc.LINK not in svc._can(db, row, staff), (
            "Ein Zahllink wird angeboten, obwohl kein Dienst eingerichtet ist – ein Knopf, "
            "der nie etwas tun kann, ist kein Angebot."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §5 – der Zahlungsdienst
# ---------------------------------------------------------------------------

def _signed(payload: dict, secret: str = "whsec_testsecret") -> tuple[bytes, str]:
    """Eine echte Stripe-Signatur über den **rohen** Rumpf – so wie der Dienst sie baut."""
    import hashlib
    import hmac
    import json
    import time
    raw = json.dumps(payload).encode()
    ts = int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return raw, f"t={ts},v1={mac}"


def test_the_webhook_writes_one_line_and_nothing_else(monkeypatch):
    """►►► **Der Webhook bucht — und tut sonst nichts.** ◄◄◄

    Im Vorgängersystem erzeugte er **Aufträge** (`CheckoutIntent`, «Stripe ist Quelle der
    Wahrheit»), und daran hing die halbe Komplexität: Reservierungen ohne Auftrag, ein
    Aufräumer für verlassene Warenkörbe, Snapshot-Spalten an vier Tabellen. Hier nennt das
    ERP Betrag und Währung – der Dienst kassiert und meldet, mehr nicht.

    Geprüft wird mit **echter Signatur** über den rohen Rumpf: die Signatur gilt für die
    Bytes, und wer sie über ein neu serialisiertes Objekt prüfte, prüfte etwas anderes.

    Bug-Formen: (a) die doppelte Zustellung bucht zweimal; (b) eine gefälschte Signatur
    kommt durch; (c) ein fremdes Ereignis wird zum Fehler und damit endlos erneut
    zugestellt; (d) die Erstattung fällt mit der Zahlung zusammen (gleiche Referenz).
    """
    from fastapi import HTTPException
    from app.core.config import get_settings
    from app.models import Invoice, Payment
    from app.services import invoices, payments, purchase as svc, stripe_pay

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_testsecret")
    get_settings.cache_clear()
    # **Eine eindeutige Referenz je Lauf** – wie im echten Leben (Stripe-Ids sind es).
    # Und sie muss es hier sein: der Webhook **committet**, wie er es in Produktion tut,
    # also überlebt seine Zeile den Rollback am Testende. Eine feste Referenz fände beim
    # zweiten Lauf die alte Buchung wieder – genau das, wogegen die Idempotenz schützt,
    # nur diesmal gegen den Test selbst.
    intent = f"pi_{uuid.uuid4().hex[:16]}"
    # **Auch die Rechnungsnummer je Lauf eindeutig** – aus demselben Grund: der Webhook
    # committet, also überlebt alles in dieser Szene den Rollback am Testende. Eine feste
    # Nummer fiele beim zweiten Lauf in die eigene 409-Regel («gibt es bereits am
    # Auftrag …») – gemessen, nicht vermutet.
    number = f"RW-{uuid.uuid4().hex[:10]}"
    db = _db()
    try:
        assert stripe_pay.available(), "Mit Schlüssel ist der Dienst eingerichtet."
        kunde = _customer(db)
        art = _article(db, "Welle N", steps=[_sell_step()])
        order, rows = _make(db, quantity=2, article=art)
        staff = _commit(db, order, rows[0], kunde, amount=250)
        row = svc.of_step(db, rows[0].id)
        # ►► **Ohne Forderung kein Zahllink** – und das ist keine Hürde, sondern die
        #    Disziplin, die die dritte Achse bringt: man kassiert nicht, was niemand
        #    gefordert hat. Vorher lud der Link die **Zusage** ein, auch wenn nie eine
        #    Rechnung entstand.
        assert svc.LINK not in svc._can(db, row, staff), (
            "Der Zahllink erscheint, bevor überhaupt etwas gefordert wurde."
        )
        invoices.record(db, purchase=row, amount=250, number=number)
        assert svc.LINK in svc._can(db, row, staff), (
            "Mit eingerichtetem Dienst und offener Forderung gibt es den Zahllink."
        )

        paid = {"type": stripe_pay.PAID, "data": {"object": {
            "id": "cs_1", "payment_intent": intent, "amount_total": 25000,
            "metadata": {"purchase_id": str(row.id)}}}}
        raw, sig = _signed(paid)
        assert stripe_pay.handle_webhook(db, raw=raw, signature=sig) == "paid"
        # **Dieselbe Meldung ein zweites Mal** – der Dienst stellt mehrfach zu.
        assert stripe_pay.handle_webhook(db, raw=raw, signature=sig) == "paid"
        assert len(payments.of_purchase(db, row)) == 1, (
            "Die doppelte Zustellung hat zweimal gebucht."
        )
        assert payments.balance(db, row).settled

        refund = {"type": stripe_pay.REFUNDED, "data": {"object": {
            "payment_intent": intent, "amount_refunded": 5000}}}
        raw2, sig2 = _signed(refund)
        assert stripe_pay.handle_webhook(db, raw=raw2, signature=sig2) == "refunded"
        assert len(payments.of_purchase(db, row)) == 2, (
            "Die Erstattung fiel mit der Zahlung zusammen – sie braucht eine EIGENE "
            "Referenz, sonst wirft die Idempotenz sie weg."
        )
        assert payments.balance(db, row).open == 50

        # Eine gefälschte Signatur ist kein fremdes Ereignis, sondern ein fremder Absender.
        with pytest.raises(HTTPException) as err:
            stripe_pay.handle_webhook(db, raw=raw, signature="t=1,v1=deadbeef")
        assert err.value.status_code == 400

        # Und ein Ereignis, das uns nichts angeht, wird **quittiert** – ein Fehlercode
        # brächte den Dienst nur dazu, es endlos erneut zuzustellen.
        raw3, sig3 = _signed({"type": "invoice.paid", "data": {"object": {}}})
        assert stripe_pay.handle_webhook(db, raw=raw3, signature=sig3) == "ignored"
    finally:
        # Der Webhook hat committet – die zwei Zeilen gehören aufgeräumt, sonst wächst
        # die Wächter-Datenbank mit jedem Lauf um Buchungen, die niemand mehr liest.
        db.rollback()
        db.query(Payment).filter(Payment.reference.like(f"{intent}%")).delete(
            synchronize_session=False)
        db.query(Invoice).filter(Invoice.number == number).delete(
            synchronize_session=False)
        db.commit()
        db.close()
        get_settings.cache_clear()


def test_the_route_hands_over_the_raw_bytes_not_a_reserialised_object(monkeypatch):
    """►►► **Der Webhook wird über die ROUTE geprüft, nicht nur über den Dienst.** ◄◄◄

    Der Wächter darüber ruft ``handle_webhook`` unmittelbar – er prüft die Regel, aber
    nicht die Schicht davor: das Lesen des **rohen** Rumpfs, den Kopfzeilen-Alias
    ``Stripe-Signature`` und die Statuscodes. Genau dort sitzt die Fehlerklasse «ein Feld,
    das nie ankommt».

    **Der Rumpf trägt darum Leerraum, den kein Serialisierer so erzeugt.** Wer den Rumpf
    parst und neu schreibt (``await request.json()``), signiert danach *andere* Bytes –
    die Prüfung schlägt fehl, und der Wächter meldet `400` statt `200`. Mit einem
    gewöhnlich formatierten Rumpf käme eine solche Fassung durch, und der Wächter wäre
    stumpf.

    **Es wird nichts gebucht**: ein fremdes Ereignis kommt bis zur Signaturprüfung und
    keinen Schritt weiter. Der Wächter braucht darum keinen Beleg, keine Datenbank und
    kein Aufräumen – die Buchung selbst prüft der Wächter darüber.

    Bug-Formen: (a) der Rumpf wird neu serialisiert; (b) die Kopfzeile heisst anders und
    kommt nie an; (c) ein fremdes Ereignis wird zum Fehlercode – dann stellt der Dienst
    es endlos erneut zu.
    """
    import hashlib
    import hmac
    import time
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    import app.main as main

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_testsecret")
    get_settings.cache_clear()
    try:
        # Ungewöhnlicher Leerraum: dieselben Daten, andere Bytes – daran scheitert jede
        # Fassung, die den Rumpf durch einen Serialisierer schickt.
        raw = b'{"type":   "invoice.paid",\n  "data": {"object": {}}}'
        ts = int(time.time())
        mac = hmac.new(b"whsec_testsecret", f"{ts}.".encode() + raw,
                       hashlib.sha256).hexdigest()

        client = TestClient(main.app)
        good = client.post("/api/v1/payments/webhook", content=raw,
                           headers={"Stripe-Signature": f"t={ts},v1={mac}"})
        assert good.status_code == 200, good.text
        assert good.json() == {"status": "ignored"}, (
            "Ein fremdes Ereignis wird quittiert, nicht abgelehnt."
        )

        # Ein fremder Absender ist etwas anderes als ein fremdes Ereignis.
        bad = client.post("/api/v1/payments/webhook", content=raw,
                          headers={"Stripe-Signature": "t=1,v1=deadbeef"})
        assert bad.status_code == 400, bad.text

        # Und ganz ohne Kopfzeile erst recht – nicht etwa 500.
        none = client.post("/api/v1/payments/webhook", content=raw)
        assert none.status_code == 400, none.text
    finally:
        get_settings.cache_clear()


def test_without_a_key_there_is_no_payment_service_at_all():
    """**Ohne Schlüssel gibt es den Dienst nicht** – kein Stub, kein 503, kein Knopf.

    Ein «abgeschaltet» zu melden, wo schlicht nichts eingerichtet ist, wäre eine Auskunft,
    die nicht stimmt. Und eine **Überweisung ist kein Fallback**, sondern der B2B-
    Normalfall: der alte `manual`-Provider simulierte einen Zahlungsdienstleister samt
    eigener Bezahlseite – er kommt nicht zurück.

    Bug-Form: ein zweiter Provider neben Stripe. Dann gäbe es zwei Wege zu einer Zahlung,
    und der zweite bekäme den nächsten Fix nicht mit.
    """
    from fastapi import HTTPException
    from app.services import purchase as svc, stripe_pay

    assert not stripe_pay.available(), "Der Test läuft ohne Schlüssel."
    assert not (BACKEND / "app" / "services" / "payments").is_dir(), (
        "Es gibt wieder ein Provider-Paket – eine Abstraktion über einer Zeile."
    )
    src = (BACKEND / "app" / "services" / "payments.py").read_text(encoding="utf-8")
    assert "stripe" not in src.lower(), (
        "Der Zahlungs-Dienst kennt den Anbieter – dann ist er keine Schreibstelle mehr, "
        "sondern eine Anbindung."
    )
    db = _db()
    try:
        kunde = _customer(db)
        art = _article(db, "Welle O", steps=[_sell_step()])
        order, rows = _make(db, quantity=1, article=art)
        _commit(db, order, rows[0], kunde, amount=10)
        with pytest.raises(HTTPException) as err:
            stripe_pay.checkout_url(db, purchase=svc.of_step(db, rows[0].id), label="x")
        assert err.value.status_code == 404, (
            "Ohne eingerichteten Dienst ist die Antwort 404 – «abgeschaltet» wäre falsch."
        )
    finally:
        db.rollback(); db.close()
