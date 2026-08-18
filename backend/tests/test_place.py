"""**Der Ort** — die Regeln aus `SYSTEM_LOGIC` §7, als Wächter.

Der Ort ist der Bereich, in dem der Vorgänger dreimal an derselben Wand stand (ADR 009
§2). Die Fehler waren nie einzelne Zeilen, sondern **Formen**: eine Auswahlfunktion mit
Fallunterscheidungen, eine Mengen-Map neben einem Skalar, ein System, das selbst anlegt,
und eine gespeicherte Klassifikation. Darum prüft die Hälfte dieser Datei den
**Quelltext** — eine Aussage über Code ist mit einem Verhaltenstest nicht widerlegbar.

Die andere Hälfte läuft über die **echten** Dienstpfade gegen echtes PostgreSQL. Ein
nachgestellter Zustand würde genau das nicht finden, was hier zählt: dass eine Ablage
nichts anfasst ausser dem Ort.
"""

import ast
import os
import pathlib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


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


def _units(db, *, quantity: int = 2, serialization: str = "unit"):
    """Echte Einzelinstanzen über den echten Weg: ein freigegebener Erzeugungsauftrag.

    Sie von Hand einzufügen wäre schneller und würde genau die Fehler verstecken, die
    zwischen den Schritten entstehen.
    """
    from app.models import Article, Instance, InstanceUnit, OrderUnit
    from app.services import article_process as tpl, objects as obj, process as proc

    art = Article(object_id=obj.next_object_id(db), name="Ortstück", unit="stk",
                  serialization=serialization)
    db.add(art)
    db.flush()
    # Ein Erzeugungsauftrag fährt die Vorlage des Artikels – ohne sie gibt es keinen
    # Prozess und damit keine Freigabe (§6.2). Das Modul ist hier Beiwerk.
    tpl.create_steps(db, art, [{"module_type": "datenerfassung",
                                "config": {"points": [{"label": "OK", "type": "bool"}]}}])
    db.flush()
    order = proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=[], actor_id=None,
    )
    db.flush()
    # Die Stücke des Auftrags über die Zugehörigkeit – Instance kennt den Auftrag nicht.
    units = (db.query(InstanceUnit)
             .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
             .filter(OrderUnit.order_id == order.id)
             .order_by(InstanceUnit.id).all())
    instances = db.query(Instance).filter(
        Instance.id.in_({u.instance_id for u in units})).all()
    return order, instances, units


