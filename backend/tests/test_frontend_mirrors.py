"""Spiegel über die API-Grenze – was auf beiden Seiten steht, darf nicht auseinanderlaufen.

Das Frontend pflegt einige Aufzählungen von Hand (schnell, ohne Generierung). Damit sie
nicht still von den Backend-Quellen abweichen, vergleicht dieser Wächter beide Seiten.

Nach dem Basis-Neuaufbau ist die Liste kurz – das ist der Punkt: es gibt kaum noch etwas
zu spiegeln, weil es kaum noch etwas gibt. Was hier fehlt, fehlt absichtlich.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"


def _read(path: pathlib.Path) -> str:
    assert path.exists(), f"Erwartete Datei fehlt: {path}"
    return path.read_text(encoding="utf-8")


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
    body = svc.split("def add_units(")[1]
    assert "next_object_id" not in body and "next_object_ids" not in body, (
        "add_units vergibt Objektnummern aus dem gemeinsamen Kreis – die Nummer einer "
        "Einzelinstanz ist <Instanznummer>-<Suffix>, abgeleitet."
    )
    objects = _read(BACKEND / "app" / "services" / "objects.py")
    assert '"instance_unit"' not in objects, (
        "Die Einzelinstanz steht als eigener Objekttyp in der Registry."
    )


def test_the_suffix_is_cumulative():
    """Eine einmal vergebene Nummer kommt nie zurück – sie ist eine Identität, keine
    Position. Ermittelt unter Zeilensperre, damit zwei gleichzeitige Anlagen nicht
    dieselbe ziehen."""
    svc = _read(BACKEND / "app" / "services" / "instances.py")
    body = svc.split("def add_units(")[1]
    assert "func.max(InstanceUnit.suffix)" in body, "Der Suffix wird nicht mehr aus MAX abgeleitet."
    assert "with_for_update()" in body, (
        "Die Suffix-Vergabe läuft ohne Zeilensperre – zwei gleichzeitige Anlagen könnten "
        "dieselbe Nummer ziehen."
    )
    assert "is_active" not in body.split("func.max(InstanceUnit.suffix)")[1].split(")")[0], (
        "MAX filtert auf aktive Zeilen – dann käme die Nummer einer deaktivierten "
        "Einzelinstanz zurück."
    )


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

def test_the_process_logic_is_gone_from_both_sides():
    """Der Auftrag und seine Prozesslogik sind ersatzlos entfernt – nicht auskommentiert,
    nicht deaktiviert, nicht als Vorlage aufbewahrt."""
    # ``services/orders.py`` gibt es wieder – als Anlage des DATENSATZES, nicht als
    # Prozess-Engine. Der Unterschied wird unten geprüft (der Auftrag trägt nichts
    # ausser seiner Identität, und die Pflichteingaben stehen an einer Stelle).
    for gone in ("process.py", "subject.py", "reservation.py", "ledger.py",
                 "units.py", "recovery.py", "supply.py", "deviation.py", "provisioning.py"):
        assert not (BACKEND / "app" / "services" / gone).exists(), (
            f"services/{gone} ist wieder da – die Prozesslogik wird neu gebaut, nicht "
            f"wiederverwendet."
        )
    for gone in ("order-flow.tsx", "flow-line.tsx", "process-steps.tsx",
                 "order-positions.tsx", "purchase-step-panel.tsx"):
        assert not (FRONTEND / "components" / "erp" / gone).exists(), (
            f"components/erp/{gone} ist wieder da."
        )
    # ``order-detail.tsx`` gibt es wieder – aber als **Datensatz**-Fenster, nicht als
    # Prozess-Oberfläche. Der Unterschied ist hier festgehalten:
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "OrderFlow" not in detail and "ProcessSteps" not in detail, (
        "Das Auftrags-Fenster baut wieder Prozesslogik – die kommt neu, nicht zurück."
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


def test_the_order_carries_nothing_but_its_identity():
    """Der Auftrag trägt heute **nur** seine Objektnummer und die Systematik-Felder.

    Spalten auf Vorrat wären erfundene Anforderungen – was er führt, entscheidet sich
    mit der Prozesslogik. Bricht dieser Wächter, hat jemand ein Feld erfunden.
    """
    src = _read(BACKEND / "app" / "models" / "order.py")
    columns = {l.split(":")[0].strip() for l in src.split("\n") if "mapped_column(" in l}
    assert columns == {"id", "object_id"}, (
        f"models/order.py trägt {sorted(columns)} – erwartet nur id und object_id "
        f"(created_at/updated_at/is_active kommen aus dem TimestampMixin)."
    )


def test_the_required_fields_live_at_exactly_one_place():
    """Die Pflichteingaben des Auftrags stehen an EINER Stelle – heute leer, aber verdrahtet.

    Sie ist absichtlich schon da: sonst landen die Regeln später verteilt in Router,
    Schema und Oberfläche, und die Oberfläche legt einen anderen Massstab an als der
    Server.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import orders as orders_svc

    assert orders_svc.validate_draft({}) == [], (
        "validate_draft meldet Pflichtfelder – die sind noch nicht definiert. Wer welche "
        "einträgt, passt auch diesen Wächter an."
    )
    router = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "validate_draft" in router or "assert_saveable" in router, (
        "Der Router prüft nicht über die eine Stelle."
    )
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "validateOrder" in detail, (
        "Die Oberfläche fragt die Regel nicht ab, sondern formuliert sie vermutlich nach – "
        "das wären zwei Massstäbe für dieselbe Frage."
    )


