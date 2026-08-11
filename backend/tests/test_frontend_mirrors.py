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

def test_the_status_list_is_closed_and_says_the_same_on_both_sides():
    """Module wählen aus einer **geschlossenen** Liste – sie erfinden keine Werte.

    Läuft die Liste zwischen Backend und Oberfläche auseinander, zeigt die eine Seite
    einen Zustand, den die andere nicht kennt: genau die zweite Wahrheit, gegen die die
    geschlossene Liste gebaut ist.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    ts = _read(FRONTEND / "lib" / "process-status.ts")
    for value, text in st.STATUS_LABELS.items():
        assert f"'{value}'" in ts, f"Das Frontend kennt den Status «{value}» nicht."
        assert text in ts, f"Die Beschriftung «{text}» fehlt im Frontend."
    # Kein erfundener Zusatzwert auf der TS-Seite.
    m = re.search(r"export const STATUS_VALUES = \[(.*?)\]", ts, re.S)
    assert m, "STATUS_VALUES fehlt."
    listed = [v for v in re.split(r"[,\s]+", m.group(1)) if v]
    assert len(listed) == len(st.STATUSES), (
        f"Die Oberfläche führt {len(listed)} Statuswerte, das Backend {len(st.STATUSES)}."
    )


def test_colour_hangs_on_the_status_at_exactly_one_place():
    """Farbe hängt am **Status**, nie an der Position – und die Zuordnung steht EINMAL.

    Baut eine Komponente sich ihre eigene Farblogik, sieht derselbe Zustand an zwei
    Stellen verschieden aus, und jede neue Ansicht muss die Regel neu erfinden.
    """
    for name in ("process-diagram.tsx", "order-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "statusCfg" in src, f"{name} liest die zentrale Zuordnung nicht."
        # ``MODULE_TONE`` ist ausdrücklich erlaubt: Prozessmodule tragen eine eigene,
        # von der Ampel getrennte Farbfamilie (§5.3). Verboten ist der Griff zur Ampel.
        for ampel in ("TONE.done", "TONE.pending", "TONE.danger"):
            assert ampel not in src, (
                f"{name} greift direkt auf «{ampel}» zu – die Zuordnung Status→Farbe "
                f"gehört in lib/process-status.ts."
            )


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
        "append-only, und die Struktur ist nach der Freigabe eingefroren."
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
    stock = _read(FRONTEND / "components" / "erp" / "instance-list.tsx")
    assert "onCreated" not in stock and "api." not in stock, (
        "Die Bestandsliste schreibt – sie ist eine Summierung, keine Werkbank."
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
                  "_assert_chain(", "held_by(", "_assert_may_leave(",
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
    assert {t.key for t in ct.ALL} == {"text", "bool", "photo", "signature", "measure"}
    assert len(files) == len(ct.ALL), (
        "Jede Datei im Paket ist genau ein Typ – sonst wird die Registry zur Aufzählung."
    )

    registry = _read(pkg / "__init__.py")
    assert "iter_modules" in registry, "Ohne Auto-Erkennung gäbe es eine Liste zum Vergessen."
    for hay in (registry, _read(pkg / "base.py")):
        assert 'type == "' not in hay and "type == '" not in hay, (
            "Ein Typ-Vergleich ist der Anfang der Kette, die es nicht geben soll."
        )


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

    ts = _read(FRONTEND / "lib" / "process-status.ts")
    m = re.search(r"export const ORDER_STATUSES = \[(.*?)\]", ts, re.S)
    assert m, "ORDER_STATUSES fehlt im Frontend."
    assert "FREIGEGEBEN" not in m.group(1), (
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


def test_everything_captured_is_mandatory():
    """**Das Feld «Pflicht ja/nein» ist gelöscht** – Modell, Migration, UI, Validierung.

    Ein Schalter dafür wäre die Frage, warum man einen Erfassungspunkt anlegt, den
    niemand ausfüllen muss; und jeder ausgeschaltete Punkt eine Lücke, die erst später
    auffällt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import capture_types
    from app.schemas.process import CapturePoint, CapturePointInput

    assert "required" not in CapturePointInput.model_fields
    assert "required" not in CapturePoint.model_fields
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

    # Und das Label wird wörtlich aus §2 abgeleitet: der Start-Eintrag trägt «Im Prozess».
    proc = _read(BACKEND / "app" / "services" / "process.py")
    body = _body(proc, "deviation_flags")
    assert "ProcessEvent" in body and "KIND_START" in body and "IM_PROZESS" in body, (
        "«Abweichung» kommt nicht aus dem Log – dann ist es irgendwo gespeichert."
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
    assert "current_step_id" not in hand.split("values(")[-1], (
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
    schema = _read(BACKEND / "app" / "schemas" / "process.py")
    point = _code(schema[schema.index("class CapturePointInput"):schema.index("class ModuleConfigInput")])
    assert "min_length" not in point, (
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
    assert "hasNew" in ui and "{!hasNew && (" in ui, "Der Knopf «Zeile» bleibt trotz «Neu»."
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
    assert "unitNumber?: string;" in detail, "Der Seed verlangt weiterhin ein Stück."


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

    # Der Vorschlag hängt an seiner Grundlage (Stücke UND Menge), nicht an einem Ereignis.
    effect = re.search(r"useEffect\(\(\) => \{\s*if \(!options \|\| chosen\.length\)[\s\S]*?\}, \[([^\]]*)\]\);", code)
    assert effect, "Die FIFO-Vorauswahl ist nicht mehr auffindbar."
    deps = {d.strip() for d in effect.group(1).split(",") if d.strip()}
    assert deps == {"options", "quantity"}, (
        f"Die Vorauswahl hängt an {sorted(deps)}. Ihre Grundlage sind die vorhandenen "
        f"Stücke UND die verlangte Menge – ändert sich eine davon ohne neuen Vorschlag, "
        f"steht dort «0 von 3»."
    )
    assert "!o.in_order" in code, (
        "Die Vorauswahl schlägt wieder Stücke vor, die in einem anderen Auftrag laufen – "
        "daraus würde still eine Abweichung."
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
