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


def _body(source: str, name: str, *, kind: str = "def") -> str:
    """Der Rumpf genau einer Funktion/Klasse – ohne die nächste mitzunehmen.

    Ein blosses ``split`` läuft bis ans Dateiende und trifft dann Nachbarn, die gar nicht
    gemeint waren; der Test schlüge aus einem Grund fehl, der nichts mit ihm zu tun hat.
    """
    head = f"{kind} {name}"
    start = source.index(head)
    rest = source[start + len(head):]
    end = re.search(r"\n(?:def |class |@)", rest)
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
    assert columns == {"id", "object_id", "status", "end_status"}, (
        f"models/order.py trägt {sorted(columns)} – erwartet id, object_id, status, "
        f"end_status (created_at/updated_at/is_active kommen aus dem TimestampMixin)."
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
    # Sie wird NACH der Exklusivitätsprüfung gezogen: eine Sequence ist nicht
    # transaktional, ein Rollback danach liesse eine Lücke im Nummernkreis.
    body = svc.split("def release(")[1]
    assert body.index("_assert_exclusive") < body.index("next_object_id(db,"), (
        "Die Objektnummer wird vor der Exklusivitätsprüfung gezogen – jeder Verstoss "
        "verbrennt dann eine Nummer."
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
    assert "ProcessDiagram" in detail, "Der Auftrag-Reiter zeigt das Diagramm nicht."
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
    assert m.group(1).count(",") + 1 == len(st.STATUSES), (
        "Die Oberfläche führt mehr oder weniger Statuswerte als das Backend."
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


def test_an_instance_can_be_created_in_the_browser():
    """Ohne Instanz gibt es keine Einzelinstanz – und ohne die keinen Prozess.

    ``api.createInstance`` existierte, wurde aber von **keiner** Stelle aufgerufen: der
    «+»-Knopf im Feed kennt nur Artikel und Auftrag, und der Bestand-Reiter zeigte nur
    an. Damit war der Ablauf im Browser nicht startbar, obwohl jeder Endpunkt dafür da
    war – eine Lücke, die kein Backend-Test sehen kann.
    """
    detail = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "createInstance" in detail, (
        "Der Bestand-Reiter kann keine Instanz anlegen – dann lässt sich der Prozess "
        "im Browser gar nicht erst beginnen."
    )
    # Typ und Anzahl werden ausdrücklich verlangt, nichts aus dem Artikel erraten –
    # dieselbe Regel wie in ``schemas/instance.InstanceCreate``.
    assert "KIND_LABEL" in detail, "Der Typ wird nicht gewählt, sondern geraten."


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
    # Die Suffix-Vergabe steht in genau diesem Modul, in zwei Formen derselben Regel:
    # bei 1 beginnen (neue Instanz) und weiterzählen (bestehende).
    assert "def create_instances(" in svc and "def add_units(" in svc

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
                  "_assert_chain(", "_assert_exclusive(", "assert_quantity("):
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
    assert "disabled={!hasArticle || !hasTemplate}" in ui, (
        "«Neu» ist ohne Erzeugungsprozess nicht gesperrt."
    )
    assert "Erzeugungsprozess" in ui, "Der Grund steht nicht im Klartext."
    # FIFO ist ein Vorschlag, kein Zwang: die Auswahl bleibt sichtbar und abwählbar.
    assert "fifo" in ui.lower() and "entfernen" in ui


def test_large_quantities_are_counted_not_listed():
    """Bei Menge 5000 zeigt das Diagramm **eine Pille mit Anzahl**, nicht 5000 Zeilen.

    Die Datenhaltung bleibt pro Einzelinstanz – dies ist die Darstellungsfrage. Und der
    Deckel der Historie wird ausgewiesen: eine stumm gekappte Liste sähe aus wie die
    ganze Wahrheit.
    """
    svc = _read(BACKEND / "app" / "services" / "process.py")
    assert "def unit_groups(" in svc and "func.count(" in svc, (
        "Die Gruppen werden nicht gezählt, sondern aufgelistet."
    )
    schema = _read(BACKEND / "app" / "schemas" / "order.py")
    assert "class UnitGroup(" in schema and "event_count" in schema
    diagram = _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")
    assert "DiagramGroup" in diagram and "g.count" in diagram
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "von {total} Einträgen" in detail, "Der Deckel der Historie wird verschwiegen."


def test_the_article_carries_a_template_tab_that_cannot_execute():
    """Der Reiter «Erzeugungsprozess» nutzt **dieselbe** Darstellung wie der Auftrag.

    Kein Nachbau: der Unterschied liegt nicht in der Optik, sondern darin, was fehlt –
    keine Einzelinstanzen, kein Start, keine Ausführung (§8.2).
    """
    detail = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    assert "'prozess'" in detail and "Erzeugungsprozess" in detail
    assert "ProcessDiagram" in detail, "Der Reiter baut die Darstellung nach."
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
    editor = _read(FRONTEND / "components" / "erp" / "module-editor.tsx")
    assert "STATUS_VALUES" not in editor and "statusLabel" not in editor, (
        "Der Editor bietet wieder eine Status-Auswahl an."
    )
    # Das Testmodul ist ersatzlos weg – es war ein Testvehikel, kein Modul.
    assert "testmodul" not in _read(BACKEND / "app" / "models" / "process_step.py")
    assert "testmodul" not in _read(FRONTEND / "components" / "erp" / "order-detail.tsx")


def test_capture_is_written_only_in_the_process():
    """Eine Erfassung entsteht, wenn ein Stück vor einem Modul steht – sonst nie.

    Der frühere Weg (Formular am Instanz-Detail) legte Werte ohne Anlass an und war eine
    zweite Tür zu derselben Sache.
    """
    router = _read(BACKEND / "app" / "routers" / "captures.py")
    assert "@router.post" not in router, (
        "Es gibt wieder einen Schreib-Endpunkt für Erfassungen ausserhalb des Prozesses."
    )
    panel = _read(FRONTEND / "components" / "erp" / "capture-panel.tsx")
    assert "recordCapture" not in panel, "Das Instanz-Detail erfasst wieder selbst."

    model = _read(BACKEND / "app" / "models" / "capture.py")
    for column in ("order_id", "step_id"):
        assert f"{column}: Mapped[int]" in model, (
            f"``captures.{column}`` fehlt – eine Erfassung ohne Anlass wäre wieder möglich."
        )


def test_the_article_process_tab_is_the_order_component():
    """Der Reiter «Erzeugungsprozess» ist eine **Übernahme**, kein Nachbau.

    Gleiche Darstellung, gleiche Prozesslinien, gleicher Modul-Editor. Der einzige
    Unterschied ist der fehlende Definitionsbereich darüber – ein Artikel hat keine
    Einzelinstanzen.
    """
    tab = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    order = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    for shared in ("ProcessDiagram", "AddModule"):
        assert shared in tab and shared in order, (
            f"{shared} wird nicht an beiden Definitionsorten benutzt – zwei Stände driften."
        )
    assert "DefinitionLines" not in tab, (
        "Der Artikel hat keine Einzelinstanzen – ein Definitionsbereich gehört nicht hierhin."
    )
    assert 'mode="definition"' in tab


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
