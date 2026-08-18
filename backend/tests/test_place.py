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

import pytest

from .support import (
    APP, code_only, live_sources, make_company, make_move_step, make_units, session,
    source,
)

# Die Hilfen stehen in ``tests/support`` – **eine** Stelle, mehrere Wächter. Zwei Kopien
# von ``make_units`` wären zwei Aufbauten desselben Zustands, und sobald sie
# auseinanderlaufen, prüfen zwei Dateien gegen zwei verschiedene Welten.

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

    db = session()
    try:
        _, instances, units = make_units(db, quantity=1)
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
    for rel, src in live_sources():
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
    for rel, src in live_sources():
        assert "location_type" not in code_only(src), (
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

    db = session()
    try:
        _, instances, units = make_units(db, quantity=3)
        u = units[0]

        container = Instance(object_id=obj.next_object_id(db),
                             article_id=instances[0].article_id, kind="einzeln",
                             label="Behälter A")
        company = make_company(db, "Werk Nord")
        person = UserProfile(object_id=obj.next_object_id(db), firebase_uid=f"t{obj.obj_nr(1)}",
                             email="lager@example.com", first_name="Max", last_name="Müller")
        db.add_all([container, person])
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

    db = session()
    try:
        _, _, units = make_units(db, quantity=1)
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

    db = session()
    try:
        _, instances, units = make_units(db, quantity=2)
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
    src = source("services/places.py")
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
    src = source("services/places.py") + source("routers/places.py")
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

    db = session()
    try:
        _, instances, _ = make_units(db, quantity=1)
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

    db = session()
    try:
        _, instances, units = make_units(db, quantity=1)
        art = instances[0].article_id
        werk = make_company(db, "Werk Nord", street="Industriestrasse", street_nr="4",
                        zip_code="8000", city="Zürich", country="Schweiz")
        box = Instance(object_id=obj.next_object_id(db), article_id=art,
                       kind="einzeln", label="Behälter A")
        db.add(box)
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

    db = session()
    try:
        _, instances, units = make_units(db, quantity=3)
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

    db = session()
    try:
        _, instances, units = make_units(db, quantity=4)
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
    for rel, src in live_sources():
        code = code_only(src)
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
        src = code_only(source(rel))
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

    Bug-Form: die Arbeitsmenge wird aus dem Ort bestimmt statt aus dem Zustandspunkt.
    Geprüft am Quelltext, weil es eine Aussage über **Code** ist: `process.py` und die
    Modul-Registry dürfen den Ort gar nicht erst lesen, und `moving` **bekommt** seine
    Stücke, statt sie zu suchen.
    """
    import inspect
    from app.services import moving

    for rel in ("services/process.py", "domain/modules.py"):
        src = code_only(source(rel))
        assert "places" not in src and "unit_place" not in src.lower(), (
            f"{rel} liest den Ort. Ein Modul entscheidet nie anhand des Ortes, WELCHE "
            f"Stücke es anfasst (O6)."
        )
    # ``moving`` darf den Ort lesen – aber nur zum **Gruppieren**. Seine Arbeitsmenge
    # kommt als Argument herein; würde es sie selbst abfragen, wäre die Regel offen.
    for fn in (moving.hauls, moving.record_for_step):
        assert "units" in inspect.signature(fn).parameters, (
            f"moving.{fn.__name__} muss seine Stücke bekommen, nicht suchen (O6)."
        )
    body = code_only(inspect.getsource(moving))
    assert "_units_at" not in body and "query ( InstanceUnit )" not in body, (
        "moving sucht sich seine Arbeitsmenge selbst – das ist die Form, an der der "
        "Vorgänger gescheitert ist (ADR 009 §2.1)."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# B1–B6 — Das Modul «Bewegen» (PROCESS_CORE §9.8)
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_module_has_exactly_one_setting():
    """**B1 – genau EINE Einstellung: das Ziel.**

    Kein Transportmodus, keine Quelle, keine Menge, kein Zeitpunkt. Der Modus ist
    abgeleitet, alles andere gehört zur Laufzeit: ein Modul ist eine **Vorlage**, und was
    es beim Definieren nicht wissen kann, darf es nicht behaupten.

    Bug-Form: ein gespeicherter `transport_mode` – der Vorgänger hatte ihn und brauchte
    zwei Migrationen, um die Werte wieder loszuwerden (ADR 009 §2.4).
    """
    from fastapi import HTTPException
    from app.domain import modules

    mod = modules.get(modules.BEWEGEN)
    config = mod.clean_config({"target": 100000123})
    assert config[mod.TARGET] == 100000123
    # Nur Ziel + die beiden Felder, die JEDE Lesestelle vorfindet – nichts über den Weg.
    assert set(config) == {"target", "points", "sample"}, (
        f"«Bewegen» trägt mehr als sein Ziel: {sorted(config)}"
    )
    assert not config["points"], "Bewegt wird, was ankommt – ohne Erfassung."

    # Das Ziel ist Pflicht: «leer = frei wählbar» wäre ein zweiter Betriebsmodus, dem
    # niemand ansieht, welcher gerade gilt.
    for bad in ({}, {"target": 0}, {"target": None}, {"target": "abc"}):
        with pytest.raises(HTTPException) as e:
            mod.clean_config(bad)
        assert e.value.status_code == 400

    # Und ein Modus wird nirgends gespeichert.
    assert "transport" not in code_only(source("domain/modules.py"))


def test_two_source_places_are_two_hauls_one_is_one():
    """**B2 – die Fuhre ist abgeleitet, nicht eingestellt.**

    Zwei Ausgangsorte sind **zwei** Transporte: zwei Preise, zwei Etiketten, zwei
    Ankünfte. Drei Stücke am selben Ort sind **einer**.

    Bug-Form: nach dem Ziel gruppieren (dann wäre alles immer eine Fuhre) oder je Stück
    eine Zeile (dann wären drei Schrauben drei Pakete).
    """
    from app.models import Instance
    from app.services import moving, objects as obj, places

    db = session()
    try:
        order, instances, units = make_units(db, quantity=3)
        art = instances[0].article_id
        regal = Instance(object_id=obj.next_object_id(db), article_id=art,
                         kind="einzeln", label="Regal C1")
        band = Instance(object_id=obj.next_object_id(db), article_id=art,
                        kind="einzeln", label="Band A")
        ziel = Instance(object_id=obj.next_object_id(db), article_id=art,
                        kind="einzeln", label="Versandzone")
        db.add_all([regal, band, ziel])
        db.flush()
        step = make_move_step(db, order, ziel.object_id)

        # Alle drei am selben Ort → EINE Fuhre.
        places.record(db, [u.id for u in units], regal.object_id, actor_id=None)
        db.flush()
        one = moving.hauls(db, step=step, units=units)
        assert len(one) == 1 and one[0].pieces_count == 3, (
            f"Drei Stücke am selben Ort sind eine Fuhre, nicht {len(one)}."
        )

        # Eines woandershin → ZWEI Fuhren.
        places.record(db, [units[0].id], band.object_id, actor_id=None)
        db.flush()
        two = moving.hauls(db, step=step, units=units)
        assert len(two) == 2, f"Zwei Ausgangsorte sind zwei Fuhren, nicht {len(two)}."
        assert sorted(h.pieces_count for h in two) == [1, 2]
    finally:
        db.rollback()
        db.close()


def test_internal_creates_no_award_line():
    """**B3 – gleiche Adresse ⇒ innerbetrieblich, und dann passiert gar nichts.**

    Keine Vergabe-Zeile, auch keine leere und auch keine mit Kanal «selbst». Ein
    Formular für zwanzig Meter durch die Halle ist Papier für nichts.

    Bug-Form: den **Halter** vergleichen statt die **Adresse** – dann verlangte jeder
    Regalwechsel einen Transport.
    """
    from app.models import CompanySettings, Instance, InstanceUnit
    from app.services import moving, objects as obj, places

    db = session()
    try:
        order, instances, units = make_units(db, quantity=2)
        art = instances[0].article_id
        werk = make_company(db, "Werk Süd", street="Industriestrasse", street_nr="4",
                        zip_code="8000", city="Zürich", country="Schweiz")
        # Zwei Behälter im SELBEN Werk – verschiedene Halter, gleiche Anschrift.
        regal, band = [Instance(object_id=obj.next_object_id(db), article_id=art,
                                kind="einzeln", label=n) for n in ("Regal", "Band")]
        db.add_all([regal, band])
        db.flush()
        for box in (regal, band):
            bu = InstanceUnit(instance_id=box.id, suffix=1)
            db.add(bu)
            db.flush()
            places.record(db, [bu.id], werk.object_id, actor_id=None)
        places.record(db, [u.id for u in units], regal.object_id, actor_id=None)
        db.flush()

        assert places.same_place(db, regal.object_id, band.object_id), (
            "Zwei Behälter im selben Werk sind derselbe Ort – verglichen wird die "
            "ADRESSE, nicht der Halter."
        )
        step = make_move_step(db, order, band.object_id)
        haul = moving.hauls(db, step=step, units=units)[0]
        assert haul.internal, "Gleiche Anschrift ⇒ innerbetrieblich, keine Vergabe."
    finally:
        db.rollback()
        db.close()


def test_a_move_needs_the_context_scan():
    """**O5/B-Vollzug – ohne Ausgangsort passiert nichts.**

    Und zwar mit einem Satz, nicht mit einem ausgegrauten Feld: eine Sperre in der
    Oberfläche ist eine Bitte (G6.4).

    Bug-Form: einen Vorgabewert nehmen (etwa den zuletzt bekannten Ort). Dann schriebe
    ein vergessener Wechsel den falschen Ort, und **nichts** schlüge fehl.
    """
    from fastapi import HTTPException
    from app.models import Instance
    from app.services import moving, objects as obj

    db = session()
    try:
        order, instances, units = make_units(db, quantity=1)
        ziel = Instance(object_id=obj.next_object_id(db),
                        article_id=instances[0].article_id, kind="einzeln", label="Ziel")
        db.add(ziel)
        db.flush()
        step = make_move_step(db, order, ziel.object_id)

        with pytest.raises(HTTPException) as e:
            moving.record_for_step(db, step=step, units=units,
                                   from_holder_object_id=None, actor_id=None)
        assert e.value.status_code == 400
        assert "Ausgangsort" in e.value.detail
    finally:
        db.rollback()
        db.close()


def test_the_module_effect_is_a_no_op_for_every_other_module():
    """**Kein `if` nach dem Modultyp an der Ausführungsstelle.**

    `moving.record_for_step` wird bedingungslos gerufen – genau wie
    `capture_svc.record_for_step` und `consumption_svc.plan`. Die Fallunterscheidung
    entsteht aus der **Konfiguration** (kein Ziel → nichts), nicht aus einem Zweig.

    Bug-Form: `if step.module_type == 'bewegen':` in `process.confirm_step`.
    """
    from app.services import moving

    db = session()
    try:
        order, _, units = make_units(db, quantity=1)
        from app.models import ProcessStep
        capture = db.query(ProcessStep).filter(ProcessStep.order_id == order.id).first()
        assert moving.record_for_step(db, step=capture, units=units,
                                      from_holder_object_id=None, actor_id=None) is None, (
            "Ein Modul ohne Ziel muss ein No-op sein – auch ohne Kontext-Scan."
        )
    finally:
        db.rollback()
        db.close()

    src = code_only(source("services/process.py"))
    for smell in ("== 'bewegen'", '== "bewegen"', "modules.BEWEGEN"):
        assert smell not in src, (
            f"process.py verzweigt nach dem Modultyp ({smell}) – die Wirkung eines "
            f"Moduls entsteht aus seiner Konfiguration, nicht aus einem if."
        )


def test_moving_end_to_end_through_the_real_execution_point():
    """**Das ganze Modul durch ``process.confirm_step``** – nicht am Dienst vorbei.

    Geprüft wird, was danach wahr ist: der Ort steht, der Vorgang steht im Log **mit
    Ausgangs- und Zielort**, und der Status hat sich durch die Bewegung nicht geändert
    (§15.6). Genau die Kombination fände ein Test am Dienst allein nicht – die
    interessanten Fehler entstehen zwischen den Schritten.

    Bug-Form: den Ort erst nach dem Übergang schreiben (dann bliebe bei einem Fehler ein
    vorgerücktes Stück ohne Ort zurück) oder ihn gar nicht ins Ereignis hängen (dann
    stünde nirgends, woher es kam).
    """
    from app.models import Instance, InstanceUnit, ProcessEvent, ProcessStep
    from app.models.process_event import KIND_STEP
    from app.services import (
        article_process as tpl, objects as obj, places, process as proc,
    )
    from app.models import Article

    db = session()
    try:
        werk = make_company(db, "Werk Ost", street="Bahnhofstrasse", street_nr="1",
                        zip_code="9000", city="St. Gallen", country="Schweiz")
        art = Article(object_id=obj.next_object_id(db), name="Wanderstück", unit="stk",
                      serialization="unit")
        db.add(art)
        db.flush()
        regal = Instance(object_id=obj.next_object_id(db), article_id=art.id,
                         kind="einzeln", label="Regal C1")
        db.add(regal)
        db.flush()
        ru = InstanceUnit(instance_id=regal.id, suffix=1)
        db.add(ru)
        db.flush()
        places.record(db, [ru.id], werk.object_id, actor_id=None)   # Regal steht im Werk

        # Der Erzeugungsprozess besteht aus genau EINEM Modul: Bewegen ins Regal.
        tpl.create_steps(db, art, [{"module_type": "bewegen",
                                    "config": {"target": regal.object_id}}])
        db.flush()
        order = proc.release(
            db, lines=[{"article_object_id": art.object_id, "quantity": 2,
                        "origin": "neu", "units": []}], steps=[], actor_id=None)
        db.flush()
        step = db.query(ProcessStep).filter(ProcessStep.order_id == order.id).one()
        work = proc.step_work(db, order, step)
        assert work, "Vor dem Bewegen-Modul muss etwas stehen."

        units = proc.units_at_step(db, order, step)
        before = {u.id: u.status for u in units}

        # **Der echte Weg**: Kontext-Scan (wo bin ich) + Instanz-Scan, dann bestätigen.
        proc.confirm_step(
            db, order=order, step_id=step.id, values={},
            instance_object_id=work[0]["instance_object_id"], verification="scan",
            from_holder_object_id=werk.object_id, actor_id=None,
        )
        db.flush()

        moved = [u for u in units if u.instance_id == units[0].instance_id]
        for u in moved:
            assert places.current_of(db, u.id) == regal.object_id, (
                f"Einzelinstanz {u.id} liegt nicht im Ziel – der Ort wurde nicht "
                f"geschrieben."
            )

        # **Der Ort hat den Status nicht angefasst.** Was ihn danach ändert, ist der
        # Prozess (Ende-Objekt), nicht die Bewegung.
        rows = (db.query(ProcessEvent)
                .filter(ProcessEvent.order_id == order.id,
                        ProcessEvent.kind == KIND_STEP,
                        ProcessEvent.step_id == step.id).all())
        assert rows, "Die Bewegung muss als Schritt im Log stehen."
        for r in rows:
            assert r.status_before == r.status_after == before[r.instance_unit_id], (
                "Ein Ort ändert nie einen Status (§15.6, O3)."
            )
            assert r.payload.get("from") == werk.object_id, (
                "Woher gehört ins Ereignis – sonst sagte der Nachweis nur, wo es "
                "hinterher lag."
            )
            assert r.payload.get("to") == regal.object_id
    finally:
        db.rollback()
        db.close()


def test_an_external_haul_says_why_it_cannot_run_yet():
    """**Andere Anschrift ⇒ Versand ⇒ Vergabe** (§15.4/§15.5).

    Solange die Vergabe nicht gebaut ist, wird ein Versand **nicht** stillschweigend als
    innerbetriebliche Bewegung verbucht – das wäre die Behauptung, etwas sei angekommen,
    das nie losgefahren ist (G3). Stattdessen sagt die Ablehnung den Grund.

    Bug-Form: `same_place` grosszügig auslegen (etwa «keine Adresse ⇒ gleich»). Dann
    ginge ein echter Versand als interner Weg durch.
    """
    from fastapi import HTTPException
    from app.models import Instance, InstanceUnit
    from app.services import moving, objects as obj, places

    db = session()
    try:
        order, instances, units = make_units(db, quantity=1)
        art = instances[0].article_id
        nord = make_company(db, "Werk Nord", street="Industriestrasse", street_nr="4",
                        zip_code="8000", city="Zürich", country="Schweiz")
        sued = make_company(db, "Werk Süd", street="Seestrasse", street_nr="9",
                        zip_code="6000", city="Luzern", country="Schweiz")
        ziel = Instance(object_id=obj.next_object_id(db), article_id=art,
                        kind="einzeln", label="Halle Süd")
        db.add(ziel)
        db.flush()
        zu = InstanceUnit(instance_id=ziel.id, suffix=1)
        db.add(zu)
        db.flush()
        places.record(db, [zu.id], sued.object_id, actor_id=None)

        assert not places.same_place(db, nord.object_id, ziel.object_id), (
            "Zwei verschiedene Anschriften sind nicht derselbe Ort."
        )
        step = make_move_step(db, order, ziel.object_id)
        with pytest.raises(HTTPException) as e:
            moving.record_for_step(db, step=step, units=units,
                                   from_holder_object_id=nord.object_id, actor_id=None)
        assert e.value.status_code == 409
        assert "Versand" in e.value.detail, "Die Ablehnung muss den Grund nennen."
        assert not places.current(db, [units[0].id]), (
            "Nichts darf abgelegt worden sein – es ist nie losgefahren."
        )
    finally:
        db.rollback()
        db.close()


def test_the_address_rule_lives_in_one_place_and_has_two_readers():
    """**B6 – EINE Adressregel.**

    Der Vergleich selbst wohnt in `services/address.same`; `places.same_place` sagt nur,
    *welche* Adressen verglichen werden. Zwei Ableitungen wären zwei Antworten auf
    dieselbe Frage (V-6).

    Bug-Form: `moving` (oder später das Ressourcenmodul) baut sich einen eigenen
    Vergleich – etwa über PLZ-Gleichheit.
    """
    src = code_only(source("services/moving.py"))
    assert "same_place" in src, "moving muss die eine Regel benutzen."
    for smell in ("zip", "postal", "city", "street"):
        assert smell not in src, (
            f"moving vergleicht Adressteile selbst ('{smell}') statt die eine Regel zu "
            f"fragen (V-6)."
        )
    assert "def same" in source("services/address.py"), (
        "Die Adressregel gehört nach services/address.py."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# O7/O8 — Ohne Beobachtung wird nicht eingestuft · eine Handlung hat eine Stelle
# ═══════════════════════════════════════════════════════════════════════════════

def test_an_unknown_source_is_not_classified_as_internal():
    """**O7 – «nicht bekannt» ist weder intern noch Versand.**

    Bug-Form (der gemeldete Fehler): ``internal = src is None or same_place(...)``. Ohne
    Beobachtung wird geraten, und zwar in die falsche Richtung – die Fuhre gilt als
    innerbetrieblich, trägt darum keine Vergabe, und die Oberfläche zeigt genau die
    Handlung nicht, die fehlt. Die Ausführung stuft über den **Kontext-Scan** derweil
    korrekt als Versand ein und verlangt eine Vergabe, die nirgends anzufragen ist:
    eine Sackgasse.
    """
    from app.services import moving, places

    db = session()
    try:
        nord = make_company(db, "Werk Nord O7", street="Industriestrasse", street_nr="4",
                            zip_code="8000", city="Zürich", country="CH")
        sued = make_company(db, "Werk Süd O7", street="Bahnhofplatz", street_nr="1",
                            zip_code="3000", city="Bern", country="CH")
        order, _instances, units = make_units(db, quantity=2)
        step = make_move_step(db, order, sued.object_id)

        # **Ohne Ablage**: nicht bekannt – und darum keine Einstufung.
        offen = moving.hauls(db, step=step, units=units)
        assert len(offen) == 1
        assert offen[0].from_holder is None
        assert offen[0].internal is None, (
            "Ein unbekannter Ausgangsort wurde eingestuft – «nicht bekannt» ist weder "
            "intern noch Versand (O7).")
        assert offen[0].award is None, "Ohne Ausgangsort gibt es keinen Anlass."

        # **Mit Ablage**: jetzt steht es fest, und zwar als Versand.
        places.record(db, [u.id for u in units], nord.object_id, actor_id=None)
        db.flush()
        klar = moving.hauls(db, step=step, units=units)
        assert klar[0].internal is False, (
            "Andere Anschrift ist ein Versand – erst mit der Beobachtung ist das "
            "entscheidbar.")
    finally:
        db.rollback()
        db.close()


def test_a_human_lays_down_an_instance_not_a_list_of_unit_keys():
    """**O8 – die Eingabe ist, was ein Mensch scannt.**

    Bug-Form: der Endpunkt verlangt ``instance_unit_ids``. Eine Einzelinstanz trägt gar
    kein Etikett (§4.4) – diese Schlüssel kann ein Mensch nie haben, und genau daran war
    der Endpunkt seit Stufe 2 unbenutzbar, obwohl Dienst, Regel und Wächter standen.

    Die **Systemwege** rufen ``places.record`` unmittelbar und kennen ihre Stücke
    ohnehin; über den Router legt nur ein Mensch ab.
    """
    from app.schemas.place import PlaceCreate

    fields = set(PlaceCreate.model_fields)
    assert "instance_object_id" in fields, (
        "Die Ablage muss die Instanz nennen – das steht auf dem Etikett.")
    assert "instance_unit_ids" not in fields, (
        "Der Endpunkt verlangt wieder Einzelinstanz-Schlüssel; die kann ein Mensch nicht "
        "scannen (O8).")

    # Und die Systemwege gehen **nicht** über den Router.
    for rel in ("services/awards.py", "services/moving.py"):
        assert "places.record(" in source(rel), (
            f"{rel} soll unmittelbar über den einen Dienst schreiben, nicht über den "
            f"menschlichen Endpunkt.")


def test_laying_down_turns_the_haul_into_a_requestable_shipment():
    """**Der gemeldete Fall, Ende zu Ende** – über die echten Dienstpfade.

    Vorher: keine Beobachtung ⇒ keine Einstufung ⇒ kein Anlass ⇒ die Vergabe ist
    nirgends anzufragen, während die Ausführung sie verlangt.
    Nachher: eine Ablage ⇒ Versand ⇒ der Anlass steht, und die Vergabe ist anfragbar.
    """
    from app.domain import vergabe
    from app.services import awards, moving, places

    db = session()
    try:
        nord = make_company(db, "Werk Nord E2E", street="Industriestrasse", street_nr="4",
                            zip_code="8000", city="Zürich", country="CH")
        sued = make_company(db, "Werk Süd E2E", street="Bahnhofplatz", street_nr="1",
                            zip_code="3000", city="Bern", country="CH")
        order, instances, units = make_units(db, quantity=2)
        step = make_move_step(db, order, sued.object_id)

        vorher = moving.hauls(db, step=step, units=units)[0]
        assert vorher.internal is None and vorher.from_holder is None

        # Die Ablage – über den Dienst, den der neue Knopf ruft.
        places.record(db, [u.id for u in units], nord.object_id, actor_id=None)
        db.flush()

        fuhre = moving.hauls(db, step=step, units=units)[0]
        assert fuhre.internal is False and fuhre.from_holder == nord.object_id
        assert fuhre.award is None, "Das System fragt nie von sich aus an (§15.7)."

        # Und jetzt lässt sie sich anfragen – der Anlass ist der Ausgangsort.
        award = awards.request(db, subject_object_id=nord.object_id,
                               target_object_id=sued.object_id,
                               channel=vergabe.SELBST, actor_id=None)
        db.flush()
        assert awards.open_for(db, nord.object_id, sued.object_id) is not None
        assert award.state == vergabe.ANGEFRAGT
        assert moving.hauls(db, step=step, units=units)[0].award is not None, (
            "Die angefragte Vergabe hängt nicht an ihrer Fuhre.")
    finally:
        db.rollback()
        db.close()
