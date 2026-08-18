"""**Das Ressourcenmodul und der Ort** — die Regeln R1–R6 aus `SYSTEM_LOGIC` §7.3b.

Das Modul fragt «ist genug da?». Mit dem Ort kommt eine **zweite** Frage dazu — «liegt
es hier?» —, und der schwierige Teil ist, dass sie die erste nicht überschreiben darf:
ein Ort **blockiert nie**, er sagt nur, ob daraus ein Transport folgt.

Über die echten Dienstpfade gegen echtes PostgreSQL; wo es um eine Aussage über Code
geht (»kein automatisch angelegter Transport«, »keine Abzweig-Kante«), steht ein
AST-Wächter. Jeder Wächter nennt seine **Bug-Form**.
"""

import ast

from .support import BACKEND, live_sources, make_company, make_units, session, source

CAPTURE_WORK = (BACKEND.parent / "frontend" / "src" / "components" / "erp"
                / "capture-work.tsx")

ZUERICH = dict(street="Industriestrasse", street_nr="4", zip_code="8000", city="Zürich",
               country="CH")
BERN = dict(street="Bahnhofplatz", street_nr="1", zip_code="3000", city="Bern",
            country="CH")


def _consumer(db, *, article_object_id: int, per_unit: int = 2):
    """Ein laufender Auftrag mit einem **Verbrauch**-Modul auf diesen Artikel.

    Über den echten Weg: die Vorlage des Artikels trägt das Modul, der Auftrag kopiert
    sie bei der Freigabe.
    """
    from app.models import Article, InstanceUnit, OrderUnit
    from app.services import article_process as tpl, objects as obj, process as proc

    art = Article(object_id=obj.next_object_id(db), name="Erzeugnis", unit="stk",
                  serialization="unit")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, [{
        "module_type": "verbrauch",
        "config": {"lines": [{"article": article_object_id, "quantity": per_unit}]},
    }])
    db.flush()
    order = proc.release(
        db, lines=[{"article_object_id": art.object_id, "quantity": 1,
                    "origin": "neu", "units": []}],
        steps=[], actor_id=None)
    db.flush()
    units = (db.query(InstanceUnit)
             .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
             .filter(OrderUnit.order_id == order.id).all())
    return order, units


def _module(db, order):
    """Das Verbrauchs-Modul dieses Auftrags."""
    from app.services import process as proc
    return next(s for s in proc.steps_of(db, order) if s.module_type == "verbrauch")


def _needs_of(db, order, step):
    """Die Zeilen, so wie die Oberfläche sie bekommt – über den echten Router-Pfad."""
    from app.routers.orders import _needs
    return _needs(db, order, step, pieces=1)


def _stock(db, quantity: int = 5):
    """**Freier** Bestand eines Artikels – ein *abgeschlossener* Erzeugungsauftrag.

    Der Auftrag wird über den echten Weg durchgefahren (Erfassung je Instanz), damit die
    Stücke ihn wirklich verlassen. Sie von Hand auf «freigegeben» zu setzen wäre ein
    Zustand, den kein Dienstpfad je erzeugt – und dann prüfte der Test eine Welt, die es
    nicht gibt.
    """
    from app.models import Article, Instance
    from app.services import process as proc
    from .support import per_unit

    order, instances, units = make_units(db, quantity=quantity)
    step = proc.steps_of(db, order)[0]
    for inst in instances:
        proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step,
                            instance_object_id=inst.object_id),
            instance_object_id=inst.object_id, verification="scan", actor_id=None)
    db.flush()
    art = db.query(Article).filter(
        Article.id == db.query(Instance).filter(Instance.id == instances[0].id)
        .first().article_id).first()
    return art.object_id, instances, units