def test_a_draft_never_touches_the_database():
    """Ein Auftragsentwurf lebt nur im Browser: keine Entwurfs-Zeile, keine vorreservierte
    Objektnummer, kein Autosave. Die Nummer entsteht ausschliesslich beim Speichern."""
    svc = _read(BACKEND / "app" / "services" / "orders.py")
    assert svc.count("next_object_id") == 2, (   # Import + genau EIN Aufruf
        "Die Objektnummer wird an mehr als einer Stelle gezogen."
    )
    assert "next_object_id" in svc.split("def create_order(")[1], (
        "Die Nummer entsteht nicht in create_order."
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
    from app.services import capture

    assert capture.evaluate([{"key": "n", "type": "text"}], {"n": "x"}) is None
    assert capture.evaluate([{"key": "l", "type": "measure"}], {"l": 5}) is None
    assert capture.evaluate(
        [{"key": "l", "type": "measure", "target": 10, "tolerance": 1}], {"l": 10.5}) == "passed"
    assert capture.evaluate(
        [{"key": "l", "type": "measure", "target": 10, "tolerance": 1}], {"l": 12}) == "failed"


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

    mock = _read(FRONTEND / "components" / "erp" / "order-process-mockup.tsx")
    assert "absolute" not in mock, (
        "Das Mockup positioniert einen Knoten absolut – Knoten liegen im Fluss."
    )
    assert "<svg" not in mock, (
        "Das Mockup zeichnet ein eigenes SVG – es gibt EINEN Rahmen, der das tut."
    )
    assert "anchors[" in mock, (
        "Die Linien lesen keine gemessenen Anker mehr."
    )


def test_the_process_object_is_one_component():
    """Ein Prozessobjekt = eine Komponente (§8). Der Modultyp ist Konfiguration.

    Kein Copy-Paste je Modulart – sonst wächst mit jedem Modul ein zweites Bauteil, das
    beim nächsten Design-Wechsel vergessen wird.
    """
    mock = _read(FRONTEND / "components" / "erp" / "order-process-mockup.tsx")
    assert mock.count("function ModuleCard") == 1, (
        "Es gibt mehr als eine Modul-Komponente."
    )
    assert "FlowNode" in mock, "Das Mockup benutzt die gemeinsame Knoten-Hülle nicht."


def test_the_mockup_says_that_it_is_one_and_touches_no_data():
    """Statische Beispieldaten, klar gekennzeichnet, ohne Datenbank.

    Ein Mockup, das man nicht als solches erkennt, ist eine Falschaussage über den
    Systemzustand – und eines, das Daten liest, ist keines mehr.
    """
    mock = _read(FRONTEND / "components" / "erp" / "order-process-mockup.tsx")
    assert "Mockup" in mock, "Das Mockup weist sich nicht als Mockup aus."
    assert "@/lib/api" not in mock and "useQuery" not in mock, (
        "Das Mockup hängt an der API – dann ist es keins."
    )
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "OrderProcessMockup" in detail, (
        "Der Auftrag-Reiter zeigt das Mockup nicht."
    )