def _source(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    """Nur der **ausgeführte** Quelltext – ohne Kommentare und ohne Zeichenketten.

    Die verbotenen Formen sind Aussagen über **Code**. Ein roher Textvergleich verböte
    dem Projekt, seine eigene Historie zu dokumentieren: ADR 009 nennt
    ``location_split`` und ``movable_instances`` beim Namen, und mehrere Docstrings
    verweisen zu Recht darauf, was es einmal gab. Ein Wächter, der daran anschlägt,
    erzieht zum Verschweigen – und das ist die teurere Sorte Fehler.
    """
    import io
    import tokenize

    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover - defekte Datei wäre ein anderer Test
        return src
    return " ".join(out)


def _live_sources() -> list[tuple[str, str]]:
    """Der **aktive** Quelltext. Abgeschaltete Module (`core/features.py`) bleiben als
    Historie liegen und dürfen die Aussage nicht verfälschen."""
    from app.core import features  # noqa: F401  (nur zur Existenzprüfung)
    disabled = ("services/ai/", "services/payments/", "services/shipping/",
                "services/sale.py", "services/selling.py", "services/refund.py",
                "services/customer_returns.py", "services/pricing.py", "services/tax.py",
                "services/fx.py", "services/operating_costs.py", "services/document",
                "services/consent.py", "services/legal.py",
                "routers/sales.py", "routers/shop.py", "routers/document",
                "routers/ai.py", "routers/consent.py", "routers/legal.py",
                "schemas/sale", "schemas/shop.py", "schemas/document",
                "schemas/consent.py", "schemas/ai.py")
    out = []
    for p in APP.rglob("*.py"):
        rel = p.relative_to(APP).as_posix()
        if any(rel.startswith(d) for d in disabled):
            continue
        out.append((rel, p.read_text(encoding="utf-8")))
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# O1 — Der Ort ist eine Beobachtung, kein Zustand
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_place_is_an_observation_not_a_state():
    """**Der aktuelle Ort ist die letzte Zeile — nichts wird überschrieben.**

    Bug-Form: ein Feld an der Einzelinstanz (oder ein `UPDATE` hier) würde die zweite
    Ablage die erste vergessen lassen. Dann wäre «wo war es» unbeantwortbar, und genau
    daran ist der Vorgänger gescheitert (ADR 009 §2.2).
    """
    from app.models import UnitPlace
    from app.services import objects as obj, places

    db = _db()
    try:
        _, instances, units = _units(db, quantity=1)
        u = units[0]
        a, b = obj.next_object_id(db), obj.next_object_id(db)
        from app.models import Instance
        for oid in (a, b):
            db.add(Instance(object_id=oid, article_id=instances[0].article_id,
                            kind="einzeln", label=f"Behälter {oid}"))
        db.flush()

        places.record(db, [u.id], a, actor_id=None)
        places.record(db, [u.id], b, actor_id=None)
        db.flush()

        assert places.current_of(db, u.id) == b, "Der aktuelle Ort ist die letzte Zeile."
        rows = db.query(UnitPlace).filter(UnitPlace.instance_unit_id == u.id).all()
        assert len(rows) == 2, (
            "Beide Beobachtungen müssen stehen bleiben – append-only heisst, dass die "
            "erste Ablage die zweite überlebt."
        )
    finally:
        db.rollback()
        db.close()


def test_a_placement_needs_no_order():
    """**Eine Ablage verlangt keinen Auftrag** — das ist der Kern (§15.1).

    Freier Bestand ist der Normalzustand eines Lagers; ein Endpunkt, der einen Auftrag
    verlangte, hätte die Lücke nicht geschlossen, sondern verschoben.

    Bug-Form: ein Pflichtparameter `order` an `record()` oder ein Feld `order_id` an der
    Tabelle. Beides wird hier direkt widerlegt.
    """
    import inspect
    from app.models import UnitPlace
    from app.schemas.place import PlaceCreate
    from app.services import places

    params = set(inspect.signature(places.record).parameters)
    assert not (params & {"order", "order_id", "step", "step_id"}), (
        f"record() darf keinen Auftrag verlangen, hat aber {params}."
    )
    cols = {c.name for c in UnitPlace.__table__.columns}
    assert not (cols & {"order_id", "step_id"}), (
        f"unit_places darf nicht am Auftrag hängen, hat aber {cols}."
    )
    assert not (set(PlaceCreate.model_fields) & {"order_id", "order_object_id", "step_id"})


def test_the_place_table_has_no_update_path():
    """**Append-only ist eine Aussage über den Code**, nicht über einen Testlauf.

    Bug-Form: ein `UPDATE`/`DELETE` auf `unit_places`, das einen einzelnen Wert
    korrigiert, statt eine neue Zeile zu schreiben. Ein Verhaltenstest fände es erst,
    wenn jemand genau diesen Pfad ruft — der Quelltext sagt es sofort.
    """
    for rel, src in _live_sources():
        if "UnitPlace" not in src:
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = ast.unparse(node.func)
            if fn.endswith(".delete") or fn.endswith(".update"):
                assert "UnitPlace" not in ast.unparse(node), (
                    f"{rel}: {ast.unparse(node)[:90]} – eine Beobachtung wird nie "
                    f"geändert oder gelöscht; eine Korrektur ist eine NEUE Zeile."
                )


# ═══════════════════════════════════════════════════════════════════════════════
# O2 — Ein Halter ist eine Objektnummer
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_holder_is_an_object_number_without_a_type_field():
    """**Kein `location_type` neben der `id`** (§15.2, verbotene Form V-5).

    Bug-Form: eine zweite Spalte, die den Typ nennt. Daraus folgt zwingend eine
    Whitelist, eine Validierung und eine «unbekannter Typ»-Fallunterscheidung — im
    Vorgänger musste ein entfallener Wert tolerant aufgelöst werden, damit er nicht jede
    Ansicht zerlegte.
    """
    from app.models import UnitPlace

    cols = {c.name for c in UnitPlace.__table__.columns}
    assert "holder_object_id" in cols
    assert not [c for c in cols if "type" in c or c.endswith("_kind")], (
        f"unit_places trägt ein Typfeld neben der Objektnummer: {cols}"
    )
    for rel, src in _live_sources():
        assert "location_type" not in _code_only(src), (
            f"{rel}: `location_type` ist die verbotene Form V-5 (ADR 009 §3.2)."
        )


def test_every_kind_of_record_can_be_a_holder():
    """**Keine Whitelist** (O2.2): Instanz, Unternehmen und **Mensch** sind Halter.

    Der Mensch ist der Fall, der die Regel trägt: nimmt ein Kollege ein Teil mit, liegt
    es **bei ihm**. Der alte Ort wäre eine Behauptung über etwas, das dort nachweislich
    nicht liegt (G3).
    """
    from app.models import CompanySettings, Instance, UserProfile
    from app.services import objects as obj, places

    db = _db()
    try:
        _, instances, units = _units(db, quantity=3)
        u = units[0]

        container = Instance(object_id=obj.next_object_id(db),
                             article_id=instances[0].article_id, kind="einzeln",
                             label="Behälter A")
        company = CompanySettings(object_id=obj.next_object_id(db), company_name="Werk Nord")
        person = UserProfile(object_id=obj.next_object_id(db), firebase_uid=f"t{obj.obj_nr(1)}",
                             email="lager@example.com", first_name="Max", last_name="Müller")
        db.add_all([container, company, person])
        db.flush()

        for holder in (container.object_id, company.object_id, person.object_id):
            places.record(db, [u.id], holder, actor_id=None)
            db.flush()
            assert places.current_of(db, u.id) == holder, (
                f"Halter {holder} wurde nicht übernommen – ein Halter ist eine "
                f"Objektnummer, und jeder Datensatz mit einer darf es sein."
            )
        assert places.resolve_holder(db, person.object_id).type == "user"
        assert places.resolve_holder(db, company.object_id).type == "organization"
        assert places.resolve_holder(db, container.object_id).type == "instance"
    finally:
        db.rollback()
        db.close()


def test_an_unresolvable_holder_is_reported_not_swallowed():
    """**Tolerant lesen, streng schreiben** (O2.4 / G3.3).

    Bug-Form: eine Nummer, die ins Leere zeigt, still zu «kein Ort» aufzulösen. Dann
    sähe ein kaputter Verweis aus wie ein Stück, das nirgends liegt — und das ist der
    Fehler, den man sehen müsste.
    """
    from fastapi import HTTPException
    from app.services import places

    db = _db()
    try:
        _, _, units = _units(db, quantity=1)
        ghost = 999_999_999

        holder = places.resolve_holder(db, ghost)
        assert holder.object_id == ghost and holder.type is None and not holder.known, (
            "Ein unauflösbarer Halter wird als solcher zurückgegeben, nicht verschwiegen."
        )
        with pytest.raises(HTTPException) as e:
            places.record(db, [units[0].id], ghost, actor_id=None)
        assert e.value.status_code == 400, "Geschrieben wird nur auf einen Halter, den es gibt."
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# O3 — Der Ort ändert nie Status oder Zugehörigkeit
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_place_never_changes_status_or_belonging():
    """**Die Robustheitsgarantie** (§15.6): eine Ablage fasst nichts an ausser dem Ort.

    Sie ist konstruktiv, nicht bloss geprüft — weil nichts anderes berührt wird, muss
    keine andere Regel im System von ihr wissen. Darum darf ein Stück in **jedem**
    Zustand abgelegt werden.

    Bug-Form: `record()` setzt nebenbei den Status (z. B. «am Lager»), schliesst eine
    Zugehörigkeit oder schreibt in den Ereignis-Log. Alle drei werden hier gezählt.
    """
    from app.models import Instance, OrderUnit, ProcessEvent, UnitPlace
    from app.services import objects as obj, places

    db = _db()
    try:
        _, instances, units = _units(db, quantity=2)
        u = units[0]
        before_status = u.status
        before_units = db.query(OrderUnit).count()
        before_events = db.query(ProcessEvent).count()
        before_open = db.query(OrderUnit).filter(OrderUnit.released_at.is_(None)).count()

        holder = Instance(object_id=obj.next_object_id(db),
                          article_id=instances[0].article_id, kind="einzeln", label="Regal")
        db.add(holder)
        db.flush()
        places.record(db, [u.id], holder.object_id, actor_id=None)
        db.flush()
        db.refresh(u)

        assert u.status == before_status, "Eine Ablage ändert keinen Status."
        assert db.query(OrderUnit).count() == before_units, "Sie legt keine Zugehörigkeit an."
        assert db.query(OrderUnit).filter(OrderUnit.released_at.is_(None)).count() == before_open, \
            "Sie schliesst keine Zugehörigkeit."
        assert db.query(ProcessEvent).count() == before_events, (
            "Sie schreibt nicht in den Ereignis-Log – sonst wäre eine Ablage ohne "
            "Auftrag gar nicht möglich (§15.1)."
        )
        assert db.query(UnitPlace).filter(UnitPlace.instance_unit_id == u.id).count() == 1
    finally:
        db.rollback()
        db.close()


def test_the_place_service_touches_only_its_own_table():
    """Dieselbe Aussage über den **Quelltext** — damit sie auch für Pfade gilt, die
    dieser Test nicht fährt.

    Bug-Form: irgendwo in `services/places.py` ein Schreibzugriff auf `InstanceUnit`,
    `OrderUnit` oder `ProcessEvent`.
    """
    src = _source("services/places.py")
    tree = ast.parse(src)
    written = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith((".add", ".add_all")):
            written.add(ast.unparse(node).split("(", 1)[-1][:60])
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                    written.add(ast.unparse(t))
    forbidden = [w for w in written
                 if any(k in w for k in ("InstanceUnit(", "OrderUnit(", "ProcessEvent(",
                                         "unit.status", "u.status"))]
    assert not forbidden, (
        f"services/places.py schreibt ausserhalb seines Bereichs: {forbidden}. "
        f"Der Ort ändert nie einen Status und nie eine Zugehörigkeit (O3)."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# O5 — Der Kontext-Scan hat keinen Vorgabewert
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_context_scan_has_no_default():
    """**Der erste Scan ist der Ausgangsort — ohne Vorgabewert** (O5).

    Bug-Form: ein Standardwert oder ein gemerkter Ort («der letzte gilt weiter»). Das
    ist die klassische stille Fehlerklasse: wer den Wechsel vergisst, schreibt den
    falschen Ort, und nichts schlägt fehl.
    """
    from app.schemas.place import PlaceCreate

    field = PlaceCreate.model_fields["holder_object_id"]
    assert field.is_required(), (
        "holder_object_id muss Pflicht sein – ein Vorgabewert wäre ein Ort, den "
        "niemand gescannt hat."
    )
    src = _source("services/places.py") + _source("routers/places.py")
    for smell in ("last_place", "remembered", "session_place", "default_holder"):
        assert smell not in src, f"Ein gemerkter Ort ({smell}) widerspricht O5."


# ═══════════════════════════════════════════════════════════════════════════════
# Die Kette und die Gegenrichtung (§15.9)
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_chain_is_cycle_safe_and_reports_it():
    """**Ein Zyklus wird gemeldet, nicht endlos verfolgt** (P4/G3.3).

    Bug-Form: eine `while`-Schleife ohne `seen`-Menge. Sie hängt genau dann, wenn ein
    Mensch zwei Behälter ineinander gescannt hat — also im Betrieb, nicht im Test.
    """
    from app.models import Instance, InstanceUnit
    from app.services import objects as obj, places

    db = _db()
    try:
        _, instances, _ = _units(db, quantity=1)
        art = instances[0].article_id
        a = Instance(object_id=obj.next_object_id(db), article_id=art, kind="einzeln", label="A")
        b = Instance(object_id=obj.next_object_id(db), article_id=art, kind="einzeln", label="B")
        db.add_all([a, b])
        db.flush()
        ua = InstanceUnit(instance_id=a.id, suffix=1)
        ub = InstanceUnit(instance_id=b.id, suffix=1)
        db.add_all([ua, ub])
        db.flush()

        places.record(db, [ua.id], b.object_id, actor_id=None)   # A liegt in B
        places.record(db, [ub.id], a.object_id, actor_id=None)   # B liegt in A
        db.flush()

        chain = places.chain(db, a.object_id)
        assert chain.cycle, "Ein Zyklus muss gemeldet werden."
        assert len(chain.hops) <= places.MAX_HOPS
    finally:
        db.rollback()
        db.close()


def test_the_chain_ends_in_an_address_without_an_object_number():
    """**Behälter → Werk → Anschrift.** Die Anschrift ist kein Datensatz, trägt also
    keine Objektnummer und ist nicht anklickbar (§15.9).

    Bug-Form: der Anschrift eine Objektnummer geben — dann zeigte ein Klick ins Leere.
    """
    from app.models import CompanySettings, Instance, InstanceUnit
    from app.services import objects as obj, places

    db = _db()
    try:
        _, instances, units = _units(db, quantity=1)
        art = instances[0].article_id
        werk = CompanySettings(object_id=obj.next_object_id(db), company_name="Werk Nord",
                               street="Industriestrasse", street_nr="4",
                               zip_code="8000", city="Zürich", country="Schweiz")
        box = Instance(object_id=obj.next_object_id(db), article_id=art,
                       kind="einzeln", label="Behälter A")
        db.add_all([werk, box])
        db.flush()
        box_unit = InstanceUnit(instance_id=box.id, suffix=1)
        db.add(box_unit)
        db.flush()

        places.record(db, [box_unit.id], werk.object_id, actor_id=None)  # Behälter im Werk
        places.record(db, [units[0].id], box.object_id, actor_id=None)   # Stück im Behälter
        db.flush()

        chain = places.chain(db, box.object_id)
        kinds = [h.type for h in chain.hops]
        assert kinds[:2] == ["instance", "organization"], f"Kette falsch: {kinds}"
        assert kinds[-1] == "address", f"Die Kette endet in der Anschrift, nicht in {kinds[-1]}."
        assert chain.hops[-1].object_id is None, (
            "Die Anschrift ist kein Datensatz – eine Objektnummer daran wäre ein Klick "
            "ins Leere."
        )
        assert not chain.cycle and not chain.truncated
    finally:
        db.rollback()
        db.close()


def test_what_lies_here_is_the_other_reading_of_the_same_table():
    """**Zwei Fragen, eine Tabelle** (§15.9).

    Bug-Form: eine zweite Tabelle (oder ein Zähler) für die Gegenrichtung. Sie liefe
    auseinander, sobald jemand nur eine der beiden pflegt.

    Zusätzlich die Aussage, die den Unterschied macht: wird ein Stück weiterbewegt,
    **verschwindet** es hier — gezählt wird die *letzte* Beobachtung, nicht jede.
    """
    from app.models import Instance
    from app.services import objects as obj, places

    db = _db()
    try:
        _, instances, units = _units(db, quantity=3)
        art = instances[0].article_id
        regal = Instance(object_id=obj.next_object_id(db), article_id=art,
                         kind="einzeln", label="Regal C1")
        band = Instance(object_id=obj.next_object_id(db), article_id=art,
                        kind="einzeln", label="Band A")
        db.add_all([regal, band])
        db.flush()

        places.record(db, [u.id for u in units], regal.object_id, actor_id=None)
        db.flush()
        rows, total = places.contents(db, regal.object_id)
        assert total == len(units) == 3, f"Erwartet 3 Stück im Regal, sind {total}."

        places.record(db, [units[0].id], band.object_id, actor_id=None)
        db.flush()
        _, regal_total = places.contents(db, regal.object_id)
        _, band_total = places.contents(db, band.object_id)
        assert (regal_total, band_total) == (2, 1), (
            f"Nach dem Umlagern: Regal {regal_total}, Band {band_total} – gezählt wird "
            f"die LETZTE Beobachtung, nicht jede."
        )
    finally:
        db.rollback()
        db.close()


def test_a_split_batch_is_a_group_by_not_a_quantity_map():
    """**«990 im Regal, 10 am Band» sind Einzelinstanzen mit anderem Halter** (V-2).

    Das ist die Regel, die `location_split.py` ersatzlos ersetzt: die Aufteilung einer
    Charge ist eine Gruppierung, keine Mengen-Map mit einem denormalisierten Skalar
    daneben (ADR 009 §2.2).

    Bug-Form: eine Mengenspalte an der Ablage. Dann bräuchte es `reconcile`, `trim`,
    `set_single` — und einen Umschalter, welcher der beiden Werte gerade gilt.
    """
    from app.models import Instance, UnitPlace
    from app.services import objects as obj, places

    cols = {c.name for c in UnitPlace.__table__.columns}
    assert not (cols & {"quantity", "qty", "amount"}), (
        f"unit_places trägt eine Mengenspalte: {cols}. Eine Ablage gilt für EIN Stück."
    )

    db = _db()
    try:
        _, instances, units = _units(db, quantity=4)
        art = instances[0].article_id
        regal = Instance(object_id=obj.next_object_id(db), article_id=art,
                         kind="einzeln", label="Regal")
        band = Instance(object_id=obj.next_object_id(db), article_id=art,
                        kind="einzeln", label="Band")
        db.add_all([regal, band])
        db.flush()

        places.record(db, [u.id for u in units[:3]], regal.object_id, actor_id=None)
        places.record(db, [u.id for u in units[3:]], band.object_id, actor_id=None)
        db.flush()

        assert places.contents(db, regal.object_id)[1] == 3
        assert places.contents(db, band.object_id)[1] == 1
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# §7.4 — Was nicht wiederkommen darf
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_forbidden_forms_do_not_come_back():
    """**Die vier Altlasten, als Aussage über den Quelltext** (SYSTEM_LOGIC §7.4).

    Ein Verhaltenstest kann sie nicht widerlegen: sie sind Formen, keine Ergebnisse.
    Jede stand einmal im System und hat eine dokumentierte Bug-Form (ADR 009 §2).
    """
    forbidden = {
        "movable_instances": "V-1: eine Auswahl mit Fallunterscheidungen (ADR 009 §2.1)",
        "location_split": "V-2: eine Mengen-Map je Standort (§2.2)",
        "transport_class": "V-4: eine gespeicherte Transportklasse (§2.4)",
        "transport_mode": "V-4: derselbe gespeicherte Modus (§2.4)",
        "location_type": "V-5: ein Typfeld neben der Objektnummer (§3.2)",
    }
    hits = []
    for rel, src in _live_sources():
        code = _code_only(src)
        for needle, why in forbidden.items():
            if needle in code:
                hits.append(f"{rel}: '{needle}' – {why}")
    assert not hits, "Verbotene Formen sind zurück:\n  " + "\n  ".join(hits)


def test_the_system_never_creates_a_transport_by_itself():
    """**Das System legt nichts an — es bietet an** (§15.7, V-3).

    Dreimal gescheitert: die Begleit-Bewegungen (`companion`/`locked`) und die
    abgeleitete Bereitstellung, die heute auf `AUTO_PROVISIONING = False` steht. Ein
    Transport, den das System selbst anlegt, gehört niemandem.

    Bug-Form: `places.py`/`routers/places.py` legt einen Auftrag oder einen
    Prozessschritt an. Geprüft am Quelltext, weil ein Verhaltenstest nur die Pfade
    fände, an die jemand gedacht hat.
    """
    creators = ("Order(", "ProcessStep(", "create_order", "release(", "ensure_supply",
                "ensure_provisioning")
    for rel in ("services/places.py", "routers/places.py"):
        src = _code_only(_source(rel))
        for c in creators:
            assert c not in src, (
                f"{rel} legt selbst etwas an ('{c}'). Ein Transport entsteht nur durch "
                f"den Klick eines Menschen auf einen vorausgefüllten Entwurf (§15.7)."
            )


def test_no_module_reads_the_place_to_decide_which_units_it_touches():
    """**Was vor dem Modul steht, ist was vor dem Modul steht** (O6, V-1).

    Der teuerste Fehler des Vorgängers: `movable_instances` las Verbleib und
    Auftragsgrund, um zu entscheiden, woran ein Modul arbeitet — damit kamen vier
    Fremdbereiche (Verkauf, Retoure, Reservierung, Sperre) in der Bewegung an.

    Bug-Form: `services/process.py` oder ein Modul importiert `places`, um seine
    Arbeitsmenge zu bestimmen.
    """
    for rel in ("services/process.py", "domain/modules.py"):
        src = _code_only(_source(rel))
        assert "places" not in src and "unit_place" not in src.lower(), (
            f"{rel} liest den Ort. Ein Modul entscheidet nie anhand des Ortes, WELCHE "
            f"Stücke es anfasst (O6)."
        )