# ═══════════════════════════════════════════════════════════════════════════════
# R1/R2/R3 — Der Ort steht neben der Verfügbarkeit
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_place_never_reduces_availability():
    """**«200 verfügbar — in Werk 2» ist eine Auskunft, kein Abzug** (R1).

    Bug-Form: die Verfügbarkeit zählt nur, was hier liegt. Dann verschwände Material aus
    der Zahl, das es sehr wohl gibt – und ein Ort **blockiert nie** (§7.2-O4). Statt die
    Zahl zu senken, sagt die Zeile, dass ein Transport nötig wäre.
    """
    from app.services import places

    db = session()
    try:
        nord = make_company(db, "Werk Nord", **ZUERICH).object_id
        sued = make_company(db, "Werk Süd", **BERN).object_id
        art, _inst, units = _stock(db, quantity=5)
        places.record(db, [u.id for u in units], sued, actor_id=None)   # Material im Süden

        order, products = _consumer(db, article_object_id=art, per_unit=2)
        places.record(db, [u.id for u in products], nord, actor_id=None)  # Arbeit im Norden
        step = _module(db, order)

        rows = _needs_of(db, order, step)
        assert len(rows) == 1
        need = rows[0]
        assert need.available == 5, (
            "Der Ort hat die Verfügbarkeit gesenkt – er ist eine Auskunft, kein Abzug.")
        assert need.needed_at and need.needed_at.object_id == nord
        assert all(src.here is False for src in need.sources), (
            "Material im Süden gilt als «hier» – verglichen wird die Anschrift.")
        assert all(src.holder and src.holder.object_id == sued for src in need.sources)
    finally:
        db.rollback()
        db.close()


def test_the_address_decides_not_the_holder():
    """**Ein Regalwechsel ist kein Transport** (R2).

    Bug-Form: verglichen wird der **Halter**. Dann verlangte jedes Umräumen innerhalb
    desselben Werks einen Transport – und die Zeile stünde dauernd auf Rot.

    Der unterscheidende Fall ist **anderer Halter, gleiche Anschrift**: das Material
    liegt in einer Kiste, und die Kiste steht im Werk. Ihre Anschrift hat sie über die
    **Kette** (§15.3) – ein Halter-Vergleich könnte das nie sehen, und genau daran wäre
    er zu erkennen.

    Die Gegenprobe steht daneben: hat die Kiste selbst keinen Ort, ist die Frage nicht
    beantwortbar – und «nicht beantwortbar» ist etwas anderes als «woanders».
    """
    from app.services import places

    db = session()
    try:
        werk = make_company(db, "Werk Nord", **ZUERICH).object_id

        # ── Anderer Halter, gleiche Anschrift ────────────────────────────────────
        art, _instances, units = _stock(db, quantity=4)
        _o, kisten, kisten_units = make_units(db, quantity=1)
        kiste = kisten[0].object_id
        # Die Kiste steht im Werk – ihr Ort ist der ihrer eigenen Stücke.
        places.record(db, [u.id for u in kisten_units], werk, actor_id=None)
        places.record(db, [u.id for u in units], kiste, actor_id=None)

        order, products = _consumer(db, article_object_id=art, per_unit=1)
        places.record(db, [u.id for u in products], werk, actor_id=None)
        step = _module(db, order)

        need = _needs_of(db, order, step)[0]
        assert need.sources, "Ohne Quellen prüft dieser Wächter nichts."
        assert all(src.holder and src.holder.object_id == kiste for src in need.sources)
        assert all(src.here is True for src in need.sources), (
            "Material in einer Kiste im selben Werk gilt als «woanders» – verglichen "
            "wird der Halter statt der Anschrift.")
        assert need.transports == [], (
            "Für einen Regalwechsel wird ein Transport angeboten.")

        # ── Ohne auflösbare Anschrift wird NICHTS behauptet ──────────────────────
        art2, _i2, units2 = _stock(db, quantity=2)
        _o2, freie, _fu = make_units(db, quantity=1)
        nirgends = freie[0].object_id            # eine Kiste, die selbst nirgends steht
        places.record(db, [u.id for u in units2], nirgends, actor_id=None)
        order2, products2 = _consumer(db, article_object_id=art2, per_unit=1)
        places.record(db, [u.id for u in products2], werk, actor_id=None)
        step2 = _module(db, order2)

        assert all(src.here is None for src in _needs_of(db, order2, step2)[0].sources), (
            "Ohne auflösbare Anschrift wird eine Lage behauptet, statt sie offen zu lassen.")
    finally:
        db.rollback()
        db.close()


