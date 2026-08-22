"""**Beschaffen: ein Tor, drei Stufen — und das Modul räumt selbst auf.**

Die Regeln, die dabei entstanden sind, gehören nicht diesem Modul, sondern dem Rahmen:

1. **Das Modul erzeugt keine Einzelinstanzen.** Die entstehen bei der Freigabe eines
   Erzeugungsauftrags; ein Beschaffungs-Modul lässt sie passieren. Und **eine Leistung
   taucht darum nie im Bestand auf** – nicht weil ein Feld sie ausschliesst, sondern weil
   hier nichts entsteht.
2. **Die Stufen gehören dem Beleg, nicht dem Stück.** Die Einzelinstanz ist von der
   Anfrage bis zum Wareneingang durchgehend ``Im Prozess``.
3. **Teillieferung = Teilabschluss** – kein eigener Mechanismus: ``confirm_step`` ist ein
   Teilabschluss, und solange etwas davorsteht, bleibt der Beleg in «Bestellung».
4. **Ein Modul räumt selbst auf.** Jede Zusage nach aussen hat ihre Gegenhandlung an
   derselben Stelle, und es ist **eine**: was ``revoke`` bewirkt, sagt die Stufe. Was
   **Stücke** betrifft, entscheidet dagegen ein Mensch – dieses Modul legt keinen Auftrag
   an.
5. **Vor der Bestellung zieht die Menge still nach, ab ihr wird geklärt.** Ab «Bestellung»
   ist eine zweite Partei gebunden; eine stille Änderung wäre ein Beleg, der nicht mehr
   stimmt.

Geprüft über die **echten** Dienstpfade gegen echtes PostgreSQL.
"""

import os
import pathlib

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


def _supplier(db, name: str):
    from app.models import UserProfile
    from app.services import objects as obj
    import uuid
    user = UserProfile(
        firebase_uid=f"test-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.test",
        company_name=name, role="supplier", object_id=obj.next_object_id(db),
    )
    db.add(user)
    db.flush()
    return user


def _article(db, name: str, *, steps: list[dict] | None = None,
             serialization: str = "batch", moq=None):
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization=serialization, min_order_qty=moq)
    db.add(art)
    db.flush()
    if steps:
        tpl.create_steps(db, art, steps)
        db.flush()
    return art


def _buy_step(suppliers, instruction: str = "liefern"):
    """Ein Beschaffungs-Modul – **ohne Artikel**: den sagt der Prozess."""
    return {"module_type": "beschaffen",
            "config": {"instruction": instruction,
                       "suppliers": [s.object_id for s in suppliers]}}


def _total(db, order, row) -> int:
    """Die Gesamtmenge des Belegs – die Summe seiner (abgeleiteten) Zeilen."""
    from app.services import purchase as svc
    return sum(int(line["quantity"]) for line in svc.lines_of(db, order, row))


def _make(db, *, quantity: int, article, steps=None):
    """Ein freigegebener Erzeugungsauftrag über diesen Artikel."""
    from app.models import ProcessStep
    from app.services import process as proc
    order = proc.release(
        db,
        lines=[{"article_object_id": article.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=steps or [], actor_id=None,
    )
    db.flush()
    rows = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position).all())
    return order, rows


def _staff(db):
    from app.models import UserProfile
    from app.services import objects as obj
    import uuid
    user = UserProfile(firebase_uid=f"staff-{uuid.uuid4()}",
                       email=f"{uuid.uuid4()}@example.test", role="employee",
                       object_id=obj.next_object_id(db))
    db.add(user)
    db.flush()
    return user


def _confirm_all(db, order, step):
    """Wareneingang, bis nichts mehr davorsteht – **nach jedem Vorgang neu gefragt**.

    Ein Vorgang ist EINE Instanz (Scan-Regel); was dabei sonst noch vorrückt (der
    ungezogene Rest einer Stichprobe), entscheidet der Prozess. Eine vorab genommene
    Liste abzuarbeiten hiesse, den zweiten Vorgang auf einem Stand zu fahren, den es
    nach dem ersten nicht mehr gibt.
    """
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
# §1 – das Modul erzeugt nichts
# ---------------------------------------------------------------------------

