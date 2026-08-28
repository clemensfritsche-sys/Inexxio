"""Spiegel über die API-Grenze – was auf beiden Seiten steht, darf nicht auseinanderlaufen.

Das Frontend pflegt einige Aufzählungen von Hand (schnell, ohne Generierung). Damit sie
nicht still von den Backend-Quellen abweichen, vergleicht dieser Wächter beide Seiten.

Nach dem Basis-Neuaufbau ist die Liste kurz – das ist der Punkt: es gibt kaum noch etwas
zu spiegeln, weil es kaum noch etwas gibt. Was hier fehlt, fehlt absichtlich.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"


def _read(path: pathlib.Path) -> str:
    assert path.exists(), f"Erwartete Datei fehlt: {path}"
    return path.read_text(encoding="utf-8")


def _code(source: str) -> str:
    """Nur der Code — Kommentare und Docstrings raus.

    Ein Waechter, der einen Kommentar liest, prueft die Erklaerung statt der Sache: er
    schlaegt an, weil jemand den Fehler *beschreibt*, den er verhindern soll. Genau das
    ist beim Schreiben dieser Runde passiert.
    """
    # Blockkommentare: /* … */ und JSX {/* … */}, dazu Python-Docstrings.
    without = re.sub(r"\{?/\*[\s\S]*?\*/\}?", "", source)
    without = re.sub(r'"""[\s\S]*?"""', "", without)
    # Zeilenkommentare nur am Zeilenanfang – sonst trifft es «https://».
    return "\n".join(
        l for l in without.split("\n")
        if not l.lstrip().startswith(("//", "#", "*"))
    )


def _body(source: str, name: str, *, kind: str = "def") -> str:
    """Der Rumpf genau einer Funktion/Klasse – ohne die nächste mitzunehmen.

    Ein blosses ``split`` läuft bis ans Dateiende und trifft dann Nachbarn, die gar nicht
    gemeint waren; der Test schlüge aus einem Grund fehl, der nichts mit ihm zu tun hat.
    """
    head = f"{kind} {name}"
    start = source.index(head)
    rest = source[start + len(head):]
    # Python endet beim nächsten Top-Level-Konstrukt, TypeScript beim nächsten
    # ``export``/``function``. Dieselbe Absicht, zwei Sprachen – die Alternative wäre ein
    # Parser für eine Frage, die eine Zeile beantwortet.
    # TypeScript endet beim nächsten Konstrukt auf Spalte 0 – oder bei einer
    # eingerückten ``function``, die eine verschachtelte Hilfsfunktion abgrenzt. Ein
    # eingerücktes ``const`` bleibt bewusst draussen: das ist ganz normaler Rumpf.
    stop = (r"\n(?:def |class |@)" if kind in ("def", "class")
            else r"\n(?:export |function |interface |const |/\*\*)|\n\s+function ")
    end = re.search(stop, rest)
    return rest[: end.start()] if end else rest


# ---------------------------------------------------------------------------
# Der zentrale Schalter
# ---------------------------------------------------------------------------

def test_the_one_switch_says_the_same_on_both_sides():
    """``core/features.ACTIVE`` und ``lib/features.ACTIVE`` sind EINE Entscheidung.

    Ein Modul, das nur auf einer Seite abgeschaltet ist, wäre genau die zweite Wahrheit,
    die dieser Umbau loswerden wollte: die Oberfläche böte etwas an, das der Server mit
    503 abweist – oder schlimmer, umgekehrt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.core import features

    ts = _read(FRONTEND / "lib" / "features.ts")

    m = re.search(r"export const ACTIVE: readonly FeatureModule\[\] = \[([^\]]*)\]", ts)
    assert m, "ACTIVE fehlt in lib/features.ts"
    ts_active = {x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()}
    assert ts_active == set(features.ACTIVE), (
        f"Aktive Module laufen auseinander: Backend {sorted(features.ACTIVE)} "
        f"≠ Frontend {sorted(ts_active)}"
    )

    ts_modules = set(re.findall(r"^  (\w+): '", ts, re.M))
    assert ts_modules == set(features.MODULES), (
        f"Modul-Liste läuft auseinander: Backend {sorted(features.MODULES)} "
        f"≠ Frontend {sorted(ts_modules)}"
    )


def test_a_disabled_module_answers_instead_of_disappearing():
    """«Nicht da» und «abgeschaltet» sind verschiedene Aussagen.

    Ein 404 sieht aus wie ein Tippfehler in der URL. Darum bekommt jedes abgeschaltete
    Modul mit eigenem Prefix einen Stub, der 503 und den Grund liefert.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.core import features
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    for module in features.disabled():
        for prefix in features.MODULES[module][1]:
            assert prefix in paths, (
                f"Abgeschaltetes Modul «{module}» beantwortet {prefix} nicht – "
                f"der Aufrufer bekäme 404 statt des Grundes."
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


def test_the_instance_kinds_mirror():
    """``einzeln`` | ``batch`` – auf beiden Seiten dieselben zwei Wörter."""
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models.instance import KINDS

    labels = _read(FRONTEND / "lib" / "record-status.ts")
    for kind in KINDS:
        assert f"'{kind}'" in labels, (
            f"Instanz-Typ «{kind}» hat in der Oberfläche keine Beschriftung "
            f"(lib/record-status.KIND_LABEL)."
        )


# ---------------------------------------------------------------------------
# Was entfallen ist, bleibt entfallen
# ---------------------------------------------------------------------------

def test_the_old_process_concepts_stay_gone():
    """Die **alten Konzepte** kommen nicht zurück – auch nicht unter neuem Namen.

    ``services/process.py`` gibt es wieder; das ist die NEUE Engine (PROCESS_CORE.md),
    nicht die alte. Der Unterschied ist nicht der Dateiname, sondern was fehlt: die
    ganze Mengen-Buchhaltung, die es nur brauchte, weil eine Instanz eine **Menge** war
    und ein Auftrag seine Menge zur Laufzeit verlieren konnte. Beides gibt es nicht mehr
    (§2.1, §3). Wer eines dieser Module wieder anlegt, hat vermutlich eine der beiden
    Regeln aufgeweicht.
    """
    for gone in ("subject.py", "reservation.py", "ledger.py",
                 "units.py", "recovery.py", "supply.py", "deviation.py", "provisioning.py"):
        assert not (BACKEND / "app" / "services" / gone).exists(), (
            f"services/{gone} ist wieder da – Reservierung, Anteil und Unterdeckung "
            f"entfallen ersatzlos (§3)."
        )
    for gone in ("order-flow.tsx", "flow-line.tsx", "process-steps.tsx",
                 "order-positions.tsx", "purchase-step-panel.tsx"):
        assert not (FRONTEND / "components" / "erp" / gone).exists(), (
            f"components/erp/{gone} ist wieder da."
        )
    # ``order-detail.tsx`` gibt es wieder – aber als **Datensatz**-Fenster, nicht als
    # Prozess-Oberfläche. Der Unterschied ist hier festgehalten:
    for concept in ("Anteil", "Reservierung", "Unterdeckung", "Nachschub"):
        svc = _read(BACKEND / "app" / "services" / "process.py")
        assert concept not in svc, (
            f"«{concept}» ist zurück in der Prozesslogik – das Konzept ist ersatzlos "
            f"entfallen (§3)."
        )
    assert not (FRONTEND / "lib" / "process.ts").exists()
    assert not (FRONTEND / "lib" / "order.ts").exists()


def test_the_order_is_a_record_type_like_every_other():
    """Der «Auftrag» reiht sich in die Datensatz-Systematik ein: Feed-Typ, Symbol, Filter."""
    types = _read(FRONTEND / "types" / "index.ts")
    m = re.search(r"export type ErpRecordType = ([^;]+);", types)
    assert m and "'order'" in m.group(1), "Der Feed kennt den Auftrag nicht."

    meta = _read(FRONTEND / "lib" / "erp-record.ts")
    assert "order:" in meta, "TYPE_META kennt den Auftrag nicht (Symbol/Farbe fehlen)."
    assert "'order'" in meta, "FILTER_TYPES kennt den Auftrag nicht."


def test_the_order_carries_only_what_the_process_needs():
    """Der Auftrag trägt seine Identität, seinen Lebenszyklus und den **einen** Ort des
    Endzustands – sonst nichts.

    Spalten auf Vorrat wären erfundene Anforderungen. ``end_status`` steht hier und
    nirgends sonst (§4.2): wäre der Endzustand über die Fachlogik verteilt hart kodiert,
    kostete die spätere Erweiterung (verkauft · verbaut · ausgesondert) einen Umbau
    statt einer Änderung.
    """
    src = _read(BACKEND / "app" / "models" / "order.py")
    columns = {l.split(":")[0].strip() for l in src.split("\n") if "mapped_column(" in l}
    assert columns == {"id", "object_id", "name", "end_status"}, (
        f"models/order.py trägt {sorted(columns)} – erwartet id, object_id, name, "
        f"end_status (created_at/updated_at/is_active kommen aus dem TimestampMixin). "
        f"Der Status ist ABGELEITET (Notiz #669) und darum keine Spalte."
    )
    # Der Endzustand steht an EINER Stelle: die Fachlogik liest ``order.end_status``,
    # sie schreibt den Wert nicht selbst hin.
    svc = _read(BACKEND / "app" / "services" / "process.py")
    assert svc.count("DEFAULT_END_STATUS") == 1, (
        "Der Endzustand wird an mehr als einer Stelle gesetzt."
    )


def test_a_draft_never_touches_the_database():
    """Ein Auftragsentwurf lebt nur im Browser: keine Entwurfs-Zeile, keine vorreservierte
    Objektnummer, kein Autosave. Die Nummer entsteht ausschliesslich beim Speichern."""
    svc = _read(BACKEND / "app" / "services" / "process.py")
    assert svc.count("next_object_id") == 2, (   # Import + genau EIN Aufruf
        "Die Objektnummer wird an mehr als einer Stelle gezogen."
    )
    assert "next_object_id" in svc.split("def release(")[1], (
        "Die Nummer entsteht nicht in der Freigabe."
    )
    # Sie wird NACH der Auflösung der bestehenden Stücke gezogen: eine Sequence ist nicht
    # transaktional, ein Rollback danach liesse eine Lücke im Nummernkreis.
    body = svc.split("def release(")[1]
    assert body.index("held_by(") < body.index("next_object_id(db,"), (
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
# Datenerfassung
# ---------------------------------------------------------------------------

def test_a_capture_hangs_on_a_single_unit():
    """Erfasst wird am Stück – nie an der Instanz, nie am Artikel."""
    model = _read(BACKEND / "app" / "models" / "capture.py")
    assert "instance_unit_id" in model
    assert "instance_id" not in model.replace("instance_unit_id", ""), (
        "Die Erfassung hängt (auch) an der Instanz – das verletzt die Einzelinstanz-Regel."
    )


def test_a_capture_without_something_judgeable_has_no_verdict():
    """``None`` heisst «nichts Bewertbares dabei». Ein erfundenes «bestanden» wäre eine
    Aussage, die niemand getroffen hat."""
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import capture_types as ct

    assert ct.verdict([{"key": "n", "type": "text"}], {"n": "x"}) is None
    assert ct.verdict([{"key": "f", "type": "photo"}], {"f": "x"}) is None
    assert ct.verdict([{"key": "l", "type": "measure"}], {"l": 5}) is None
    assert ct.verdict(
        [{"key": "l", "type": "measure", "target": 10, "tolerance": 1}], {"l": 10.5}) == "passed"
    assert ct.verdict(
        [{"key": "l", "type": "measure", "target": 10, "tolerance": 1}], {"l": 12}) == "failed"
    # Ja/Nein trägt ein Urteil, «nicht angetippt» ist aber kein «nein».
    assert ct.verdict([{"key": "g", "type": "bool"}], {"g": True}) == "passed"
    assert ct.verdict([{"key": "g", "type": "bool"}], {"g": False}) == "failed"
    assert ct.get("bool").missing({"key": "g", "type": "bool"}, None) is True
    assert ct.get("bool").missing({"key": "g", "type": "bool"}, False) is False


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

    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
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

def test_the_status_list_is_generated_not_mirrored():
    """Die Statusliste ist eine **Quelle**, kein Spiegel.

    Vorher stand sie zweimal da – in ``domain/statuses.py`` und, von Hand nachgepflegt,
    im Frontend. Ein Test verglich beide; er **fand** ein Auseinanderlaufen, verhinderte
    es aber nicht: ein neuer Status kostete zwei Einträge, und wer den zweiten vergass,
    sah es erst in der CI.

    Jetzt wird die eine Quelle ausgeschrieben (``scripts/dump_statuses.py``), genau wie
    ``api.ts`` aus dem OpenAPI-Schema entsteht. Der Wächter vergleicht darum nicht mehr
    Wert für Wert, sondern verlangt, dass die Datei **exakt** die ist, die der Generator
    schreibt – damit kann sie gar nicht mehr abweichen.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st
    from scripts.dump_statuses import build

    path = FRONTEND / "lib" / "status-catalog.ts"
    current = _read(path)
    assert "GENERIERT" in current, "Der Katalog behauptet nicht mehr, generiert zu sein."
    assert current == build(), (
        "Der Status-Katalog ist veraltet – neu erzeugen: "
        "cd backend && python -m scripts.dump_statuses"
    )

    # Und die Anzeige-Seite fügt nichts hinzu ausser dem Symbol: Beschriftung, Ton und
    # Bestands-Zugehörigkeit kommen aus dem Katalog, nicht aus einer zweiten Liste.
    ts = _read(FRONTEND / "lib" / "process-status.ts")
    for value, text in st.STATUS_LABELS.items():
        assert f"'{text}'" not in ts, (
            f"Die Beschriftung «{text}» steht wieder von Hand im Frontend."
        )
        assert value in ts or "STATUS_CATALOG" in ts, (
            f"Das Frontend kennt den Status «{value}» nicht."
        )


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
    mig = _read(BACKEND / "alembic" / "versions" / "104_process_engine.py")
    assert "uq_order_units_active" in mig, "Die Migration legt den Index nicht an."
    net = _read(BACKEND / "app" / "main.py")
    assert "uq_order_units_active" in net, (
        "Der Index fehlt im Lifespan-Netz – scheitert Alembic, gibt es die Regel nicht."
    )


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
    proc = _read(BACKEND / "app" / "services" / "process.py")
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
    proc = _read(BACKEND / "app" / "services" / "process.py")
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
    proc = _read(BACKEND / "app" / "services" / "process.py")
    body = proc.split("def release(")[1]
    number_at = body.index("next_object_id(db,")
    head = body[:number_at]
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
    tabs = detail.split("const TABS")[1].split("];")[0]
    assert "Erzeugungsprozess" not in tabs, (
        "Der Prozess steht wieder als eigener Reiter in der Reiterzeile."
    )
    # Er steht im Spezifikations-Zweig, nicht in einem eigenen.
    spec = detail.split("{tab === 'spezifikation' && (")[1].split("{tab === 'bestand'")[0]
    assert "<ArticleProcess" in spec, (
        "Der Erzeugungsprozess steht nicht im Reiter «Spezifikation»."
    )
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
# Bug 2 – eine Tabelle mit fremder Form wird neu aufgebaut, nicht geflickt
# ---------------------------------------------------------------------------