def test_without_an_observation_nothing_is_claimed():
    """**Ein Stück ohne Ort ist nicht «woanders»** (R3).

    Bug-Form: ``None`` wird als «nicht hier» gelesen. Dann böte das Modul einen Transport
    für Material an, von dem niemand weiss, wo es liegt – und der Transport ginge ins
    Leere.
    """
    db = session()
    try:
        art, _inst, _units = _stock(db, quantity=3)          # keine Ablage
        order, _products = _consumer(db, article_object_id=art, per_unit=1)
        step = _module(db, order)

        need = _needs_of(db, order, step)[0]
        assert need.needed_at is None, "Ohne Beobachtung gibt es keinen «gebraucht in»-Ort."
        assert all(src.here is None and src.holder is None for src in need.sources)
        assert need.transports == []
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# R4/R5 — Der Transport ist ein Klick und keine Kante
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_system_never_creates_a_transport():
    """**Das System legt nichts an – es bietet an** (R4, §15.7).

    Bug-Form: das Modul legt beim Erreichen einen Transport-Auftrag an. Genau daran sind
    die Begleit-Bewegungen und die abgeleitete Bereitstellung gescheitert: ein Transport,
    den das System selbst anlegt, gehört niemandem.

    Zwei Formen derselben Aussage: der Quelltext legt nichts an, und ein Lauf über den
    echten Lesepfad hinterlässt **keinen** neuen Auftrag.
    """
    from app.models import Order
    from app.services import places

    tree = ast.parse(source("routers/orders.py"))
    creators = {
        fn.name
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("release", "create_order")
                for n in ast.walk(fn))
    }
    assert "_needs" not in creators and "_transports" not in creators, (
        "Die Zeile legt einen Auftrag an – sie liest nur.")

    db = session()
    try:
        nord = make_company(db, "Werk Nord", **ZUERICH).object_id
        sued = make_company(db, "Werk Süd", **BERN).object_id
        art, _inst, units = _stock(db, quantity=5)
        places.record(db, [u.id for u in units], sued, actor_id=None)
        order, products = _consumer(db, article_object_id=art, per_unit=2)
        places.record(db, [u.id for u in products], nord, actor_id=None)
        step = _module(db, order)

        before = db.query(Order).count()
        _needs_of(db, order, step)
        assert db.query(Order).count() == before, (
            "Das Lesen der Zeile hat einen Auftrag angelegt.")
    finally:
        db.rollback()
        db.close()