def test_the_module_never_creates_a_single_unit():
    """**Einzelinstanzen entstehen bei der Freigabe, nicht durch dieses Modul.**

    Bug-Form: ein Wareneingang, der Stücke «anlegt». Dann gäbe es zwei Erzeugungswege,
    und eine gekaufte Leistung («Härten») stünde plötzlich als Bestand im Lager.
    """
    from app.models import InstanceUnit
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        # Der Prozess des Artikels: eine einzige Beschaffung.
        art = _article(db, "Schraube M6 (Zukauf)", steps=[_buy_step([wuerth])])

        before = db.query(InstanceUnit).count()
        order, rows = _make(db, quantity=5, article=art)
        after_release = db.query(InstanceUnit).count()
        assert after_release - before == 5, "Die Freigabe erzeugt die Stücke."

        row = svc.of_step(db, rows[0].id)
        assert row is not None, "Die Freigabe legt den Beleg an."
        assert row.stage == "anfrage"

        # Bestellen und Ware buchen – dabei entsteht **kein einziges** neues Stück.
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 84}, actor=staff)
        _confirm_all(db, order, rows[0])
        assert db.query(InstanceUnit).count() == after_release, (
            "Das Beschaffungs-Modul hat Einzelinstanzen erzeugt – der einzige Weg dorthin "
            "ist die Freigabe eines Erzeugungsauftrags."
        )
    finally:
        db.rollback(); db.close()


def test_a_service_is_an_instruction_not_an_article():
    """**Eine Leistung braucht keinen Artikel** – sie ist der Auftrag an den Lieferanten.

    «Härten» wird an einem Stück gekauft, das es schon gibt: auf dem Beleg steht die
    **Welle** (sie steht vor dem Modul), und was mit ihr geschehen soll, steht als Satz
    daneben. Vorher war «Härten» ein eigener Artikel – ein Datensatz, der nie Material
    wird, in Bestand, Stückliste und Auswahl aber wie einer aussieht.

    Bug-Form: der Beleg nennt einen anderen Artikel als den, dessen Stücke davorstehen.
    Dann bestellt man etwas, das mit dem Auftrag nichts zu tun hat.
    """
    from app.models import Instance
    from app.services import purchase as svc
    db = _db()
    try:
        hardener = _supplier(db, "Härterei Meier")
        shaft = _article(db, "Welle",
                         steps=[_buy_step([hardener], "Härten auf 58 HRC")])
        order, rows = _make(db, quantity=3, article=shaft)
        staff = _staff(db)

        facts = svc.embed_data(db, order=order, step=rows[0])
        assert [l["article_object_id"] for l in facts["lines"]] == [shaft.object_id], (
            "Der Beleg nennt einen anderen Artikel als den, dessen Stücke davorstehen."
        )
        assert facts["instruction"] == "Härten auf 58 HRC", (
            "Was der Lieferant tun soll, steht nirgends – die Spezifikation beschreibt "
            "die Sache, nicht den Auftrag."
        )

        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [hardener.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": hardener.object_id, "amount": 150}, actor=staff)
        _confirm_all(db, order, rows[0])

        assert db.query(Instance).filter(Instance.article_id == shaft.id).count() == 1, (
            "Das Härten hat Bestand erzeugt – es ist aber eine Leistung an einem Stück, "
            "das es schon gibt."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §2 – die Stufen gehören dem Beleg
# ---------------------------------------------------------------------------

def test_the_stages_belong_to_the_document_not_to_the_piece():
    """Von der Anfrage bis zum Wareneingang ist die Einzelinstanz ``Im Prozess``.

    Bug-Form: «angefragt»/«bestellt» als Zustand des Stücks. Das wären Zustände, die
    nichts über das Material aussagen – und sie stünden in der Bestandsleiste.
    """
    from app.domain import statuses as st
    from app.models import InstanceUnit, OrderUnit
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        target = _article(db, "Schraube M6")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])])
        order, rows = _make(db, quantity=4, article=art)
        staff = _staff(db)

        def states():
            return {
                u.status for u in db.query(InstanceUnit)
                .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
                .filter(OrderUnit.order_id == order.id).all()
            }

        assert states() == {st.IM_PROZESS}
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        assert states() == {st.IM_PROZESS}, "Die Anfrage hat den Zustand des Stücks verändert."
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 84}, actor=staff)
        assert states() == {st.IM_PROZESS}, "Die Bestellung hat den Zustand verändert."

        # Und die Stufen selbst sind drei, immer dieselben.
        facts = svc.embed_data(db, order=order, step=rows[0])
        assert [s["key"] for s in facts["stages"]] == ["anfrage", "bestellung", "wareneingang"]
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §3 – Teillieferung ist ein Teilabschluss
# ---------------------------------------------------------------------------