def test_a_stale_table_is_rebuilt_not_patched():
    """``create_all()`` fasst eine vorhandene Tabelle nicht an – genau daran starb der
    Reiter «Erzeugungsprozess» (``column article_process_steps.module_type does not
    exist``). Der Wächter prüft, dass das Netz die **Form** vergleicht und alle
    neu aufgebauten Tabellen abdeckt."""
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.main import _shape_problem

    main = _read(BACKEND / "app" / "main.py")
    guard = _body(main, "_ensure_rebuilt_tables_shape")
    for table in ("ArticleProcessStep", "OrderLine", "ProcessStep", "OrderUnit",
                  "ProcessEvent", "Instance", "InstanceUnit", "Capture", "Order"):
        assert table in guard, (
            f"{table} fehlt im Form-Netz – eine veraltete Tabelle bliebe unentdeckt."
        )
    assert "_ensure_rebuilt_tables_shape()" in _body(main, "_run_startup_fixups_once"), (
        "Das Form-Netz muss im Startup laufen, sonst repariert es nie etwas."
    )

    class _Col:
        pass

    class _FakeInsp:
        def __init__(self, cols):
            self._cols = cols

        def get_columns(self, _table):
            return self._cols

    class _FakeModel:
        class __table__:  # noqa: N801
            columns = {"id": None, "name": None}

    ok = [{"name": "id", "nullable": False, "default": "nextval()"},
          {"name": "name", "nullable": False, "default": None}]
    assert _shape_problem(_FakeInsp(ok), "t", _FakeModel) is None

    # Fehlende erwartete Spalte → der gemeldete Fehler.
    lacking = [{"name": "id", "nullable": False, "default": "nextval()"}]
    assert "es fehlen name" in _shape_problem(_FakeInsp(lacking), "t", _FakeModel)

    # Fremde Pflichtspalte → jedes INSERT wäre tot, auch wenn nichts fehlt.
    blocking = ok + [{"name": "order_id", "nullable": False, "default": None}]
    assert "order_id" in _shape_problem(_FakeInsp(blocking), "t", _FakeModel)

    # Fremde NULLABLE Spalte ist harmlos – reparieren, was nicht kaputt ist, kostet Daten.
    harmless = ok + [{"name": "notiz", "nullable": True, "default": None}]
    assert _shape_problem(_FakeInsp(harmless), "t", _FakeModel) is None


# ---------------------------------------------------------------------------
# Das Modul «Datenerfassung»
# ---------------------------------------------------------------------------

