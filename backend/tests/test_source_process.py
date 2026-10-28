"""Quelltext-Wächter: Datenmodell, Prozesslogik, Prozessbild, Editor, Abweichung,
Aussondern, Bewegen, Verbrauch.
"""

import re

from tests._source import (
    BACKEND,
    FRONTEND,
    ROOT,
    _beleg,
    _body,
    _code,
    _component,
    _read,
)


# ---------------------------------------------------------------------------
# Das Datenmodell
# ---------------------------------------------------------------------------


def test_a_quantity_is_never_a_stored_field():
    """Die Menge einer Instanz ist die **Anzahl** ihrer Einzelinstanzen.

    Eine gespeicherte Menge wäre eine zweite Wahrheit neben den Zeilen, die sie zählt –
    und genau diese Fehlerklasse hat das Vorgängermodell wieder und wieder produziert.
    Was es nicht gibt, kann nicht driften.
    """
    for model in ("instance.py", "instance_unit.py"):
        src = _read(BACKEND / "app" / "models" / model)
        # Gemeint ist eine **Spalte**, nicht das Wort: der Docstring erklärt ja gerade,
        # warum es sie nicht gibt.
        columns = [l for l in src.split("\n") if "mapped_column(" in l]
        assert not [l for l in columns if "quantity" in l], (
            f"models/{model} trägt wieder eine Mengen-Spalte. Die Menge wird gezählt "
            f"(services/instances.quantity), nicht gespeichert."
        )

    svc = _read(BACKEND / "app" / "services" / "instances.py")
    assert "func.count(" in svc, "services/instances zählt die Menge nicht mehr."


def test_a_piece_number_is_derived_not_drawn_from_the_sequence():
    """Die Einzelinstanz zieht KEINE Nummer aus ``object_id_seq``.

    Der ganze Grund für die Instanz-Ebene ist, dass zigtausend Schrauben nicht
    zigtausend Objektnummern des gemeinsamen Kreises verbrauchen.
    """
    svc = _read(BACKEND / "app" / "services" / "instances.py")
    body = _body(svc, "create_instances")
    assert "next_object_ids(db, instance_count" in body, (
        "Die Objektnummern der INSTANZEN kommen nicht mehr aus der Sequence."
    )
    # Die Suffixe daneben – abgeleitet, nicht gezogen.
    suffixes = body.split("insert(InstanceUnit)")[1]
    assert "next_object_id" not in suffixes, (
        "Eine Einzelinstanz zieht eine Objektnummer aus dem gemeinsamen Kreis – ihre "
        "Nummer ist <Instanznummer>-<Suffix>, abgeleitet."
    )
    objects = _read(BACKEND / "app" / "services" / "objects.py")
    assert '"instance_unit"' not in objects, (
        "Die Einzelinstanz steht als eigener Objekttyp in der Registry."
    )


def test_the_suffix_counts_within_its_instance():
    """Der Suffix zählt ab 1 innerhalb seiner Instanz – vergeben an EINER Stelle.

    Er wird nicht mehr aus ``MAX(suffix)+1`` unter Zeilensperre ermittelt: es gibt kein
    Nachträglich-Hinzufügen mehr, also auch keine zwei gleichzeitigen Vergaben, gegen
    die eine Sperre schützen müsste. Die Stücke entstehen mit ihrer Instanz, in einem Zug.
    """
    svc = _read(BACKEND / "app" / "services" / "instances.py")
    assert "range(1, units_each + 1)" in _body(svc, "create_instances"), (
        "Die Suffixe zählen nicht mehr ab 1 innerhalb ihrer Instanz."
    )
    assert svc.count("insert(InstanceUnit)") == 1, (
        "Es gibt mehr als eine Stelle, an der Einzelinstanzen entstehen."
    )


def test_a_piece_is_created_only_with_its_instance_and_never_removed():
    """**Eine Einzelinstanz entsteht mit ihrer Instanz – und verschwindet nie.**

    Erzeugt wird sie damit ausschliesslich über einen Auftrag (Testnotiz #678): das ist
    der einzige Weg, auf dem eine Instanz entsteht. Die früheren drei Türen daneben –
    Instanz von Hand anlegen, Einzelinstanz nachschieben, Einzelinstanz deaktivieren –
    liessen Material ohne Auftrag, ohne Prozess und ohne Ereignis in die Welt kommen und
    wieder verschwinden.

    Und gelöscht wird nie (#679): die Nummer ist eine Identität, keine Position. Ein
    Verweis aus der Historie darf nicht ins Leere zeigen.
    """
    svc = _read(BACKEND / "app" / "services" / "instances.py")
    for gone in ("def add_units", "def create_instance("):
        assert gone not in svc, f"«{gone}» ist wieder da – ein zweiter Weg ins Dasein."

    router = _read(BACKEND / "app" / "routers" / "instances.py")
    assert "@router.post" not in router and "@router.delete" not in router, (
        "Die Instanzen haben wieder einen Schreib-Endpunkt."
    )
    schema = _read(BACKEND / "app" / "schemas" / "instance.py")
    for gone in ("class InstanceCreate", "class InstanceUnitsAdd"):
        assert gone not in schema, f"«{gone}» ist wieder da."

    api = _read(FRONTEND / "lib" / "api.ts")
    for gone in ("createInstance", "addInstanceUnits", "deactivateInstanceUnit"):
        assert gone not in api, f"Die Oberfläche ruft wieder «{gone}»."


# ---------------------------------------------------------------------------
# Was entfallen ist, bleibt entfallen
# ---------------------------------------------------------------------------


def test_the_order_is_a_record_type_like_every_other():
    """Der «Auftrag» reiht sich in die Datensatz-Systematik ein: Feed-Typ, Symbol, Filter."""
    types = _read(FRONTEND / "types" / "index.ts")
    m = re.search(r"export type ErpRecordType = ([^;]+);", types)
    assert m and "'order'" in m.group(1), "Der Feed kennt den Auftrag nicht."

    meta = _read(FRONTEND / "lib" / "erp-record.ts")
    assert "order:" in meta, "TYPE_META kennt den Auftrag nicht (Symbol/Farbe fehlen)."
    assert "'order'" in meta, "FILTER_TYPES kennt den Auftrag nicht."


def test_the_order_carries_only_what_the_process_needs():
    """Der Auftrag trägt seine Identität und seinen Lebenszyklus – sonst nichts.

    Spalten auf Vorrat wären erfundene Anforderungen. Der Endzustand ist keine Angabe des
    Auftrags: er steht einmal in der Fachschicht (``statuses.DEFAULT_END_STATUS``).
    """
    src = _read(BACKEND / "app" / "models" / "order.py")
    columns = {l.split(":")[0].strip() for l in src.split("\n") if "mapped_column(" in l}
    assert columns == {"id", "object_id", "name"}, (
        f"models/order.py trägt {sorted(columns)} – erwartet id, object_id, name "
        f"(created_at/updated_at/is_active kommen aus dem TimestampMixin). "
        f"Der Status ist ABGELEITET und darum keine Spalte."
    )
    # Der Endzustand steht an EINER Stelle: das Ende-Objekt liest ihn aus der Fachschicht.
    svc = _read(BACKEND / "app" / "services" / "process.py")
    assert svc.count("DEFAULT_END_STATUS") == 1, (
        "Der Endzustand wird an mehr als einer Stelle gesetzt."
    )


def test_a_draft_never_touches_the_database():
    """Ein Auftragsentwurf lebt nur im Browser: keine Entwurfs-Zeile, keine vorreservierte
    Objektnummer, kein Autosave. Die Nummer entsteht ausschliesslich beim Speichern."""
    svc = _read(BACKEND / "app" / "services" / "release.py")
    assert svc.count("next_object_id") == 2, (   # Import + genau EIN Aufruf
        "Die Objektnummer wird an mehr als einer Stelle gezogen."
    )
    assert "next_object_id(db," in _body(svc, "_write_definition"), (
        "Die Nummer entsteht nicht in der Freigabe."
    )
    # Sie wird NACH der Prüfung (samt Auflösung der bestehenden Stücke) gezogen: eine
    # Sequence ist nicht transaktional, ein Rollback danach liesse eine Lücke.
    body = _body(svc, "release")
    assert "held_by(" in _body(svc, "_take_picks") and "_take_picks(" in _body(svc, "_checked")
    assert body.index("_checked(") < body.index("_write_definition("), (
        "Die Objektnummer wird gezogen, bevor die bestehenden Stücke aufgelöst sind – "
        "jeder Verstoss verbrennt dann eine Nummer."
    )
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "next_object_id" not in router, "Der Router zieht selbst eine Nummer."

    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    # Gemeint ist der **Hook**, nicht das Wort: der Docstring erklärt ja gerade, warum
    # es keinen Autosave gibt.
    assert "useAutosave" not in detail, (
        "Das Auftrags-Fenster speichert automatisch – der Entwurf darf nichts anlegen."
    )


def test_the_order_tab_row_has_exactly_one_tab():
    """Genau EIN Reiter «Auftrag» – keine weiteren, auch keine leeren oder deaktivierten."""
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    m = re.search(r"const TABS = \[(.*?)\];", detail, re.S)
    assert m, "TABS fehlt im Auftrags-Fenster."
    assert m.group(1).count("key:") == 1, (
        f"Das Auftrags-Fenster hat {m.group(1).count('key:')} Reiter – es soll genau einen haben."
    )
    tabs = _read(FRONTEND / "components" / "erp" / "detail-tabs.tsx")
    assert "disabled" not in tabs, (
        "Die Reiter-Leiste kennt wieder deaktivierte Reiter – die soll es nicht geben."
    )


# ---------------------------------------------------------------------------
# Prozess-Darstellung (PROCESS_CORE.md §8)
# ---------------------------------------------------------------------------


def test_the_process_lines_are_computed_from_measured_anchors():
    """Knoten bestimmen ihre Position selbst, Linien werden **gemessen** – nie gesetzt.

    Das ist die eine Zusage, die beim vierten Modul bricht, wenn sie jemand aufweicht:
    eine Position, die im Code steht, ist eine Behauptung über eine Schrittzahl, die
    niemand kennt. Darum wird hier nicht geprüft, ob es «schön aussieht», sondern ob die
    Mechanik überhaupt noch die gemessene ist.
    """
    frame = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    assert "ResizeObserver" in frame and "getBoundingClientRect" in frame, (
        "Der Fluss misst seine Knoten nicht mehr – dann stehen die Linien irgendwo."
    )
    # Genau EINE absolute Positionierung ist erlaubt: das SVG über der Fläche. Jede
    # weitere wäre ein Knoten, der nicht mehr im Fluss liegt.
    assert frame.count("'absolute'") == 1, (
        f"process-flow.tsx positioniert {frame.count(chr(39) + 'absolute' + chr(39))} Dinge "
        f"absolut – erlaubt ist nur das Linien-Overlay."
    )

    # **Der Code, nicht die Prosa.** Ohne ``_code`` las dieser Waechter seine eigene
    # Begruendung mit: eine Erklaerung, die sagt «ohne absolute Position», enthaelt das
    # Wort – und er schlug an, weil jemand die Regel *beschreibt*, die er schuetzt.
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "absolute" not in diagram, (
        "Das Diagramm positioniert einen Knoten absolut – Knoten liegen im Fluss."
    )
    assert "<svg" not in diagram, (
        "Das Diagramm zeichnet ein eigenes SVG – es gibt EINEN Rahmen, der das tut."
    )
    assert "anchors[" in diagram, (
        "Die Linien lesen keine gemessenen Anker mehr."
    )


def test_the_process_object_is_one_component():
    """Ein Prozessobjekt = eine Komponente (§8). Der Modultyp ist Konfiguration.

    Kein Copy-Paste je Modulart – sonst wächst mit jedem Modul ein zweites Bauteil, das
    beim nächsten Design-Wechsel vergessen wird.
    """
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert diagram.count("function StepCard") == 1, (
        "Es gibt mehr als eine Modul-Komponente."
    )
    assert "FlowNode" in diagram, "Das Diagramm benutzt die gemeinsame Knoten-Hülle nicht."


def test_the_mockup_is_replaced_by_the_real_thing():
    """Das Grob-Mockup ist weg – an seiner Stelle steht das lauffähige Testmodul.

    Ein Mockup neben der echten Sache wäre eine zweite, unverbindliche Darstellung
    desselben Prozesses; welche gilt, müsste man raten.
    """
    assert not (FRONTEND / "components" / "erp" / "order-process-mockup.tsx").exists()
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "ProcessColumns" in detail, "Der Auftrag-Reiter zeigt das Prozessbild nicht."
    assert "Mockup" not in detail and "Beispieldaten" not in detail, (
        "Im Auftrag stehen noch Mockup-Reste."
    )


# ---------------------------------------------------------------------------
# Prozesslogik (PROCESS_CORE.md)
# ---------------------------------------------------------------------------


def test_colour_hangs_on_the_status_at_exactly_one_place():
    """Farbe hängt am **Status**, nie an der Position – und die Zuordnung steht EINMAL.

    Baut eine Komponente sich ihre eigene Farblogik, sieht derselbe Zustand an zwei
    Stellen verschieden aus, und jede neue Ansicht muss die Regel neu erfinden.
    """
    # Geprüft wird das **Verbot**, nicht die Anwesenheit eines Imports: die frühere
    # Fassung verlangte, dass jede dieser Dateien `statusCfg` *nennt* – und hielt damit
    # einen Import am Leben, der längst nichts mehr tat. Ein Wächter, der tote Zeilen
    # erzwingt, arbeitet gegen sein eigenes Ziel.
    for name in ("process-diagram.tsx", "order-detail.tsx", "stock-view.tsx",
                 "unit-numbers.tsx", "stock-bar.tsx"):
        src = _code(_read(FRONTEND / "components" / "erp" / name))
        # ``MODULE_TONE`` ist ausdrücklich erlaubt: Prozessmodule tragen eine eigene,
        # von der Ampel getrennte Farbfamilie (§5.3). Verboten ist der Griff zur Ampel.
        for ampel in ("TONE.done", "TONE.pending", "TONE.danger"):
            assert ampel not in src, (
                f"{name} greift direkt auf «{ampel}» zu – die Zuordnung Status→Farbe "
                f"gehört in lib/process-status.ts."
            )

    # Und wer Farbe zeigt, holt sie dort: das Diagramm färbt Knoten nach Zustand.
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "statusCfg" in diagram, "Das Diagramm färbt nicht über die zentrale Zuordnung."


def test_the_process_diagram_is_one_component_with_two_modes():
    """EINE Komponente für Definition und Ausführung (§8.1).

    Zweimal zu bauen wäre an dieser Stelle der teuerste Fehler: der Artikel-Reiter
    «Erzeugungsprozess» ist dieselbe Darstellung, und ein zweites Bauteil liefe beim
    ersten Design-Wechsel auseinander.
    """
    src = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "'definition'" in src and "'ausfuehrung'" in src, "Die zwei Modi fehlen."
    assert src.count("function StepCard") == 1, "Es gibt mehr als eine Modul-Komponente."
    # Die Definition der Einzelinstanzen ist ein Slot, kein fester Bestandteil – sonst
    # wäre die Komponente am Artikel (der keine Einzelinstanzen hat) unbrauchbar.
    assert "head" in src, "Die Definition ist kein Slot – der Artikel könnte sie nicht weglassen."
    code = "\n".join(
        l for l in src.split("\n")
        if not l.lstrip().startswith(("*", "//", "/*"))
    )
    assert "Einzelinstanz" not in code, (
        "Das Diagramm kennt Einzelinstanzen fachlich – dann ist es am Artikel nicht "
        "wiederverwendbar. (Im Kommentar ist das Wort in Ordnung.)"
    )


def test_the_exclusivity_rule_lives_in_the_database():
    """Die Exklusivität steht als **partieller Unique-Index** in der Datenbank (§3).

    In der Anwendungslogik geprüft, lesen zwei gleichzeitige Freigaben beide «ist frei»
    und schreiben beide. Der Index ist die einzige Stelle, an der das nicht passieren
    kann – darum darf er nicht still verschwinden.
    """
    model = _read(BACKEND / "app" / "models" / "order_unit.py")
    assert "uq_order_units_active" in model and "released_at IS NULL" in model, (
        "Der partielle Unique-Index fehlt am Modell."
    )
    mig = _read(BACKEND / "alembic" / "versions" / "161_baseline.sql")
    assert "uq_order_units_active" in mig and "released_at IS NULL" in mig, (
        "Die Migration legt den Index nicht an.")


def test_a_status_change_always_writes_the_log():
    """Es gibt **einen** Schreibweg für einen Statuswechsel (§10.2).

    Zöge jemand ``instance_units.status`` an einer zweiten Stelle nach, liefen Projektion
    und Ereignis-Log auseinander – und die Historie wäre keine Wahrheit mehr, sondern
    eine Behauptung.
    """
    svc = _read(BACKEND / "app" / "services" / "process.py")
    # Die Schreibstelle arbeitet auf einer **Liste** (5000 Stück wären 15 000 einzelne
    # Anweisungen). Ein schneller Pfad daneben wäre genau der zweite Schreibweg – also
    # muss alles, was einen Status setzt, in dieser einen Funktion stehen.
    body = svc.split("def _pass(")[1].split("\ndef ")[0]
    assert svc.count("update(InstanceUnit)") == 1 and "update(InstanceUnit)" in body, (
        "Der Status wird an mehr als einer Stelle gesetzt."
    )
    assert svc.count(".status = status_after") == 1 and ".status = status_after" in body, (
        "Die Projektion wird ausserhalb der einen Schreibstelle nachgezogen."
    )
    assert "insert(ProcessEvent)" in body, (
        "Die eine Schreibstelle schreibt keinen Log-Eintrag."
    )
    # Kein Update-/Delete-Pfad auf die Historie.
    model = _read(BACKEND / "app" / "models" / "process_event.py")
    # Gemeint ist die **Vererbung**, nicht das Wort: der Docstring erklärt ja gerade,
    # warum es sie hier nicht gibt.
    assert "class ProcessEvent(Base)" in model, (
        "Der Ereignis-Log erbt den TimestampMixin – ein ``updated_at`` verspricht, dass "
        "eine Zeile sich ändern kann. Eine Korrektur ist ein neuer Eintrag."
    )
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "@router.delete" not in router and "@router.patch" not in router, (
        "Der Auftrags-Router bietet einen Änderungs-/Löschpfad an – die Historie ist "
        "append-only, und die Struktur ist nach der Freigabe eingefroren. Was an einem "
        "Auftrag geschieht, ist eine **Handlung** und damit ein `POST` (wie `/confirm` "
        "oder `/steps/{id}/purchase`): sie hinterlässt einen Eintrag, statt ein Feld zu "
        "überschreiben."
    )