def test_a_partial_delivery_is_a_partial_confirmation():
    """300 von 500 da → 300 rücken vor, der Beleg bleibt in «Bestellung».

    Bug-Form: der Wareneingang gilt beim ersten Stück als vollständig. Dann stünde der
    Rest als geliefert da, ohne je angekommen zu sein.
    """
    from app.services import process as proc, purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])],
                       serialization="unit")
        order, rows = _make(db, quantity=3, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 30}, actor=staff)

        work = proc.step_work(db, order, rows[0])
        assert len(work) == 3, "Einzelserialisierung: drei Instanzen, drei Vorgänge."
        proc.confirm_step(db, order=order, step_id=rows[0].id, actor_id=None, values={},
                          instance_object_id=work[0]["instance_object_id"],
                          verification="scan")
        db.flush()
        assert svc.of_step(db, rows[0].id).stage == "bestellung", (
            "Der Beleg gilt schon als geliefert, obwohl noch etwas davorsteht."
        )
        for row in proc.step_work(db, order, rows[0]):
            proc.confirm_step(db, order=order, step_id=rows[0].id, actor_id=None,
                              values={}, instance_object_id=row["instance_object_id"],
                              verification="scan")
        db.flush()
        assert svc.of_step(db, rows[0].id).stage == "wareneingang"
        assert art.landed_unit_cost is not None, (
            "Der Einstandspreis wandert beim Abschluss an den Artikel – Summe ÷ Menge."
        )
    finally:
        db.rollback(); db.close()


def test_nothing_arrives_before_it_was_ordered():
    """Ein Wareneingang ohne Bestellung ist ein Beleg ohne Anlass."""
    from fastapi import HTTPException
    from app.services import process as proc, purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        target = _article(db, "Schraube M6")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])])
        order, rows = _make(db, quantity=2, article=art)
        work = proc.step_work(db, order, rows[0])
        with pytest.raises(HTTPException) as err:
            proc.confirm_step(db, order=order, step_id=rows[0].id, actor_id=None,
                              values={}, instance_object_id=work[0]["instance_object_id"],
                              verification="scan")
        assert err.value.status_code == 409
        assert "bestellt" in err.value.detail.lower()
        assert svc.of_step(db, rows[0].id).stage == "anfrage"
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §4 – das Modul räumt selbst auf
# ---------------------------------------------------------------------------

def test_one_counter_action_and_the_stage_says_what_it_does():
    """``revoke`` nimmt vor der Bestellung die Anfrage zurück – danach storniert es.

    Bug-Form: zwei Verben («zurückziehen» und «stornieren») für dieselbe Sache. Dann
    entscheidet der Aufrufer, was gerade gilt – und irgendwann falsch.
    """
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        target = _article(db, "Schraube M6")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])])
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)

        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        assert len(svc.of_step(db, rows[0].id).quotes) == 1
        svc.apply(db, order=order, step=rows[0], action="revoke", payload={}, actor=staff)
        assert svc.of_step(db, rows[0].id).quotes == [], "Die Anfrage steht noch."
        assert svc.of_step(db, rows[0].id).stage == "anfrage", (
            "Zurückziehen hat storniert – vor der Bestellung war aber nichts zugesagt."
        )

        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 20}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="revoke", payload={}, actor=staff)
        assert svc.of_step(db, rows[0].id).stage == "storniert", (
            "Nach der Bestellung muss «zurück» eine Stornierung sein – dort liegt eine "
            "Bestellung beim Lieferanten."
        )
    finally:
        db.rollback(); db.close()


def test_a_cancelled_document_keeps_the_way_it_walked():
    """Ein Storno macht die Bestellung nicht ungeschehen.

    Die Kette sagt die **Vergangenheit** (dieselbe Regel wie die Prozesslinie): sie steht
    still da, wo sie stehengeblieben ist, und der Satz daneben sagt, dass nichts mehr
    ankommt. Bug-Form: bei ``storniert`` findet die Stufen-Ableitung ihren Platz nicht
    mehr und setzt alles auf grau – dann sähe ein stornierter Beleg aus wie einer, bei
    dem nie etwas geschehen ist, und man könnte die beiden nicht unterscheiden.
    """
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])])
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)

        def stages() -> dict[str, dict]:
            data = svc.embed_data(db, order=order, step=rows[0], viewer=staff)
            return {s["key"]: s for s in data["stages"]}

        assert stages()["anfrage"]["active"] is True

        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 20}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="revoke", payload={}, actor=staff)

        after = stages()
        assert after["anfrage"]["done"] and after["bestellung"]["done"], (
            "Der stornierte Beleg hat seine Vergangenheit verloren: angefragt und "
            "bestellt WURDE, das bleibt gegangen."
        )
        assert not after["wareneingang"]["done"], "Angekommen ist nichts."
        assert not any(s["active"] for s in after.values()), (
            "Storniert ist keine Stufe – es ist keine mehr an der Reihe."
        )
        assert not any(s["verb"] for s in after.values()), (
            "Ein Verb an einem stornierten Beleg bietet eine Handlung an, die es nicht "
            "mehr gibt."
        )
    finally:
        db.rollback(); db.close()