def test_a_sixth_capture_type_is_one_new_file():
    """Die Typen sind **austauschbare Bausteine**, keine ``if/else``-Kette.

    Der Test hält die Vorgabe wörtlich fest: die Registry findet die Typen selbst, und
    keine der drei Fragen (Definition prüfen · fehlt der Wert · bewerten) wird irgendwo
    per Typ-Vergleich beantwortet.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import capture_types as ct

    pkg = BACKEND / "app" / "domain" / "capture_types"
    files = {p.stem for p in pkg.glob("*.py")} - {"__init__", "base"}
    # **Keine Liste der Typen hier.** Sie wäre genau die zweite Aufzählung, vor der
    # dieser Test warnt – und ein Typ hat die Vorhersage in beide Richtungen bestätigt:
    # «Objekt scannen» war **eine neue Datei**, und sein Rückbau (#719) war **eine
    # gelöschte** – keine Zeile sonst.
    assert len(files) == len(ct.ALL), (
        "Jede Datei im Paket ist genau ein Typ – sonst wird die Registry zur Aufzählung."
    )

    registry = _read(pkg / "__init__.py")
    assert "iter_modules" in registry, "Ohne Auto-Erkennung gäbe es eine Liste zum Vergessen."
    for hay in (registry, _read(pkg / "base.py")):
        assert 'type == "' not in hay and "type == '" not in hay, (
            "Ein Typ-Vergleich ist der Anfang der Kette, die es nicht geben soll."
        )


def test_a_picture_is_taken_never_uploaded():
    """**Ein Bild entsteht in der Kamera, nicht im Dateidialog** (Testnotizen #718/#720).

    Eine Datei aus der Galerie belegt nichts über *diesen* Vorgang – sie belegt nur, dass
    es irgendwann eine Datei gab. Ein Nachweis, der auf **beide** Arten entstehen kann,
    ist hinterher keiner: man sieht ihm nicht an, welche der beiden es war. Der Upload ist
    darum ersatzlos entfallen, nicht ausgeblendet.

    **Genau eine Aufnahme je Einzelinstanz**, und nicht optional: bei mehreren bliebe
    offen, welche die gemeinte ist, und bei null wäre der Punkt ein Vermerk statt eines
    Belegs. Durchgesetzt wird das **serverseitig** (``Photo.missing``) – ein Formular, das
    den Knopf ausgraut, ist keine Regel.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import capture_types as ct

    photo = ct.get("photo")
    point = {"key": "bild", "label": "Bild", "type": "photo"}
    assert photo.missing(point, None), "Ohne Aufnahme gilt der Punkt als erfasst."
    assert photo.missing(point, ""), "Ein leerer Wert gilt als Aufnahme."
    assert photo.missing(point, ["/x/a.jpg", "/x/b.jpg"]), (
        "Eine Liste geht durch – dann sind wieder mehrere Bilder möglich, und welches "
        "gemeint ist, steht nirgends."
    )
    assert not photo.missing(point, "/x/aufnahme.jpg")

    shot = _code(_read(FRONTEND / "components" / "erp" / "photo-capture.tsx"))
    assert "useCamera" in shot, (
        "Die Aufnahme baut sich wieder eine eigene Kamera – dann gibt es sie zweimal."
    )
    assert "toBlob" in shot, "Das Einzelbild aus dem Strom fehlt."
    for leak in ("type=\"file\"", "type='file'", "input type=", "accept=\"image", "<input"):
        assert leak not in shot, (
            f"«{leak}» ist zurück – der Dateidialog ist damit ein zweiter Weg zu einem "
            f"Nachweis, der genau einen haben darf."
        )

    form = _code(_read(FRONTEND / "components" / "erp" / "capture-form.tsx"))
    assert "PhotoShot" in form, "Der Erfassungspunkt «Bild» benutzt die Aufnahme nicht."
    assert "asList(" not in form, (
        "Der Sammel-Pfad ist zurück – ein Punkt trägt genau ein Bild."
    )


def test_the_object_scan_capture_type_is_gone():
    """**Ersatzlos entfernt** (Testnotiz #719) – und zwar überall, nicht nur im Menü.

    Ein Typ, den die Registry noch kennt, aber niemand anbietet, ist ein toter Pfad: er
    steht in jeder Definition, die ihn je getragen hat, und er würde zur Laufzeit wieder
    auftauchen. Ein Rest im Frontend (Symbol, Beschriftung) wäre dasselbe eine Ebene
    höher.

    *Der Nachweis für **Werkzeug und Prüfmittel**, den dieser Typ getragen hat, ist damit
    nirgends mehr abgebildet – bewusst und vermerkt in ``SYSTEM_LOGIC.md``, nicht
    stillschweigend gestrichen.*
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import capture_types as ct

    assert "object" not in ct.ALL, "Der Typ steht wieder in der Registry."
    assert not (BACKEND / "app" / "domain" / "capture_types" / "object_scan.py").exists()

    for path in (FRONTEND / "lib" / "modules.ts",
                 FRONTEND / "components" / "erp" / "capture-form.tsx",
                 FRONTEND / "components" / "erp" / "process-designer.tsx"):
        body = _code(_read(path))
        assert "Objekt scannen" not in body, f"{path.name} bietet den Typ wieder an."


def test_the_module_dictates_its_transition():
    """«Fest verdrahtet, nicht einstellbar»: der Übergang gehört zum Modultyp.

    Damit gibt es beim Anlegen keine Status-Auswahl mehr – die einzige richtige Antwort
    stand schon fest, und jede andere ergäbe einen Prozess, der nicht läuft.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules, statuses as st

    m = modules.get(modules.DATENERFASSUNG)
    assert (m.status_before, m.status_after) == (st.IM_PROZESS, st.IM_PROZESS), (
        "Die Datenerfassung ist ein Durchläufer – sie misst, sie verändert nichts."
    )
    schema = _read(BACKEND / "app" / "schemas" / "process.py")
    assert "status_before" not in _body(schema, "ModuleInput", kind="class"), (
        "Der Übergang darf nicht mehr eingegeben werden."
    )
    editor = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    assert "STATUS_VALUES" not in editor and "statusLabel" not in editor, (
        "Der Editor bietet wieder eine Status-Auswahl an."
    )
    # Das Testmodul ist ersatzlos weg – es war ein Testvehikel, kein Modul.
    assert "testmodul" not in _read(BACKEND / "app" / "models" / "process_step.py")
    assert "testmodul" not in _read(FRONTEND / "components" / "erp" / "order-detail.tsx")


def test_capture_is_written_in_the_process_and_read_there_too():
    """Eine Erfassung entsteht, wenn ein Stück vor einem Modul steht – sonst nie.

    Und **gelesen wird sie am Prozess, nicht am Stück** (Testnotiz #677): die frühere
    Historie am Instanz-Detail war eine zweite Ansicht auf dieselbe Sache, an einem Ort,
    an dem man nicht arbeitet. Die Zeilen selbst bleiben – sie sind der Nachweis, nicht
    die Ansicht.
    """
    assert not (BACKEND / "app" / "routers" / "captures.py").exists(), (
        "Der Erfassungs-Endpunkt ist wieder da – eine zweite Tür zu derselben Sache."
    )
    assert not (FRONTEND / "components" / "erp" / "capture-panel.tsx").exists()
    assert "captures.router" not in _read(BACKEND / "app" / "main.py")

    svc = _read(BACKEND / "app" / "services" / "capture.py")
    assert "def record_for_step" in svc, "Erfasst wird nicht mehr im Prozess."
    assert "def history" not in svc, "Die Historie am Stück ist wieder da."

    model = _read(BACKEND / "app" / "models" / "capture.py")
    for column in ("order_id", "step_id"):
        assert column in model, (
            f"Die Erfassung trägt kein «{column}» – dann steht sie ohne Anlass da."
        )

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


def test_module_and_capture_icons_cover_exactly_the_backend_keys():
    """Symbole sind das Einzige, was die Oberfläche selbst hält – und sie müssen die
    Backend-Listen **genau** abdecken: ein Typ ohne Symbol wäre eine leere Fläche, ein
    Symbol ohne Typ eine tote Zeile."""
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import capture_types as ct, modules

    ts = _read(FRONTEND / "lib" / "modules.ts")

    def keys(const: str) -> set[str]:
        body = ts.split(f"export const {const}")[1].split("};")[0]
        return set(re.findall(r"^\s{2}(\w+):", body, re.M))

    assert keys("CAPTURE_ICON") == set(ct.KEYS)
    assert keys("MODULE_ICON") == set(modules.KEYS)


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

    process = _read(BACKEND / "app" / "services" / "process.py")
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
    body = _body(_read(BACKEND / "app" / "services" / "process.py"), "release")
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
    assert "ix-palette" in designer and "ix-palette-name" in designer
    css = _read(FRONTEND / "app" / "globals.css")
    assert ".ix-palette-name" in css, "Der Hover-Name der Palette hat keine Darstellung."


def test_the_module_colour_comes_from_the_registry():
    """**Ein neuer Modultyp = ein Eintrag in der Liste, kein Eingriff in die UI.**

    Welche Farbfamilie ein Modul trägt, sagt das Backend (`Module.tone`); die Oberfläche
    hält nur die konkreten Farbwerte. Stünde die Zuordnung in einer Komponente, wäre der
    nächste Modultyp eine Änderung an ihr.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    assert set(modules.TONES) == set(modules.KEYS)
    ts = _read(FRONTEND / "lib" / "modules.ts")
    tones = set(re.findall(r"^  (\w+): \{ bg:", ts.split("MODULE_TONE")[1], re.M))
    assert set(modules.TONES.values()) <= tones, (
        "Das Backend nennt eine Farbfamilie, die die Oberfläche nicht kennt."
    )
    for name in ("process-diagram.tsx", "process-designer.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "moduleTone" in src, f"{name} liest die Farbe nicht aus der einen Stelle."
        assert "#" not in re.sub(r"//.*|/\*.*?\*/", "", src, flags=re.S).replace("#'", ""), (
            f"{name} enthält einen harten Farbwert – Farben stehen in lib/modules."
        )


def test_the_swiss_thousands_separator_is_pinned():
    """**Ein Betrag sieht überall gleich aus** – auch in verschiedenen Laufzeiten.

    ``toLocaleString('de-CH')`` liefert je nach ICU-Fassung ein typografisches ``’``
    (U+2019, so im Browser) oder ein gerades ``'`` (U+0027, so in Node) – gemessen. Das
    Design-System schreibt den geraden fest (``9'999 CHF``); und dieselbe Zahl darf nicht
    je nach Laufzeit anders aussehen: server- und clientseitig gerendert wären das zwei
    Texte an derselben Stelle, und React wirft die Seite weg (Hydrations-Fehler).

    Bug-Form: ein Aufrufer formatiert selbst statt über ``formatAmount``.
    """
    utils = _read(FRONTEND / "lib" / "utils.ts")
    assert "\\u2019" in utils and "formatAmount" in utils, (
        "Der Tausender-Trenner ist nicht festgeschrieben."
    )
    for name in ("purchase-work.tsx",):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "toLocaleString" not in src, (
            f"{name} formatiert selbst – dann gilt die Regel dort nicht."
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
    # Der Beleg steht ausserhalb der Verzweigung – er gehört zum Modul, nicht zum Moment.
    body = src[src.index("const stepBody ="):src.index("// **Ohne Prozessbild")]
    assert body.index("<Wrapped") < body.index("{isActive ?"), (
        "Der Beleg steht wieder innerhalb der Aktiv-Verzweigung."
    )

    panel = _read(FRONTEND / "components" / "erp" / "purchase-work.tsx")
    assert "(stage.active || stage.done)" in panel, (
        "Eine Stufe zeigt ihren Inhalt nur, solange sie dran ist – danach steht dort "
        "nichts mehr, obwohl genau dort steht, was passiert ist."
    )


def test_the_purchase_panel_asks_for_nothing_the_process_already_knows():
    """**Menge und Termin sind keine Eingaben** (Testnotizen #741/#745).

    Die Menge sagen die Einzelinstanzen vor dem Modul; der Termin ist aus Bestelldatum
    und Lieferfrist ableitbar. Beide zu tippen wären zweite Aussagen über dieselbe Sache.

    Und **ohne Lieferfrist keine Offerte** (#743) – die Regel steht im Dienst, hier ist
    sie die freundliche Hälfte: der Knopf bleibt zu.
    """
    panel = _read(FRONTEND / "components" / "erp" / "purchase-work.tsx")
    for gone in ("<Label>Menge</Label>", "<Label>Termin</Label>", "type=\"date\"",
                 "due_date", "quantity: Number("):
        assert gone not in panel, f"«{gone}» ist wieder da – der Prozess weiss das schon."
    assert "const ready = price.trim() !== '' && lead.trim() !== ''" in panel, (
        "Eine Offerte lässt sich wieder ohne Lieferfrist abschicken."
    )
    # #748: Auto-Save wie überall im Haus – der Speichern-Knopf war die einzige Stelle
    # im ERP mit einem, und er sah aus, als täte er nichts.
    assert "useAutosave" in panel and "Übernehmen" not in panel, (
        "Der Beleg hat wieder einen Speichern-Knopf statt Auto-Save."
    )
    # #742: die Zeile ist der Schalter, kein Häkchen daneben.
    assert 'type="checkbox"' not in panel, (
        "Die Lieferantenwahl ist wieder eine Häkchen-Liste."
    )


def test_the_purchase_module_has_no_article_field():
    """**Was beschafft wird, sagt der Prozess; was zu tun ist, sagt das Modul.**

    Das Artikelfeld am Beschaffungs-Modul war eine zweite Aussage über dieselbe Sache –
    die Einzelinstanzen vor dem Modul tragen ihren Artikel. Was fehlte, war der
    **Auftrag** an den Lieferanten: die Spezifikation beschreibt die Sache, nicht was mit
    ihr geschehen soll.

    Bug-Formen: (a) der Editor fragt wieder nach einem Artikel; (b) der Beleg zeigt einen
    einzelnen Artikel statt seiner Zeilen; (c) der Auftrag ist optional.
    """
    designer = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    assert "Was bestellt wird" not in designer and "purchaseArticle" not in designer, (
        "Der Editor fragt wieder nach einem Artikel – der steht im Prozess."
    )
    assert "Auftrag an den Lieferanten" in designer, (
        "Der Auftrag an den Lieferanten fehlt – ohne ihn weiss er, WAS das Teil ist, "
        "aber nicht, was er tun soll."
    )

    modules_ts = _read(FRONTEND / "lib" / "modules.ts")
    assert "purchaseArticle" not in modules_ts, "Der Entwurf trägt wieder einen Artikel."
    assert "kein Auftrag an den Lieferanten" in modules_ts, (
        "Ein Beschaffungs-Modul ohne Auftrag gilt wieder als vollständig."
    )

    panel = _read(FRONTEND / "components" / "erp" / "purchase-work.tsx")
    assert "p.article_name" not in panel and "p.quantity" not in panel, (
        "Der Beleg zeigt wieder EINEN Artikel mit EINER Menge – zwei Artikel vor dem "
        "Modul sind aber zwei Zeilen auf einem Beleg."
    )
    assert "p.lines.map" in panel and "p.instruction" in panel, (
        "Der Beleg zeigt seine Zeilen oder seinen Auftrag nicht."
    )
    assert "l.spec" in panel, (
        "Die Spezifikation steht nicht auf dem Beleg – sie ist die eine Auskunft, die "
        "der Lieferant über die Sache bekommt."
    )


def test_the_module_looks_the_same_for_both_roles():
    """►►► **Eine Ansicht, zwei Rollen – und keine Rollenabfrage.** ◄◄◄ (Testnotiz #751)

    Personal und Lieferant sehen dieselbe Karte; was sie unterscheidet, ist einzig, **was
    man hier tun darf** – und das sagt der Beleg (`purchase.can`). Die Oberfläche fragt
    `may(...)`, nicht die Rolle: eine Rollenabfrage dort wäre die zweite Stelle für
    dieselbe Regel, und sie würde beim nächsten Verb vergessen.

    Bug-Formen: (a) `purchase-work` fragt nach der Rolle; (b) eine Aktion rendert wieder
    ungeprüft, sobald die Stufe aktiv ist; (c) das interne Modul-Protokoll steht in der
    verengten Ansicht.
    """
    panel = _read(FRONTEND / "components" / "erp" / "purchase-work.tsx")
    # **Die Bug-Form ist ein Rollenvergleich**, nicht das Wort «Lieferant» in der Prosa:
    # `q.supplier_object_id` ist eine Objektnummer, `role === 'supplier'` wäre die zweite
    # Stelle für dieselbe Regel.
    for role in ("role", "'supplier'", '"supplier"', "isSupplier", "isStaff"):
        assert role not in panel, (
            f"«{role}» steht wieder im Beleg – was jemand darf, sagt `can`, nicht seine Rolle."
        )
    assert "function may(" in panel, "Die eine Rechte-Frage der Komponente fehlt."
    for verb in ("'ask'", "'revoke'", "'order'", "'quote'", "'note'",
                 "'clarified'", "'receive'"):
        assert f"may(p, active, {verb})" in panel, (
            f"Die Aktion {verb} wird nirgends geprüft – für einen Lieferanten wäre sie "
            f"ein Knopf, der nie etwas tun kann."
        )
    # **Und `active` allein ist NIE das Tor.** Der erste Anlauf dieses Wächters prüfte
    # bloss, ob jedes Verb *irgendwo* in der Datei geprüft wird – er liess damit genau
    # die Bug-Form durch, gegen die er gebaut war (eine Aktion zurück auf `active`, das
    # Verb steht ja noch anderswo). Gemessen und nachgeschärft: gefragt wird nach der
    # **Form des Tors**, nicht nach dem Vorkommen eines Wortes.
    for gate in ("&& active && (", "{active && ("):
        assert gate not in panel, (
            f"«{gate}» rendert eine Aktion nur danach, ob das Modul dran ist – ob man "
            f"sie tun DARF, sagt `can`."
        )
    # #750: ein Wort, immer dasselbe – die Zahl fiel ausgerechnet dann weg, wenn sie am
    # grössten ist.
    assert "Bei {picked.length} anfragen" in panel and "? 'Anfragen'" not in panel, (
        "Der Anfrage-Knopf hat wieder zwei Beschriftungen."
    )
    # Das Verb der Stufe kommt vom Server – `PurchaseStage.verb` war sonst ein Feld,
    # das niemand liest.
    assert "verbOf(p)" in panel, "Der Bestell-Knopf erfindet sein Wort wieder selbst."

    src = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "{internal && !isActive && <StepRecord" in src, (
        "Das Modul-Protokoll steht wieder in jeder Ansicht – sein Endpunkt ist "
        "Personal-only, ein Lieferant bekäme dort einen Fehler."
    )


def test_the_order_reference_moved_into_the_definition():
    """**Zwei Fragen, zwei Orte** (Testnotiz #753).

    Wie man bei einem Lieferanten bestellt, steht bei ihm in der **Definition**; die
    Sendungsnummer entsteht erst nach der Bestellung.

    Bug-Form: das alte Sammelfeld «Bestellnummer, Link, Sendungsnummer» ist zurück.
    """
    panel = _read(FRONTEND / "components" / "erp" / "purchase-work.tsx")
    assert "Bestellnummer, Link, Sendungsnummer" not in panel, (
        "Das Sammelfeld ist zurück – es beantwortete zwei Fragen zu zwei Zeitpunkten."
    )
    assert "<Label>Sendungsnummer</Label>" in panel, "Die Sendungsnummer fehlt am Beleg."
    assert "q.ref" in panel, (
        "Die Bestellangabe erreicht die Angebotszeile nicht – dann steht nirgends, unter "
        "welcher Nummer man bei ihm bestellt."
    )
    designer = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    assert "Artikelnummer oder Link beim Lieferanten" in designer, (
        "Die Bestellangabe lässt sich nicht mehr definieren."
    )


def test_the_scan_chip_carries_the_global_symbol():
    """**Ein Scan sucht einen Datensatz – also trägt er dessen Symbol** (Testnotiz #754).

    `ScanStep.kind` versprach seit jeher «erwarteter Objekttyp → Symbol im Scanner»;
    gerendert wurde nie eines. Symbol **und Wort** kommen jetzt aus `TYPE_META` – der
    Quelle, aus der auch der Feed und jeder Detail-Kopf sie nehmen.

    Bug-Formen: (a) der Chip bleibt reiner Text; (b) eine Aufrufstelle schreibt die Sorte
    wieder von Hand hin.
    """
    lib = _read(FRONTEND / "lib" / "erp-record.ts")
    assert "SCAN_RECORD_TYPE" in lib, "Die Zuordnung Scan-Sorte → Datensatztyp fehlt."
    scan = _read(FRONTEND / "lib" / "scan.ts")
    assert "export function scanKindLabel" in scan, "Die eine Auflösung der Sorte fehlt."
    dialog = _read(FRONTEND / "components" / "scan" / "scan-dialog.tsx")
    # Nach dem **Rendern** gefragt, nicht nach der Deklaration: die erste Fassung prüfte
    # nur, ob der Name vorkommt – und liess damit die Bug-Form durch (Symbol berechnet,
    # aber nicht gezeichnet).
    assert "<KindIcon size=" in dialog and "TYPE_META" in dialog, (
        "Der Scan-Chip zeichnet kein Symbol – `kind` verspricht seit jeher eines."
    )
    for name in ("capture-work.tsx", "definition-lines.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "label: 'Instanz'" not in src, (
            f"{name} schreibt die Sorte wieder von Hand hin – sie steht in `TYPE_META`."
        )


def test_a_supplier_sees_his_module_without_the_process_picture():
    """**Die Lieferanten-Sicht ist eine Spiegelung** (Testnotiz #747).

    Der Server verengt die Antwort (``orders._mine_only``); die Oberfläche zeichnet
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
    from app.domain import capture_types
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

    # Und die Altdaten tragen ihn auch nicht mehr mit sich herum.
    mig = _read(BACKEND / "alembic" / "versions" / "107_status_und_name.py")
    assert "p - 'required'" in mig, "Die Migration räumt den Schlüssel nicht aus den Zeilen."


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


def test_the_net_adds_a_column_before_it_throws_a_table_away():
    """**Ein Neuaufbau ist das letzte Mittel, nicht die erste Reaktion.**

    ``start.sh`` startet uvicorn auch dann, wenn Alembic scheitert – dann zählt nur noch
    das Netz (Lehre aus Migration 090). Lief der Formwächter zuerst, warf er bei einer
    bloss **fehlenden** Spalte die ganze Tabelle weg, obwohl der Eintrag daneben sie in
    einer Zeile ergänzt hätte: auf einer 106er-Datenbank war der Alt-Auftrag danach
    spurlos verschwunden.

    Also erst die Spalten, dann die Form – und der Neuaufbau ist die Antwort auf das,
    was auch danach noch unbenutzbar ist.
    """
    body = _body(_read(BACKEND / "app" / "main.py"), "_run_startup_fixups_once")
    assert body.index("_ensure_columns()") < body.index("_ensure_rebuilt_tables_shape()"), (
        "Der Formwächter läuft vor dem Spaltennetz – eine fehlende Spalte kostet dann "
        "die ganze Tabelle."
    )


def test_the_column_net_reflects_on_its_own_connection():
    """Der Inspektor sitzt auf **derselben** Verbindung wie die DDL.

    ``inspect(engine)`` zieht eine zweite Verbindung aus dem Pool; die blockiert, sobald
    diese Funktion eine Tabelle geändert hat, denn das ``ALTER TABLE`` hält seinen Lock
    bis zum ``commit`` ganz am Ende. Sie wartet damit auf eine Transaktion, die erst nach
    ihr fertig wird – der Start bliebe für immer stehen (gemessen: der erste
    ``DROP COLUMN`` auf ``instances`` hat es ausgelöst).
    """
    body = _body(_read(BACKEND / "app" / "main.py"), "_ensure_columns")
    assert "inspect(conn)" in body, (
        "Das Spaltennetz reflektiert auf einer zweiten Verbindung – das verklemmt sich "
        "mit seiner eigenen offenen Transaktion."
    )
    code = re.sub(r"#.*", "", body)   # der Kommentar erklärt ja gerade den Fehler
    assert "inspect(engine)" not in code


def test_the_capture_point_shape_mirrors_the_backend():
    """``CapturePoint`` steht von Hand im Frontend – und muss dem Backend gleichen.

    Von Hand, weil ``process_steps.config`` ein **freies** Objekt ist: was darin steht,
    entscheidet der Modultyp. Es fest zu typisieren nagelte die Konfiguration aller
    künftigen Modultypen auf die des heutigen einen fest. Ein Spiegel darf darum
    existieren – aber nicht unbemerkt auseinanderlaufen.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.process import CapturePoint

    ts = _body(_read(FRONTEND / "types" / "index.ts"), "CapturePoint", kind="interface")
    fields = set(re.findall(r"^  (\w+)\??:", ts, re.M))
    assert fields == set(CapturePoint.model_fields), (
        f"Erfassungspunkt läuft auseinander: Backend {sorted(CapturePoint.model_fields)} "
        f"≠ Frontend {sorted(fields)}"
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
    from app.models import Order, ProcessEvent

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
    main = _read(BACKEND / "app" / "main.py")
    assert "ix_process_events_unit_timeline" in main, (
        "Der Journey-Index fehlt im Lifespan-Netz."
    )


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
    assert "<select" not in src, "Der Erfassungstyp hat wieder ein Auswahlfeld."
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
    from app.services import process as process_svc

    # Eine Quelle: der Feed leitet ab wie das Detail.
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "process_svc.order_statuses" in router and "process_svc.order_status" in router
    assert hasattr(process_svc, "order_statuses")

    api = _read(FRONTEND / "lib" / "api.ts")
    assert "function notifyDataChanged" in api, "Die Meldestelle fehlt."
    assert "if (!idempotent) notifyDataChanged(path);" in api, (
        "Nicht jede schreibende Anfrage meldet – dann bleibt der Feed irgendwann stehen."
    )
    # Und kein zweiter Melde-Weg in den Detailfenstern.
    for name in ("order-detail.tsx", "article-detail.tsx", "instance-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "inexxio:data-changed" not in src, (
            f"{name} meldet selbst – das ist der zweite Weg."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Abweichungsaufträge
# ═════════════════════════════════════════════════════════════════════════════


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
    proc = _read(BACKEND / "app" / "services" / "process.py")
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
    proc = _read(BACKEND / "app" / "services" / "process.py")
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
    proc = _read(BACKEND / "app" / "services" / "process.py")
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
    for field in ("steps", "flow", "active_step_id", "end_status"):
        assert field in related, f"«{field}» fehlt – der Nachbar kann nicht gerendert werden."


def test_many_deviations_are_cut_off_and_say_so():
    """Bei vielen Abweichungen wird **abgeschnitten und die Zahl genannt** (§4).

    Gruppieren wäre hier falsch: zwei Abweichungen sind zwei verschiedene Abläufe, eine
    Gruppe daraus sagte nichts. Eine stumm gekappte Liste sähe aus wie alles.
    """
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "RELATED_LIMIT" in router, "Es gibt keine Grenze – die Antwort wächst unbegrenzt."
    assert "deviation_total=len(branches)" in router, (
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
    proc = _read(BACKEND / "app" / "services" / "process.py")
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
    proc = _read(BACKEND / "app" / "services" / "process.py")
    assert "def pending_returns(" in proc, "Es gibt keine Ableitung, worauf ein Modul wartet."
    assert "pending_returns(db, order).get(step.id)" in _body(proc, "confirm_step"), (
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


def test_the_header_is_defined_once_for_every_record_type():
    """**#697 — Layout, Raster, Farben, Schriften: global, nicht je Datensatztyp.**

    Was variieren darf, ist der **Inhalt**. Symbol, Farbfamilie und Eyebrow kommen darum
    aus der einen Quelle (``lib/erp-record.TYPE_META``) und werden **im Kopf** aufgelöst –
    vorher reichte jede Ansicht sie einzeln herein, drei davon mit hart getippten
    Hex-Werten und einem zweiten Mal ausgeschriebenem Namen.
    """
    fields = _read(FRONTEND / "components" / "erp" / "fields.tsx")
    assert "type: ErpRecordType;" in fields, "Der Kopf kennt den Datensatztyp nicht."
    assert "TYPE_META[type]" in fields, "Der Kopf löst die Identität nicht selbst auf."

    for name in ("article-detail", "instance-detail", "order-detail",
                 "organization-detail", "user-detail"):
        src = _read(FRONTEND / "components" / "erp" / f"{name}.tsx")
        head = src[src.index("<DetailHeader"):]
        head = head[:head.index("/>") if "/>" in head[:4000] else 4000]
        for forbidden in ("iconBg=", "iconFg=", "eyebrow=", "avatar="):
            assert forbidden not in head, (
                f"{name} bringt eine eigene Kopf-Definition mit ({forbidden})."
            )
        assert 'type="' in head, f"{name} nennt seinen Datensatztyp nicht."


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


def test_an_unfinished_capture_point_is_a_missing_entry_not_a_field_error():
    """**#695 — dieselbe Klasse wie #682/#686, eine Ebene tiefer.**

    Der Entwurf legt einen Erfassungspunkt beim Klick an und füllt ihn beim Tippen. Eine
    Schema-Pflicht machte daraus bei jedem Tastendruck einen rohen Feldpfad-Fehler
    («Erfassungspunkte → 1 → Bezeichnung: darf nicht leer sein»). Verlangt wird sie darum
    bei der **Freigabe** – mit einem Satz statt einem Feldpfad.
    """
    schema = _code(_read(BACKEND / "app" / "schemas" / "process.py"))
    assert "min_length" not in schema, (
        "Die Bezeichnung ist schema-pflichtig – dann scheitert /validate beim Tippen."
    )
    types = _read(BACKEND / "app" / "domain" / "capture_types" / "__init__.py")
    assert "braucht noch eine Bezeichnung" in types, "Bei der Freigabe wird sie nicht verlangt."


def test_new_is_an_origin_on_its_own():
    """**#693 — mit «Neu» kommt keine zweite Zeile dazu, und umgekehrt.**

    Ein Erzeugungsauftrag fährt die Vorlage genau dieses Artikels; ihr Versionsstempel
    gilt nur für seine Stücke. Die Regel steht **serverseitig** – ein fehlender Knopf ist
    keine Absicherung.
    """
    proc = _read(BACKEND / "app" / "services" / "process.py")
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


def test_the_origin_uses_the_shared_switch():
    """**#694 — Neu/Lager ist derselbe Schiebe-Regler wie die Mengeneinheit.**"""
    ui = _read(FRONTEND / "components" / "erp" / "definition-lines.tsx")
    assert "IconSwitch, inputCls } from '@/components/erp/fields'" in ui, (
        "Der Regler wird nicht aus dem gemeinsamen Vokabular geholt."
    )
    # Geprüft wird die **Verdrahtung**, nicht das Vorkommen des Wortes: der Regler muss
    # an der Herkunft hängen, sonst steht er irgendwo und die Knöpfe stehen daneben.
    assert "value={line.origin}" in ui, "Der Regler hängt nicht an der Herkunft."
    assert "function OriginBtn(" not in ui, "Der nachgebaute Knopf steht noch da."


def test_the_release_hint_is_not_repeated_in_the_body():
    """**#692 — «Zur Freigabe fehlt …» entfällt; der ausgegraute Knopf sagt es.**"""
    art = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "Zur Freigabe fehlt" not in _code(art)
    assert "Es fehlt:" in art, "Auch der Hover nennt den Grund nicht mehr."
    order = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "Zur Freigabe fehlt" not in _code(order)


def test_the_palette_symbol_is_centred():
    """**#691 — kein Abstand zum eingeklappten Namen, sonst sitzt das Symbol daneben.**

    Der Name ist ein Flex-Kind mit ``max-width: 0`` – ein ``gap`` gilt aber auch zu einem
    nullbreiten Kind. Zentral gelöst: es gibt genau einen Modul-Knopf.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    palette = css[css.index(".ix-palette {"):css.index(".ix-palette-sm")]
    assert "gap: 0;" in palette, "Der Abstand gilt auch eingeklappt – das Symbol sitzt daneben."
    assert "gap: 7px;" in css[css.index(".ix-palette:hover"):][:200], (
        "Aufgeklappt fehlt der Abstand zum Namen."
    )


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
    proc = _read(BACKEND / "app" / "services" / "process.py")
    body = _body(proc, "started_at")
    assert "ProcessEvent" in body and "KIND_START" in body, "Der Zeitpunkt kommt nicht aus dem Log."
    model = _read(BACKEND / "app" / "models" / "order_unit.py")
    assert "started_at" not in model, "Es gibt eine zweite Wahrheit als Spalte."
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "startedAt" in diagram, "Der Hover zeigt den Zeitpunkt nicht."


def test_the_header_never_mixes_font_shorthand_with_a_conditional_override():
    """**Warum der Auftragsname trotz EINER Kopf-Definition anders aussah.**

    Die Standardisierung hatte gegriffen – das Stilobjekt ist für jeden Datensatztyp
    dasselbe. Der Unterschied kam aus der **Kurzschreibweise**: `DH.title` setzte
    `font: '800 26px …'`, und `DH.titleEmpty` überschrieb daneben `fontWeight`. Fällt die
    Überschreibung später weg – beim Auftrag passiert genau das, weil er als einziger
    Typ ohne Namen startet und ihn nachlädt –, entfernt React die Longhand, indem es sie
    auf `''` setzt. Der Wert aus der Kurzschreibweise kommt dabei **nicht** zurück: sie
    hat ihn in die Deklaration geschrieben, und das Löschen der Longhand löscht ihn
    daraus. Übrig blieb der Initialwert, 400 statt 800.

    Die Regel ist darum allgemein: **ein Stilobjekt, das konditional überschrieben wird,
    benutzt keine `font`-Kurzschreibweise.** Sonst hängt das Ergebnis davon ab, ob die
    Überschreibung je aktiv war – und das ist ein Zustand, kein Entwurf.
    """
    fields = _read(FRONTEND / "components" / "erp" / "fields.tsx")
    header = _body(fields, "DetailHeader", kind="function")

    # Welche DH-Stile werden im Kopf konditional zusammengeführt?
    overridden = set(re.findall(r"\.\.\.DH\.(\w+),\s*\.\.\.\(", header))
    overridden |= {m for m in re.findall(r"\.\.\.\(\w+ \? null : DH\.(\w+)\)", header)}
    assert "title" in overridden or "titleEmpty" in " ".join(overridden) or overridden, (
        "Im Kopf wird kein Stil mehr konditional überschrieben – dann ist dieser "
        "Wächter blind. Prüfen, ob die Regel noch gebraucht wird."
    )

    block = fields[fields.index("export const DH"):]
    for name in overridden | {"title"}:
        style = re.search(rf"\n  {name}: \{{(.*?)\n  \}},", block, re.S)
        assert style, f"DH.{name} nicht gefunden."
        assert not re.search(r"\bfont:", style.group(1)), (
            f"DH.{name} wird konditional überschrieben und benutzt trotzdem die "
            f"`font`-Kurzschreibweise. Fällt die Überschreibung weg, kommt der Wert "
            f"nicht zurück – genau so wurde der Auftragsname 400 statt 800."
        )


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


def test_the_origin_has_no_state_that_only_a_detour_can_reach():
    """**Die Vorauswahl «Lager» IST der Wert, nicht seine Anzeige.**

    ``origin`` war ``… | null``, angezeigt wurde aber ``origin ?? LAGER``: der Regler stand
    auf «Lager», der Zustand sagte «nichts». Alles, was an ``origin === LAGER`` hing – die
    Instanz-Auswahl und damit die FIFO-Vorauswahl – lief deshalb nicht an, und die Zeile
    fiel beim Absenden aus dem Nutzdatensatz («keine Einzelinstanz gewählt»). Erreichbar
    wurde der Zustand nur über den Umweg *einmal umschalten und zurück*.

    Ein angezeigter Zustand, den es in den Daten nicht gibt, ist kein Vorzustand, sondern
    ein Widerspruch.
    """
    code = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    assert re.search(r"origin: typeof NEU \| typeof LAGER;", code), (
        "`origin` trägt wieder einen dritten Wert – dann weicht die Anzeige wieder vom "
        "Zustand ab."
    )
    assert "origin ??" not in code, (
        "Die Herkunft wird für die Anzeige wieder ersetzt (`origin ?? …`) – genau so "
        "entstand ein Regler, dessen Stellung nichts auslöst."
    )
    assert "origin: null" not in code, "Die Zeile startet wieder ohne Herkunft."

    # **Der Vorschlag kommt vom Server** (Testnotiz #740). Er aus der geladenen Seite zu
    # ziehen war der Fehler: sind die ersten Stücke verbaut, findet die Oberfläche
    # nichts, obwohl freie da sind. FIFO ist eine Regel, keine Anzeige.
    assert "preselect: quantity" in code, (
        "Die Oberfläche bittet nicht mehr um die Vorauswahl – dann baut sie sie wieder "
        "selbst, aus einer gekappten Seite."
    )
    effect = re.search(
        r"useEffect\(\(\) => \{\s*if \(!preselect\?\.length \|\| chosen\.length\)"
        r"[\s\S]*?\}, \[([^\]]*)\]\);", code)
    assert effect, "Die Übernahme der Vorauswahl ist nicht mehr auffindbar."
    deps = {d.strip() for d in effect.group(1).split(",") if d.strip()}
    assert deps == {"preselect"}, (
        f"Die Übernahme hängt an {sorted(deps)}. Sie entsteht nur ins Leere: was der "
        f"Mensch gewählt hat, darf sie nie überschreiben."
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

    svc = _code(_read(BACKEND / "app" / "services" / "process.py"))
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


def test_nothing_invisible_decides_the_width():
    """**Seitwärts scrollen ist verboten** (Testnotiz #703) – auch versehentlich.

    Der Hover-Tooltip ist absolut positioniert und bis 240 px breit. Ein absolut
    positioniertes Kind zählt zur *scrollable overflow area* seiner Vorfahren – auch
    unsichtbar bei ``opacity: 0``. An einem 46-px-Symbol schob er damit den nächsten
    ``overflow-auto``-Container über seine Breite hinaus, und der Browser bot seitwärts
    scrollen über leere Fläche an. Gemessen: 991 → 1007 px, an jeder Fensterbreite.

    Was man nicht sieht, darf die Breite nicht bestimmen.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    tip = css[css.index("[data-tip]::after"):]
    tip = tip[:tip.index("}")]
    assert "display: none" in tip, (
        "Der Tooltip liegt wieder dauerhaft im Layout – dann scrollt irgendein Container "
        "seitwärts über leere Fläche."
    )
    assert "opacity: 0" not in tip, (
        "Unsichtbar über `opacity` heisst: trotzdem im Layout. Genau das war der Fehler."
    )


def test_a_scrollbar_never_changes_the_available_width():
    """**Kein sichtbarer Scrollbalken – generell, an genau einer Stelle.**

    Ein Balken kostet auf Windows und Linux echte Breite. Erscheint er, weil ein
    Aufklappen die Seite verlängert, wird der Inhalt schmaler und alles Zentrierte
    **springt seitlich** – mitten in einer Bedienung. Gescrollt wird weiterhin ganz
    normal; nur die Leiste verschwindet, und damit die Breite, die sich ändern könnte.

    **Global, nicht je Container.** Ein Klassenname ist eine Bitte: er hilft dort, wo
    jemand daran gedacht hat, und der nächste ``overflow: auto`` fängt wieder an zu
    springen. Genau darum darf es die frühere Einzelklasse nicht mehr geben.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    assert "* { scrollbar-width: none" in css, (
        "Die Regel steht nicht global – dann entscheidet je Container, ob es springt."
    )
    assert "*::-webkit-scrollbar" in css, "WebKit blendet die Leiste nicht aus."
    assert ".ix-noscrollbar" not in css, (
        "Die Einzelklasse ist zurück – zwei Wahrheiten für dieselbe Regel."
    )
    for path in FRONTEND.rglob("*.tsx"):
        assert "ix-noscrollbar" not in _read(path), (
            f"{path.name} bittet noch einzeln um eine unsichtbare Leiste."
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
    assert "data-tip={history} data-tip-list={history ? '' : undefined}" in head, (
        "Das Modul trägt die Historie gar nicht mehr."
    )


def test_only_one_bubble_at_a_time():
    """**Eine Blase, und zwar die unter dem Zeiger.**

    Zwei Wege führten dazu, dass zwei gleichzeitig standen:

    * **Geschachtelt** – zeigt man auf das innere `[data-tip]`, ist das äussere ebenfalls
      «hover». Gemeint ist immer das genauere.
    * **Fokus nach Klick** – ein Mausklick setzt Fokus, und die Blase blieb danach
      stehen, während der Zeiger längst woanders war. Der Fokus-Weg ist für Touch und
      Tastatur gedacht; mit Maus zählt darum nur `:focus-visible`.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    assert "[data-tip]:has([data-tip]:hover)::after" in css, (
        "Die innere Blase gewinnt nicht mehr – geschachtelt stehen wieder zwei."
    )
    assert "@media (hover: none)" in css and "@media (hover: hover)" in css, (
        "Der Fokus-Weg ist nicht mehr nach Eingabeart getrennt."
    )
    focus = css.split("@media (hover: hover)")[1][:200]
    assert ":focus-visible::after" in focus and ":focus::after" not in focus, (
        "Mit Maus zeigt ein Klick wieder eine Blase, die dann stehen bleibt."
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
# Reiter «Bestand» — wie viel, in welchem Zustand, unter welcher Nummer
# ---------------------------------------------------------------------------

def test_the_stock_is_answered_at_exactly_one_place():
    """**Eine Frage, ein Endpunkt** – und die Aufstellung ersetzt den Zustand.

    Der Vorgänger las ``Instance.status``, eine Spalte, die es nicht gibt: jeder Aufruf
    endete mit 500, der Reiter war nie zu sehen. Die eigentliche Lehre steckt aber nicht
    im Tippfehler, sondern darin, warum es ihn geben konnte – eine Gruppe hat keinen
    Zustand (Testnotiz #675), und wer trotzdem einen liest, greift ins Leere. Was sie
    hat, ist eine **Aufstellung**: 3 freigegeben, 1 im Prozess.

    Daneben darf keine zweite Tür zu derselben Frage stehen; der frühere Filter
    ``article_object_id`` am Instanz-Feed war genau das, ohne einen einzigen Aufrufer.
    """
    router = _read(BACKEND / "app" / "routers" / "articles.py")
    assert "status=i.status" not in router, (
        "Der Bestand liest wieder einen Zustand an der Instanz – die Spalte gibt es nicht."
    )
    assert "/{object_id}/stock" in router, "Es gibt keinen Bestands-Endpunkt."
    assert "/{object_id}/instances" not in router, (
        "Neben dem Bestand steht wieder eine reine Instanzliste – zwei Wege, eine Frage."
    )
    feed = _read(BACKEND / "app" / "routers" / "instances.py")
    assert "article_object_id: int | None = Query(" not in feed, (
        "Der Instanz-Feed filtert wieder nach Artikel – das beantwortet der Bestand."
    )

    # Die Aufstellung wird EINMAL gezählt; die Menge ist ihre Summe.
    svc = _read(BACKEND / "app" / "services" / "instances.py")
    assert "def states(" in svc and "def article_states(" in svc
    assert "return {i: sum(by_status.values())" in svc, (
        "Menge und Aufstellung werden getrennt gezählt – zwei Abfragen für eine Frage."
    )

    api = _read(FRONTEND / "lib" / "api.ts")
    assert "getArticleInstances" not in api, "Der alte, kaputte Weg ist wieder da."
    assert "getArticleStock" in api and "getInstanceUnits" in api


def test_no_view_ever_renders_every_unit_at_once():
    """**Niemals 600 Zeilen auf einmal** – und zwar in jeder Ansicht, nicht nur im Reiter.

    Die Nummern einer 5000er-Charge am Stück zu liefern kostete gemessen 149 ms und 5000
    Zeilen; im Instanz-Datensatz stand genau das, einen Klick vom Bestand entfernt. Eine
    Regel, die eine Ansicht einhält und die Nachbaransicht bricht, ist keine.

    Der Riegel ist nicht Disziplin, sondern **Abwesenheit**: es gibt keine Funktion mehr,
    die alle Stücke einer Instanz zurückgibt.
    """
    svc = _read(BACKEND / "app" / "services" / "instances.py")
    assert "def units_of(" not in svc, (
        "Es gibt wieder einen Weg, alle Einzelinstanzen auf einmal zu holen."
    )
    assert "def units_page(" in svc and "limit" in _body(svc, "units_page")

    schema = _read(BACKEND / "app" / "schemas" / "instance.py")
    body = schema.split("class InstanceResponse(")[1].split("\nclass ")[0]
    assert "units: list[" not in body, (
        "Das Instanz-Detail liefert wieder alle Nummern mit – unbegrenzt."
    )
    assert "class UnitPage(" in schema, "Die Seite der Nummern fehlt."

    # Und im Frontend gibt es genau EINE Liste, die Nummern zeigt.
    detail = _read(FRONTEND / "components" / "erp" / "instance-detail.tsx")
    assert "rec.units.map" not in detail, "Der Instanz-Datensatz zeichnet wieder alles."
    stock = _read(FRONTEND / "components" / "erp" / "stock-view.tsx")
    assert "UnitNumbers" in stock, "Der Bestand hat eine zweite Nummernliste."
    units = _read(FRONTEND / "components" / "erp" / "unit-numbers.tsx")
    assert "offset" in units and "weitere" in units, (
        "Die Nummernliste lädt alles oder sagt nicht, dass sie gekappt ist."
    )


def test_the_stock_groups_instead_of_filtering():
    """**Kein Filter** – die Aufteilung selbst ist das Bedienelement.

    Ein Filter ist das Eingeständnis, dass die Standardansicht zu viel Rauschen enthält;
    und er versteckt, was er nicht zeigt. Stattdessen: ein Segment der Leiste anklicken
    heisst «zeig mir diese Nummern», und der Rest bleibt sichtbar.

    **Eine Gruppe je Zustand**, und zwar genau für die, die wirklich vorkommen: die
    Ansicht rendert `states` vom Server, nicht eine Liste, die sie selbst führt. Kommt
    morgen ein Zustand dazu, erscheint er ohne eine Zeile Code – ihn hier aufzuzählen
    hiesse, ihn beim nächsten Mal zu vergessen.

    Vorher waren es **zwei feste Blöcke** («Bestand»/«Historie»). Das war schon eine
    Aufteilung, aber eine grobe: ein neuer Zustand verschwand darin, statt sich zu zeigen.
    """
    stock = _read(FRONTEND / "components" / "erp" / "stock-view.tsx")
    # Nur der Code: die **Begründung**, warum es keinen Filter gibt, darf ihn benennen.
    for word in ("filterBy", "<select", "Filter:"):
        assert word not in _code(stock), f"Im Bestand steht wieder ein Filter («{word}»)."

    code = _code(stock)
    assert "states.map((s) =>" in code, (
        "Die Gruppen entstehen nicht aus den gelieferten Zuständen – dann sind sie fest."
    )
    # **Kein Status steht im Code** – weder für die Gruppierung noch für die Reihenfolge.
    for named in ("freigegeben", "im_prozess", "gesperrt", "verschrottet",
                  "FREIGEGEBEN", "IM_PROZESS", "GESPERRT", "VERSCHROTTET"):
        assert named not in code, (
            f"Die Bestandsansicht nennt «{named}» – dann landet ein neuer Zustand "
            f"irgendwo, statt an seiner Stelle zu erscheinen."
        )
    assert "BUCKETS" not in code, "Die festen zwei Blöcke sind zurück."
    # Und die grosse Gesamtzahl bleibt weg: sie summierte auch Verschrottetes.
    assert "fontSize: 26" not in code, (
        "Die eine grosse Zahl steht wieder im Kopf – sie zählt Bestand und Historie zusammen."
    )

    # Die Leiste ist EINE Komponente – oben wie in jeder Zeile.
    bar = _read(FRONTEND / "components" / "erp" / "stock-bar.tsx")
    assert "statusCfg(" in _code(bar), "Die Leiste liest die eine Statuskarte nicht."
    # Und sie färbt nicht selbst: jeder Ton kommt aus `cfg`, keiner steht hier.
    own = re.findall(r"var\(--(?:success|warning|danger)[^)]*\)", _code(bar))
    assert not own, (
        f"Die Leiste kennt eigene Ampelfarben ({', '.join(sorted(set(own)))}) – dann "
        f"sieht derselbe Zustand hier anders aus als in seiner Badge."
    )
    # Die Leiste steht **einmal**, über dem ganzen Umfang – und sie gilt für beide
    # Aufrufe (Artikel und Instanz), weil es EINE Ansicht für beide gibt. Die frühere
    # zweite Leiste je Instanz-Zeile ist entfallen: seit es eine Gruppe je Zustand gibt,
    # IST die Gruppe die Auswahl, und die Leiste in der Zeile sagte dasselbe noch einmal.
    assert stock.count("<StockBar") == 1, (
        "Es gibt wieder mehr als eine Leiste – dann steht dieselbe Aufteilung zweimal."
    )
    assert "scope.kind === 'instance'" in code and "InstanceRow" in code, (
        "Artikel- und Instanz-Umfang sind nicht mehr dieselbe Ansicht."
    )
    assert "onPick" in bar, "Ein Segment ist nicht anklickbar – dann braucht es doch einen Filter."


def test_live_or_history_is_a_property_of_the_status_not_a_list():
    """**Bestand oder Historie gehört an den Status** – nicht in die Bestandsansicht.

    Vorher war es eine Liste (``LIVE_UNIT_STATUSES``), auf beiden Seiten gepflegt. Eine
    Liste ist genau die Form, die man beim nächsten neuen Zustand vergisst: er wäre
    stillschweigend als Bestand gezählt worden, weil «alles, was ein Stück tragen kann»
    zufällig heute dasselbe ist.

    Jetzt deklariert **jeder** Stück-Zustand seine Zugehörigkeit (``Status.stock``), ein
    Import-Wächter weist eine fehlende ab, und die Antwort reist als ``StockState.stock``
    mit den Daten. Die Oberfläche entscheidet dabei **nichts** mehr.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    # 1. Deklariert, nicht abgeleitet: jeder Zustand, den ein Stück tragen kann, sagt es.
    for value in st.UNIT_STATUSES:
        assert st.stock_kind(value) in (st.LIVE, st.HISTORY), (
            f"«{value}» sagt nicht, ob es Bestand oder Historie ist."
        )
    # 2. Und ein Wert, den es nicht gibt, wird gemeldet statt geraten.
    assert st.stock_kind("gibt-es-nicht") == st.UNKNOWN

    # 3. Die Oberfläche führt keine eigene Liste mehr und liest die Zugehörigkeit am Segment.
    for name in ("process-status.ts", "status-catalog.ts"):
        src = _read(FRONTEND / "lib" / name)
        assert "LIVE_UNIT_STATUSES" not in src, (
            f"{name} führt wieder eine Bestands-Liste – sie gehört an den Status."
        )
    view = _code(_read(FRONTEND / "components" / "erp" / "stock-view.tsx"))
    # Die Zugehörigkeit bleibt eine **Eigenschaft**, die die Ansicht liest – seit #716
    # aber nur noch, um das **Unbekannte** zu melden. Was zugeklappt startet, entscheidet
    # sie nicht mehr: es startet alles zugeklappt.
    assert "s.stock !== 'live' && s.stock !== 'history'" in view, (
        "Die Ansicht liest die Zugehörigkeit nicht mehr – dann landet ein Zustand ohne "
        "Zuordnung stillschweigend irgendwo."
    )
    for value in st.UNIT_STATUSES:
        assert f"'{value}'" not in view and f'"{value}"' not in view, (
            f"Die Bestandsansicht nennt «{value}» beim Namen – dann entscheidet sie doch."
        )


def test_a_status_without_a_bucket_is_reported_not_guessed():
    """Ein Zustand ohne Zugehörigkeit ist ein **Fehler**, kein Sonderfall.

    Zwei Riegel, und beide müssen halten: die **Deklaration** kommt gar nicht erst durch
    (Import-Wächter), und ein zur Laufzeit auftauchender Wert (Altdaten, von Hand
    geschrieben) wird in der Oberfläche **benannt**. Ihn in einen Block zu raten wäre
    eine Behauptung, ihn wegzulassen ein stiller Verlust.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    import pytest
    from app.domain import statuses as st

    # Riegel 1: ein Stück-Zustand ohne ``stock`` fliegt beim Import.
    with pytest.raises(ValueError, match="stock"):
        st._check(st.CATALOG + (st.Status("neu", "Neu", "done", (st.UNIT,)),))

    # Riegel 2: die Oberfläche meldet, was weder Bestand noch Historie ist.
    # Geprüft wird die **Anwendung**, nicht die Anwesenheit: eine Komponente, die nur
    # definiert ist, meldet nichts – und genau so hätte der Wächter geschwiegen.
    view = _code(_read(FRONTEND / "components" / "erp" / "stock-view.tsx"))
    assert "<UnknownStates" in view, "Die Bestandsansicht meldet einen unbekannten Zustand nicht."
    assert "s.stock !== 'live' && s.stock !== 'history'" in view, (
        "Die Ansicht filtert das Unbekannte nicht heraus – dann landet es im falschen Block."
    )


def test_the_stock_is_one_module_for_the_article_and_the_instance():
    """**Keine zweite Kopie – dasselbe Modul.**

    Der Bestand beantwortet dieselbe Frage an zwei Orten: am **Artikel** «was habe ich
    davon», an der **Instanz** «was liegt in dieser Gruppe». Der Unterschied ist der
    Umfang der Daten, nicht die Darstellung – die Ansicht an der Instanz ist exakt der
    Teilbaum, den man am Artikel aufklappt.

    Zwei Fassungen hätten sich beim ersten neuen Zustand, beim ersten Design-Wechsel und
    bei der ersten Regel (Bestand ↔ Historie) getrennt; genau so stand es hier: der
    Artikel hatte drei Ebenen mit Leiste und Legende, die Instanz eine schlichte Liste.
    """
    view = FRONTEND / "components" / "erp" / "stock-view.tsx"
    src = _read(view)
    assert "export function StockView" in src, "Das Bestandsmodul heisst nicht mehr so."
    assert not (FRONTEND / "components" / "erp" / "instance-list.tsx").exists(), (
        "Die alte, zweite Bestandsansicht ist wieder da."
    )

    # Beide Orte rufen dasselbe Modul – und keiner baut sich Leiste/Legende selbst.
    for name in ("article-detail.tsx", "instance-detail.tsx"):
        caller = _read(FRONTEND / "components" / "erp" / name)
        assert "StockView" in caller, f"{name} benutzt das Bestandsmodul nicht."
        for own in ("StockBar", "StockLegend", "getArticleStock", "getInstanceUnits"):
            assert own not in caller, (
                f"{name} baut den Bestand teilweise selbst ({own}) – das ist die zweite Kopie."
            )

    # Der Umfang ist das EINZIGE, was die beiden Aufrufe unterscheidet.
    assert "kind: 'article'" in src and "kind: 'instance'" in src, (
        "Das Modul kennt die beiden Umfänge nicht."
    )


def test_the_stock_wears_the_specification_design():
    """Der Bestand sieht aus wie die **Spezifikation** – aus derselben Quelle.

    Karte, Kopf und Werteraster sind die Anatomie JEDER Detail-Ansicht; sie standen
    lokal im Artikel und waren dort auf «Spezifikation» festgenagelt. Wer daneben eine
    zweite Ansicht baute, musste sich einen eigenen Kopf schreiben – und dann sahen die
    Karten nur noch *ähnlich* aus.
    """
    fields = _read(FRONTEND / "components" / "erp" / "fields.tsx")
    assert "export function SpecHead" in fields and "export function SpecSection" in fields, (
        "Der Karten-Kopf wohnt nicht im gemeinsamen Vokabular."
    )

    article = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "function CardHead" not in article and "function SubSection" not in article, (
        "Der Artikel hält wieder eine eigene Karten-Anatomie."
    )

    for name in ("stock-view.tsx", "instance-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "SPEC.card" in src and "SpecHead" in src, (
            f"{name} trägt nicht die Spezifikations-Karte."
        )


def test_the_instance_links_its_article_and_wears_the_shared_header():
    """Die Instanz nennt ihren **Artikel als Datensatz**, nicht als abgeschriebenen Namen.

    Sie ist eine Gruppe, die aus genau einem Artikel entstanden ist; alles Fachliche über
    sie steht dort. Darum die **verlinkte Objektnummer** – ein Klick, immer aktuell –
    statt einer Kopie, die veraltet, sobald jemand den Artikel anfasst.

    Und der Kopf bleibt der EINE (`DetailHeader`): Layout, Raster, Farben und Schriften
    sind über alle Datensatztypen identisch, nur der Inhalt unterscheidet sich.
    """
    src = _read(FRONTEND / "components" / "erp" / "instance-detail.tsx")
    assert "<DetailHeader" in src, "Die Instanz baut sich wieder einen eigenen Kopf."
    assert "<ObjId value={rec.article_object_id}" in src, (
        "Die Artikelnummer ist nicht klickbar – dann ist sie nur Text."
    )
    assert "<ReadField" in src, "Die Herkunft steht nicht im Werteraster der Spezifikation."
    # Der Kopf entscheidet über Symbol/Eyebrow/Status selbst (#697) – hier keine Kopie.
    assert "TYPE_META" not in src, (
        "Das Instanz-Fenster löst die Typ-Identität selbst auf, statt sie dem Kopf zu überlassen."
    )


def test_the_scanner_suggests_with_the_feeds_own_search():
    """**Dieselbe Suche wie im Feed** – nicht eine zweite «für die Kamera».

    Die Vorschlagsliste gab es im Scanner längst; sie filterte ``step.candidates``. Nur
    hatte der einzige Aufrufer keine: ein freier Lookup über das ganze ERP kann keine
    fertige Kandidatenliste mitgeben, also war die Quelle **immer leer** – wer «00787»
    tippte, sah nichts, und der Knopf blieb grau, weil eine Teilnummer keine gültige
    Objektnummer ist.

    Jetzt reicht der Feed seine eigene Suche durch (``suggest``). **Nur die
    Vorschlagsquelle wird breiter, nicht die Gültigkeitsregel**: was ein Schritt annimmt,
    sagt weiterhin allein ``validateForStep``.
    """
    lib = _read(FRONTEND / "lib" / "scan.ts")
    assert "suggest?:" in lib, "Die Vorschlagsquelle ist keine Naht am Schritt."
    # Die Gültigkeitsregel bleibt, wo sie war – `suggest` taucht dort nicht auf.
    rule = _body(lib, "validateForStep", kind="function")
    assert "suggest" not in rule, (
        "Die Vorschlagsquelle entscheidet mit über die Gültigkeit – dann ist sie keine."
    )

    dialog = _code(_read(FRONTEND / "components" / "scan" / "scan-dialog.tsx"))
    assert "step?.suggest" in dialog, "Der Dialog fragt die Vorschlagsquelle nicht."
    assert "step?.restrict || step?.expected != null) { setFound([]); return; }" in dialog, (
        "Ein eingeschränkter oder verifizierender Schritt bekommt breitere Vorschläge – "
        "dann bietet er an, was er gar nicht annimmt."
    )
    # **Und jeder Schritt hat eine Vorschlagsmenge**, ohne dass ein Aufrufer sie mitgibt:
    # sie ist abgeleitet aus dem, was er ANNIMMT. Genau daran fehlte es im Modul – dort
    # gab es keine Liste, also blieb die Suche leer und nur die volle Nummer ging durch.
    assert "export function offersFor" in lib, "Die Vorschläge sind wieder eine Bringschuld."
    assert "offersFor(step)" in dialog, "Der Dialog leitet die Vorschläge nicht ab."
    assert "stale = true" in dialog, "Eine ältere Antwort kann eine neuere überholen."

    # Und der Feed gibt seine EIGENE Suche herein, keine nachgebaute.
    page = _code(_read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx"))
    assert "suggest: suggestFromFeed" in page, "Der Feed reicht seine Suche nicht durch."
    body = _body(page, "suggestFromFeed", kind="function")
    assert "feedMatch(" in body and "api.getInstances(" in body, (
        "Die Vorschläge suchen anders als der Feed – zwei Suchen, zwei Ergebnisse."
    )
    assert "feedMatch(r, search.toLowerCase())" in page, (
        "Die Liste filtert nicht über die geteilte Regel."
    )
    assert "rowSearchText(" in _body(page, "feedMatch", kind="function"), (
        "Die geteilte Regel liest den Suchtext nicht – dann ist sie eine zweite."
    )
    assert page.count("rowSearchText(") == 2, (
        "Der Suchtext wird ausserhalb der einen Regel gelesen (Definition + 1 Anwendung)."
    )
    # Der Hardware-Scanner-Pfad bleibt: volle Nummer + Enter geht direkt durch – und
    # zwar **immer**. Er hing einmal an einer Vorprüfung (`typedDirectOk`), und damit
    # passierte bei einer nicht passenden Nummer gar nichts: kein Sprung, keine Meldung.
    # Jetzt geht jede Eingabe durch dieselbe Prüfung wie ein Kamerabild und sagt ihren
    # Grund, wenn sie nicht passt.
    assert "if (e.key === 'Enter') { e.preventDefault(); submitQuery(); }" in dialog, (
        "Der direkte Weg (volle Nummer + Enter) ist weg."
    )
    assert "übernehmen" not in dialog and "Übernehmen" not in dialog, (
        "Es gibt wieder einen Zwischenschritt zwischen Eingabe und Ergebnis."
    )


def test_a_running_piece_names_the_order_it_runs_in():
    """Ein Stück «Im Prozess» ohne den Weg zu seinem Auftrag ist eine Sackgasse.

    Man sieht, dass es läuft, aber nicht wo – und genau das ist die Frage, die man am
    Bestand stellt. Die Zuordnung kommt aus **derselben** Stelle, die die Exklusivität
    liest (``process.held_by``); eine zweite Abfrage «welcher Auftrag hat dieses Stück»
    wäre eine zweite Antwort auf eine Frage, die nur eine haben darf.
    """
    proc = _read(BACKEND / "app" / "services" / "process.py")
    assert "def holders(" in proc and "held_by(db, unit_ids)" in _body(proc, "holders"), (
        "Die Auftrags-Zuordnung wird neben der Exklusivität noch einmal abgeleitet."
    )
    schema = _read(BACKEND / "app" / "schemas" / "instance.py")
    assert "order_object_id" in schema, "Das Stück nennt seinen Auftrag nicht."
    units = _code(_read(FRONTEND / "components" / "erp" / "unit-numbers.tsx"))
    assert "<ObjId value={u.order_object_id}" in units, (
        "Die Zeile zeigt den Auftrag nicht als anklickbare Objektnummer – dann ist das "
        "Stück zwar als «läuft» erkennbar, aber der Weg dorthin fehlt."
    )
    assert "u.order_object_id ?" in units, (
        "Der Auftrag wird unbedingt gerendert – ein freies Stück hat keinen."
    )


# ---------------------------------------------------------------------------
# Der Scanner — wieder in Betrieb, und robuster als vorher
# ---------------------------------------------------------------------------

def test_a_button_without_effect_is_caught_by_the_linter():
    """**Ein Knopf, der nichts tut, muss auffallen** – automatisch, nicht durch Lesen.

    Der Scan-Knopf im Feed setzte einen Zustand, den niemand las: seit dem Basis-Neuaufbau
    tat er nichts, und nichts hat es gemeldet. Die Ursache war nicht Unachtsamkeit,
    sondern eine ausgeschaltete Regel – `next/core-web-vitals` allein prüft ungenutzte
    Variablen nicht, und eine ungenutzte **Destrukturierung** (`const [x, setX] = …`) ist
    genau die Form, in der ein toter Knopf auftritt.

    Der Wächter hält fest, dass die Regel an ist. Gefunden hat sie danach nicht eine
    Leiche, sondern **46** – darunter zwei API-Abfragen für einen Wert, den niemand liest.
    """
    cfg = json.loads(_read(FRONTEND.parent / ".eslintrc.json"))
    rule = cfg.get("rules", {}).get("no-unused-vars")
    assert rule, "Die Regel gegen ungenutzte Variablen ist nicht eingeschaltet."
    assert rule[0] == "error", "Die Regel warnt nur – dann fällt nichts auf."
    assert "destructuredArrayIgnorePattern" in rule[1], (
        "Ohne diese Option bleibt die tote `useState`-Destrukturierung unbemerkt – "
        "und genau die war der tote Scan-Knopf."
    )
    # Und die CI führt sie aus; eine Regel, die nur lokal läuft, ist keine.
    ci = _read(ROOT / ".github" / "workflows" / "deploy-dev.yml")
    assert "npm run lint" in ci, "Der Linter läuft nicht in der CI."

    feed = _read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx")
    assert "feedCapture" not in feed, "Der tote Zustand hinter dem Scan-Knopf ist zurück."
    assert "onClick={openScanner}" in feed, "Der Scan-Knopf ist wieder ohne Wirkung."


def test_an_aborted_scan_never_completes():
    """**Wer abbricht, löst nichts aus.**

    Der Erfolgs-Timer (380 ms) lief ungebremst weiter: Esc oder Klick daneben in diesem
    Fenster → der Dialog war weg, der Timer feuerte trotzdem, und `onComplete` bewegte
    eine Instanz, die niemand mehr bewegen wollte. Ein Datenfehler, kein Schönheitsfehler.
    """
    src = _code(_read(FRONTEND / "components" / "scan" / "scan-dialog.tsx"))
    assert "clearTimeout" in src, "Der Quittierungs-Timer wird nicht aufgeräumt."
    assert "if (!alive.current) return;" in src, (
        "Nach dem Abbruch fehlt die Prüfung, ob der Dialog überhaupt noch lebt – die "
        "asynchrone Existenzprüfung kann sonst NACH dem Schliessen einen Timer setzen, "
        "den kein Cleanup mehr erwischt."
    )
    # Und die Marke wird beim Betreten **zurückgesetzt**: React ruft einen Effekt in der
    # Entwicklung zweimal auf (mount → cleanup → mount). Fehlt die Zeile, steht sie nach
    # dem ersten Cleanup für immer auf «tot» und der Dialog nimmt gar nichts mehr an –
    # genau das hat der Browser-Durchlauf gemeldet, nicht das Lesen.
    assert "alive.current = true;" in src, (
        "Die Lebend-Marke wird beim Mount nicht zurückgesetzt (StrictMode-Doppellauf)."
    )


def test_a_free_lookup_asks_whether_the_object_exists():
    """**«Erkannt» heisst «gibt es».**

    Ohne `expected`/`restrict` galt jede formal gültige 9-stellige Zahl – irgendein
    fremder QR-Code kam durch, der Rahmen wurde grün, der Dialog schloss, und beim
    Aufrufer passierte stillschweigend nichts (404, verschluckt). Die Meldung «… ist
    nicht im ERP» gab es bereits; sie war nur unerreichbar.
    """
    lib = _code(_read(FRONTEND / "lib" / "scan.ts"))
    assert "exists?:" in lib, "Der Schritt kann die Existenzfrage nicht stellen."
    assert "ist nicht im ERP" in lib and "await step.exists(" in lib, (
        "Die Deutung fragt nicht nach – dann meldet der Scanner Erfolg für Nummern, "
        "die es nicht gibt."
    )
    feed = _code(_read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx"))
    assert "exists: (id) => api.resolveObject(id)" in feed, (
        "Der Feed reicht die Frage nicht herein – dort trifft sie am häufigsten zu."
    )


def test_the_dialog_knows_neither_decoder_nor_object_semantics():
    """**Drei Schichten, und die Deutung ist austauschbar** (die Naht für später).

    Der Dialog besitzt die Kamera und liefert ein Ergebnis; was das Ergebnis BEDEUTET,
    steht in `ScanReading` (heute `objectCodes`). Vorher griff er selbst zu
    `parseScannedCode`/`validateForStep` – damit wusste er, dass ein Scan eine
    Objektnummer ist, und eine zweite Deutung wäre ein Umbau statt eines neuen Objekts.
    """
    dialog = _code(_read(FRONTEND / "components" / "scan" / "scan-dialog.tsx"))
    for leak in ("parseScannedCode", "validateForStep", "@zxing"):
        assert leak not in dialog, f"Der Dialog greift wieder direkt zu «{leak}»."
    for call in ("reading.read(", "reading.check(", "reading.prompt("):
        assert call in dialog, f"Der Dialog benutzt den Vertrag nicht ({call})."

    lib = _code(_read(FRONTEND / "lib" / "scan.ts"))
    assert "export interface ScanReading" in lib and "export const objectCodes" in lib
    # Die Logikschicht bleibt frei von React und API.
    assert "react" not in lib.lower() and "lib/api" not in lib, (
        "lib/scan.ts zieht React oder den API-Client herein – die unterste Schicht muss "
        "ohne beides auskommen, sonst ist sie keine."
    )


def test_the_camera_is_one_layer_and_the_decoder_another():
    """**Die Kamera ist ein Bauteil, das Decodieren ein zweites** (Testnotiz #718).

    Ein Bild aufnehmen und einen Code darin suchen sind zwei verschiedene Dinge – nur die
    Beschaffung des Bildes ist dieselbe: Linsenwahl, Strom, Taschenlampe, Aufräumen. Sie
    steht darum in `use-camera.ts` und wird **geteilt** (Scanner *und* Aufnahme); der
    Decoder hängt sich über einen Rückruf daran (`Attach`).

    Ohne die Naht gäbe es die Kamera zweimal – und die zweite hätte die Ultraweitwinkel-
    Falle, den Taschenlampen-Pfad und das Track-Aufräumen von neuem lernen müssen.

    **In der Halle entscheidet sich das:** `facingMode: 'environment'` überlässt die Wahl
    dem Browser, und der greift auf Telefonen mit mehreren Rückkameras oft zur
    Ultraweitwinkel-Linse – die bei 10 cm nicht scharf stellt, also genau dort, wo man ein
    Etikett hält.
    """
    cam = _code(_read(FRONTEND / "components" / "scan" / "use-camera.ts"))
    assert "export function pickCamera" in cam, "Die Linsenwahl fehlt."
    assert "torch" in cam and "applyConstraints" in cam, "Die Taschenlampe fehlt."
    assert "export function useCamera" in cam, "Die geteilte Kamera-Schicht fehlt."

    # **Die Kamera weiss nichts vom Decodieren.** Sonst wäre die Trennung eine Behauptung.
    for leak in ("BarcodeDetector", "@zxing", "decode"):
        assert leak not in cam, (
            f"«{leak}» steht in der Kamera-Schicht – dann ist sie keine, und die Aufnahme "
            f"zieht den Decoder mit."
        )

    # **Der Speicherleck-Fix bleibt.** ZXings `stop()` beendet nur die Decode-Schleife;
    # ohne explizites Stoppen der Tracks wächst der Video-Puffer über jeden Scan hinweg.
    # Geprüft wird der **Cleanup**, nicht die Datei: `getTracks` steht auch im Abbruch-
    # Zweig, und der räumt beim Schliessen nichts auf.
    cleanup = cam.split("return () => {")[-1]
    assert "getTracks" in cleanup and "t.stop()" in cleanup, (
        "Der Cleanup stoppt die Kamera-Tracks nicht mehr – das Speicherleck ist zurück."
    )

    # Der Decoder: nativ zuerst, ZXing nur als **dynamischer** Rückfall – sonst kosten die
    # ~112 kB auch die Geräte, die sie nicht brauchen.
    dec = _code(_read(FRONTEND / "components" / "scan" / "use-barcode-scanner.ts"))
    assert "BarcodeDetector" in dec, "Der native Schnellpfad fehlt."
    assert "await import('@zxing/browser')" in dec, (
        "ZXing wird statisch geladen – dann kostet der Rückfall auch die Geräte, die ihn "
        "nicht brauchen."
    )
    assert "import { BrowserMultiFormatReader" not in dec
    assert "useCamera(active, attach)" in dec, (
        "Der Decoder baut die Kamera wieder selbst – dann gibt es sie zweimal."
    )
    assert "getUserMedia" not in dec, (
        "Der Decoder greift wieder selbst zum Strom – der gehört der Kamera-Schicht."
    )


def test_the_focus_follows_the_camera():
    """Läuft die Kamera, bleibt die Tastatur zu – **ausser** sie ist der einzige Weg.

    `autoFocus` öffnete auf dem Telefon sofort die Bildschirmtastatur über dem Bild, um
    das es geht. Ohne Fokus verlöre man aber den Hardware-Scanner: ein USB-/Bluetooth-
    Gerät tippt Nummer + Enter in das fokussierte Feld. Beides zugleich geht, weil die
    erste Ziffer den Fokus holt und mitgenommen wird.
    """
    src = _code(_read(FRONTEND / "components" / "scan" / "scan-dialog.tsx"))
    assert "autoFocus" not in src, "Die Tastatur springt wieder unbedingt auf."
    assert "if (cameraLive) sheetRef.current?.focus();" in src
    assert "/^\\d$/.test(e.key)" in src, (
        "Ohne die Ziffern-Weiche verliert der Hardware-Scanner sein Ziel."
    )
    assert 'role="dialog"' in src and 'aria-modal="true"' in src


def test_every_record_type_can_print_its_label():
    """**Was man scannen soll, muss man etikettieren können.**

    Den QR-Knopf gab es nur am Artikel – ausgerechnet nicht an der **Instanz**, dem Ding
    im Regal. Ein Etikett trägt nur die Objektnummer, und die hat jeder Datensatz; der
    Knopf ist darum EIN Bauteil, kein Nachbau je Ansicht.
    """
    label = _read(FRONTEND / "components" / "scan" / "object-label.tsx")
    assert "export function LabelButton" in label
    for name in ("article-detail.tsx", "instance-detail.tsx", "order-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "<LabelButton" in src, f"{name} kann kein Etikett drucken."
        assert "printObjectLabel(" not in src, (
            f"{name} baut den Knopf selbst nach, statt das gemeinsame Bauteil zu nehmen."
        )


def test_the_scanner_lies_above_the_detail_and_below_the_notes():
    """Die Stapel-Ordnung ist eine Entscheidung – also steht sie fest.

    Der Scanner liegt über den Detail-Dialogen (die Kamera ist der Vordergrund) und unter
    dem Notiz-Werkzeug (beim Testen muss man ihn selbst melden können).
    """
    dialog = _code(_read(FRONTEND / "components" / "scan" / "scan-dialog.tsx"))
    assert "zIndex: 100" in dialog, "Der Scanner hat seine Ebene verloren."
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "zIndex: 60" in fields, "Der Detail-Dialog liegt nicht mehr unter dem Scanner."
    pin = _read(FRONTEND / "components" / "feedback" / "feedback-pin.tsx")
    assert "z-[2000]" in pin, "Das Notiz-Werkzeug liegt nicht mehr über dem Scanner."


def test_the_object_registry_claims_only_what_it_can_serve():
    """Ein Typ, den kein Endpunkt liefern kann, ist eine Behauptung.

    ``document`` stammt aus dem abgeschalteten Dokumentmodul – jede Auflösung einer
    unbekannten Nummer durchsuchte eine Tabelle, die immer leer ist. **Der Nummernraum
    ist davon getrennt**: die Spalte speist ``current_max_object_id`` → ``setval``, und
    eine Alt-Zeile mit der höchsten Nummer würde sonst ein zweites Mal vergeben.
    """
    src = _read(BACKEND / "app" / "services" / "objects.py")
    models = src.split("_TYPE_MODELS = {")[1].split("}")[0]
    assert '"document"' not in models, "Der Scan löst wieder auf ein totes Modul auf."
    assert "DocumentFile.object_id" in src.split("_OBJECT_ID_COLUMNS")[1][:300], (
        "Die Alt-Nummern fallen aus dem Nummernraum – die Sequence kann sie neu vergeben."
    )


# ---------------------------------------------------------------------------
# Datenerfassung – Scan-Pflicht, Stichprobe, Entscheidung
# ---------------------------------------------------------------------------

def test_no_entry_without_a_confirmed_instance():
    """**Ohne Bestätigung keine Eingabe** (§3) – und die Regel steht im Backend.

    Die Oberfläche zeigt das Formular erst nach einer Bestätigung; das ist die Bedienung.
    Die **Regel** ist die Ablehnung in ``process._verified_instance``: ein ausgegrautes
    Feld ist keine Sperre, sondern eine Bitte. Beides muss dastehen – ein Gate, das nur
    im Backend steht, wäre eine Fehlermeldung statt einer Führung; eines, das nur im
    Frontend steht, wäre gar keins.
    """
    work = _read(FRONTEND / "components" / "erp" / "capture-work.tsx")
    code = _code(work)
    assert "via ? (" in code, "Das Formular hängt nicht mehr an der Bestätigung."
    assert "expected: w.instance_object_id" in code, (
        "Der Scan verifiziert nicht mehr die Instanz – ohne ``expected`` ist er ein "
        "beliebiger Lookup und bestätigt gar nichts."
    )
    # **Ein Weg, nicht zwei.** Die Tastatur ist die Alternative **im Dialog** (die Leiste
    # im Bild) – ein zweiter Knopf daneben war ein zweiter Weg zum selben Ziel, und er
    # umging die Verifikation ganz. Wie bestätigt wurde, sagt der Dialog selbst.
    assert "setVerified('manual')" not in code, (
        "Neben dem Scanner steht wieder ein eigener «von Hand»-Weg – zwei Wege zum "
        "selben Ziel, und der zweite bestätigt gar nichts."
    )
    # Geprüft wird die **Aussage**, nicht ihr Wortlaut: der Dialog liefert ``how``, und
    # der Aufrufer reicht genau das an ``accept`` weiter. Ob daneben noch die gescannten
    # Nummern gebraucht werden (der Zielort einer Bewegung), ist eine Frage des Moduls
    # und darf diesen Wächter nicht brechen.
    assert "onComplete: (ids, how)" in code or "onComplete: (_ids, how)" in code, (
        "Die Art der Bestätigung kommt nicht mehr aus dem Dialog – dann rät der "
        "Aufrufer, wie die Nummer zustande kam."
    )
    assert "accept(w, how" in code, (
        "Die Bestätigung geht nicht mehr durch ``accept`` – dann gibt es einen zweiten "
        "Weg, eine Instanz als bestätigt zu markieren."
    )
    api = _code(_read(FRONTEND / "lib" / "api.ts"))
    # **Der ganze Rumpf, nicht die ersten n Zeichen.** Ein Fenster fester Grösse bricht,
    # sobald die Signatur wächst – und sagt dann etwas über die Zeichenzahl statt über
    # die Sache.
    start = api.index("confirmStep(")
    call = api[start:][: api[start:].index("\n  }")]
    assert "verification: verification ?? null" in call, (
        "Die Art der Bestätigung fährt nicht mehr mit – von Hand wäre damit eine stille "
        "Umgehung statt einer protokollierten Alternative."
    )
    proc = _read(BACKEND / "app" / "services" / "process.py")
    assert "def _verified_instance" in proc, "Die Regel steht nur noch im Frontend."


def test_one_scan_per_instance_and_no_serialisation_question():
    """**Der Scan verifiziert die Instanz, nicht die Einzelinstanz** (§3).

    Das Etikett klebt am physischen Ding, und das ist die Instanz – eine Einzelinstanz
    zieht bewusst keine Objektnummer. Daraus fällt der Unterschied von selbst heraus:
    eine Charge ist **ein** Scan, Einzelserialisierung sind **n**. Steht im Modul eine
    Abfrage nach der Serialisierung, ist genau diese Ableitung nachgebaut worden.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    for forbidden in ("serialization", "'batch'", '"batch"', "'unit'"):
        assert forbidden not in work, (
            f"«{forbidden}» im Datenerfassungs-Modul – der Unterschied wird abgefragt "
            f"statt abgeleitet."
        )
    assert "work.map(" in work, "Die Arbeit steht nicht mehr je Instanz da."


def test_the_sample_rule_is_written_in_exactly_one_place():
    """**Die Stichprobe ist eine Regel, kein Satz im Frontend** (§2).

    Wie sie lautet, sagt ``sampling.describe`` – die Oberfläche bekommt sie fertig
    (``ProcessStepResponse.sample``). Formulierte sie sie selbst, gäbe es zwei Texte für
    dieselbe Regel, und «10 %» hiesse an einer Stelle je Instanz und an der anderen je
    Auftrag.
    """
    order = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "?.sample" in _body(order, "sampleOf", kind="function"), (
        "Der Satz kommt nicht mehr vom Server."
    )
    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    assert "sampling.describe(modules.sample_of(self.config))" in schema, (
        "Die Antwort trägt die Regel nicht mehr mit."
    )
    designer = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    assert "je Instanz" not in designer, (
        "Die Definition spricht wieder von «je Instanz» – die Bezugsgrösse ist die "
        "Gesamtmenge dessen, was am Modul wartet."
    )
    # **Der Zusatz «der Gesamtmenge» ist entfallen** (#705): die Bezugsgrösse steht im
    # Hover jeder Option («… aller wartenden Einzelinstanzen») und in der Auskunft zur
    # Laufzeit. Zweimal danebengeschrieben war er ein Satzende, das nie jemand las.
    assert "der Gesamtmenge" not in designer, (
        "Der Zusatz steht wieder in der Fläche – er gehört in den Hover der Optionen."
    )
    assert "aller wartenden Einzelinstanzen" in designer, (
        "Die Bezugsgrösse steht nirgends mehr – dann ist «25 %» eine Zahl ohne Nenner."
    )
    mods = _code(_read(FRONTEND / "lib" / "modules.ts"))
    assert "sample: samplePayload(m.sample)" in mods, (
        "Der Entwurf deutet die Stichprobe selbst – ein halb getipptes Feld würde damit "
        "stillschweigend zu «alle»."
    )
    # Und die Ziehung selbst zählt über den **Auftrag**, nicht je Instanz: sonst wäre
    # «die Hälfte» in Wahrheit «die Hälfte aus jeder Kiste».
    draw = _read(BACKEND / "app" / "services" / "sampling.py")
    assert "def _population" in draw and "OrderUnit.order_id == order.id" in draw, (
        "Gezogen wird wieder aus der Welle statt aus dem Bestand des Auftrags."
    )
    assert "by_instance" not in draw, "Die Ziehung gruppiert wieder je Instanz."


def test_a_failed_capture_creates_nothing_by_itself():
    """**Erfassen ist eine Aussage, kein Auftrag** (§4).

    Ein automatischer Folgeauftrag wäre ein Entwurf, den niemand bestellt hat – und er
    zöge Stücke aus dem laufenden Auftrag, ohne dass jemand zugestimmt hätte. Das System
    **hält an** und **bietet an**; angelegt wird über denselben Weg wie jeder Auftrag.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    assert "api.createOrder" not in work, (
        "Das Modul legt selbst einen Auftrag an – ein zweiter Anlagepfad."
    )
    assert "onDeviate({" in work, "Die Entscheidung öffnet keinen Entwurf mehr."
    assert "work.held" in work, (
        "Der Haltezustand wird nicht mehr gezeigt – stilles Weiterlaufen."
    )
    held = _code(_read(BACKEND / "app" / "services" / "process.py"))
    held = _body(held, "confirm_step")
    assert 'if result == "failed":' in held and '"moved": 0, "held": len(units)' in held, (
        "Ein «nicht bestanden» rückt wieder vor, statt anzuhalten."
    )
    assert held.index('if result == "failed":') < held.index("    _pass("), (
        "Der Haltezweig steht hinter dem Vorrücken – er kommt zu spät."
    )


def test_the_deviation_is_the_only_way_out_of_a_hold():
    """►►► **Eine Frage, EINE Antwort** (§4.1, Testnotiz #713). ◄◄◄

    Neben der Abweichung stand einmal eine «100 %-Kontrolle». Sie war **kein zweiter
    Mechanismus**, sondern derselbe: ein Abweichungsauftrag über die übrigen Stücke mit
    der Stichprobe «alle». Zwei Wege zu demselben Ergebnis sind einer zu viel – und der
    zweite war der schwächere, weil er die Stichprobe der Auflösung stillschweigend
    festlegte, statt sie wählen zu lassen.

    Entfallen ist sie **ersatzlos, auf allen Ebenen**: der Knopf, die Gruppe ``rest`` im
    Dienst und die im Endpunkt. Ein toter Pfad wäre die Einladung, ihn wiederzubeleben.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    assert "'failed'" in work, "Die Abweichung holt ihre Vorauswahl nicht mehr vom Server."
    assert "'rest'" not in work, "Die 100 %-Kontrolle ist zurück – zwei Wege, ein Ziel."

    proc = _read(BACKEND / "app" / "services" / "process.py")
    body = _body(proc, "held_numbers")
    assert '"rest"' not in body and "'rest'" not in body, (
        "Der Dienst kennt die Gruppe «rest» wieder – ein toter Pfad, den niemand ruft."
    )
    assert "_units_at(db, order, step.id, instance_id=" in body, (
        "Die Vorauswahl wird nicht mehr auf dieses Modul begrenzt – sie griffe nach der "
        "ganzen Charge."
    )


def test_the_number_of_scans_follows_the_sample():
    """►►► **Gescannt wird nur, was auch erfasst wird** (Testnotiz #714). ◄◄◄

    Die Reihenfolge stand auf dem Kopf: **jede** wartende Instanz wurde zum Scan
    angeboten, und erst danach entschied die Ziehung, ob es dort etwas zu erfassen gab.
    Bei zwei Instanzen und 50 % waren das zwei Scans für eine Erfassung.

    Die Oberfläche bietet den Scan darum nur noch an, wo die Stichprobe zugreift – und
    der Dienst bewegt das Ungezogene selbst weiter (``_run_through``), damit aus dem
    weggelassenen Knopf keine Sackgasse wird.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    assert "w.sample > 0" in work, (
        "Der Scan-Knopf hängt nicht (mehr) an der Ziehung – dann bestätigt er nichts."
    )
    proc = _read(BACKEND / "app" / "services" / "process.py")
    assert "def _run_through(" in proc and "def _sample_cleared(" in proc, (
        "Der Dienst bewegt das Ungezogene nicht mehr – ohne Scan-Knopf steht es für "
        "immer still."
    )
    body = _body(proc, "_run_through")
    assert "_sample_cleared(" in body, (
        "Der Rest läuft, ohne dass die Stichprobe durch ist – bei einem «nicht "
        "bestanden» wäre er weg, bevor ihn jemand aussondern kann."
    )


def test_the_collective_scan_is_the_scan_sequence():
    """**Der Sammel-Scan ist kein zweiter Mechanismus** (Testnotiz #711).

    Die Scan-Sequenz ist genau dafür gebaut: ein Dialog, ein Schritt je Instanz, der
    Reihe nach. Der Unterschied zum Knopf in der Zeile ist die **Zahl der Schritte** –
    nicht eine zweite Kamera-Logik daneben.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "capture-work.tsx"))
    # **Dieselbe Quelle, andere Zahl der Schritte.** Wie die Bausteine heissen, ist
    # gleichgültig – dass der Sammel-Scan sie aus derselben Funktion nimmt wie der
    # Einzel-Scan, ist die Regel.
    assert "open.flatMap(goodsSteps)" in work or "open.flatMap(scanSteps)" in work, (
        "Der Sammel-Scan baut sich seine eigene Mechanik, statt die Sequenz zu benutzen."
    )
    # **Und beide Wege bauen ihre Schritte an derselben Stelle.** Der Unterschied ist die
    # Zahl der Instanzen, nicht die Zusammensetzung eines Vorgangs – sonst scannte der
    # kleine Knopf die Kisten des Verbrauchsmoduls und der grosse nicht.
    assert "steps: scanSteps(w)" in work, (
        "Der Knopf in der Zeile baut seine Schritte selbst zusammen."
    )
    assert "open.length > 1" in work, (
        "Der grosse Knopf steht auch bei einer einzigen Instanz da – dann ist er ein "
        "zweiter Weg zum selben Ziel."
    )


def test_the_stock_view_shows_each_quantity_once():
    """**Keine doppelten Daten auf engem Raum** (Testnotiz #716).

    Unter der Leiste stand eine Legende (Punkt, Wort, Menge je Zustand) – und drei Zeilen
    tiefer stand dasselbe noch einmal als Gruppen-Kopf, in derselben Reihenfolge und
    derselben Farbe, nur anklickbar. Geblieben ist die Fassung, mit der man arbeitet.

    Und **zugeklappt startet alles**: eine Gruppe, die von selbst offensteht, entscheidet
    für den Betrachter, was ihn interessiert.
    """
    view = _code(_read(FRONTEND / "components" / "erp" / "stock-view.tsx"))
    assert "StockLegend" not in view, "Die Zahlen stehen wieder zweimal untereinander."
    assert "useState(false)" in view, "Eine Gruppe startet wieder von selbst offen."
    assert "state.stock !== 'history'" not in view, (
        "Das Aufklappen hängt wieder am Zustand – bei einem Artikel mit genau einem "
        "Zustand steht damit immer etwas offen."
    )
    bar = _code(_read(FRONTEND / "components" / "erp" / "stock-bar.tsx"))
    assert "export function StockLegend" not in bar, (
        "Die Legende steht als toter Pfad herum – die Einladung, sie wieder einzubauen."
    )


# ---------------------------------------------------------------------------
# Aussondern – zwei Ausprägungen, eine Registry
# ---------------------------------------------------------------------------

def test_the_disposal_modes_match_the_backend_exactly():
    """**Zwei Fälle, ein Modul** – und die Liste steht im Backend.

    Ein dritter Fall wäre dort ein Eintrag; hier stehen nur Wort und Erklärung. Ein
    Modus ohne Gegenstück wäre eine tote Auswahl, ein Gegenstück ohne Modus eine Wahl,
    die niemand treffen kann.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain.modules import Aussondern

    ts = _read(FRONTEND / "lib" / "modules.ts")
    body = ts.split("export const DISPOSAL_MODES")[1].split("];")[0]
    assert set(re.findall(r"value: '(\w+)'", body)) == set(Aussondern.MODES)


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
    form = ts.split("export const MODULE_FORM")[1].split("\n};")[0]
    assert set(re.findall(r"^  (\w+): \{", form, re.M)) == set(modules.KEYS)

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
    assert "'Menge je Einzelinstanz'" in ui


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
    assert "const required = need.per_unit * pieces;" in work, (
        "Die Menge wird nicht mehr auf die Stücke dieser Instanz gerechnet."
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
    body = _body(proc, "confirm_step")
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
    assert "else:" in body.split("if module.terminal:")[1].split("_finish(")[0], (
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


def test_the_transport_list_is_the_bit_not_a_module_type_check():
    """**«Bewegt dieses Modul?» beantwortet die Transportliste, nicht ein Typvergleich.**

    Sie ist bei jedem anderen Modultyp leer – dieselbe Bauart wie `needs` bei der
    Stückliste. Ein `moduleType === 'bewegen'` in der Oberfläche wäre eine zweite Stelle,
    an der sie über Modultypen Bescheid wissen müsste; die erste, die man beim nächsten
    Modul vergisst.
    """
    work = _read(FRONTEND / "components" / "erp" / "capture-work.tsx")
    assert "transports.length > 0" in _code(work), (
        "Das Bit «bewegt dieses Modul» kommt nicht mehr aus der Transportliste."
    )
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

def test_a_free_scan_step_brings_its_own_suggestions():
    """**Der Scanner bietet an, was er annimmt — auch beim freien Lookup** (#730–#732).

    Bei einer **Verifikation** ist die Vorschlagsliste abgeleitet (`offersFor` = die
    erwartete Nummer); dort braucht niemand etwas mitzugeben. Ein **freier** Schritt hat
    diese Ableitung nicht: ohne `suggest` bleibt seine Liste für immer leer, und wer
    «00292» tippt, sieht nichts – obwohl es die Nummer gibt.

    Geprüft wird darum, dass jeder freie Schritt eine Quelle mitbringt. Genau daran
    scheiterte es dreimal: der Feed hatte eine, der Zielort nicht.
    """
    # Der Editor öffnet seinen Zielort-Scan seit #738 über das gemeinsame Referenzfeld
    # (`ObjectSelect`) – die Regel gilt dort, für **jede** Referenz, nicht nur für den Ort.
    for surface, opener in (
        ("capture-work.tsx", 'label: \'Zielort\''),
        ("object-select.tsx", "label: scanLabel"),
    ):
        code = _code(_read(FRONTEND / "components" / "erp" / surface))
        assert opener in code, f"{surface} öffnet keinen freien Scan-Schritt mehr."
        step = code[code.index(opener):][:600]
        assert "suggest:" in step, (
            f"Der Zielort-Schritt in {surface} hat keine Vorschlagsquelle – wer eine "
            f"Teilnummer tippt, sieht nichts."
        )
        assert "exists:" in step, (
            f"Der Zielort-Schritt in {surface} prüft nicht, ob es die Nummer gibt – "
            f"dann meldet der Dialog Erfolg und beim Aufrufer passiert nichts."
        )


def test_the_target_field_is_a_searchable_reference():
    """**«001» oder «Clemens» muss reichen** (#732) – wie bei jeder Referenz im Haus.

    Ein reines Nummernfeld verlangt, dass man die Objektnummer auswendig weiss. Das Haus
    hat dafür `SearchSelect`; hier sucht es serverseitig, weil die Menge der Halter das
    halbe ERP ist. Kein zweites Auswahlfeld – dieselbe Komponente, andere Quelle.
    """
    code = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    assert "ObjectSelect" in code and "searchPlaces" in code, (
        "Das Zielfeld ist wieder ein reines Nummernfeld – dann muss man die "
        "Objektnummer auswendig wissen."
    )


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


def test_the_record_shows_a_state_only_when_it_changed():
    """**Ein Zustand, der sich nicht ändert, ist keine Aussage** (#726).

    Ein Durchläufer führt «Im Prozess» → «Im Prozess»; in jeder Zeile des Protokolls
    stünde dasselbe Wort. Gefragt wird nach den **Daten** (`status_before` ≠
    `status_after`), nicht nach dem Modultyp – die Oberfläche muss nicht wissen, welcher
    Typ was tut, und der Dienst liefert weiterhin beide Werte.
    """
    code = _code(_read(FRONTEND / "components" / "erp" / "step-record.tsx"))
    assert "entry.status_after !== entry.status_before" in code, (
        "Das Protokoll zeigt den Nachher-Zustand wieder unbedingt – beim Durchläufer "
        "ist das in jeder Zeile dasselbe Wort."
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
# «Leer» ist eine Wahl, und der Scanner nennt die Nummer (Testnotizen #734–#737)
# ---------------------------------------------------------------------------

def test_nothing_is_a_choice_not_three_workarounds():
    """**«Kein Ziel» steht in der Liste, in der man wählt.**

    Bug-Form: dieselbe Aussage an drei Stellen – ein erklärender Platzhalter («leer lassen
    für …»), ein Erklärsatz darunter und ein X-Knopf daneben. Keine davon war die Liste,
    und der Knopf war eine Rücknahme, keine Wahl (Testnotizen #734/#735/#736).
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "emptyOption" in fields, (
        "`SearchSelect` muss «nichts» als erste Zeile der Liste anbieten können – sonst "
        "wächst der Notbehelf beim nächsten Feld wieder nach."
    )
    designer = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    assert "emptyOption" in designer, "Das Bewegen-Ziel nennt seine Leer-Wahl nicht."
    assert "Ziel entfernen" not in designer, (
        "Der X-Knopf ist eine Rücknahme neben der Liste – die Wahl gehört hinein."
    )
    assert "leer lassen" not in designer.lower(), (
        "Der Platzhalter erklärt wieder, was die Liste sagen soll."
    )
    assert "Ohne Ziel wird beim Ausführen gescannt" not in _read(
        FRONTEND / "components" / "erp" / "process-designer.tsx"), (
        "Der Erklärsatz unter dem Feld ist zurück – dritte Stelle für eine Aussage."
    )


def test_a_scan_label_names_the_kind_not_the_number():
    """**Das Label nennt die Sorte, die Nummer hängt der Scanner an.**

    Bug-Form: «Instanz 100000825 100000825 scannen» (Testnotiz #737). `objectCodes.prompt`
    setzt die erwartete Nummer hinter das Label – schreibt eine Aufrufstelle sie auch
    hinein, steht sie zweimal da.

    Geprüft wird die **Regel**, nicht der Einzelfall: kein `ScanStep`-Label darf eine
    Objektnummer bauen.
    """
    scan = _code(_read(FRONTEND / "lib" / "scan.ts"))
    assert "prompt(step)" in scan or "prompt(" in scan, "Der Platzhalter wird nicht mehr zentral gebaut."

    # **Jede** `label:`-Zuweisung, nicht nur die am Zeilenanfang: die Bug-Form stand in
    # einer einzeiligen Objektliteral-Zeile (`{ label: \`Instanz ${…}\`, kind: … }`), und
    # ein Wächter, der nur `^label:` sieht, lässt sie durch – geprüft und korrigiert.
    #
    # Geprüft wird nur, was ein **Scan-Schritt** ist: eine Auswahl-Option darf ihre Nummer
    # sehr wohl anzeigen – dort ist sie die Zeile, nicht der Auftrag an den Menschen.
    bad: list[str] = []
    for path in sorted((FRONTEND / "components").rglob("*.tsx")) + [FRONTEND / "lib" / "scan.ts"]:
        code = _code(_read(path))
        for m in re.finditer(r"\blabel:", code):
            window = code[m.start():m.start() + 320]
            if not re.search(r"\b(expected|suggest|restrict|exists|kind):", window):
                continue                      # kein ScanStep – z. B. eine Options-Zeile
            if "formatObjectId" in _expr(window) or re.search(r"\bobject_id\b", _expr(window)):
                bad.append(f"{path.name}: {_expr(window).strip()[:90]}")
    assert not bad, (
        "Ein Scan-Label baut eine Objektnummer ein – der Scanner hängt sie selbst an "
        "(`objectCodes.prompt` aus `expected`), und dann steht sie zweimal im "
        "Platzhalter:\n  " + "\n  ".join(bad)
    )


def _expr(window: str) -> str:
    """Der **Wert** einer `label:`-Zuweisung – bis zum Komma auf gleicher Klammerebene.

    Ohne diese Abgrenzung liest ein Wächter das Nachbarfeld mit und meldet
    `label: 'Zielort', expected: target.object_id` als Fehler, obwohl das Label sauber ist.
    """
    body = window[window.index(":") + 1:]
    depth = 0
    for i, ch in enumerate(body):
        if ch in "([{`":
            depth += 1
        elif ch in ")]}`":
            depth -= 1
            if depth < 0:
                return body[:i]
        elif ch == "," and depth == 0:
            return body[:i]
    return body


# ---------------------------------------------------------------------------
# EIN Referenzfeld, überall (Testnotiz #738)
# ---------------------------------------------------------------------------

def test_a_record_reference_is_always_the_same_field():
    """**«Welchen Datensatz meinst du?» hat EINE Bauart.**

    Bug-Form: vier – ein Auswahlfeld mit Server-Suche, eines mit fertigen Optionen, ein
    natives `<select>` über alle Artikel des Hauses (nicht durchsuchbar, tausend Knoten je
    Zeile) und der Scanner mit eigener Suche. Wer «100000743» tippte, fand je nach Stelle
    etwas oder nichts.
    """
    picker = FRONTEND / "components" / "erp" / "object-select.tsx"
    assert picker.exists(), "Das eine Referenzfeld (`ObjectSelect`) fehlt."
    code = _code(_read(picker))
    assert "SearchSelect" in code, (
        "`ObjectSelect` muss AUF `SearchSelect` bauen – ein zweites Auswahlfeld daneben "
        "wäre der erste Weg, der beim nächsten Feld ausläuft."
    )
    assert "useScan" in code and "suggest" in code, (
        "Kamera und Tastatur stehen nebeneinander – und der Scanner bekommt dieselbe "
        "Suche wie das Feld, sonst findet er bei einer Teileingabe nichts."
    )

    # **Kein natives Dropdown über Datensätze mehr.** Aufzählungen (Währung, Land,
    # Ja/Nein) bleiben erlaubt – sie sind endlich und keine Referenz.
    for path in sorted((FRONTEND / "components" / "erp").rglob("*.tsx")):
        code = _code(_read(path))
        for m in re.finditer(r"<select\b", code):
            window = code[m.start():m.start() + 900]
            assert "object_id" not in window, (
                f"{path.name} wählt einen Datensatz über ein natives <select> – "
                f"nicht durchsuchbar, und bei tausend Artikeln tausend Knoten je Zeile. "
                f"Dafür gibt es `ObjectSelect`."
            )


def test_the_search_condition_is_number_or_name_everywhere():
    """**Nummer ODER Name – eine Bedingung, ein Modul.**

    Bug-Form: dreimal ausgeschrieben und an der vierten Stelle nur der Name. Wer
    «100000743» in die Artikel-Auswahl tippte, fand nichts, obwohl die Nummer im Dropdown
    darunter stand (#738). Ein Weg, der an drei Stellen richtig ist, ist keine Regel.
    """
    src = _read(BACKEND / "app" / "services" / "lookup.py")
    assert "def matches(" in src, "Die eine Suchbedingung (`services/lookup`) fehlt."
    for path in ("routers/articles.py", "routers/instances.py", "routers/orders.py",
                 "services/places.py"):
        code = _read(BACKEND / "app" / path)
        assert "lookup.matches(" in code, (
            f"{path} schreibt seine Suchbedingung selbst aus – genau die Stelle, an der "
            f"sie beim nächsten Mal abweicht."
        )


def test_the_camera_lives_in_the_field_not_beside_it():
    """**EIN Bedienelement mit zwei Eingängen, nicht zwei Bedienelemente.**

    Bug-Form: das Referenzfeld und daneben ein eigener Scan-Knopf (`erp-idbtn`) – zwei
    Flächen für **eine** Frage («welchen Datensatz meinst du?»). Die Kamera sitzt jetzt am
    rechten Innenrand des Feldes und ersetzt dort das Zierzeichen: dass es eine Liste
    gibt, sagt der Klick, und eine echte Aktion ist den Platz wert.

    Geprüft wird die **Regel**, nicht die Optik: `SearchSelect` muss eine Aktion **im**
    Feld tragen können, und `ObjectSelect` darf keinen Knopf daneben mehr stellen.
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "action?: {" in fields and "erp-fieldaction" in fields, (
        "`SearchSelect` kann keine Aktion am rechten Innenrand tragen – dann wächst der "
        "zweite Knopf daneben wieder nach."
    )
    # Der Klick gehört der Aktion: er darf weder den Fokus ins Feld ziehen noch die Liste
    # offen stehen lassen (sie liegt INNERHALB des Feldes, der Klick-daneben-Schliesser
    # greift dort nicht).
    assert "onMouseDown={(e) => e.preventDefault()}" in fields, (
        "Der Klick auf die Aktion zieht den Fokus ins Eingabefeld – die Liste klappt auf, "
        "während sich der Dialog davorlegt."
    )

    picker = _code(_read(FRONTEND / "components" / "erp" / "object-select.tsx"))
    assert "action={{" in picker, "`ObjectSelect` reicht die Kamera nicht als Feld-Aktion durch."
    assert "erp-idbtn" not in picker, (
        "Der eigene Scan-Knopf neben dem Feld ist zurück – zwei Bedienelemente für eine "
        "Frage."
    )
    # Und der Platz dafür kommt aus dem Feld, nicht aus einem Umbruch daneben.
    assert "paddingRight: action ? 34 : 28" in fields, (
        "Das Feld macht der Aktion keinen Platz – der Text läuft unter das Symbol."
    )


def test_the_dialog_is_the_same_field_only_big():
    """**Feld und Scanner sind sichtbar dieselbe Sache.**

    Bug-Form: dieselbe Frage in zwei Formensprachen – hier ein Dropdown mit einem
    fertigen String je Zeile, dort ein Vollbild mit eigener Zeilenform, eigenem
    Platzhalter und ohne die «nichts»-Wahl, die daneben im Feld steht. Beide riefen
    seit #738 dieselbe Suche und lieferten dieselben Treffer – man sah es ihnen nur nicht
    an, und die Frage «warum gibt es das zweimal» blieb.

    Drei Träger, alle drei aus **einer** Quelle: Platzhalter · Zeilenform · «nichts».
    """
    lib = _code(_read(FRONTEND / "lib" / "scan.ts"))
    picker = _code(_read(FRONTEND / "components" / "erp" / "object-select.tsx"))
    dialog = _code(_read(FRONTEND / "components" / "scan" / "scan-dialog.tsx"))
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))

    # (1) EIN Platzhalter, eine Quelle – und er ist kein Handlungsauftrag mehr: «scannen»
    #     wäre in einem Textfeld falsch, und genau das Verb war das Einzige, was die
    #     beiden Oberflächen daran hinderte, denselben Satz zu tragen.
    assert "export const LOOKUP_HINT" in lib, "Der gemeinsame Platzhalter fehlt."
    assert "LOOKUP_HINT" in picker, (
        "Das Referenzfeld schreibt seinen Platzhalter selbst aus – dann läuft er beim "
        "nächsten Wort vom Dialog weg."
    )
    prompt = _body(lib, "prompt", kind="function") if "function prompt" in lib else lib[
        lib.index("prompt(step) {"):lib.index("prompt(step) {") + 260]
    assert "LOOKUP_HINT" in prompt and "scannen" not in prompt, (
        "`objectCodes.prompt` ist wieder ein Handlungsauftrag statt eines Platzhalters – "
        "in einem Textfeld steht dann «scannen»."
    )

    # (2) EINE Zeilenform – buchstäblich dasselbe Bauteil, nicht dieselbe Absicht.
    assert "export function OptionRow" in fields, "Die eine Zeilenform fehlt."
    assert "OptionRow" in dialog, (
        "Der Scanner baut seine Vorschlagszeile wieder selbst – dann sieht dieselbe "
        "Auswahl je nach Oberfläche anders aus."
    )
    assert "fontFamily: 'var(--font-mono)'" not in dialog, (
        "Im Dialog steht wieder eine eigene Zeilen-Auszeichnung neben `OptionRow`."
    )

    # (3) «Nichts» steht auch im Dialog – sonst müsste man ihn schliessen, um eine
    #     Entscheidung zu treffen, die er selbst anbietet.
    assert "emptyOption?: { label: string; pick: () => void }" in lib, (
        "Der Scan-Schritt kennt keine «nichts»-Wahl."
    )
    assert "empty.pick()" in dialog, "Der Dialog bietet die «nichts»-Wahl nicht an."
    assert "emptyOption: emptyOption ?" in picker, (
        "Das Feld reicht seine «nichts»-Wahl nicht an den Scanner durch."
    )

    # (4) Dieselbe Anatomie: die SORTE steht als Beschriftung, nicht im Platzhalter –
    #     der verschwindet beim ersten Zeichen, und im Vollbild bliebe dann nichts mehr,
    #     das sagt, wonach gesucht wird.
    assert "style={kindLine}" in dialog and "{kind}</span>" in dialog, (
        "Der Dialog nennt die Sorte nicht mehr als Beschriftung über der Leiste."
    )
    assert "textTransform: 'uppercase', letterSpacing: '0.05em'" in dialog, (
        "Die Beschriftung im Dialog trägt nicht die Typografie von `fields.Label` – dann "
        "ist es eine zweite Formensprache."
    )