def test_a_transport_is_a_reference_not_a_branch():
    """**Zwei klickbare Verweise, keine Kante** (R5, §15.8).

    Bug-Form: der Transport wird als Abzweig gezeichnet. Er bewegt Stücke, die **nie auf
    dieser Achse waren** – jeder ``fork`` zieht ab und jeder ``join`` addiert, also
    rechnete die Bilanz falsch.

    Und er ist **abgeleitet, nicht gespeichert**: ein Zeiger am Auftrag wäre eine fünfte
    Spalte auf einer Tabelle, die bewusst vier hat – und er könnte veralten.
    """
    from app.models import Order
    from app.services import flow, places, process as proc

    assert not hasattr(Order, "origin_step_id"), (
        "Der Auftrag trägt wieder einen Anlass-Zeiger – abgeleitet kann er nicht veralten.")

    db = session()
    try:
        nord = make_company(db, "Werk Nord", **ZUERICH).object_id
        sued = make_company(db, "Werk Süd", **BERN).object_id
        art, instances, units = _stock(db, quantity=5)
        places.record(db, [u.id for u in units], sued, actor_id=None)

        order, products = _consumer(db, article_object_id=art, per_unit=2)
        places.record(db, [u.id for u in products], nord, actor_id=None)
        step = _module(db, order)
        assert _needs_of(db, order, step)[0].transports == []

        # Ein **ganz gewöhnlicher** Auftrag, der das Material nach Norden bringt.
        from app.models import Instance as Inst
        from app.services.instances import unit_number
        by_id = {i.id: i for i in db.query(Inst).filter(
            Inst.id.in_({u.instance_id for u in units})).all()}
        picked = [unit_number(by_id[u.instance_id], u) for u in units[:2]]
        transport = proc.release(
            db,
            lines=[{"article_object_id": art, "quantity": 2, "origin": "lager",
                    "units": [{"number": n} for n in picked]}],
            steps=[{"module_type": "bewegen", "config": {"target": nord}}],
            actor_id=None)
        db.flush()

        rows = _needs_of(db, order, step)
        assert [t.object_id for t in rows[0].transports] == [transport.object_id], (
            "Der laufende Transport erscheint nicht als Verweis.")
        assert rows[0].transports[0].from_holder.object_id == sued

        # …und er ist **keine** Kante im Bild dieses Auftrags.
        graph = flow.build(db, order)
        assert transport.object_id not in {n.order_object_id for n in graph.neighbours}, (
            "Der Transport ist ein Abzweig geworden – dann rechnet die Bilanz falsch.")
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# R6 — Angeboten wird nur, was Sinn ergibt
# ═══════════════════════════════════════════════════════════════════════════════

def test_only_the_option_that_makes_sense_is_offered():
    """**Reicht es hier → nichts · woanders → Transport · nichts → Nachschub** (R6).

    Bug-Form: alle drei stehen immer da. Dann muss der Mensch jedes Mal herausfinden,
    welche gerade gemeint ist – und die Zeile sagt nichts mehr aus.

    Die Fallunterscheidung steht in der **Oberfläche** (sie zeigt Knöpfe), aber sie
    rechnet nicht: was hier liegt und was nicht, sagt der Server je Quelle.
    """
    work = CAPTURE_WORK.read_text(encoding="utf-8")

    assert "s2.here === true" in work and "s2.here === false" in work, (
        "Die Oberfläche liest die Lage nicht je Quelle – dann rechnet sie sie selbst.")
    assert "needsTransport" in work and "hereFree < required" in work, (
        "Der Transport wird nicht an «hier reicht es nicht, woanders liegt etwas» geknüpft.")
    # Und die Verfügbarkeit bleibt die echte Zahl.
    assert "need.available" in work and "hereAvailable" not in work, (
        "Es gibt eine zweite Verfügbarkeits-Zahl «hier verfügbar» – dann stünden zwei "
        "Zahlen für dieselbe Frage.")


def test_the_place_question_is_asked_at_exactly_one_place():
    """**Verglichen wird über `places.same_place`** – die eine Funktion (R2/V-6).

    Bug-Form: eine zweite Adressregel im Ressourcen-Pfad. Zwei Ableitungen wären zwei
    Antworten auf dieselbe Sache – und die eine wird irgendwann nicht mitgepflegt.
    """
    askers = [rel for rel, src in live_sources()
              if "same_place(" in src and rel not in ("services/places.py",)]
    assert set(askers) <= {"routers/orders.py", "services/moving.py"}, (
        f"Die Adressregel wird an weiteren Stellen gefragt: {askers}")
    for rel in ("routers/orders.py", "services/moving.py"):
        assert "addr.same(" not in source(rel), (
            f"{rel} vergleicht Adressen selbst, statt ``places.same_place`` zu fragen.")