def test_before_the_order_the_quantity_follows_after_it_we_ask():
    """**Vor der Bestellung still nachziehen, ab ihr klären.**

    Bug-Form: die Menge zieht auch nach der Bestellung still nach. Dann steht auf dem
    Beleg eine andere Zahl als beim Lieferanten, und niemand hat es gemerkt.
    """
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        target = _article(db, "Schraube M6")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])])
        order, rows = _make(db, quantity=5, article=art)
        staff = _staff(db)
        row = svc.of_step(db, rows[0].id)
        assert _total(db, order, row) == 5

        # Ein Stück verlässt den Auftrag (eine Abweichung greift zu) – noch nicht bestellt.
        from app.models import OrderUnit
        from datetime import datetime, timezone
        taken = (db.query(OrderUnit)
                 .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
                 .first())
        taken.released_at = datetime.now(timezone.utc)
        db.flush()
        svc.rebase(db, order)
        assert _total(db, order, svc.of_step(db, rows[0].id)) == 4, (
            "Vor der Bestellung ist niemand ausser uns beteiligt – die Menge zieht nach."
        )

        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 40}, actor=staff)

        # Jetzt geht noch eines weg – ab hier ist eine zweite Partei gebunden.
        again = (db.query(OrderUnit)
                 .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
                 .first())
        again.released_at = datetime.now(timezone.utc)
        db.flush()
        svc.rebase(db, order)
        row = svc.of_step(db, rows[0].id)
        assert _total(db, order, row) == 4, (
            "Die Menge hat sich nach der Bestellung still geändert – der Beleg beim "
            "Lieferanten sagt etwas anderes."
        )
        assert svc.mismatch(db, order, row) == 3, "Die Abweichung wird nicht gemeldet."

        svc.apply(db, order=order, step=rows[0], action="clarified", payload={}, actor=staff)
        row = svc.of_step(db, rows[0].id)
        assert _total(db, order, row) == 3
        assert svc.mismatch(db, order, row) is None
    finally:
        db.rollback(); db.close()


def test_the_module_never_creates_an_order():
    """**Was Stücke betrifft, entscheidet ein Mensch.**

    Bug-Form: das Modul legt bei einer Abweichung selbst einen Auftrag an. Dann zöge es
    Stücke aus einem Auftrag, ohne dass jemand zugestimmt hätte.
    """
    src = (BACKEND / "app" / "services" / "purchase.py").read_text(encoding="utf-8")
    for forbidden in ("release(", "create_deviation", "Order(", "next_object_id"):
        assert forbidden not in src, (
            f"`services/purchase` legt etwas an («{forbidden}») – ein Modul räumt selbst "
            f"auf, aber es legt nie einen Auftrag an."
        )


# ---------------------------------------------------------------------------
# §5 – die Lieferantensicht
# ---------------------------------------------------------------------------

def test_a_supplier_never_sees_a_foreign_quote():
    """Konkurrenzpreise sind kein Nebeneffekt einer Ansicht.

    Bug-Form: der Beleg trägt alle Angebotszeilen, und die Oberfläche filtert. Ein
    Filter dort ist eine Bitte – die Antwort selbst muss die Grenze ziehen.
    """
    from app.services import purchase as svc
    db = _db()
    try:
        a = _supplier(db, "Würth AG")
        b = _supplier(db, "Bossard AG")
        target = _article(db, "Schraube M6")
        art = _article(db, "Schraube", steps=[_buy_step([a, b])])
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [a.object_id, b.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="quote",
                  payload={"supplier": a.object_id, "amount": 84, "lead_days": 3}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="quote",
                  payload={"supplier": b.object_id, "amount": 79, "lead_days": 6}, actor=staff)

        full = svc.embed_data(db, order=order, step=rows[0])
        assert len(full["quotes"]) == 2, "Das Personal sieht den Angebotsspiegel."

        mine = svc.embed_data(db, order=order, step=rows[0], viewer=b)
        assert [q["supplier_object_id"] for q in mine["quotes"]] == [b.object_id], (
            "Ein Lieferant sieht eine fremde Angebotszeile."
        )
        assert [q["supplier_object_id"] for q in mine["allowed"]] == [b.object_id], (
            "Ein Lieferant sieht, wer sonst zugelassen ist – auch das ist fremd."
        )
    finally:
        db.rollback(); db.close()