def test_the_release_conditions_live_at_exactly_one_place():
    """Die beiden harten Freigabebedingungen (§6.2) stehen EINMAL.

    Die Oberfläche fragt sie ab, statt sie nachzuformulieren – sonst legt der
    Freigabe-Knopf einen anderen Massstab an als der Server.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import orders as orders_svc

    # Ein leerer Entwurf berührt die Datenbank nicht – darum genügt hier ``None``.
    # Der gefüllte Fall braucht echte Artikel und steht im PostgreSQL-Durchlauf.
    assert orders_svc.validate_draft(None, {}) == [
        "mindestens eine Einzelinstanz", "mindestens ein Prozessschrittmodul",
    ]

    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "validateOrder" in detail, "Die Oberfläche fragt die Regel nicht ab."
    assert "Es fehlt:" in detail, "Der Knopf sagt nicht, was fehlt."


def test_an_instance_is_never_created_beside_an_order():
    """**Material entsteht nur über einen Auftrag** (Testnotiz #678).

    Der Bestand-Reiter konnte eine Instanz von Hand anlegen – damit gab es Einzelinstanzen
    ohne Auftrag, ohne Prozess, an dem sie hängen, und ohne Ereignis, das ihre Entstehung
    festhält. Der Weg über den Auftrag ist nicht der bequemere, sondern der einzige, bei
    dem die Herkunft eines Stücks beantwortbar bleibt.
    """
    detail = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "createInstance" not in detail and "AddInstance" not in detail, (
        "Der Bestand-Reiter legt wieder Instanzen an – dann entsteht Material ohne Auftrag."
    )
    # Gefragt ist «schreibt sie?», nicht «spricht sie mit dem Server?»: der Bestand ist
    # eine Summierung, und die muss er lesen. Geprüft wird darum jeder Aufruf einzeln –
    # erlaubt sind ausschliesslich Lese-Methoden.
    for name in ("stock-view.tsx", "unit-numbers.tsx", "stock-bar.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        calls = set(re.findall(r"\bapi\.([A-Za-z_]+)\(", src))
        writes = {c for c in calls if not c.startswith("get")}
        assert not writes, (
            f"«{name}» schreibt ({', '.join(sorted(writes))}) – der Bestand ist eine "
            f"Summierung, keine Werkbank."
        )


# ---------------------------------------------------------------------------
# Definitionsbereich und Erzeugungsprozess
# ---------------------------------------------------------------------------


def test_new_unit_numbers_come_from_exactly_one_place():
    """Neue Einzelinstanznummern entstehen **nur** bei der Freigabe eines Auftrags.

    Kein Import, kein Direkteintrag, kein Modul. Gäbe es einen zweiten Weg, wäre die
    Nummer keine Identität mehr, sondern eine Vereinbarung – und der erste Parallelzugriff
    hätte zwei Stücke mit derselben.
    """
    import sys
    sys.path.insert(0, str(BACKEND))

    svc = _read(BACKEND / "app" / "services" / "instances.py")
    # Die Suffix-Vergabe steht in genau diesem Modul und in genau EINER Funktion: die
    # Stücke entstehen mit ihrer Instanz, und ein Nachschieben gibt es nicht (#678).
    assert "def create_instances(" in svc and "def add_units(" not in svc

    # Ausserhalb dieses Moduls **vergibt** niemand einen Suffix. Gemeint ist das
    # Schreiben – eine Einzelinstanz bauen oder ihren Suffix setzen –, nicht das Lesen:
    # ``object_id, suffix = parsed`` liest eine Nummer und ist genau richtig so.
    app = BACKEND / "app"
    writes = re.compile(r"InstanceUnit\(|[\"']suffix[\"']\s*:|\.suffix\s*=(?!=)")
    offenders = [
        f.relative_to(ROOT)
        for f in app.rglob("*.py")
        if f.name != "instances.py"
        and "models/instance_unit.py" not in str(f)
        and writes.search(_read(f))
    ]
    assert not offenders, f"Suffixe werden ausserhalb von instances.py vergeben: {offenders}"

    # Und die Erzeugung hat genau einen Aufrufer: die Freigabe.
    mat = _read(BACKEND / "app" / "services" / "materialize.py")
    assert "create_instances(" in mat, "materialize erzeugt nicht über die eine Stelle."
    proc = _read(BACKEND / "app" / "services" / "release.py")
    assert "materialize.create_for_line(" in proc, (
        "Die Freigabe erzeugt die neuen Stücke nicht über materialize."
    )


def test_the_two_serialization_cases_are_parameters_not_two_code_paths():
    """Einzelserialisierung und Charge sind ein **Zahlenpaar**, kein zweiter Zweig.

    3 einzeln = (3, 1) · Charge über 3 = (1, 3). In beiden Fällen ist das Produkt die
    Menge – genau das prüft ``assert_quantity`` danach.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import materialize

    assert materialize.plan("unit", 3) == (3, 1)
    assert materialize.plan("batch", 3) == (1, 3)
    assert materialize.plan("unit", 1) == (1, 1)
    assert materialize.plan("batch", 1) == (1, 1)
    for serialization in ("unit", "batch"):
        for qty in (1, 2, 7, 5000):
            count, each = materialize.plan(serialization, qty)
            assert count * each == qty, (serialization, qty, count, each)


def test_the_quantity_invariant_is_checked_before_and_after():
    """Menge N heisst N Einzelinstanzen – geprüft **vor** der ersten Nummer und danach.

    Der erste Aufruf fängt eine Eingabe ab, ohne eine Objektnummer zu kosten; der zweite
    ist der Wächter gegen einen Fehler in diesem Code.
    """
    proc = _read(BACKEND / "app" / "services" / "release.py")
    assert proc.count("materialize.assert_quantity(") == 2, (
        "Die Mengen-Invariante wird nicht zweimal geprüft (Plan und Ergebnis)."
    )
    plan_at = proc.index("materialize.assert_quantity(")
    number_at = proc.index("next_object_id(db, \"order\")")
    assert plan_at < number_at, (
        "Die Mengen-Prüfung läuft erst nach der Nummernvergabe – dann kostet jeder "
        "Eingabefehler eine Objektnummer."
    )


def test_every_check_runs_before_the_first_object_number():
    """Ein abgebrochener Freigabe-Versuch verbraucht **keine** Objektnummer (AK8).

    ``nextval`` ist absichtlich nicht transaktional; ein Rollback danach liesse eine
    Lücke. Darum liegt jede Prüfung davor. Der einzige Rest ist der echte
    Parallelzugriff, den erst der Unique-Index abfängt – und der ist dokumentiert.
    """
    proc = _read(BACKEND / "app" / "services" / "release.py")
    body = _body(proc, "release")
    assert body.index("_checked(") < body.index("_write_definition("), (
        "Die Prüfung läuft nach der Nummernvergabe.")
    head = _body(proc, "_checked") + _body(proc, "_take_picks")
    for guard in ("resolve_lines(", "steps_for(", "assert_releasable(",
                  "chain.assert_closes(", "held_by(", "_assert_may_leave(",
                  "assert_quantity("):
        assert guard in head, f"«{guard}» läuft nach der Nummernvergabe."


def test_the_template_is_a_copy_not_a_reference():
    """Die Vorlage wird **kopiert**, mit Versionsstempel.

    Ein Verweis hiesse, dass eine spätere Artikeländerung laufende Aufträge rückwirkend
    umschreibt – das widerspricht «eingefroren» (§6.4).
    """
    step = _read(BACKEND / "app" / "models" / "process_step.py")
    assert "source_article_id" in step and "source_version" in step, (
        "Der kopierte Schritt trägt keinen Herkunftsstempel."
    )
    tpl = _read(BACKEND / "app" / "services" / "article_process.py")
    assert "def mirror(" in tpl and '"source_version": version' in tpl
    # Die Vorlage ist eine eigene Tabelle: was es nicht gibt, kann nicht ausgeführt werden.
    model = _read(BACKEND / "app" / "models" / "article_process_step.py")
    assert "__tablename__ = \"article_process_steps\"" in model
    router = _read(BACKEND / "app" / "routers" / "articles.py")
    assert "confirm" not in router, (
        "Der Artikel-Router bietet eine Ausführung an – die Vorlage führt nichts aus."
    )


def test_the_definition_asks_in_one_order_and_locks_the_rest():
    """Artikel → Menge → Herkunft. Jedes Feld ist gesperrt, bis das davor beantwortet ist.

    Ohne Artikel ist die Menge nicht deutbar (einzeln oder Charge?), ohne Menge die
    Herkunft nicht entscheidbar (welche Stücke?).
    """
    ui = _read(FRONTEND / "components" / "erp" / "definition-lines.tsx")
    assert "disabled={!hasArticle}" in ui, "Die Menge ist vor der Artikelwahl nicht gesperrt."
    # «Neu» braucht eine Vorlage – geprüft wird die **Bedingung**, nicht ihre Schreibweise:
    # sie steht seit Notiz #694 als Option des Schiebe-Reglers, nicht mehr als eigener Knopf.
    assert "!hasTemplate" in ui, "«Neu» ist ohne Erzeugungsprozess nicht gesperrt."
    assert "Erzeugungsprozess" in ui, "Der Grund steht nicht im Klartext."
    # FIFO ist ein Vorschlag, kein Zwang: die Auswahl bleibt sichtbar und abwählbar.
    assert "fifo" in ui.lower() and "entfernen" in ui


def test_large_quantities_are_counted_not_listed():
    """Bei Menge 5000 zeigt das Diagramm **eine Pille mit Anzahl**, nicht 5000 Zeilen.

    Die Datenhaltung bleibt pro Einzelinstanz – dies ist die Darstellungsfrage. Und der
    Deckel der Historie wird ausgewiesen: eine stumm gekappte Liste sähe aus wie die
    ganze Wahrheit.
    """
    svc = _read(BACKEND / "app" / "services" / "flow.py")
    assert "func.count(" in svc, "Die Gruppen werden nicht gezählt, sondern aufgelistet."
    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    assert "class FlowUnits(" in schema and "event_count" in schema
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "GraphUnits" in diagram and "g.count" in diagram
    # Der Deckel steht dort, wo die Historie jetzt steht: **am Prozessobjekt** (§5).
    assert "von ${total} Einträgen" in diagram, "Der Deckel der Historie wird verschwiegen."


def test_the_article_process_stands_under_the_specification():
    """**Kein eigener Reiter mehr** (Testnotiz #671): der Erzeugungsprozess steht in der
    Spezifikation, direkt unter dem ersten Container.

    Es war eine Trennung, die es fachlich nicht gibt: beide Hälften gehören zur selben
    Anlage, und der Artikel entsteht erst, wenn sie zusammen vollständig sind. Wer den
    Prozess in einem zweiten Reiter versteckt, lässt den Nutzer nach der Hälfte der
    Freigabebedingung suchen.
    """
    detail = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "'prozess'" not in detail, "Der Reiter «Erzeugungsprozess» ist wieder da."
    # **Seit Testnotiz #760 hat der Artikel gar keine Reiter mehr** – der Bestand ist in
    # dieselbe Ansicht gerückt, und damit blieb nichts, was einen zweiten rechtfertigt.
    # Der Wächter prüft darum die Aussage, nicht die frühere Bauform: alles steht in
    # EINER Ansicht, und der Prozess ist Teil davon.
    assert "const TABS" not in detail and "DetailTabs" not in detail, (
        "Der Artikel hat wieder Reiter – dann ist die Freigabebedingung erneut auf zwei "
        "Ansichten verteilt."
    )
    assert "<ArticleProcess" in detail, "Der Erzeugungsprozess wird nicht gerendert."
    assert "confirmStep" not in detail, "Der Artikel führt einen Schritt aus."
    assert "getArticleProcess" in detail


# ---------------------------------------------------------------------------
# Bug 1 – der Artikel entsteht erst bei der Freigabe
# ---------------------------------------------------------------------------


def test_an_article_is_created_at_release_not_while_typing():
    """**Vor der Freigabe existiert kein Datensatz und keine Objektnummer.**

    Vorher speicherte das Formular per Autosave, sobald die Pflichtfelder der
    Spezifikation standen – der Artikel bekam eine Nummer, konnte aber nichts erzeugen,
    weil sein Prozess leer war. Der Wächter hält beide Hälften fest: die Oberfläche legt
    nicht mehr im Vorbeitippen an, und der Server verlangt beides.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import articles as svc

    detail = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "useAutosave" not in detail, (
        "Das Artikel-Formular speichert wieder automatisch – genau der behobene Fehler."
    )
    assert detail.count("api.createArticle") == 1 and "async function release()" in detail, (
        "Der Artikel darf an GENAU EINER Stelle entstehen: in `release()`."
    )
    assert "api.validateArticle" in detail, (
        "Die Oberfläche muss die Freigabebedingungen abfragen, statt sie nachzuformulieren."
    )

    # Beide Bedingungen, an EINER Stelle – und beide werden auch verlangt.
    assert svc.missing_for_release({"name": "X", "size": "1x1", "weight_kg": 1, "steps": []}) == [
        "mindestens ein Prozessschrittmodul"
    ]
    assert svc.missing_for_release({"steps": [{"module_type": "datenerfassung"}]}) == [
        "Artikelname", "Abmessungen", "Gewicht"
    ]
    assert svc.missing_for_release(
        {"name": "X", "size": "1x1", "weight_kg": 1,
         "steps": [{"module_type": "datenerfassung"}]}) == []

    # Und es gibt keinen Schreibpfad, der die Vorlage nachträglich ändert.
    router = _read(BACKEND / "app" / "routers" / "articles.py")
    assert "/process/steps" not in router, (
        "Ein «Modul nachträglich hinzufügen» wäre eine Tür in einen eingefrorenen Artikel."
    )


# ---------------------------------------------------------------------------
# Bug 2 – eine Tabelle mit fremder Form wird GEMELDET, nie gelöscht (Cleanup 2026-10)
# ---------------------------------------------------------------------------


def test_the_start_builds_no_schema_and_drops_nothing():
    """**Das Schema baut allein die Migration** – der Start legt nichts an und löscht
    nichts. Bis Oktober 2026 legten ``create_all`` und Spalten-Netze beim Start an, was
    eine Migration vergessen hatte, und versteckten die Lücke damit; davor stand hier ein
    ``DROP TABLE`` für Tabellen fremder Form, in denen heute Aufträge und der append-only
    Log stehen."""
    code = _code(_read(BACKEND / "app" / "main.py"))
    for word in ("DROP TABLE", "create_all", "ALTER TABLE", "ADD COLUMN"):
        assert word not in code, f"Der Start baut wieder am Schema («{word}»)."


# ---------------------------------------------------------------------------
# Das Modul «Datenerfassung»
# ---------------------------------------------------------------------------


def test_the_article_process_is_the_order_component():
    """Der Erzeugungsprozess ist eine **Übernahme**, kein Nachbau.

    Beide Definitionsorte – Artikel und Auftrag – benutzen denselben `ProcessDesigner`.
    Der einzige Unterschied ist der fehlende Bereich darüber, in dem der Auftrag seine
    Einzelinstanzen definiert: ein Artikel hat keine (§8.1/§8.2).
    """
    tab = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    order = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "ProcessDesigner" in tab and "ProcessDesigner" in order, (
        "Die beiden Definitionsorte teilen sich den Editor nicht – zwei Stände driften."
    )
    assert "DefinitionLines" not in tab, (
        "Der Artikel hat keine Einzelinstanzen – ein Definitionsbereich gehört nicht hierhin."
    )
    # Der Bereich darüber ist der EINE Unterschied: nur der Auftrag füllt ihn.
    assert "head=" in order and "head=" not in tab


# ---------------------------------------------------------------------------
# #669 – eine Statusliste, drei Achsen
# ---------------------------------------------------------------------------


def test_there_is_exactly_one_status_list():
    """**So wenige Status wie möglich, so viele gemeinsame wie möglich.**

    Vorher trug jede Achse ihre eigene Karte: der Artikel in ``lib/article``, der Auftrag
    hart im ``record-status``, das Stück in ``process-status``. Derselbe Zustand hiess
    darum an drei Orten drei Mal etwas anderes – und beim Auftrag ausgerechnet
    «Freigegeben», was gar kein Zustand ist, sondern die Aktion, mit der er entstanden
    ist.

    Der Wächter hält fest, dass es die zweite Karte nicht mehr gibt: Beschriftung und
    Farbe eines Status stehen ausschliesslich in ``lib/process-status``.
    """
    article = _read(FRONTEND / "lib" / "article.ts")
    assert "ARTICLE_STATUS" not in article and "statusConfig" not in article, (
        "lib/article hält wieder eine eigene Statuskarte – das ist die zweite Wahrheit."
    )

    record = _read(FRONTEND / "lib" / "record-status.ts")
    for fn in ("articleStatus", "orderStatus", "organizationStatus"):
        assert "statusCfg" in _body(record, fn, kind="function"), (
            f"{fn} baut seine Badge selbst, statt die eine Liste zu lesen."
        )
    assert "'Freigegeben'" not in record and "'Abgeschlossen'" not in record, (
        "In record-status stehen wieder Statuswörter – sie gehören in process-status."
    )


def test_the_order_has_exactly_three_states_and_none_of_them_is_released():
    """Ein Auftrag ist **Im Prozess · Abgeschlossen · Abgebrochen** – sonst nichts.

    «Freigegeben» ist die *Aktion*, mit der er entstanden ist (§6.1); als Zustand daneben
    wäre es die Behauptung, ein Auftrag könne freigegeben sein, ohne zu laufen.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    assert st.ORDER_STATUSES == (st.IM_PROZESS, st.ABGESCHLOSSEN, st.ABGEBROCHEN)
    assert st.FREIGEGEBEN not in st.ORDER_STATUSES

    # Im Frontend ist die Achse eine **Eigenschaft** des Eintrags, keine zweite Liste –
    # geprüft wird darum der Eintrag selbst.
    ts = _read(FRONTEND / "lib" / "status-catalog.ts")
    m = re.search(r"\{ value: FREIGEGEBEN,.*?\}", ts, re.S)
    assert m, "Der Katalog kennt «Freigegeben» nicht."
    assert '"order"' not in m.group(0), (
        "Die Oberfläche kennt «Freigegeben» wieder als Auftragszustand."
    )


def test_no_state_is_stored_where_it_can_be_derived():
    """**Kein zweiter Ort, an dem er gesetzt wird.**

    Auftrag und Instanz leiten ihren Zustand aus ihren Einzelinstanzen ab. Eine Spalte
    daneben ist genau der zweite Ort – und der lief prompt weg: ``orders.status`` stand
    auf ``released``, ``instances.status`` auf ``new``, und geschrieben hat sie nie
    jemand.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import Instance, Order

    assert "status" not in Order.__table__.columns, (
        "Der Auftrag trägt wieder eine Status-Spalte – er leitet ihn ab."
    )
    assert "status" not in Instance.__table__.columns, (
        "Die Instanz trägt wieder eine Status-Spalte – sie ist eine Gruppe und leitet ab."
    )

    process = _read(BACKEND / "app" / "services" / "order_state.py")
    assert "def order_status" in process and "def order_statuses" in process, (
        "Die Ableitung des Auftragsstatus fehlt (Einzel- und Batch-Form)."
    )
    # Die **Instanz** leitet ihn nicht einmal mehr ab: eine Gruppe hat keinen Zustand
    # (Testnotiz #675). Bei einer Charge mit gemischten Stücken gäbe es keine richtige
    # Antwort, und jede gewählte wäre eine Behauptung.
    inst = _read(BACKEND / "app" / "services" / "instances.py")
    assert "def status_of" not in inst and "def statuses" not in inst
    from app.schemas.instance import InstanceResponse, InstanceSummary, InstanceUnitResponse
    for cls in (InstanceResponse, InstanceSummary):
        assert "status" not in cls.model_fields, (
            f"{cls.__name__} trägt wieder einen Zustand – den hat nur die Einzelinstanz."
        )
    assert "status" in InstanceUnitResponse.model_fields, (
        "Die Einzelinstanz hat ihren Zustand verloren – er ist der einzige, den es gibt."
    )
    assert "instanceStatus" not in _read(FRONTEND / "lib" / "record-status.ts")


# ---------------------------------------------------------------------------
# #672 – der Auftrag bekommt seinen Namen mit seiner Nummer
# ---------------------------------------------------------------------------


def test_the_order_is_named_in_the_same_breath_as_its_number():
    """«Auftrag <Objektnummer>», vergeben **im selben Zug** wie die Nummer.

    Zwei Schritte daraus zu machen hiesse, dass es einen Moment gibt, in dem ein Auftrag
    existiert und keinen Namen hat – und die Oberfläche müsste einen erfinden.
    """
    body = _body(_read(BACKEND / "app" / "services" / "release.py"), "_write_definition")
    assert 'name=f"Auftrag {object_id}"' in body, (
        "Der Name entsteht nicht zusammen mit der Objektnummer."
    )
    assert body.index("next_object_id") < body.index("name=f\"Auftrag"), (
        "Der Name wird vor der Nummer vergeben – dann steht er auf einer Nummer, die es "
        "noch nicht gibt."
    )

    name_ts = _read(FRONTEND / "lib" / "record-name.ts")
    assert "o.name" in _body(name_ts, "orderName", kind="function"), (
        "Die Oberfläche baut den Auftragsnamen selbst – dann gibt es zwei Stellen dafür."
    )
    assert "'Auftrag '" not in name_ts and '"Auftrag "' not in name_ts


# ---------------------------------------------------------------------------
# #673 / #674 – Palette, Autosave, kein Bearbeiten, Drag & Drop
# ---------------------------------------------------------------------------


def test_a_module_is_created_by_the_palette_and_never_edited():
    """**Kein «Hinzufügen», kein «Bearbeiten».**

    Ein Klick auf die Palette legt das Modul an; es steht ab dem ersten Moment im Fluss
    und füllt sich, während man tippt. Ändern heisst löschen und neu anlegen – der
    Mülleimer ist der einzige zweite Weg.

    Ein deaktivierter Bearbeiten-Knopf wäre kein Kompromiss, sondern ein toter Pfad: er
    verspricht etwas, das es nicht gibt.
    """
    assert not (FRONTEND / "components" / "erp" / "module-editor.tsx").exists(), (
        "Der alte Modul-Editor ist wieder da – mit ihm der Hinzufügen-/Bearbeiten-Pfad."
    )
    src = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    code = re.sub(r"/\*.*?\*/|//.*", "", src, flags=re.S)   # Kommentare erklären, sie tun nichts
    for gone in ("Bearbeiten", "onEdit", "editing", "Hinzufügen"):
        assert gone not in code, f"«{gone}» steht wieder im Editor."
    assert "onPick" in src and "onChange([...modules," in src, (
        "Die Palette legt das Modul nicht direkt an."
    )
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "onDelete" in diagram, "Der Mülleimer fehlt – dann gibt es gar keinen Weg zurück."


def test_the_palette_stands_where_the_next_module_would_go():
    """Die Auswahl sitzt **am Ende des letzten Moduls**, nicht in einem eigenen Kasten.

    Ein Symbol je Modultyp in seiner Farbe, Name im Hover – dieselbe Interaktion wie die
    Mengeneinheit am Artikel (`IconSwitch labelActiveOnly`), nicht etwas Neues.
    """
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    body = _body(diagram, "columnRows", kind="export function")
    # Der Palettenknoten wird **vor** dem Ende-Knoten eingeschoben – nicht danach und
    # nicht am Listenende, wo er hinter der Zielflagge stünde.
    assert "if (extra.tail && n.kind === 'end') rows.push" in body, (
        "Die Palette steht nicht unmittelbar vor dem Ende-Objekt."
    )
    designer = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    # ►►► **Die Bewegung ist geteilt, die Gestalt nicht** (Runde #877–#896). ◄◄◄
    # Sieben Testnotizen wollten genau diese Geste auch am Aktionsknopf – also steht sie
    # jetzt EINMAL (`.ix-tuck`), und die Palette ist ihre getönte Ausprägung. Geprüft
    # wird darum die **Regel**: die Palette ist ein Symbol-Knopf, der seinen Namen beim
    # Zeigen ausklappt – nicht, wie die Klasse dafür heisst.
    # ►►► **Gezählt, nicht gesucht.** ◄◄◄ Ein blosses «kommt vor» liesse seine eigene
    # Bug-Form durch: es gibt zwei Palettenknöpfe (Modul und Erfassungspunkt), also bliebe
    # der Name auch dann stehen, wenn einer von beiden ihn verliert.
    names = designer.count("ix-tuck-name")
    buttons = len(re.findall(r'className="ix-palette(?:"| )', designer))
    assert names and names == buttons, (
        f"Ein Palettenknopf hat keinen Namen zum Ausklappen ({buttons} Knöpfe, "
        f"{names} Namen)."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    assert ".ix-tuck-name" in css, "Der Hover-Name der Palette hat keine Darstellung."
    # **Die Geste ist geteilt, die Gestalt getrennt** (#900): `.ix-palette` trägt nur noch
    # Grösse und Radius – die Bewegung steht einmal in `.ix-tuck` und gilt auch für den
    # Aktionsknopf jeder Modul-Karte.
    assert "ix-tuck" in designer, (
        "Die Palette teilt die Geste nicht mehr – dann gibt es sie zweimal, und die "
        "zweite läuft beim nächsten Mal davon."
    )


def test_a_module_shows_its_own_matter_in_every_state():
    """**Ein Modul zeigt seine Sache in jedem Zustand** – nur die Aktionen hängen daran,
    ob es an der Reihe ist.

    Vorher hatte die Ausführungsstelle **zwei** Körper: aktiv das Formular, sonst eine
    hand-gepflegte **Aufzählung** dessen, was ein Modul tragen kann (Punkte, Umfang, Verb,
    Grund, Ziel). Diese Liste musste mit jedem neuen Modul-Fakt wachsen – und der
    Beschaffungs-Beleg stand nicht darin: ein abgeschlossenes Modul zeigte von ihm
    **nichts** (Testnotiz #749).

    Bug-Form: ``renderStep`` verzweigt wieder oben in zwei Körper.
    """
    src = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "renderStep: (step, isActive) => (isActive ?" not in src, (
        "Die Ausführungsstelle hat wieder zwei Körper – dann fehlt beim nächsten "
        "Modul-Fakt genau er im nicht-aktiven Zustand."
    )
    assert "const stepBody = (step: DiagramStep, isActive: boolean, internal: boolean)" in src, (
        "Es gibt keinen EINEN Modul-Körper mehr."
    )
    # ►► **Der Beleg steht ausserhalb der Verzweigung** – er gehört zum Modul, nicht zum
    #    Moment. Gefragt wird nach dem **gerenderten Baum**, nicht nach der Reihenfolge im
    #    Quelltext: die erste Fassung verglich die Position von `<Wrapped` mit der von
    #    `{isActive ?` über den ganzen Rumpf und prüfte damit die **Form** der damaligen
    #    Lösung. Wer die Aktiv-Verzweigung in eine eigene Konstante zieht (und den Beleg
    #    damit *noch* eindeutiger davor stellt), liess sie anschlagen, obwohl die Regel
    #    besser erfüllt ist als vorher. Gemessen, nachgeschärft, gegengeprüft.
    body = src[src.index("const stepBody ="):src.index("// **Ohne Prozessbild")]
    tree = body[body.index("return ("):]
    assert "<BelegWork" in tree, "Der Vorgang steht nicht mehr im gerenderten Baum."
    ahead = tree[:tree.index("<BelegWork")]
    assert "isActive ?" not in ahead and "isActive &&" not in ahead, (
        "Der Vorgang steht wieder innerhalb der Aktiv-Verzweigung – dann zeigt ein "
        "abgeschlossenes Modul von ihm nichts."
    )

    # **Und eine Stufe zeigt ihren Inhalt, sobald sie dran ODER vorbei ist** – sonst
    # steht am abgeschlossenen Modul nichts mehr, obwohl genau dort steht, was passiert
    # ist. Die Karte selbst bekommt `active` durchgereicht und entscheidet damit allein
    # über das **Handeln**.
    panel = _beleg()
    assert "function may(d: Filled, action: string)" in panel, (
        "Die Karte fragt nicht mehr an EINER Stelle, ob gehandelt werden darf."
    )


def test_a_supplier_sees_his_module_without_the_process_picture():
    """**Die Lieferanten-Sicht ist eine Spiegelung** (Testnotiz #747).

    Der Server verengt die Antwort (``orders._to_response``); die Oberfläche zeichnet
    darum **dieselbe** Modul-Karte, nur ohne Achse. Ein Nachbau wäre eine zweite
    Darstellung desselben Moduls.
    """
    src = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "StepCard" in src and "stepBody(step" in src, (
        "Die Modul-Karte wird nachgebaut statt wiederverwendet."
    )
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "export function StepCard(" in diagram


def test_an_unknown_module_looks_unknown_not_like_another_one():
    """**Unbekanntes borgt sich kein fremdes Symbol** – dieselbe Regel wie bei der Farbe.

    Ein Browser-Stand, der älter ist als das Backend, ist nach **jedem** Deploy mit einem
    neuen Modultyp der Normalfall. Der Ton sagt dann längst «kaputt» (``UNKNOWN_TONE``),
    das Symbol log: es gab **drei** Rückfälle, und jeder zeigte ein anderes echtes Modul –
    ``Blocks`` den **Verbrauch**, ``PackageX`` das **Aussondern**, ``CAPTURE_ICON.text``
    den Erfassungspunkt «Text», also ein schlichtes **T** (genau das gemeldete Symbol).

    Bug-Form: ein Aufrufer liest ``MODULE_ICON`` selbst und hängt ein ``??`` daran.
    """
    lib = _read(FRONTEND / "lib" / "modules.ts")
    assert "export function moduleIcon" in lib, (
        "Die Auflösung des Symbols steht nicht an einer Stelle."
    )
    assert "?? CircleHelp" in lib, (
        "Der Rückfall zeigt kein Fragezeichen – ein unbekanntes Modul gibt sich damit "
        "als ein bekanntes aus."
    )
    for name in ("process-diagram.tsx", "process-designer.tsx", "order-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "MODULE_ICON[" not in src, (
            f"{name} greift am ``moduleIcon`` vorbei in die Tabelle – und wählt damit "
            f"seinen eigenen Rückfall."
        )


def test_everything_captured_is_mandatory():
    """**Das Feld «Pflicht ja/nein» ist gelöscht** – Modell, Migration, UI, Validierung.

    Ein Schalter dafür wäre die Frage, warum man einen Erfassungspunkt anlegt, den
    niemand ausfüllen muss; und jeder ausgeschaltete Punkt eine Lücke, die erst später
    auffällt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.process import CapturePoint, ModuleInput

    assert "required" not in CapturePoint.model_fields
    # Und die Eingabe kennt gar keine Feldliste mehr: was in einer Konfiguration
    # stehen darf, entscheidet der **Modultyp** (``Module.clean_config``) – eine
    # zweite Liste im Schema verwarf stillschweigend, was sie nicht kannte.
    assert ModuleInput.model_fields["config"].annotation is not None
    # Geprüft wird JEDER Punkt, nicht eine Teilmenge.
    check = _body(_read(BACKEND / "app" / "domain" / "capture_types" / "__init__.py"),
                  "check_values")
    assert "required" not in check, "Die Prüfung fragt wieder nach einem Pflicht-Schalter."
    # Der Code, nicht die Kommentare: die erklären ja gerade, warum es ihn nicht gibt.
    for name in ("lib/modules.ts", "components/erp/process-designer.tsx",
                 "components/erp/capture-form.tsx"):
        code = re.sub(r"/\*.*?\*/|//.*", "", _read(FRONTEND / name), flags=re.S)
        assert "required" not in code, f"{name} kennt wieder einen Pflicht-Schalter."


def test_modules_are_reordered_by_dragging_not_by_a_second_form():
    """Die Reihenfolge **ist** der Prozess – also wird sie im Bild geändert.

    Gezogen wird am **Griff**, nicht an der Karte: ein `draggable` auf der ganzen Karte
    macht ihren Inhalt zum Ziehgriff, und in ihren Eingabefeldern liesse sich kein Text
    mehr markieren. Das fällt bei einem Modul kaum auf und bei zwanzig sofort.
    """
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    card = _body(diagram, "StepCard", kind="function")
    assert "onDragStart" in card and "onDrop" in card
    grip = card[card.index("GripVertical") - 800:card.index("GripVertical")]
    assert "draggable" in grip, (
        "Gezogen wird nicht am Griff – dann lässt sich in den Feldern kein Text markieren."
    )
    assert "draggable={!!drag}" not in card, "Die ganze Karte ist wieder ziehbar."

    designer = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    assert "splice" in _body(designer, "move", kind="function"), "Das Umsortieren fehlt."

    # Und die Linien folgen: sie werden nach JEDEM Commit neu gemessen, nicht nur bei
    # einer Grössenänderung – ein Modul kann wandern, ohne seine Grösse zu ändern.
    flow = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    assert "useIsoLayout(() => { measure(); });" in flow, (
        "Die Prozesslinien werden nach einem Umsortieren nicht neu gemessen."
    )


def test_the_instance_points_at_its_article_instead_of_copying_it():
    """**Woher stammt diese Gruppe?** Ein Verweis auf den Artikel – mehr nicht (#676).

    Die frühere Merkmale-Karte schrieb Name, Nummer, Typ und Menge ab. Name und Nummer
    stehen am Artikel, aktuell und an einer Stelle; die Menge eine Zeile weiter unten.
    Eine Kopie daneben ist zusätzlicher Pflegeaufwand für dieselbe Auskunft – und beim
    ersten umbenannten Artikel wäre sie falsch.
    """
    detail = _read(FRONTEND / "components" / "erp" / "instance-detail.tsx")
    # Der Code, nicht die Kommentare – die erklären ja gerade, warum es sie nicht gibt.
    code = re.sub(r"\{/\*.*?\*/\}|/\*.*?\*/|//.*", "", detail, flags=re.S)
    assert 'title="Merkmale"' not in code, "Die Merkmale-Karte ist wieder da."
    assert "<ObjId value={rec.article_object_id}" in detail, (
        "Der Artikel ist nicht verlinkt – dann bleibt die Herkunft eine Behauptung."
    )


def test_there_is_nothing_to_do_at_an_instance():
    """Am Instanz-Detail wird **gelesen**, nicht gearbeitet.

    Erzeugt wird über einen Auftrag (#678), gelöscht wird nie (#679), und erfasst wird
    am Modul (#677). Bliebe hier ein Knopf, wäre er entweder eine zweite Tür oder eine
    Schaltfläche, die nichts tut.
    """
    detail = _read(FRONTEND / "components" / "erp" / "instance-detail.tsx")
    for gone in ("addUnits", "removeUnit", "CapturePanel", "Trash2", "Datenerfassung"):
        assert gone not in detail, f"«{gone}» steht wieder am Instanz-Detail."
    assert "<button" not in detail, "Am Instanz-Detail gibt es wieder etwas zu drücken."


def test_a_piece_number_is_written_the_same_way_everywhere():
    """**Der Suffix ist überall leise** (#681) – und überall gleich.

    Die Identität, die ein Mensch kennt, ist die Objektnummer; der Suffix sagt nur,
    welches Stück davon gemeint ist. Beide gleich laut zu setzen macht aus einer Nummer
    zwei, und in einer Liste springt dann jede Zeile an, obwohl sich nur die letzte
    Stelle unterscheidet.
    """
    comp = _read(FRONTEND / "components" / "erp" / "unit-number.tsx")
    assert "lastIndexOf('-')" in comp, "Der Suffix wird nicht mehr abgetrennt."
    assert "var(--fg-4)" in comp, "Der Suffix ist nicht mehr leiser als die Nummer."

    # Und **niemand** schreibt sie selbst hin: eine roh ausgegebene Stück-Nummer wäre
    # genau die Stelle, an der der Suffix wieder mitruft.
    # Gemeint ist die **Ausgabe** als JSX-Kind, nicht die Weitergabe als Attribut:
    # ``key={o.number}`` und ``value={o.number}`` sind genau richtig so.
    attr = re.compile(r"\b(?:key|value|number)=\{[^}]*\}")
    raw = re.compile(r">\s*\{[a-z]\w*\.(?:unit_)?number\}")
    for f in sorted((FRONTEND / "components").rglob("*.tsx")):
        hits = raw.findall(attr.sub("", _read(f)))
        assert not hits, (
            f"{f.name} gibt eine Stück-Nummer roh aus ({', '.join(hits)}) – "
            f"sie gehört durch <UnitNumber>."
        )
    # Mehrere Stellen zeigen sie – alle über dasselbe Bauteil. (Die History-Box war eine
    # davon und ist entfallen (§5); die Historie steht jetzt am Prozessobjekt.)
    users = [f.name for f in (FRONTEND / "components").rglob("*.tsx")
             if "<UnitNumber" in _read(f)]
    assert len(users) >= 3, f"Nur {users} nutzen das gemeinsame Bauteil."
    # **Und sie führt zu ihrem Datensatz** (Auftrag §3) – über die bestehende Navigation,
    # nicht über einen eigenen Weg.
    comp_nav = _read(FRONTEND / "components" / "erp" / "unit-number.tsx")
    assert "useErpNav" in comp_nav and "nav(objectId)" in comp_nav, (
        "Die Stück-Nummer führt nicht mehr zu ihrer Einzelinstanz."
    )


# ---------------------------------------------------------------------------
# Die Journey der Einzelinstanz (Teil A)
# ---------------------------------------------------------------------------


def test_the_journey_is_derived_never_maintained():
    """**Abgeleitet, nicht gepflegt** – die harte Vorgabe an die Journey.

    Zeiger-Felder (``vorheriger_auftrag`` / ``naechster_auftrag``) müssten bei jeder
    Freigabe mitgeschrieben werden und liefen irgendwann auseinander. Dann wäre die
    Journey für genau das unbrauchbar, was sie beweisen soll. Die Quelle ist darum die,
    die es ohnehin gibt: der append-only Ereignis-Log.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import Order

    for forbidden in ("previous_order_id", "next_order_id", "prev_order_id"):
        assert forbidden not in Order.__table__.columns, (
            f"«{forbidden}» ist ein gepflegter Zeiger – die Journey wird abgeleitet."
        )
    svc = _read(BACKEND / "app" / "services" / "journey.py")
    assert "ProcessEvent" in svc, "Die Journey liest nicht den Ereignis-Log."
    # Kein zweiter Datenbestand: gelesen wird, geschrieben nicht.
    for write in ("db.add(", "insert(", "update(", "db.commit("):
        assert write not in svc, f"Die Journey schreibt («{write}») – sie soll nur lesen."


def test_the_journey_scales_by_grouping_not_by_listing():
    """Bei 5000 Stück werden **Nachbarn gezählt**, nicht 5000 Verweise gerendert.

    Zwei Abfragen je Auftrag, unabhängig von der Stückzahl – kein N+1. Und die Antwort
    ist eine Liste je Nachbar-Auftrag mit Anzahl, keine Liste je Stück.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.order import JourneyNeighbour

    assert set(JourneyNeighbour.model_fields) == {"object_id", "name", "unit_count"}, (
        "Der Nachbar trägt etwas anderes als Objektnummer, Name und Anzahl."
    )
    svc = _read(BACKEND / "app" / "services" / "journey.py")
    assert "func.count()" in svc and "group_by" in svc, "Es wird nicht gruppiert."
    assert "for " not in _body(svc, "_neighbour_counts").split("return")[0], (
        "Die Nachbarn werden je Stück einzeln geholt – das ist ein N+1."
    )
    # Der Index, der den Sprung an die Nachbarzeile trägt.
    mig = _read(BACKEND / "alembic" / "versions" / "161_baseline.sql")
    assert "ix_process_events_unit_timeline" in mig, "Der Journey-Index fehlt im Schema."


def test_no_neighbour_means_nothing_shown():
    """Kein Vorgänger/Nachfolger → **nichts**, kein Platzhalter mit Fantasiedaten."""
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    body = _body(diagram, "columnRows", kind="export function")
    pushes = re.findall(r"^\s*(if \(extra\.journey\w+\) rows\.push.*)$", body, re.M)
    assert len(pushes) == 2, f"Erwartet zwei Journey-Zeilen, gefunden {len(pushes)}."
    cols = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")
    # Die Bedingung hat **einen** Ort (`hasJourney`), seit die Zeile auch die hier
    # entstandenen Stücke trägt (§6). Sie bleibt eine Bedingung: leer heisst leer.
    assert "hasJourney(inStops, origins)" in cols, (
        "Die Journey-Zeile entsteht unbedingt – bei leerer Liste stünde eine leere Zeile."
    )
    assert "stops.length > 0 || origins.length > 0" in diagram, (
        "«Gibt es die Zeile» ist keine Bedingung mehr, sondern eine Behauptung."
    )
    assert "useErpNav" in diagram, (
        "Der Verweis ist nicht anklickbar – oder er benutzt eine zweite Navigation."
    )


# ---------------------------------------------------------------------------
# #682 / #687 – die ID ist die Identität, der Typ der Name
# ---------------------------------------------------------------------------


def test_a_module_is_identified_by_its_id_and_named_by_its_type():
    """**Kein Modulname** – weder als Feld noch als Identität.

    Der Name war immer «Datenerfassung» und trotzdem Pflicht (#682); als *Identität*
    taugte er nie (#687): ein Name lässt sich ändern, doppelt vergeben oder leer lassen,
    und dann zeigt die Historie auf etwas, das es so nie gab.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import ArticleProcessStep, ProcessStep
    from app.schemas.process import ModuleInput

    for model in (ProcessStep, ArticleProcessStep):
        assert "name" not in model.__table__.columns, (
            f"{model.__name__} trägt wieder einen Namen."
        )
    assert "name" not in ModuleInput.model_fields, "Der Entwurf schickt wieder einen Namen."

    # Beschriftet wird aus der Registry – an EINER Stelle.
    from app.domain import modules
    assert modules.label(modules.DATENERFASSUNG) == "Datenerfassung"
    assert modules.label("gibtsnicht") == "gibtsnicht", (
        "Ein unbekannter Typ wird schöngefärbt statt gemeldet."
    )


def test_the_history_points_at_the_id_not_at_a_name():
    """Die Historie referenziert **ausschliesslich die ID** – nie den Namen, nie die
    Position. Die Beschriftung daneben kommt aus dem Modultyp."""
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import ProcessEvent

    assert "step_id" in ProcessEvent.__table__.columns
    for forbidden in ("step_name", "module_name", "position"):
        assert forbidden not in ProcessEvent.__table__.columns, (
            f"Der Log trägt «{forbidden}» – er soll auf die ID zeigen."
        )
    # Die Historie steht seit §5 **am Prozessobjekt** statt in einer Box darunter – die
    # Regel ist dieselbe: aufgelöst wird über die ID.
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    log = _body(diagram, "historyTip", kind="export function")
    assert "e.step_id === node.at" in log, (
        "Die Historie löst den Schritt nicht über seine ID auf."
    )
    assert "s.name" not in log, "Die Historie beschriftet wieder über einen Namen."
    assert "EventLog" not in _read(FRONTEND / "components" / "erp" / "order-detail.tsx"), (
        "Die History-Box ist zurück – sie sollte am Objekt stehen, nicht darunter."
    )


# ---------------------------------------------------------------------------
# #683 / #684 / #686 / #688
# ---------------------------------------------------------------------------


def test_the_capture_type_is_chosen_once():
    """Die Art eines Erfassungspunktes wird über die **Palette** gewählt – nicht daneben
    noch einmal über ein Auswahlfeld. Zwei Wege zur selben Entscheidung sind einer zu
    viel (#683); gezeigt wird sie als Symbol der Zeile."""
    src = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    # ►►► **Gefragt ist DIESER Feldsatz, nicht die ganze Datei.** ◄◄◄
    #
    # Die Regel lautet «die Art eines Erfassungspunktes wird über die Palette gewählt» –
    # sie sagt nichts über Auswahlfelder anderswo. Ein Verbot über die **ganze Datei**
    # prüfte die Form der damaligen Lösung und verbot damit jedes künftige `<select>`
    # über einer echten Aufzählung; genau daran schlug er an, als der Steuersatz
    # dazukam (eine endliche Liste, kein Datensatz – die Hausregel erlaubt sie
    # ausdrücklich).
    fields = _component(src, "ModuleFields")
    assert "<select" not in _code(fields), "Der Erfassungstyp hat wieder ein Auswahlfeld."
    assert "PointIcon" in src, "Die Art der Zeile ist nicht mehr erkennbar."
    assert "ix-palette-sm" in src, "Die Palette, die die Art wählt, fehlt."


def test_the_process_picture_brings_its_own_width():
    """Der Prozess sieht am Artikel **genau so aus** wie im Auftrag (#684).

    Es war schon EINE Komponente – aber der Artikel stellte sie in einen 880-px-Container
    und der Auftrag in einen 620er. Eine visuelle Abweichung ist der Beweis, dass irgendwo
    zwei Stände sind; hier war es nicht die Komponente, sondern das Mass. Also bringt sie
    es selbst mit.
    """
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "export const PROCESS_MAXW" in diagram, "Das Prozessbild hat keine eigene Breite."
    # Das Mass wird dort angewandt, wo der Rahmen entsteht – und den gibt es genau einmal.
    assert "maxWidth: PROCESS_MAXW" in _read(
        FRONTEND / "components" / "erp" / "process-columns.tsx")
    # Das Mass kommt aus den Spurmassen (`process-flow.LANE`) – dort steht jede Breite,
    # die dieses Bild kennt, und nur dort.
    assert "export const PROCESS_MAXW = LANE.MID_MAX" in diagram, (
        "PROCESS_MAXW ist wieder eine eigene Zahl neben den Spurmassen."
    )
    flow = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    width = re.search(r"\n  MID_MAX: (\d+)", flow)
    assert width, "LANE.MID_MAX ist keine Zahl."
    _PROCESS_MAXW = int(width.group(1))
    for name in ("article-detail.tsx", "order-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "ProcessDesigner" in src or "ProcessColumns" in src
        assert "function StepCard" not in src, f"{name} baut die Modul-Karte nach."
        # **Das Mass steht nur an EINER Stelle.** Wer die Zahl abschreibt, hat wieder
        # zwei Stände – genau die Lage, aus der der gemeldete Unterschied entstand.
        assert str(_PROCESS_MAXW) not in src, (
            f"{name} schreibt die Prozessbreite ab, statt PROCESS_MAXW zu lesen."
        )


def test_a_validation_error_says_what_is_missing_and_where():
    """Rohe Validator-Texte gehören nicht ins UI (#686).

    «String should have at least 1 character» ist wahr und trotzdem unbrauchbar: kein
    Feld, kein Ort. Der Handler steht an **einer** Stelle statt als Übersetzung an jedem
    Endpunkt.
    """
    main = _read(BACKEND / "app" / "main.py")
    assert "@app.exception_handler(RequestValidationError)" in main, (
        "Eingabefehler laufen wieder in FastAPIs Vorgabe – rohe Validator-Texte im UI."
    )
    body = _body(main, "validation_error_handler")
    assert "_field_path" in body, "Die Meldung nennt nicht, WO der Fehler steckt."
    assert "_VALIDATION_TEXTS" in body, "Die Meldung nennt nicht in Klartext, WAS fehlt."


def test_the_feed_learns_about_every_write_from_one_place():
    """Feed und Detail lesen **dieselbe** Ableitung – der Feed hatte nur einen alten
    Stand (#688), und eine frische Instanz erschien erst nach Reload (#685).

    Gemeldet wird das an genau einer Stelle: jede Anfrage, die kein GET ist. Ein
    Aufrufer kann es damit nicht vergessen, und ein zweiter Melde-Weg kann nicht
    entstehen.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import order_state

    # Eine Quelle: der Feed leitet ab wie das Detail.
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "order_state.order_statuses" in router and "order_state.order_status" in router
    assert hasattr(order_state, "order_statuses")

    api = _read(FRONTEND / "lib" / "api.ts")
    assert "function notifyDataChanged" in api, "Die Meldestelle fehlt."
    assert re.search(r"if \(!idempotent\) \{?[^}\n]*\bnotifyDataChanged\(path\);", api), (
        "Nicht jede schreibende Anfrage meldet – dann bleibt der Feed irgendwann stehen."
    )
    # **Gehört wird an EINER Stelle** (`lib/use-feed.ts`), und invalidiert wird, was der Pfad
    # betrifft. Die Listen des Feeds sind Queries – ein eigener `useState` je Liste daneben
    # wäre die zweite Datenquelle, die nach einem Schreibvorgang stehen bleibt.
    hook = _read(FRONTEND / "lib" / "use-feed.ts")
    assert "feedsTouchedBy(path)" in hook and "invalidateQueries" in hook, (
        "Der Feed hört nicht auf die Meldung – oder lädt ohne Blick auf den Pfad."
    )
    assert "detail: { path }" in api, "Die Meldung nennt den Pfad nicht."
    feed = _read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx")
    assert "inexxio:data-changed" not in feed and "DATA_CHANGED" not in feed, (
        "Der Feed hört selbst auf die Meldung – das ist der zweite Weg."
    )
    for kind in ("UserProfile", "Article", "OrderSummary", "InstanceSummary",
                 "CompanySettings", "DocumentSummary"):
        assert f"useState<{kind}[]>" not in feed, (
            f"Die Liste «{kind}» lebt neben React Query in einem eigenen Zustand."
        )
    # Und kein zweiter Melde-Weg in den Detailfenstern.
    for name in ("order-detail.tsx", "article-detail.tsx", "instance-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "inexxio:data-changed" not in src, (
            f"{name} meldet selbst – das ist der zweite Weg."
        )


# ---------------------------------------------------------------------------
# Abweichungsaufträge
# ---------------------------------------------------------------------------


def test_a_deviation_order_is_a_regular_order():
    """Es gibt **keinen** Auftragstyp «Abweichung» (§2).

    Kein zweites Modell, kein zweiter Endpunkt, kein ``if abweichung:`` in der
    Auftragslogik. Was es gibt, ist eine **Auskunft** über einen ganz gewöhnlichen
    Auftrag – abgeleitet aus dem Ereignis-Log.
    """
    models = (BACKEND / "app" / "models").glob("*.py")
    assert not [m for m in models if "deviation" in m.name or "abweichung" in m.name], (
        "Es gibt ein eigenes Modell für Abweichungen – dann ist es ein zweiter Typ."
    )
    order = _read(BACKEND / "app" / "models" / "order.py")
    for forbidden in ("is_deviation", "deviation", "parent_order_id"):
        assert forbidden not in order, (
            f"``orders`` trägt «{forbidden}» – die Abweichung ist ein Feld geworden."
        )
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "/deviation" not in router, "Es gibt einen eigenen Endpunkt für Abweichungen."

    # Und das Label wird aus dem **Log** abgeleitet: der Start-Eintrag sagt, in welchem
    # Zustand das Stück gegriffen wurde.
    proc = _read(BACKEND / "app" / "services" / "order_state.py")
    body = _body(proc, "deviation_flags")
    assert "ProcessEvent" in body and "KIND_START" in body, (
        "«Abweichung» kommt nicht aus dem Log – dann ist es irgendwo gespeichert."
    )

    # **Und die Regel nennt keinen einzelnen Status.** Sie vergleicht gegen den EINEN
    # Regelstart (``START_BEFORE``): alles, was anders beginnt, ist ein Zugriff auf
    # Material, das nicht regulär verfügbar war – und genau das ist auszuweisen. Stünde
    # hier ein Status, wäre die Frage «ist das eine Abweichung?» eine Liste, die beim
    # nächsten Zustand jemand nachziehen muss; ein vergessener Eintrag hiesse: kein
    # Nachweis, und zwar stillschweigend.
    assert "START_BEFORE" in body, (
        "Die Abweichungsregel vergleicht nicht mit dem Regelstart."
    )
    for named in ("IM_PROZESS", "GESPERRT", "VERSCHROTTET"):
        assert named not in body, (
            f"Die Abweichungsregel nennt «{named}» – damit ist sie wieder eine Liste."
        )


def test_the_return_belongs_to_the_connection_not_to_the_order():
    """Die Rückführung hängt an der **Verbindung** zwischen zwei Aufträgen (§6).

    Nur dadurch funktionieren Schachtelung und Parallelität ohne Zusatzregel: jedes
    ausgeliehene Stück trägt seine eigene Antwort.
    """
    unit = _read(BACKEND / "app" / "models" / "order_unit.py")
    assert "return_to_order_id" in unit, "Die Verbindung hat keinen Ort."
    order = _read(BACKEND / "app" / "models" / "order.py")
    assert "return_to" not in order and "returns" not in order, (
        "Die Rückführung steht am Auftrag – dann gilt sie für alle seine Stücke gleich."
    )
    # Und «wartet auf» wird gezählt, nicht gespeichert.
    proc = _read(BACKEND / "app" / "services" / "order_state.py")
    assert "def waiting_counts(" in proc
    assert "waiting_for_return" not in _read(BACKEND / "app" / "models" / "order.py"), (
        "Am Auftrag steht ein Wartezähler – den vergisst irgendwann jemand zu senken."
    )


def test_the_return_position_needs_no_field_of_its_own():
    """Die Rückkehrposition steht schon da: ``current_step_id`` der ausgescherten Zeile.

    Sie wird beim Ausscheren **nicht** angetastet – «wo steht dieses Stück» ist genau die
    Frage, die diese Spalte beantwortet, und beim Ausscheren steht es eben noch dort.
    Ein zweites Feld dafür wäre eine Kopie, die auseinanderlaufen kann.
    """
    unit = _read(BACKEND / "app" / "models" / "order_unit.py")
    for forbidden in ("return_step_id", "return_position", "resume_step_id"):
        assert forbidden not in unit, f"«{forbidden}» ist ein zweites Feld für die Position."
    proc = _read(BACKEND / "app" / "services" / "release.py") + _read(BACKEND / "app" / "services" / "process.py")
    hand = _body(proc, "_hand_over")
    # **Gefragt ist, ob geSCHRIEBEN wird** – geprüft wird darum jede einzelne
    # ``values(…)``-Zuweisung, nicht «alles nach der letzten». Die grobe Form meldete
    # jedes spätere *Lesen* der Spalte mit; ein Wächter, der bei richtigem Code
    # anschlägt, wird stillgelegt statt verstanden.
    for call in hand.split(".values(")[1:]:
        assigned = call[: call.index(")")]
        assert "current_step_id" not in assigned, (
            "Das Ausscheren setzt die Position zurück – dann ist die Rückkehr geraten."
        )
    home = _body(proc, "_return_home")
    assert "released_at=None" in home, "Die Rückkehr öffnet die alte Zeile nicht wieder."


def test_the_neighbours_are_drawn_with_the_same_component():
    """Die Spalten daneben zeigen den **echten** Ablauf – dieselbe Komponente (§4).

    Eine Zusammenfassung oder ein Symbol wäre eine zweite Darstellungsform für dieselbe
    Sache, und die läuft irgendwann von der ersten weg.
    """
    flow = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")
    assert "FlowColumn" in flow, "Die Nachbarn werden nicht mit der Prozess-Komponente gezeichnet."
    assert "faded" in flow, "Die Nachbarn heben sich nicht ab – der Fokus geht verloren."
    # Ein Rahmen für alle Spalten: sonst gäbe es keine gemeinsame Linie.
    assert flow.count("<FlowFrame") == 1, (
        "Mehrere Rahmen – dann haben die Spalten verschiedene Nullpunkte und die "
        "Verbindungslinie lässt sich nicht zeichnen."
    )
    assert "function Cross(" in flow, "Es gibt keine Linie zwischen den Spalten."
    # **Eine** Stelle für beide Richtungen: hinaus in eine Abweichung und herein aus dem
    # übergeordneten Auftrag sind dieselbe Verbindung, von zwei Seiten gelesen. Zwei
    # Zeichenfunktionen dafür waren zwei Geometrien, die auseinanderlaufen konnten.
    assert "function Inflow(" not in flow and "function Detour(" not in flow, (
        "Die Querverbindung wird wieder an zwei Stellen gezeichnet."
    )
    # Und der Server liefert dafür dieselben Felder wie für die Mitte.
    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    related = schema.split("class RelatedOrder")[1].split("class ")[0]
    for field in ("steps", "flow", "active_step_id"):
        assert field in related, f"«{field}» fehlt – der Nachbar kann nicht gerendert werden."


def test_many_deviations_are_cut_off_and_say_so():
    """Bei vielen Abweichungen wird **abgeschnitten und die Zahl genannt** (§4).

    Gruppieren wäre hier falsch: zwei Abweichungen sind zwei verschiedene Abläufe, eine
    Gruppe daraus sagte nichts. Eine stumm gekappte Liste sähe aus wie alles.
    """
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "RELATED_LIMIT" in router, "Es gibt keine Grenze – die Antwort wächst unbegrenzt."
    assert '"deviation_total": len(branches)' in router, (
        "Die wahre Zahl wird nicht mitgeliefert – die gekappte Liste sähe aus wie alles."
    )
    flow = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")
    assert "deviationTotal" in flow and "function Rest(" in flow, (
        "Die Oberfläche verschweigt, dass abgeschnitten wurde."
    )
    assert "deviation_total" in _read(FRONTEND / "components" / "erp" / "order-detail.tsx"), (
        "Die wahre Zahl kommt gar nicht erst im Bild an."
    )


def test_leaving_a_module_is_a_question_of_the_module_type():
    """►►► Die offene Frage (§5) hat **genau eine** Stelle im Code ◄◄◄

    Ob ein Stück ein Modul verlassen darf, hängt am Modultyp – eine globale Regel wäre
    für die reversible Datenerfassung zu streng und für einen künftigen Einkauf zu lasch.
    """
    reg = _read(BACKEND / "app" / "domain" / "modules.py")
    assert "units_may_leave" in reg, "Die Eigenschaft fehlt – dann ist die Regel global."
    proc = _read(BACKEND / "app" / "services" / "release.py") + _read(BACKEND / "app" / "services" / "process.py")
    assert "def _assert_may_leave(" in proc
    # Gelesen wird sie in **einer** Funktion – sonst gäbe es zwei Antworten auf dieselbe
    # Frage, und die eine würde beim Ändern vergessen.
    readers = [name for name in ("_assert_may_leave", "release", "confirm_step", "_hand_over")
               if "units_may_leave" in _body(proc, name)]
    assert readers == ["_assert_may_leave"], f"Gelesen in: {readers}"
    # Und die vorläufig strengere Variante steht im Fenster, wo sie allein stehen kann.
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "deviateBlocked" in detail and "entryStarted" in detail, (
        "Eine begonnene Erfassung sperrt den Auslöser nicht – das ist die lockerere "
        "Variante, und entschieden ist noch nichts."
    )


def test_the_trigger_sits_where_the_piece_stands():
    """Der Auslöser sitzt **am Stück, an seiner Stelle im Prozess** (§3.1).

    Und er legt nichts an: er öffnet einen ganz gewöhnlichen Auftragsentwurf, in dem das
    Stück schon steht. Eine eigene «Abweichung anlegen»-Aktion wäre ein zweiter
    Anlage-Weg.
    """
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "onDeviate" in diagram, "Am Stück gibt es keinen Auslöser."
    assert "function StateRow(" in diagram
    page = _read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx")
    assert "OrderSeed" in page and "startCreate('order', seed)" in page, (
        "Der Auslöser führt nicht in den gewöhnlichen Entwurf."
    )
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "api.createOrder" in detail and detail.count("api.createOrder") == 1, (
        "Es gibt mehr als einen Anlage-Weg."
    )


# ---------------------------------------------------------------------------
# Testrunde 7.8.2026 nachmittags (#689–#700)
# ---------------------------------------------------------------------------


def test_a_branch_hangs_on_a_state_point_not_on_a_module():
    """**#700 — die Abzweigung sitzt VOR dem Modul, an einem Zustandspunkt.**

    Ein Stück kann nur abweichen, solange am Modul noch nichts eingegeben wurde: es hat
    das Modul gar nicht betreten. Die Linie geht darum von der **Stelle auf der
    Prozesslinie** ab, an der es wartete – und führt an denselben Punkt zurück, sodass es
    das Modul danach regulär durchläuft.

    Ein Zustandspunkt heisst «vor Modul X»; darum ist sein Anker **berechenbar**
    (``statePointId``) und muss nirgends gesucht werden. Der frühere Rückfall auf das
    Modul («gibt es den Zustandsknoten nicht, nimm das Modul») war genau der gemeldete
    Fehler – und er ist ersatzlos weg: den Punkt gibt es immer, wo eine Abzweigung ansetzt.
    """
    # **Der Abzweigepunkt ist ein eigener Knoten** – und der Rückführpunkt auch. Solange
    # es einer war, standen das gebliebene und das zurückgekehrte Stück an derselben
    # Stelle im Bild, und man sah der Zeichnung die Runde nicht an.
    svc = _read(BACKEND / "app" / "services" / "flow.py")
    assert 'NODE_FORK = "fork"' in svc and 'NODE_JOIN = "join"' in svc, (
        "Abzweige- und Rückführpunkt sind keine Knoten – dann gibt es die Stelle nicht, "
        "an der die Linie ansetzt."
    )
    assert "def fork_id(" in svc and "def join_id(" in svc, (
        "Die Kennung des Punktes wird nicht berechnet – beim Suchen war das Modul der "
        "Rückfall, und genau das war der gemeldete Fehler."
    )

    cols = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")
    assert "resolveAnchor" not in cols, (
        "Der Anker wird gesucht statt berechnet – und beim Suchen war das Modul der Rückfall."
    )
    # **Und der Nachbar spannt von der Zeile seines fork bis zu der seines join.** Nur
    # dadurch bleibt die Verbindung kurz: die Zeilen wachsen auf seine Höhe, die
    # Hauptachse wächst mit, und es entsteht das Bild, das die Sache ist – Teilung, zwei
    # Wege, Zusammenfluss.
    assert "rowOfNode(mid.rows," in cols and "e.kind === 'out' ? e.frm : e.to" in cols, (
        "Der Nachbar steht nicht in den Zeilen seiner Punkte – dann muss die Linie "
        "wieder quer über das halbe Bild laufen."
    )
    assert "gridRow: `${b.from + 1} / ${b.to + 2}`" in cols, (
        "Die Zeilenspanne wird nicht auf das Raster gelegt."
    )

    # Serverseitig: je Zustandspunkt eine Zeile, nicht ein geratenes Minimum.
    svc = _read(BACKEND / "app" / "services" / "journey.py")
    assert "func.min(sub.c.step_id)" not in svc, (
        "Die Punkte werden zu einem zusammengefasst – dann zeigt die Linie auf eine "
        "Stelle, an der nichts passiert ist."
    )
    assert "group_by(sub.c.oid, sub.c.step_id)" in svc, "Es wird nicht je Punkt gezählt."
    # Der Graph zählt **je Punkt UND Nachbar**: derselbe Auftrag kann an zwei Stellen
    # zugegriffen haben. Ein Einzelwert hätte sich für eine entschieden und die andere
    # verschwiegen – und die Linie zeigte dann auf eine Stelle, an der nichts passiert ist.
    flow = _read(BACKEND / "app" / "services" / "flow.py")
    assert "out: dict[tuple[Optional[int], int], int]" in flow, (
        "Die Abzweigungen werden nicht je Zustandspunkt und Ziel gezählt."
    )
    assert 'f"out:{at}:{t}"' in flow and 'f"back:{at}:{t}"' in flow, (
        "Eine Querverbindung nennt ihren Punkt nicht – dann ist sie nicht verortbar."
    )
    # **Und je Nachbar ein eigenes Paar.** Ein gemeinsamer Rückführpunkt liegt unter
    # dem letzten Nachbarn – der Rückweg des ersten müsste an allen folgenden vorbei.
    assert 'f"fork:{at if at is not None else \'end\'}:{target}"' in flow, (
        "Abzweigepunkte werden wieder je Zustandspunkt vergeben statt je Nachbar."
    )
    assert "def _branches(" in flow and "targets = _targets_at(" in flow, (
        "Die Auffaltung in ein Paar je Nachbar fehlt."
    )
    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    assert "class BranchPoint(" not in schema, (
        "Der Zustandspunkt steht wieder neben dem Graph statt in ihm – zwei Wahrheiten "
        "darüber, wo eine Abzweigung ansetzt."
    )
    assert "origin_step_id" not in schema, "Der Einzelwert steht noch da."


def test_a_module_is_told_whether_it_may_run():
    """**#698 — die Sperre steht zentral, nicht im Modul.**

    Ein Modul fragt nicht, ob es darf; ihm wird gesagt, dass es nicht darf. Darum steht
    die Regel an dem EINEN Mechanismus, den jedes Modul auslöst (``confirm_step``), und
    in der EINEN Karte, die jedes Modul rendert (``StepCard``). Ein künftiger Einkauf
    oder Verkauf erbt beides, ohne eine Zeile dafür zu schreiben.

    **Durchgesetzt wird serverseitig** – eine deaktivierte Oberfläche ist keine
    Absicherung. Der Inhalt bleibt sichtbar, nur bedienen lässt er sich nicht.
    """
    proc = _read(BACKEND / "app" / "services" / "process.py") + _read(BACKEND / "app" / "services" / "order_state.py")
    assert "def pending_returns(" in proc, "Es gibt keine Ableitung, worauf ein Modul wartet."
    assert "_ready_at(" in _body(proc, "confirm_step")
    assert "pending_returns(db, order).get(step.id)" in _body(proc, "_ready_at"), (
        "Die Sperre steht nicht am Ausführungs-Mechanismus – dann muss jedes Modul sie "
        "selbst kennen."
    )

    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    card = _body(diagram, "StepCard", kind="function")
    assert "<fieldset disabled={locked}" in card, (
        "Die Sperre schaltet nicht die Eingaben ab – dann müsste jedes Modul sie kennen. "
        "`fieldset[disabled]` tut es für JEDES Modul, ohne dass es davon weiss."
    )
    assert "waitingFor" in diagram, "Die Karte kennt die Sperre nicht."

    # Und die Datenerfassung weiss NICHTS davon – sonst wäre sie die Vorlage, die jedes
    # künftige Modul abschreiben müsste.
    capture = _read(FRONTEND / "components" / "erp" / "capture-form.tsx")
    assert "waiting" not in capture.lower().replace("wartet", ""), (
        "Das Modul fragt selbst, ob es darf."
    )


def test_the_deviation_mark_comes_from_one_component():
    """**#699 — «Abweichung» ist ein Zeichen am Symbol, in Feed UND Kopf dasselbe.**

    Zwei Implementierungen driften garantiert auseinander (das war #688). Also rendert
    **eine** Komponente das Symbol eines Datensatzes, und beide Orte benutzen sie; nur die
    Grösse unterscheidet sie.
    """
    fields = _read(FRONTEND / "components" / "erp" / "fields.tsx")
    assert "export function RecordIcon(" in fields
    assert "deviation" in _body(fields, "RecordIcon", kind="function")

    page = _read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx")
    assert "<RecordIcon" in page, "Der Feed baut das Symbol selbst."
    assert "Abweichung" not in _code(page), "Im Feed steht das Label noch als Text."

    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "deviation={shown?.is_deviation" in detail, "Der Kopf trägt das Zeichen nicht."


def test_modules_are_collapsed_unless_they_are_up_next():
    """**#696 — eingeklappt, ausser das Modul ist dran. Eine Stelle, nicht je Modultyp.**"""
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    card = _body(diagram, "StepCard", kind="function")
    assert "useState(!!defaultOpen)" in card, "Die Karte hat keinen Aufklapp-Zustand."
    assert "setOpen(!open)" in card, "Der Kopf klappt nicht auf."
    assert "children && open" in card, "Der Inhalt hängt nicht am Zustand."
    assert "expandedStepId" in diagram, "Niemand sagt, welches Modul offen startet."


def test_new_is_an_origin_on_its_own():
    """**#693 — mit «Neu» kommt keine zweite Zeile dazu, und umgekehrt.**

    Ein Erzeugungsauftrag fährt die Vorlage genau dieses Artikels; ihr Versionsstempel
    gilt nur für seine Stücke. Die Regel steht **serverseitig** – ein fehlender Knopf ist
    keine Absicherung.
    """
    proc = _read(BACKEND / "app" / "services" / "release.py")
    assert "def _assert_single_new(" in proc
    assert "_assert_single_new(out)" in _body(proc, "resolve_lines"), (
        "Die Regel greift nicht auf dem gemeinsamen Weg von /validate und Freigabe."
    )
    ui = _read(FRONTEND / "components" / "erp" / "definition-lines.tsx")
    # In der **Stückliste** (`perUnit`) gibt es «Neu» gar nicht – dort ist die Regel
    # gegenstandslos, und der Knopf bleibt darum stehen.
    assert "hasNew" in ui and "{(perUnit || !hasNew) && (" in ui, (
        "Der Knopf «Zeile» bleibt trotz «Neu»."
    )
    assert "multi" in ui, "«Neu» bleibt wählbar, obwohl es eine zweite Zeile gibt."


def test_the_release_hint_is_not_repeated_in_the_body():
    """**#692 — «Zur Freigabe fehlt …» entfällt; der ausgegraute Knopf sagt es.**"""
    art = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "Zur Freigabe fehlt" not in _code(art)
    assert "Es fehlt:" in art, "Auch der Hover nennt den Grund nicht mehr."
    order = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "Zur Freigabe fehlt" not in _code(order)


def test_the_article_shortcut_only_preselects_the_article():
    """**#690 — ein reiner Shortcut, kein zweiter Anlagepfad.**

    Er öffnet denselben Entwurf wie «+», nur mit vorbelegtem Artikel. Menge, Herkunft und
    Prozess bleiben offen – eine vorausgefüllte «1» wäre eine Behauptung, die meistens
    falsch ist und trotzdem freigebbar aussieht.
    """
    art = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "onCreateOrder?.(record.object_id)" in _body(art, "createOrderShortcut", kind="function"), (
        "Der Shortcut tut nichts."
    )
    assert "api.createOrder" not in art, "Der Artikel legt selbst einen Auftrag an."
    page = _read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx")
    assert "startCreate('order', { articleObjectId })" in page
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    # **Optional, nicht abwesend.** Der Auslöser am Stück (§3.1) und die Entscheidung nach
    # einem «nicht bestanden» reichen sehr wohl Stücke herein – nur eben mehrere und nur
    # dort, wo sie bekannt sind. Der Artikel-Shortcut lässt das Feld leer; hier steht die
    # Form, nicht die Zahl.
    assert "unitNumbers?: string[];" in detail, "Der Seed verlangt weiterhin ein Stück."


def test_the_start_time_comes_from_the_event_log():
    """**#689 — «wann hat das Stück den Start passiert» steht schon im Log.**

    Ein Feld daneben wäre eine Kopie, die beim ersten Nacherfassen von der Wahrheit
    abweicht – und die Wahrheit ist der Log (§7.2).
    """
    proc = _read(BACKEND / "app" / "services" / "order_state.py")
    body = _body(proc, "started_at")
    assert "ProcessEvent" in body and "KIND_START" in body, "Der Zeitpunkt kommt nicht aus dem Log."
    model = _read(BACKEND / "app" / "models" / "order_unit.py")
    assert "started_at" not in model, "Es gibt eine zweite Wahrheit als Spalte."
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "startedAt" in diagram, "Der Hover zeigt den Zeitpunkt nicht."


def test_the_lane_widths_live_in_exactly_one_place():
    """**Die Umbruchpunkte stehen an EINER Stelle, und drei Spuren tragen ein Notebook.**

    Entschieden wird nach **effektiver CSS-Breite**, nicht nach der Panel-Auflösung: ein
    MacBook Pro 13,3″ hat 2560 × 1600 Pixel und liefert dem Browser 1440 × 900 CSS-Pixel
    (Standard, DPR 2) bzw. 1280 / 1680 in den skalierten Modi. Der Rahmen im Detailfenster
    ist rund 380 px schmaler als das Fenster (Feed + Polsterung) – gemessen: 1152 → 776,
    1280 → 904, 1366 → 990, 1440 → 1064, 1680 → 1304.

    Zwei Aussagen, beide gemessen und nicht geschätzt:

    1. Alle Masse kommen aus ``process-flow.LANE``. Eine zweite Zahl in einer Komponente
       wäre ein zweiter Umbruchpunkt, und der läuft vom ersten weg.
    2. Drei Spuren müssen bei 1280 px Fensterbreite (Rahmen 904) stehen – der schmalste
       Modus, den ein 13,3″-Notebook üblicherweise fährt.
    """
    flow = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    lane = {k: int(v) for k, v in re.findall(r"\n  (GAP|MID_MIN|MID_MAX|SIDE_MIN|SIDE_MAX): (\d+)", flow)}
    assert len(lane) == 5, f"LANE ist unvollständig: {sorted(lane)}"
    assert "export const LANES_FROM = LANE.MID_MIN + 2 * LANE.SIDE_MIN + 2 * LANE.GAP" in flow, (
        "Die Schwelle ist nicht mehr aus den Spurbreiten abgeleitet – dann ist sie eine "
        "zweite Zahl neben ihnen."
    )
    threshold = lane["MID_MIN"] + 2 * lane["SIDE_MIN"] + 2 * lane["GAP"]
    assert threshold <= 904, (
        f"Drei Spuren brauchen {threshold} px Rahmen – bei 1280 px Fensterbreite (der "
        f"schmalste übliche Modus eines 13,3″-Notebooks) sind nur 904 da."
    )
    assert lane["SIDE_MIN"] >= 150, (
        f"Ein Nachbar mit {lane['SIDE_MIN']} px trägt seine Modul-Karten nicht mehr."
    )
    assert lane["MID_MIN"] < lane["MID_MAX"], (
        "Die Mitte darf schmaler werden – sonst ist sie kein Verhandlungsspielraum, "
        "sondern eine feste Sperre."
    )

    # Keine zweite Stelle: die Prozess-Komponenten bringen keine eigenen Spurbreiten mit.
    for name in ("process-columns.tsx", "process-diagram.tsx"):
        code = _code(_read(FRONTEND / "components" / "erp" / name))
        strays = re.findall(r"const (SIDE_\w*|MID_\w*|WIDE|GAP)\s*=\s*\d", code)
        assert not strays, (
            f"{name} definiert eigene Spurmasse {strays} – sie gehören in "
            f"`process-flow.LANE`, sonst gibt es zwei Umbruchpunkte."
        )
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "export const PROCESS_MAXW = LANE.MID_MAX" in diagram, (
        "PROCESS_MAXW ist wieder eine eigene Zahl statt der Spurbreite."
    )


def test_the_process_picture_has_one_line_system():
    """**Zwei Stärken, zwei Farben, ein Linientyp — mehr trägt keine Information.**

    Die Ausscherung in einen Nebenauftrag ist **keine andere Art Linie**, sondern derselbe
    Strang, der abzweigt: sie folgt darum derselben Regel wie die Achse (gegangen ↔
    ausstehend). Ob ein Stück zurückkehrt, sagt nicht ein Strichmuster, sondern **ob es
    die Linie gibt**.

    Vorher waren es drei Farben (Achse gegangen · Achse offen · Abzweigung) und zwei
    Linientypen (durchgezogen · gestrichelt) – vier Zeichen für zwei Aussagen.
    """
    files = [_code(_read(FRONTEND / "components" / "erp" / f))
             for f in ("process-columns.tsx", "process-diagram.tsx", "process-flow.tsx")]
    code = "\n".join(files)
    assert "strokeDasharray" not in code, (
        "Im Prozessbild ist wieder eine gestrichelte Linie – das Fehlen einer Linie IST "
        "die Aussage «kommt nicht zurück»."
    )
    strokes = set(re.findall(r"stroke=\{?['\"]?(var\(--[a-z0-9-]+\))", code))
    inline = set(re.findall(r"stroke=\{[^}]*?(var\(--[a-z0-9-]+\))", code))
    used = strokes | inline
    assert used <= {"var(--fg-2)", "var(--border-2)"}, (
        f"Das Prozessbild benutzt weitere Linienfarben: {sorted(used)}. Farbe an einer "
        f"Prozesslinie ist keine freie Entscheidung – gegangen und ausstehend, sonst nichts."
    )
    # **Genau EIN Bauteil zeichnet, und genau EIN Generator formt.** Achse, Ausscherung
    # und Rückführung sind derselbe Strang; drei Zeichenstellen wären drei Gelegenheiten,
    # sich anders zu entscheiden – und genau daraus entstanden die Abweichungen im Bild.
    assert code.count("<path") == 1, (
        "Es gibt mehr als eine Stelle, die eine Prozesslinie zeichnet."
    )
    assert code.count("export function polyPath(") == 1 and code.count(" d={polyPath(") >= 1, (
        "Es gibt mehr als einen Pfad-Generator."
    )
    for f in files[:2]:
        assert " d=\"M" not in f and "d={`M" not in f, (
            "Ein Pfad wird von Hand geschrieben statt aus dem einen Generator geholt."
        )


def test_a_pick_says_where_it_was_taken_from():
    """**Ein Auftrag darf nie unbemerkt seine Art ändern.**

    Ein Entwurf lebt im Browser, die Freigabe passiert später. Nimmt jemand dazwischen
    dasselbe Stück, verhinderte der Unique-Index (§3) zwar, dass beide es halten – aber
    nicht, **wer** verliert: ein als frei gewähltes Stück, das inzwischen lief, machte die
    Freigabe **still** zur Abweichung und entzog es dem anderen Auftrag, mit
    ``return_to = NULL``, also für immer. Gefragt wurde niemand.

    Die Auswahl trägt deshalb ihre **Absicht** mit («war frei» ↔ «aus Auftrag N»), und die
    Freigabe vergleicht sie mit der Wirklichkeit. Es ist optimistisches Sperren mit dem
    Wert, den der Mensch gesehen hat – **eine** Auswahl-Logik für beide Fälle, kein
    zweiter Weg «nur nach Kriterium».
    """
    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    assert "class UnitPick(" in schema and "from_order: Optional[int]" in schema, (
        "Die Auswahl nennt nicht mehr, wo das Stück lag."
    )
    assert "unit_numbers" not in schema, (
        "Die alte, absichtslose Nummernliste steht wieder da – dann entscheidet die Zeit, "
        "welche Art Auftrag entsteht."
    )

    svc = _code(_read(BACKEND / "app" / "services" / "release.py"))
    assert "def _assert_as_picked(" in svc, "Die Absicht wird bei der Freigabe nicht geprüft."
    assert "_assert_as_picked(db, ln, pairs, held)" in svc, (
        "Die Prüfung ist nicht verdrahtet – sie muss VOR dem Übernehmen laufen."
    )
    assert '"code": "pick_stale"' in svc, (
        "Der Konflikt hat keinen Code. Die Oberfläche müsste im Meldungstext nach Wörtern "
        "suchen, und eine Umformulierung würde ihn still verschlucken."
    )

    ui = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    assert "fromOrder: number | null" in ui, "Die Oberfläche merkt sich den Halter nicht."
    assert "from_order: u.fromOrder" in ui, "Der Halter wird nicht mitgeschickt."
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "'pick_stale'" in detail and "setRefreshKey" in detail, (
        "Nach dem Abbruch wird die Auswahl nicht gegen die Wirklichkeit nachgezogen – "
        "dann sieht der Mensch nicht, was sich geändert hat."
    )


def test_the_branch_leaves_the_axis_and_the_line_reaches_the_module():
    """**Zwei Aussagen der Prozesslinie, beide gemessen an dem, was das Backend sagt.**

    1. Eine Ausscherung geht von der **Achse** ab, nicht vom Rand der Spur. Der
       Zustandsknoten ist so breit wie seine Spur; nähme man seinen rechten Rand, begänne
       die Linie weit neben der Prozesslinie und sähe aus, als hinge sie an nichts.
    2. Kräftig läuft die Linie **bis in das Modul, das jetzt dran ist**. «Vor Modul X
       stehen» (``current_step_id``) und «X ist dran» (``active_step_id``) sind dieselbe
       Tatsache; zwischen dem Zustandspunkt und dem Modul liegt kein Prozessobjekt. Der
       Abstand dazwischen ist Layout – die Zeile macht Platz für einen Nebenauftrag.
    """
    cols = _code(_read(FRONTEND / "components" / "erp" / "process-columns.tsx"))
    branch = _body(cols, "Cross", kind="function")
    assert "port(here.a, 'center')" in branch, (
        "Die Abzweigung beginnt nicht auf der Achse – sie soll dort mit einer Kurve "
        "abbiegen wie eine Ausfahrt, nicht mit einem Knick danebenstehen."
    )
    # **Der Zug beginnt IM Punkt – kein Stummel davor.** Ein gerades Stück auf der
    # Achse vor dem Bogen überlagert die Hauptlinie; sichtbar als überstehendes
    # Endchen. Möglich wird das dadurch, dass ein **Endstück** ganz im Bogen aufgehen
    # darf – die Halbierung gibt es nur zwischen zwei benachbarten Ecken.
    assert "[hx, hy - BEND], [hx, hy - BEND]" not in branch, (
        "Die Ausscherung liegt vor dem Bogen noch ein Stück auf der Achse – genau das "
        "ist das überstehende Linienstück am Knotenpunkt."
    )
    # **Die Krümmung folgt dem FLUSS, nicht der Lage des Ziels.** Der Fluss geht von oben
    # nach unten; das Stück, mit dem eine Querlinie die Achse berührt, wird darum immer
    # stromabwärts durchlaufen: hinaus ab dem Punkt hinunter (er ist der Anfang), herein
    # von oben auf ihn zu (er ist das Ende). Erst dadurch sind Zu- und Rückführung allein
    # an der Krümmung zu unterscheiden – nach der Lage des Ziels waren beide gleich
    # gekrümmt, und der Rückführpunkt sah aus wie ein Abzweigepunkt.
    assert "[hx, hy], [hx, hy + BEND]" in branch, (
        "Die Ausscherung läuft am Punkt nicht stromabwärts – sie krümmt sich dann nicht "
        "weg vom Strang."
    )
    assert "[hx, hy - BEND], [hx, hy]" in branch, (
        "Die Rückführung mündet nicht stromabwärts ein – sie sieht dann aus wie eine "
        "Ausscherung."
    )
    assert "other >= hy" not in branch, (
        "Die Richtung hängt wieder an der Lage des Ziels statt am Fluss."
    )
    flowsrc = _read(FRONTEND / "components" / "erp" / "process-flow.tsx")
    assert "i === 1 ? 1 : 2" in flowsrc and "i === pts.length - 2 ? 1 : 2" in flowsrc, (
        "Ein Endstück darf nicht ganz im Bogen aufgehen – dann bleibt der Stummel."
    )
    assert ".right" not in branch and "P.right" not in cols, (
        "Die Abzweigung beginnt wieder am Spurrand – sie hängt dann sichtbar an nichts."
    )
    # **Der Kantenzustand kommt vom Server, das Frontend rechnet ihn nicht.** Die frühere
    # Zählung «bis zum wievielten Knoten» las den *aktuellen* Zustand – und verschwand
    # darum, sobald an einer Stelle nichts mehr stand.
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "walkedEdges" not in diagram and "walkedEdges" not in cols, (
        "Die Linienstärke wird wieder im Browser abgeleitet."
    )
    assert "walked={e.walked}" in diagram, "Die Kante trägt ihren Zustand nicht selbst."


def test_a_neighbour_is_its_process_and_a_lock_needs_no_paragraph():
    """**Was das Bild zeigt, wird nicht danebengeschrieben** (Notizen #701/#702/#704).

    Drei Texte sagten dasselbe wie die Darstellung: die Kopfkarte über einem Nachbarn
    (Art, Nummer, Status, Stückzahl), die Notiz über dem Bild («eine Einzelinstanz ist in
    einer Abweichung») und die Sperr-Notiz im Modul. Alles davon steht in den Linien, den
    Pillen und der Abzweigung.

    Geblieben ist, was das Bild nicht kann: **hinführen**. Das tut jetzt der Prozess
    selbst – ein Klick auf die Spalte öffnet den Auftrag, der Rest steht im Hover.
    """
    cols = _code(_read(FRONTEND / "components" / "erp" / "process-columns.tsx"))
    assert "function SideHead(" not in cols, "Die Kopfkarte über dem Nachbarn steht wieder da."
    assert "nav(rel.object_id)" in cols, (
        "Die Nachbar-Spalte führt nicht mehr zu ihrem Auftrag – das war das Einzige, was "
        "die Karte konnte und das Bild nicht."
    )
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "WaitingNotice" not in detail, "Die Warte-Notiz über dem Bild steht wieder da."
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "function LockNotice(" not in diagram, "Die Sperr-Notiz im Modul steht wieder da."
    assert "fieldset disabled={locked}" in diagram.replace("<", ""), (
        "Die Sperre selbst ist weg – der Text war überflüssig, die Wirkung nicht."
    )


def test_the_pill_reads_the_present_and_the_line_the_past():
    """**Zwei Aussagen, zwei Träger** (Auftrag §1).

    «In Abweichung» ist ein Satz in der Gegenwartsform. Er stand unbedingt an jeder
    ausgescherten Zeile – auch dann noch, wenn der Nachbar fertig war und das Stück in
    keinem Prozess mehr stand. Die Antwort steht in den Daten, die die Kante ohnehin
    trägt: ``status``. Wer sie ignoriert und das Wort festverdrahtet, behauptet wieder
    Gegenwart über Vergangenes.
    """
    src = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "u.status === IM_PROZESS" in src and "u.status !== IM_PROZESS" in src, (
        "Die ausgescherten Stücke werden nicht mehr nach ihrem Zustand getrennt – dann "
        "sagt die Pille wieder für immer «In Abweichung»."
    )
    assert "Abgegeben ·" in src, "Für «dort geblieben» fehlt das Wort."
    # Die Linie bleibt, was sie ist: Vergangenheit aus dem Log.
    assert "walked={e.walked}" in src, "Die Linie liest nicht mehr den Log."


def test_the_history_hangs_where_nothing_clips_it():
    """**Die Blase ist ein `::after` – ein `overflow: hidden` schneidet sie weg.**

    Genau das war der Grund, warum der Ereignis-Log an Start und Ende erschien, am
    **Modul** aber nicht: dort hing er an der Beschriftung, und die kürzt lange Namen
    (`truncate`). Ein Hinweis, der an manchen Objekten unsichtbar ist, ist kein Muster.
    """
    src = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    head = src.split("function StepCard(")[1].split("\nfunction ")[0]
    for block in re.findall(r"<span[^>]*truncate[^>]*>", head):
        assert "data-tip" not in block, (
            "Die Historie hängt wieder an einem kürzenden Element – dort ist sie unsichtbar."
        )
    # **Gefragt wird nach der WEITERGABE, nicht nach dem Bauteil.** Seit die Hülle
    # geteilt ist (`ModuleShell`, #783), rendert die Karte das Zeichen nicht mehr selbst –
    # sie reicht die Historie durch, und die Hülle hängt sie an. Ein Wächter, der hier
    # `<ModuleMark` verlangt, prüfte die **Form** der alten Lösung und verböte die
    # geteilte: er schlüge an, obwohl die Regel besser erfüllt ist als vorher.
    assert "history={history}" in head, (
        "Die Modul-Karte reicht ihre Historie nicht weiter – dann hängt sie nirgends."
    )


def test_the_history_belongs_to_the_whole_head_not_to_the_symbol():
    """►►► **Die Historie gilt für die Kopfzeile, nicht für das Symbol** (Testnotiz #790).

    Sie hing am 32-px-Quadrat links in der Karte – man musste es also treffen, um zu
    erfahren, was an diesem Modul passiert ist. Gemeldet wurde genau das: «die
    Hover-Historie sollte für den ganzen Prozessschritt-Container gelten und nicht nur
    beim Symbol-Bereich».

    Die Kopfzeile **ist** dieser Container: sie läuft über die ganze Kartenbreite, und
    zugeklappt – der Normalfall – ist sie die Karte. Bewusst **nicht** der äussere
    Rahmen: darin steht der aufgeklappte Feldsatz, und eine Blase, die beim Tippen in
    einem Eingabefeld aufgeht, ist Störung statt Auskunft.

    Bug-Formen, alle drei geprüft:
      (a) `data-tip` sitzt wieder am `ModuleMark` (dem Symbol);
      (b) die Kopfzeile trägt sie gar nicht;
      (c) sie ist einzeilig (ohne `data-tip-list` bleiben die Zeilenumbrüche aus
          `attr()` unwirksam – die Liste stünde als ein Wortband da).
    """
    src = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    mark = src.split("export function ModuleMark(")[1].split("\nexport function ")[0]
    assert "data-tip" not in mark, (
        "Die Historie hängt wieder am Symbol – dann muss man ein 32-px-Quadrat treffen, "
        "um zu erfahren, was an diesem Modul passiert ist (#790)."
    )
    shell = src.split("export function ModuleShell(")[1].split("\nexport function ")[0]
    # Der Kopf ist die Zeile mit `ModuleMark` darin – gesucht wird das Element, das sie
    # öffnet, nicht eine Zeilennummer.
    head_tag = shell.split("<ModuleMark")[0].split("<div")[-1]
    assert "'data-tip': history" in head_tag, (
        "Die Kopfzeile trägt die Historie nicht – dann gibt es sie nirgends mehr."
    )
    assert "'data-tip-list': ''" in head_tag, (
        "Ohne `data-tip-list` ist die Blase einzeilig – die Historie ist eine Liste."
    )
    assert "tabIndex={history ? 0 : undefined}" in head_tag, (
        "Ohne Fokus gibt es die Historie auf dem Touchgerät und an der Tastatur nicht."
    )


def test_the_return_switch_sits_where_its_line_starts():
    """**Der Schalter steht auf der Linie, die er schaltet** (Auftrag §5).

    Drei Anläufe: neben der Stückauswahl (Aussage ≠ Wirkung), als Ersatz-Knoten mit
    **eigener** Linie (zwei Linien für eine Entscheidung), als Klick auf die ganze
    Nachbarspalte (kein Bedienelement, nur Fläche). Jetzt: eine Pille unter dem
    Ende-Objekt – **die letzte Zeile der Spalte**, und genau dort dockt die echte
    Rückführungslinie an (§8.1a″).

    Sie **bleibt**, wenn die Linie geht: sonst wäre die Entscheidung einmalig.
    """
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    cols = _read(FRONTEND / "components" / "erp" / "process-columns.tsx")
    assert "function ReturnRow(" in diagram, "Es gibt keinen Schalter mehr."
    assert "if (extra.returns) rows.push({ key: 'return', slot: 'return' });" in diagram, (
        "Der Schalter ist nicht die letzte Zeile – dann beginnt die Linie woanders als er."
    )
    # Die Linie dockt an der letzten Zeile an; steht der Schalter nicht dort, driften sie.
    assert "rows[rows.length - 1]" in cols, (
        "Die Querverbindung dockt nicht mehr an der letzten Zeile der Spalte an."
    )
    assert "onToggle" not in _code(cols).split("function Neighbour(")[1].split("\n}")[0], (
        "Die Nachbarspalte schaltet wieder – eine Fläche ohne Aufforderung ist kein "
        "Bedienelement."
    )


def test_the_definition_is_the_fields_not_a_frame_around_them():
    """**Kein Container um Karten, keine Überschrift über Feldern.**

    Über der Anlage stand «Definition» und der Satz «Was bearbeitet dieser Auftrag? Ohne
    Definition kein Start.» – beides sagte, was die Felder darunter zeigen, und der
    Rahmen legte eine zweite Kante um Zeilen, die bereits Karten sind.
    """
    src = _read(FRONTEND / "components" / "erp" / "definition-lines.tsx")
    assert "Ohne Definition kein Start" not in src, "Der Erklärsatz steht wieder da."
    body = src.split("export function DefinitionLines(")[1].split("\nfunction ")[0]
    assert ">\n          Definition\n" not in body, "Die Überschrift steht wieder da."
    assert "border: '1px solid var(--border-1)'" not in body, (
        "Um die Zeilen liegt wieder ein eigener Rahmen."
    )


# ---------------------------------------------------------------------------
# Aussondern – zwei Ausprägungen, eine Registry
# ---------------------------------------------------------------------------


def test_a_module_type_brings_its_own_fields_from_one_registry():
    """**Welche Felder ein Modul hat, sagt sein Typ** – als Zuordnung, nicht als Kette.

    Verteilt über `toModulePayload`, `moduleIncomplete` und den Editor wären es drei
    Ketten, die beim dritten Modultyp auseinanderlaufen. Sie stehen darum an je einer
    Stelle, und die Schlüssel decken die Backend-Registry genau ab.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    ts = _read(FRONTEND / "lib" / "modules.ts")
    # Ab dem Zuweisungs-`{`, sonst fängt die **Typ-Signatur** mit (dort stehen `config`
    # und `draft` auf derselben Einrückung) – dieselbe Vorsichtsmassnahme wie bei
    # `MODULE_FIELDS` ein paar Zeilen tiefer.
    form = ts.split("export const MODULE_FORM")[1].split("}> = {", 1)[1].split("\n};")[0]
    # **Ein Eintrag je Typ – gleich, ob er ein Literal ist oder auf einen geteilten
    # zeigt.** Die Regel ist «jeder Modultyp hat genau einen»; wie er geschrieben ist,
    # gehört nicht dazu. Vorher stand hier ``(\w+): \{`` und verlangte damit ein
    # Inline-Objekt – zwei Module, die sich denselben Eintrag teilen (Ein- und Verkauf
    # tragen denselben Beleg), fielen als «fehlend» heraus, und die naheliegende
    # Reparatur wäre gewesen, den Eintrag zu **kopieren**. Ein Wächter, der zur Doppelung
    # drängt, prüft die falsche Sache.
    assert set(re.findall(r"^  (\w+): ", form, re.M)) == set(modules.KEYS)

    designer = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    # Ab dem Zuweisungs-`{`, sonst fängt die Typ-Signatur der Props mit.
    fields = designer.split("const MODULE_FIELDS")[1].split("= {", 1)[1].split("\n};")[0]
    assert set(re.findall(r"^  (\w+):", fields, re.M)) == set(modules.KEYS)
    assert "MODULE_FIELDS[m.moduleType]" in designer, (
        "Der Editor wählt den Feldsatz nicht mehr über die Zuordnung."
    )

    # Und es gibt genau EINE Stelle, an der ein Modul-Entwurf entsteht.
    assert "blankModule(id, moduleType)" in designer
    assert "moduleType, points: []" not in _code(designer), (
        "Ein zweites Objektliteral für einen Modul-Entwurf – der nächste Feldzusatz "
        "fehlt dann an einer der beiden Stellen."
    )


def test_the_parts_list_uses_the_very_same_component_as_the_demand():
    """►►► **Die Stückliste ist der Bedarf, nur je Stück.** ◄◄◄

    «Welcher Artikel, wie viele» ist dieselbe Frage wie am Auftragsanfang – also
    dieselbe Komponente (`DefinitionLines`), kein Nachbau. Zwei Zeilen-Editoren für
    denselben Satz Angaben liefen beim ersten neuen Feld auseinander.

    Zwei der drei Fragen entfallen, und beide aus einem Grund, nicht aus Bequemlichkeit:

    *Herkunft* – eine Stückliste erzeugt nichts, sie verbaut Vorhandenes.
    *Welche Stücke* – **das ist keine Frage der Definition.** Ein Modul ist eine Vorlage:
    es läuft je Auftrag und je Produkt-Stück erneut, und ein hier festgenageltes Stück
    wäre nach dem ersten Mal verbraucht. Gewählt wird beim Ausführen, wo es eine echte
    Wahl ist (`StepNeed.sources`).
    """
    designer = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    assert "DefinitionLines" in designer and "perUnit" in designer, (
        "Der Verbrauch baut sich seinen eigenen Zeilen-Editor."
    )
    assert "api.getArticleOptions()" not in designer, (
        "Der Editor holt die Artikel selbst – dann ist es doch ein zweiter Zeilen-Editor."
    )
    ui = _read(FRONTEND / "components" / "erp" / "definition-lines.tsx")
    assert "{!perUnit && hasArticle && line.origin === LAGER && (" in ui, (
        "Die Stückliste nagelt konkrete Stücke fest – die sind beim Definieren nicht "
        "entscheidbar."
    )

    # Und die Menge heisst, was sie ist – **die Einzelinstanz**, denn das ist das
    # Arbeitsobjekt des Systems (Testnotiz #725). «Stück» war das Wort daneben.
    #
    # Gefragt ist das **Wort**, nicht sein Ort: seit #1024 steht es im Hover über dem
    # Feld statt als Beschriftung darüber – eine Beschriftung über einem 96-px-Zahlenfeld
    # kostet eine ganze Zeile für ein Wort. Wer hier auf die Beschriftung bestünde,
    # verböte genau die Lösung, um die der Nutzer gebeten hat.
    assert "Menge je Einzelinstanz" in ui


def test_a_shortage_is_shown_not_turned_into_a_state():
    """**Nichtverfügbarkeit ist kein Zustand** (§4) – sie ist eine unfertige Zeile.

    Es gibt keinen Pausen-Wert, keine Sperre und keine Verknüpfung auf einen
    Nachschub-Auftrag. Gezeigt wird, was fehlt, und angeboten werden die zwei Wege, die
    es ohnehin gibt: eine andere Instanz wählen (dieselbe Wahl, die der Scan trifft) und
    ein **ganz gewöhnlicher** Auftragsentwurf.

    **Angeboten wird aber nur, was gerade Sinn ergibt** (Testnotiz #723): geht der Plan
    auf, gibt es nichts zu entscheiden; liegt gar nichts frei, ist «wählen» eine
    Sackgasse – dann bleibt der Nachschub. Eine Option, die man anklicken kann und die
    nirgends hinführt, ist schlimmer als keine.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    assert "verfügbar" in work, (
        "Die Zeile nennt nicht mehr, was fehlt – dann sucht der Mensch."
    )
    assert "Andere Instanz wählen" in work and "Nachschub" in work
    assert "onDeviate({ articleObjectId: article })" in work, (
        "Der Nachschub ist kein gewöhnlicher Entwurf mehr – dann gibt es einen zweiten "
        "Anlagepfad."
    )

    # ►► Die Bedingung selbst (#723). ◄◄
    assert "const enough = need.available >= required;" in work, (
        "Der Vergleich «reicht das?» ist weg – ohne ihn steht die Wahl auch dann da, "
        "wenn es nichts zu wählen gibt."
    )
    assert "const empty = need.available <= 0;" in work
    at = work.index("Andere Instanz wählen")
    guard = work[max(0, at - 700):at]
    assert "!empty" in guard and ("!enough" in guard or "misplaced" in guard), (
        "«Andere Instanz wählen» hängt nicht mehr an der Lage – entweder es steht immer "
        "da (auch wenn der Plan aufgeht) oder es führt ins Leere (kein Bestand)."
    )
    assert "{empty && onSupply && (" in work, (
        "Der Nachschub steht wieder unabhängig davon da, ob überhaupt etwas fehlt."
    )

    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    assert "class StepNeed(" in schema
    for word in ("waiting_for_material", "blocked_by_material", "shortage_status"):
        assert word not in schema, f"«{word}» wäre ein Zustand für eine Zahl."


def test_the_flow_is_first_where_then_what():
    """**Erst wohin, dann was** (Testnotiz #724) – die Darstellung folgt dem Handgriff.

    Gearbeitet wird so: die Einzelinstanz scannen (das Ding, an dem gleich etwas
    geschieht), dann das Material dazu holen. Also steht die Instanz **oben** und ihre
    Stückliste **eingerückt darunter** – die Einrückung ist die Zugehörigkeit, und die
    braucht man, sobald ein Auftrag mehrere Erzeugnisse hat: sonst stünde eine Liste von
    Komponenten da, ohne dass sie sagt, zu welchem Stück sie gehört.

    Vorher stand die Stückliste **über** allen Instanzen, einmal für den ganzen Auftrag –
    das las sich wie eine Bestellung und nicht wie ein Arbeitsschritt.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))

    # Die Stückliste wird IN der Instanz-Zeile gerendert, nicht daneben.
    row = work.split("function InstanceRow")[-1]
    assert "needs.map(" in row, (
        "Die Stückliste hängt nicht mehr an der Instanz – dann ist die Zugehörigkeit bei "
        "mehreren Erzeugnissen nicht mehr ablesbar."
    )
    assert "borderLeft: '1px solid var(--border-1)'" in row, (
        "Die Einrückung ist weg – sie IST die Aussage «gehört zu dieser Instanz»."
    )

    # Und die Menge ist die **dieser** Instanz, nicht die des Auftrags.
    assert "need.per_unit * pieces" in work, (
        "Die Menge wird nicht mehr auf die Stücke dieser Instanz gerechnet."
    )


def test_the_shortfall_is_measured_against_the_module_not_against_one_row():
    """►►► **Der Bestand ist ein TOPF – also ist die Messlatte der Bedarf des Moduls**
    (Testnotiz #1027). ◄◄◄

    *«Bei jeder der drei Einzelinstanzen steht ‹aus Charge 00741›, obwohl von diesem
    Artikel nur ein Stück freigegeben ist. Ist das richtig, oder müsste es zugewiesen
    sein?»*

    **Der Topf ist richtig**: zugeteilt wird beim Bestätigen (``consumption.plan``, FIFO,
    je Produkt-Stück) und aufgeschrieben im Log (``payload.into``). Reservierungen gibt
    es im System nirgends – die Freigabe *ist* die Verfügbarkeitsprüfung.

    Falsch war die **Messlatte**: jede Zeile hielt den gemeinsamen freien Bestand gegen
    ihren **eigenen** Anteil, also las sich ein freier Schraubendreher unter drei
    Instanzen dreimal als «genug». ``need.required`` ist die Zahl, gegen die auch der
    Dienst prüft (Menge je Stück × alle Stücke vor dem Modul) – zwei Formen einer Regel,
    ein Massstab.

    Bug-Form: ``enough`` (und damit «Andere Instanz wählen» / «Nachschub») wieder aus dem
    Anteil dieser Zeile rechnen.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    row = work.split("function NeedRow")[-1].split("function InstanceRow")[0]
    assert "const required = need.required;" in row, (
        "Die Deckung wird wieder gegen den Anteil EINER Instanz gehalten – dann liest "
        "sich ein einziges freies Stück unter drei Instanzen dreimal als «genug»."
    )
    assert "need.available >= required" in row, (
        "«Reicht es?» fragt nicht mehr den Bedarf des Moduls."
    )
    # Und die Zeile sagt beide Zahlen: sonst steht dort «1 verfügbar» über einem Bedarf,
    # den niemand sieht.
    assert "von {required} verfügbar" in row, (
        "Die Unterdeckung nennt die Bezugsgrösse nicht – «1 verfügbar» ist wahr und "
        "nutzlos, wenn 3 gebraucht werden."
    )


def test_the_action_verb_comes_from_the_server():
    """**Was der Knopf sagt, sagt das Modul** (`ProcessStepResponse.action`).

    Beim Aussondern hängt es an der Ausprägung – «Erfassen & bestätigen» über einem
    Verschrotten-Modul wäre schlicht falsch, und eine Fallunterscheidung in der
    Oberfläche wäre eine zweite Aussage über dieselbe Sache.
    """
    form = _code(_read(FRONTEND / "components" / "erp" / "capture-form.tsx"))
    assert "Erfassen &amp; bestätigen" not in form and "Erfassen & bestätigen" not in form, (
        "Das Verb steht wieder fest in der Oberfläche."
    )
    assert "{action}" in form
    order = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "action={stepInfo(order, step.id)?.action" in order

    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    assert "action_for(self.config)" in schema


def test_a_terminal_module_is_an_exit_not_a_step():
    """**Ein Ausgang ist kein Durchgang** – die Regel steht am Modultyp, nicht im Ablauf.

    Zwei Folgen, beide ohne Fallunterscheidung: hinter ihm steht kein Modul (die Kette
    endet), und es passiert das Ende-Objekt nicht – dort hängt die Rückführung, und ein
    ausgesondertes Stück kehrt nirgends zurück.
    """
    mods = _read(BACKEND / "app" / "domain" / "modules.py")
    assert "terminal: bool = False" in mods and "terminal = True" in mods

    chain = _read(BACKEND / "app" / "domain" / "chain.py")
    assert ".terminal:" in chain, "Die Kette kennt den Ausgang nicht mehr."

    proc = _code(_read(BACKEND / "app" / "services" / "process.py"))
    assert "_advance(" in _body(proc, "confirm_step")
    body = _body(proc, "_advance")
    # **Die Ausführung fragt die Eigenschaft, nicht den Modulnamen.** Ein Ausgang setzt
    # den Ausgangszustand und schliesst die Zugehörigkeit; alles andere läuft weiter.
    assert "if module.terminal:" in body, (
        "Die Ausführung liest die Eigenschaft nicht mehr – dann entschiede der Name."
    )
    # Und **nur** der Zweig der Weiterlaufenden erreicht das Ende-Objekt. Das ist die
    # Regel, die hier zählt: ein terminales Modul darf ``_finish`` nie erreichen, sonst
    # löste es eine Rückführung aus, die es nicht geben darf.
    assert body.index("if module.terminal:") < body.index("_finish("), (
        "Das Ende-Objekt hängt nicht mehr am Zweig, der weiterläuft."
    )
    assert "return" in body.split("if module.terminal:")[1].split("_finish(")[0], (
        "Der Ausgang und der Durchgang sind nicht mehr die zwei Zweige einer Frage."
    )


def test_an_exit_is_one_property_with_three_consequences():
    """**Module, hinter denen nichts mehr kommt — eine Eigenschaft, kein Regelwerk.**

    ``Module.terminal`` sagt, dass ein Modultyp ein **Ausgang** ist. Daraus folgt alles
    Weitere, ohne dass jemand es dreimal aufschreibt:

    ==========================  ===========================================
    der Editor                  bietet dahinter nichts mehr an
    die Freigabe                weist ein Modul dahinter ab (das Netz)
    das Bild                    endet dort – kein Ende-Objekt
    ==========================  ===========================================

    Ein neuer Modultyp mit derselben Eigenschaft erbt alle drei. Genau darum ist die
    Eigenschaft der Prüfgegenstand und nicht «Aussondern»: eine Regel, die den Modulnamen
    kennt, ist keine Eigenschaft, sondern ein Sonderfall.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    # 1 – die Eigenschaft, und sie reist mit (Katalog **und** gespeicherter Schritt).
    assert modules.get("aussondern").terminal is True
    assert modules.get("datenerfassung").terminal is False
    from app.schemas.process import ModuleFacts, ModuleTypeInfo
    assert "terminal" in ModuleTypeInfo.model_fields
    assert "terminal" in ModuleFacts.model_computed_fields, (
        "Ein gespeicherter Schritt sagt nicht, ob er ein Ausgang ist – dann muss es die "
        "Oberfläche raten."
    )

    # 2 – die Freigabe liest sie (das Netz, serverseitig).
    chain = _read(BACKEND / "app" / "domain" / "chain.py")
    assert ".terminal" in chain, "Die Kettenregel kennt den Ausgang nicht mehr."

    # 3 – das Bild endet dort, auf beiden Seiten: Server (Graph) und Entwurf (Definition).
    flow = _read(BACKEND / "app" / "services" / "flow.py")
    assert "terminal" in _body(flow, "build"), "Der Graph hängt hinter den Ausgang ein Ende."
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "s.terminal" in _body(diagram, "definitionGraph", kind="function"), (
        "Der Entwurf zeichnet hinter dem Ausgang ein Ende-Objekt."
    )

    # 4 – und der Editor bietet dahinter nichts an. Eine fehlende Schaltfläche ist keine
    #     Absicherung (dafür ist 2 da) – aber sie erspart die Sackgasse.
    designer = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    assert "steps.some((s) => s.terminal)" in designer, (
        "Die Modul-Palette steht weiterhin hinter einem Ausgang."
    )
    mods = _code(_read(FRONTEND / "lib" / "modules.ts"))
    assert "export function chainProblems" in mods, (
        "Ein Modul, das hinter den Ausgang sortiert wurde, wird nicht gemeldet."
    )


def test_a_module_colour_travels_with_the_step_and_is_never_guessed():
    """**Die Farbfamilie gehört zum Schritt – und Unbekanntes wird gemeldet.**

    Sie kam einmal über einen Rückruf des Rahmens (``ColumnProps.tone``), gefüttert aus
    dem Modul-Katalog. Den lädt aber nur der Editor: im **freigegebenen** Auftrag kam
    nichts an, und ein stiller Rückfall auf ``slate`` gab jedem Modul die Farbe der
    Datenerfassung – die Aussonderung wechselte beim Freigeben ihr Aussehen.

    Zwei Konsequenzen, beide strukturell: die Farbe ist ein **Feld des Schritts** (man
    kann sie nicht mehr vergessen), und ``moduleTone`` hat **keinen** Rückfall auf eine
    echte Modulfarbe – eine unbekannte Familie sieht kaputt aus, statt sich als anderes
    Modul auszugeben.
    """
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "tone?: (moduleType" not in diagram, (
        "Die Farbe ist wieder ein Prop des Rahmens – dann kann ein Aufrufer sie vergessen."
    )
    assert "moduleTone(step.tone)" in diagram, "Die Farbe kommt nicht vom Schritt."
    assert "moduleTone(undefined)" not in diagram, "Es wird wieder geraten."

    mods = _code(_read(FRONTEND / "lib" / "modules.ts"))
    assert "?? MODULE_TONE.slate" not in mods, (
        "Ein unbekannter Ton fällt wieder auf eine echte Modulfarbe zurück – der Fehler "
        "ist dann nicht zu sehen, sondern zu verwechseln."
    )
    assert "UNKNOWN_TONE" in mods, "Eine unbekannte Farbfamilie wird nicht gemeldet."

    # Und die Antwort trägt sie – aus derselben Registry wie die Beschriftung.
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.process import ModuleFacts
    assert {"label", "tone", "terminal"} <= set(ModuleFacts.model_computed_fields)
    cols = _code(_read(FRONTEND / "components" / "erp" / "process-columns.tsx"))
    assert "tone: s.tone" in cols, "Der laufende Auftrag reicht die Farbe nicht durch."


def test_a_terminal_piece_is_not_offered_anywhere_in_the_interface():
    """**Terminal heisst unerreichbar – auch für die Oberfläche** (Notiz #705er-Runde).

    Der Server lehnt ab, das war nie die Frage. Die Frage war, ob die Oberfläche es
    **anbietet**: sie tat es. Der Abweichungstrigger stand an jedem Stück – auch an einem
    verschrotteten –, die Vorauswahl behielt es, der Entwurf galt als freigebbar, und der
    Fehler kam erst beim letzten Klick.

    Die Ursache war eine weggeworfene Angabe: die Antwort trägt den Zustand jedes Stücks,
    die Ansicht liess ihn beim Einlesen fallen. Danach **konnte** sie nicht mehr prüfen.

    Geprüft wird darum die Kette, nicht die Meldung: der Zustand reist mit, die eine
    abgeleitete Frage wird gestellt, und keine Datei zählt dafür Status auf.
    """
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    lines = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    status = _code(_read(FRONTEND / "lib" / "process-status.ts"))

    # 1. Die eine abgeleitete Frage – aus dem **generierten** Katalog, nicht aus einer Liste.
    assert "export function isTerminal(" in status and "export function isPickable(" in status
    assert ".terminal" in status, (
        "Die Frage wird nicht aus der Katalog-Eigenschaft beantwortet."
    )
    for named in ('"verschrottet"', "'verschrottet'", "VERSCHROTTET ==="):
        assert named not in status, f"«{named}» steht als Wert im Code – dann ist es eine Liste."

    # 2. Der Zustand reist mit dem Stück, statt beim Einlesen verloren zu gehen.
    assert "status: u.status" in detail, (
        "Der Zustand wird beim Einlesen weggeworfen – dann kann die Ansicht nicht prüfen."
    )
    assert "status?: string | null;" in diagram, "Das Stück trägt seinen Zustand nicht."

    # 3. Und der Auslöser folgt daraus – nicht ausgegraut, sondern gar nicht da.
    assert "onDeviate && isPickable(u.status)" in diagram, (
        "Der Abweichungstrigger steht auch an einem Stück, mit dem nichts mehr geht."
    )

    # 4. Die Vorauswahl führt nichts, was kein Auftrag greifen kann.
    assert "o.available" in lines and "!.available" in lines, (
        "Eine vorgewählte Einzelinstanz bleibt stehen, auch wenn sie unerreichbar ist."
    )


def test_the_capture_is_per_piece_and_the_scan_is_per_instance():
    """**Ein Scan, n Formulare** – die Oberfläche koppelt die beiden nicht mehr.

    Sie tat es: **ein** Formular je Bestätigung, dessen Werte der Server auf alle
    gezogenen Stücke kopierte. Bei einer Charge über zwei Stück standen hinterher zwei
    Messwerte – gemessen war einer.

    Geprüft wird die **Form** der Nutzlast (zweistufig, geschlüsselt nach Nummer) und
    dass die Nummern **erst auf Klick** geholt werden: bei 1500 gezogenen Stücken darf
    diese Liste nicht in jeder Auftrags-Antwort mitreisen.
    """
    form = _code(_read(FRONTEND / "components" / "erp" / "capture-form.tsx"))
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    client = _code(_read(FRONTEND / "lib" / "api.ts"))

    assert "Record<string, Record<string, unknown>>" in client, (
        "Die Nutzlast ist wieder flach – dann wird eine Messung zu n gleichen."
    )
    assert "numbers.map((n) =>" in form, (
        "Es gibt nur ein Formular – erfasst wird aber je Einzelinstanz."
    )
    assert "byUnit" in form, "Die Werte hängen nicht am Stück."
    assert "'sample'" in work, (
        "Die zu erfassenden Stücke werden nicht erfragt – dann rät die Ansicht sie."
    )
    # Erst nach dem Scan: die Vorschau davor kommt mit den Zahlen aus, die mitreisen.
    # Geprüft wird die **Stelle**, nicht die Zeilenreihenfolge – ``accept`` holt sie, und
    # ``accept`` wird ausschliesslich aus ``onComplete`` gerufen.
    assert "'sample'" in _body(work, "accept", kind="function"), (
        "Die Nummern werden nicht (mehr) nach dem Scan geholt."
    )
    assert work.count("accept(w, how") == 2, (
        "Die Nummern werden ausserhalb des Scan-Abschlusses geholt – bei 6000 Stück ist "
        "das die Liste, die niemand braucht. (Zweimal: der Knopf in der Zeile und der "
        "Sammel-Scan – beide gehen durch dieselbe Stelle.)"
    )


def test_every_module_shows_what_is_coming_before_the_scan():
    """**Die Vorschau steht zentral, nicht im Modul** (#708).

    Der Scan bleibt die Voraussetzung für die **Eingabe** – er war aber auch die
    Voraussetzung für die **Auskunft**, und das war zu viel: man musste scannen, um zu
    erfahren, was man erfassen soll.

    Sie steht an der einen Ausführungsstelle, also erbt sie jedes Modul: `points` und
    `work` hat jedes, das hier durchläuft. Ein Modul ohne Erfassungspunkte zeigt die
    Menge – dass es nichts zu erfassen gibt, ist dann die Auskunft.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    # **Sie ist keine eigene Komponente mehr, sondern die zweite Ebene der Zeile**
    # (#715) – die Regel ist dieselbe: sie steht an der gemeinsamen Ausführungsstelle,
    # also erbt sie jedes Modul, und sie ist **vor** dem Scan da.
    row = _body(work, "InstanceRow", kind="function")
    assert "Stück erfassen" in row, "Es gibt keine Vorschau vor dem Scan."
    assert "via ? (" in row, (
        "Die Vorschau steht nicht mehr an der Stelle, an die nach dem Scan das Formular "
        "tritt – dann sind es zwei Aussagen statt einer."
    )
    assert "points.length === 0" in row, (
        "Ein Modul ohne Erfassungspunkte bekommt keine eigene Auskunft."
    )
    # Der eigene Scan-Knopf je Instanz – zusätzlich, nicht anstelle des Sammel-Knopfs.
    assert "Instanz ${nr} scannen" in work, "Es gibt keinen Scan-Knopf je Instanz."


def test_a_hold_is_shown_beside_the_way_forward_not_instead_of_it():
    """►►► **Die Oberfläche erfindet keine Sperre, die der Dienst nicht hat.** ◄◄◄

    Der gemeldete Fall: ein Stück fällt durch, der Mensch legt die angebotene Abweichung
    an, lässt sie durchlaufen, das Stück kommt zurück – und der Prozess steht immer noch.
    Ursache war **nicht** der Dienst: ``confirm_step`` hat einen Halt nie abgelehnt.
    Ursache war diese Ansicht: sie rendete bei ``held`` **ausschliesslich** die
    Entscheidung (``held ? <Decision/> : <Scan/>``) und blendete den Scan-Knopf aus.

    Damit hatte sie eine Regel erfunden – und die erfundene Regel hatte keinen Schlüssel:
    aufgehoben wird ein Halt durch einen **neuen Befund**, und genau den konnte man nicht
    mehr erheben. Jeder Anlauf legte die nächste Abweichung an, im Bild eine Teilung
    mehr, im Prozess kein Schritt.

    Geprüft wird die **Form**: der Halt steht neben dem Weg nach vorn, und der Scan-Knopf
    hängt nicht an ihm. Das ist dieselbe Regel wie überall – «die Regel ist die Ablehnung
    im Backend, nicht das ausgegraute Feld», hier in ihrer Umkehrung.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))

    assert "work.held ? (" not in work, (
        "Der Halt verdrängt wieder den Weg nach vorn – das ist die Sackgasse."
    )
    assert "{work.held && (" in work, "Der Halt wird gar nicht mehr gezeigt."
    # Der Scan-Knopf hängt an der **Bestätigung** und an der **Ziehung** (#714) – nie am
    # Halt. Käme er dort weg, wäre die Wiederholungsprüfung unerreichbar.
    assert "{!via && !idle && (" in work, (
        "Der Scan-Knopf hängt an einer anderen Bedingung – steht darin der Halt, ist die "
        "Wiederholungsprüfung wieder unerreichbar."
    )
    assert "work.held" not in _body(work, "InstanceRow", kind="function").split("{work.held && (")[0], (
        "Der Halt entscheidet weiter oben in der Zeile mit – dann verdrängt er etwas."
    )

    # Und der Dienst hält seine Seite: ein Halt ist eine Auskunft, keine Ablehnung.
    proc = _read(BACKEND / "app" / "services" / "process.py")
    body = _body(proc, "confirm_step")
    assert "held_units(" not in body, (
        "Der Dienst lehnt bei einem Halt ab – dann ist die Wiederholungsprüfung "
        "unmöglich, und der Halt hat wieder keinen Ausgang."
    )


# ---------------------------------------------------------------------------
# Bewegen — Ware zuerst, Ziel zuletzt
# ---------------------------------------------------------------------------


def test_the_goods_are_scanned_before_the_destination():
    """**Der Ziel-Scan ist die Quittung der Ablage — also kommt er zuletzt.**

    So arbeitet jedes Lagersystem beim Ein- und Umlagern: erst die Ware, dann der Platz.
    Man hat das Stück in der Hand, geht hin, legt ab, scannt. Zuerst gescannt wäre der
    Zielort eine **Absichtserklärung**: zwischen «Ziel gescannt» und «hingelegt» kann
    alles passieren, und der Nachweis behauptete dann etwas, das niemand gesehen hat.

    Geprüft wird die **Reihenfolge in der Sequenz**, nicht ein Kommentar darüber.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    seq = _body(work, "scanSteps", kind="const")
    assert "goodsSteps(w)" in seq and "placeStep()" in seq, (
        "Die Sequenz setzt sich nicht mehr aus Ware und Ziel zusammen."
    )
    assert seq.index("goodsSteps(w)") < seq.index("placeStep()"), (
        "Der Zielort wird vor der Ware gescannt – dann quittiert er eine Ablage, die "
        "noch gar nicht stattgefunden hat."
    )
    # Auch im Sammel-Scan: alle Waren, dann EIN Ziel. Eine Fuhre geht an einen Ort.
    collective = _body(work, "scanAll", kind="function")
    assert collective.index("goodsSteps") < collective.index("placeStep"), (
        "Der Sammel-Scan quittiert das Ziel, bevor die Ware gescannt ist."
    )


def test_moving_is_a_property_not_a_module_type_check():
    """**«Bewegt es?» kommt vom Schritt, nicht aus einem Vergleich.**

    Die frühere Fassung prüfte, dass das Bit aus der **Transportliste** kommt (sie war
    bei jedem anderen Modultyp leer – eine Liste als Bit). Die Liste gibt es nicht mehr;
    die Aussage bleibt und ist ehrlicher geworden: eine Eigenschaft, `moves`, aus
    derselben Registry wie Beschriftung und Farbe.

    *Daneben stand einmal `buys` («trägt dieses Modul einen Einkaufs-Beleg?»). Mit den
    Modulen «Beschaffen»/«Verkauf» ist der Beleg entfallen – und mit ihm die Frage.*

    Bug-Form: ein `moduleType === 'bewegen'` in der Oberfläche – die zweite Stelle, an
    der sie über Modultypen Bescheid wissen müsste, und die erste, die man beim nächsten
    Modul vergisst.
    """
    cols = _code(_read(FRONTEND / "components" / "erp" / "process-columns.tsx"))
    assert "moves: s.moves" in cols, (
        "Der Schritt bringt «bewegt es?» nicht mehr mit – dann muss die Oberfläche es "
        "wieder aus dem Modultyp erraten."
    )
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "step.moves" in detail, "Die Ausführungsstelle liest die Eigenschaft nicht."
    assert "transports" not in detail, "Die Transportart-Liste ist zurück."
    for surface in ("capture-work.tsx", "order-detail.tsx"):
        code = _code(_read(FRONTEND / "components" / "erp" / surface))
        assert "'bewegen'" not in code and '"bewegen"' not in code, (
            f"{surface} fragt nach dem Modultyp «bewegen» – die Oberfläche soll ihn "
            f"nicht kennen müssen, sie soll sehen, was das Modul mitbringt."
        )


def test_the_place_is_shown_per_piece_and_resolved_by_the_server():
    """**Der Ort hängt am Stück – und die Kette kommt fertig vom Server.**

    Zwei Schrauben derselben Charge dürfen an zwei Orten liegen; darum steht der Ort in
    der **Zeile** des Stücks und nicht am Kopf der Instanz. Und die Kette wird **nicht**
    je Zeile nachgeschlagen: sechzig Zeilen wären sechzig Abfragen mal Kettentiefe – die
    N+1-Falle, an der die Ortsanzeige des Vorgängers hing.
    """
    units = _read(FRONTEND / "components" / "erp" / "unit-numbers.tsx")
    assert "PlaceTrail" in units and "place={u.place}" in _code(units), (
        "Der Ort steht nicht mehr an der Zeile des Stücks."
    )
    assert "getPlace" not in _code(units), (
        "Die Liste löst Orte selbst auf – der Server liefert sie fertig mit der Seite."
    )
    trail = _code(_read(FRONTEND / "components" / "erp" / "place-trail.tsx"))
    assert "TYPE_META" in trail, (
        "Das Symbol des Halters kommt aus einer zweiten Zuordnung statt aus der einen, "
        "aus der es auch der Feed nimmt."
    )
    assert "data-tip" in trail, (
        "Die Kette steht nicht mehr im Hover – ausgeschrieben ist sie bei sechzig Zeilen "
        "eine Wand aus Text, in der die eigentliche Angabe untergeht."
    )


# ---------------------------------------------------------------------------
# Testnotizen #726–#733 – die Runde nach dem Bewegen-Modul
# ---------------------------------------------------------------------------


def test_the_active_module_opens_even_when_it_becomes_active_later():
    """**Wird ein Modul zum aktiven, klappt es auf** (#727).

    `defaultOpen` war ein reiner Startwert: wer den Auftrag öffnete, bevor die Stücke
    ankamen, bekam `false` – und dabei blieb es. Als das Modul dann dran war, blieb es
    zu, ohne blockiert zu sein.

    Der Effekt hängt an `defaultOpen` und nur daran: er läuft beim **Wechsel** des
    aktiven Moduls, nicht bei jedem Rendern. Wer selbst zuklappt, bleibt zugeklappt.
    """
    code = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "useEffect(() => { setOpen(!!defaultOpen); }, [defaultOpen]);" in code, (
        "Der Öffnungszustand zieht nicht mehr nach – ein Modul, das erst später dran "
        "wird, bleibt zu."
    )


def test_the_order_shortcut_wears_the_order_icon():
    """**Ein Auftrags-Knopf sieht aus wie ein Auftrag** (#728).

    Er legt einen ganz gewöhnlichen Auftrag an; was daraus wird, entscheidet die Auswahl
    (#608) und nicht das Symbol. Es kommt aus derselben Zuordnung wie überall –
    `TYPE_META.order` –, nicht aus einer zweiten Liste daneben.
    """
    code = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "TYPE_META.order.icon" in code, (
        "Der Auftrags-Knopf am Stück trägt wieder ein eigenes Symbol statt des einen, "
        "das jeder Auftrag im Haus trägt."
    )


# ---------------------------------------------------------------------------
# Material am richtigen Ort — die Oberfläche rechnet ihn nicht selbst aus
# ---------------------------------------------------------------------------


def test_the_place_requirement_is_derived_not_configured():
    """**Kein Ortsfeld am Verbrauchsmodul.**

    Wo das Material liegen muss, folgt aus dem Ort des Produkts. Ein eigenes Feld daneben
    wäre eine zweite Ortsangabe neben dem Ziel des Bewegen-Moduls – und zwei können sich
    widersprechen. Der Editor darf also gar nicht danach fragen.
    """
    from app.domain import modules

    src = _code(_read(FRONTEND / "lib" / "modules.ts"))
    form = _body(src, "MODULE_FORM", kind="const")
    consume = form[form.index("verbrauch:"):]
    consume = consume[:consume.index("},")]
    assert "target" not in consume, (
        "Der Verbrauch konfiguriert keinen Ort – er erbt ihn vom Produkt "
        "(``consumption.required_place``)."
    )
    assert modules.MODULES[modules.VERBRAUCH].material_place == modules.AT_PRODUCT, (
        "Die Deklaration steht in der Registry, nicht in einem Dienst: ein künftiges "
        "Modul mit Ortsbedarf ist eine Zeile, kein Umbau."
    )


def test_the_ui_never_computes_where_a_piece_lies():
    """«Am Ort» ist eine Aussage über die **Kette** — die kann nur der Server auflösen.

    Die Oberfläche darf darum weder Halter-Nummern vergleichen noch aus ``sources``
    ableiten, was «hier» liegt: sie bekommt beides als Zahl (``here``). Ein Vergleich
    von Objektnummern wäre in genau dem Fall falsch, der in der Praxis der Normalfall
    ist – Material steht in Behältern, und der Behälter steht am Arbeitsplatz.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    assert "need.here" in src and "s.here" in src, (
        "Die Zahlen kommen vom Server (``StepNeed.here`` / ``NeedSource.here``)."
    )
    assert "place.object_id ===" not in src and "place?.object_id ===" not in src, (
        "Ein Vergleich von Halter-Nummern in der Oberfläche wäre die naive Lesart von "
        "«am Ort» – und bei einer Kiste auf der Werkbank schlicht falsch."
    )


def test_hauling_is_an_ordinary_order_draft():
    """**«Holen lassen» ist kein zweiter Anlagepfad.**

    Es ist derselbe Entwurf wie «Nachschub» (``onDeviate``), nur mit Menge und einem
    vorbelegten Bewegen-Modul. Angelegt wird nichts – der Entwurf lebt im Browser
    (Testnotiz #386), und was daraus wird, entscheidet weiterhin die Auswahl.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    haul = src[src.index("onHaul={"):]
    haul = haul[:haul.index("}))}") + 4]
    assert "onDeviate({" in haul, "Derselbe Weg wie jeder andere Entwurf."
    assert "MOVE_MODULE" in haul and "need.place?.object_id" in haul, (
        "Der Entwurf bringt das Bewegen-Modul mit dem Arbeitsort als Ziel mit – und den "
        "Modulschlüssel aus ``lib/modules``, nicht als Zeichenkette im Panel."
    )
    assert "api." not in haul, (
        "Kein eigener Endpunkt: ein «Holen lassen», das anlegt, wäre ein Auftrag, den "
        "niemand bestellt hat."
    )

    seed = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "seed?.steps" in seed, "Der Entwurf nimmt den vorbelegten Ablauf auf."


def test_a_carrier_is_named_by_its_piece_number():
    """Ein **Träger** heisst nach seinem Stück, führt aber auf seine Instanz.

    Ein Stück hat keinen eigenen Datensatz – geöffnet wird die Instanz. Sein *Name* ist
    trotzdem genauer (``100000123-3``), und die Anzeige zieht ihn vor: «in 100000123»
    wären bei einer Charge sechshundert Getriebe, also eine Gruppe und kein Ort.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "place-trail.tsx"))
    assert "holder.number" in src, "Die Zeile nennt die Stück-Nummer."
    assert "'unit'" in src and "'instance'" in src, (
        "Ein Träger trägt das Symbol seiner Instanz – eine zweite Symbol-Zuordnung wäre "
        "dieselbe Aussage ein zweites Mal (``TYPE_META``)."
    )


# ---------------------------------------------------------------------------
# EIN Referenzfeld, überall (Testnotiz #738)
# ---------------------------------------------------------------------------


def test_the_article_name_is_said_once():
    """**Eine Sache, eine Stelle** – auch auf dem Bildschirm (Testnotizen #761/#760).

    Bug-Form: der Name stand im Kopf **und** als erstes Lesefeld der Spezifikation. Zwei
    Anzeigen derselben Angabe sind nicht doppelt so klar, sondern erzeugen die Frage,
    welche gilt (der Kopf ist die Antwort – dort steht er bei **jedem** Datensatztyp).

    Und der **Bestand** steht nicht mehr hinter einem Reiter: «wie viel habe ich davon»
    wird an einem Artikel öfter gefragt als alles andere, und ein Klick dafür ist einer
    zu viel.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "article-detail.tsx"))

    read = _body(src, "SpecRead", kind="function")
    assert 'label="Artikelname"' not in read, (
        "Der Name steht wieder als Lesefeld in der Spezifikation – im Kopf steht er "
        "ohnehin."
    )

    assert "<StockView" in src, "Der Bestand steht nicht mehr am Artikel."
    assert "DetailTabs" not in src, (
        "Der Artikel hat wieder Reiter – der Bestand gehört in dieselbe Ansicht, und "
        "damit bleibt nichts, was einen zweiten Reiter rechtfertigt."
    )


def test_the_frozen_process_shows_the_same_fields_only_locked():
    """►►► **Ein Modul zeigt seine Sache in JEDEM Zustand** (Testnotiz #771). ◄◄◄

    Gemeldet: «hier im Artikel haben wir das Abbild des hinterlegten Prozesses. wenn ich
    drauf klicke, dann sollen sich alle Prozessdetails öffnen – überall sonst funktioniert
    es, nur hier wieder nicht.» Der Editor rendete im eingefrorenen Zustand **gar keinen**
    Körper (``renderStep: frozen ? undefined : …``): der Kopf klappte auf, und darin war
    nichts.

    Es ist **derselbe Feldsatz**, nur gesperrt – ein zweiter, nur-lesender wäre die
    Stelle, an der die nächste Angabe fehlt. Möglich wird das durch die **Umkehrform**
    derselben Zuordnung (``MODULE_FORM[…].draft``), die neben ihrem Gegenstück steht.

    Bug-Form: die Bedingung kommt zurück, oder die Umkehrform fehlt (dann sind die Felder
    leer, was schlimmer ist als gar keine).
    """
    designer = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    assert "renderStep: frozen ? undefined" not in designer, (
        "Der eingefrorene Prozess zeigt wieder nichts – genau die gemeldete Form."
    )
    assert "<fieldset disabled={frozen}" in designer, (
        "Gesperrt wird nicht über `fieldset[disabled]` – dann ist es entweder editierbar "
        "oder ein zweites Layout."
    )

    mods = _read(FRONTEND / "lib" / "modules.ts")
    form = _body(mods, "MODULE_FORM", kind="const")
    keys = set(re.findall(r"^  (\w+): \{", form, re.M))
    for key in keys:
        entry = form.split(f"  {key}: {{", 1)[1]
        assert "draft: (" in entry.split("\n  },", 1)[0], (
            f"«{key}» hat keine Umkehrform – sein Feldsatz bliebe im eingefrorenen "
            f"Prozess leer."
        )
    assert "export function moduleFromConfig" in mods, (
        "Die eine Stelle, die eine gespeicherte Konfiguration zum Entwurf macht, fehlt."
    )
    detail = _code(_read(FRONTEND / "components" / "erp" / "article-detail.tsx"))
    assert "moduleFromConfig" in detail, (
        "Der Artikel reicht seinen eingefrorenen Stand nicht als Entwurf durch."
    )


def test_a_quantity_can_never_reach_zero():
    """**Der Fehler entsteht gar nicht erst** (Testnotiz #774).

    Ein geleertes Feld hiess ``0`` – also genau der Wert, den der Server als «ist zu
    klein» abweist. Das Löschen einer Ziffer ist aber ein ganz normaler Schritt beim
    Ändern einer Zahl: die Meldung kam nicht aus einem Fehler, sondern aus dem Tippen.

    Bug-Form: `onChange` schickt jeden Tastendruck weiter und macht aus «leer» eine Null.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    assert "quantity: raw ? Number(raw) : 0" not in src, (
        "Ein geleertes Mengenfeld wird wieder zur Null – und die Null meldet der Server."
    )
    assert "Math.max(1" in src, "Ohne Untergrenze kann die Null wieder entstehen."
    assert "<QuantityInput" in src and "onBlur={commit}" in src, (
        "Übernommen wird nicht beim Verlassen – dann kann der Zwischenzustand «leer» gar "
        "nicht existieren, und man kann die Zahl nicht mehr ändern."
    )


# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #1023–#1031 — weniger Beschriftung, EIN Suchfeld, EINE Nummer
# ---------------------------------------------------------------------------


def test_a_number_in_the_parts_list_leads_to_its_record():
    """►►► **Eine Objektnummer sieht überall gleich aus – und führt** (Testnotiz #1028).

    In der Zeile «aus 100000741» stand sie als blosser Text: dieselbe Kennung wie
    überall, nur ohne Ziel. ``ObjId`` ist die eine Form; eine zweite Schreibweise wäre
    der erste Schritt zurück zu «Nummern sehen je nach Ort anders aus» (#282/#784).
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    row = work.split("function NeedRow")[-1].split("function InstanceRow")[0]
    assert "<ObjId value={id} />" in row, (
        "Die Nummer der Quell-Instanz ist wieder nackter Text – sie führt nirgendwohin."
    )
    assert "plan.map((id) => formatObjectId(id)).join" not in row, (
        "Die alte Schreibweise steht daneben."
    )


def test_the_draft_does_not_explain_where_its_process_comes_from():
    """**Der Satz unter dem Entwurfsbild ist gelöscht** (Testnotiz #1031).

    *«Ich checke nicht, warum diese Info kommt – bitte gänzlich aus dem Code sauber
    löschen.»* Und «sauber» heisst: mit dem, was nur ihn gefüttert hat – der Artikelname
    kam über ``onArticlesChosen`` aus dem Zeilen-Editor nach oben, und dieser Weg hat
    danach keinen Leser mehr.
    """
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    lines = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    assert "Erzeugungsprozess von" not in detail, "Der Satz steht wieder da."
    assert "onArticlesChosen" not in detail and "onArticlesChosen" not in lines, (
        "Der Weg, der nur ihn gefüttert hat, steht noch – eine Leitung ohne Leser."
    )


# ---------------------------------------------------------------------------
# Testnotizen #1032-#1036
# ---------------------------------------------------------------------------


def test_a_cut_deviation_does_not_stretch_the_axis():
    """►►► **Ohne Rueckfluss keine Klammer** (Testnotiz #1036). ◄◄◄

    Ein Nachbar, der zurueckkehrt, klammert einen Abschnitt der Achse ein (fork oben,
    join unten) – diese Zeilen duerfen auf seine Hoehe wachsen, das ist der Bypass. Eine
    **gekappte** Ausleihe hat keinen join, ihre Spanne war damit **eine** Zeile, und die
    wuchs auf die volle Hoehe des Nachbarn: gemessen 424 px leerer Streifen, an dessen
    Ende die Pille «In Abweichung» stand – getrennt von dem Punkt, an dem sie passiert
    ist.
    """
    cols = _code(_read(FRONTEND / "components" / "erp" / "process-columns.tsx"))
    span = cols.split("const span = useMemo")[1].split("const wires = useMemo")[0]
    assert "kind === 'back'" in span, (
        "Die Spanne fragt nicht mehr, ob der Nachbar zurueckkommt."
    )
    assert "to: Math.max(...rows) }" not in span, (
        "Eine gekappte Abweichung endet wieder an ihrem Abzweigepunkt – die Zeile "
        "wächst auf ihre Hoehe, und die Pille faellt dahinter."
    )
    assert "last" in span, "Der Nachbar ohne Rueckweg laeuft nicht mehr bis ans Ende."


def test_the_journey_row_holds_only_branches():
    """►►► **Der Rest ist kein Ast** (Testnotiz #1035). ◄◄◄

    Die Chip-Reihe zentriert ihre Kinder auf dem Stamm. Stand der «… N»-Hinweis als
    gleichberechtigtes Kind darin, rutschte die ganze Gruppe um seine halbe Breite zur
    Seite (gemessen: der mittlere Ast 14,1 px neben dem Startsymbol), und seine Linie
    bekam einen Knick. Er hat keine Linie – also steht er nicht in der Reihe der Aeste.
    """
    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    row = _component(diagram, "JourneyRow")
    chips = row.split("items-start justify-center")[1].split("</div>")[0]
    assert "{note}" not in chips, "Der Hinweis steht wieder in der Reihe der Aeste."
    assert "rest" not in chips, "Der Hinweis steht wieder in der Reihe der Aeste."


def test_the_article_does_not_show_yet_where_it_is_built_in():
    """►►► **Vertagt, nicht verworfen** (Testnotiz #1034). ◄◄◄

    Der Streifen zeigt «Wird verbaut in» heute nicht – die **Ableitung** bleibt aber:
    sie ist die Gegenrichtung derselben Abfrage, die «was mir fehlt» beantwortet, und
    kommt ohne eine zweite Abfrage mit.
    """
    art = _code(_read(FRONTEND / "components" / "erp" / "article-detail.tsx"))
    assert "Wird verbaut in" not in art, "Der Container ist wieder da."
    assert "used_in" not in art, "Der Artikel liest die Liste wieder."
    bom = _code(_read(BACKEND / "app" / "services" / "bom.py"))
    assert "used_in" in bom, "Die Ableitung ist geloescht statt ausgeblendet."