def test_a_supplier_offers_and_the_buyer_orders():
    """Die Verantwortungstrennung ist der Sinn des Portals."""
    from fastapi import HTTPException
    from app.services import purchase as svc
    db = _db()
    try:
        a = _supplier(db, "Würth AG")
        b = _supplier(db, "Bossard AG")
        target = _article(db, "Schraube M6")
        art = _article(db, "Schraube", steps=[_buy_step([a, b])])
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [a.object_id, b.object_id]}, actor=staff)

        # Der Lieferant füllt SEINE Zeile – ohne sie zu benennen, er ist sie.
        svc.apply(db, order=order, step=rows[0], action="quote",
                  payload={"amount": 84, "lead_days": 3, "supplier": b.object_id}, actor=a)
        quotes = {q["supplier"]: q for q in svc.of_step(db, rows[0].id).quotes}
        assert quotes[a.object_id]["state"] == "offeriert", (
            "Der Lieferant hat die Zeile eines anderen gefüllt."
        )
        assert quotes[b.object_id]["state"] == "angefragt"

        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=rows[0], action="order",
                      payload={"supplier": a.object_id, "amount": 84}, actor=a)
        assert err.value.status_code == 403
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §6 – die Definition
# ---------------------------------------------------------------------------

def test_a_supplier_sees_his_module_and_nothing_else():
    """**Die Lieferanten-Sicht ist eine Spiegelung, keine zweite Antwort.**

    Ein Lieferant sieht die Aufträge, in denen er **angefragt** ist – und von jedem nur
    sein eigenes Modul. Alles andere ist der interne Lauf: der Prozess-Graph, die
    Historie, die Nachbar-Aufträge, die Positionen.

    Geprüft wird über die **echten Router-Funktionen**, denn genau dort sitzt die Regel.

    Bug-Formen: (a) die Antwort trägt den internen Lauf mit (Datenleck); (b) sie zeigt
    fremde Module; (c) ein Lieferant kommt an einen Auftrag, in dem er nicht angefragt
    ist; (d) er kann an einem fremden Modul handeln.
    """
    import pytest as _pytest
    from fastapi import HTTPException
    from app.routers import orders as router
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        other = _supplier(db, "Fremd AG")
        art = _article(db, "Schraube", steps=[
            _buy_step([wuerth]),
            {"module_type": "datenerfassung",
             "config": {"points": [{"key": "t", "type": "text", "label": "Notiz"}]}},
        ])
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        db.flush()

        full = router._to_response(db, order, viewer=staff)
        assert len(full.steps) == 2 and full.flow is not None

        seen = router._to_response(db, order, viewer=wuerth)
        assert [s.id for s in seen.steps] == [rows[0].id], (
            "Der Lieferant sieht ein Modul, das ihn nichts angeht."
        )
        # **Leer heisst: der Vorgabewert** – dasselbe, was ``_mine_only`` setzt. Auf
        # «falsy» zu prüfen ginge daneben: ein leerer Graph ist ein Objekt und damit wahr.
        from app.schemas.order import OrderResponse as _Resp
        for field in router._INTERNAL_FIELDS:
            empty = _Resp.model_fields[field].get_default(call_default_factory=True)
            assert getattr(seen, field) == empty, (
                f"«{field}» verrät den internen Lauf des Auftrags: {getattr(seen, field)!r}"
            )
        # **Und die Prüfung muss etwas sagen können**: diese vier tragen in genau dieser
        # Szene beim Personal wirklich Inhalt. Ohne sie wäre «beim Lieferanten leer» auch
        # dann erfüllt, wenn die Verengung gar nicht liefe.
        for field in ("lines", "flow", "events", "event_count"):
            empty = _Resp.model_fields[field].get_default(call_default_factory=True)
            assert getattr(full, field) != empty, (
                f"«{field}» ist auch beim Personal leer – die Prüfung sagt dann nichts."
            )
        assert seen.object_id == order.object_id and seen.name == full.name, (
            "Es ist derselbe Auftrag – nur sein Teil davon."
        )

        # (c) Ein Lieferant, der nicht angefragt ist, sieht den Auftrag gar nicht.
        with _pytest.raises(HTTPException) as caught:
            router._to_response(db, order, viewer=other)
        assert caught.value.status_code == 404, (
            "403 bestätigt, dass es den Auftrag gibt – 404 sagt nichts."
        )

        # (d) Und er handelt nur an seinem Modul.
        assert router._visible(db, order, wuerth) == {rows[0].id}
        assert router._visible(db, order, staff) is None
    finally:
        db.rollback(); db.close()


def test_one_supplier_is_a_list_with_one_entry():
    """**n statt 1**: der Angebotsvergleich ist kein zweiter Mechanismus."""
    from fastapi import HTTPException
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    m = modules.get("beschaffen")
    one = m.clean_config({"suppliers": [100000001], "instruction": "liefern"})
    assert one["suppliers"] == [100000001]
    three = m.clean_config({"suppliers": [1, 2, 3], "instruction": "liefern"})
    assert three["suppliers"] == [1, 2, 3]

    with pytest.raises(HTTPException):
        m.clean_config({"suppliers": [], "instruction": "liefern"})
    with pytest.raises(HTTPException):
        m.clean_config({"suppliers": [1, 1], "instruction": "liefern"})

    # **Kein Artikelfeld – und es kommt auch nicht durch die Hintertür zurück.**
    assert "article" not in m.clean_config({"suppliers": [1], "instruction": "x",
                                            "article": 42}), (
        "Die Konfiguration nimmt wieder einen Artikel entgegen – damit gibt es zwei "
        "Aussagen darüber, was bestellt wird."
    )


def test_the_module_is_a_pass_through_and_not_an_exit():
    """Ein Tor, kein Ausgang: hinter ihm darf etwas stehen, und es verändert nichts."""
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules, statuses as st

    m = modules.get("beschaffen")
    assert m.status_before == st.IM_PROZESS and m.status_after == st.IM_PROZESS
    assert not m.terminal, (
        "Ein terminales Beschaffungs-Modul wäre ein Ausgang – dahinter dürfte kein Modul "
        "mehr stehen, und ein Zukaufteil könnte nie geprüft werden."
    )
    assert m.requires_verification, "Der Wareneingang wird gescannt."
    assert m.units_may_leave, (
        "Ein Stück darf herausgenommen werden – nur nicht still. Das Modul reagiert "
        "(`rebase`), statt zu sperren."
    )


def test_the_quantity_is_never_an_input():
    """**Die Bestellmenge kommt aus dem Prozess** – sie lässt sich nicht eintragen.

    Ein Beschaffungs-Modul sitzt in einem Ablauf: wie viel bestellt wird, sagen die
    Einzelinstanzen, die davorstehen. Eine getippte Menge daneben wäre eine zweite
    Aussage über dieselbe Sache – und die getippte gewinnt, auch wenn sie falsch ist.

    Bug-Form: ``ask``/``order`` nehmen eine Menge aus der Nutzlast entgegen. Dann steht
    auf dem Beleg eine Zahl, die mit dem Auftrag nichts zu tun hat.

    *Die Mindestbestellmenge des Artikels wird hier bewusst NICHT aufgeschlagen*: das
    Modul erzeugt keine Einzelinstanzen (§9.9) – für die Übermenge gäbe es also gar keine
    Stücke, sie käme an und existierte im System nicht.
    """
    from decimal import Decimal
    from app.schemas.process import PurchaseUpdate
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])], moq=Decimal(100))
        order, rows = _make(db, quantity=5, article=art)
        staff = _staff(db)
        row = svc.of_step(db, rows[0].id)

        assert _total(db, order, row) == 5, (
            "Die Menge ist die Zahl der Einzelinstanzen, die vor dem Modul stehen."
        )
        assert "quantity" not in PurchaseUpdate.model_fields, (
            "Der Beleg nimmt wieder eine Menge entgegen – damit gibt es zwei Zahlen für "
            "dieselbe Sache."
        )

        # Auch wer sie trotzdem mitschickt, ändert nichts: Pydantic verwirft, was das
        # Schema nicht kennt – die Regel steht im Schema, nicht in einer Prüfung daneben.
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id], "quantity": 100}, actor=staff)
        assert _total(db, order, svc.of_step(db, rows[0].id)) == 5

        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 50, "quantity": 100},
                  actor=staff)
        after = svc.of_step(db, rows[0].id)
        assert _total(db, order, after) == 5, (
            "Beim Bestellen wird die Menge des PROZESSES eingefroren, nicht eine getippte."
        )
        assert [int(l["quantity"]) for l in after.ordered_lines] == [5]
    finally:
        db.rollback(); db.close()


def test_an_offer_without_a_lead_time_is_not_an_offer():
    """**Ohne Lieferfrist keine Offerte** – aus ihr kommt der Liefertermin.

    Bug-Form: ``lead_days`` ist optional. Dann steht ein Preis da, zu dem niemand sagen
    kann, wann die Ware kommt – und zwei Angebote sind nicht mehr vergleichbar.
    """
    import pytest as _pytest
    from fastapi import HTTPException
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        art = _article(db, "Schraube", steps=[_buy_step([wuerth])])
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)

        with _pytest.raises(HTTPException) as caught:
            svc.apply(db, order=order, step=rows[0], action="quote",
                      payload={"supplier": wuerth.object_id, "amount": 20}, actor=staff)
        assert caught.value.status_code == 400
        assert "Lieferfrist" in caught.value.detail

        with _pytest.raises(HTTPException):
            svc.apply(db, order=order, step=rows[0], action="quote",
                      payload={"supplier": wuerth.object_id, "lead_days": 5}, actor=staff)

        svc.apply(db, order=order, step=rows[0], action="quote",
                  payload={"supplier": wuerth.object_id, "amount": 20, "lead_days": 5},
                  actor=staff)
        quote = svc.of_step(db, rows[0].id).quotes[0]
        assert quote["state"] == "offeriert" and quote["lead_days"] == 5
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §7 – was beschafft wird, sagt der Prozess
# ---------------------------------------------------------------------------

def test_what_is_bought_comes_from_the_process():
    """**Kein Artikelfeld – der Beleg liest, was vor dem Modul steht.**

    Und daraus fällt der Mehrartikel-Fall von selbst heraus: stehen Stücke zweier Artikel
    davor, hat der Beleg **zwei Zeilen** – EINE Bestellung mit zwei Positionen, wie im
    echten Leben. Es braucht dafür keine Regel, nur eine Gruppierung.

    Bug-Formen: (a) der Beleg nennt einen von Hand gewählten Artikel; (b) bei zwei
    Artikeln nennt er nur einen – dann bestellt man die Hälfte, ohne es zu merken.
    """
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        screw = _article(db, "Schraube M6", steps=[_buy_step([wuerth])])
        nut = _article(db, "Mutter M6")
        order, rows = _make(db, quantity=4, article=screw)

        facts = svc.embed_data(db, order=order, step=rows[0])
        assert [(l["article_object_id"], l["quantity"]) for l in facts["lines"]] == [
            (screw.object_id, 4.0)
        ], "Die Zeile des Belegs stimmt nicht mit dem überein, was davorsteht."

        # Ein zweiter Artikel tritt am Modul ein – dieselbe Bestellung, eine Zeile mehr.
        from app.models import Instance, InstanceUnit, OrderUnit
        from app.domain import statuses as st
        from app.services import objects as obj
        inst = Instance(object_id=obj.next_object_id(db), article_id=nut.id, kind="batch")
        db.add(inst)
        db.flush()
        for suffix in (1, 2):
            unit = InstanceUnit(instance_id=inst.id, suffix=suffix, status=st.IM_PROZESS)
            db.add(unit)
            db.flush()
            db.add(OrderUnit(order_id=order.id, instance_unit_id=unit.id,
                             current_step_id=rows[0].id))
        db.flush()

        two = svc.embed_data(db, order=order, step=rows[0])
        got = {l["article_object_id"]: l["quantity"] for l in two["lines"]}
        assert got == {screw.object_id: 4.0, nut.object_id: 2.0}, (
            f"Zwei Artikel vor dem Modul sind ZWEI Zeilen auf EINEM Beleg – gesehen: {got}"
        )
    finally:
        db.rollback(); db.close()


def test_the_specification_travels_with_the_document():
    """**Der Lieferant sieht die Sache – ohne dass jemand Felder auswählt.**

    Die Spezifikation beschreibt das Teil und gilt für jeden Lieferanten; eine
    Konfiguration «welche Felder sieht er?» wäre eine vierte Stelle für dieselbe Frage
    und müsste bei zwei zugelassenen Lieferanten zweimal beantwortet werden.

    **Die Lieferanten-Artikelnummer reist NICHT mit**: sie gehört genau einem Lieferanten,
    und sie allen zu zeigen wäre genau der Fehler, den die dritte Schicht vermeidet.

    Bug-Formen: (a) der Beleg trägt keine Spezifikation – dann weiss der Lieferant nicht,
    was das Teil ist; (b) er trägt eine fremde Bestellnummer mit.
    """
    from decimal import Decimal
    from app.services import article_fields, purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        art = _article(db, "Welle", steps=[_buy_step([wuerth], "Härten auf 58 HRC")])
        art.size = "12x12x300"
        art.weight_kg = Decimal("2.500")
        art.material = "1.4301"
        art.supplier_article_number = "W-4711"
        db.flush()

        order, rows = _make(db, quantity=1, article=art)
        spec = svc.embed_data(db, order=order, step=rows[0])["lines"][0]["spec"]
        seen = {f["label"]: f["value"] for f in spec}
        assert seen.get("Grösse") == "12x12x300 mm", seen
        assert seen.get("Gewicht") == "2.5 kg", seen
        assert seen.get("Werkstoff") == "1.4301", seen
        assert "W-4711" not in str(seen), (
            "Die Lieferanten-Artikelnummer reist mit – sie gehört EINEM Lieferanten."
        )
        # Leere Felder fallen weg: eine Zeile «Oberfläche: —» sagt weniger als keine.
        assert "Oberfläche" not in seen, seen

        # Und es gibt keine Auswahl mehr, welche Felder gezeigt werden.
        assert not hasattr(article_fields, "normalize_shared_fields"), (
            "Die Feld-Auswahl ist zurück – eine Spezifikation, die je nach Empfänger "
            "anders lautet, ist keine."
        )
    finally:
        db.rollback(); db.close()


def test_the_landed_cost_needs_exactly_one_line():
    """**Summe ÷ Menge nur, wenn es EINE Zeile gibt.**

    Bug-Form: die Bestellsumme wird durch die Gesamtmenge geteilt und beiden Artikeln als
    Einstandspreis geschrieben. Dann steht an zwei Artikeln dieselbe Zahl, und für beide
    ist sie falsch – mit ihr wird danach kalkuliert.
    """
    from app.services import purchase as svc
    db = _db()
    try:
        wuerth = _supplier(db, "Würth AG")
        screw = _article(db, "Schraube M6", steps=[_buy_step([wuerth])])
        nut = _article(db, "Mutter M6")
        order, rows = _make(db, quantity=4, article=screw)
        staff = _staff(db)

        # Erst der einfache Fall: eine Zeile, 4 Stück, 84.– → 21.– je Stück.
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 84}, actor=staff)
        _confirm_all(db, order, rows[0])
        assert screw.landed_unit_cost is not None
        assert float(screw.landed_unit_cost) == 21.0, screw.landed_unit_cost

        # Und der gemischte: zwei Zeilen, nichts wird geschrieben.
        second = _article(db, "Welle", steps=[_buy_step([wuerth])])
        order2, rows2 = _make(db, quantity=2, article=second)
        from app.models import Instance, InstanceUnit, OrderUnit
        from app.domain import statuses as st
        from app.services import objects as obj
        inst = Instance(object_id=obj.next_object_id(db), article_id=nut.id, kind="batch")
        db.add(inst)
        db.flush()
        unit = InstanceUnit(instance_id=inst.id, suffix=1, status=st.IM_PROZESS)
        db.add(unit)
        db.flush()
        db.add(OrderUnit(order_id=order2.id, instance_unit_id=unit.id,
                         current_step_id=rows2[0].id))
        db.flush()

        svc.apply(db, order=order2, step=rows2[0], action="ask",
                  payload={"suppliers": [wuerth.object_id]}, actor=staff)
        svc.apply(db, order=order2, step=rows2[0], action="order",
                  payload={"supplier": wuerth.object_id, "amount": 300}, actor=staff)
        _confirm_all(db, order2, rows2[0])
        assert second.landed_unit_cost is None and nut.landed_unit_cost is None, (
            "Bei zwei Zeilen wurde ein Einstandspreis erfunden – die Bestellsumme ist "
            "eine gemeinsame, ihre Aufteilung muss ein Mensch vornehmen."
        )
    finally:
        db.rollback(); db.close()


def test_the_instruction_is_mandatory_and_reaches_the_supplier():
    """**Ohne den Satz ist das Modul nicht anlegbar** – und er steht auf dem Beleg.

    Die Spezifikation beschreibt die Sache, nicht was mit ihr geschehen soll. Ein Beleg
    ohne Auftrag ist eine Bestellung, aus der niemand liest, was verlangt ist.

    Bug-Form: ``instruction`` ist optional oder wird beim Aufbau der Antwort vergessen.
    """
    from fastapi import HTTPException
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    m = modules.get("beschaffen")
    with pytest.raises(HTTPException) as caught:
        m.clean_config({"suppliers": [1]})
    assert caught.value.status_code == 400
    with pytest.raises(HTTPException):
        m.clean_config({"suppliers": [1], "instruction": "   "})
    with pytest.raises(HTTPException):
        m.clean_config({"suppliers": [1], "instruction": "x" * (m.MAX_INSTRUCTION + 1)})

    clean = m.clean_config({"suppliers": [1], "instruction": "  Härten auf 58 HRC  "})
    assert clean["instruction"] == "Härten auf 58 HRC", "Der Satz wird nicht getrimmt."


def test_a_supplier_sees_the_specification_but_no_foreign_number():
    """Die Spiegelung nimmt weg, sie erfindet nichts – der Auftrag bleibt lesbar.

    Bug-Form: die Verengung auf «sein Modul» nimmt ihm auch die Sache und den Auftrag.
    Dann sieht er eine Bestellung, ohne zu wissen, was er tun soll.
    """
    from app.services import purchase as svc
    db = _db()
    try:
        a = _supplier(db, "Würth AG")
        b = _supplier(db, "Bossard AG")
        art = _article(db, "Welle", steps=[_buy_step([a, b], "Härten auf 58 HRC")])
        art.size = "12x12x300"
        db.flush()
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"suppliers": [a.object_id, b.object_id]}, actor=staff)

        mine = svc.embed_data(db, order=order, step=rows[0], viewer=b)
        assert mine["instruction"] == "Härten auf 58 HRC", (
            "Der Lieferant sieht nicht, was er tun soll."
        )
        assert [l["article_object_id"] for l in mine["lines"]] == [art.object_id]
        assert any(f["label"] == "Grösse" for f in mine["lines"][0]["spec"]), (
            "Der Lieferant sieht die Sache nicht – die Spezifikation reist mit dem Beleg."
        )
    finally:
        db.rollback(); db.close()
