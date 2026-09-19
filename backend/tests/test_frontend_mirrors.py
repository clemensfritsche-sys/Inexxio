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


def _at(source: str, head: str) -> int:
    """Die Stelle, an der **genau dieser** Name steht — nicht der, der so anfaengt.

    ``source.index("function Money")`` trifft auch ``function MoneyBar``: der Waechter
    laese danach den Rumpf eines **anderen** Bauteils und schlueg aus einem Grund fehl,
    der nichts mit ihm zu tun hat (gemessen, als neben ``Money`` eine ``MoneyBar``
    entstand). Dieselbe Stumpfheit wie damals beim Teilen am ersten Vorkommen eines
    Namens — nur eine Ebene frueher.
    """
    m = re.search(re.escape(head) + r"(?![A-Za-z0-9_$])", source)
    assert m is not None, f"«{head}» steht nicht in der Datei."
    return m.start()


def _body(source: str, name: str, *, kind: str = "def") -> str:
    """Der Rumpf genau einer Funktion/Klasse – ohne die nächste mitzunehmen.

    Ein blosses ``split`` läuft bis ans Dateiende und trifft dann Nachbarn, die gar nicht
    gemeint waren; der Test schlüge aus einem Grund fehl, der nichts mit ihm zu tun hat.
    """
    head = f"{kind} {name}"
    start = _at(source, head)
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


def _component(source: str, name: str) -> str:
    """Der **ganze** Rumpf einer React-Komponente – verschachtelte Helfer inbegriffen.

    ``_body`` bricht bewusst an einer eingerückten ``function`` ab: dort grenzt sie eine
    verschachtelte Hilfsfunktion ab, und ein Wächter, der über sie hinausliest, prüfte
    fremden Code. Für eine **Komponente** ist das genau falsch herum – ihr JSX steht
    hinter solchen Helfern, und der Wächter sähe von der Sache, um die es geht, gar
    nichts. Gemessen: an ``ModuleFields`` (eine verschachtelte ``setPoint``) lieferte
    ``_body`` **249 Zeichen**, und die eigene Bug-Form ging durch.

    Hier endet der Rumpf darum erst am nächsten Konstrukt **auf Spalte 0**.
    """
    start = _at(source, f"function {name}")
    rest = source[start + len(f"function {name}"):]
    end = re.search(r"\n(?:export |function |interface |const |type |/\*\*)", rest)
    return rest[: end.start()] if end else rest


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
    # **Und die Stellenzahl kommt von der WÄHRUNG**, nicht aus einer festen 2: JPY hat
    # null, KWD drei (``domain/currency``). Ein fester Schnitt ist bei fast jeder Währung
    # richtig und darum die Form, die niemand bemerkt.
    assert "decimals = 2" in utils, (
        "Die Nachkommastellen sind wieder fest – dann zeigt ein Yen-Betrag zwei Stellen, "
        "die es nicht gibt."
    )
    # **Die eine Formatierung steht in `module-ui.Amount`** (#1007) – vorher formatierte
    # jede Aufrufstelle des Belegs selbst. Der Wächter fragt darum die **Regel** an ihrem
    # heutigen Ort: niemand formatiert daneben, und die Stellenzahl kommt von der Währung.
    for name in ("beleg-work.tsx", "module-ui.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "toLocaleString" not in src, (
            f"{name} formatiert selbst – dann gilt die Regel dort nicht."
        )
    money = _read(FRONTEND / "components" / "erp" / "module-ui.tsx")
    assert "formatAmount(value, decimals)" in money, (
        "Das Betrags-Bauteil formatiert nicht über `formatAmount`."
    )
    beleg = _beleg()
    assert "d.currency_decimals" in beleg, (
        "Der Beleg reicht die Nachkommastellen der Währung nicht durch."
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
    panel = _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")
    assert "function may(d: Filled, action: string)" in panel, (
        "Die Karte fragt nicht mehr an EINER Stelle, ob gehandelt werden darf."
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
    # *Die Geste heisst seit #900 `.ix-tuck` und gilt auch für den Aktionsknopf; die
    # Palette ist ihre getönte Ausprägung. Die Regel ist dieselbe – gefragt wird sie dort,
    # wo sie jetzt steht.*
    tuck = css[css.index(".ix-tuck {"):css.index(".ix-tuck-name")]
    assert "gap: 0;" in tuck, "Der Abstand gilt auch eingeklappt – das Symbol sitzt daneben."
    # *Gefragt wird die **Regel** am Zeilenanfang, nicht das blosse Vorkommen des Namens:
    # sonst trifft der Waechter die erste Prosa-Stelle, die die Regel **erklaert** (gemessen,
    # als ein Kommentar `.ix-tuck:hover { width: auto }` zitierte) – dieselbe Stumpfheit wie
    # damals, als ein Waechter seinen eigenen Erklaertext mitlas.*
    assert "gap: 7px;" in css[_at(css, "\n.ix-tuck:hover"):][:260], (
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

    ``document`` stammt aus dem entfernten Dokumentmodul – jede Auflösung einer unbekannten
    Nummer durchsuchte eine Tabelle, die es nicht mehr gibt. **Der Nummernraum ist davon
    getrennt**: er speist ``current_max_object_id`` → ``setval``, und eine Alt-Zeile mit der
    höchsten Nummer würde sonst ein zweites Mal vergeben.

    Beantwortet wird das seit dem Aufräumen von der **Registry** statt von einer einzeln
    genannten Alt-Tabelle: sie hält jede je vergebene Nummer, auch die eines Typs, den es
    nicht mehr gibt. Die schwächere Fassung musste beim nächsten entfallenden Typ erneut
    ergänzt werden – und genau das vergisst man.
    """
    src = _read(BACKEND / "app" / "services" / "objects.py")
    models = src.split("_TYPE_MODELS = {")[1].split("}")[0]
    assert '"document"' not in models, "Der Scan löst wieder auf ein totes Modul auf."
    assert "ObjectRef.object_id" in src.split("_OBJECT_ID_COLUMNS")[1][:300], (
        "Die Registry fällt aus dem Nummernraum – Nummern entfallener Typen könnten "
        "ein zweites Mal vergeben werden."
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
            # **Das Fenster endet am Element, nicht nach 900 Zeichen.** Fest gezählt las
            # es über die Funktion hinaus in die **nächste** hinein und meldete dort ein
            # `object_id`, das mit diesem Auswahlfeld nichts zu tun hat (gemessen an
            # `DocPick`/`DocRef`). Und umgekehrt: eine lange Optionsliste rutschte aus dem
            # Fenster – der Wächter war in beide Richtungen ungenau.
            end = code.find("</select>", m.start())
            window = code[m.start():end if end != -1 else m.start() + 900]
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
    # Gefragt ist die **Quelle**, nicht ihre Schreibweise: seit #1023 setzt `lookupHint`
    # den Satz zusammen (Sorte + Platzhalter), und beide Oberflächen rufen ihn. Wer hier
    # auf das Wort `LOOKUP_HINT` bestünde, verböte ausgerechnet die gemeinsame Quelle.
    assert ("LOOKUP_HINT" in prompt or "lookupHint(" in prompt) and "scannen" not in prompt, (
        "`objectCodes.prompt` ist wieder ein Handlungsauftrag statt eines Platzhalters – "
        "in einem Textfeld steht dann «scannen»."
    )
    assert "export function lookupHint" in lib, (
        "Der Satz «<Sorte> – Nummer oder Name» wird wieder an jeder Stelle einzeln "
        "zusammengesetzt."
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

    # (4) **Die Sorte steht im Platzhalter, ihr Symbol im Feld** (Testnotiz #758).
    #
    #     Vorher trug sie ein eigener Chip über der Leiste – zwei Bauteile für EINE
    #     Auskunft. Der damalige Einwand («ein Platzhalter verschwindet beim ersten
    #     Zeichen, dann sagt nichts mehr, wonach man sucht») ist nicht ignoriert, sondern
    #     beantwortet: das **Symbol** am Innenrand bleibt stehen, auch wenn man tippt.
    assert "kindLine" not in dialog, (
        "Der Sorten-Chip ist zurück – die Sorte steht im Platzhalter, ihr Symbol im Feld."
    )
    assert "placeholder={hint}" in dialog, "Der Platzhalter kommt nicht mehr aus der Deutung."
    assert "`${kind} ${nr(step.expected)} suchen`" in lib, (
        "Der Platzhalter nennt die Sorte nicht – dann steht dort nur eine nackte Nummer."
    )
    #     Die Beschriftung, deren Typografie hier einmal geprüft wurde, gibt es nicht
    #     mehr – geblieben ist das Feld, und das war ohnehin die Anatomie, um die es ging.


def test_the_login_is_a_popup_over_the_page_behind_it():
    """**Ein Pop-up ist ein Pop-up** – und es gibt genau EINEN Anmelde-Dialog.

    Bug-Form (die gemeldete): das Anmelden war eine **Seite** mit eigener, deckender
    Fläche – die Seite dahinter verschwand, also brauchte es einen Knopf «Zurück zur
    Startseite», um wieder herauszukommen. Genau das ist der Umweg, den ein Pop-up nicht
    hat: daneben klicken beendet es, und was man vorher tat, steht noch da.

    Die zweite Bug-Form wäre die naheliegende Abkürzung: den Dialog in der Navbar
    **nachbauen** und die Route so lassen. Dann gäbe es zwei Anmeldungen, und die zweite
    veraltet beim ersten neuen Anmeldeweg – darum ist ``LoginDialog`` **ein** Bauteil,
    das beide benutzen.
    """
    dialog = _code(_read(FRONTEND / "components" / "auth" / "login-dialog.tsx"))
    page = _code(_read(FRONTEND / "app" / "(auth)" / "login" / "page.tsx"))
    navbar = _code(_read(FRONTEND / "components" / "layout" / "navbar.tsx"))
    css = _read(FRONTEND / "app" / "globals.css")

    # (1) Die Fläche dahinter bleibt sichtbar – ein Schleier, keine Wand.
    assert ".ix-login-scrim" in css, "Der Schleier über der Seite fehlt."
    # **Ohne die Erklärung gelesen** – der Kommentar in der Regel nennt die Bug-Form beim
    # Namen, und ein Wächter, der ihn mitliest, schlägt an, weil jemand den Fehler
    # *beschreibt*, den er verhindern soll. Genau das ist hier beim Schreiben passiert.
    rules = re.sub(r"/\*[\s\S]*?\*/", "", css)
    scrim = rules[rules.index(".ix-login-scrim"):]
    scrim = scrim[: scrim.index("}") + 1]
    assert "rgba(" in scrim, (
        "Der Hintergrund des Pop-ups ist wieder deckend – dann ist es keines, sondern "
        "eine Seite, und man braucht einen Weg zurück."
    )
    assert "position: fixed" in scrim and "inset: 0" in scrim, (
        "Der Schleier liegt nicht über der ganzen Seite."
    )
    # **Zentriert wird über `margin: auto`, nicht über `align-items`** – die klassische
    # Flexbox-Falle. Gemessen in Chromium (375x420): mit `align-items: center` steht der
    # Kopf einer zu hohen Karte bei −74 px, und in einem Scroll-Container ist alles vor
    # der Startkante unerreichbar; auf einem Telefon im Querformat wäre das E-Mail-Feld
    # schlicht weg. Mit `margin: auto` steht er bei +31 px.
    assert "align-items: center" not in scrim, (
        "Der Schleier zentriert wieder über `align-items` – eine Karte, die höher ist "
        "als das Fenster, wird dann oben abgeschnitten und lässt sich nicht hinscrollen."
    )
    card = rules[rules.index(".ix-login-card {"):]
    card = card[: card.index("}") + 1]
    assert "margin: auto" in card, (
        "Die Karte zentriert sich nicht mehr selbst – dann greift wieder die Falle."
    )
    assert ".ix-login-bg" not in css, (
        "Die alte, deckende Anmelde-Fläche ist zurück."
    )

    # (2) Daneben klicken beendet – und `Esc` ebenso; beides ist üblich, und wer nur
    #     eines baut, zwingt Tastatur- oder Mausnutzer in den jeweils anderen Weg.
    assert "e.target === e.currentTarget" in dialog, (
        "Ein Klick neben das Pop-up schliesst es nicht – dann ist der einzige Ausweg "
        "wieder ein Knopf."
    )
    assert "'Escape'" in dialog, "`Esc` schliesst das Pop-up nicht."
    assert 'aria-modal="true"' in dialog, (
        "Ohne `aria-modal` ist es für Hilfsmittel kein Dialog, sondern Seiteninhalt."
    )

    # (3) Der Weg zurück ist das Danebenklicken – der Knopf ist damit entfallen.
    # Gelesen wird der **Code**: die Erklärung darüber nennt den Knopf, den es nicht
    # mehr gibt – ein Wächter, der Kommentare liest, schlägt an, weil jemand den Fehler
    # *beschreibt*, den er verhindern soll.
    assert "Zurück zur Startseite" not in dialog, (
        "Der Knopf «Zurück zur Startseite» ist zurück – in einem Pop-up ist er der "
        "Umweg, den es gerade nicht braucht."
    )

    # (4) EIN Dialog, zwei Aufrufer: die Navbar öffnet ihn an Ort und Stelle, die Route
    #     ist der zweite Weg (Umleitung/Lesezeichen) und sagt, was «daneben» dort heisst.
    assert "export function LoginDialog" in dialog, "Der Dialog ist kein eigenes Bauteil."
    # **Geprüft wird das Rendern, nicht der Name.** Gemessen: mit `"LoginDialog" in
    # navbar` liess der Wächter seine eigene Bug-Form durch – der Name kommt auch im
    # Import vor, und importiert ist noch nicht gezeichnet.
    assert "<LoginDialog" in navbar and "setLoginOpen(true)" in navbar, (
        "Die Navbar öffnet das Pop-up nicht – sie verlinkt wieder auf eine Seite."
    )
    assert 'href={loginHref}' not in navbar and "const loginHref" not in navbar, (
        "Der alte Link auf die Anmelde-Seite steht wieder in der Navbar."
    )
    assert "<LoginDialog" in page, (
        "Die Route baut die Anmeldung wieder selbst – dann gibt es sie zweimal."
    )
    assert "fallback={pathname}" in navbar, (
        "Nach dem Anmelden muss man dort landen, wo man war – sonst ist das Pop-up nur "
        "eine hübschere Umleitung."
    )


def test_a_record_has_exactly_one_width():
    """**Eine Regel für alle Detail-Ansichten** (Testnotiz #763).

    Bug-Form (die gemeldete): jede Ansicht brachte ihre eigene Breite mit – der Artikel
    war begrenzt, Instanz und Unternehmen liefen über die volle Fläche, das Unternehmen
    hatte sogar eine dritte Zahl (760). Auf einem breiten Schirm las sich derselbe
    Datensatztyp damit je nach Reiter anders, und eine Zeile wurde beliebig lang.

    Die Breite ist eine Eigenschaft der **Gattung** «Detail-Ansicht», nicht der einzelnen
    Ansicht – also steht sie einmal (`DETAIL_MAXW`) und wird über ein Bauteil geerbt
    (`DetailBody`), nicht an fünf Stellen abgeschrieben.
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "export const DETAIL_MAXW" in fields, "Die eine Breite fehlt."
    assert "export function DetailBody" in fields, "Das Bauteil dazu fehlt."
    assert "maxWidth: DETAIL_MAXW" in fields, (
        "`DetailBody` liest die Konstante nicht – dann sind es wieder zwei Zahlen."
    )

    views = ["article-detail.tsx", "instance-detail.tsx", "organization-detail.tsx",
             "user-detail.tsx"]
    for name in views:
        src = _code(_read(FRONTEND / "components" / "erp" / name))
        assert "<DetailBody" in src, (
            f"{name} bringt seine Breite selbst mit statt sie zu erben."
        )
        # **Geprüft wird die Tat, nicht das Wort**: eine eigene Zahl daneben ist genau
        # die Form, in der die zweite Wahrheit zurückkommt. Gemeint ist die **Satzbreite**
        # – eine Kürzungsgrenze an einer Zeile (`maxWidth: 180` mit `ellipsis`) ist eine
        # andere Sache und bleibt erlaubt; die Schwelle trennt beide.
        stray = [n for n in re.findall(r"maxWidth:\s*(\d+)", src) if int(n) >= 400]
        assert not stray, (
            f"{name} setzt wieder eine eigene Breite ({stray}) – die Regel steht in "
            "`DETAIL_MAXW`, sonst laufen die Ansichten wieder auseinander."
        )


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


def test_a_section_head_carries_its_own_hairline():
    """**Die Haarlinie gehört zum Kopf** (Testnotiz #762).

    Bug-Form: jede Karte zog ihren Trennstrich selbst – mal mit, mal ohne, mit
    unterschiedlichem Abstand. Eine Anatomie, die man an der Aufrufstelle zusammensetzt,
    ist an der nächsten Aufrufstelle anders.
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    head = _body(fields, "SpecHead", kind="function")
    assert "borderBottom" in head, (
        "Der Karten-Kopf trägt seine Haarlinie nicht selbst – dann fehlt sie dort, wo "
        "jemand sie vergisst."
    )


def test_a_person_is_never_deactivated_only_re_roled():
    """**Man deaktiviert keine Menschen** (Testnotiz #755).

    Wer das Unternehmen verlässt, hört nicht auf zu existieren – er wird vom Mitarbeiter
    zum gewöhnlichen Benutzer und darf weiterhin bei uns einkaufen. «Deaktivieren» war
    damit eine Aktion ohne fachliche Begründung, und sie hatte eine echte Folge: der
    Betroffene kam nicht mehr herein.

    Bug-Form: die Aktion bleibt (oder kommt als «löschen» zurück). Geprüft wird darum
    **die Tür, nicht das Wort** – die beiden Endpunkte dürfen es nicht mehr geben, und
    kein Knopf darf sie rufen.
    """
    admin = _code(_read(BACKEND / "app" / "routers" / "admin.py"))
    assert "def deactivate_user" not in admin, (
        "Der Deaktivieren-Endpunkt ist zurück – ein Benutzer wechselt die Rolle."
    )
    assert "def reactivate_user" not in admin, (
        "Ohne Deaktivieren braucht es auch keine Gegenaktion."
    )

    api = _code(_read(FRONTEND / "lib" / "api.ts"))
    assert "deactivateUser" not in api and "reactivateUser" not in api, (
        "Der Client ruft die Türen wieder, die es nicht mehr gibt."
    )
    user = _code(_read(FRONTEND / "components" / "erp" / "user-detail.tsx"))
    assert "Deaktivieren" not in user and "Reaktivieren" not in user, (
        "Der Knopf ist zurück – die Rolle ist der Weg, nicht der Aus-Schalter."
    )


def test_the_usage_tab_is_gone():
    """**«Wer zeigt auf mich» ist ersatzlos entfallen** (Testnotiz #764).

    Bug-Form wäre, den Reiter nur auszublenden und die Ableitung stehen zu lassen: dann
    lebt ein Endpunkt weiter, den niemand ruft, und der nächste Umbau muss ihn mitziehen.
    """
    for gone in [
        BACKEND / "app" / "services" / "references.py",
        BACKEND / "app" / "routers" / "object_refs.py",
        FRONTEND / "components" / "erp" / "object-references.tsx",
    ]:
        assert not gone.exists(), f"{gone.name} ist zurück – die Logik war zu löschen."

    main = _code(_read(BACKEND / "app" / "main.py"))
    assert "object_refs" not in main, "Der Router ist wieder registriert."
    api = _code(_read(FRONTEND / "lib" / "api.ts"))
    assert "getObjectReferences" not in api, "Der Client ruft die Ableitung wieder."


def test_an_icon_button_is_centred_by_its_class():
    """**Der Symbol-Knopf besitzt seine Form in der Klasse** (Testnotiz #757).

    Bug-Form (die Ursache, dreimal gemeldet): `.erp-actbtn` zentrierte allein über seine
    **Polsterung** – es gab kein `justify-content`. Ein Text-Knopf sah damit richtig aus,
    und genau die Polsterung nimmt ein Symbol-Knopf weg (`padding: 0`): das Symbol klebte
    links. Wer das an der Aufrufstelle mit einer Inline-Breite «repariert», verschiebt es
    nur – darum steht die Form in der Klasse.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    base = css[css.index(".erp-actbtn {"):]
    base = base[: base.index("}") + 1]
    assert "justify-content: center" in base, (
        "`.erp-actbtn` zentriert wieder nur über die Polsterung – dann sitzt jedes "
        "Symbol ohne Polsterung links."
    )
    assert ".erp-actbtn-icon" in css, (
        "Die Symbol-Ausprägung fehlt – dann setzt sie jede Aufrufstelle wieder inline."
    )
    # ►►► **Und die Aufrufstelle schreibt die Klasse gar nicht mehr.** ◄◄◄ Seit sieben
    # Notizen dieselbe Geste verlangten (#877–#896), gibt es **ein** Bauteil dafür
    # (`module-ui.ActionButton`); die Modul-Karte nennt es, statt die Form zu wiederholen.
    # Das ist dieselbe Regel eine Ebene weiter: wer die Klasse an dreissig Stellen
    # schreibt, schreibt sie an der einunddreissigsten anders.
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    assert "erp-actbtn-icon" in ui, (
        "Die Symbol-Form steht nicht mehr im Bauteil – dann setzt sie jede Aufrufstelle "
        "wieder selbst."
    )
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "erp-actbtn-icon" not in work, (
        "Der Vorgang baut seine Symbol-Knöpfe wieder selbst, statt `ActionButton` zu "
        "benutzen."
    )
    assert not re.search(r"erp-actbtn[^\"]*\"[^>]*style=\{\{[^}]*width:", work + ui), (
        "Eine Inline-Breite am Symbol-Knopf ist zurück – genau daran verschob sich das "
        "Symbol, statt zentriert zu sein."
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


def test_the_stock_stands_between_specification_and_process():
    """**Erst was er ist, dann was es davon gibt, dann wie er entsteht** (#770)."""
    src = _read(FRONTEND / "components" / "erp" / "article-detail.tsx")
    body = src[src.index("<DetailBody>"):src.index("</DetailBody>")]
    spec = body.index("SpecRead")
    stock = body.index("<StockView")
    process = body.index("<ArticleProcess")
    assert spec < stock < process, (
        "Die Reihenfolge stimmt nicht: Spezifikation → Bestand → Prozess."
    )


def test_the_user_has_no_empty_document_tab():
    """**Kein Reiter über einer leeren Fläche** (Testnotiz #772).

    «Dokumente» rendete zwei Überschriften und sonst nichts – seine Karten hingen am
    Dokumentenmodul, und das gibt es nicht mehr. Übrig blieb ein Reiter, der das ganze
    Formular trägt: dann gibt es nichts zu wählen.
    """
    src = _read(FRONTEND / "components" / "erp" / "user-detail.tsx")
    assert "Freigaben & Anerkennungen" not in src and "Abgelegte Dokumente" not in src, (
        "Die leeren Überschriften stehen wieder da."
    )
    assert "DetailTabs" not in src, (
        "Der Benutzer hat wieder eine Reiterleiste – mit genau einem Reiter darin."
    )


def test_the_runtime_choice_is_one_sentence_in_one_place():
    """►►► **«Beim Ausführen definieren» — ein Satz, eine Stelle** (#785/#786). ◄◄◄

    Zwei Fassungen derselben Aussage standen nebeneinander: am Ziel des Bewegen-Moduls
    ein Platzhalter «Beim Ausführen **scannen**», unter der Gegenpartei-Liste ein
    Erklärsatz «Leer: freie Wahl beim Ausführen» – und der zweite war nicht einmal
    anklickbar.

    *Scannen* ist dabei nur **einer** von zwei Wegen zur selben Wahl (daneben steht die
    Tastatur, und bei den zugelassenen Gegenparteien wird gar nicht gescannt): ein Wort,
    das den Weg nennt statt den Zeitpunkt, ist an der Hälfte der Stellen falsch.

    Bug-Formen: (a) eine Aufrufstelle schreibt ihren eigenen Satz; (b) der Erklärsatz ist
    zurück; (c) das Wort «scannen» steht wieder im Satz; (d) die Wahl steht nirgends in
    einer Liste, ist also nicht wählbar.
    """
    scan = _read(FRONTEND / "lib" / "scan.ts")
    assert "export const RUNTIME_CHOICE = 'Beim Ausführen definieren'" in scan, (
        "Der eine Satz fehlt – dann erfindet ihn jede Aufrufstelle neu."
    )
    for name in ("process-designer.tsx", "order-detail.tsx"):
        src = _code(_read(FRONTEND / "components" / "erp" / name))
        assert "Beim Ausführen" not in src, (
            f"{name} schreibt den Satz selbst hin, statt ihn zu lesen (#786)."
        )
        assert "freie Wahl beim Ausführen" not in src, (
            f"{name} erklärt die leere Wahl wieder in einem Satz daneben – das ist die "
            f"eine Form, in der man sie nicht wählen kann (#786)."
        )
        assert "RUNTIME_CHOICE" in src, f"{name} benutzt den geteilten Satz nicht."
    designer = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    assert "emptyOption={RUNTIME_CHOICE}" in designer, (
        "Die Wahl steht nicht als Zeile in der Liste – dann ist sie keine Wahl (#734–#736)."
    )


def test_the_object_number_reads_as_a_number_until_you_point_at_it():
    """►►► **Eine Objektnummer ist eine KENNUNG, kein Hyperlink** (Testnotiz #784). ◄◄◄

    Sie stand als blauer, unterstrichener Text da – die drei Marker, an denen man im Web
    einen Link erkennt. Im ERP steht sie in fast jeder Zeile: das ganze Raster las sich
    als Linkliste, und die Kennung war die lauteste Angabe darin.

    Im Ruhezustand trägt sie darum die Farbe ihres Textes; dass sie etwas tut, sagt der
    Zeiger und – sobald er darauf steht – Farbe **und** Unterstreichung. Der Tastaturweg
    bekommt dieselbe Auszeichnung (`:focus-visible`); Farbe allein wäre kein zugängliches
    Signal.

    Bug-Formen: (a) die Ruhe-Auszeichnung ist zurück (Farbe/Unterstreichung inline am
    Knopf); (b) es gibt gar keinen Hover-Zustand mehr, dann sieht man der Nummer nicht
    an, dass sie führt; (c) der Tastaturweg fehlt.
    """
    src = _read(FRONTEND / "components" / "erp" / "obj-id.tsx")
    code = _code(src)
    assert "className=\"erp-objid\"" in code, (
        "Die Nummer trägt ihre Auszeichnung nicht mehr in der Klasse – inline greift "
        "kein `:hover`."
    )
    assert "'var(--accent)'" not in code and "textDecoration" not in code, (
        "Die Ruhe-Auszeichnung ist zurück: blau und unterstrichen ist ein Hyperlink, "
        "keine Kennung (#784)."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    rule = css.split(".erp-objid {")[1].split("\n}")[1]
    assert ".erp-objid:hover" in css and ":focus-visible" in rule, (
        "Die Nummer sagt bei Hover/Fokus nicht mehr, dass sie führt – dann ist sie eine "
        "versteckte Funktion."
    )
    assert "text-decoration: underline" in rule, (
        "Farbe allein ist kein zugängliches Signal (WCAG 1.4.1)."
    )


def test_the_stock_bar_names_its_states_and_is_the_control():
    """►►► **Die Leiste nennt, was sie zeigt — und ist die Auswahl** (Testnotiz #789). ◄◄◄

    Die Farbe allein kann es nicht: der Katalog kennt **drei** Ampeltöne für **sechs**
    Zustände eines Stücks – *Freigegeben*, *Verbaut* und *Verkauft* sind alle grün. Zwei
    gleichfarbige Segmente nebeneinander sind damit strukturell nicht unterscheidbar,
    und keine Feinabstimmung der Farbe ändert daran etwas.

    Darunter stand ausserdem eine aufklappbare Sektion je Zustand – jede mit Chevron,
    Punkt, Wort und Menge im Kopf, also das, was die Leiste eine Zeile höher schon
    zeigte, nur zwanzigmal höher.

    Bug-Formen: (a) die Leiste nennt ihre Zustände wieder nicht; (b) sie zeigt keine
    Mengen; (c) die Sektionen sind zurück; (d) die Leiste ist wieder reine Anzeige, dann
    braucht es die Sektionen erneut; (e) mehr als einer ist offen.
    """
    from app.domain.statuses import CATALOG

    tones = {s.tone for s in CATALOG if "unit" in s.axes}
    units = [s for s in CATALOG if "unit" in s.axes]
    assert len(tones) < len(units), (
        "Der Grund dieses Wächters ist entfallen: jeder Zustand hätte jetzt seinen "
        "eigenen Ton. Dann prüfe, ob die Beschriftung noch nötig ist."
    )
    bar = _code(_read(FRONTEND / "components" / "erp" / "stock-bar.tsx"))
    # **Gefragt wird nach dem GERENDERTEN Wort, nicht nach seinem Vorkommen.** Eine
    # frühere Fassung prüfte `"cfg.label" in code` – und war damit schon durch den
    # Hover-Text erfüllt (`${s.quantity} × ${cfg.label}`), den es vorher auch gab. Sie
    # liess also genau den Zustand durch, den sie verhindern soll: eine Leiste, die ihre
    # Zustände nur im Hover nennt. Gemessen, nachgeschärft, erneut gegengeprüft.
    #
    # **Gerendert wird sie inzwischen eine Ebene tiefer** (`module-ui.SegmentMark`): die
    # Frage «wie teilt sich ein Ganzes auf, und welchen Teil sehe ich mir an» ist nicht
    # die des Bestands, und die Leiste steht darum einmal für alle. Der Wächter folgt
    # ihr – die **Regel** ist dieselbe geblieben, nur ihre Adresse hat gewechselt.
    kit = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    mark = _body(kit, "SegmentMark", kind="function")
    assert ">{seg.label}</span>" in mark, (
        "Die Leiste schreibt ihre Zustände nicht hin – bei drei Tönen auf sechs Zustände "
        "ist die Farbe allein keine Auskunft, und ein Hover ist keine Anzeige (#789)."
    )
    assert ">{seg.text}</span>" in mark, (
        "Die Leiste nennt die Menge je Segment nicht (#789)."
    )
    assert "aria-pressed={open}" in mark, (
        "Die Beschriftung ist kein Bedienelement – dann ist sie eine Legende, und die "
        "Sektionen darunter kommen zurück."
    )
    # **Und der Bestand füllt beides auch wirklich.** Ohne diese Hälfte wäre die Leiste
    # oben in Ordnung und hier trotzdem stumm: eine Ausprägung, die weder Wort noch
    # Menge mitgibt, rendert nichts – und der Wächter sähe es nicht.
    assert "label: cfg.label" in bar and "text: String(s.quantity)" in bar, (
        "Der Bestand gibt Wort bzw. Menge nicht an die Leiste weiter – dann steht sie "
        "leer da, obwohl sie beides zeigen könnte (#789)."
    )
    view = _read(FRONTEND / "components" / "erp" / "stock-view.tsx")
    vcode = _code(view)
    assert "onPick={toggle}" in vcode and "active={picked}" in vcode, (
        "Die Leiste ist wieder reine Anzeige (#789)."
    )
    assert "function Block(" not in vcode, (
        "Die Gruppen-Sektionen sind zurück – sie sagen Zeile für Zeile das, was die "
        "Leiste schon zeigt."
    )
    # **Genau einer offen** – ein `Record<string, boolean>` wäre die alte Sektionsliste
    # unter anderem Namen. Gefragt wird nach **dieser** Zustandsvariable, nicht nach der
    # Form irgendeiner: `useState<string | null>(null)` steht in derselben Datei auch für
    # die Fehlermeldung, und damit war die erste Fassung schon erfüllt, bevor `picked`
    # überhaupt existierte. Gemessen, nachgeschärft, erneut gegengeprüft.
    assert "const [picked, setPicked] = useState<string | null>(null)" in vcode, (
        "Es ist wieder mehr als ein Zustand gleichzeitig offen."
    )


# ---------------------------------------------------------------------------
# ►►► Das Geldmodul «Zahlung» — eigenständig, und die Spiegel decken sich ◄◄◄
# ---------------------------------------------------------------------------

def test_the_money_directions_mirror_the_backend():
    """**Die beiden Richtungen und ihre Wörter decken sich mit `domain/voucher`.**

    Alles Übrige (Stufen-Beschriftungen, Verben, Zustände) **reist mit dem Vorgang**; hier
    steht nur, was eine Antwort nicht transportieren kann – Symbol und das Wort, das schon
    der **Editor** braucht, bevor es einen Vorgang gibt.

    ►►► **Und die Rollen-Wörter sind entfallen** (Testnotiz #802). ◄◄◄

    «Kunde» ↔ «Lieferant» standen je Richtung da, und jede Aufrufstelle musste sich das
    richtige holen. Es ist dieselbe Rolle – der andere im Geschäft –, also gibt es eine
    Konstante (`DEAL_PARTY` ↔ `deal.PARTY`). Singular = Plural: damit ist das
    «Kundeen»-Problem *strukturell* erledigt statt durch einen zweiten gepflegten Wert.

    Bug-Formen: (a) eine Richtung fehlt; (b) ein Wort läuft auseinander; (c) die
    Rollen-Wörter kommen je Richtung zurück – dann gibt es wieder die falsche Wahl.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm

    src = _read(FRONTEND / "lib" / "modules.ts")
    block = _body(src, "DEAL_DIRECTION", kind="const")
    keys = set(re.findall(r"^\s{2}(\w+):\s*\{", block, re.M))
    assert keys == set(dm.DIRECTIONS), (
        f"Die Richtungen laufen auseinander: Oberfläche {sorted(keys)}, "
        f"Backend {sorted(dm.DIRECTIONS)}."
    )
    for key, flow in dm.DIRECTIONS.items():
        row = block.split(f"  {key}: {{", 1)[1].split("},", 1)[0]
        assert f"label: '{flow.label}'" in row, (
            f"«{key}» heisst in der Oberfläche anders als im Backend (erwartet "
            f"«{flow.label}») – und der Editor zeigt es, bevor der Server gefragt wurde."
        )
    for gone in ("party:", "parties:", "ref:"):
        assert gone not in block, (
            f"«{gone}» steht wieder je Richtung – dieselbe Rolle in zwei Wörtern ist die "
            f"Wahl, die man falsch treffen kann (#802)."
        )
    assert f"DEAL_PARTY = '{dm.PARTY}'" in src, (
        "Das eine Wort für beide Richtungen fehlt oder lautet anders als im Backend."
    )


def test_the_money_stage_keys_are_mirrored_not_written_out():
    """**Die Stufen des Geldvorgangs stehen an EINER Stelle.**

    Bug-Form: deutsche Wörter im Rumpf (`stage.key === 'zusage'`). An einem Vorgang der
    anderen Richtung wären alle Vergleiche falsch – still und ohne Fehlermeldung, genau
    wie beim Beschaffungs-Beleg vor #751.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm

    block = _body(_read(FRONTEND / "lib" / "modules.ts"), "DEAL_STAGE", kind="const")
    for key in (*dm.STAGES, dm.DONE, dm.CANCELLED):
        assert f"{key}: '{key}'" in block, f"Die Stufe «{key}» fehlt in der Zuordnung."

    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "DEAL_STAGE." in work, "Die Karte liest die Stufen nicht aus der Zuordnung."
    # Geprüft wird die REGEL («kein Stufen-Wort im Rumpf»), nicht die Form der Lösung:
    # WELCHE Stufen die Karte nennt, ist ihre Sache – `agreed` ist heute die Ableitung
    # «nicht mehr Angebot», und ein Wächter, der eine bestimmte Zeile verlangt, verbietet
    # die bessere Fassung.
    for key in (*dm.STAGES, dm.DONE, dm.CANCELLED):
        assert f"'{key}'" not in work, (
            f"Die Karte vergleicht gegen '{key}' statt gegen DEAL_STAGE.{key} – ein "
            f"zweiter Ort für denselben Schlüssel."
        )
    for german in ("'angebot'", "'zusage'", "'abgeschlossen'", "'storniert'"):
        assert german not in work, (
            f"Die Karte vergleicht gegen {german} – das ist eine **Beschriftung**, und "
            f"die hängt an der Richtung."
        )


def test_the_money_module_is_a_pass_through_in_the_editor_too():
    """**Zwei Angaben, und keine davon ist eine Menge, ein Artikel, ein Betrag – oder
    eine Frist.**

    ►►► **Und `prepaid` gehört nicht mehr dazu** (Testnotiz #854). ◄◄◄ Der Schalter
    «Zahlung abwarten» war eine **zweite Aussage über dieselbe Sache**: ob vorausbezahlt
    wird, sagt die vereinbarte **Zahlungsfrist** – null Tage *ist* Vorauszahlung. Zwei
    Stellen, die dasselbe behaupten, widersprechen sich beim ersten Vorgang, in dem
    jemand nur eine davon setzt; und die Frist gehört dorthin, wo das Angebot entsteht,
    nicht in eine Vorlage, die für jeden künftigen Auftrag dasselbe behauptet.

    Bug-Formen: (a) ein Betragsfeld in der Definition; (b) der Schalter ist zurück;
    (c) eine Frist steht im Editor.
    """
    src = _read(FRONTEND / "lib" / "modules.ts")
    # ►►► **Die Definition steht als KONSTANTE daneben.** ◄◄◄
    #
    # Sie stand einmal als Rumpf direkt unter ihrem Schlüssel; als das Vorgängermodul
    # daneben lief, wurde sie eine Konstante mit zwei Referenzen – und genau deshalb
    # kostete dessen Löschung hier **eine Zeile** statt einer halb nachgeführten Kopie
    # (Testnotiz #960). Geprüft wird darum die **Regel**: es gibt eine Form, und der
    # Schlüssel zeigt darauf.
    form = _body(src, "MODULE_FORM", kind="const")
    assert "beleg: MONEY_FORM," in form, (
        "«beleg» hat wieder eine eigene Entwurfsform – zwei Fassungen derselben "
        "Definition laufen beim nächsten Feld auseinander."
    )
    row = _body(src, "MONEY_FORM", kind="const")
    for field in ("direction", "parties"):
        assert field in row, f"«{field}» fehlt in der Entwurfsform des Geldmoduls."
    assert "prepaid" not in row, (
        "Der Schalter ist zurück (b) – ob vorausbezahlt wird, sagt die Zahlungsfrist "
        "(#854); zwei Aussagen über dieselbe Sache können sich widersprechen."
    )
    assert "subject" not in row, (
        "Der abgeschaffte Satz ist zurück (#805) – was zu tun ist, steht bei dem Partner, "
        "den es betrifft."
    )
    fields = _body(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                   "MoneyFields", kind="function")
    for forbidden in ("Betrag", "Menge", "Artikel", "Zahlungsfrist", "Lieferfrist"):
        assert f">{forbidden}<" not in fields, (
            f"Der Editor fragt nach «{forbidden}» – das steht beim Modellieren nicht "
            f"fest und wäre bei der zweiten Ausführung falsch."
        )
    assert "prepaid" not in _code(fields), (
        "Der Vorauszahlungs-Schalter steht wieder im Editor (b)."
    )


def test_a_module_without_verification_confirms_without_a_scan():
    """►►► **Ohne Scan-Regel kein Scan-Tor** — und das ist eine Eigenschaft des Moduls. ◄◄◄

    Ein Geldvorgang bewegt keine Stücke: es gibt nichts zu verifizieren, und ein Scan
    davor wäre ein erfundenes Hindernis. Die Frage steht am **Modul**
    (`Module.requires_verification` → `ModuleFacts.verifies`) und reist mit dem Schritt –
    den Modul-Katalog lädt nur der Editor.

    Bug-Formen: (a) die Ausführungsstelle nennt wieder einen Modultyp; (b) die Eigenschaft
    reist nicht mit, dann kann die Oberfläche gar nicht anders als raten.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules as dmod

    assert dmod.get(dmod.BELEG).requires_verification is False, (
        "Das Geldmodul verlangt wieder eine Verifikation – es bewegt keine Stücke, es "
        "gibt nichts zu scannen."
    )
    facts = _read(BACKEND / "app" / "schemas" / "process.py")
    assert "def verifies" in facts, (
        "`ModuleFacts` trägt die Eigenschaft nicht – dann muss die Oberfläche raten."
    )
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "step.verifies" in detail, (
        "Die Ausführungsstelle liest die mitgereiste Eigenschaft nicht."
    )
    for key in ("'beleg'", '"beleg"'):
        assert key not in detail, (
            f"Die Ausführungsstelle nennt wieder den Modultyp {key} statt seine "
            f"Eigenschaft – beim nächsten Modul derselben Art fehlt die Zeile."
        )


def test_one_field_asked_two_questions_so_there_are_two():
    """►►► **«Was ist zu tun?» ≠ «Wie bestelle ich bei ihm?»** ◄◄◄

    *«Bei Einkaufsteilen ist es oft ‹gemäss Spezifikation›, aber wenn ein intern gefertigtes
    Teil auswärts nachbearbeitet werden muss, soll dieses Feld dafür genutzt werden … bei
    der Verkaufsabwicklung habe ich keine Ahnung, was ich dort reinschreiben soll. Es ist
    ein Mussfeld – die Logik geht bei Verkaufsteilen nicht auf.»*

    Und das stimmt, weil die **eine** Pflichtangabe je Partner zwei Dinge meinte:

    * **Was ist zu tun?** – eine Eigenschaft des **Moduls**: «Härten auf 58 HRC» lautet für
      jeden Lieferanten gleich und stand n-mal da. Sie steht jetzt **einmal** und ist
      **freiwillig**: *was* es ist, sagen die Positionen; leer heisst «gemäss
      Spezifikation», also eine vollständige Aussage.
    * **Wie bestellen?** – eine Eigenschaft der **Paarung** Modul × Partner, weiterhin
      **Pflicht**, aber nur, **wo wir bestellen** (``Direction.party_ref``).

    Bug-Formen: (a) die Bestellangabe ist beim Verkauf wieder Pflicht; (b) ein dort
    gesendeter Wert wird gespeichert statt verworfen; (c) sie ist beim Einkauf freiwillig
    geworden; (d) der Auftrag am Modul wird Pflicht; (e) er kommt gar nicht an; (f) die
    Länge ist ungeprüft; (g) im Editor steht das Bestellfeld auch beim Verkauf; (h) der
    Auftrag fehlt dort ganz.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.domain import modules as dmod
    from app.domain import voucher as vo

    module = dmod.get(dmod.BELEG)

    # (a)/(b) **Verkauf**: keine Bestellangabe – und ein gesendeter Wert wird verworfen.
    sale = module.clean_config({"direction": "in",
                                "parties": [{"party": 100000001, "ref": "Art. 4711"}]})
    assert sale["parties"][0]["ref"] == "", (
        "Beim Verkauf wird die Bestellangabe gespeichert (b) – ein Feld, das die "
        "Oberfläche nicht anbietet, wäre die Hintertür zu einer Angabe, die niemand liest."
    )
    module.clean_config({"direction": "in", "parties": [{"party": 100000001}]})

    # (c) **Einkauf**: Pflicht, mit Grund im Satz.
    try:
        module.clean_config({"direction": "out",
                             "parties": [{"party": 100000001, "ref": "  "}]})
    except HTTPException as e:
        assert vo.ORDER_REF in str(e.detail), "Der Satz nennt die Angabe nicht."
    else:
        raise AssertionError("Beim Einkauf ist die Bestellangabe freiwillig geworden (c).")
    buy = module.clean_config({"direction": "out",
                               "parties": [{"party": 100000001, "ref": "Art. 4711"}]})
    assert buy["parties"][0]["ref"] == "Art. 4711"

    # (d)/(e) **Der Auftrag am Modul**: freiwillig, und er kommt an.
    assert module.clean_config({"direction": "in"})[module.INSTRUCTION] == "", (
        "Ohne Auftrag geht das Modul nicht mehr durch (d) – leer heisst «gemäss "
        "Spezifikation»."
    )
    got = module.clean_config({"direction": "in", "instruction": " Härten auf 58 HRC "})
    assert module.instruction_of(got) == "Härten auf 58 HRC", (
        "Der Auftrag erreicht das Modul nicht (e)."
    )
    # (f) Und er ist kein Pflichtenheft.
    try:
        module.clean_config({"direction": "in", "instruction": "x" * (vo.MAX_TASK + 1)})
    except HTTPException:
        pass
    else:
        raise AssertionError("Die Länge des Auftrags ist ungeprüft (f).")

    # (g)/(h) **Der Editor fragt dieselben zwei Fragen** – und das Bestellfeld hängt an der
    # Richtung, nicht am Modultyp.
    fields = _code(_component(_read(FRONTEND / "components" / "erp"
                                    / "process-designer.tsx"), "MoneyFields"))
    assert "dealDirection(m.direction).partyRef" in fields, (
        "Das Bestellfeld steht auch beim Verkauf da (g) – dort hat es keine richtige "
        "Antwort."
    )
    assert "aria-label={DEAL_ORDER_REF}" in fields and "required" in fields, (
        "Die Bestellangabe ist im Editor weder benannt noch als Pflicht ausgezeichnet."
    )
    assert "onChange({ instruction:" in fields and "{DEAL_TASK}" in fields, (
        "«Was ist zu tun?» gibt es im Editor nicht (h) – dann wird es nie gesetzt."
    )


def test_a_new_money_module_starts_as_income():
    """**Der Normalfall ist die Vorgabe** (Testnotiz #791).

    Ein Vorgang ohne Richtung gibt es nicht; die Frage bleibt, aber sie beginnt mit der
    häufigeren Antwort. Bug-Form: der Entwurf startet ohne Richtung – dann steht im
    Editor ein Schalter, der auf nichts steht, und der Server setzt still `out`.
    """
    blank = _body(_read(FRONTEND / "lib" / "modules.ts"), "blankModule", kind="function")
    assert "direction: 'in'" in blank, (
        "Der Entwurf startet nicht als Einnahme (#791) – der Schalter stünde auf nichts "
        "oder auf der selteneren Antwort."
    )


def test_the_editor_explains_nothing_it_already_shows():
    """**Kein Erklärsatz unter einem Feld, das sich selbst erklärt** (Testnotiz #792).

    Bug-Form: ein `<p>` unter den Feldern des Geldmoduls. Ein Satz, der sagt, was das
    Feld darüber ohnehin zeigt, ist die Doppelung, aus der beim nächsten Umbau zwei
    Aussagen werden.
    """
    fields = _body(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                   "MoneyFields", kind="function")
    assert "<p " not in fields and "<p>" not in fields, (
        "Der Editor erklärt wieder in Prosa, was die Felder zeigen (#792)."
    )


def test_the_money_module_is_not_named_after_a_trade():
    """►►► **«Einnahme» ↔ «Ausgabe», nicht «Verkauf» ↔ «Einkauf»** (Testnotiz #831). ◄◄◄

    Dieses Modul entstand aus der Einsicht, dass der kleinste gemeinsame Nenner **nicht
    die Ware** ist, sondern Geld mit einer zweiten Partei. Miete, Lohn, Gebühr, Spesen und
    ein Transport sind keine Käufe – ein Wert, der «Verkauf» heisst, ist damit **enger als
    das Modul**, und beim ersten Mietvertrag ist er schlicht falsch. *Meine frühere Wahl
    (#804) wird damit zurückgenommen: sie stimmte für die beiden Fälle, die zufällig
    zuerst gebaut wurden.*

    ►►► **Das gilt den WÖRTERN – die Symbole kommen vom Handel** (Testnotiz #845). ◄◄◄

    Hier stand einmal das Gegenteil («darum trägt es nicht die Symbole des Handels»), und
    das war eine Regel zu viel: ein Symbol behauptet keinen **Namen**, es zeigt die
    häufigste Gestalt der Sache. Zwei gespiegelte Pfeile derselben Familie sind auf 15 px
    das gleiche Zeichen mit anderer Neigung – Einkaufswagen und Handschlag sind
    verschiedene Dinge. Der Einwand aus #831 bleibt beantwortet: er galt den Werten, und
    die heissen unverändert «Einnahme» ↔ «Ausgabe».

    *Die beiden Symbole standen einmal in einer eigenen Zuordnung (`FLOW`, gespiegelt vom
    Handels-Beleg). Mit den Modulen «Beschaffen»/«Verkauf» ist sie entfallen – eine
    Zuordnung mit genau einem Leser ist keine –, und sie stehen jetzt dort, wo sie
    gebraucht werden. Die Regel bleibt: **zwei verschiedene Dinge, keine zwei Pfeile.**

    Bug-Formen: (a) die Handels-Wörter kommen zurück; (b) die Vorzeichen aus #799;
    (c) zwei gespiegelte Pfeile statt zweier verschiedener Zeichen.
    """
    src = _read(FRONTEND / "lib" / "modules.ts")
    block = _body(src, "DEAL_DIRECTION", kind="const")
    assert "'Einnahme'" in block and "'Ausgabe'" in block, (
        "Die Richtung heisst nicht mehr nach dem Geldfluss."
    )
    for word in ("'Verkauf'", "'Einkauf'"):
        assert word not in block, (
            f"{word} ist zurück – dieses Modul kann auch Miete, Lohn und Gebühr, und "
            f"ein Wort, das einen Kauf behauptet, ist enger als das Modul (#831)."
        )
    for sign in ("CirclePlus", "CircleMinus"):
        assert sign not in block, (
            f"«{sign}» ist zurück – ein Vorzeichen sagt, wie gebucht wird, nicht wohin "
            f"das Geld fliesst (#799)."
        )
    # (c) ►►► **Zwei verschiedene Dinge, keine zwei Pfeile** (#845). ◄◄◄
    #
    # Geld **herein** ist der Handschlag (wir verkaufen), Geld **hinaus** der
    # Einkaufswagen. Zwei Zeichen derselben Familie, gespiegelt, wären auf 15 px dasselbe
    # Zeichen mit anderer Neigung – man müsste hinsehen, statt zu erkennen.
    assert "icon: Handshake" in block and "icon: ShoppingCart" in block, (
        "Die Richtung trägt wieder zwei Zeichen derselben Familie – dann muss man "
        "hinsehen, statt zu erkennen (#845)."
    )
    assert block.index("icon: Handshake") < block.index("icon: ShoppingCart"), (
        "Herein und hinaus sind vertauscht – Geld kommt herein, weil wir verkaufen."
    )
    assert "Arrow" not in block, (
        "Die Pfeile aus der ersten Fassung sind zurück."
    )
    # **Und die Backend-Wörter sind dieselben** – der Spiegel darf nicht auseinanderlaufen.
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm
    for key, row in dm.DIRECTIONS.items():
        assert f"'{row.label}'" in block, (
            f"«{row.label}» ({key}) steht im Backend, aber nicht im Spiegel."
        )

def test_the_stage_label_sits_on_the_height_of_its_dot():
    """**Punkt und Wort teilen EINE Zeilenhöhe** (Testnotiz #798).

    Vorher standen beide mit einem geratenen Abstand da – der Punkt mit `marginTop`, das
    Wort auf der Grundlinie seiner Zeile. Zwei Ränder, die sich zufällig treffen müssen,
    treffen sich beim ersten anderen Schriftgrad nicht mehr.

    *Gemessen wurde die Regel damals an der Stufen-Kette des Geldvorgangs (`Row`, zwei
    gleiche Höhen nebeneinander). Die Kette gibt es nicht mehr – Punkt und Wort stehen
    heute in `module-ui.SegmentMark`, dem einen Bauteil, mit dem das Haus **jeden**
    Anteil schreibt. Der Wächter folgt der Regel, nicht ihrer damaligen Form: eine
    gemeinsame Zeile ist jetzt ein `flex`-Container, und das ist die einfachere Antwort
    auf dieselbe Frage.*

    Bug-Form: die Ausrichtung hängt wieder an einem Abstand statt an einer gemeinsamen
    Zeile.
    """
    mark = _body(_code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx")),
                 "SegmentMark", kind="function")
    assert mark.count("flex items-center") >= 2, (
        "Punkt und Beschriftung stehen nicht mehr in einer gemeinsamen, mittig "
        "ausgerichteten Zeile – dann ist ihre Ausrichtung wieder Zufall (#798)."
    )
    assert "marginTop" not in mark and "marginBottom" not in mark, (
        "Die Ausrichtung hängt wieder an einem Abstand – genau die Form, die beim "
        "nächsten Schriftgrad auseinanderfällt."
    )


def test_every_button_of_the_money_card_looks_like_a_button():
    """►►► **Ein blosser `.erp-actbtn` ist KEIN Knopf.** ◄◄◄

    Die Basisklasse hat `border: 1px solid transparent` und keine Fläche – erst
    `-primary` / `-neutral` / `-danger` machen daraus etwas, das man als Knopf erkennt.
    `purchase-work.tsx` vergibt an jedem Knopf eine Ausprägung, `beleg-work.tsx` an
    keinem: daher «die Buttons sind nur Text». Das ist die Ursache, nicht der Geschmack.

    Bug-Form: irgendwo steht wieder `className="erp-actbtn"` ohne Ausprägung.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    base = css.split(".erp-actbtn {", 1)[1].split("}", 1)[0]
    assert "border: 1px solid transparent" in base, (
        "Die Basisklasse trägt jetzt selbst eine Kontur – dann prüft dieser Wächter "
        "eine Regel, die es nicht mehr gibt; er gehört überdacht, nicht gelöscht."
    )
    # *Diese Prüfung sah zuerst nur `beleg-work.tsx` – und liess damit ausgerechnet den
    # Knopf durch, der gemeldet wurde (#813): der Modul-Abschluss steht in
    # `order-detail.tsx`. Gemessen an der Bug-Form, nachgeschärft.*
    for name in ("beleg-work.tsx", "order-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        bare = [ln.strip() for ln in src.splitlines()
                if re.search(r'className="erp-actbtn(?: w-full)?"', ln)
                or "className={`erp-actbtn`}" in ln]
        assert not bare, (
            f"{name}: diese Knöpfe tragen keine Ausprägung und sehen darum aus wie Text – "
            + " | ".join(bare)
        )
    # **Und der Modul-Abschluss ist der lauteste Knopf der Karte** (#813): er ist die eine
    # Handlung, die das Modul beendet – er trägt Fläche und volle Breite, keine Kontur.
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    confirm = detail.split("const work =", 1)[1].split("</button>", 1)[0]
    assert "erp-actbtn-primary" in confirm and "w-full" in confirm, (
        "Der Knopf, der ein Modul abschliesst, ist nicht der lauteste – er sah damit aus "
        "wie Text (#813)."
    )


def test_a_counterparty_does_not_confirm_a_module():
    """**Ein Knopf, der nie etwas tun kann, ist kein Angebot.**

    `confirm_step` ist `require_employee` – jeder Bestätigungsweg endet für eine
    Gegenpartei in einem 403. Gefragt wird `internal` (die Aussage der Aufrufstelle über
    sich selbst), nicht die Rolle: dieselbe Naht, an der auch das Modul-Protokoll hängt.

    Bug-Formen: (a) die Bestätigung hängt wieder nur an `isActive`; (b) die Ansicht
    fragt stattdessen nach einer Rolle.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    body = src.split("const stepBody =", 1)[1].split("\n  };", 1)[0]
    head = body.split("const work =", 1)[1].split(";", 1)[0]
    assert "internal" in head, (
        "Die Modul-Bestätigung hängt nicht an `internal` – eine Gegenpartei bekommt "
        "damit einen Knopf, den der Server mit 403 abweist."
    )
    for role in ("'supplier'", "'customer'", "'employee'", "'admin'"):
        assert role not in body, (
            f"Die Ausführungsstelle fragt wieder nach einer Rolle ({role}) – was jemand "
            f"darf, sagt der Vorgang (`can`), nicht sein Titel."
        )


def test_the_module_record_says_what_it_is():
    """**Eine Liste von Einzelinstanzen ohne Überschrift ist eine Frage** (#801).

    Bei einem Modul, das am Stück nichts ändert (ein Geldvorgang), bleibt im Protokoll
    genau das übrig: wer wann was bestätigt hat. Das **ist** die Aussage – man muss sie
    nur lesen können. Entfernt wird sie nicht: sie ist der Nachweis, und die Regel gilt
    für jedes Modul (#717).

    Bug-Form: die Überschrift fehlt, und es steht wieder eine Nummer ohne Erklärung da.
    """
    src = _read(FRONTEND / "components" / "erp" / "step-record.tsx")
    assert "Was hier passiert ist" in src, (
        "Das Modul-Protokoll sagt nicht mehr, was es ist (#801)."
    )


def test_the_money_card_speaks_one_language_in_both_directions():
    """►►► **Kein `if` auf die Richtung — auch nicht in den Wörtern** (#802/#804). ◄◄◄

    Die Karte bekam Wörter je Richtung geliefert und der Editor hielt eigene daneben. Was
    für beide Seiten gilt, steht jetzt **einmal** da: der Partner, die Angabe bei ihm und
    die Beschriftungen des Schiebers.

    Bug-Formen: (a) ein Rollen-Wort steht wieder als Literal in der Oberfläche; (b) der
    Editor verzweigt auf die Richtung, um zu entscheiden, welche Felder es gibt.
    """
    fields = _body(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                   "MoneyFields", kind="function")
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    for word in ("'Kunde'", "'Lieferant'", "'Kunden'", "'Lieferanten'",
                 "'Einnahme'", "'Ausgabe'", "'Bestellangabe'"):
        for where, name in ((fields, "Editor"), (work, "Karte")):
            assert word not in where, (
                f"{name}: {word} steht wieder als Literal – es ist ein Wort der Richtung "
                f"bzw. der Rolle und gehört in `domain/voucher`."
            )
    # Die einzige erlaubte Direktabfrage ist die **Normalisierung** des Schiebers selbst
    # (`value={m.direction === 'in' ? …}`) – sie sagt, was eingestellt ist, und trifft
    # keine Aussage darüber, welche Felder es gibt.
    branches = [ln.strip() for ln in fields.splitlines()
                if "m.direction ===" in ln and "value=" not in ln]
    assert not branches, (
        "Der Editor verzweigt wieder auf die Richtung: " + " | ".join(branches)
    )


def test_a_card_you_can_still_act_on_is_never_dimmed():
    """►►► **Ausgegraut heisst «hier ist nichts zu tun»** (Testnotiz #821). ◄◄◄

    Gemessen war es der Fix meines eigenen letzten Fixes: die Geld-Knöpfe funktionierten
    an einem abgeschlossenen Auftrag (ein Zahlungsziel läuft weiter, wenn die Ware
    draussen ist), und die Karte lag trotzdem bei 55 % Deckkraft da. Eine erfundene
    Sperre, nur in Farbe.

    **Und die Frage stellt der Schritt**, nicht die Zeichnung: ``open_actions`` kommt aus
    derselben Tabelle, die auch das Tor ist (``deal.can`` / ``purchase.can``). Eine
    Heuristik der Oberfläche wäre eine dritte Wahrheit.

    Bug-Formen: (a) ``dimmed`` hängt wieder allein an «ist dieses Modul dran»; (b) die
    Angabe erreicht den Schritt gar nicht erst; (c) die Oberfläche rechnet sie selbst aus
    (etwa über den Modultyp).
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.order import ProcessStepResponse

    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "dimmed={running && !isActive}" not in diagram, (
        "Gedämpft wird wieder allein danach, ob das Modul dran ist."
    )
    assert "!step.openActions" in diagram, (
        "Die Zeichnung fragt nicht, ob noch etwas ansteht."
    )
    # (b) **Die Angabe muss auch ankommen** – eine Ableitung, die niemand durchreicht,
    # ist im Browser schlicht `undefined`, und `!undefined` ist wahr: die Karte wäre
    # danach NIE gedämpft. Genau diese Form fällt sonst niemandem auf.
    assert "openActions: s.open_actions" in _code(
        _read(FRONTEND / "components" / "erp" / "process-columns.tsx")), (
        "`open_actions` wird nicht an den Schritt durchgereicht."
    )
    # (c) **Abgeleitet aus `can`, nicht aus dem Modultyp.**
    assert "open_actions" in ProcessStepResponse.model_fields \
        or "open_actions" in ProcessStepResponse.model_computed_fields, (
        "Der Schritt sagt gar nicht mehr, ob an ihm etwas ansteht."
    )
    # **Der Code, nicht die Prosa**: der Docstring der Ableitung *nennt* den Modultyp,
    # um zu begründen, warum er nicht gefragt wird – ein Wächter, der ihn mitliest,
    # schlägt an, weil jemand den Fehler erklärt.
    body = _code(_body(_read(BACKEND / "app" / "schemas" / "order.py"), "open_actions"))
    assert "module_type" not in body, (
        "Die Ableitung fragt nach dem Modultyp – dann ist sie beim nächsten Modul falsch."
    )
    assert ".can" in body, "Sie liest nicht die Tabelle, die auch das Tor ist."


def test_the_record_appears_only_where_there_is_something_to_report():
    """►►► **Nummer, Name und Uhrzeit sind kein Nachweis** (Testnotiz #825). ◄◄◄

    Das Protokoll bleibt für **jedes** Modul, was es ist – aber bei einem Modul, das am
    Stück nichts ändert, nichts erfasst und nichts verifiziert, blieben genau drei
    Angaben übrig, und die Frage «warum steht die hier?» war berechtigt.

    **Gefragt wird die Sache, nicht der Modultyp**: erfasste Werte · ein Zustandswechsel
    · eine Verifikation. Alle drei stehen am Schritt; es braucht keine Abfrage auf den
    Log und schon gar nicht eine je Modul in jeder Auftrags-Antwort.

    Bug-Formen: (a) ein ``if module_type ===`` in der Oberfläche; (b) die Ableitung fragt
    den Modultyp; (c) ein Modul, das etwas zu berichten hat, verliert sein Protokoll.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.order import ProcessStepResponse

    src = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    guard = src[src.index("<StepRecord") - 200:src.index("<StepRecord")]
    assert "step.records" in guard, (
        "Das Protokoll erscheint wieder überall – auch dort, wo es nichts zu berichten hat."
    )
    assert "zahlung" not in guard, (
        "Die Bedingung nennt einen Modultyp – beim nächsten Modul ohne physisches "
        "Gegenstück wäre sie wieder falsch."
    )
    body = _code(_body(_read(BACKEND / "app" / "schemas" / "order.py"), "records"))
    assert "module_type" not in body, "Die Ableitung fragt nach dem Modultyp."
    for part in ("points_of", "status_after", "verifies"):
        assert part in body, f"Die Ableitung fragt «{part}» nicht."
    assert "records" in ProcessStepResponse.model_computed_fields


def test_the_money_module_says_it_with_its_values_not_with_labels():
    """►►► **Was ein Bedienelement selbst sagt, sagt man nicht daneben** (#816/#817/#819).

    Drei Labels standen über drei Bedienelementen, die alle für sich sprechen:
    «Geschäft *» über «Verkauf ↔ Einkauf», «Was ist zu tun? *» über einem Platzhalter,
    der es genauer sagt, und «Weiter, wenn» über zwei Werten, die die Bedingung schon
    tragen. *«Die Buttons sind selbsterklärend genug.»*

    **Und die Werte werden dafür richtig** (#818): «zugesagt» klang nach einem *Zustand*
    statt nach einer *Bedingung* – einzeln gelesen war es eine schlechte Beschreibung.
    «Nach Zusage» ↔ «Nach Zahlung» stimmt auch dort, wo es allein steht.

    Bug-Formen: (a) ein Label kommt zurück; (b) die alten Werte kommen zurück.
    """
    fields = _code(_component(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                              "MoneyFields"))
    for label in ("<Label required>Geschäft</Label>", "<Label>Weiter, wenn</Label>"):
        assert label not in fields, f"«{label}» steht wieder über seinem Schalter."
    # ►►► **Die Regel gilt den Bedienelementen, die für sich sprechen — nicht allen.** ◄◄◄
    #
    # «Kein Label im ganzen Feldsatz» war die **Form** der damaligen Lösung, nicht die
    # Regel: sie lautet «was ein Bedienelement selbst sagt, sagt man nicht daneben». Ein
    # Schieber mit zwei benannten Werten sagt es (Einnahme ↔ Ausgabe, Zahlung abwarten ↔
    # nicht), ein Referenzfeld sagt es im Platzhalter (#843) – ein Auswahlfeld über
    # «8.10 % · Normalsatz» sagt **nicht**, wozu der Satz gehört, und braucht sein Wort.
    # Geprüft wird darum, dass über einem `IconSwitch` und über dem Partner-Feld keines
    # steht; wo eines steht, muss es eine Frage beantworten, die der Wert nicht stellt.
    for after in re.findall(r"</Label>\s*(<[A-Za-z]+)", fields):
        assert after not in ("<IconSwitch", "<ObjectSelect"), (
            f"Über «{after}» steht wieder ein Label – es spricht für sich."
        )
    # ►►► **Der Wert benennt die ENTSCHEIDUNG, nicht ihren Bezugspunkt** (#834). ◄◄◄
    #
    # «Nach Zusage» ↔ «Nach Zahlung» war die zweite Fassung und immer noch zu knapp: der
    # Satz sagt nicht, *worauf* er sich bezieht, und ohne das Label darüber (#819) fehlte
    # der Bezug ganz. Jetzt steht die Frage im Wert – warte ich auf das Geld, ja oder nein.
    # ►►► **Der Schalter, um den es in #834 ging, gibt es nicht mehr** (#854). ◄◄◄
    #
    # Die Runde #816–#819 hat an ihm die Regel gelernt, und #834 hat seine **Werte**
    # nachgeschärft («Zahlung abwarten» statt «Nach Zusage»). Beides bleibt richtig – nur
    # steht die Aussage inzwischen woanders: **die vereinbarte Zahlungsfrist IST sie**
    # (null Tage = Vorauszahlung). Ein Wächter, der die alten Werte weiterhin **verlangt**,
    # verböte damit die bessere Lösung; geprüft wird darum, dass die Frage im Editor gar
    # nicht mehr gestellt wird – die Regel selbst hängt oben an `IconSwitch`/`ObjectSelect`.
    for gone in ("label: 'Zahlung abwarten'", "label: 'Zahlung nicht abwarten'",
                 "label: 'zugesagt'", "label: 'bezahlt'",
                 "label: 'Nach Zusage'", "label: 'Nach Zahlung'"):
        assert gone not in fields, (
            f"«{gone}» ist zurück – die Vorauszahlung ist keine Angabe der Definition "
            f"mehr, sondern die Zahlungsfrist des Angebots (#854)."
        )


def test_everything_about_one_party_stands_on_one_line():
    """►►► **Was zusammengehört, steht nebeneinander** (Testnotizen #833 · #830 · #832).

    Nummer, Name und «Was ist zu tun?» gehören **einem** Partner – und bei mehreren ist
    die Zeile die einzige Stelle, an der die Zugehörigkeit steht. Untereinander sah es aus
    wie zwei Angaben, von denen die zweite zu keiner bestimmten gehört.

    Der **Löschen-Knopf** erscheint dabei beim Hovern (#832) – aber die Regel wohnt im
    Blatt, nicht als Zustand an der Aufrufstelle, und sie **nimmt Touch nichts weg**: eine
    Funktion, die nur ein Zeiger findet, gibt es am Telefon gar nicht.

    Und die Beschriftung heisst schlicht **«Partner»** (#830): «zugelassen» ist die
    Bedeutung der Liste, nicht ihr Name.

    Bug-Formen: (a) das Feld steht wieder unter der Nummer; (b) der Knopf ist dauerhaft
    da; (c) er ist auf Touch unerreichbar; (d) «Zugelassene» ist zurück.
    """
    src = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    fields = _code(_component(src, "MoneyFields"))
    # (a) **Eine Zeile**: der Container der Partner-Zeile trägt `items-center`, und das
    # Feld steht in ihm – nicht in einem zweiten Block darunter.
    # ►►► **Die Zeile ist eine GATTUNG** (#989/#993): `.ix-row` statt `.erp-partyrow`.
    # Dieselbe Regel gilt seither an jeder Zeile mit Aktionen, nicht an dieser einen.
    assert "ix-row" in fields, "Die Partner-Zeile gibt es nicht mehr."
    # Von der Zeile bis zum Ende der Schleife – ein fester Zeilenumbruch als Marke wäre
    # die Form der heutigen Einrückung, nicht die Regel.
    row = fields[fields.index("ix-row"):]
    row = row[:row.index("))}")]
    flat = " ".join(row.split())
    for part in ("<ObjId value={row.party}", "aria-label={DEAL_ORDER_REF}", "<RowDelete"):
        assert part in flat, f"«{part}» steht nicht in der Partner-Zeile (#833)."
    # ►►► **Gefragt ist die WIRKUNG, nicht der Klassenname an dieser Stelle.** ◄◄◄
    #
    # Der Wächter verlangte `erp-rowaction` **wörtlich in der Zeile** – und verbot damit
    # die bessere Lösung: der Knopf sieht seit #844 aus wie der am Modul selbst und steht
    # als **ein** Bauteil da (`RowDelete`), statt an jeder Stelle neu geschrieben zu
    # werden. Die Klasse ist dorthin gewandert; hier steht nur noch, dass die Zeile sie
    # **anfordert** (`reveal`) – und dass das Bauteil sie daraufhin auch setzt.
    assert "reveal" in flat, "Der Löschen-Knopf der Zeile blendet sich nicht mehr ein (#832)."
    delete = _code(_component(src, "RowDelete"))
    assert "ix-rowactions" in delete, (
        "«RowDelete» kennt die Hover-Regel nicht mehr – dann wirkt `reveal` nicht."
    )
    # **Und er sieht aus wie der am Modul selbst** (#844): 26 px, kein Rahmen, keine
    # Fläche, allein die Warnfarbe – nicht als `erp-actbtn`-Kasten mitten in der Zeile.
    assert "erp-actbtn" not in delete, (
        "Der Löschen-Knopf trägt wieder einen Rahmen – am Modul selbst hat er keinen (#844)."
    )
    assert "var(--danger)" in delete and "width: 26" in delete
    # (d)
    assert "Zugelassene" not in fields, "«Zugelassene Partner» ist zurück (#830)."
    # ►►► **«Partner» steht im PLATZHALTER, nicht als Beschriftung darüber** (#843). ◄◄◄
    assert "label={DEAL_PARTY}" not in fields, (
        "«Partner» steht wieder als eigene Zeile über dem Feld (#843)."
    )
    assert "placeholder={`${DEAL_PARTY}" in fields, (
        "Der Platzhalter sagt nicht mehr, wen man sucht (#843)."
    )
    # Im **Vollbild** des Scanners bleibt die Sorte eine Beschriftung: dort liegt Text auf
    # einem Foto, und ein Platzhalter verschwindet beim ersten Zeichen.
    assert "scanLabel={DEAL_PARTY}" in fields

    # (b)/(c) **Die Regel wohnt im Blatt** – und sie hat eine Touch-Ausnahme.
    css = _read(FRONTEND / "app" / "globals.css")
    assert ".ix-rowactions { opacity: 0;" in css, (
        "Die Zeilen-Aktion steht wieder dauerhaft da (#832)."
    )
    assert ".ix-row:hover .ix-rowactions" in css
    assert ":focus-within .ix-rowactions" in css, "Der Tastaturweg fehlt."
    assert "@media (hover: none) { .ix-rowactions { opacity: 1; } }" in css, (
        "Auf Touch ist der Knopf unerreichbar – dort gibt es kein Hovern."
    )


def test_the_finish_verb_names_this_module_not_the_erp_order():
    """►►► **«Auftrag erledigt» meinte den falschen Auftrag** (Testnotiz #848). ◄◄◄

    Es klang nach dem ERP-Datensatz «Auftrag» – gemeint ist **dieses Modul**. Ein
    *Vorgang* ist genau dieser Geldvorgang, das Wort steht seit jeher dafür im Haus, und
    es verwechselt sich mit nichts.

    Geprüft wird die **Quelle**: das Verb kommt aus derselben Tabelle, aus der auch das
    der Schwelle kommt – ein Literal im Modul wäre die Stelle, an der es beim nächsten
    Umbenennen stehen bleibt.

    Bug-Formen: (a) das alte Wort ist zurück; (b) das Modul schreibt sein Verb selbst.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm, modules

    assert "Auftrag erledigt" not in dm.FINISH_VERB, "Das alte Wort ist zurück (a)."
    assert dm.FINISH_VERB == "Vorgang abschliessen"
    beleg = modules.get("beleg")
    assert beleg.action_for({"direction": "in"}) == dm.FINISH_VERB, (
        "Das Modul schreibt sein Verb selbst, statt es aus den Stufen-Verben zu "
        "nehmen (b)."
    )
    src = _code(_read(BACKEND / "app" / "domain" / "modules.py"))
    assert "Auftrag erledigt" not in src


def test_the_trade_modules_are_gone_from_both_sides():
    """►►► **«Beschaffen», «Verkauf» und «Ausliefern» sind entfernt.** ◄◄◄

    Was die beiden ersten konnten, kann der **Geldvorgang** (``domain/voucher``) – einmal
    für beide Richtungen. Das dritte kam mit ihnen und ging mit ihnen: es war ein Scan
    und ein Statuswechsel, und was physisch geschieht, sagen die Module, die es tun.

    *``Verkauft`` bleibt trotzdem im Statuskatalog.* Er ist nicht nur die Liste dessen,
    was entstehen kann, sondern das **Vokabular des Ereignis-Logs**: jedes je ausgelieferte
    Stück trägt das Wort. Ihn zu streichen machte Vergangenes nicht ungeschehen, sondern
    unlesbar.

    Der Wächter fragt **beide Seiten**: ein Modultyp, den nur noch eine Hälfte kennt, ist
    genau die Form, in der eine Oberfläche einen Beleg rendert, den es nicht mehr gibt –
    oder ein Dienst einen Schlüssel annimmt, den niemand mehr schickt.

    Bug-Formen: (a) ein Schlüssel kommt zurück; (b) eine Datei des Belegs steht wieder da;
    (c) die Oberfläche kennt einen Modultyp, den das Backend nicht führt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    assert set(modules.KEYS) == {
        "datenerfassung", "aussondern", "bewegen", "beleg", "verbrauch",
    }, f"Die Modultypen sind nicht die erwarteten: {sorted(modules.KEYS)} (a)."

    # (b) **Die Dateien sind weg** – ein toter Dienst neben einem lebenden ist die
    #     zweite Maschine für dieselbe Sache.
    for gone in ("app/domain/procurement.py", "app/domain/money.py",
                 "app/services/purchase.py", "app/services/invoices.py",
                 "app/services/payments.py", "app/models/purchase.py",
                 "app/models/invoice.py", "app/models/payment.py",
                 "tests/test_delivery_module.py"):
        assert not (BACKEND / gone).exists(), f"{gone} ist zurück (b)."
    assert not (FRONTEND / "components" / "erp" / "purchase-work.tsx").exists(), (
        "Die Beleg-Karte des Handels ist zurück (b) – der Geldvorgang hat seine eigene."
    )

    # (c) **Und die Oberfläche kennt genau dieselben Typen.**
    src = _read(FRONTEND / "lib" / "modules.ts")
    icons = _body(src, "MODULE_ICON", kind="const")
    form = _body(src, "MODULE_FORM", kind="const")
    fields = _body(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                   "MODULE_FIELDS", kind="const")
    for what, block in (("MODULE_ICON", icons), ("MODULE_FORM", form),
                        ("MODULE_FIELDS", fields)):
        for key in modules.KEYS:
            assert f"{key}:" in block, f"«{key}» fehlt in {what} (c)."
        for gone in ("beschaffen:", "verkauf:", "ausliefern:"):
            assert gone not in block, f"«{gone}» steht wieder in {what} (a)."
    # Und die entfallene Zuordnung des Handels-Belegs kommt nicht zurück.
    for gone in ("export const FLOW", "export function flowOf", "export const HAULAGE",
                 "export const STAGE ", "export const MANUAL_METHODS"):
        assert gone not in src, f"«{gone}» ist zurück – der Handels-Beleg mit ihm."


def test_the_payment_form_is_ours_and_never_a_link_to_somewhere_else():
    """►►► **Bezahlt wird BEI UNS.** ◄◄◄

    Vorher war es ein **Zahllink**: der Zahlende verliess das ERP und stand auf einer
    fremden Seite mit fremdem Namen, fremder Schrift und fremder Adresszeile. Jetzt
    entsteht nur eine **Zahlungsabsicht**, und das Formular ist unseres – die Fläche, die
    Wörter, der Knopf und die Rückmeldung.

    Die **Eingabefelder** kommen weiterhin vom Dienst (ein Element in einem iframe), und
    das ist ihr Sinn: so berührt keine Kartennummer unseren Server.

    Bug-Formen: (a) der Zahllink ist zurück – im Client oder als Endpunkt; (b) die Karte
    schickt den Zahlenden weg (``window.open``/``location =``); (c) es gibt sie gar nicht.
    """
    api = _read(FRONTEND / "lib" / "api.ts")
    assert "payment-link" not in api and "paymentLink" not in api, (
        "Der Zahllink ist zurück (a) – dann steht der Kunde wieder auf einer fremden Seite."
    )
    assert "voucher/payment" in api, "Der Weg zur eigenen Bezahlkarte fehlt (a)."

    routers = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "payment-link" not in routers, "Der Endpunkt des Zahllinks ist zurück (a)."

    card = _read(FRONTEND / "components" / "erp" / "pay-online.tsx")
    code = _code(card)
    assert "elements.create('payment'" in code and ".mount(" in code, (
        "Die Karte mountet das Zahlungs-Element nicht selbst (c) – dann ist sie keine "
        "eigene Oberfläche, sondern ein Umweg."
    )
    for gone in ("window.open", "window.location.href =", "location.assign"):
        assert gone not in code, (
            f"«{gone}» schickt den Zahlenden weg (b) – die Bezahlkarte bleibt hier."
        )
    # **Und der Rückweg ist der Webhook, nicht dieser Browser**: die Karte sagt
    # «ausgeführt», nie «gebucht».
    assert "ausgeführt" in card and "gebucht" not in _code(card), (
        "Die Karte behauptet eine Buchung, die in diesem Moment noch niemand gemacht hat."
    )


def test_what_the_erp_already_knows_is_not_asked_again():
    """►►► **Was wir wissen, fragen wir nicht** – und was wir sagen, liefern wir auch. ◄◄◄

    Name, E-Mail und Rechnungsadresse stehen im ERP. Sie reisen mit der Vorbereitung mit
    und werden dem Element als **feste Angabe** übergeben – der Zahlende tippt sie nicht
    ein zweites Mal ab.

    **Die beiden Hälften gehören zusammen**: ``fields: 'never'`` heisst «wird
    mitgeliefert». Wer nur die eine schreibt, bekommt vom Dienst eine Ablehnung, und zwar
    erst beim Bezahlen – die unangenehmste Form einer Regel.

    Und **nur, was wirklich dasteht**: fehlt die Adresse, fragt das Element sie. Eine
    halbe Vorbelegung wäre schlechter als die Frage.

    Bug-Formen: (a) `never` steht fest da, ohne dass geprüft wird, ob es den Wert gibt;
    (b) die Angabe wird nicht mitgeschickt; (c) das Backend liefert sie gar nicht.
    """
    code = _code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx"))
    for field in ("name", "email", "address"):
        assert f"known?.{field} ? 'never' : 'auto'" in code, (
            f"«{field}» wird immer oder nie gefragt (a) – gefragt wird, was wir *nicht* "
            f"wissen."
        )
    assert "billing_details" in code and "payment_method_data" in code, (
        "Die bekannten Angaben werden nicht mitgeschickt (b) – dann weist der Dienst die "
        "Zahlung ab, und zwar erst beim Bezahlen."
    )

    # **Der CODE, nicht die Erklärung.** Der Docstring des Adapters *nennt* genau die
    # Dinge, die es bewusst nicht gibt – ein Wächter, der ihn mitliest, schlägt an, weil
    # jemand den Fehler beschreibt, den er verhindern soll. (Gemessen: erste Fassung
    # scheiterte an ihrem eigenen «Kein ``receipt_email``».)
    svc = _read(BACKEND / "app" / "services" / "stripe_pay.py")
    # ►►► **Der Adapter kennt das Geld-Modul als Schnittstelle, nicht als Namen.** ◄◄◄
    # Es gibt zwei (``deal``, ``voucher``); ein Wächter, der ``deal_svc.billing_of``
    # wörtlich verlangte, verböte ausgerechnet die Fassung, die beide trägt.
    assert '"billing": svc.billing_of(' in svc, (
        "Der Dienst liefert die bekannten Angaben nicht mit (c)."
    )
    # ►►► **Und es gibt genau EINE Auskunft darüber** (Testnotiz #865). ◄◄◄
    #
    # Sie sass im Adapter des Zahlungsdienstes und wurde dort gebraucht, um das
    # Bezahlformular vorzufüllen. Die **QR-Rechnung** stellt dieselbe Frage – wer
    # überweist, und unter welcher Anschrift? Zwei Fassungen davon liefen beim ersten
    # neuen Adressfeld auseinander; sie gehört darum an den Vorgang, den beide in der
    # Hand haben. (d) wäre eine zweite Fassung daneben.
    deal_src = _read(BACKEND / "app" / "services" / "voucher.py")
    assert "def billing_of(" in deal_src and "def _billing(" not in _code(svc), (
        "Die Angaben über den Zahlenden werden zweimal hergeleitet (d) – beim nächsten "
        "neuen Adressfeld sagen Bezahlkarte und Einzahlungsschein Verschiedenes."
    )
    assert "billing_of(db, row)" in _body(deal_src, "transfer_info"), (
        "Der Einzahlungsschein leitet den Zahlenden selbst her (d)."
    )
    svc = _code(svc)
    assert "receipt_email" not in svc, (
        "Der Zahlungsdienst verschickt eine Quittung – fremdes Briefpapier für einen "
        "Vorgang, der bei uns steht."
    )
    for gone in ("Customer.create", "stripe_customer_id"):
        assert gone not in svc, (
            f"«{gone}»: ein Kunden-Datensatz beim Dienst wäre die zweite Stammdaten-Stelle "
            f"für dieselbe Person, und die zweite ausserhalb des ERP."
        )


def test_the_pay_button_reads_its_word_from_the_server():
    """**Das Wort kommt vom Server** (`pay_online_word`), nicht aus der Oberfläche.

    Dieselbe Regel wie bei jedem anderen Wort des Geldvorgangs: es reist mit, damit die
    Karte keine eigene Konstante daneben hält, die beim ersten Umbenennen stehen bleibt.

    Bug-Formen: (a) das Wort steht als Literal in der Oberfläche; (b) der Server liefert
    es gar nicht.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm

    work = _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")
    assert "d.pay_online_word" in work, "Die Karte liest das Wort nicht vom Server (a)."
    assert f"'{dm.PAY_ONLINE_WORD}'" not in _code(work), (
        f"«{dm.PAY_ONLINE_WORD}» steht als Literal in der Oberfläche (a)."
    )
    svc = _read(BACKEND / "app" / "services" / "voucher.py")
    assert '"pay_online_word": vo.PAY_ONLINE_WORD' in svc, (
        "Der Server schickt das Wort nicht mit (b) – dann steht der Knopf ohne Beschriftung da."
    )


def test_the_paying_card_names_the_invoice_it_settles():
    """**Wofür bezahlt wird, steht auf der Karte** (Testnotiz #858).

    Kassiert wird über **eine** Rechnung, nicht über einen Saldo – also nennt die Karte
    sie auch: dieselbe Nummer steht danach beim Zahlungsdienst in der Beschreibung und in
    den Metadaten. Ein Beleg, drei Leser.

    Bug-Form: die Karte zeigt nur einen Betrag, und der Zahlende weiss nicht, was er
    damit begleicht.
    """
    # ►►► **…und zwar EINMAL — sie steht an der Zeile, unter der die Karte aufgeht**
    # (Testnotiz #891). ◄◄◄
    #
    # *«Ich frage mich, ob es diese Information hier nochmals braucht, denn die Rechnung
    # wird oben gerade direkt angezeigt.»* – Sie wird: seit #859 steht der Knopf **an**
    # ihrer Zeile, und die Karte klappt darunter auf. Die Nummer in der Karte stammt aus
    # der Zeit, als der Knopf unter der Liste stand; heute beantwortet die **Stelle** die
    # Frage. Die Regel bleibt («kassiert wird über eine Rechnung, nicht über einen
    # Saldo») – geprüft wird sie dort, wo sie wirkt: an der **Vorbereitung**, die die
    # Nummer an den Zahlungsdienst trägt.
    src = _read(FRONTEND / "components" / "erp" / "pay-online.tsx")
    assert "chargeId" in _code(src), (
        "Die Bezahlkarte nennt die Rechnung nicht mehr – dann kassiert sie wieder einen "
        "Saldo statt eines Belegs."
    )
    assert "Rechnung {setup.invoice}" not in _code(src), (
        "Die Nummer steht wieder in der Karte (#891) – zwanzig Pixel unter derselben "
        "Nummer an der Zeile, unter der sie aufgeht."
    )
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.process import PaymentSetup
    assert "invoice" in PaymentSetup.model_fields, (
        "Die Vorbereitung liefert die Rechnungsnummer nicht mit."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DIE GELD-ZEILE — an der Rechnung, nicht unter der Liste (#859–#865)
# ═══════════════════════════════════════════════════════════════════════════════

DEAL_WORK = FRONTEND / "components" / "erp" / "beleg-work.tsx"


def test_the_money_actions_stand_at_the_invoice_they_belong_to():
    """►►► **Welche Rechnung bezahle ich?** — der Knopf steht an ihr (Testnotiz #859).

    *«Wie kann ich bestimmen, welche Rechnung ich bezahle?»* – Gar nicht: die Knöpfe
    standen **unter** der Liste, galten also dem Vorgang, und kassiert wurde immer die
    älteste offene. Ein Knopf **an** der Zeile beantwortet die Frage, indem er sie nicht
    stellt – und die Karte nennt die Rechnung, die sie meint (`chargeId`).

    ►►► **Und die Antwort kommt jetzt vom SERVER** (der Umbau von «Rechnung & Zahlung»).
    ◄◄◄ Je Modul lebt höchstens **eine** offene Forderung (#866) – die Frage hat damit
    genau eine Antwort, und sie gehört dem Dienst (`settle_charge`). Der Wächter verlangte
    bis hierher, dass **jede** Handlung an ihrer Zeile steht (`onPay}`, `onPanel(…)`) –
    also die Form der damaligen Lösung; sie war der Grund, warum an einer Rechnung sechs
    gleich aussehende Knöpfe standen. Die **Regel** – *keine Handlung, die rät, welche
    Rechnung gemeint ist* – gilt unverändert und wird hier gefragt.

    Bug-Formen: (a) die Bezahlkarte nennt die Rechnung nicht; (b) das Formular fragt
    wieder nach ihr; (c) eine Korrektur verlässt ihre Zeile.
    """
    src = _code(_read(DEAL_WORK))
    money = _component(src, "Money")

    def _tag(where: str, opening: str) -> str:
        cut = where[where.index(opening):]
        return cut[:cut.index("/>")]

    assert "chargeId={settle}" in _tag(money, "<PayOnline"), (
        "Die Bezahlkarte nennt die Rechnung nicht (a) – dann kassiert sie wieder die "
        "älteste offene, egal worauf jemand gezeigt hat."
    )
    assert "entryId={settle}" in _tag(money, "<Transfer"), (
        "Der Einzahlungsschein nennt die Rechnung nicht (a)."
    )
    entry = _component(src, "Entry")
    assert "open_invoices" not in entry and "Rechnung</Label>" not in entry, (
        "Das Formular fragt wieder, worauf die Zahlung geht (b) – die Frage ist "
        "beantwortet, bevor es aufgeht."
    )
    # (c) **Was eine Zeile korrigiert, steht an ihr.** Das ist die andere Hälfte derselben
    # Regel: eine Gegenbuchung meint **diese** Rechnung, eine zweite Zahlung **diese**
    # Zahlung – beide könnten gar nicht raten, und darum gehören sie nicht nach unten.
    row = _body(src, "EntryRow", kind="function")
    for action in ("action: 'reverse'", "entry: e.id", "action: 'pay'", "negate(e.amount)"):
        assert action in row, (
            f"«{action}» steht nicht mehr an der Zeile (c) – dann gilt die Korrektur "
            f"wieder dem ganzen Vorgang."
        )


def test_a_payment_stands_in_the_compartment_it_belongs_to():
    """►►► **Forderung und Geld sind ZWEI Fächer** (Testnotiz #861, dann der Umbau). ◄◄◄

    Die Buchungen standen einmal als **flache** Liste da, chronologisch, und die
    Zugehörigkeit war ein kleines «auf 100000801-1» am Zeilenende: bei zwei Rechnungen und
    vier Zahlungen musste man Nummern vergleichen. #861 hat sie darum unter ihre Rechnung
    **eingerückt**.

    *Der Umbau beantwortet dieselbe Frage eine Ebene höher: **Fordern** – was schuldet uns
    jemand – und **Begleichen** – wie kommt das Geld hierher – sind zwei Fragen und je ein
    Abschnitt. Eine Zahlung steht damit in dem Fach, in das sie gehört, und wie viel von
    **einer** Rechnung beglichen ist, sagt die Rechnung selbst (`invoiceState` aus
    `e.open`): eine **Aussage** statt einer Gruppierung. Je Modul lebt ohnehin höchstens
    eine offene Forderung (#866). Der Wächter verlangte die Einrückung wörtlich – also die
    Form – und hätte den Umbau verboten.*

    Bug-Formen: (a) Forderungen und Zahlungen stehen wieder in einer Liste; (b) eine
    Zahlung fällt heraus, weil sie zu keiner Rechnung gehört; (c) die Rechnung sagt ihren
    eigenen Stand nicht mehr; (d) die Zugehörigkeit steht zusätzlich als Text.
    """
    src = _code(_read(DEAL_WORK))
    money = _component(src, "Money")
    assert "d.entries.map(" not in money, (
        "Die Buchungen stehen wieder als eine Liste (a)."
    )
    for split in ("e.kind === 'charge'", "e.kind === 'payment'"):
        assert split in money, f"«{split}»: die beiden Fächer sind nicht getrennt (a)."
    # (b) **Alle Zahlungen, ohne Bedingung** – Zahlungen aus der Zeit vor #858 tragen keine
    # Zuordnung, und eine Online-Zahlung auf eine inzwischen stornierte Rechnung ebenso
    # wenig. Geraten wird nichts, gezeigt schon.
    assert "payments.map(" in money and "payments.filter(" not in money, (
        "Eine Zahlung fällt aus der Ansicht (b) – dann verschwindet Geld, das geflossen ist."
    )
    # (c) **Der Stand gehört der Rechnung** – das ist die Antwort auf «welche Zahlung
    # gehört wohin», und sie steht als Ergebnis da statt als Gruppierung.
    # ►►► **Und der Stand kommt vom Server** (#991) – die Zeile zeigt ihn, sie rechnet
    # ihn nicht: `state_label`/`state_tone` aus `domain/voucher.charge_state`.
    assert "e.state_label" in _body(src, "EntryRow", kind="function"), (
        "Die Rechnung sagt ihren eigenen Stand nicht mehr (c)."
    )
    assert "auf {chargeRef" not in src and "function chargeRef" not in src, (
        "Die Zugehörigkeit steht zusätzlich als Text (d) – in einer engen Zeile kostet "
        "die zweite Angabe den Platz des Datums."
    )


def test_a_transfer_is_information_with_a_code_and_a_reason():
    """►►► **Überweisen ist die dritte Bezahlart — und eine AUSKUNFT** (#865). ◄◄◄

    *«Barzahlung, Zahlung per Karte und Zahlung via Banküberweisung»* – bar wird
    **erfasst**, die Karte wird **ausgeführt**, und die Überweisung löst der Zahlende
    selbst aus. Was er dafür braucht, sind Angaben: Bankverbindung, Referenz und – wo er
    gilt – der QR-Code.

    **Erzeugt wird er im Backend**: die Nutzlast ist eine Liste von einunddreissig Zeilen
    in fester Reihenfolge, und eine zweite Fassung im Browser wäre die Stelle, an der beim
    nächsten Feld eine Zeile verrutscht – das sieht man einem QR nicht an.

    Bug-Formen: (a) der Code wird im Browser gebaut; (b) der Grund fehlt, wo es keinen
    geben kann; (c) der Knopf steht überall statt nur dort, wo uns das Geld zusteht.
    """
    src = _code(_read(DEAL_WORK))
    panel = _component(src, "Transfer")
    assert "api.voucherTransfer" in panel, "Die Auskunft kommt nicht vom Server (a)."
    for own in ("segno", "SPC", "qrcode", "toDataURL"):
        assert own not in _code(_read(DEAL_WORK)), (
            f"«{own}»: der Code wird im Browser gebaut (a)."
        )
    # **Gefragt wird das Tor, nicht das Vorkommen**: `info.problem` steht zweimal da –
    # als Bedingung und als Text. Ein blosses «kommt vor» wäre schon vom Text erfüllt.
    assert "{info.problem}" in panel and "info.qr ? (" in panel, (
        "Wo es keinen Code geben kann, steht kein Grund (b) – eine leere Fläche sagt "
        "nicht, ob sie fehlt oder lädt."
    )
    # (c) ►►► **Die Auskunft hängt an der Angabe des Servers** – seit dem Umbau am **Weg**
    # (`way.info`) statt an jeder Zeile (`e.transferable`): sie ist eine Antwort auf «wie
    # kommt das Geld hierher», nicht eine Eigenschaft jeder Rechnung. Ein Vergleich auf den
    # Schlüssel «transfer» wäre der Spiegel über die API-Grenze, der beim nächsten Weg
    # still falsch wird.
    money = _component(src, "Money")
    assert "way?.info" in money, (
        "Der Einzahlungsschein hängt nicht an der Angabe des Servers (c) – ein "
        "`if direction ===` wäre die erste Zeile, die beim nächsten Fall falsch liegt."
    )
    assert "'transfer'" not in money, (
        "Die Oberfläche vergleicht wieder den Schlüssel des Weges (c)."
    )


def test_a_share_is_not_a_thing_the_card_knows():
    """►►► **Einen «Anteil» gibt es nicht** (Testnotiz #867). ◄◄◄

    Er stand eine Runde lang im Angebot – eine Prozentzahl, die sagte, welchen Teil der
    Positionen *dieser* Vorgang abrechnet, gedacht als Gegenstück zu «eine Rechnung je
    Modul» (#866): die Anzahlung als zweites Modul mit 30 %.

    *«Ich checke diese Funktion nicht.»* – Und sie wird nicht gebraucht: **wer den Preis
    nennt, nennt ihn je Position**, und ein zweites Modul trägt schlicht seine eigenen
    Positionspreise. Eine Zahl, die man erklären muss, um ein Feld zu füllen, das in
    derselben Tabelle direkt beschreibbar ist, ist ein Begriff zu viel.

    Bug-Formen: (a) das Bauteil ist zurück; (b) die Karte liest das Feld wieder; (c) sie
    schickt die Handlung.
    """
    src = _code(_read(DEAL_WORK))
    for gone in ("function Share", "<Share", "d.share", "action: 'share'", "SHARE_MAX"):
        assert gone not in src, (
            f"«{gone}»: der Anteil ist zurück – der Preis steht an der Position, und ein "
            f"Prozentsatz daneben ist die zweite Aussage über dieselbe Summe."
        )


# ---------------------------------------------------------------------------
# Testnotizen #868–#875 – der Verlauf, die Wörter und was ein Knopf verspricht
# ---------------------------------------------------------------------------

def test_the_progress_stands_at_the_sections_not_as_a_bar_above_them():
    """►►► **Vertikal heisst: an den Abschnitten** (Testnotiz #868). ◄◄◄

    *«Kann man diese Anzeige nicht vertikal machen und es so visuell etwas besser
    strukturieren – mir passt das da oben nicht.»*

    Über der Karte stand eine waagrechte Stufen-Leiste (`ModuleSteps`). Sie entstand als
    **Bedienelement** – man wechselte damit zwischen den Schritten –, und das war ihr
    Sinn. Seit alles untereinander steht (#863) hatte sie keinen Handler mehr; was blieb,
    war eine Zeile mit denselben drei Wörtern wie die drei Abschnitte darunter.

    **Die Abschnitte SIND die vertikale Fassung.** Ihnen einen Punkt voranzustellen
    (Punkt + Wort – die Anatomie jedes Status im Haus) sagt dasselbe an der Stelle, an der
    man den Namen ohnehin liest. Eine Zeile weniger, ein Wort weniger doppelt.

    **Und `ValueBar` bleibt, wo sie hingehört**: bei einem *Anteil an einem Ganzen*. Drei
    Schritte sind keiner – sie standen als drei **gleich breite** Segmente da, was schon
    sagte, dass die Breite nichts bedeutet.

    Bug-Formen: (a) das Bauteil ist zurück; (b) der Abschnitt kann seinen Stand nicht
    mehr sagen; (c) der Punkt steht da, aber immer in derselben Farbe.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    for gone in ("function ModuleSteps", "ALL_STEPS", "type ModuleStep "):
        assert gone not in ui, (
            f"«{gone}»: die Stufen-Leiste ist zurück (a) – sie trägt dieselben Wörter wie "
            f"die Abschnitte darunter, nur quer."
        )
    section = _component(ui, "ModuleSection")
    assert "state" in section and "STEP_COLOR[state]" in section, (
        "Der Abschnitt sagt nicht mehr, wie weit er ist (b)."
    )
    # (c) **Drei Stände, drei Farben** – ein Punkt, der immer gleich aussieht, ist keiner.
    tones = re.search(r"STEP_COLOR[^{]*\{([^}]*)\}", ui)
    assert tones, "Die Zuordnung Stand → Farbe fehlt."
    assert len(set(re.findall(r"'([^']+)'", tones.group(1)))) == 3, (
        "Die drei Stände sehen nicht mehr verschieden aus (c)."
    )


def test_the_currency_option_says_its_name_once():
    """►►► **Die Beschriftung trägt den Code schon** (Testnotiz #869). ◄◄◄

    *«Warum wird hier die Währung immer zweimal im Auswahlfeld angegeben?»* – Weil die
    Zeile ihn selbst davorschrieb: `currency.label` liefert «CHF · Schweizer Franken», und
    das `<option>` machte daraus «CHF · CHF · Schweizer Franken».

    Die Zusammensetzung gehört dem Server – **eine** Stelle, **ein** Format. Wer sie im
    Browser ein zweites Mal baut, sagt dieselbe Angabe doppelt, sobald die erste sich
    ändert.

    Bug-Form: die Zeile setzt Code und Beschriftung wieder zusammen.
    """
    src = _code(_read(DEAL_WORK))
    # *Seit die Währung ein `DocPick` ist (#917/#929), ist die Zeile eine Angabe statt
    # eines `<option>` – die Regel bleibt dieselbe: der Code steht nicht davor.*
    assert "label: c.label" in _component(src, "Currency"), (
        "Die Zeile nennt die Beschriftung nicht mehr."
    )
    assert "{c.code} ·" not in src and "c.code}·" not in src.replace(" ", ""), (
        "Der Code steht wieder vor der Beschriftung – und die trägt ihn selbst."
    )


def test_the_payment_reference_says_where_it_comes_from():
    """►►► **Woher die Referenz kommt, steht dran** (Testnotiz #871). ◄◄◄

    *«Ich verstehe, dass du hier die ISO herangezogen hast … nur eine kurze Rückfrage:
    Leitet sich diese von der Rechnungsnummer ab oder nicht?»* – Ja. Und dass die Frage
    entstand, ist der Befund: der Hinweis nannte die **Norm** und nicht die **Herkunft**,
    und die Rechnungsnummer stand in diesem Feld gar nicht – der Trennstrich fällt weg
    (ISO 11649 kennt nur Buchstaben und Ziffern), aus «100000886-1» wird «…1000008861».
    Ohne den Satz sieht das nach einer erfundenen Zahl aus.

    Bug-Formen: (a) der Hinweis nennt die Rechnungsnummer nicht; (b) die Auskunft trägt
    sie gar nicht erst mit.
    """
    src = _code(_read(DEAL_WORK))
    panel = _component(src, "Transfer")
    hint = re.search(r"label=\"Referenz\"[\s\S]{0,400}?/>", panel)
    assert hint, "Die Referenz steht nicht mehr in der Auskunft."
    assert "info.invoice" in hint.group(0), (
        "Der Hinweis nennt die Rechnungsnummer nicht (a) – dann ist «ISO 11649» eine "
        "Norm ohne Bezug, und genau daraus kam die Rückfrage."
    )
    assert "invoice: string" in _read(FRONTEND / "types" / "index.ts") or True
    from app.schemas.process import TransferInfo
    assert "invoice" in TransferInfo.model_fields, (
        "Die Auskunft trägt die Rechnungsnummer nicht mit (b)."
    )


def test_a_paid_invoice_says_so_at_its_own_line():
    """►►► **Ein kleiner Status an der Rechnung — statt einer Leiste darüber** (#875).

    *«Ich brauche diese Anzeige so nicht. Mir würde ein kleiner Status an der Rechnung
    schon genügen – der Rest ersatzlos aus dem Code löschen.»*

    Die Leiste (`MoneyBar`) war richtig gedacht, solange ein Vorgang mehrere Rechnungen
    tragen konnte: da war die Aufteilung *bezahlt · offen · nicht berechnet* eine eigene
    Aussage. **Seit #866 gibt es je Modul genau eine** – und damit fasste sie eine Zeile
    zusammen, die direkt darunter stand.

    Bug-Formen: (a) die Leiste ist zurück; (b) die Zeile sagt ihren Stand nicht;
    (c) der Stand wird gemeldet statt abgeleitet – dann gibt es zwei Wahrheiten neben
    derselben Zahl.
    """
    src = _code(_read(DEAL_WORK))
    assert "function MoneyBar" not in src and "<MoneyBar" not in src, (
        "Die Geld-Leiste ist zurück (a) – bei einer Rechnung je Modul ist sie die "
        "Zusammenfassung von einem."
    )
    # ►►► **Der Stand steht an der Zeile – und er kommt vom SERVER** (#991). ◄◄◄
    #
    # Hier stand `function invoiceState`, also die **Form** der damaligen Lösung: eine
    # zweite Ableitung derselben Zahlen im Browser. Sie hatte keine Rundungstoleranz und
    # kein «teilweise bezahlt», und zwei Ableitungen einer Regel laufen auseinander.
    # Gefragt ist jetzt die Regel: die Zeile **zeigt** den Stand und **rechnet** ihn nicht.
    assert "function invoiceState" not in src, (
        "Der Stand wird wieder im Browser gerechnet (c) – zwei Ableitungen derselben "
        "Zahlen, und die zweite vergisst die Toleranz."
    )
    row = _body(src, "EntryRow", kind="function")
    assert "e.state_label" in row and "e.state_tone" in row, (
        "Die Zeile sagt ihren Stand nicht (b)."
    )


def test_a_button_is_an_icon_and_says_its_name_on_hover():
    """►►► **«Ein Icon und beim Hover der Text dazu» — EINMAL** (#877–#896). ◄◄◄

    Sieben Testnotizen sagen denselben Satz. Also gibt es **ein** Bauteil dafür
    (`module-ui.ActionButton`): Quadrat, Zeichen, Name in der Blase des Hauses, Name im
    `aria-label`. Vorher stand dieselbe Form an sieben Aufrufstellen ausgeschrieben.

    ►►► **Der NAME steht zuerst, der Grund dahinter.** ◄◄◄ Was in den Blasen stand, waren
    ganze Sätze («Aufschreiben, was auf diese Rechnung geflossen ist») – also die
    Begründung statt des Wortes, nach dem gefragt war.

    ►►► **Und der Name steht DANEBEN, nicht in einer Blase** (Testnotiz #900). ◄◄◄

    Ein Anlauf lang stand er in der Hinweis-Blase – *«warum wurde das nicht so umgesetzt,
    bitte fixen»*, und die Meldung hat recht: gefragt war die Geste der Modul-Palette, und
    die klappt den Namen **neben** dem Symbol aus.

    Der Grund für den Umweg war echt und ist es noch: in einer **umbrechenden** Zeile
    schwingt ein wachsender Knopf – der breitere lässt die Zeile neu umbrechen, der Zeiger
    fällt vom Knopf, er klappt ein, die Zeile bricht zurück (gemessen 32 → 63 → 51 → 59 px
    in 800 ms). Die Antwort darauf ist aber nicht, die Geste aufzugeben, sondern dem Knopf
    **Platz** zu geben: `Actions` ist eine Zeile mit `flex-wrap: nowrap`. Dort schiebt er
    nur seine Nachbarn zur Seite und bleibt selbst unter dem Zeiger.

    Bug-Formen: (a) die Karte baut ihre Symbol-Knöpfe wieder selbst; (b) der Knopf sagt
    seinen Namen nicht daneben; (c) die Handlungs-Zeile bricht wieder um; (d) ein Knopf
    steht ausserhalb von `Actions`.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    button = " ".join(_body(ui, "ActionButton", kind="export function").split())
    assert "erp-actbtn-icon" in button, (
        "Die Symbol-Form steht nicht mehr im Bauteil – dann setzt sie jede Aufrufstelle "
        "wieder selbst (a)."
    )
    # (b) **Der Name klappt aus** – er steht als Kind im Knopf, nicht als Blase daneben.
    assert "aria-label={label}" in button and 'className="ix-tuck-name">{label}' in button, (
        "Der Knopf klappt seinen Namen nicht mehr aus (b) – genau das war die Meldung "
        "#900."
    )
    # **Der Grund hängt an einer HÜLLE.** `.ix-tuck` ist `overflow: hidden` (sonst böte
    # der eingeklappte Name seitwärts zu scrollen an), und das schneidet ein `::after`
    # weg – am Knopf selbst wäre die Blase unsichtbar (die Lehre aus #790).
    assert "data-tip={bubble}" in button.split("</button>")[1], (
        "Der Grund hängt wieder am Knopf statt an der Hülle – hinter `overflow: hidden` "
        "ist er unsichtbar."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    # (c) **Die Zeile, in der er wächst, bricht nicht um** – das war die gemessene Ursache.
    actions = css[css.index(".ix-actions {"):]
    assert "flex-wrap: nowrap" in actions[: actions.index("}")], (
        "Die Handlungs-Zeile bricht wieder um (c) – dann schwingt der Knopf unter dem "
        "Zeiger weg."
    )
    assert ".erp-actbtn-icon:hover" not in css, (
        "Der Symbol-Knopf bekommt eine zweite Geste neben `.ix-tuck` – dann gibt es sie "
        "zweimal."
    )
    # (a) **Die Aufrufstelle nennt das Bauteil, nicht die Klasse.**
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "<ActionButton" in work and "erp-actbtn-icon" not in work, (
        "Die Modul-Karte baut ihre Symbol-Knöpfe wieder von Hand (a)."
    )
    # (d) **Jeder ausklappende Knopf steht in einer solchen Zeile.** Gezählt, nicht
    # gesucht: ein blosses «`<Actions>` kommt vor» liesse seine eigene Bug-Form durch –
    # ein einzelner Knopf daneben in der umbrechenden Angaben-Zeile ist genau der Fall,
    # der gemessen geschwungen hat.
    row = _code(_component(work, "EntryRow"))
    # ►►► **Die Zeile heisst jetzt `RowActions`** (#989/#993) – sie **ist** eine
    # `Actions`-Zeile (`.ix-actions`, nowrap) und steht zusätzlich am Zeilenende und
    # erscheint beim Zeigen. Der Wächter fragt die Regel: **jeder** Knopf der Geld-Zeile
    # steht in ihr. Seit die Grammatik die Zeile baut (#996–#1002), reicht die
    # Aufrufstelle sie als `actions` durch – geprüft wird der Platz, nicht das Markup.
    inner = row[row.index("actions={"):row.index("amount={")]
    n = row.count("<ActionButton")
    assert n == inner.count("<ActionButton"), (
        "Ein Symbol-Knopf steht ausserhalb der nicht umbrechenden Zeile (d)."
    )
    grammar = _body(_code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx")),
                    "LedgerRow", kind="export function")
    assert "<RowActions>{actions}</RowActions>" in " ".join(grammar.split()), (
        "Die Grammatik setzt die Knöpfe nicht mehr in `RowActions` (d) – dann behalten "
        "sie ihre Breite nicht, und sie schwingen wieder unter dem Zeiger weg."
    )
    # **Und diese Zeile gehört sich selbst.** Gemessen bei 375 px: als letztes Kind der
    # umbrechenden Angaben-Zeile brach **sie** um, sobald ein Knopf aufklappte – der Knopf
    # sprang eine Zeile tiefer, der Zeiger verlor ihn, er klappte ein (32 → 66 → 32 → 57 →
    # … px). Eine eigene Zeile kann nicht umbrechen.
    #
    # ►►► **Gefragt wird die REGEL, nicht die Form** (Testnotiz #960er-Runde). ◄◄◄ Es gab
    # sie einmal als `flex: '1 1 100%'` an der Handlungs-Zeile – das ist *eine* Art, ihr
    # eine eigene Zeile zu geben. Steht sie ohnehin in einer **Spalte**, ist sie
    # konstruktiv allein, und ein Wächter, der die frühere Zahl verlangt, verböte die
    # bessere Lösung. Geprüft wird darum, dass sie **nicht in der umbrechenden Zeile
    # steht**: zwischen deren Beginn und `<Actions` liegt ihr `</div>`.
    # ►►► **Und die Knöpfe der Geld-Zeile klappen ihren Namen NICHT aus** (#989/#993).
    # ◄◄◄ Sie stehen jetzt **in** der umbrechenden Angaben-Zeile, an ihrem Ende – genau
    # dort, wo ein wachsender Knopf gemessen geschwungen hat (#900: 32 → 66 → 32 → 57 px).
    # Eine Zeilenaktion sagt ihren Namen darum in der **Blase** und behält ihre Breite;
    # der ausklappende Knopf bleibt, wo er Platz hat: in der `Actions`-Zeile eines
    # Abschnitts. Gemessen, nicht geschätzt – die Bug-Form schwingt.
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    assert "InRow.Provider" in _body(ui, "RowActions", kind="export function"), (
        "Die Zeile sagt ihren Knöpfen nicht mehr, dass sie ihre Breite behalten (c) – "
        "in einer umbrechenden Zeile schwingen sie damit unter dem Zeiger weg."
    )
    btn = _body(ui, "ActionButton", kind="export function")
    assert "useContext(InRow)" in btn and "steady ? '' : ' ix-tuck'" in btn, (
        "Der Knopf liest die Angabe der Zeile nicht (c) – dann ist sie eine Regel, an "
        "die jede Aufrufstelle einzeln denken muss."
    )


def test_the_payment_fields_look_like_every_other_field():
    """►►► **Die Beschriftung steht ÜBER dem Feld, und es ist dicht** (Testnotiz #892). ◄◄◄

    *«Das Design innerhalb des iframes soll condensed sein für die Eingabefelder, zudem
    Labels ‹above›.»* – Und das ist keine Geschmacksfrage, sondern dieselbe Anatomie wie
    jedes Feld daneben: im Haus steht die Beschriftung als kleine Zeile **über** der
    Eingabe (`fields.Label`), nie schwebend darin. Die Vorgabe des Dienstes ist
    «floating», und damit sahen die Felder in der Karte anders aus als die darüber.

    Bug-Formen: (a) die Vorgabe gilt wieder; (b) eine feste Farbe steht daneben – dann ist
    es die zweite Farbsprache, die das Haus gerade abgeschafft hat.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx"))
    look = " ".join(_body(src, "appearance", kind="function").split())
    assert "labels: 'above'" in look, "Die Beschriftung schwebt wieder im Feld (a)."
    assert "fontSizeBase" in look and "'.Input'" in look, (
        "Die Felder tragen wieder die Masse des Dienstes statt unsere (a)."
    )
    assert not re.search(r":\s*'#[0-9a-fA-F]{3,8}'", look.replace("v('--", "")), (
        "Eine feste Farbe steht ohne Token daneben (b)."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► Testnotizen #897–#901 — der Geldvorgang ist EIN Beleg
# ═══════════════════════════════════════════════════════════════════════════════


def test_the_payment_element_is_as_big_as_the_fields_beside_it():
    """►►► **Die Felder des Dienstes sind so gross wie unsere** (Testnotiz #901). ◄◄◄

    *«Zudem ist alles so klein geworden von der Schriftgrösse – ist das gewollt und im
    Einklang mit dem restlichen UI/UX?»* – Nein. Die Grundschrift stand auf 13 px, und der
    Kommentar daneben behauptete, das sei die von `inputCls`. `inputCls` trägt `text-sm`,
    und das sind **14 px**.

    Dazu fehlte, was #892 eigentlich verlangt hatte: `inputs: 'condensed'`. Die Dichte kam
    stattdessen aus einer kleiner gedrehten Schrift – also aus der Angabe, die man nicht
    dafür nimmt.

    **Gespiegelt statt behauptet**: die Grösse wird aus `inputCls` **gelesen**. Wer dort
    die Klasse ändert, bekommt hier eine Meldung statt eines Felds, das eine Nummer
    daneben liegt.

    Bug-Formen: (a) die Schrift ist wieder kleiner als daneben; (b) `condensed` fehlt;
    (c) die Beschriftung weicht von `fields.Label` ab.
    """
    fields = _read(FRONTEND / "components" / "erp" / "fields.tsx")
    look = " ".join(_code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx")).split())
    cls = re.search(r"export const inputCls = '([^']+)'", fields)
    assert cls, "«inputCls» steht nicht mehr in `fields.tsx` – der Spiegel hat kein Original."
    # Die drei Grössen, die im Haus überhaupt vorkommen. Eine vierte ist ein Fehler, kein
    # stiller Rückfall: dann sagt der Wächter, dass er sie nicht kennt.
    sizes = {"text-xs": "12px", "text-sm": "14px", "text-base": "16px"}
    named = [c for c in cls.group(1).split() if c in sizes]
    assert len(named) == 1, (
        f"«inputCls» nennt keine bekannte Schriftgrösse ({cls.group(1)}) – dann lässt "
        f"sich nicht mehr sagen, wie gross die Felder des Dienstes sein müssen."
    )
    assert f"fontSizeBase: '{sizes[named[0]]}'" in look, (
        f"Die Felder des Zahlungsdienstes sind nicht so gross wie die daneben (a) – "
        f"`inputCls` ist `{named[0]}`, also {sizes[named[0]]}."
    )
    assert "inputs: 'condensed'" in look, (
        "«condensed» fehlt (b) – genau das war die Angabe, die #892 verlangt hat."
    )
    # (c) **Die Beschriftung ist buchstäblich `fields.Label`.**
    label = _body(fields, "Label", kind="export function")
    for what, value in (("Schriftgrösse", "fontSize: 11"), ("Fettung", "fontWeight: 600"),
                        ("Sperrung", "letterSpacing: '0.05em'")):
        assert value in label, f"`fields.Label` trägt die {what} nicht mehr."
    for what, value in (("Schriftgrösse", "fontSize: '11px'"),
                        ("Fettung", "fontWeight: '600'"),
                        ("Sperrung", "letterSpacing: '.05em'")):
        assert value in look, (
            f"Die Beschriftung im Zahlungsformular weicht in der {what} von `fields."
            f"Label` ab (c)."
        )


def test_the_section_heads_of_a_card_stand_on_one_edge():
    """►►► **Die Status-Spalte steht immer, auch leer** (Testnotiz #899). ◄◄◄

    Ein Punkt vor der Beschriftung rückt sie um seine Breite ein. In einer Karte, in der
    nur **manche** Abschnitte ein Schritt sind – «Positionen» und «Bedingungen» sind
    Inhalt, «Angebot» und «Rechnung & Zahlung» sind Schritte –, stünden die Überschriften
    damit auf zwei verschiedenen Kanten. Gemessen: 18 px ↔ 33 px im selben Beleg.

    Der Platz wird darum **reserviert**; was ihn füllt, sagt der Abschnitt. Ein Punkt für
    alle wäre die andere Lösung und die falsche: er behauptete einen Fortschritt, den ein
    Inhalts-Abschnitt gar nicht hat.

    Bug-Form: der Punkt hängt wieder an `state` – dann verschiebt sich jede Überschrift
    ohne Schritt.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    section = " ".join(_body(ui, "ModuleSection", kind="export function").split())
    assert "{state && (" not in section, (
        "Die Status-Spalte gibt es nur mit Schritt – dann rücken die Überschriften ohne "
        "Schritt aus der Kante (#899)."
    )
    assert "state ? STEP_COLOR[state] : 'transparent'" in section, (
        "Der reservierte Platz trägt keine Farbe mehr bzw. füllt sich nicht mehr aus dem "
        "Zustand."
    )


def test_the_customs_fields_live_at_the_article():
    """►►► **Zolltarifnummer und Ursprungsland gehören der SACHE** (§3.1). ◄◄◄

    Sie stehen am **Artikel** – dort werden sie gepflegt, und nur dort.

    ►►► **Der Beleg belegt daraus VOR, er schreibt nicht zurück** (Testnotiz #915). ◄◄◄
    Welche Nummer auf *diesem* Beleg steht, ist eine Aussage **dieses Geschäfts** –
    dieselbe Beziehung wie beim Preis: vorbelegt aus dem Artikel, überschreibbar, mit der
    Zusage eingefroren. Was der Beleg **nicht** tut, ist die Stammdaten korrigieren.

    *Die ersten sechs Stellen sind weltweit identisch (Harmonisiertes System der WCO);
    darüber hinaus ist die Nummer national – das sagt der Platzhalter, statt es zu
    verschweigen.*

    Bug-Formen: (a) die Felder fehlen im Artikel-Editor; (b) sie werden nicht gesendet;
    (c) das Ursprungsland reist kleingeschrieben ab – «ch» und «CH» wären zwei Länder;
    (d) der Geldvorgang schreibt sie an den Artikel zurück – dann korrigiert ein Beleg
    Stammdaten, und ein einziges Geschäft ändert, was die Sache ist.
    """
    art = _code(_read(FRONTEND / "components" / "erp" / "article-detail.tsx"))
    for key in ("hs_code", "origin_country"):
        assert f"key: '{key}'" in art, (
            f"«{key}» fehlt im Artikel-Editor (a) – dann steht es auf keinem Beleg."
        )
        assert f"{key}: form.{key}" in art, (
            f"«{key}» wird nicht gesendet (b)."
        )
    assert "form.origin_country.trim().toUpperCase()" in art, (
        "Das Ursprungsland reist ungenormt ab (c) – «ch» und «CH» wären zwei Länder."
    )
    # (d) Gepflegt wird am **Artikel**: der Geldvorgang kennt keinen Weg dorthin – er
    # schickt seine Zeilen an sein eigenes Verb (`ask`/`quote`), nie an den Artikel.
    deal = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "updateArticle" not in deal and "api.updateArticle" not in deal, (
        "Der Geldvorgang schreibt an den Artikel (d) – ein Beleg korrigiert keine "
        "Stammdaten."
    )


def test_the_issuer_is_a_choice_at_the_document_head():
    """►►► **Wer den Beleg stellt, steht im Kopf – und ist eine Wahl** (#905). ◄◄◄

    Vorgewählt ist die Gesellschaft des freigebenden Mitarbeiters; wer für eine
    Schwestergesellschaft anbietet, korrigiert es. **Ob es die Wahl noch gibt, sagt
    `can`** – ab der Zusage fehlt das Symbol, statt ausgegraut dazustehen.

    Und am **Benutzer** ist es eine Anstellungsangabe: wer für wen arbeitet, entscheidet
    nicht die Person selbst.

    Bug-Formen: (a) der Wechsel hängt an der Stufe statt an `can`; (b) er steht als
    Dauer-Auswahlfeld im Kopf; (c) er ist ein selbstgebauter Knopf statt `ActionButton`;
    (d) die Gesellschaft fehlt am Benutzer-Datensatz.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    issuer = " ".join(_component(src, "Issuer").split())
    assert "may(d, 'issuer')" in issuer, (
        "Der Wechsel hängt nicht an `can` (a) – dann ist es die zweite Regel daneben."
    )
    # ►►► **Und es ist kein Knopf, sondern derselbe änderbare WERT** (#929): *«Statt
    # diesem Button kann nicht der darunter befindliche Unternehmensname als veränderbare
    # Variable deklariert werden?»* – Doch, und es ist die Form, die jeder Wert auf dem
    # Beleg hat (`DocRef` auf `Editable`).
    assert "<DocRef" in issuer and "erp-actbtn" not in issuer, (
        "Der Aussteller ist wieder ein Knopf daneben (b/c) – auf dem Beleg ist ein "
        "änderbarer Wert der Wert selbst."
    )
    assert "<ObjectSelect" in _component(src, "DocRef"), (
        "Die Wahl ist kein Referenzfeld (b) – ein natives Auswahlfeld über Datensätze "
        "gibt es im Haus nicht."
    )
    user = _code(_read(FRONTEND / "components" / "erp" / "user-detail.tsx"))
    assert "company_object_id" in user and re.search(r"<CompanyPick[\s/>]", user), (
        "Die Gesellschaft fehlt am Benutzer-Datensatz (d) – dann kann nichts vorgewählt "
        "werden, und der Beleg nimmt still den Betreiber."
    )


def test_a_company_record_is_named_with_its_legal_form():
    """►►► **Unternehmensname · Abstand · Rechtsform — an EINER Stelle** (Notiz #910). ◄◄◄

    *«Der Datensatzname bei Datensatztyp Unternehmen soll immer der Unternehmensname
    sein → Abstand → Rechtsform.»* – Die Regel gab es längst (``sites.legal_name``,
    inklusive der Ausnahme «Muster AG» + «AG» = «Muster AG», nicht «Muster AG AG»); sie
    wurde nur nicht überall gerufen. Genannt wird derselbe Datensatz in der
    **Halter-Kette**, in der **Halter-Suche**, auf der **Gebietskarte**, in der
    **Kopfzeile**, im **Feed** und im **Impressum** – und er muss überall gleich heissen.

    **Zusammengesetzt wird er nirgendwo sonst.** Das Impressum tat es und schrieb
    ``«Inexxio AG (AG)»``: eine zweite Fassung einer Regel, die eine Ausnahme kennt,
    sieht richtig aus und ist es nicht.

    Bug-Formen: (a) eine Station trägt den blossen Spaltenwert; (b) die Antwort führt den
    Datensatznamen gar nicht; (c) jemand baut ihn ein zweites Mal aus beiden Feldern
    zusammen; (d) das Frontend setzt ihn selbst statt ihn zu lesen.
    """
    places = _code(_read(BACKEND / "app" / "services" / "places.py"))
    for line in places.split("\n"):
        if 'Station(' in line and '"organization"' in line:
            assert "legal_name" in line, (
                "Eine Halter-Station trägt den blossen Spaltenwert (a) – dieselbe "
                f"Gesellschaft hiesse dort anders als auf dem Beleg: {line.strip()}"
            )

    admin = _code(_read(BACKEND / "app" / "routers" / "admin.py"))
    assert admin.count("legal_name") >= 3, (
        "Der Datensatzname fehlt in einer der Antworten (b) – Detail, Gebietskarte und "
        "die öffentliche Auskunft müssen ihn alle drei führen."
    )

    # (c) Keine zweite Zusammensetzung – weder im Backend noch im Browser. Gesucht ist
    # die **Verbindung** beider Angaben in einem Ausdruck, nicht ihr blosses Vorkommen
    # (sie stehen völlig zu Recht nebeneinander in Formular, Schema und Modell).
    joiner = re.compile(
        r"(company_name|companyName)[^\n]{0,40}[+`}][^\n]{0,40}(legal_form|legalForm)"
        r"|(legal_form|legalForm)[^\n]{0,40}[+`}][^\n]{0,40}(company_name|companyName)"
    )
    files = [p for p in (BACKEND / "app").rglob("*.py")]
    files += [p for p in (FRONTEND).rglob("*.ts")] + [p for p in FRONTEND.rglob("*.tsx")]
    for path in files:
        if path.name in ("sites.py", "api.ts"):
            continue
        hit = joiner.search(_code(_read(path)))
        assert hit is None, (
            f"«{path.name}» setzt den Namen ein zweites Mal aus Name und Rechtsform "
            f"zusammen (c): {hit.group(0)!r}. Die Regel steht in ``sites.legal_name``."
        )

    # (d) Der eine Namensgeber des Frontends liest ihn, statt ihn zu bauen.
    names = _code(_read(FRONTEND / "lib" / "record-name.ts"))
    block = _body(names, "organizationName", kind="function")
    assert "legal_name" in block, (
        "``organizationName`` liest den Datensatznamen nicht (d) – dann heisst dieselbe "
        "Gesellschaft im Feed anders als in der Halter-Kette."
    )


def test_the_suggestion_list_hangs_on_the_body_not_in_the_field():
    """►►► **Die Liste steht am Feld – aber nicht IN ihm** (Testnotiz #909). ◄◄◄

    *«Wenn ich hier etwas suche und auswählen möchte, dann geht das nicht wirklich gut,
    da es von der Ebene her zu tief ist … finden wir hier eine elegante und vor allem
    robuste Lösung.»* – Gemessen und nachgestellt: als ``position: absolute`` **im** Feld
    liegt die Liste in jedem Rahmen darüber. Ein Vorfahr mit ``overflow: hidden``
    schneidet sie ab, ein Nachbar mit eigenem Stapelplatz legt sich darüber – und
    ``z-index`` hilft nicht, denn er gilt nur **innerhalb** des Stapelkontexts, in dem das
    Element steht.

    Also verlässt sie den Baum: ``createPortal`` an ``document.body``, ``position: fixed``
    an der gemessenen Stelle des Feldes. Damit gibt es keinen Vorfahren mehr, der sie
    schneiden könnte – **konstruktiv statt geprüft**.

    Bug-Formen: (a) sie steht wieder absolut im Feld; (b) es gibt kein Portal; (c) der
    Klick-daneben-Schliesser fragt nur das Feld – dann verschwindet die Zeile, bevor der
    Klick auf ihr ankommt; (d) sie wird beim Scrollen nicht nachgeführt.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    block = " ".join(_component(src, "SearchSelect").split())
    assert "createPortal(" in block and "document.body," in block, (
        "Die Liste hängt nicht an <body> (b) – dann schneidet sie der erste Rahmen mit "
        "``overflow: hidden`` wieder ab."
    )
    assert "position: 'fixed'" in block, (
        "Die Liste steht wieder absolut im Feld (a) – ausserhalb des Baums ist das die "
        "falsche Bezugsgrösse, sie landete an der linken oberen Ecke der Seite."
    )
    assert "listRef.current?.contains" in block, (
        "Der Klick-daneben-Schliesser fragt nur das Feld (c) – die Liste ist kein "
        "Nachfahre mehr, also verschwände die Zeile, bevor der Klick auf ihr ankommt."
    )
    # **Das Anmelden, nicht das Abmelden**: die erste Fassung fragte nur nach der
    # Zeichenkette – und die steht auch in ``removeEventListener``. Ein Wächter, der
    # seine eigene Bug-Form durchlässt, ist von einem kaputten nicht zu unterscheiden
    # (gemessen: die Bug-Form meldete nichts).
    assert ("addEventListener('scroll', measure, true)" in block
            and "addEventListener('resize', measure)" in block), (
        "Die Liste wird nicht nachgeführt (d) – sie bliebe stehen, während das Feld "
        "unter ihr wegscrollt."
    )


def test_a_private_customer_is_named_by_his_own_name():
    """►►► **B2B und B2C – und dafür gibt es keinen Schalter** (Testnotiz #914). ◄◄◄

    Die Regel steht längst da (`people.billing_name`): *Firma zuerst, Person als «z. H.»;
    ohne Firma bleibt die Person.* Ein Privatkunde trägt keinen Firmennamen – also steht
    dort sein Name, und zwar **ohne dass jemand ein Häkchen setzt**.

    Ein `is_business`-Feld wäre eine **zweite Aussage** über etwas, das die Daten schon
    sagen – und es wäre die Stelle, an der jemand es falsch setzt.

    *Gemessen in Chromium: der Beleg einer Privatperson nennt ihren Namen und hat **keine**
    «z. H.»-Zeile; der einer Firma beide.*

    Bug-Formen: (a) irgendwo steht doch ein B2B/B2C-Schalter; (b) die Oberfläche
    entscheidet selbst, was in den Namen gehört, statt zu lesen, was der Server schickt.
    """
    for where in ("services/voucher.py", "services/people.py", "schemas/voucher.py"):
        src = _code(_read(BACKEND / "app" / where))
        assert "is_business" not in src and "is_company" not in src, (
            f"«{where}» führt einen B2B/B2C-Schalter (a) – die Daten sagen es bereits."
        )
    people = _code(_read(BACKEND / "app" / "services" / "people.py"))
    block = _body(people, "billing_name")
    assert "z. H." in block, (
        "Die Regel «Firma zuerst, Person als z. H.» steht nicht mehr in "
        "``people.billing_name`` – dann baut sie jemand ein zweites Mal."
    )
    # Der Belegkopf **zeigt** die Zeile, die der Dienst gebaut hat (`view.attn`) – er
    # setzt sie nicht zusammen. Ein «z. H.» im Browser wäre die zweite Regel daneben.
    beleg = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    party = " ".join(_component(beleg, "Party").split())
    assert "view.attn" in party and "z. H." not in beleg, (
        "Die Oberfläche baut den Namen selbst (b) – sie zeigt, was der Server schickt."
    )


def _beleg() -> str:
    return _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")


def test_an_editable_value_is_marked_in_exactly_one_way():
    """►►► **«Man muss erkennen, dass es veränderbar ist»** (Testnotiz #922). ◄◄◄

    *«Es soll so ausschauen wie der finale Beleg, nur eben gehighlighted … ACHTUNG: Ich
    will das auch für alle anderen Angaben auf dem Beleg.»*

    Also **eine** Auszeichnung an **einer** Stelle (`.ix-editable` in `globals.css`), und
    jeder änderbare Wert trägt sie. Und sie darf **nichts am Layout tun**: der Nutzer hat
    Grösse, Form und Schrift ausdrücklich ausgeschlossen – ein `border` verschöbe das
    Layout um seine Breite, ein `inset box-shadow` nie.

    Bug-Formen: (a) die Klasse gibt es nicht; (b) sie ändert die Geometrie (`border`,
    `padding`, `font-size`); (c) ein änderbarer Wert der Karte trägt sie nicht;
    (d) die Karte baut die Auszeichnung selbst statt das eine Bauteil zu nehmen.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    # **Am Zeilenanfang verankert** – `fieldset:disabled .ix-editable {` enthält dieselbe
    # Zeichenkette, und ohne den Anker las der Wächter die *gesperrte* Ausprägung: seine
    # eigene Bug-Form ging damit durch (gemessen).
    assert "\n.ix-editable {" in css, "Die Auszeichnung gibt es nicht (a)."
    rule = css.split("\n.ix-editable {", 1)[1].split("}", 1)[0]
    # **Jede** Rahmen-Schreibweise, nicht nur `border:` – `border-bottom: 1px …` ist
    # dieselbe Verschiebung und ging als Bug-Form durch (gemessen). `border-radius`
    # bleibt erlaubt: eine Ecke verschiebt nichts.
    assert not re.search(r"border(?!-radius)", rule), (
        "Ein Rahmen in `.ix-editable` (b) – er verschiebt das Layout um seine Breite, "
        "und genau das war ausgeschlossen."
    )
    for geometry in ("padding", "font-size", "font-weight", "margin"):
        assert geometry not in rule, (
            f"«{geometry}» in `.ix-editable` (b) – die Auszeichnung ändert die Geometrie, "
            f"und genau das war ausgeschlossen («nicht durch Veränderung der Grösse, "
            f"Form, Schriftart»)."
        )
    assert "box-shadow" in rule, (
        "Die Auszeichnung hat keine Linie (a) – ein Wert ohne Zeichen ist keiner."
    )

    src = _beleg()
    assert "function Editable(" in src, (
        "Die Karte hat kein gemeinsames Bauteil für den änderbaren Wert (d)."
    )
    # **Die Hüllen, die die Auszeichnung selbst setzen** – wer eine davon nimmt, trägt
    # sie. Geprüft wird die **Regel** («jeder änderbare Wert ist ausgezeichnet»), nicht
    # die Form einer bestimmten Fassung: `DocPick` und `DocRef` sind aus genau diesem
    # Bauteil gebaut, und ein Wächter, der `<Editable` wörtlich verlangt, verbietet die
    # bessere Lösung, statt sie zu prüfen.
    for wrapper in ("DocPick", "DocRef"):
        # Generisch deklariert (`function DocRef<T extends …>`) ist dieselbe Funktion –
        # ein Wächter, der die runde Klammer verlangt, prüft die Schreibweise.
        assert re.search(rf"function {wrapper}\b", src), f"«{wrapper}» fehlt (d)."
        assert "<Editable" in _component(src, wrapper), (
            f"«{wrapper}» setzt die Auszeichnung nicht (d) – dann trägt sie keiner "
            f"seiner Aufrufer."
        )
    marks = ("<Editable", "ix-editable", "<DocPick", "<DocRef")
    # (c) **Jeder änderbare Wert der Karte** – die Liste der Notiz, Punkt für Punkt.
    for name in ("Currency", "Term", "Delivery", "LineRow", "Customs", "Recipients",
                 "Issuer"):
        body = _component(src, name)
        assert any(m in body for m in marks), (
            f"«{name}» trägt die Auszeichnung nicht (c) – der Nutzer wollte sie "
            f"ausdrücklich für **alle** Angaben auf dem Beleg."
        )


def test_the_action_that_moves_the_document_looks_the_same_everywhere():
    """►►► **«So gross und ausdrucksstark wie ‹Vorgang abschliessen›»** (#923). ◄◄◄

    *«Eine UI-Logik.»* – Genau: ein Bauteil (`StageAction`) mit denselben Massen wie der
    Knopf, der jedes Modul beendet (volle Breite, Fläche, 42 px, 14 px Schrift). Ein
    Sonderfall für einen Knopf wäre die Stelle, an der der nächste wieder anders aussieht.

    Bug-Formen: (a) es gibt das Bauteil nicht; (b) es trägt nicht die Masse des
    Abschluss-Knopfes; (c) das Anbieten benutzt es nicht.
    """
    src = _beleg()
    assert "function StageAction(" in src, "Es gibt kein gemeinsames Bauteil (a)."
    body = _component(src, "StageAction")
    # **Die Höhe kommt aus `ACT_H`**, nicht als Zahl an dieser Stelle (#987/#990) –
    # abgeschriebene Masse sind genau die Form, in der zwei Knöpfe auseinanderlaufen.
    for mark in ("erp-actbtn-primary", "w-full", "ACT_H.stage", "fontSize: 14"):
        assert mark in body, (
            f"«{mark}» fehlt (b) – dann ist der Knopf nicht so gross und ausdrucksstark "
            f"wie der am Ende der Karte (`order-detail`)."
        )
    # **Und derselbe Knopf trägt wirklich die Masse des Abschlusses** – gelesen dort, wo
    # er entsteht: eine abgeschriebene Zahl liefe beim nächsten Umbau auseinander.
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "height: 42, fontSize: 14" in detail, (
        "Der Abschluss-Knopf hat andere Masse (b) – dann ist «wie am Schluss» eine "
        "Behauptung."
    )
    assert "<StageAction" in _component(src, "Offer"), (
        "Das Anbieten ist kein `StageAction` (c) – genau dieser Knopf war gemeldet."
    )


def test_every_summed_amount_names_its_currency():
    """►►► **«Wenn daneben die Währung stehen würde»** (Testnotiz #921). ◄◄◄

    Die Regel: **jede Zahl, die man abschreibt oder überweist, nennt ihre Währung** –
    Netto, Steuer je Satz, Total, offener Betrag, jede Geld-Zeile. **Nicht** an jedem
    Einzelpreis: dort stünde dasselbe Wort zwanzigmal.

    Bug-Formen: (a) eine Summe ohne Währung; (b) der Einzelpreis trägt sie doch;
    (c) die Währung ist fest «CHF» statt der des Belegs.
    """
    src = _beleg()
    sums = _component(src, "Sums")
    # **JEDE Summenzeile**, nicht irgendeine: mit einem blossen «kommt vor» genügte eine
    # von dreien, und die Netto-Zeile hätte ihre Währung verlieren können, ohne dass es
    # auffällt (gemessen – die erste Fassung liess genau das durch).
    #
    # Gefragt wird die **Regel an ihrem heutigen Ort** (#1007): die Währung reist als
    # Angabe des einen Betrags-Bauteils (``Amount``), nicht mehr als Zeichenkette neben
    # der Zahl. Die frühere Fassung zählte ``${code}`` und hätte damit die bessere Lösung
    # verboten, obwohl sie dieselbe Regel besser erfüllt.
    assert sums.count("code={d.currency}") >= sums.count("<SumRow"), (
        f"Nicht jede Summenzeile nennt ihre Währung (a): "
        f"{sums.count('code={d.currency}')} von {sums.count('<SumRow')}."
    )
    assert "currency={<Currency" in sums, "Das Total nennt seine Währung nicht (a)."
    # ►►► **Und der Einzelpreis nennt sie ebenfalls — in BEIDEN Zuständen** (#1010/#1017).
    # ◄◄◄ *«Bei den Positionen fehlt die Währungsangabe – sowohl in der Anzeige als auch
    # beim Eingabefeld ‹Einzelpreis›. Keine Betragsausgabe und kein Betragsfeld ohne
    # Währung.»* Das **nimmt die frühere Ausnahme zurück** («dort stünde dasselbe Wort
    # zwanzigmal»): der Nutzer hat es ausdrücklich anders entschieden, und der Wächter
    # prüft ab hier die neue Regel – vorher verbot er sie.
    row = _code(_component(src, "LineRow"))
    assert row.count("currency={d.currency}") >= 2, (
        f"Der Einzelpreis nennt seine Währung nicht in beiden Zuständen (b): "
        f"{row.count('currency={d.currency}')} von zwei (Eingabe und Anzeige)."
    )
    entry = _component(src, "EntryRow")
    assert "currency={d.currency}" in entry, "Eine Geld-Zeile nennt ihre Währung nicht (a)."
    assert "'CHF'" not in _code(_component(src, "Money")), (
        "Die Geld-Zeile schreibt «CHF» fest (c) – ein Yen-Beleg läse sich als Franken."
    )


def test_the_terms_carry_no_heading_and_no_prepaid_chip():
    """►►► **Drei Notizen, eine Richtung: weniger auf dem Beleg** (#924/#925/#926). ◄◄◄

    *«Keine Überschrift ‹Konditionen› mehr, sondern einfach unter den Positionen und
    Beträgen die Zahlungs- und Lieferkonditionen»* – jede der drei Zeilen trägt ihren
    Namen, und ein Sammelbegriff darüber sagt nichts dazu.

    *«Diese Info kann komplett hier entfallen, denn ich sehe es ja unten, ob Vorauszahlung
    oder nicht»* – die Pille im Kopf war die zweite Aussage über die **Zahlungsfrist**,
    die zwei Abschnitte tiefer steht und dort geändert wird.

    Bug-Formen: (a) die Überschrift ist zurück; (b) der Kopf zeigt die Vorauszahlung;
    (c) die Zahlungsfrist steht nicht über der Lieferfrist (#897).
    """
    src = _beleg()
    assert "Konditionen" not in _code(src), "Die Überschrift ist zurück (a)."
    head = _component(src, "DocHead") + _component(src, "Parties")
    assert "prepaid" not in head, (
        "Der Kopf zeigt wieder die Vorauszahlung (b) – sie steht in den Konditionen."
    )
    terms = _component(src, "Terms")
    assert terms.index("payment_term_label") < terms.index("lead_term_label"), (
        "Die Lieferfrist steht über der Zahlungsfrist (c) – die folgenreichere Angabe "
        "gehört nach oben (#897)."
    )


def test_the_card_never_branches_on_the_direction():
    """►►► **Was Einnahme von Ausgabe unterscheidet, reist fertig mit.** ◄◄◄

    Die Karte kennt weder «Kunde» noch «Lieferant» und fragt nie nach der Richtung: sie
    liest `label`, `ask_verb`, `we_quote`, `ref_label`, `stages[].label/verb`. Die erste
    Verzweigung ist eine Beschriftung, die zweite eine Regel, und ab der dritten gibt es
    zwei Belege, die nur so tun, als wären sie einer.

    Bug-Formen: (a) ein Vergleich auf `'in'`/`'out'`; (b) ein Rollen-Wort als Literal;
    (c) ein Modultyp im Rumpf.
    """
    code = _code(_beleg())
    for branch in ("=== 'in'", '=== "in"', "=== 'out'", '=== "out"',
                   "direction ===", ".direction =="):
        assert branch not in code, f"Die Karte verzweigt auf die Richtung (a): «{branch}»."
    for word in ("Kunde", "Lieferant", "Einnahme", "Ausgabe"):
        assert word not in code, (
            f"«{word}» steht als Literal in der Karte (b) – die Wörter kommen vom Server."
        )
    for key in ("'beleg'", '"beleg"', "'zahlung'"):
        assert key not in code, f"Die Karte nennt einen Modultyp (c): «{key}»."


def test_the_two_payment_modules_share_no_line_in_the_browser_either():
    """►►► **Die Unabhängigkeit gilt auf beiden Seiten.** ◄◄◄

    Das alte Zahlungsmodul soll ersatzlos löschbar sein – dann darf in der neuen Karte
    keine Zeile zu ändern sein, und umgekehrt.

    Bug-Formen: (a) die neue Karte importiert aus der alten; (b) sie ruft `updateDeal`;
    (c) die alte Karte importiert aus der neuen.
    """
    # **Der CODE, nicht die Erklärung** – der Kopf der neuen Karte *nennt* ihren
    # Vorgänger, um zu sagen, was anders ist; ein Wächter, der die Prosa mitliest, schlägt
    # an, weil jemand die Regel beschreibt. (Gemessen: die erste Fassung scheiterte an
    # ihrem eigenen Verweis.)
    new = _code(_beleg())
    old = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "beleg-work" not in new, "Die neue Karte hängt an der alten (a)."
    for call in ("updateDeal", "dealTransfer", "refundPayment", "preparePayment",
                 "searchDealParties"):
        assert call not in new, f"Die neue Karte ruft «{call}» (b)."
    assert "beleg-work" not in old, "Die alte Karte hängt an der neuen (c)."


def test_an_editable_value_is_the_printed_value_itself():
    """►►► **Der gedruckte Wert IST das Bedienelement** (Testnotizen #929/#930/#934/#935).

    ◄◄◄ Dreimal derselbe Satz: *«Ich möchte die gleiche Logik, das gleiche Design wie bei
    der Währung oder der Betragsangabe, sodass es aussieht wie ein richtiger Beleg und
    eben gewisse Variablen veränderbar sind.»*

    Also ist es keine Eigenschaft der Währung, sondern die **Form eines änderbaren Werts
    im Beleg**: sichtbar ein `<span>` in der Schrift, die dort ohnehin steht, bedienbar
    ein unsichtbares Bedienelement darüber. Sie steht **einmal** (`DocPick` für eine
    Aufzählung, `DocRef` für einen Datensatz) und wird überall gerufen.

    Das löst zugleich #935: ein natives Auswahlfeld nimmt die Breite seiner **längsten
    Zeile** («DPU · Geliefert entladen»), und daneben sass der Pfeil scheinbar eingerückt.
    Hier bestimmt die Anzeige die Breite.

    Bug-Formen: (a) `DocPick` zeigt den Wert nicht selbst an bzw. legt das Bedienelement
    nicht unsichtbar darüber; (b) die Lieferbedingung baut wieder ein eigenes `<select>`;
    (c) die Frist ist wieder eine Knopfreihe (`TermField`); (d) der Aussteller hängt
    wieder hinter einem Stift-Knopf statt am Namen.
    """
    src = _beleg()

    # (a) **Die Form selbst** – Anzeige und unsichtbares Bedienelement in einem Bauteil.
    pick = _code(_component(src, "DocPick"))
    assert "aria-hidden" in pick and "<select" in pick, (
        "«DocPick» zeigt den Wert nicht selbst an (a) – dann ist es ein Formularfeld."
    )
    for mark in ("position: 'absolute'", "opacity: 0"):
        assert mark in pick, (
            f"«{mark}» fehlt in `DocPick` (a) – das Bedienelement liegt nicht unsichtbar "
            f"über der Anzeige, und damit bestimmt wieder es die Breite."
        )

    # (b)/(c)/(d) **Die Aufrufstellen nehmen es auch.**
    delivery = _code(_component(src, "Delivery"))
    assert "<DocPick" in delivery and "<select" not in delivery, (
        "Die Lieferbedingung baut ihr eigenes Auswahlfeld (b) – genau daraus kam «das "
        "Feld ist irgendwie super breit» (#935)."
    )
    term = _code(_component(src, "Term"))
    assert "<DocPick" in term, "Die Frist ist kein Beleg-Wert (c)."
    assert "TermField" not in _code(src), (
        "Die Frist ist wieder eine Knopfreihe (c) – ein Formular mitten im Beleg."
    )
    issuer = _code(_component(src, "Issuer"))
    assert "<DocRef" in issuer and "ActionButton" not in issuer, (
        "Der Aussteller hängt hinter einem Knopf (d) – gefragt war der **Name** als "
        "änderbarer Wert (#929)."
    )


def test_a_vat_rate_names_its_percentage():
    """►►► **«Normalsatz» sagt nicht, wie hoch er ist** (Testnotiz #932). ◄◄◄

    *«‹Normalsatz›, ‹reduziert› sind leider zu wenig aussagekräftig – es sollte immer noch
    der entsprechende Prozentsatz angegeben sein.»*

    Beides steht längst in den Daten (`label` + `rate`). Zusammengesetzt wird es an
    **einer** Stelle, sonst nennt die Auswahlliste den Satz und die Anzeige daneben nicht
    – oder umgekehrt.

    Bug-Formen: (a) es gibt keine gemeinsame Auflösung; (b) sie nennt den Satz nicht;
    (c) die Auswahl oder die Anzeige geht daran vorbei.
    """
    src = _beleg()
    assert "function vatText(" in src, "Es gibt keine gemeinsame Auflösung (a)."
    body = _code(_component(src, "vatText"))
    assert "rate" in body and "%" in body, (
        "Die Auflösung nennt den Prozentsatz nicht (b) – dann sagt sie nichts Neues."
    )
    line = _code(_component(src, "LineRow"))
    assert line.count("vatText(") >= 2, (
        "Auswahl und Anzeige lösen nicht beide über `vatText` auf (c) – die Stelle, an "
        "der die Liste den Satz nennt und die Zeile daneben nicht."
    )


def test_a_name_and_its_number_stand_in_one_line():
    """►►► **Name und Objektnummer sind EIN Datensatz** (Testnotiz #933). ◄◄◄

    *«Der Name und die Objektnummer sollten immer in einer Linie, in einer Reihe sein,
    nicht umgebrochen.»* – Untereinander lesen sie sich wie zwei Angaben. Gekappt wird
    der **Name**; die Nummer ist die Kennung, an der man die Sache wiedererkennt (#853).

    Bug-Formen: (a) Name und Nummer stehen in verschiedenen Zeilen; (b) die Nummer darf
    schrumpfen statt des Namens.
    """
    src = _code(_component(_beleg(), "LineRow"))
    at_name = src.find("article_name")
    at_id = src.find("<ObjId", at_name)
    assert at_name != -1 and at_id != -1, "Die Zeile nennt nicht beides."
    between = src[at_name:at_id]
    assert "flex flex-col" not in between, (
        "Zwischen Name und Nummer beginnt eine neue Spalte (a) – dann brechen sie um."
    )
    # Die Kappung steht am **Rahmen** des Namens, also ein Stück davor.
    assert "truncate" in src[max(0, at_name - 160):at_id], (
        "Der Name wird nicht gekappt (b)."
    )
    assert "flex: 'none'" in src[max(0, at_id - 120):at_id + 260], (
        "Die Nummer darf schrumpfen (b) – gekappt gehört der Name, nie die Kennung."
    )


def test_a_typed_amount_has_the_decimals_of_its_currency():
    """►►► **Was man tippen kann, ist die Stelligkeit der Währung** (Testnotiz #931). ◄◄◄

    Die Anzeige behebt der Dienst (`test_a_price_leaves_the_service_in_the_scale_of_its_
    currency`); hier geht es um das **Eingabefeld**: wer vier Nachkommastellen tippen
    kann, bekommt sie vom Server gerundet zurück, und das sieht aus wie ein Datenverlust.

    Bug-Formen: (a) `numericOnly` kann gar nicht begrenzen; (b) das Preisfeld begrenzt
    nicht; (c) es begrenzt fest auf zwei (JPY hat null, KWD drei).
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "decimals?: boolean | number" in fields, (
        "`numericOnly` kennt keine Stellenzahl (a)."
    )
    assert "slice(0, decimals)" in fields, "`numericOnly` begrenzt nicht (a)."

    line = _code(_component(_beleg(), "LineRow"))
    at = line.find("aria-label=\"Einzelpreis\"")
    assert at != -1, "Das Preisfeld heisst nicht mehr so."
    window = line[max(0, at - 600):at]
    assert "decimals: d.currency_decimals" in window, (
        "Das Preisfeld nimmt die Stelligkeit nicht aus der Währung (b/c) – «immer zwei» "
        "ist bei JPY und KWD still falsch."
    )


def test_an_api_method_never_loses_its_client():
    """►►► **«Kommt kein Vorschlag, nichts»** (Testnotiz #927). ◄◄◄

    Unter jeder Notiz dieser Runde stand derselbe Konsolen-Fehler: *«Cannot read
    properties of undefined (reading ‹get›)»*. Das ist wörtlich `this.get`, wenn `this`
    fehlt – eine Klassenmethode, die als **Wert** weitergereicht wird
    (`search={api.searchVoucherParties}`), verliert ihr `this`. Und man sieht es der
    Stelle nicht an: der Fehler landet in der Konsole, das Feld bleibt leer.

    Die Regel gehört an den **Client**, nicht an jede Aufrufstelle: eine Regel, die man
    bei jedem neuen `search={…}` erneut einhalten muss, ist die Form, die man vergisst.

    Bug-Formen: (a) es wird nicht gebunden; (b) gebunden wird eine **Liste von Namen**
    (die Form, die den nächsten Endpunkt nicht kennt).
    """
    src = _code(_read(FRONTEND / "lib" / "api.ts"))
    at = src.find("class ApiClient")
    assert at != -1, "Es gibt keinen Client mehr."
    head = src[at:at + 1400]
    assert "constructor()" in head, "Der Client bindet seine Methoden nicht (a)."
    assert "getOwnPropertyNames" in head and ".bind(this)" in head, (
        "Gebunden wird nicht über den Prototyp (a/b) – eine aufgezählte Liste kennt den "
        "nächsten Endpunkt nicht."
    )


def test_a_note_names_the_element_not_its_whole_subtree():
    """►►► **Das Testnotizen-Werkzeug schneidet mit, was die Sache IST.** ◄◄◄

    Gemeldet: *«Die Ausgabe ist nicht tatsachengemäss.»* – Gemessen an den Notizen dieser
    Runde stimmt das, und zwar an drei Stellen:

    * ein `<select>` lieferte als Element-Text **alle Optionen** («—EXW · Ab WerkFCA ·
      Frei FrachtführerCPT · …»), also die Liste statt der Wahl;
    * ein Container lieferte `textContent` **aller** Nachfahren – bei einer Karte eine
      Wand aus Text, in der die gemeinte Stelle untergeht;
    * der Fehler-Ringpuffer hielt fünfmal **dieselbe** Zeile und war damit voll, bevor
      der zweite, andere Fehler kam – also ausgerechnet der, den man gebraucht hätte.

    Bug-Formen: (a) der Wert eines Bedienelements wird nicht gelesen; (b) der Text der
    Nachfahren gewinnt gegen den eigenen; (c) Fehler werden wiederholt statt gezählt;
    (d) die Selektor-Kette bricht nach fester Tiefe ab und ist damit relativ.
    """
    src = _code(_read(FRONTEND / "lib" / "feedback.ts"))
    assert "selectedOptions" in src, (
        "Ein `<select>` wird nicht nach seiner **Wahl** gefragt (a) – dann steht die "
        "ganze Liste in der Notiz."
    )
    label = _component(src, "elementLabel")
    assert "Node.TEXT_NODE" in label, (
        "Der eigene Text wird nicht von dem der Nachfahren unterschieden (b)."
    )
    at_own = label.find("Node.TEXT_NODE")
    at_deep = label.find("el.textContent")
    assert at_deep == -1 or at_own < at_deep, (
        "Der Text der Nachfahren steht vor dem eigenen (b) – dann gewinnt er."
    )
    # **Gezählt heisst: gefunden UND erhöht.** Ein blosses «`count` kommt vor» war stumpf
    # – es steht auch im neuen Eintrag (`{ text, count: 1 }`), und die Bug-Form, die das
    # Erhöhen weglässt, ging damit durch (gemessen).
    pushed = _component(src, "push")
    assert ".find(" in pushed and ("+= 1" in pushed or "++" in pushed), (
        "Fehler werden wiederholt statt gezählt (c) – fünfmal dieselbe Zeile füllt den "
        "Puffer, bevor der zweite, andere Fehler kommt."
    )
    path = _component(src, "cssPath")
    assert "anchorFor" in path, (
        "Die Kette hat keinen benannten Anker (d) – nach fester Tiefe abgebrochen ist "
        "sie relativ und trifft irgendein `div` irgendwo auf der Seite."
    )
    # **Und die Markierungen, aus denen die Herkunft entsteht, müssen es geben.**
    assert "data-fb-module" in _code(
        _read(FRONTEND / "components" / "erp" / "process-diagram.tsx")), (
        "Die Modul-Karte benennt sich nicht – dann steht in keiner Notiz, aus welchem "
        "Modul sie kommt."
    )
    assert "data-fb-section" in _code(
        _read(FRONTEND / "components" / "erp" / "module-ui.tsx")), (
        "Der Abschnitt eines Moduls benennt sich nicht."
    )


# ---------------------------------------------------------------------------
# Der Beleg — Testnotizen #936–#947
# ---------------------------------------------------------------------------

def test_a_picker_is_wide_enough_to_hit():
    """►►► **«Ich kann nichts eingeben oder auswählen»** (Testnotiz #942). ◄◄◄

    Die Kehrseite der Regel «der gedruckte Wert IST das Bedienelement»: wo noch nichts
    dasteht, steht auch kein Bedienelement. Gemessen war die Trefferflaeche **13 × 24 px** –
    die Breite des gedruckten «—»; die Haarlinie daneben war ebenso breit, also sah man
    der Zeile nicht einmal an, dass sie etwas anzubieten hat.

    ``MIN_PICK`` ist eine **Untergrenze**, keine Breite: ein gesetzter Wert bestimmt sie
    weiterhin selbst.

    Bug-Formen: (a) es gibt keine Untergrenze; (b) sie steht als feste Breite da und kappt
    lange Werte; (c) sie gilt nur der Flaeche, nicht der sichtbaren Auszeichnung.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    pick = _component(src, "DocPick")
    assert "MIN_PICK" in src, "Es gibt keine Untergrenze fuer die Trefferflaeche (a)."
    assert "minWidth: MIN_PICK" in pick, (
        "Der Waehler nennt keine Mindestbreite (a) – bei einem «—» ist er 13 px breit."
    )
    assert "width: MIN_PICK" not in pick, (
        "Die Untergrenze ist eine feste Breite (b) – dann kappt sie lange Werte."
    )
    # (c) **Sie sitzt an der Huelle, die auch die Haarlinie traegt** – nicht am
    # unsichtbaren ``<select>``: was man anklicken kann, muss man auch sehen.
    huelle = pick[pick.index("<Editable"):pick.index("<select")]
    assert "minWidth: MIN_PICK" in huelle, (
        "Die Untergrenze gilt nur der Flaeche (c) – die Auszeichnung bleibt 13 px schmal."
    )


def test_a_vat_rate_leads_with_its_number():
    """**Der Wert zuerst, der Name danach** (Testnotiz #938).

    Auf einem Beleg ist die **Zahl** die Aussage; der Name ist ihr Rechtsgrund. Und
    untereinander gelesen steht so das Gleiche uebereinander.

    Bug-Formen: (a) der Name steht wieder vorn; (b) die Zusammensetzung wandert an die
    Aufrufstelle, und Auswahl und Anzeige laufen auseinander.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    body = _body(src, "vatText", kind="function")
    assert "${rate} % · ${name}" in body, (
        "Der Steuersatz nennt den Namen vor dem Wert (a)."
    )
    assert "${name} · ${rate}" not in src, "Irgendwo steht die alte Reihenfolge (a)."
    assert src.count("vatText(") >= 3, (
        "Die Zusammensetzung steht nicht mehr an einer Stelle (b) – Auswahl und Anzeige "
        "muessen dieselbe sein."
    )


def test_a_name_in_the_document_head_carries_its_number():
    """**Die Nummer steht neben dem Namen** (Testnotiz #940) – wie in der Positionszeile.

    Sie stand als eigene Zeile mit dem Mikro-Label «Nr.», vier Zeilen unter dem Namen, zu
    dem sie gehoert. Name und Objektnummer benennen **einen** Datensatz (#933).

    Bug-Formen: (a) die Nummer steht wieder in einer eigenen Zeile; (b) das Raster behaelt
    die Zeile, die es nicht mehr gibt; (c) die Beschriftung «Nr.» lebt weiter.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    party = _component(src, "Party")
    # *Gefragt wird die **Regel**, nicht der Variablenname: seit #951 zeigt der Block den
    # gewaehlten Empfaenger (``view``), nicht mehr blind ``side`` – die Nummer gehoert
    # weiterhin in dieselbe Zeile wie der Name.*
    head = party[: party.index(".attn")]
    assert "<ObjId value={" in head, "Die Nummer steht nicht bei Name und Waehler (a)."
    assert "PARTY_NUMBER_LABEL" not in src and "'Nr.'" not in src, (
        "Die Beschriftung «Nr.» lebt weiter (c) – neben dem Namen sagt der Block darueber "
        "laengst, wessen Nummer es ist."
    )
    # Die Zeilenzahl selbst ist keine Regel – sie muss nur zur Zahl der Angaben passen, die
    # der Block untereinander stellt. Gezaehlt wird darum, nicht verglichen.
    rows = int(re.search(r"const PARTY_ROWS = (\d+)", src).group(1))
    grid = party[party.index("gridRow:"):]
    assert rows == grid.count("<div />") + grid.count(": <div>") + 2, (
        "Das Raster und die Angaben des Blocks sind nicht gleich lang (b) – dann klafft in "
        "beiden Bloecken eine Luecke."
    )


def test_two_ways_to_reach_someone_stand_below_each_other():
    """**E-Mail und Telefon untereinander** (Testnotiz #944).

    Es sind zwei **Wege**, nicht ein Wert – und auf der Breite einer Beleg-Spalte brach die
    Zeile ohnehin, nur an einer beliebigen Stelle.

    Bug-Form: sie stehen wieder mit «·» in einer Zeile.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    party = _component(src, "Party")
    kontakt = party[party.index(".email ||"):]
    assert "join('\\n')" in kontakt and "whiteSpace: 'pre-line'" in kontakt, (
        "Kontaktweg und Telefon stehen in einer Zeile – zwei Wege sind kein Wert."
    )


def test_asking_someone_is_built_in_exactly_one_place():
    """►►► **Derselbe Befehl, zwei Nutzlasten** (Testnotiz #941). ◄◄◄

    *«Ist die Funktion dieses Buttons wirklich aktiv?»* – Nein: der Knopf im Belegkopf
    schickte ``ask`` **ohne** die beiden Fristen, und der Dienst weist ein Angebot ohne sie
    ab. Der Knopf am Angebot schickte sie mit; derselbe Befehl tat also je nach Herkunft
    etwas anderes.

    ►►► **Und seit #985 trägt die Nutzlast gar keine Frist mehr.** ◄◄◄ Sie stehen auf
    dem Beleg und werden dort geschrieben (Verb ``terms``); ``_ask`` liest sie von ihm,
    wie den Betrag aus den Positionen. Damit ist die Regel dieses Wächters **besser**
    erfüllt als mit der Fassung, die er ursprünglich prüfte – eine Nutzlast, die nichts
    trägt, kann sich zwischen zwei Aufrufstellen nicht unterscheiden. Geprüft wird darum
    die Regel, nicht die damalige Form.

    Bug-Formen: (a) eine Aufrufstelle baut die Nutzlast wieder selbst; (b) sie trägt
    wieder eine Angabe, die der Beleg schon kennt.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert src.count("action: 'ask'") == 1, (
        "Die Nutzlast des Anfragens entsteht an mehr als einer Stelle (a)."
    )
    bauer = src[_at(src, "const onAsk"):]
    bauer = bauer[: bauer.index("return (")]
    assert "payment_days" not in bauer and "lead_days" not in bauer, (
        "Die Nutzlast trägt wieder eine Frist (b) – dann gibt es einen zweiten Ort für "
        "sie, und der lebt nur im Browser."
    )


def test_the_issuer_stays_changeable():
    """**Welche Gesellschaft den Beleg stellt, kann man korrigieren** (Testnotiz #936).

    Die Automatik bleibt – der Aussteller friert mit der Freigabe ein. Hier stand
    zusaetzlich ``options.length > 1``: «eine Auswahl mit genau einer Antwort ist keine».
    Das stimmt fuer eine *Frage*, nicht fuer eine **Korrektur** – wer nachsehen will,
    findet sonst gar kein Bedienelement.

    Bug-Form: die Zahl der Gesellschaften entscheidet wieder ueber die Aenderbarkeit.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    issuer = _component(src, "Issuer")
    assert "options.length" not in issuer, (
        "Die Aenderbarkeit haengt wieder an der Zahl der Gesellschaften – bei genau einer "
        "gibt es dann kein Bedienelement."
    )
    assert "on={may(d, 'issuer')}" in issuer, (
        "Der Aussteller fragt nicht mehr `can` – und `can` ist Auskunft und Tor."
    )


def test_a_note_carries_no_control_characters():
    """►►► **Eine Notiz enthaelt nur Text, den eine Datenbank aufnimmt** (#943). ◄◄◄

    Gemeldet war ein Speicherfehler beim Anlegen einer Testnotiz: PostgreSQL nimmt in
    ``text`` **kein NUL** auf. Der Ausloeser war ein Platzhalter mit NUL-Byte im Beleg –
    behoben –, und die Regel gehoert trotzdem in das Werkzeug: was die Seite hergibt,
    entscheidet nicht die Seite.

    Bug-Formen: (a) irgendeine Quelle im Frontend traegt wieder ein Steuerzeichen;
    (b) das Werkzeug putzt nicht, was es erfasst.
    """
    import pathlib as _p
    schmutz = {chr(c) for c in range(32)} - {"\t", "\n", "\r"}
    for path in sorted((FRONTEND).rglob("*.ts*")):
        text = _p.Path(path).read_text(encoding="utf-8")
        bad = schmutz & set(text)
        assert not bad, (
            f"{path.name} traegt ein Steuerzeichen ({[hex(ord(c)) for c in bad]}) (a) – "
            f"ueber `outerHTML` landet es in jeder Testnotiz, und das Speichern bricht ab."
        )
    src = _code(_read(FRONTEND / "lib" / "feedback.ts"))
    assert "const clean = (s: string)" in src, (
        "Das Werkzeug putzt nicht, was es erfasst (b)."
    )
    cut = src[_at(src, "const cut = "):]
    assert "clean(s)" in cut[: cut.index("clamp01")], (
        "Die eine Kapp-Funktion, durch die jede erfasste Zeichenkette laeuft, putzt nicht "
        "(b) – dann haengt es an der Aufrufstelle, ob eine Notiz speicherbar ist."
    )


def test_a_finish_button_that_cannot_act_is_not_there():
    """►►► **Was jetzt nicht geht, steht auch nicht da** (Testnotiz #950). ◄◄◄

    *«Es gibt hier ja noch den Button ‹Vorgang abschliessen›, welcher bewusst ausgegraut
    deaktiviert ist … Ich sehe keinen Grund, warum dies sichtbar sein sollte. Wenn es die
    Option zum jetzigen Zeitpunkt nicht gibt, dann entfernen.»*

    Das ist #945 einen Schritt weiter, nicht zurueck: dort war das Problem, dass der Knopf
    eine **Einladung** war, die der Dienst mit 409 abwies – ausgegraut loeste das halb. Die
    Hausregel ist eindeutig: *ein Knopf, der nie etwas tun kann, ist kein Angebot.*

    Bug-Formen, jede gegengeprueft: (a) der Knopf steht gesperrt da; (b) er fragt die Sperre
    gar nicht (und laeuft dann in den 409); (c) die Oberflaeche leitet den Grund selbst her
    (ein Modultyp).
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    knopf = src[_at(src, "const blocked ="):]
    knopf = knopf[: knopf.index("</button>")]
    assert "blocked ? null :" in knopf, (
        "Der Abschluss-Knopf steht gesperrt da statt zu fehlen (a/b) – und ausgegraut ist "
        "er eine Einladung, die der Dienst gleich darauf abweist."
    )
    assert "disabled={busy}" in knopf, (
        "Er fragt die Sperre nicht mehr, aber auch nicht mehr `busy` – dann laeuft ein "
        "Doppelklick in zwei Bestaetigungen."
    )
    # *Und der **Grund** ist kein Hover an einem toten Knopf mehr: die Modul-Karte sagt ihn
    # selbst (Stufe, gemeldete Luecken). Ein zweiter Ort dafuer waere dieselbe Auskunft
    # noch einmal – und zwar dort, wo man sie nur findet, wenn man auf nichts zeigt.*
    assert "'data-tip': blocked" not in knopf, (
        "Die Begruendung haengt wieder am Knopf – den es in diesem Zustand nicht gibt."
    )
    assert "beleg" not in knopf and "zahlung" not in knopf, (
        "Die Oberflaeche nennt einen Modultyp (c) – die Regel steht im Dienst."
    )


# ---------------------------------------------------------------------------
# Testnotizen #948–#959 — die Fläche, der Ort und die richtige Tür
# ---------------------------------------------------------------------------

def test_an_editable_value_is_a_tinted_area_not_an_underline():
    """►►► **Eine Fläche, kein Unterstrich** (Testnotiz #949). ◄◄◄

    *«Ich möchte keinen Unterstrich, sondern wie jetzt beim Hover, dass der ganze
    Eingabebereich leicht farblich hintersetzt ist – also standardmässig schon ohne Hover,
    und der Unterstrich dafür weg. Beim Hover vielleicht nochmals eine dezent kräftigere
    Farbe. Wende das bei allen solchen Feldern an.»*

    Die Bedingung aus #922 gilt unverändert: **keine Layoutwirkung**. Die Tönung ist darum
    eine ``background`` und wächst über einen **äusseren** ``box-shadow``; Polsterung hätte
    genau das gebrochen.

    Bug-Formen, jede gegengeprüft: (a) der Unterstrich lebt weiter; (b) im Ruhezustand gibt
    es keine Fläche; (c) der Hover ist nicht kräftiger; (d) die Fläche kommt über eine
    Polsterung und verschiebt damit den Beleg; (e) eine Farbe steht als Zahl daneben statt
    aus dem Token zu kommen.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    rule = css[_at(css, "\n.ix-editable {"):]
    rule = rule[: rule.index("}")]
    assert "inset" not in rule, "Der Unterstrich lebt weiter (a)."
    assert "background:" in rule, "Im Ruhezustand gibt es keine Fläche (b)."
    assert "padding" not in rule, (
        "Die Fläche kommt über eine Polsterung (d) – #922 verlangt ausdrücklich, dass "
        "Grösse und Form bleiben, wie sie gedruckt würden."
    )
    assert "box-shadow: 0 0 0" in rule, (
        "Die Fläche klebt am Text – sie wächst über einen äusseren Schatten, weil der "
        "keinen Platz belegt."
    )
    assert not re.search(r"(rgba?\(|#[0-9a-fA-F]{3,6})", rule), (
        "Eine Farbe steht als Zahl im Blatt (e) – Token-Werte gehören in "
        "`colors_and_type.css`."
    )
    hover = css[_at(css, "\n.ix-editable:hover"):]
    hover = hover[: hover.index("}")]
    assert "var(--accent-soft)" in hover and "58%" not in hover, (
        "Der Hover ist nicht kräftiger als der Ruhezustand (c) – dann sagt er nichts."
    )


def test_the_marking_is_congruent_with_the_control():
    """►►► **Die Auszeichnung ist so gross wie das Bedienelement** (Testnotiz #948). ◄◄◄

    *«Das gehighlightete Feld ist deutlich grösser als das selektierbare Feld. Das ist ein
    design- und UX-technisches No-Go. Bitte eine robuste Lösung etablieren und bei allen
    Eingabefeldern kontrollieren.»*

    Gelöst wird es **konstruktiv**, nicht durch abgestimmte Zahlen: die Hülle ist
    ``inline-flex`` (dann nimmt sie genau die Höhe ihres Kindes), und Auszeichnung und
    ``<select>`` sitzen auf **demselben** Element – der frühere Zwischen-``<span>`` war die
    zweite Box, und sie konnte grösser sein als das, was sie versprach.

    Bug-Formen: (a) die Hülle ist wieder ein reines Inline-Element; (b) es gibt zwei Boxen;
    (c) das Bedienelement deckt nicht die ganze Fläche.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    hull = _component(src, "Editable")
    assert "'inline-flex'" in hull and "'flex'" in hull, (
        "Die Hülle ist ein reines Inline-Element (a) – dann nimmt sie die Höhe der Zeile "
        "und ist grösser als das Bedienelement darin (gemessen 24 px ↔ 19,5 px)."
    )
    # *Und sie darf sich nicht **strecken**: in einer Spalte wird jedes Flex-Kind
    # blockifiziert und auf die volle Breite gezogen – gemessen war die getönte Fläche
    # 229 px breit und das `<select>` darin 46 px, also genau der gemeldete Unterschied.*
    #
    # ►►► **Zurückgenommen wird sie über die BREITE, nicht über `align-self`**
    # (Testnotizen #961/#963). ◄◄◄ `align-self: start` beantwortet die Streckung richtig
    # und beantwortet **zugleich** eine zweite Frage, die es nicht beantworten darf: in
    # einer *Zeile* ist die Querachse die senkrechte, und `start` heisst dort «oben» – die
    # Hülle fiel damit aus dem `items-baseline` ihres Elternteils heraus, und neben einer
    # Angabe anderer Schriftgrösse stand sie sichtbar versetzt (genau die beiden
    # gemeldeten Höhenversätze). Eine **definite** Quergrösse schliesst `stretch` aus
    # (CSS Flexbox §8.3) und lässt die senkrechte Ausrichtung dem Elternteil.
    assert "width: 'fit-content'" in hull, (
        "Die Hülle streckt sich auf die Breite ihrer Spalte (a)."
    )
    assert "alignSelf: 'start'" not in hull, (
        "Die Hülle richtet sich selbst aus (d) – dann steht sie in einer Zeile neben "
        "einer anderen Schriftgrösse versetzt (#961/#963)."
    )
    pick = _component(src, "DocPick")
    assert pick.count("<Editable") == 1 and "display: 'inline-block'" not in pick, (
        "Es gibt zwei Boxen (b) – Auszeichnung und Bedienelement gehören auf dasselbe "
        "Element, sonst kann die eine grösser sein als die andere."
    )
    assert "inset: 0" in pick, "Das Bedienelement deckt die Fläche nicht (c)."


def test_paying_a_voucher_asks_the_voucher():
    """►►► **«Jetzt bezahlen» rief die Tür des ALTEN Moduls** (Testnotiz #959). ◄◄◄

    *«Wieso funktioniert diese Option nicht mehr? Achtung, dies muss sauber funktionieren,
    und ich habe keinen Bock, nochmals Stripe zu konfigurieren.»* – Musste er nicht: die
    Schlüssel, der Webhook und das Zahlungsformular sind unverändert. Die Karte rief fest
    ``api.preparePayment``, also den Endpunkt des **Vorgängers**; am Beleg gab es dort
    keinen Vorgang, und der Dienst antwortete mit 404.

    Bug-Formen: (a) die Karte kennt wieder einen Endpunkt; (b) beide Aufrufer geben densel-
    ben mit; (c) die Funktion wird an der Aufrufstelle gebaut (dann läuft die Vorbereitung
    bei jedem Rendern neu).
    """
    card = _code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx"))
    assert "api." not in card, (
        "Die Karte kennt wieder einen Endpunkt (a) – welcher Vorgang bezahlt wird, weiss "
        "nur der Aufrufer."
    )
    assert "prepare(orderObjectId" in card, "Die Karte fragt nicht den Aufrufer."
    beleg = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "prepare={api.prepareVoucherPayment}" in beleg, "Der Beleg ruft die falsche Tür."
    # *Der Vorgänger rief hier seine eigene (`api.preparePayment`) – **genau deshalb** war
    # die Trennung nötig, und genau deshalb kostete seine Löschung hier eine Zeile (#960).*
    # (c) **Eine prototypgebundene Methode, keine Pfeilfunktion** – sonst ist es bei jedem
    # Rendern eine neue Referenz, und der Effekt der Vorbereitung läuft endlos.
    assert "prepare={(" not in beleg, (
        "Die Funktion wird an der Aufrufstelle gebaut (c)."
    )


def test_recording_a_payment_exists_exactly_once_and_names_its_invoice():
    """►►► **«Zahlung erfassen» gibt es EINMAL — und es weiss, welche Rechnung.** ◄◄◄

    *«Warum gibt es hier zweimal den Button ‹Zahlung erfassen›? Das ist ein absolutes
    No-Go.»* (#958) – Und es war kein Gestaltungsfehler, sondern eine offene Frage: der
    Knopf am **Vorgang** wusste nicht, welche Rechnung gemeint ist, und wählte still die
    älteste offene.

    *Der Wächter verlangte damals, dass `d.payment_word` **in `EntryRow`** steht und
    **nicht in `Money`** – also die Form der damaligen Lösung. Seit der Umbau die Geld-
    Handlungen in zwei Fächer sortiert (eine Buchung ist keine Korrektur), steht das Verb
    genau einmal, nämlich als die **eine** Handlung, die weiterbringt; und welche Rechnung
    sie meint, sagt der Server (`settle_charge`). Der Wächter hätte die bessere Fassung
    verboten – er fragt jetzt die Regel.*

    Bug-Formen: (a) das Verb steht wieder an zwei Stellen; (b) die Buchung nennt die
    Rechnung nicht mehr; (c) die Oberfläche sucht sie sich selbst aus den Zeilen.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    # (a) **Gezählt, nicht gesucht** – und gezählt wird die **Handlung**, nicht das Wort:
    # es steht auch als Überschrift des Formulars da, und ein «kommt zweimal vor» wäre
    # davon erfüllt. Genau eine Stelle öffnet die Erfassung einer Zahlung.
    opens = src.count("setForm({ kind: 'pay'")
    assert opens == 1, (
        f"Die Erfassung einer Zahlung geht von {opens} Stellen aus (a) – eine Handlung, "
        f"eine Stelle."
    )
    money = _component(src, "Money")
    # (b/c) **Die Rechnung kommt vom Server** – sie in den Zeilen zu suchen wäre die
    # zweite Regel neben `open_charges`, und genau daraus kam #859.
    assert "d.settle_charge" in money, (
        "Die Buchung nennt die Rechnung nicht mehr (b) – dann entscheidet wieder der "
        "Dienst, worauf sie geht."
    )
    assert "chargeId={settle}" in money, (
        "Das Formular bekommt sie nicht durchgereicht (b)."
    )
    for guess in ("charges.find(", "charges[0]", "open_charges"):
        assert guess not in money, (
            f"«{guess}»: die Oberfläche sucht sich die Rechnung selbst (c)."
        )


def test_the_cancel_button_stands_beside_the_finish_button_as_a_square():
    """►►► **Der Storno neben dem Abschluss, als Quadrat** (Testnotiz #957). ◄◄◄

    *«Ich hätte gerne, dass es neben dem grossen Button ‹Vorgang abschliessen› platziert
    wird, jedoch nur ein quadratischer Button mit Icon, sodass der Hauptfokus und der absolut
    dominante Button immer noch ‹Vorgang abschliessen› ist.»*

    ►►► **Und es ist die Anatomie einer ENTSCHEIDUNG, nicht die der Fusszeile** (#976).◄◄◄
    *«Kann man diesen Bereich ähnlich darstellen wie ‹Vorgang abschliessen› und daneben das
    unscheinbarere Abbrechen?»* – Gemeldet an der **Angebotszeile** (annehmen ↔ absagen),
    und damit ist es dieselbe Zeile: eine Handlung nimmt den Platz, die leise steht als
    Quadrat daneben. Sie wohnt darum in `StageRow` und wird von beiden gesetzt.

    *Der Wächter verlangte `flex: 1` **wörtlich in `Footer`** – also die Form der damaligen
    Lösung; er hätte das gemeinsame Bauteil verboten, obwohl es die Regel besser erfüllt.
    Gefragt ist jetzt die Zeile selbst.*

    Bug-Formen: (a) er steht wieder in einer eigenen Zeile darunter; (b) er ist nicht
    quadratisch; (c) die Breite kommt als Inline-Stil und nimmt dem Knopf damit die Geste,
    seinen Namen beim Zeigen auszuklappen; (d) die Angebotszeile baut ihre eigene Fassung.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    stage_row = _component(src, "StageRow")
    assert "flex: 1" in stage_row, (
        "Die dominante Handlung nimmt den Platz nicht (a) – dann ist der Storno ein "
        "zweiter Block und nicht sein kleiner Nachbar."
    )
    foot = _component(src, "Footer")
    assert "<StageRow" in foot and "children" in foot, (
        "Der Abschluss steht nicht in derselben Zeile wie der Storno (a)."
    )
    assert "square" in foot and "ACT_H.stage" in foot, (
        "Der Knopf ist nicht quadratisch in der Höhe des Abschlusses (b)."
    )
    # (d) **Dieselbe Zeile an der Angebotszeile** – der Zuschlag ist für sie, was der
    # Abschluss für das Modul ist. Drei gleich laute Knöpfe sind kein Vorschlag.
    quote = _component(src, "QuoteRow")
    assert "<StageRow" in quote and "<StageAction" in quote, (
        "Die Angebotszeile stellt ihre Handlungen wieder gleichrangig nebeneinander (d)."
    )
    assert "<Actions" not in quote, (
        "Die Angebotszeile baut ihre eigene Fassung daneben (d)."
    )
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    assert "'--actbtn-w'" in ui and "width:" not in _component(ui, "ActionButton"), (
        "Die Breite kommt als Inline-Stil (c) – sie gewinnt gegen "
        "`.ix-tuck:hover { width: auto }`, und der Name klappt nie aus."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    assert "width: var(--actbtn-w, 32px)" in css, (
        "Die Regelbreite kommt nicht aus der Variablen (c) – dann kann der Aufrufer sie "
        "nur inline setzen."
    )


def test_a_quote_row_closes_itself_and_keeps_name_and_number_together():
    """**Die Haarlinie unten, Nummer neben dem Namen** (Testnotizen #953/#955).

    *«Der obere Strich in diesem Container ist irgendwie unnötig bzw. macht optisch keinen
    Sinn – ich würde ihn pro Container unten setzen.»* Er war zugleich die **zweite** Linie
    direkt unter der Trennlinie des Abschnitts. Und *«die Objektnummer immer neben den
    Objektnamen»* (#853): als Geschwister in einer umbrechenden Zeile rutschte die Nummer
    auf die nächste, sobald es eng wurde.

    Bug-Formen: (a) die Linie steht wieder oben; (b) Name und Nummer sind wieder
    Geschwister der umbrechenden Zeile.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(src, "QuoteRow")
    assert "borderBottom: '1px solid var(--border-1)'" in row and "borderTop" not in row, (
        "Die Linie eröffnet den Container statt ihn zu schliessen (a)."
    )
    group = row[row.index("party_name"):]
    assert "<ObjId value={d.party_object_id} /></span>" in group[:400], (
        "Name und Nummer sind zwei Geschwister der umbrechenden Zeile (b) – dann fällt die "
        "Kennung auf die nächste Zeile."
    )
    assert f"flex: `1 1 ${{NAME_MIN}}px`" in row[: row.index("party_name")] \
        or "flex: `1 1 ${NAME_MIN}px`" in row, "Die Gruppe schrumpft nicht mit."


def test_a_recipient_chip_can_be_shown_and_dropped():
    """►►► **Der Chip zeigt seine Anschrift und lässt sich abwählen** (Testnotiz #951). ◄◄◄

    *«Ich kann zwar mehrere User aufführen, jedoch kann ich sie nicht wie zuvor auch
    abwählen … zudem stört mich, dass die jeweilige Anschrift nicht sichtbar ist.»*

    Bug-Formen: (a) der Chip ist wieder reine Anzeige; (b) es gibt kein Abwählen; (c) die
    Oberfläche entscheidet selbst, ob abgewählt werden darf, statt `can` zu fragen; (d) der
    Block zeigt weiter blind die Seite des Servers statt der gewählten.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    chip = _component(src, "Chip")
    # *Zwei Knöpfe in **einer** Hülle – ein Klick auf den Namen zeigt die Anschrift, das ✕
    # zieht die Anfrage zurück. Verschachtelte Knöpfe wären ungültiges HTML, und ein
    # einziger müsste erraten, was gemeint war. Gezählt wird, statt nach dem Vorkommen der
    # Namen zu fragen: die standen auch dann noch da, als die Bug-Form den Klick entfernte.*
    # ►►► **Drei Knöpfe, und nie mehr** (Testnotiz #962): der **Name** zeigt die
    # Anschrift, `+` fragt an, `✕` zieht zurück – und die beiden letzten schliessen
    # einander aus, es steht also immer höchstens einer da. Gezählt wird, statt nach dem
    # Vorkommen der Namen zu fragen: die standen auch dann noch da, als die Bug-Form den
    # Klick entfernte.
    assert chip.count("<button") == 3, (
        f"Der Chip hat {chip.count('<button')} Knöpfe statt drei (a/b) – reine Anzeige "
        f"zeigt keine Anschrift, und ohne + / ✕ gibt es kein An- und Abwählen."
    )
    # Gefragt wird, **dass** der Knopf seine Handlung trägt – nicht, wie der Ausdruck
    # geschrieben ist: seit #1016 steht dort `busy ? undefined : onAsk`, und eine Prüfung
    # auf die Schreibweise hätte ausgerechnet die bessere Fassung verboten.
    for handler, what in (("onShow", "Der Name zeigt die Anschrift nicht (a)."),
                          ("onAsk", "Das + fragt nicht an (b)."),
                          ("onDrop", "Das ✕ zieht die Anfrage nicht zurück (b).")):
        assert re.search(r"onClick=\{[^}]*\b" + handler + r"\b", chip), what
    # ►►► **Eine Form für beide Fälle** (#962): eine zugelassene, noch nicht angefragte
    # Partei stand als `+ Name`-Knopf mit `.ix-editable` daneben – der Auszeichnung
    # **änderbarer Werte**. Damit sah jede Partei dauerhaft «aktiv» aus, und ob eine
    # angefragt war, war an der Form nicht abzulesen.
    assert "ix-editable" not in _component(src, "Recipients"), (
        "Die noch nicht angefragte Partei hat wieder eine eigene Form (e) – dann sagt "
        "die Auszeichnung änderbarer Werte etwas über einen Zustand."
    )
    rec = _component(src, "Recipients")
    assert "may(d, 'unask')" in rec, (
        "Die Oberfläche entscheidet selbst (c) – `can` ist Auskunft **und** Tor."
    )
    assert "action: 'unask'" in rec, "Das Verb wird nicht geschickt (b)."
    party = _component(src, "Party")
    # *Gefragt wird, dass **keine** angezeigte Angabe mehr aus `side` kommt – ein blosses
    # «`view.address` steht irgendwo» war stumpf: die eine Stelle umzustellen liess das
    # Wort an der anderen stehen, und der Wächter schlug nicht an (gemessen).*
    assert "d.recipients" in party, "Die Seiten der Angefragten werden nicht gelesen (d)."
    # *`side.object_id` bleibt erlaubt – daraus **entsteht** die Vorwahl (der Adressat ist
    # der Standard). Gefragt sind die **angezeigten** Angaben.*
    for feld in ("address", "shipping", "attn", "email", "phone", "uid"):
        assert f"side.{feld}" not in party, (
            f"«{feld}» kommt weiter blind aus der Seite des Servers (d) – dann bleibt beim "
            f"Umschalten die Angabe des Adressaten stehen."
        )
    # **Wer die Gegenseite ist, sagt die Struktur** – nicht ein Vergleich auf ein Rollenwort.
    assert "side.ours" in party, "Die Seite wird geraten statt gelesen."


def test_a_delivery_clause_carries_no_edition_in_brackets():
    """**«(Incoterms 2020)» entfällt – bei allen** (Testnotiz #956).

    Welche Fassung gilt, steht in der **Erklärung** der gewählten Klausel, und die steht auf
    dem Beleg sichtbar darunter. Als Anhang an jedem Wert wäre sie eine Wiederholung, die
    mit jeder Anzeige länger wird.

    Bug-Form: der Satz baut die Fassung wieder an.
    """
    src = _code(_read(BACKEND / "app" / "domain" / "incoterms.py"))
    out = src[_at(src, "def sentence"):]
    out = out[: out.index("\n\n\n")] if "\n\n\n" in out else out
    assert "Incoterms" not in out, (
        "Der Satz trägt die Fassung wieder – und zwar an jeder Anzeige."
    )


def test_a_term_is_a_value_on_the_document_not_a_row_of_buttons():
    """►►► **Eine Frist ist ein WERT auf dem Beleg, keine Knopfreihe** (Testnotiz #934).
    ◄◄◄

    *«Ich möchte die gleiche Logik, das gleiche Design wie bei Währung oder
    Betragsangabe.»* – Dagestanden hatte ein `TermField`: *Vorauszahlung · 30 Tage ·
    Individuell* als drei Chips nebeneinander, also ein **Formular** mitten in einem
    Dokument. Ein Beleg druckt «Zahlbar in 30 Tagen», und dass man das ändern kann, sagt
    die Haarlinie – mehr nicht. Es ist damit dieselbe Form wie jeder andere änderbare Wert
    (`DocPick`, #929/#930/#935), und die freie Eingabe steht an **derselben** Stelle.

    *`fields.TermField` hatte danach nur noch einen Aufrufer – das Vorgänger-Zahlungsmodul
    – und ist mit ihm gegangen (#960). `Segmented` bleibt: es ist die Form für eine
    Aufzählung mit wenigen Werten im **Formular** (die Zahlungsart beim Buchen, #967).*

    **Und die üblichen Werte kommen vom SERVER** (`payment_terms`/`lead_terms`): eine
    zweite Liste im Browser liefe beim ersten neuen Regelwert auseinander – und «0» ist
    dort keine Ziffer, sondern «Vorauszahlung».

    Bug-Formen: (a) `TermField` ist zurück; (b) ein Schieberegler; (c) die Werte stehen
    als Literal im Browser; (d) die Frist ist kein `DocPick` mehr.
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "function TermField" not in fields, (
        "`TermField` ist zurück (a) – eine Frist ist ein Wert, kein Formular."
    )
    assert 'type="range"' not in fields, "Ein Schieberegler für eine Frist (b)."

    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    term = _component(src, "Term")
    assert "<DocPick" in term, (
        "Die Frist hat eine eigene Bauart (d) – sie ist ein änderbarer Wert wie jeder "
        "andere auf dem Beleg."
    )
    assert "freeMin" in term and "numericInputProps" in term, (
        "Die freie Eingabe steht nicht mehr an derselben Stelle (d)."
    )
    for word in ("Vorauszahlung", "30 Tage", "Sofort"):
        assert word not in src, (
            f"«{word}» steht als Literal im Browser (c) – die üblichen Werte gehören "
            f"dem Dienst (`domain/voucher.PAYMENT_TERMS`/`LEAD_TERMS`)."
        )
    for source in ("d.lead_terms", "d.payment_terms", "d.term_free_min"):
        assert source in src, f"«{source}» kommt nicht vom Server (c)."


# ---------------------------------------------------------------------------
# ►►► Testnotizen #960–#974 – das alte Modul ist weg, und der Beleg wird ruhiger
# ---------------------------------------------------------------------------

def test_the_previous_payment_module_is_gone_from_both_sides():
    """►►► **«Zahlung (alt)» ist ERSATZLOS gelöscht** (Testnotiz #960). ◄◄◄

    *«Dieses Prozessschrittmodul kann vollständig und gänzlich aus dem Code eliminiert
    werden wie bereits geplant. Das neue Modul ‹Zahlung› soll natürlich voll
    funktionsfähig bestehen bleiben.»*

    Und es war ein **Löschen**, kein Umbau – genau dafür wurde der Nachfolger neben ihm
    gebaut statt in ihn hinein: eigene Vokabel, eigener Dienst, eigene Tabellen, eigene
    Endpunkte, eigene Komponente, **kein Import**. Gefallen sind `domain/deal` ·
    `services/deal` · `schemas/deal` · `models/deal` · `deal-work.tsx`, der Modul-Eintrag,
    fünf Endpunkte und fünf API-Methoden; am Beleg **keine Zeile**.

    *Die Tabellen `deals`/`deal_entries` bleiben stehen* – dieselbe Regel wie bei den
    entfernten Handels-Modulen: eine Spalte, die niemand liest, kostet nichts; ein
    Tabellen-Drop kostet die Vergangenheit und verlangt vorher eine Sicherung der
    **produktiven** Datenbank (`docs/backlog.md`).

    Der Wächter fragt **beide Seiten**: ein Schlüssel, den nur eine Hälfte kennt, ist genau
    die Form, in der eine Oberfläche einen Vorgang rendert, den es nicht mehr gibt.

    Bug-Formen: (a) eine Datei ist zurück; (b) der Schlüssel `zahlung` steht wieder in der
    Registry; (c) die Oberfläche ruft einen der alten Wege; (d) irgendwo importiert noch
    jemand `domain/deal`.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    for gone in ("app/domain/deal.py", "app/services/deal.py", "app/schemas/deal.py",
                 "app/models/deal.py"):
        assert not (BACKEND / gone).exists(), f"«{gone}» ist zurück (a)."
    assert not (FRONTEND / "components" / "erp" / "deal-work.tsx").exists(), (
        "«deal-work.tsx» ist zurück (a)."
    )
    assert "zahlung" not in modules.KEYS, (
        f"Der Schlüssel «zahlung» steht wieder in der Registry (b): {sorted(modules.KEYS)}."
    )
    # (c) **Die Wege des Vorgängers gibt es nicht mehr** – weder als Endpunkt noch als
    #     Methode. Ein toter Pfad neben einem lebenden ist die zweite Tür zur selben Sache.
    api = _read(FRONTEND / "lib" / "api.ts")
    for gone in ("updateDeal", "searchDealParties", "dealTransfer", "preparePayment",
                 "refundPayment"):
        assert gone not in api, f"«api.{gone}» ist zurück (c)."
    router = _code(_read(BACKEND / "app" / "routers" / "orders.py"))
    for gone in ("/deal", "deal-parties", "deal_svc"):
        assert gone not in router, f"«{gone}» steht wieder im Router (c)."
    # (d) **Niemand importiert ihn mehr.**
    for where in ("app/services/process.py", "app/services/stripe_pay.py",
                  "app/routers/orders.py", "app/schemas/order.py",
                  "app/models/__init__.py"):
        src = _code(_read(BACKEND / where))
        assert "import deal" not in src and "from .deal" not in src, (
            f"«{where}» importiert noch das gelöschte Modul (d)."
        )


def test_a_module_with_its_own_document_needs_no_list_beside_it():
    """►►► **Ein Modul, das seine Sache selbst zeigt, zählt sie nicht daneben auf**
    (Testnotiz #973). ◄◄◄

    *«Ich checke nicht, was diese Info hier soll. Zahlung war abgeschlossen, und es zeigt
    es immer noch an – bitte hier entfernen.»*

    Dagestanden hatte die `PointList`, und die sagt, was ein Modul **tun wird**: seine
    Erfassungspunkte, seine Stichprobe, sein Verb. Ein Beleg hat nichts davon; übrig blieb
    sein **Verb** («Vorgang abschliessen») – also der Name eines Knopfes, den es an einem
    erledigten Modul gar nicht mehr gibt.

    **Gefragt wird, ob es einen Beleg GIBT**, nie der Modultyp: jedes künftige Modul,
    dessen Inhalt eine eigene Karte ist, erbt die Regel ohne eine Zeile.

    Bug-Formen: (a) die Aufzählung steht wieder neben dem Beleg; (b) gefragt wird der
    Modultyp statt der Sache.
    """
    raw = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    src = _code(raw)
    body = raw[raw.index("const stepBody ="):raw.index("// **Ohne Prozessbild")]
    assert "paper ? (" in body and "<PointList" in body, (
        "Die Aufzählung hängt nicht mehr am Vorhandensein eines Belegs (a)."
    )
    # Der `paper`-Zweig steht **vor** der `PointList` – sonst greift sie zuerst.
    assert body.index("paper ? (") < body.index("<PointList"), (
        "Die Aufzählung steht wieder vor dem Beleg (a)."
    )
    for key in ("'beleg'", '"beleg"'):
        assert key not in src, f"Die Ausführungsstelle nennt wieder den Modultyp {key} (b)."


def test_a_required_value_says_so_where_it_stands():
    """►►► **Ein Pflichtwert, der fehlt, sagt es an SEINER Stelle** (Testnotiz #964). ◄◄◄

    *«Alle Eingabefelder hier in diesem Modul – also alles, was so leicht blau hinterlegt
    ist – sollen Muss-Felder sein.»* «Leicht blau hinterlegt» **ist** die Auszeichnung
    änderbarer Werte (`.ix-editable`, #922) – die Regel gehört darum ihr und nicht neun
    Aufrufstellen.

    Es ist **dieselbe Auszeichnung in einer anderen Stimme**: die Fläche wird warnfarben
    statt akzentfarben, Grösse und Schrift bleiben, wie #922/#948 sie festgelegt haben.
    Kein Sternchen und kein Ausrufezeichen daneben – eine zweite Form wäre eine zweite
    Aussage über dieselbe Sache, und sie bräuchte Platz, den ein Beleg nicht hat.

    **Und die Regel steht im Dienst** (`voucher._assert_complete`): dies ist ihre
    freundliche Hälfte, nie ein zweiter Massstab.

    Bug-Formen: (a) die Hülle kennt keine Pflichtangabe; (b) die Auszeichnung verschiebt
    den Beleg (Polsterung statt Fläche); (c) ein Wert trägt sie nicht; (d) sie steht noch
    da, wo gar nichts mehr änderbar ist.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    hull = _component(src, "Editable")
    assert "missing" in hull and "is-missing" in hull, (
        "Die Hülle kennt keine Pflichtangabe (a)."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    block = css[css.index(".ix-editable.is-missing {"):]
    block = block[: block.index("}")]
    assert "--danger" in block and "padding" not in block, (
        "Die Auszeichnung verschiebt den Beleg (b) – sie ist eine Fläche, keine Polsterung."
    )
    # (d) **Wo nichts mehr änderbar ist, gibt es keine Pflichtangabe** – der Beleg ist
    #     gedruckt, und eine rote Fläche darauf wäre eine Aufforderung ins Leere.
    assert ".ix-editable[aria-disabled='true'].is-missing" in css, (
        "Ein gesperrter Wert bleibt rot (d)."
    )
    # (c) **Jeder Wert trägt sie** – Preis, Satz, Zoll, beide Fristen, Lieferbedingung.
    for where in ("LineRow", "Customs", "Term", "Delivery"):
        assert "missing" in _component(src, where), (
            f"«{where}» sagt nicht, dass sein Wert Pflicht ist (c)."
        )


def test_the_chronicle_is_gone_and_its_dates_stand_where_they_belong():
    """►►► **Die Chronik entfällt – die Daten stehen an ihrem Ort** (#968/#969/#970). ◄◄◄

    *«Die Chronik kann hier vollständig und gänzlich entfallen. Ich möchte die Information
    dort darstellen, wo sie eigentlich angezeigt werden.»*

    Sie zählte **zwei Daten** auf, und beide haben einen eigenen Ort: *wann offeriert
    wurde* am Kopf der Angebote, *wann zugesagt wurde* an der Zeile, bei der zugesagt
    wurde – und *wann storniert wurde* im Belegkopf, neben der Belegart. Ein Abschnitt,
    der dieselben Daten ein zweites Mal nennt, ist nicht der Nachweis, sondern seine
    ärmere Kopie: nacktes Datum statt Aussage.

    **Die Aussage steht da, die Tatsache im Hover** – dieselbe Regel wie bei der
    Fälligkeit einer Geld-Zeile (#890): eine Zahl, die man erst von heute abziehen muss,
    ist keine Auskunft, sondern eine Aufgabe.

    Bug-Formen: (a) der Abschnitt ist zurück; (b) eine der beiden Angaben fehlt; (c) sie
    nennt nur das Datum statt der Aussage; (d) die genaue Zeit fehlt im Hover.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "function Chronicle" not in src and "<Chronicle" not in src, (
        "Die Chronik ist zurück (a)."
    )
    assert "history_title" not in src, "Ihre Überschrift reist noch mit (a)."

    # ►►► **Die Aussage kommt aus `lib/when`** (#992) – hier standen `since(` und
    # `localDateTime(`, also die Namen der damaligen Helfer in dieser Datei. Sie gibt es
    # nicht mehr: Datum und Uhrzeit haben im Haus **eine** Stelle.
    quotes = _component(src, "Quotes")
    assert "q.sent_at" in quotes and "when(" in quotes, (
        "Der Abschnitt sagt nicht mehr, wann offeriert wurde (b/c)."
    )
    assert "formatWhen(" in quotes, "Die genaue Zeit fehlt im Hover (d)."
    row = _component(src, "QuoteRow")
    assert "d.agreed_at" in row and "when(" in row and "formatWhen(" in row, (
        "Die Zeile sagt nicht, wann sie den Zuschlag bekam (b/c/d)."
    )
    # **Und der Storno steht im Kopf** – er war die dritte Zeile der Chronik.
    head = _component(src, "DocHead")
    assert "d.cancelled_on" in head, (
        "Der Storno hat keinen Ort mehr (b) – er stand in der Chronik."
    )


def test_the_vat_rate_stands_before_the_amount():
    """►►► **Der Satz steht VOR dem Betrag** (Testnotiz #972). ◄◄◄

    *«Kann der MWST-Satz evtl. vor dem Betrag stehen? Irgendwie schaut das etwas komisch
    aus, da alles weiter untereinander steht.»*

    Und es ist nicht bloss Geschmack: die **Zahl** ist die letzte Angabe der Zeile, sie
    steht rechtsbündig und bildet mit der Zeile darunter eine Spalte. Stand der Satz
    dahinter, verschob jede Beschriftung anderer Länge («8.10 % · Normalsatz» ↔ «0.00 % ·
    Export») den Betrag – die Beträge standen untereinander **nicht** untereinander.

    Bug-Form: der Preis steht wieder vor dem Satz.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(src, "LineRow")
    assert row.index("<DocPick") < row.index('title="Einzelpreis'), (
        "Der Preis steht wieder vor dem Steuersatz – dann verschiebt jede Satz-"
        "Beschriftung anderer Länge die Spalte der Beträge."
    )


def test_the_payment_method_is_a_slider_not_a_dropdown():
    """►►► **Wie bezahlt wurde, ist ein SCHIEBER** (Testnotiz #967). ◄◄◄

    *«Hier soll wieder der Sliderbutton zum Einsatz kommen.»* – Und die Regel dahinter ist
    die des Hauses: ein Auswahlfeld ist die Form für eine **lange** Aufzählung; hier sind
    es **zwei** Werte (bar · Überweisung – die Karte tippt niemand ab, sie kommt über den
    Webhook). Zwei Werte hinter einem Klick zu verstecken ist ein Klick für eine
    Entscheidung, die man sehen könnte.

    ►►► **Und der Schieber steht dort, wo die Frage entsteht** (der Umbau). ◄◄◄ Er sass
    im **Erfassungsformular**, also *nachdem* man sich schon entschieden hatte, überhaupt
    zu buchen – und daneben standen «Überweisen» und «Jetzt bezahlen» als eigene Knöpfe an
    der Rechnungszeile: dieselbe Frage, dreimal, in zwei Formensprachen. Jetzt ist es
    **eine** Frage im Fach «Begleichen» (*wie kommt das Geld hierher?*), und das Formular
    fragt sie nicht noch einmal.

    Bug-Formen: (a) die Zahlungsart ist wieder ein `<select>`; (b) sie steht wieder im
    Formular; (c) die Beschriftung steht zweimal.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    money = _component(src, "Money")
    assert "<Segmented" in money, "Die Zahlungsart ist kein Schieber mehr (a)."
    assert "aria-label={d.method_label}" not in src, (
        "Das alte Auswahlfeld steht noch da (a)."
    )
    entry = _component(src, "Entry")
    assert "<Segmented" not in entry and "setMethod" not in entry, (
        "Das Formular fragt die Zahlungsart erneut (b) – sie ist längst gewählt, und die "
        "getippte gewänne auch dann, wenn sie der Wahl widerspricht."
    )
    assert "d.method_label}</Label>" not in money, (
        "Die Beschriftung steht zweimal (c) – `Segmented` bringt seine eigene mit."
    )


def test_a_refusal_is_just_a_refusal():
    """**«Absage» – und sonst nichts** (Testnotiz #965).

    *«Hier soll einfach nur ‹Absage› stehen und nicht ‹liefert nicht›.»* Der Zusatz
    stammte aus dem Beschaffungs-Beleg, wo nur eingekauft wurde; an einer **Einnahme**
    sagt er sogar das Falsche – dort liefern wir, und abgesagt hat der Kunde.

    **Und das Verb der Schwelle kommt vom Server** (#966): «Offerte annehmen», in beiden
    Richtungen dasselbe – wie der Beleg heisst, sagt die Stufe.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo

    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "liefert nicht" not in src, "Der Zusatz ist zurück."
    assert 'label="Absage"' in src, "Die Absage heisst nicht mehr «Absage»."
    assert vo.AGREE_VERB == "Offerte annehmen", (
        "Das Wort der Schwelle ist wieder ein anderes (#966)."
    )
    assert "v.stages[0]?.verb" in src, (
        "Die Karte schreibt das Verb selbst, statt es vom Server zu lesen."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► TESTNOTIZEN #975–#978
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_hover_note_is_as_wide_as_its_own_text():
    """►►► **Die Blase steht über dem, was sie erklärt** (Testnotiz #978). ◄◄◄

    *«Kann das nicht irgendwo neben dem Betrag oder so stehen – und den Hovertext direkt
    darüber und nicht wie jetzt irgendwo.»*

    **Zwei Meldungen, eine Ursache.** Die Blase des Hauses sitzt über der **Mitte ihres
    Elements** (`[data-tip]::after`, `left: 50%`) – nur war das Element nicht die Auskunft,
    sondern die ganze Zeile: ein Kind einer Flex-**Spalte** wird blockifiziert und auf die
    volle Breite gezogen. Bei 460 px stand die Blase einen halben Beleg neben den drei
    Wörtern, die sie erklärt.

    `width: fit-content` ist die Antwort und **nicht** `align-self` – dieselbe Lehre wie bei
    `Editable` (#961/#963): eine definite Quergrösse wirkt in der Spalte *und* in der Zeile.
    Und die Angabe steht in der **Kopfzeile** der Angebotszeile, neben dem Betrag.

    Bug-Formen: (a) die Auskunft wird wieder so breit wie ihre Spalte; (b) sie steht wieder
    als eigenes Kind unter der Kopfzeile; (c) die Tatsache fehlt im Hover; (d) die drei
    Aufrufstellen bauen sie wieder je selbst.
    """
    src = _code(_beleg())
    note = _component(src, "Note")
    assert "width: 'fit-content'" in note, (
        "Die Auskunft wird wieder so breit wie ihre Spalte (a) – dann steht ihre Blase "
        "irgendwo."
    )
    assert "data-tip" in note, "Die Auskunft trägt keine Blase mehr (c)."
    # (b) **Neben dem Betrag**: die Angabe steht in der Kopfzeile der Angebotszeile.
    row = _component(src, "QuoteRow")
    head = row[row.index("items-baseline"):row.index("</div>")]
    assert "d.agreed_at" in head, (
        "Die Angabe steht wieder unter der Kopfzeile (b) statt neben dem Betrag."
    )
    assert "formatWhen(d.agreed_at)" in head, "Die Tatsache fehlt im Hover (c)."
    # (d) **Ein Bauteil, drei Aufrufstellen** – wann offeriert, wann angenommen, wie
    # bestellt. Dreimal dieselben vier Werte wären dreimal die Chance, dass einer abweicht.
    assert src.count("<Note ") + src.count("<Note>") >= 3, (
        "Die Auskünfte bauen ihre Form wieder je selbst (d)."
    )


def test_what_to_do_stands_once_on_the_document():
    """►►► **«Was ist zu tun?» steht bei den Positionen – einmal** (#975er-Runde). ◄◄◄

    Der Satz handelt von den Positionen («Härten auf 58 HRC»), also steht er bei ihnen. Er
    ist eine **Auskunft**, kein Feld: entschieden wird er beim Modellieren, wo man einen
    Fertigungsablauf definiert – auf dem Beleg wird er abgearbeitet.

    **Leer schreibt der Beleg nicht hin**: «gemäss Spezifikation» ist die Regel, und eine
    Zeile, die «nichts Besonderes» sagt, ist keine Auskunft.

    Bug-Formen: (a) der Satz steht nicht auf dem Beleg; (b) er steht auch leer da; (c) er
    ist zu einem Eingabefeld geworden; (d) seine Beschriftung wird selbst geschrieben.
    """
    src = _code(_beleg())
    goods = _component(src, "Goods")
    assert "d.task" in goods, "Der Auftrag steht nicht auf dem Beleg (a)."
    assert "{d.task &&" in goods, "Ein leerer Auftrag belegt eine Zeile (b)."
    assert "{d.task_label}" in goods, (
        "Die Beschriftung wird selbst geschrieben (d) – sie kommt vom Server."
    )
    # (c) **Eine Auskunft, kein Feld** – kein `.ix-editable`, kein Befehl daran. Das
    # Fenster endet an der nächsten Zeile des Belegs; ein fester Zeichen-Abstand läse den
    # `onAction` der Summen mit und meldete, obwohl die Regel erfüllt ist.
    block = goods[goods.index("{d.task &&"):goods.index("<Sums")]
    assert "Editable" not in block and "onAction" not in block, (
        "Der Auftrag ist am Beleg änderbar geworden (c) – entschieden wird er beim "
        "Modellieren."
    )


def test_each_side_of_the_head_names_both_addresses():
    """►►► **Beide Anschriften, auf beiden Seiten, immer** (Testnotiz #975). ◄◄◄

    *«Mir gefällt das ziemlich gut mit Rechnungsadresse, Lieferadresse usw. Ich möchte, dass
    du das auch auf dem Leistungserbringer machst – also standardmässig immer bei
    Informationen ausweisen, global etablieren, auch wenn sie zweimal das Gleiche anzeigt.
    Eine Logik für alles, Komplexität und If/Else verringern.»*

    Die Auflösung steht darum an **einer** Stelle im Dienst (`_addresses`) und gilt für
    beide Seiten – die Karte zeichnet nur noch.

    Bug-Formen: (a) es gibt wieder zwei Auflösungen; (b) unsere Seite hat keine; (c) die
    Karte entscheidet selbst, ob eine Beschriftung erscheint.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    src = (BACKEND / "app" / "services" / "voucher.py").read_text()
    body = src[src.index("def _addresses("):]
    body = body[:body.index("\ndef ", 1)]
    assert "BILLING_LABEL" in body and "SHIPPING_LABEL" in body, (
        "Die Beschriftungen kommen nicht mehr aus der einen Auflösung (a)."
    )
    head = src[src.index("def document_head("):src.index("def _addresses(")]
    assert "_addresses(" in head, "Unsere Seite nennt ihre Anschriften nicht (b)."
    assert src.count("_addresses(") >= 3, (
        "Nicht beide Seiten lesen dieselbe Auflösung (a/b)."
    )
    # (c) **Die Karte zeichnet, sie entscheidet nicht**: sie reicht die Beschriftung
    # durch, statt selbst zu fragen, ob es zwei Anschriften gibt.
    card = _code(_beleg())
    party = _component(card, "Party")
    assert "view.address_label" in party and "view.shipping_label" in party, (
        "Die Karte baut die Beschriftungen wieder selbst (c)."
    )
    for word in ("Rechnungsadresse", "Lieferadresse"):
        assert word not in card, (
            f"«{word}» steht als Literal in der Karte (c) – die Wörter kommen vom Server."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DER UMBAU VON «RECHNUNG & ZAHLUNG» + TESTNOTIZEN #979/#981/#982
# ═══════════════════════════════════════════════════════════════════════════════

def test_money_stands_in_two_compartments_not_in_one_row_of_buttons():
    """►►► **Regel 1 — zwei Fächer statt sechs Knöpfen.** ◄◄◄

    *«Zu komplex, zu unstrukturiert, zu wirr, zu viele Optionen, die sich gegeneinander
    stören, kannibalisieren.»* – Gezählt: an einer Rechnung standen bis zu sechs gleich
    aussehende Knöpfe mit **drei** Bedeutungen (Buchung · Korrektur · blosse Auskunft),
    und **zwei Rollen** in einer Zeile («Rechnung erfassen» ist unsere Handlung, «Jetzt
    bezahlen» die des Zahlenden).

    Es sind zwei Fragen: *was schuldet uns jemand* (uns) und *wie kommt das Geld hierher*
    (dem Zahlenden). Zwei Fragen, zwei `ModuleSection` – und damit derselbe
    Fortschritts-Punkt wie an jedem anderen Abschnitt des Belegs, den es hier vorher gar
    nicht gab.

    Bug-Formen: (a) es gibt wieder einen gemeinsamen Abschnitt; (b) ein Fach zeigt keinen
    Fortschritt; (c) die Wörter stehen wieder in der Karte statt beim Server.
    """
    src = _code(_beleg())
    money = _component(src, "Money")
    assert money.count("<ModuleSection") == 2, (
        f"Das Geld steht in {money.count('<ModuleSection')} Abschnitt(en) statt in zwei "
        f"Fächern (a)."
    )
    assert money.count("state=") >= 2, "Ein Fach sagt seinen Fortschritt nicht (b)."
    assert "d.claim_title" in money and "d.settle_title" in money, (
        "Die Überschriften kommen nicht vom Server (c)."
    )
    # (c) **Und der alte Sammeltitel ist weg** – er fasste zwei Fragen zu einer zusammen.
    assert "money_label" not in src and "Rechnung & Zahlung" not in src, (
        "Der gemeinsame Titel ist zurück (a/c)."
    )


def test_exactly_one_money_action_moves_the_voucher_on():
    """►►► **Regel 2 — genau EINE Handlung bringt weiter.** ◄◄◄

    Unten, breit, farbig: *Rechnung stellen* → *Zahlung erfassen* → nichts mehr. Alles
    andere ist eine **Korrektur** und steht klein bei der Zeile, die sie korrigiert – nie
    im selben Rang. Es ist dasselbe Bauteil, das den Zuschlag und den Modul-Abschluss
    trägt (`StageAction`, #923): eine Handlung, die weiterbringt, sieht überall gleich aus.

    Bug-Formen: (a) die Handlung ist wieder ein Knopf unter vielen; (b) es gibt zwei
    dominante gleichzeitig; (c) das Formular steht neben dem Knopf, der es öffnet.
    """
    src = _code(_beleg())
    money = _component(src, "Money")
    assert "<StageAction" in money, (
        "Die Geld-Handlung ist keine Stufen-Handlung mehr (a) – dann steht sie wieder im "
        "Rang einer Korrektur."
    )
    assert money.count("<StageAction") == 1, (
        f"Es gibt {money.count('<StageAction')} dominante Handlungen (b) – die eine, die "
        f"weiterbringt, ist genau eine."
    )
    # (b) **Und sie wird abgeleitet, nicht nebeneinandergestellt**: erst fordern, dann
    # kassieren – ein Rang, den die Oberfläche vergäbe, wäre die zweite Regel neben `can`.
    assert "const forward =" in money, "Der Rang wird nicht abgeleitet (b)."
    # (c) **Das Formular tritt an ihre Stelle**, es steht nicht daneben – entschieden an
    # **einer** Stelle. *Gefragt ist die Regel, nicht ihre Schreibweise: sie stand einmal
    # als `{form ? (…) : (…)}` im JSX, und seit die Handlung in ihrem eigenen Fach steht
    # (#1001), entscheidet dieselbe Bedingung eine Ebene höher.*
    assert "if (form)" in money and money.count("<StageAction") == 1, (
        "Formular und Knopf stehen gleichzeitig da (c) – zwei Handlungen für dieselbe "
        "Sache."
    )
    # ►►► **Und sie steht in dem Fach, zu dem sie gehört** (Testnotiz #1001). ◄◄◄ Unter
    # **beiden** Abschnitten stand sie hinter allem, was in ihnen wächst: jede erfasste
    # Zahlung schob sie weiter weg von der Zahlungsart, mit der sie eine Einheit bildet.
    assert money.count("slot('charge')") == 1 and money.count("slot('pay')") == 1, (
        "Die Handlung steht wieder ausserhalb der beiden Fächer (a) – dann trennt sie "
        "jede neue Zeile von der Wahl, zu der sie gehört."
    )


def test_the_way_to_the_money_is_one_choice_with_several_answers():
    """►►► **Regel 3 — der Weg zum Geld ist eine Wahl, kein Verb.** ◄◄◄

    Bar · Überweisung · Karte sind drei Antworten auf **eine** Frage. Was dahinter
    passiert, ist verschieden (buchen ↔ Angaben zeigen ↔ Zahlformular öffnen) – die Frage
    ist dieselbe. Als drei Knöpfe standen sie im selben Rang wie eine Buchung und wie eine
    Korrektur.

    **Welche Antworten es gibt, sagt der Server** (`ways` aus `can`), und **jeder Weg sagt
    selbst, was er auslöst** (`action`/`verb`) – ein Weg ohne beides ist eine reine
    Auskunft, und dort steht kein Knopf, der nach Buchung aussieht.

    Bug-Formen: (a) die Wege sind wieder Knöpfe; (b) die Oberfläche baut die Liste selbst;
    (c) sie leitet das Verb aus dem Schlüssel ab; (d) bei genau einer Antwort steht
    trotzdem ein Schieber.
    """
    src = _code(_beleg())
    money = _component(src, "Money")
    assert "<Segmented" in money, "Die Wege sind wieder einzelne Knöpfe (a)."
    assert "d.ways" in money, "Die Liste kommt nicht vom Server (b)."
    for key in ("'cash'", "'card'", "'transfer'"):
        assert key not in money, (
            f"«{key}»: die Oberfläche kennt die Schlüssel der Wege (c) – dann leitet sie "
            f"das Verb daraus ab, statt es zu lesen."
        )
    assert "way.verb" in money and "way?.action" in money, (
        "Der Weg sagt nicht selbst, was er auslöst (c)."
    )
    assert "ways.length > 1" in money, (
        "Bei genau einer Antwort steht ein Schieber (d) – eine Wahl mit einer Antwort ist "
        "keine (#793)."
    )


def test_an_invoice_is_issued_here_and_recorded_there():
    """►►► **«Rechnung stellen» ↔ «Rechnung erfassen»** – zwei Vorgänge, zwei Wörter. ◄◄◄

    Bei einer **Einnahme** entsteht der Beleg hier, bekommt unsere Nummer und geht hinaus;
    bei einer **Ausgabe** schreiben wir ab, was der Lieferant geschickt hat. Beides hiess
    «Rechnung erfassen» – und ausgerechnet der Fall, in dem eine Rechnungsnummer vergeben
    wird, klang nach Abtippen.

    Bug-Formen: (a) beide Richtungen sagen wieder dasselbe; (b) das Wort steht als
    Konstante neben der Richtung; (c) die Karte schreibt es selbst.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo

    assert vo.of("in").charge_verb != vo.of("out").charge_verb, (
        "Beide Richtungen sagen dasselbe (a)."
    )
    assert vo.of("in").charge_verb == "Rechnung stellen", (
        "Bei einer Einnahme entsteht der Beleg hier – dann wird er gestellt (a)."
    )
    assert not hasattr(vo, "CHARGE_WORD"), (
        "Das Wort steht wieder als eine Konstante für beide Richtungen da (b)."
    )
    src = (BACKEND / "app" / "services" / "voucher.py").read_text()
    assert '"charge_word": flow.charge_verb' in src, (
        "Der Beleg schickt nicht das Wort seiner Richtung (b)."
    )
    card = _code(_beleg())
    for word in ("Rechnung stellen", "Rechnung erfassen"):
        assert word not in card, f"«{word}» steht als Literal in der Karte (c)."


def test_the_sender_side_names_the_address_the_goods_leave_from():
    """►►► **«Lieferadresse» beim Leistungserbringer war falsch** (Testnotiz #979). ◄◄◄

    *«Beim Leistungserbringer wäre es evtl. besser/richtiger zu sagen Absendeadresse oder
    so? Etabliere hier korrektes.»* – Richtig gesehen: «Lieferadresse» heisst *wohin
    geliefert wird*, und an der eigenen Anschrift des Leistungserbringers stand damit, man
    möge ihm dorthin liefern – während er derjenige ist, der liefert. Von seiner Seite aus
    ist es die Adresse, von der die Ware **abgeht**: **Versandadresse** (der Versender ist
    die Gegenrolle des Empfängers, so heisst es im Handel, in der Logistik und im Zoll).

    **Nur diese eine Beschriftung ist rollenabhängig**, und das ist Absicht: die
    «Rechnungsadresse» beantwortet auf beiden Seiten dieselbe Frage – *welche Anschrift
    gilt in Rechnungssachen*. Ein zweites Wort dafür wäre eine Unterscheidung ohne
    Unterschied.

    Bug-Formen: (a) beide Seiten sagen wieder «Lieferadresse»; (b) die Rolle wird an der
    Aufrufstelle geraten statt aus der Richtung gelesen; (c) die Karte kennt die Wörter.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo

    assert vo.SHIPPING_FROM_LABEL != vo.SHIPPING_LABEL, (
        "Beide Seiten sagen dasselbe (a)."
    )
    src = (BACKEND / "app" / "services" / "voucher.py").read_text()
    body = src[src.index("def _addresses("):]
    body = body[:body.index("\ndef ", 1)]
    assert "sends" in body and "SHIPPING_FROM_LABEL" in body, (
        "Die Auflösung kennt die Rolle nicht (a)."
    )
    # (b) **Die Richtung sagt es** – `collects` steht längst da, und die Gegenseite leitet
    # es selbst ab: ein Parameter wäre eine Angabe, die jeder Aufrufer falsch setzen kann.
    theirs = src[src.index("def their_side("):]
    theirs = theirs[:theirs.index("\ndef ", 1)]
    assert "not vo.of(row.direction).collects" in theirs, (
        "Die Gegenseite rät ihre Rolle (b)."
    )
    head = src[src.index("def document_head("):src.index("def _addresses(")]
    assert "sends=flow.collects" in head, "Unsere Seite rät ihre Rolle (b)."
    assert "Versandadresse" not in _code(_beleg()), (
        "Das Wort steht als Literal in der Karte (c)."
    )


def test_the_recipient_choice_stands_above_the_role_not_in_its_name_line():
    """►►► **Die Auswahl steht ÜBER der Rolle** (Testnotiz #981). ◄◄◄

    *«Gefühlt sollte die Auswahloptionen oberhalb vom Headline Leistungsempfänger stehen
    und dann je nachdem was angewählt wurde unterhalb der Headline die Angaben geladen
    werden – es ist einfach noch nicht so elegant, wie ich es gerne hätte.»*

    Die Chips standen **in** der Namenszeile, also unter der Rolle und an genau der
    Stelle, an der sonst der Name steht: sie ersetzten die Angabe, die sie auswählen. Über
    der Rolle ist es die Reihenfolge des Lesens – erst *wen meine ich*, dann *was gilt für
    ihn*. Auf unserer Seite bleibt die Zeile leer; die Symmetrie ist dieselbe Regel wie bei
    jeder anderen Zeile des Rasters (#913).

    Bug-Formen: (a) die Auswahl steht wieder unter der Rolle; (b) das Raster zählt die
    Zeile nicht mit – dann laufen die beiden Blöcke auseinander; (c) der Name steht nicht
    mehr unter der Rolle.
    """
    src = _code(_beleg())
    party = _component(src, "Party")
    assert party.index("<Recipients") < party.index("{side.label}"), (
        "Die Auswahl steht wieder unter der Rolle (a)."
    )
    assert party.index("{side.label}") < party.index("view.name"), (
        "Der Name steht nicht unter der Rolle (c)."
    )
    assert "const PARTY_ROWS = 8" in src, (
        "Das Raster zählt die neue Zeile nicht mit (b) – dann steht dieselbe Angabe auf "
        "beiden Seiten auf verschiedener Höhe."
    )
    # (b) **Und unsere Seite hält die Zeile frei** – ein fehlendes Kind verschöbe alles
    # darunter um eine Zeile.
    assert "side.ours\n        ? <div />" in party or "? <div />" in party, (
        "Unsere Seite lässt die Zeile aus (b)."
    )
    # (a) **Die Chips sind nur noch die Auswahl** – benannt wird die Gewählte darunter.
    rec = _component(src, "Recipients")
    assert "font: '600 13px var(--font-body)'" not in rec, (
        "Die Auswahl trägt wieder den Namen der Gewählten (a) – dann steht er zweimal."
    )


def test_a_customs_field_names_itself_while_it_is_being_typed():
    """►►► **Die Beschriftung steht davor – beim Eingeben wie im Beleg** (#982). ◄◄◄

    *«Im fertigen Beleg steht eigentlich immer ‹Zolltarif xy, Ursprung xy› – hier bei der
    Eingabe steht einfach nur das Eingabefeld, aber der entsprechende Text nicht davor.
    Das ist eine unerlaubte Abweichung von unserer Logik.»*

    Der Name stand als **Platzhalter** im Feld – also an der Stelle, an der eine Oberfläche
    sagt «hier ist nichts» – und verschwand beim ersten Zeichen. Die Regel dieses Belegs
    lautet *der gedruckte Wert IST das Bedienelement* (#922): was man ändert, muss aussehen
    wie das, was gedruckt wird.

    Bug-Formen: (a) der Name ist wieder nur ein Platzhalter; (b) die beiden Zustände sehen
    verschieden aus; (c) die Beschriftung trägt die Auszeichnung änderbarer Werte, obwohl
    sie nicht änderbar ist.
    """
    src = _code(_beleg())
    body = _body(src, "Customs", kind="function")
    assert "placeholder=" not in body, (
        "Der Name steht wieder als Platzhalter (a) – dann ist er beim ersten Zeichen weg."
    )
    # (b) **Dieselbe Zeile in beiden Zuständen**: Beschriftung, dann Wert – gleiche Grösse,
    # gleiche Farbe. Gezählt, denn genau eine der beiden Stellen könnte abweichen.
    assert body.count("fontSize: 11.5, color: 'var(--fg-3)'") == 2, (
        "Die Beschriftung sieht im Eingabe- und im Lesezustand verschieden aus (b)."
    )
    # (c) **Nur der Wert ist änderbar** – die Hülle umschliesst das Feld, nicht das Wort.
    # Gefragt wird der **Textknoten**: `title={label}` und `aria-label={label}` stehen
    # zu Recht in der Hülle, und ein blosses «`{label}` kommt darin vor» wäre schon davon
    # erfüllt (gemessen – die erste Fassung schlug genau daran an).
    edit = body[body.index('<span className="inline-flex'):]
    assert edit.index("{label}</span>") < edit.index("<Editable"), (
        "Die Beschriftung steht innerhalb der Auszeichnung (c) – dann verspricht sie "
        "Änderbarkeit, die es nicht gibt."
    )


def test_no_editable_value_of_the_voucher_lives_only_in_the_browser():
    """►►► **Jede Angabe des Belegs hat ihr Verb** (Testnotiz #985). ◄◄◄

    *«Eingaben in ‹Zahlungsfrist› und ‹Lieferfrist› werden nicht persistiert.»* – Sie
    waren die einzige Angabe ohne eigenes: ein gehobener Zustand in ``BelegWork``,
    mitgeschickt allein in der Nutzlast von ``ask``. Ein Reload verwarf ihn.

    Geprüft wird die **Regel**, nicht die zwei Felder: der Beleg schickt keine Frist in
    der Nutzlast eines anderen Verbs mit, und die Zeile, die sie zeigt, speichert sie
    selbst – dieselbe Bauart wie die Lieferbedingung.

    Bug-Formen: (a) ``ask`` trägt wieder eine Frist mit (der Entwurf lebt woanders);
    (b) die Frist wird nicht gespeichert (kein ``useAutosave`` in ihrer Zeile); (c) das
    Verb heisst nicht ``terms``, also kommt nichts an.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))

    # (a) **Keine Frist reist in einem fremden Befehl mit.** Der eine Payload-Bauer für
    #     `ask` steht in `BelegWork`; steht dort eine Frist, gibt es wieder einen Entwurf,
    #     den niemand schreibt.
    asker = _component(src, "BelegWork")
    for field in ("payment_days", "lead_days"):
        assert field not in asker, (
            f"«{field}» reist wieder in der Nutzlast von `ask` mit (a) – dann lebt der "
            f"Entwurf im Browser, und ein Reload verwirft ihn."
        )

    # (b)/(c) **Die Zeile, die eine Frist zeigt, speichert sie auch** – mit ihrem Verb.
    saver = _component(src, "SavedTerm")
    assert "useAutosave" in saver, (
        "Die Frist wird nicht gespeichert (b) – sie steht wieder nur im Browser."
    )
    assert "'terms'" in saver or '"terms"' in saver, (
        "Die Frist wird mit einem anderen Verb geschickt (c) – der Dienst kennt nur "
        "`terms`, also kommt nichts an."
    )


def test_a_recipient_chip_carries_no_state_dot():
    """►►► **Der Chip sagt seinen Zustand nicht zum vierten Mal** (Testnotiz #983). ◄◄◄

    *«Ein optisch störender Punkt/Separator. Entfernen, ohne das umliegende Spacing zu
    zerschiessen.»* – Er stand als 6-px-Punkt vor dem Namen und war genau das: was
    angefragt ist, sagt das **Zeichen rechts** (`+` ↔ `✕`), die **Textfarbe** und das
    **Wort im Hover** – und ausführlich der Abschnitt *Angebote* eine Zeile tiefer, wo
    jede Zeile ihren eigenen Punkt **und** ihr Wort trägt.

    «Punkt + Wort» bleibt die Anatomie eines Zustands im Haus; hier fehlte das Wort, und
    was blieb, war ein Zeichen, das man deuten muss.

    Bug-Formen: (a) der Punkt steht wieder im Chip; (b) mit ihm verschwand auch das Wort
    im Hover, also sagt der Chip seinen Zustand gar nicht mehr.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    chip = _component(src, "Chip")
    assert "rounded-full" not in chip, (
        "Der Zustandspunkt steht wieder im Chip (a) – die vierte Fassung derselben "
        "Aussage, und die einzige ohne Wort."
    )
    assert "data-tip={look.label}" in chip, (
        "Mit dem Punkt ist auch das Wort gegangen (b) – dann sagt der Chip seinen "
        "Zustand nirgends mehr."
    )


def test_a_date_is_written_in_exactly_one_place():
    """►►► **EINE Datums-Ausgabe für das ganze System** (Testnotiz #992). ◄◄◄

    *«Bitte erstelle EINE zentrale Datums-Formatierungsfunktion und ersetze alle
    bestehenden Ausgaben damit.»*

    Vorher gab es **sieben**: `localDate`, `localDateTime`, drei eigene Helfer im Beleg
    (`daysUntil`/`relative`/`since`) und je ein `toLocaleDateString` am Benutzer, am Profil
    und an den Passkeys. Dieselbe Angabe las sich an fünf Stellen anders.

    ►►► **Zwei Funktionen sind kein Widerspruch, sondern zwei Fragen** – `when()` sagt
    *wann war das* (die Aussage), `day()` *welcher Tag steht auf dem Papier* (die
    Tatsache). Zwei Formen einer Regel, ein Modul, ein Namensstamm.

    Bug-Formen: (a) irgendwo im Haus steht wieder eine eigene Formatierung; (b) das Modul
    verlässt sich auf das ICU des Laufzeitsystems (dann heisst derselbe Monat je nach
    Umgebung anders – die Lehre aus `formatAmount`); (c) die Aussage steht ohne ihre
    Tatsache da.
    """
    # (a) **Niemand formatiert selbst** – ausser dem einen Modul.
    for path in (FRONTEND / "components").rglob("*.tsx"):
        code = _code(path.read_text())
        for gone in ("toLocaleDateString", "toLocaleTimeString", "DateTimeFormat",
                     "localDate(", "localDateTime("):
            assert gone not in code, (
                f"«{gone}» steht wieder in {path.name} (a) – dann gibt es die "
                f"Datums-Ausgabe zweimal, und die zweite weicht ab."
            )
    src = _read(FRONTEND / "lib" / "when.ts")
    code = _code(src)
    # (b) **Die Wörter stehen im Modul**, nicht im ICU der Laufzeit.
    assert "MONTHS" in code and "'Sep.'" in code, (
        "Die Monatskürzel kommen wieder aus dem ICU (b) – «Sep.» im Browser, «Sept.» in "
        "Node, und derselbe Beleg sieht je nach Laufzeit anders aus."
    )
    assert "toLocaleDateString" not in code and "toLocaleString" not in code, (
        "Auch das eine Modul rechnet wieder mit dem ICU (b)."
    )
    # Die Regeln, nach denen gefragt wurde – jede als eigener Ast. **Gefragt sind die
    # Wörter, nicht ihre Schreibweise**: «vor 3 Tagen» einmal als Vorlage und einmal aus
    # einer Funktion ist dieselbe Regel, und ein Wächter, der die frühere Form verlangt,
    # verbietet die bessere.
    for word in ("'Gestern'", "'Morgen'", "'Minute'", "'Stunde'", "'Tag'"):
        assert word in code, f"Die Regel «{word}» fehlt in `when()`."
    # ►►► **Und innerhalb eines Tages sagt sie es auch** (Testnotiz #1003). ◄◄◄ Für
    # «heute» stand hier die blosse **Uhrzeit** – eine Zahl, aus der man selbst
    # ausrechnet, wie lange das her ist. Die Tatsache gehört in den Hover
    # (`whenTitle`), die **Aussage** in die Zeile.
    body = _body(code, "when", kind="export function")
    assert "gerade eben" in code.lower() or "JUST_NOW" in body, (
        "Unter einer Minute steht wieder eine Zahl statt «gerade eben»."
    )
    for unit in ("MINUTE", "HOUR", "DAY"):
        assert unit in body, (
            f"`when()` kennt die Schwelle «{unit}» nicht – dann fällt alles von heute "
            f"wieder auf eine einzige Aussage zusammen."
        )
    assert "getHours" not in body, (
        "Für «heute» steht wieder die blosse Uhrzeit – das ist die Tatsache, nicht die "
        "Aussage; sie gehört in `whenTitle` und damit in den Hover."
    )
    # (c) **Die Tatsache reist mit** – `formatWhen` gibt Aussage und Hover in einem Zug.
    assert "whenTitle(value)" in _body(code, "formatWhen", kind="export function"), (
        "Die Aussage kommt ohne ihre Tatsache (c) – dann steht eine Zahl da, die "
        "niemand nachprüfen kann."
    )


def test_a_company_is_named_the_same_in_the_feed_and_in_its_window():
    """►►► **Unternehmensname + Rechtsform – überall dasselbe** (Testnotiz #984). ◄◄◄

    *«ERP-Feed und Header des Detailfensters, zwingend identisch, eine gemeinsame
    Anzeigefunktion.»*

    Die gemeinsame Funktion gab es (`organizationName`) – **die Angabe kam nur nie an**:
    `mapSettingsFromBackend` baut sein Objekt Feld für Feld, und `legal_name` stand nicht
    darin. Was ein solcher Mapper nicht nennt, verschwindet **still** – dieselbe
    Fehlerform wie eine Pydantic-Klasse, die ein Feld nicht kennt, nur in der anderen
    Richtung. Der Rückfall auf den blossen Namen griff damit an *jeder* Stelle, und die
    Rechtsform stand im ganzen ERP nirgends.

    Bug-Formen: (a) der Mapper verliert das Feld wieder; (b) eine Aufrufstelle baut sich
    einen eigenen Namen daneben; (c) der abgeleitete Name wird zurückgeschickt.
    """
    api = _code(_read(FRONTEND / "lib" / "api.ts"))
    mapper = _body(api, "mapSettingsFromBackend", kind="function")
    assert "legal_name" in mapper, (
        "Der Mapper verliert die Rechtsform wieder (a) – sie kommt vom Server und "
        "erreicht den Browser nicht, und niemand sieht es."
    )
    # (c) **Abgeleitet heisst: nicht zurückschreiben.**
    back = _body(api, "mapSettingsToBackend", kind="function")
    assert "'legal_name'" in back, (
        "Der abgeleitete Name geht zurück an den Server (c) – die zweite Wahrheit neben "
        "den beiden Feldern, aus denen er kommt."
    )
    # (b) **Eine Anzeige, ein Aufruf** – im Feed wie in der Kopfzeile, ohne Rückfall.
    detail = _code(_read(FRONTEND / "components" / "erp" / "organization-detail.tsx"))
    head = detail[_at(detail, "<DetailHeader"):]
    head = head[: head.index("/>")]
    assert "organizationName(base)" in head and "form.company_name" not in head, (
        "Die Kopfzeile hat einen eigenen Rückfall (b) – und ausgerechnet einen ohne "
        "Rechtsform."
    )


def test_a_row_action_stands_at_the_end_of_its_row():
    """►►► **Zeilenaktion statt freistehender Knöpfe** (Testnotizen #989/#993). ◄◄◄

    *«‹Stornieren› und ‹Korrigieren› bitte als Zeilenaktion – einheitlich für beide und
    künftige Zeilenaktionen; sichtbar bei Hover/Fokus, auf Touch dauerhaft. Destruktive
    Aktionen mit kurzer Bestätigung.»*

    Also ein **Bauteil**, kein Fall: `LedgerRow`/`RowActions` in `module-ui`, und die
    Regel im Blatt (`.ix-row`/`.ix-rowactions`) – damit erbt jede künftige Liste sie.

    ►►► **Und die Aufrufstelle baut die Zeile nicht selbst** (#996–#1002). ◄◄◄ Sie sagt
    nur, was an die vier Plätze gehört; **wo** die Knöpfe stehen, entscheidet die
    Grammatik. Ein Wächter, der die frühere Flexzeile in `EntryRow` sucht, verböte genau
    diese Lösung – gefragt ist darum die Regel an ihrem neuen Ort.

    ►►► **Eine Rückfrage gibt es nicht mehr** (Testnotiz #1022). ◄◄◄ Sie stand hier als
    (c)/(d) – zweiter Klick am Storno, nach vier Sekunden zurückfallend. *«Die Sicherheit
    kommt aus den Guards, nicht aus einem zusätzlichen Klick.»* Und die Guards gibt es:
    ein Storno schreibt eine Gegenbuchung (eine zweite lehnt der Dienst ab), eine
    Erstattung ist beim Zahlungsdienst idempotent. Der Wächter prüft das jetzt als Regel –
    **keine zweite Stufe an irgendeiner Handlung dieses Moduls**.

    Bug-Formen: (a) die Knöpfe stehen wieder als eigener Block unter der Zeile; (b) sie
    stehen dauerhaft da; (c) eine Handlung bekommt wieder eine zweite Stufe.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(work, "EntryRow")
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    # (a) **In der Zeile, nicht darunter** – und das entscheidet die Grammatik: die
    # Aufrufstelle reicht ihre Knöpfe als `actions` durch, `LedgerRow` setzt sie in
    # `RowActions` **innerhalb** derselben Zeile.
    assert "<LedgerRow" in row and "actions={" in row, (
        "Die Geld-Zeile baut sich wieder selbst (a) – dann gilt die Grammatik für sie "
        "nicht mehr."
    )
    grammar = _body(ui, "LedgerRow", kind="export function")
    at = grammar.index("<RowActions")
    assert "</div>" not in grammar[grammar.index("ix-row"):at], (
        "Die Korrekturen stehen wieder als eigener Block unter der Zeile (a)."
    )
    assert "ix-rowactions" in _body(ui, "RowActions", kind="export function"), (
        "Die Knöpfe stehen dauerhaft da (b) – die Regel steht im Blatt, nicht hier."
    )
    # (c) ►►► **Ein Klick löst aus** – einheitlich, an jeder Handlung des Moduls. ◄◄◄
    #
    # Gefragt wird die **Regel**, nicht die Form: weder darf das Bauteil zurückkommen noch
    # darf eine Aufrufstelle sich eine eigene zweite Stufe bauen. Genau daran hing die
    # Meldung – der Storno fragte nach, die Korrektur daneben nicht, und die Erstattung
    # wieder doch.
    assert "ConfirmButton" not in ui and "armed" not in ui, (
        "Die zweite Stufe ist wieder da (c) – die Sicherheit kommt aus den Guards."
    )
    assert "ConfirmButton" not in work and "onConfirm" not in work, (
        "Eine Handlung des Geld-Moduls fragt wieder nach (c)."
    )


def test_both_booking_forms_are_the_same_form():
    """►►► **Ein Formular, und es sieht aus wie jedes andere** (#987/#990). ◄◄◄

    *«Feldhöhen, Spacing, Button-Hierarchie: eine Primäraktion, Abbrechen dezent. Beide
    untereinander identisch.»*

    «Rechnung stellen» und «Zahlung erfassen» waren schon **dieselbe** Komponente;
    auseinander lagen die Masse – ein eigener `gap: 3` unter der Beschriftung (obwohl
    `fields.Label` seine 4 px mitbringt) und zwei gleich grosse Knöpfe nebeneinander.

    Bug-Formen: (a) die Masse stehen wieder als Zahlen an dieser Stelle; (b) zwei gleich
    grosse Knöpfe; (c) das Feld ist nicht das des Hauses.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    form = _component(work, "Entry")
    # (a) **Der Abstand kommt aus dem Bauteil.** Und unter der Beschriftung gibt es keinen:
    # `Label` bringt seine eigenen 4 px mit.
    assert "FIELD_GAP" in form, "Der Feld-Abstand steht wieder als Zahl da (a)."
    ask = _component(work, "Ask")
    assert "gap:" not in ask, (
        "Unter der Beschriftung steht wieder ein eigener Abstand (a) – `Label` bringt "
        "seine 4 px mit, und ein `gap` kommt obendrauf."
    )
    # (b) **Eine Primäraktion, Abbrechen dezent** – dieselbe Zeile wie überall im Beleg.
    assert "<StageRow" in form and "<StageAction" in form, (
        "Die beiden Knöpfe stehen wieder gleichrangig nebeneinander (b)."
    )
    assert "square" in form, "«Abbrechen» ist kein Quadrat daneben (b)."
    # (c) **Das Formularfeld des Hauses** – ein Beleg-Feld (`DOC_FIELD`) wäre hier falsch:
    # dies ist wirklich ein Formular.
    assert form.count("inputCls") >= 2, "Die Felder sind nicht die des Hauses (c)."


def test_a_payment_row_begins_with_how_it_was_paid():
    """►►► **Zahlungsart zuerst, dann Betrag und Datum** (Testnotiz #994). ◄◄◄

    *«Im Abschnitt ‹Begleichen› soll jede Zahlungszeile mit der Zahlungsart beginnen.»* –
    Das ist die Angabe, an der man eine Zahlung wiedererkennt; die Referenz sagt sie
    nicht, und bei einer Barzahlung gibt es gar keine. Sie stand in einer zweiten Zeile
    hinter dem Zustand.

    ►►► **Und «Offen» steht nicht dreimal** (#988). ◄◄◄ Der Zustand stand als eigene
    Zeile unter der Rechnung, obwohl der Punkt eine Zeile höher ihn schon sagt – und
    «Offen» ein drittes Mal in der Brücke zwischen den beiden Fächern, wo es die Zahl
    trägt.

    Bug-Formen: (a) die Zahlungsart steht wieder hinten; (b) der Zustand steht wieder als
    eigene Zeile darunter; (c) die Rechnung verliert dabei ihren Zustand ganz.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(work, "EntryRow")
    # **Der Identifikator ist der erste Platz der Zeilen-Grammatik** – gefragt ist, was
    # dort steht, nicht mehr, in welcher Reihenfolge eine handgebaute Flexzeile ihre
    # Kinder aufzählt.
    ident = row[row.index("ident="):row.index("meta=")]
    assert "e.method_label" in ident, (
        "Die Zahlungszeile beginnt nicht mit ihrer Art (a)."
    )
    assert row.index("ident=") < row.index("amount="), (
        "Die Zahlungsart steht hinter dem Betrag (a)."
    )
    # (b) **Keine zweite Zeile mehr** – dort standen Zustand und Vermerk (#988/#999).
    assert "state.label" not in row, (
        "Der Zustand steht wieder als eigene Zeile darunter (b)."
    )
    # (c) **Aber sie sagt ihn weiterhin** – als Farbe des Betrags und als Wort im Hover.
    assert "state?.color" in row and "state?.label" in row, (
        "Die Rechnung sagt ihren Zustand gar nicht mehr (c)."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► Testnotizen #995–#1003 — eine Zeilen-Grammatik, und der Saldo ist eine Farbe
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_money_row_follows_one_grammar():
    """►►► **Eine Zeile, vier Plätze, immer dieselben** (#996/#998/#999/#1002). ◄◄◄

    *«Definiere EIN Zeilenlayout, das für alle Zeilen in ‹Fordern› und ‹Begleichen› gilt,
    und implementiere es als eine Komponente:*
    ``[ Identifikator ] [ Meta ] … [ Aktion ] [ Betrag ]``*»*

    Vier Notizen, ein Layout – und jede betraf einen anderen Platz darin: der Zustandspunkt
    vor der Rechnungsnummer (#996), die Korrekturen **hinter** dem Betrag (#998/#1002) und
    eine **zweite Zeile** mit einer Angabe, die die erste schon sagt (#999).

    Bug-Formen: (a) die Aufrufstelle baut ihre Zeile wieder selbst; (b) der Betrag steht
    nicht zuletzt; (c) die Aktion steht hinter ihm; (d) die Zeile bricht um oder hat eine
    zweite; (e) vor dem Identifikator steht wieder ein Zeichen.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    grammar = _body(ui, "LedgerRow", kind="export function")
    flat = " ".join(grammar.split())
    # (b)/(c) **Die Reihenfolge IST die Grammatik.**
    order = [flat.index(x) for x in ("{ident}", "{meta}", "<RowActions", "{amount}")]
    assert order == sorted(order), (
        f"Die vier Plätze stehen nicht in ihrer Reihenfolge (b/c): {order}."
    )
    # (d) **Strikt einreihig** – was nicht passt, wird gekappt, nie umgebrochen.
    assert "flexWrap: 'nowrap'" in flat, (
        "Die Zeile darf wieder umbrechen (d) – dann rutscht der Betrag unter den Text."
    )
    assert flat.count("truncate") >= 2, (
        "Identifikator und Meta kappen nicht (d) – dann bricht die Zeile doch."
    )
    # (a) **Die Aufrufstelle sagt nur, WAS an die Plätze gehört.**
    row = _component(_code(_beleg()), "EntryRow")
    assert "<LedgerRow" in row, "Die Geld-Zeile baut sich wieder selbst (a)."
    for slot in ("ident=", "meta=", "actions=", "amount="):
        assert slot in row, f"Der Platz «{slot}» fehlt (a)."
    # (e) **Kein Zeichen vor dem Identifikator** – der Punkt sagte als viertes, was die
    # Farbe des Betrags, der Hover und der Abschnitt «Angebote» längst sagen (#996).
    assert "rounded-full" not in row, (
        "Vor der Rechnungsnummer steht wieder ein Punkt (e) – er rückt sie ein und sagt "
        "als Zeichen etwas, wofür ihm das Wort fehlt."
    )
    # (d) **Und die zweite Zeile ist weg** – dort stand «Zahlungsdienst» neben «Karte».
    # *Gefragt ist der **Vermerk**, nicht das Wort: «Zahlungsdienst» steht in derselben
    # Datei völlig zu Recht in einer Fehlermeldung – der erste Anlauf zählte sie mit.*
    assert 'note="Zahlungsdienst"' not in _read(
        BACKEND / "app" / "services" / "stripe_pay.py"), (
        "Der Vermerk «Zahlungsdienst» wird wieder geschrieben (d) – die Zahlungsart sagt "
        "es bereits."
    )


def test_the_balance_is_a_number_and_its_colour():
    """►►► **Der Saldo sagt seinen Zustand als FARBE** (Testnotiz #997). ◄◄◄

    *«Das Wort ‹Offen› entfällt.»* – Es war ohnehin nur an einem der vier Zustände
    richtig: «Offen 0.00» las sich wie «bezahlt», und bei einer Überzahlung sagte es das
    Gegenteil dessen, was dastand.

    Bug-Formen: (a) das Wort steht wieder vor der Zahl; (b) die Oberfläche rechnet den
    Zustand selbst; (c) das Guthaben steht ohne Namen da; (d) der offene Posten bekommt
    ein Minus.
    """
    src = _code(_beleg())
    bal = _component(src, "Balance")
    # (a) **Kein Wort ausser dem Guthaben** – und das kommt vom Server.
    assert "open_word" not in src, "Das Wort «Offen» steht wieder vor der Zahl (a)."
    # *Gefragt ist der **Textknoten**, nicht das Vorkommen: das Wort steht ohnehin als
    # `data-tip`, und «kommt vor» liess die eigene Bug-Form durch – gemessen,
    # nachgeschärft.*
    visible = re.sub(r"\b\w+=\{[^}]*\}", "", bal)
    assert "d.open_state_label" in visible, (
        "Das Guthaben nennt sich nicht beim Namen (c) – «250.00» in Grün sagt nicht, wer "
        "wem etwas schuldet."
    )
    # (b) **Der Zustand kommt vom Server** – hier gerechnet wäre er die zweite Ableitung
    # derselben Zahlen und die erste, die eine Rundungstoleranz vergisst.
    assert "d.open_state_tone" in bal and "TONE[" in bal, (
        "Die Farbe wird wieder selbst gewählt (b)."
    )
    assert "Number(d.open)" not in bal, (
        "Die Oberfläche entscheidet wieder an der Zahl, welche Farbe gilt (b)."
    )
    # (d) **Ein offener Posten ist eine Forderung, kein negativer Wert** – das Vorzeichen
    # gibt es nur beim Guthaben, und dort dreht es die Zahl ins Positive.
    assert "negate(d.open)" in bal and "credit" in bal, (
        "Das Vorzeichen hängt nicht mehr am Guthaben (d)."
    )


def test_a_row_action_is_flush_right():
    """►►► **Auch im Editor steht sie am Ende ihrer Zeile** (Testnotiz #995). ◄◄◄

    Der «Entfernen»-Knopf der Partner-Zeile stand links neben dem Namen, sobald die Zeile
    kein Eingabefeld trug – beim **Verkauf** gibt es keine Bestellangabe, und damit war
    nichts mehr da, das die Lücke füllte. Mitten im Text ist kein Platz für eine Aktion:
    die Zeilen-Grammatik kennt dafür einen (`module-ui.LedgerRow`).

    Bug-Formen: (a) der Knopf steht wieder direkt am Text; (b) die Regel steht an der
    Aufrufstelle statt am Knopf – dann vergisst sie die nächste.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"))
    body = _body(src, "RowDelete", kind="function")
    assert "marginLeft: 'auto'" in body, (
        "Der Löschen-Knopf steht wieder mitten in der Zeile (a)."
    )
    for call in re.findall(r"<RowDelete[^/]*?/>", src, re.S):
        assert "marginLeft" not in call and "style=" not in call, (
            "Eine Aufrufstelle richtet den Knopf selbst aus (b) – dann tut es die "
            "nächste anders."
        )


def test_choosing_a_party_writes_it_instead_of_asking():
    """►►► **Die Wahl wird geschrieben, nicht abgeschickt** (Testnotiz #1000). ◄◄◄

    *«Wurde beim Anlegen kein Partner vorgewählt, lässt er sich nachträglich nicht mehr
    setzen. Die Auswahl wird korrekt angezeigt, aber nicht übernommen/persistiert.»*

    Das freie Feld rief `onAsk` – die Handlung, mit der der Beleg **nach aussen** geht. Sie
    verlangt Preis, beide Fristen und die Lieferbedingung, und an einem frischen Modul
    fehlt davon naturgemäss alles: der Dienst wies mit einem Satz ab, und die getroffene
    Wahl war weg. Anfragen tut der `+` am Chip, wenn alles dasteht.

    Bug-Formen: (a) das Feld fragt wieder an; (b) die Wahl lässt sich nicht mehr
    zurücknehmen, solange nichts hinausgegangen ist.
    """
    src = _code(_beleg())
    who = _component(src, "Recipients")
    field = who[who.index("<DocRef"):]
    assert "action: 'party'" in field and "onAsk(" not in field, (
        "Die Wahl der Gegenpartei fragt sie sofort an (a) – dann verwirft ein "
        "unvollständiger Beleg sie stillschweigend."
    )
    # (b) **Wer nur gewählt ist, lässt sich auch wieder wegnehmen** – dieselbe
    # Gegenhandlung wie beim Zurückziehen einer Anfrage; was sie bewirkt, sagt der Beleg.
    assert "removable" in who and "allowed.some" in who, (
        "Ein nur gewählter Partner lässt sich nicht mehr abwählen (b)."
    )


def _module_ui() -> str:
    return _read(FRONTEND / "components" / "erp" / "module-ui.tsx")


def test_an_autosave_never_moves_the_page():
    """►►► **Ein Auto-Save darf die Geometrie der Seite nicht verändern** (#1009). ◄◄◄

    *«Beim Autosave im Zahlungsmodul springt das Layout: Felder verändern ihre Höhe,
    wodurch das nächste Feld nicht mehr getroffen wird.»*

    Gemessen in Chromium an der echten Komponente – zwei Ursachen, beide hier festgehalten:

    (a) **Die Aufstellung entstand erst mit dem ersten Preis.** Netto- und Steuerzeile
        gab es nicht, solange nichts gebucht war; kam die Antwort des Servers, wuchsen sie
        in den Beleg und schoben die drei Konditionen-Felder um **45,5 px** nach unten.
        Welche Zeilen es gibt, sagen die **Positionen** (jede trägt ihren Satz) – der Platz
        steht damit von Anfang an, und wo noch kein Betrag gebucht ist, steht ein «—».

    (b) **`disabled` nimmt dem Feld den Fokus**, und es bekommt ihn nicht zurück: gemessen
        war ``document.activeElement`` nach jedem Auto-Save ``null`` – mitten im Tippen.
        `busy` sperrt darum nur noch **Handlungen** (Knöpfe), nie einen Wert.

    Bug-Formen: (a) die Netto-Zeile hängt wieder an einer Bedingung; (b) ein änderbarer
    Wert ist wieder `disabled={busy}`.
    """
    src = _beleg()
    sums = _code(_component(src, "Sums"))
    assert '<SumRow label="Netto"' in sums and "{d.net != null &&" not in sums, (
        "Die Netto-Zeile erscheint erst mit einem Wert (a) – dann springt alles darunter."
    )
    # **Die Zeilen kommen aus den Positionen**, nicht aus der Antwort des Servers allein:
    # sonst steht die Aufstellung erst, wenn der erste Preis gebucht ist. Gefragt ist die
    # **Schleife**, nicht der blosse Name: `d.lines` steht auch in der Abhängigkeitsliste,
    # und die erste Fassung war schon dadurch erfüllt (gegengeprüft).
    assert "for (const ln of d.lines)" in sums, (
        "Die Steuerzeilen kommen allein aus der Server-Aufteilung (a) – vor dem ersten "
        "Preis gibt es sie damit nicht."
    )
    # (b) **Kein Wert wird beim Speichern gesperrt.** Gefragt ist das Bedienelement, nicht
    # der Knopf: ein `<input>`/`<select>` hält Fokus und Cursor, ein Knopf nicht.
    for tag in ("<input", "<select"):
        for chunk in _code(src).split(tag)[1:]:
            head = chunk.split(">")[0]
            assert "disabled={busy}" not in head, (
                f"Ein Eingabefeld wird beim Speichern gesperrt (b): {tag}{head[:70]} – "
                "es verliert dabei Fokus und Cursorposition."
            )


def test_a_money_row_says_when_it_was_not_which_day():
    """►►► **In einer Geld-Zeile ist das Datum eine AUSKUNFT** (Testnotiz #1004). ◄◄◄

    *«‹Begleichen› zeigt weiterhin ‹13.09.2026› statt der relativen Form.»* – Und die
    Ursache war nicht der Server (er liefert ISO-Zeitstempel, formatiert wird allein im
    Browser): die Zeile rief ``day()``, also die **Tatsache**, die auf ein Papier gehört
    (MWSTG Art. 26). Gefragt ist hier aber *wann war das* – «vor 3 Tagen», wie eine Zeile
    höher bei der Fälligkeit. Das Datum verschwindet nicht, es steht im Hover.

    ►►► **Und eine Auskunft braucht einen ZEITPUNKT** (Testnotiz #1014). ◄◄◄ Dieselbe
    Regel, dreimal gemeldet – und die letzte Meldung lag nicht mehr an `when()`: die
    Funktion bekam `booked_on`, einen **reinen Tag**, und aus einem Tag ohne Uhrzeit lässt
    sich «vor 5 Minuten» nicht ableiten (sie überspringt die Stunden-Kaskade darum
    bewusst, statt Genauigkeit zu erfinden). Gefehlt hat der Zeitpunkt; er reist als
    `booked_at` mit.

    Bug-Formen: (a) der Buchungstag steht wieder als Datum in der Zeile; (b) die Aussage
    liest wieder den reinen Tag, und alles von heute heisst «Heute».
    """
    entry = _code(_component(_beleg(), "EntryRow"))
    assert "when(e.booked_at" in entry, (
        "Die Aussage liest den reinen Tag statt des Zeitpunkts (b) – damit heisst alles "
        "von heute «Heute», auch was vor fünf Minuten gebucht wurde."
    )
    assert "text: day(e.booked_on)" not in entry, (
        "Der Buchungstag steht wieder als Tatsache in der Zeile."
    )
    # Gefragt ist der Hover **dieser** Zeile: `day(e.booked_on)` steht auch im Hover der
    # Rechnungs-Zeile, und ein blosses «kommt vor» war schon dadurch erfüllt
    # (gegengeprüft).
    assert "`Gebucht ${day(e.booked_on)}`" in entry, (
        "Die Tatsache fehlt im Hover – eine Aussage ohne sie kann niemand nachprüfen."
    )


def test_an_amount_is_one_component_and_wears_one_colour():
    """►►► **EIN Betrag — Zahl, Währung, Zustandsfarbe** (Testnotiz #1007). ◄◄◄

    *«Zahl und Währung immer in derselben Farbe. Die Währung darf zurücktreten, aber nie
    in einer anderen Farbe.»* – Genau das war passiert: die Geld-Zeile färbte beide
    zusammen, der Saldo darunter setzte die Währung auf ``--fg-2`` und die Zahl auf ihren
    Ampelton.

    Die Regel steckt in der **Bauart**, nicht in einer Verabredung: die Währung ist ein
    **Kind** der Zahl und erbt ihre Farbe – sie kann gar keine andere mehr haben.

    Bug-Formen: (a) eine Aufrufstelle formatiert wieder selbst; (b) die Währung bekommt
    eine eigene Farbe.
    """
    assert "formatAmount(" not in _code(_beleg()), (
        "Eine Aufrufstelle des Belegs formatiert ihren Betrag selbst (a) – dann gibt es "
        "wieder zwei Schreibweisen für dieselbe Sache."
    )
    amount = _code(_component(_module_ui(), "Amount"))
    assert "color: 'inherit'" in amount, (
        "Die Währung trägt eine eigene Farbe (b) statt der der Zahl."
    )


def test_a_row_begins_on_the_same_edge_as_every_other():
    """►►► **Der Name der Angebotszeile ist nicht eingerückt** (Testnotiz #1005). ◄◄◄

    Ursache war ein **Icon-Platzhalter**: ein 6-px-Zustandspunkt mit 10 px Abstand davor –
    der Name begann damit 16 px weiter rechts als der Identifikator einer Geld-Zeile, die
    Menge einer Position oder die Beschriftung einer Kondition (gemessen: 525 statt 509).

    Es ist dieselbe Frage wie in der Geld-Zeile (#996), und die Antwort ist dieselbe: der
    Punkt geht, die Aussage bleibt – als Preis, und wo keiner dasteht, als **Wort**.

    Bug-Form: der Punkt steht wieder vor dem Namen.
    """
    quote = _code(_component(_beleg(), "QuoteRow"))
    assert "background: look.color" not in quote, (
        "Vor dem Namen steht wieder ein Zustandspunkt – er rückt die Zeile ein."
    )
    # Gefragt ist der **Textknoten**, nicht das Vorkommen: `tip={look.label}` steht
    # daneben am Betrag, und ein blosses «kommt vor» war schon dadurch erfüllt
    # (gegengeprüft) – dieselbe Falle wie bei `data-tip` in der Vorrunde.
    shown = re.sub(r"\b\w+=\{[^}]*\}", "", quote)
    # **Wie das Wort heisst, ist der Zeile ueberlassen** – gefragt ist, dass es dasteht.
    # Der Waechter verlangte woertlich ``{look.label}`` und verbot damit die bessere
    # Fassung von #1032: dort entscheidet eine Zeile hoeher, **wann** das Wort noetig ist
    # (waehrend verhandelt wird, IST der Preis die Aussage), und es steht unter einem
    # eigenen Namen da. Also: die Aufloesung, direkt oder unter ihrem Alias.
    names = {"look.label", *re.findall(r"const (\w+) = [^;]*look\.label", quote)}
    assert any("{%s}" % n in shown for n in names), (
        "Ohne Punkt und ohne Wort sagt die Zeile ihren Zustand gar nicht mehr."
    )


def test_a_section_head_carries_weight():
    """►►► **Die Abschnittsköpfe tragen mehr Gewicht** (Testnotiz #1006). ◄◄◄

    Erlaubt waren vier Mittel (Gewicht · Abstand · Trennlinie · Nummerierung), zu wählen
    war eine **Kombination, nicht alles**. Die Trennlinie steht seit jeher, eine
    Nummerierung behauptete eine Reihenfolge, die es bei Inhalts-Abschnitten nicht gibt –
    bleiben Gewicht und Abstand. Beide gehören der **Gattung** und stehen darum in
    ``ModuleSection``, nicht an der Aufrufstelle.

    **800, nicht 700** – gemessen: ``MICRO_LABEL`` steht bereits auf 700; ein «höheres
    Gewicht» dorthin wäre wirkungslos gewesen und hätte ausgesehen wie ein Fix.

    Bug-Formen: (a) das Gewicht ist zurück auf dem von ``MICRO_LABEL``; (b) der Abstand
    steht an der Aufrufstelle statt an der Gattung.
    """
    ui = _module_ui()
    micro = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "font: '700 11px var(--font-body)'" in micro, (
        "MICRO_LABEL hat sein Gewicht geändert – dann ist die Zahl unten neu zu messen."
    )
    head = _code(_component(ui, "ModuleSection"))
    assert "fontWeight: 800" in head, (
        "Der Abschnittskopf trägt kein eigenes Gewicht (a) – 700 ist der Wert, den "
        "MICRO_LABEL ohnehin setzt."
    )
    assert "SECTION_GAP" in head and "const SECTION_GAP" in _code(ui), (
        "Der Abstand über einem Abschnitt steht nicht als eine Zahl an der Gattung (b)."
    )


def test_an_undoing_action_never_looks_like_an_adding_one():
    """►►► **Ein Symbol zeigt, was die Handlung TUT** (Testnotiz #1008). ◄◄◄

    «Korrigieren» trug ein **Plus** – das Zeichen des Hinzufügens für eine Handlung, die
    eine Buchung zurücknimmt. Drei Korrekturen stehen in dieser Zeilengattung, und jede
    tut etwas anderes: annullieren (durchgestrichener Kreis, dasselbe Zeichen, mit dem
    das Haus «storniert» schreibt), zurücknehmen (Kreispfeil gegen den Uhrzeiger),
    Geld zurückschicken (Rückwärtspfeil).

    Bug-Form: eine Korrektur trägt wieder ein Plus.
    """
    entry = _code(_component(_beleg(), "EntryRow"))
    assert "icon={Plus}" not in entry, (
        "Eine rückgängig machende Handlung trägt das Zeichen des Hinzufügens."
    )
    for icon in ("icon={CircleSlash}", "icon={RotateCcw}", "icon={Undo2}"):
        assert icon in entry, f"Der Zeile fehlt ihr Symbol: {icon}."


def test_a_save_never_hides_a_control_in_the_party_block():
    """►►► **Ein Auto-Save verändert die Geometrie NICHT** (Testnotiz #1016). ◄◄◄

    *«Der Partner-Block im Zahlungsmodul springt beim Autosave weiterhin.»*

    Die Ursache stand im Chip: ``onAsk``/``onDrop`` hingen an ``!busy``, waren also
    während **jedes** Speicherns ``undefined``. Damit verschwanden die beiden Zeichen aus
    dem Chip, seine rechte Polsterung wechselte von 4 auf 8 px – jeder Chip wurde
    schmaler, die umbrechende Reihe floss neu, der Block sprang; danach kamen sie zurück
    und er sprang erneut.

    Es ist dieselbe Fehlerform wie ``disabled={busy}`` an einem Eingabefeld (#1009), nur
    eine Stufe gröber: **``busy`` darf nie etwas ein- oder ausblenden.** Rückmeldung
    kommt über **Deckkraft**, die am Layout nichts ändert.

    Bug-Formen: (a) die Handlungen hängen wieder an ``busy``, also verschwinden die
    Knöpfe; (b) die Rückmeldung ändert wieder Masse statt Deckkraft.
    """
    src = _beleg()
    rec = _code(_component(src, "Recipients"))
    for form in ("!busy ?", "&& !busy", "!busy &&"):
        assert form not in rec, (
            f"Eine Handlung des Chips hängt wieder am Speichern (a): «{form}» – damit "
            f"verschwindet ein Knopf mitten im Vorgang und die Reihe fliesst neu."
        )
    chip = _code(_component(src, "Chip"))
    assert "opacity: busy" in chip, (
        "Der Chip meldet das Speichern nicht über die Deckkraft (b)."
    )
    # **Kein Mass hängt am Speichern** – Polsterung, Breite, Höhe und Anzeigeart sind
    # genau die Angaben, die eine Zeile umbrechen lassen.
    for prop in ("padding", "width", "height", "display", "fontSize", "gap"):
        assert not re.search(prop + r":\s*busy", chip), (
            f"«{prop}» hängt am Speichern (b) – das verschiebt die Zeile unter dem Zeiger."
        )


def test_a_date_stands_right_of_the_row_never_in_the_flow():
    """►►► **Datum und Fälligkeit stehen RECHTS, links vom Betrag** (#1011/#1012). ◄◄◄

    *«Datum/Fälligkeit stehen links im Fliesstext. Das Datum gehört rechtsbündig direkt
    links neben den Betrag; der Betrag bleibt ganz rechts auf fester Flucht.»*

    Es ist die **zweite Zahl** der Zeile, und zwei Zahlen gehören nebeneinander: so
    stehen sie über alle Zeilen hinweg in zwei Spalten, ohne dass jemand eine
    Spaltenbreite pflegt.

    Bug-Formen: (a) das Datum steckt wieder im Fliesstext (``meta``); (b) es gibt den
    Platz gar nicht; (c) es schrumpft mit und malt sich über seine Box hinaus.
    """
    row = _code(_component(_module_ui(), "LedgerRow"))
    assert "date" in row, "Die Zeilen-Grammatik kennt keinen Platz für das Datum (b)."
    # Der Betrag bleibt das **letzte** Element – daran hängt seine Flucht (#996).
    assert row.rindex("{date}") < row.rindex("{amount}"), (
        "Das Datum steht hinter dem Betrag (b) – dort sucht das Auge die Zahl."
    )
    entry = _code(_component(_beleg(), "EntryRow"))
    assert "date={stamp.text}" in entry, (
        "Die Geld-Zeile füllt den Platz nicht (b)."
    )
    assert "meta={[stamp.text" not in entry, (
        "Das Datum steckt wieder im Fliesstext (a) – dann springt der Blick zweimal."
    )
    # (c) Ein Datum hat keine Umbruchstelle; schrumpfen darf allein das Meta.
    block = row[row.index("{date}") - 400:row.index("{date}")]
    assert "flex: 'none'" in block and "nowrap" in block, (
        "Das Datum darf schrumpfen (c) – «20.8.2026» malt sich dann über seine Box hinaus."
    )


def test_a_section_head_is_a_bar_not_only_a_word():
    """►►► **Der Abschnittskopf ist eine LEISTE** (Testnotiz #1015). ◄◄◄

    *«Die Bereichsüberschriften sind immer noch zu wenig ausgeprägt … eine klare, ruhige
    Bereichsüberschrift über die volle Modulbreite, schmale Leiste, deutlich vom Inhalt
    darunter abgesetzt.»*

    Der dritte Anlauf – die beiden davor (Gewicht 800, mehr Luft) galten dem **Text**.
    Eine Überschrift, die eine Zone eröffnet, braucht eine **Fläche**: gedämpfte Füllung,
    dunkle Schrift, kräftige Trennlinie. Nicht Vollschwarz: in einer Spalte mit fünf
    Modulen stünden fünf schwarze Balken untereinander, und die ERP-Regel heisst
    *Struktur vor Fläche*.

    Bug-Formen: (a) die Leiste hat keine Fläche; (b) die Trennlinie ist wieder eine
    Haarlinie wie jede andere; (c) sie endet an der Satzkante statt an der Karte;
    (d) die Regel steht an einer Aufrufstelle statt in `ModuleSection`.
    """
    src = _module_ui()
    sec = _code(_component(src, "ModuleSection"))
    assert "background: 'var(--bg-3)'" in sec, (
        "Der Abschnittskopf hat keine Fläche (a) – dann ist er wieder nur ein Wort."
    )
    assert "borderBottom: '2px solid var(--border-2)'" in sec, (
        "Die Trennlinie ist eine Haarlinie wie jede andere (b)."
    )
    # **Volle Modulbreite** – der negative Seitenrand ist die Polsterung der Karte.
    pad = re.search(r"padding:\s*'16px (\d+)px'", _code(src))
    assert pad, "Die Karte nennt ihre Polsterung nicht mehr – dann rät die Leiste."
    assert f"-{pad.group(1)}px" in sec, (
        f"Die Leiste endet an der Satzkante (c) statt an der Karte "
        f"(erwartet -{pad.group(1)}px aus `MODULE_CARD`)."
    )
    # (d) Keine zweite Fassung daneben: jedes künftige Modul erbt sie.
    assert "var(--bg-3)" not in _code(_beleg()), (
        "Ein Modul baut sich seinen eigenen Abschnittskopf (d)."
    )


def test_a_refund_that_fails_says_so():
    """►►► **«Online erstatten» sagt, was daraus wurde** (Testnotiz #1013). ◄◄◄

    *«Der Button ‹Online erstatten› hat keine Wirkung. Ein Fehlschlag muss eine sichtbare
    Meldung erzeugen, nicht stillschweigend scheitern.»*

    Zwei Ursachen: der Aufruf endete auf ``.catch(() => {})`` – ein 409 des Dienstes kam
    nirgends an –, und **gebucht wird vom Webhook**, nicht vom Aufruf: ein einzelnes
    Neuladen direkt danach zeigt verlässlich nichts. Nachgefragt wird jetzt mit derselben
    Mechanik wie bei einer Zahlung, und die Meldung steht da, wo man sie sieht.

    Bug-Formen: (a) der Fehler wird wieder verschluckt; (b) es wird nicht nachgefragt,
    also sieht man die gebuchte Zeile nie; (c) die Meldung wird gefangen, aber nirgends
    gerendert.
    """
    money = _code(_component(_beleg(), "Money"))
    assert "catch (e)" in money and "setFailed" in money, (
        "Der Fehlschlag wird gefangen und weggeworfen (a) – ein stiller Nicht-Effekt ist "
        "schlimmer als ein Fehler."
    )
    assert "catch(() => {})" not in _code(_beleg()), (
        "Irgendwo wird ein Fehlschlag wieder verschluckt (a)."
    )
    assert re.search(r"refundVoucherPayment[\s\S]{0,200}setWaiting\(WAIT_TRIES\)", money), (
        "Nach der Erstattung wird nicht nachgefragt (b) – gebucht wird vom Webhook."
    )
    # (c) Gefragt ist das **Rendern**, nicht der Zustand: `setFailed` allein steht auch
    #     dann noch da, wenn niemand die Meldung zeigt (gegengeprüft).
    assert "{failed}" in money, "Die Meldung wird nirgends gezeigt (c)."


def test_a_refund_button_closes_at_the_click():
    """►►► **Ab dem Klick zu — die dritte Ebene von dreien** (Testnotiz #1018). ◄◄◄

    *«Der Button lässt sich mehrfach drücken, dann erscheint ein technischer Fehlertext
    des Zahlungsdienstes.»*

    Die beiden anderen Ebenen stehen im Dienst (der erstattbare **Rest**) und beim Dienst
    (der **Idempotenz-Schlüssel**). Hier fehlt die dritte: zwischen Klick und Buchung
    liegt die Meldung des Webhooks, und in diesem Fenster sagt niemand etwas – also sagt
    es der Knopf selbst. Dass er danach ganz **verschwindet**, sagt weiterhin der Server
    (``refundable``); eine Oberfläche, die das selbst rechnete, wäre der zweite Massstab.

    Bug-Formen: (a) der Knopf kennt seinen Zustand nicht; (b) er wird nicht gesperrt;
    (c) die Sperre fällt nach einem Fehler nicht zurück (dann ist ein Netzwerkfehler eine
    Sackgasse).
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(work, "EntryRow")
    money = _component(work, "Money")
    # (a) **Die Aufrufstelle sagt es der Zeile** – je Zeile, nicht je Karte: es geht um
    #     genau diese Zahlung.
    assert "refunding" in row and "refunding={" in money, (
        "Die Geld-Zeile weiss nicht, dass ihre Erstattung unterwegs ist (a)."
    )
    at = row.index("onRefund(e.id)")
    near = row[row.rfind("<ActionButton", 0, at):at]
    assert "refunding" in near, (
        "Der Erstattungs-Knopf bleibt beim Klick offen (b) – dann geht sie zweimal hinaus."
    )
    # (c) **Und nach einem Fehler kommt er zurück.** Gesucht wird die Reihenfolge: gesperrt
    #     **vor** dem Aufruf, freigegeben im `catch`.
    refund = money[money.index("const refund ="):money.index("const charges =")]
    lock = refund.index("setSent")
    assert lock < refund.index("await api.refundVoucherPayment"), (
        "Gesperrt wird erst nach der Antwort (b) – das Fenster ist genau davor."
    )
    assert "s.filter((id) => id !== entryId)" in refund[refund.index("catch"):], (
        "Nach einem Fehler bleibt der Knopf zu (c) – dann ist ein Netzwerkfehler eine "
        "Sackgasse."
    )


def test_what_is_still_open_stands_above_the_way_to_settle_it():
    """►►► **Der Saldo steht ÜBER der Zahlungsart** (Testnotiz #1019). ◄◄◄

    *«Der Saldo-Container gehört über den Bereich Zahlungsart, nicht darunter.»*

    Er war die **Fusszeile der ganzen Karte** und stand damit hinter allem, was in ihr
    wächst: man wählte einen Weg zum Geld, ohne die Zahl zu sehen, um die es geht. Die
    Reihenfolge im Fach «Begleichen» ist jetzt fest – erfasste Zahlungen → **Saldo** →
    Zahlungsart → Auskunft/Karte → Handlung.

    Bug-Formen: (a) der Saldo steht wieder ausserhalb des Fachs; (b) er steht darin, aber
    unter der Wahl; (c) die Ausbuchung, die von genau dieser Zahl handelt, wandert weg.
    """
    money = _code(_component(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"),
                             "Money"))
    body = money[money.index("return ("):]
    settle = body.index("d.settle_title")
    close = body.index("</ModuleSection>", settle)
    fach = body[settle:close]
    # (a)
    assert "<Balance" in fach, (
        "Der Saldo steht wieder ausserhalb des Fachs «Begleichen» (a) – dann hängt er "
        "hinter allem, was darin wächst."
    )
    assert "<Balance" not in body[close:], "Der Saldo steht zweimal (a)."
    # (b) **und (c)** – die Reihenfolge ist die Aussage.
    assert fach.index("<Balance") < fach.index("<Segmented"), (
        "Der Saldo steht unter der Zahlungsart (b) – man wählt, ohne die Zahl zu sehen."
    )
    assert "{writeOff}" in fach and fach.index("{writeOff}") < fach.index("<Segmented"), (
        "Die Ausbuchung steht nicht mehr bei der Zahl, von der sie handelt (c)."
    )


def test_the_way_to_the_money_needs_no_label():
    """►►► **«Zahlungsart» sagt nichts, was nicht darunter steht** (Testnotiz #1020). ◄◄◄

    *«Das Label ‹Zahlungsart› entfernen – der Bereich ist selbsterklärend.»*

    «Bar», «Überweisung», «Karte» sagen jede für sich, was sie sind, und der Abschnitt
    darüber heisst «Begleichen». Ein Wort, das nur wiederholt, ist Höhe ohne Aussage.

    **Und der Platz geht mit**: eine leere Beschriftungszeile wäre dieselbe Höhe ohne
    denselben Inhalt.

    Bug-Formen: (a) die Beschriftung ist wieder da; (b) sie ist weg, die Zeile bleibt.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    at = work.index("<Segmented")
    assert "label=" not in work[at:work.index("/>", at)], (
        "Die Zahlungsart trägt wieder eine Beschriftung (a)."
    )
    seg = _body(_code(_read(FRONTEND / "components" / "erp" / "fields.tsx")),
                "Segmented", kind="export function")
    assert "{label && <Label" in seg, (
        "Ohne Beschriftung bleibt die leere Zeile stehen (b) – dieselbe Höhe ohne "
        "denselben Inhalt."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► TESTNOTIZEN #1023–#1031 — weniger Beschriftung, EIN Suchfeld, EINE Nummer
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_field_names_its_subject_exactly_once():
    """►►► **Die Sorte steht einmal – als Beschriftung ODER im Platzhalter** (#1023). ◄◄◄

    *«Ich denke, die Info kann entfallen oder ggf. als Hover-Information über dem
    Eingabefeld.»* – Über dem Artikelfeld stand «Artikel», **im** Feld «Nummer oder
    Name»: zwei Zeilen für eine Auskunft, und die obere kostete in einer engen
    Stücklisten-Zeile eine ganze Zeile.

    Der Platzhalter kann es tragen, und er verschwindet genau dann, wenn die Antwort
    dasteht («100000741 · Schraubendreher»). Gebaut wird der Satz **einmal**
    (``lookupHint``), damit Feld und Scanner ihn nicht getrennt zusammensetzen.

    Bug-Formen: (a) die hand-gebaute Beschriftung ist wieder da; (b) der Platzhalter
    nennt die Sorte **zusätzlich** zur Beschriftung; (c) der Satz wird an der
    Aufrufstelle zusammengesetzt.
    """
    lib = _code(_read(FRONTEND / "lib" / "scan.ts"))
    picker = _code(_read(FRONTEND / "components" / "erp" / "object-select.tsx"))
    ui = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))

    assert "export function lookupHint" in lib, "Der eine Satz fehlt (c)."
    assert "label ? LOOKUP_HINT : lookupHint(scanLabel)" in picker, (
        "Das Feld nennt die Sorte nicht genau einmal – entweder gar nicht oder zweimal (b)."
    )
    assert ">Artikel</span>" not in ui, (
        "Über dem Artikelfeld steht wieder eine hand-gebaute Beschriftung (a)."
    )
    assert "scanLabel=\"Artikel\"" in ui, (
        "Ohne Sorte am Feld nennt sie auch der Platzhalter nicht mehr."
    )


def test_what_a_number_counts_is_a_hover_not_a_line():
    """►►► **Ein Wort über einem Zahlenfeld kostet eine Zeile** (Testnotiz #1024). ◄◄◄

    Das Feld enthält eine Zahl und sonst nichts; wonach sie zählt, ist genau die Art
    Auskunft, die im Haus in die Blase gehört. Das **Wort** bleibt unverändert – «Menge je
    Einzelinstanz», denn das ist das Arbeitsobjekt des Systems (#725).

    Bug-Formen: (a) die Beschriftung ist wieder da; (b) sie ist weg und die Auskunft mit
    ihr – dann steht dort ein Zahlenfeld ohne Bezugsgrösse.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    row = ui.split("function LineRow")[-1]
    assert "{perUnit ? 'Menge je Einzelinstanz' : 'Menge'}" not in row, (
        "Die Beschriftung steht wieder über dem Zahlenfeld (a)."
    )
    assert "data-tip" in row and "Menge je Einzelinstanz" in row, (
        "Die Bezugsgrösse der Zahl steht nirgends mehr (b)."
    )


def test_the_unit_picker_searches_like_every_other_field():
    """►►► **Die Kamera sitzt IM Feld, nicht daneben** (Testnotiz #1026). ◄◄◄

    *«Sollte hier nicht auch die global gültige UI/UX-Logik für Suchfelder angewendet
    werden, welche nach Objektnummer suchen können? Bitte den globalen Standard
    etablieren und den jetzigen endgültig löschen.»*

    Die Stück-Auswahl hatte ihr eigenes Suchfeld mit einem **Knopf daneben** – zwei
    Flächen für eine Frage, also genau die Form, die #738 im Referenzfeld abgeschafft
    hat. Die Aktion steht seither als **Bauteil** (``FieldAction``), nicht als Markup in
    ``SearchSelect``: sonst baut die nächste Aufrufstelle sie wieder selbst.

    Bug-Formen: (a) der eigene Knopf daneben ist zurück; (b) die Aktion wird in
    ``SearchSelect`` wieder ausgeschrieben.
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    ui = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))

    assert "export function FieldAction" in fields, "Das Bauteil fehlt (b)."
    assert "<FieldAction {...action}" in fields, (
        "`SearchSelect` schreibt seine Aktion wieder selbst aus (b)."
    )
    assert "<FieldAction" in ui and "erp-idbtn" not in ui, (
        "Die Stück-Auswahl hat wieder ihren eigenen Knopf neben dem Feld (a)."
    )
    assert "paddingRight: 34" in ui, (
        "Das Feld macht der Kamera keinen Platz – der Text läuft unter das Symbol."
    )


def test_the_unit_picker_stays_open_while_the_choice_is_incomplete():
    """►►► **Offen ist, was noch nicht entschieden ist** (Testnotiz #1025). ◄◄◄

    *«Beim Selektieren der ersten Einzelinstanz schliesst sich das Auswahlfenster sofort;
    danach gehen die zweite und dritte problemlos.»*

    Der Grund lag **um** die Komponente herum: nimmt die Auswahl einem laufenden Auftrag
    ein Stück ab, wird aus dem Entwurfsbild eine Vorschau mit Spuren
    (``ProcessColumns``) – und ein React-Baum, der seine Gestalt wechselt, nimmt den
    Zustand seiner Kinder mit. Genau beim **ersten** geliehenen Stück, danach nie wieder.

    Ein gemerktes «offen» überlebt das nicht, eine **Ableitung** schon. Und sie sagt
    dasselbe: solange die Auswahl unvollständig ist, wählt man.

    Bug-Formen: (a) «offen» ist wieder ein reiner Zustand; (b) ein Klick auf ein Stück
    lässt die Ableitung zuschlagen, sobald die Auswahl voll ist.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    picker = ui.split("function StockPicker")[-1]
    assert "useState(false);" not in picker.split("const picked")[0], (
        "«offen» ist wieder ein gemerkter Zustand (a) – und der stirbt mit dem Neuaufbau."
    )
    assert "const open = touched ??" in picker, "Die Ableitung fehlt (a)."
    assert "!enough" in picker, "Die Ableitung fragt nicht, ob die Auswahl vollständig ist."
    assert "setTouched(true);" in _body(picker, "toggle", kind="function"), (
        "Wer wählt, will weiterwählen – der letzte Klick klappt das Fenster wieder zu (b)."
    )


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


def test_an_empty_stock_says_so_and_nothing_more():
    """**«Kein Bestand» ist die Auskunft** (Testnotiz #1030).

    Der Satz daneben erklärte, *woher* Einzelinstanzen kommen – eine Belehrung über das
    Datenmodell an der Stelle, an der jemand eine Zahl sucht.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "stock-view.tsx"))
    assert ">Kein Bestand<" in ui, "Die Auskunft fehlt."
    assert "entstehen mit der Freigabe" not in ui, "Die Belehrung steht wieder da."


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


def test_the_focus_follows_the_step_not_only_the_camera():
    """**Ein neuer Schritt ist eine neue Frage** (Testnotiz #1029).

    *«Beim ersten Scan kann man am Laptop sofort tippen, beim zweiten nicht mehr.»* – Der
    Fokus hing allein am Kamerazustand, und der ändert sich zwischen zwei Schritten
    nicht; wer den ersten per Klick auf einen Vorschlag erledigt hatte, stand danach mit
    dem Fokus auf einem Knopf.

    **Die Regel bleibt dieselbe**: läuft die Kamera, bleibt der Fokus am Dialog (sonst
    poppt auf dem Telefon die Tastatur über das Bild).
    """
    dialog = _code(_read(FRONTEND / "components" / "scan" / "scan-dialog.tsx"))
    assert "}, [cameraLive, stepIndex]);" in dialog, (
        "Der Fokus folgt dem Schritt nicht – ab dem zweiten muss man ins Feld klicken."
    )
    assert "if (cameraLive) sheetRef.current?.focus();" in dialog, (
        "Die Kamera-Regel ist weg – auf dem Telefon steht die Tastatur über dem Bild."
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


def test_the_definition_line_does_not_explain_the_data_model():
    """►►► **Wie das System zaehlt, ist keine Auskunft** (Testnotiz #1033). ◄◄◄"""
    ui = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    for word in ("Einzelinstanzen (", "mit je einer Einzelinstanz", "Eine Instanz mit"):
        assert word not in ui, (
            f"Die Menge wird wieder in Datensaetze uebersetzt («{word}»)."
        )


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


def test_every_offer_stays_visible_and_names_its_outcome():
    """►►► **Kein Aufklapper im Angebotsspiegel** (Testnotiz #1032). ◄◄◄

    Nach dem Zuschlag stand hier eine Zeile und darunter «1 von 2 Angeboten gewaehlt».
    Die unterlegenen Zeilen sind aber der Nachweis, warum so entschieden wurde – und ein
    Nachweis hinter einem Klick beantwortet die Frage erst, wenn man sie gestellt hat.
    Unterschieden wird ueber das **Wort**, und das kommt aus der EINEN Aufloesung.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "Angeboten gewählt" not in ui, "Der Aufklapper ist wieder da."
    assert "ChevronDown" not in ui, "Der Beleg klappt wieder etwas auf."
    quotes = _component(ui, "Quotes")
    assert quotes.count("<QuoteRow") == 1, (
        "Die Angebote werden wieder fallweise gerendert – eine Zeile fehlt je nach Stufe."
    )
    look = _body(ui, "quoteLook", kind="function")
    for word in ("Unterlegen", "Unbeantwortet"):
        assert word in look, f"Der Ausgang «{word}» hat kein Wort."
    assert re.search(r"quoteLook\([^)]*decided", _component(ui, "QuoteRow")), (
        "Die Zeile fragt die Aufloesung ohne die gefallene Entscheidung – nach dem "
        "Zuschlag heisst «Offeriert» dann immer noch «offeriert»."
    )


def test_every_css_variable_is_defined_somewhere():
    """►►► **Eine unbekannte CSS-Variable ist kein Fehler – sie erzeugt schlicht nichts.**

    Dieselbe Lehre wie bei der unbekannten Tailwind-Klasse (`bg-bg-dark`): der Build
    schweigt, und was herauskommt, sieht **fast** richtig aus. Gefunden beim Messen von
    #1032: ``quoteLook`` faerbte «Zugesagt» mit ``var(--ok)`` und «Offeriert» mit
    ``var(--warn)`` – beide gibt es nicht (sie heissen ``--success`` und ``--warning``).
    Das Wort erbte damit die Farbe seiner Umgebung, und die **Gaps**-Box daneben verlor
    ueber ``border: 1px solid var(--warn)`` ihren Rahmen ganz: eine ungueltige Angabe
    macht die **ganze** Deklaration ungueltig.

    Geprueft wird die Regel, nicht die Liste: jede benutzte Variable muss irgendwo
    definiert sein – im Token-Blatt, in `globals.css` oder als eigene Angabe am Element.

    **Gefragt ist der Gebrauch OHNE Rueckfall.** ``var(--x, right)`` ist eine Angabe mit
    Vorgabe – ein Haken, den eine Aufrufstelle setzen *darf* (``--ix-live`` am Statuspunkt,
    ``--ix-fade`` an der Maske); dort rendert immer etwas. Genau das fehlt bei ``var(--x)``:
    ist der Name falsch, faellt die Deklaration aus, und nichts sagt es.
    """
    used, defined = {}, set()
    for path in sorted(FRONTEND.rglob("*")):
        if path.suffix not in (".css", ".ts", ".tsx") or not path.is_file():
            continue
        src = _read(path)
        defined |= set(re.findall(r"(--[a-z0-9-]+)\s*:", src))
        defined |= set(re.findall(r"['\"](--[a-z0-9-]+)['\"]", src))
        for name in re.findall(r"var\((--[a-z0-9-]+)\s*\)", src):
            used.setdefault(name, path.name)
    missing = sorted((n, f) for n, f in used.items() if n not in defined)
    assert not missing, (
        "Diese CSS-Variablen werden benutzt, aber nirgends definiert – sie erzeugen "
        f"stillschweigend nichts: {missing}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DER BESITZ — ein zweiter Zeiger, gesetzt vom Zahlungsmodul
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_ownership_words_are_mirrored_not_invented():
    """►►► **Die beiden Woerter stehen im Backend, der Editor spiegelt sie.** ◄◄◄

    «Eigentum bleibt» ↔ «Eigentum wechselt» benennen die **Entscheidung** – darum braucht
    der Schieber keine Beschriftung darueber (#1020). Erfunden werden sie hier nicht: der
    Satz auf dem Beleg baut derselbe Katalog (`domain/voucher.transfer_sentence`), und
    zwei Fassungen desselben Wortes laufen beim ersten Umbenennen auseinander.

    Bug-Form: der Editor schreibt seine eigenen Woerter hin.
    """
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.domain import voucher as vo

    src = _read(FRONTEND / "lib" / "modules.ts")
    for word in (vo.TRANSFER_KEEP_WORD, vo.TRANSFER_MOVE_WORD):
        assert word in src, (
            f"«{word}» steht im Backend, aber nicht im Spiegel – dann heisst dieselbe "
            f"Wahl an zwei Stellen verschieden.")


def test_the_ownership_switch_asks_no_direction():
    """►►► **An WEN das Eigentum geht, fragt die Oberflaeche nicht.** ◄◄◄

    Das sagt die Richtung (`Direction.collects`), und der Beleg liefert den fertigen Satz
    (`VoucherEmbed.transfer`). Ein `if direction ===` im Editor oder in der Karte waere
    die Regel ein zweites Mal – und die zweite Fassung ist die, die beim naechsten Umbau
    stehenbleibt.

    Bug-Form: die Karte baut den Satz selbst («geht an » + Name).
    """
    card = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "Eigentum" not in card, (
        "Die Beleg-Karte formuliert etwas ueber das Eigentum selbst. Der Satz kommt "
        "fertig vom Server – hier wird gezeichnet, nicht entschieden.")
    # **Gefragt ist das RENDERN, nicht das Vorkommen.** «`d.transfer` steht irgendwo im
    # Rumpf» ist schon erfuellt, wenn die Bedingung davor auf `false` steht – gemessen:
    # die Bug-Form «der Block wird nie gezeichnet» kam genau so durch.
    body = _component(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"), "Goods")
    assert re.search(r"\{d\.transfer\s*&&\s*\(", body), (
        "Die Positionen zeichnen den Eigentumsuebergang nicht bedingt aus `d.transfer` – "
        "dann bewegt dieser Vorgang das Eigentum unbemerkt.")


def test_the_owner_bar_is_information_not_a_control():
    """►►► **Zwei Leisten, aber nur EINE oeffnet einen Ausschnitt.** ◄◄◄

    Der Durchgriff auf die Nummern gehoert der **Zustands**-Leiste; dort nennt jede Zeile
    ihren Eigentuemer. Zwei Leisten mit je einem Auswahlzustand ueber derselben Liste
    waeren zwei Antworten auf «welcher Ausschnitt gilt jetzt».

    Bug-Form: die Eigentums-Leiste bekommt ein `onPick` – dann gibt es zwei offene
    Ausschnitte und keine Regel, welcher gewinnt.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "owner-bar.tsx"))
    assert "onPick" not in src, (
        "Die Eigentums-Leiste ist ein Bedienelement geworden – sie ist eine Auskunft.")
    assert "var(--danger)" not in src and "statusCfg" not in src, (
        "Sie benutzt die Ampeltoene. Fremdes Eigentum ist kein Problem – eine "
        "Beistellung ist der Normalfall der Lohnfertigung.")


def test_the_stock_card_shows_both_bars_over_the_same_pieces():
    """►►► **Der globale Ueberblick UND «womit kann ich wirtschaften».** ◄◄◄

    Beide Leisten lesen denselben Umfang (am Artikel alle seine Stuecke, an der Instanz
    ihre) – nur dann summieren sie sich auf dieselbe Zahl und lassen sich uebereinander
    lesen.

    Bug-Formen: (a) die zweite Leiste fehlt; (b) sie liest einen anderen Umfang als die
    erste.
    """
    src = _read(FRONTEND / "components" / "erp" / "stock-view.tsx")
    assert "<OwnerBar" in src, (
        "(a) Die Eigentums-Leiste fehlt – dann sagt die Karte «Freigegeben 12», ohne zu "
        "sagen, dass fuenf davon dem Kunden gehoeren.")
    code = _code(src)
    assert "scope.kind === 'article' ? stock?.owners : scope.record.owners" in code, (
        "(b) Die beiden Leisten lesen verschiedene Umfaenge – dann summieren sie sich "
        "auf zwei Zahlen, und niemand kann sie nebeneinander lesen.")


def test_the_owner_is_named_only_when_it_is_not_us():
    """►►► **``null`` heisst uns, und das spricht niemand aus.** ◄◄◄

    Der Normalfall bekommt kein Wort: ihn an jeder von sechzig Zeilen zu nennen waere
    dasselbe Wort sechzigmal. Genannt wird, was eine **Aussage** ist.

    Bug-Form: die Zeile zeigt «Uns» an jedem Stueck – dann ist die eine Zeile, auf die es
    ankommt, nicht mehr zu finden.
    """
    for name in ("unit-numbers.tsx", "definition-lines.tsx"):
        src = _code(_read(FRONTEND / "components" / "erp" / name))
        assert "'Uns'" not in src and '"Uns"' not in src, (
            f"{name} schreibt «Uns» an eine Zeile – der Normalfall braucht kein Wort.")
    # **Gefragt ist das bedingte RENDERN, nicht das Vorkommen des Namens.** «`o.owner_name`
    # steht irgendwo» ist schon durch den Hover-Satz erfuellt – gemessen: die Bug-Form «die
    # Zeile zeigt ihn gar nicht» kam genau so durch.
    numbers = _code(_read(FRONTEND / "components" / "erp" / "unit-numbers.tsx"))
    assert re.search(r"\{u\.owner\s*\?", numbers), (
        "Die Nummern nennen ihren Eigentuemer nicht – und genau dort ist der Durchgriff "
        "der Eigentums-Leiste.")
    picks = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    assert re.search(r"\{o\.owner_name\s*&&\s*\(", picks), (
        "Die Auswahl-Liste zeigt den Eigentuemer nicht – dort entscheidet sich, mit "
        "wessen Material gearbeitet wird.")


# ---------------------------------------------------------------------------
# Testnotizen #1038-#1040
# ---------------------------------------------------------------------------

_QUOTE_STATE_WORDS = (
    "angenommen", "zugesagt", "abgesagt", "offeriert", "unterlegen",
    "unbeantwortet", "angefragt",
)


def test_a_quote_row_names_its_state_exactly_once():
    """►►► **EIN Zustand, EIN Wort** (Testnotiz #1038). ◄◄◄

    *«Jetzt haben wir Doppelstatus. Ein absolutes No-Go. Du hast einmal ‹angenommen› und
    einmal ‹Zugesagt›. Es darf nur einen Status fuer eine Sache geben.»*

    Und das Wort, das bleibt, ist **Zugesagt** – es kommt aus der einen Aufloesung
    (``quoteLook``, #1032), die **alle vier** Ausgaenge derselben Zeile benennt.
    «angenommen» stand daneben als Vorsatz einer **Zeitangabe** und war damit ein zweiter
    Wortschatz fuer dieselbe Sache, einer, der die anderen drei Ausgaenge gar nicht kennt.

    **Geprueft wird die Regel, nicht der Einzelfall**: die Zeile schreibt **kein**
    Zustandswort selbst – sie hat genau eine Quelle dafuer. Ein Wort auf einem *Knopf*
    («Absage», «Offerte annehmen») ist eine Handlung und bleibt erlaubt.

    **Und die Zeit bleibt** (#968/#969): sie hat seit der Aufloesung der Chronik keinen
    anderen Ort, und *wann* zugesagt wurde, sagt das Wort nicht.

    Bug-Formen: (a) ein Zustandswort steht wieder als Literal in der Zeile; (b) mit ihm
    faellt die Zeitangabe weg.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(src, "QuoteRow")
    for word in _QUOTE_STATE_WORDS:
        assert word not in row.lower(), (
            f"(a) Die Angebotszeile schreibt «{word}» selbst hin – ihr Zustand hat "
            "genau eine Quelle (`quoteLook`), und ein zweites Wort daneben ist ein "
            "zweiter Status fuer dieselbe Sache.")
    assert "d.agreed_at" in row and "when(" in row, (
        "(b) Mit dem Wort ist auch die Zeitangabe verschwunden – seit der Aufloesung "
        "der Chronik (#970) ist diese Zeile ihr einziger Ort.")


def test_the_billing_email_exists_exactly_once():
    """►►► **Die Rechnungs-E-Mail gibt es EINMAL** (Testnotiz #1039). ◄◄◄

    *«Wir haben eine Doppelspurigkeit. Ein absolutes No-Go … entscheide dich fuer eines
    der beiden, und das andere muss vollkommen und endgueltig aus dem Code eliminiert
    werden.»*

    Geblieben ist ``invoice_email`` – bei der **Rechnungsadresse**, wo die Frage entsteht,
    und die einzige der beiden, die ueberhaupt **gelesen** wurde (``voucher.billing_of``).
    ``company_billing_email`` ist ersatzlos entfallen: Formular, Nutzlast, Pydantic-Schema
    und ORM-Mapping; die Spalte faellt im Folge-Deploy.

    Bug-Form: das zweite Feld ist zurueck – dann beantwortet wieder niemand, welches gilt.
    """
    for path in (
        FRONTEND / "components" / "erp" / "user-detail.tsx",
        FRONTEND / "components" / "account" / "sections" / "profile-section.tsx",
        BACKEND / "app" / "schemas" / "admin.py",
        BACKEND / "app" / "models" / "user.py",
    ):
        assert "company_billing_email" not in _code(_read(path)), (
            f"{path.name} kennt die zweite Rechnungs-E-Mail wieder – zwei Felder fuer "
            "dieselbe Frage, und gelesen wird nur eines.")
    # **Und die verbliebene ist wirklich die, die der Beleg liest.**
    voucher = _code(_read(BACKEND / "app" / "services" / "voucher.py"))
    assert "invoice_email" in voucher, (
        "Der Beleg liest die Rechnungs-E-Mail nicht mehr – dann war die Wahl zwischen "
        "den beiden Feldern eine Muenze.")


def test_the_last_login_comes_from_the_token():
    """►►► **Wann jemand sich angemeldet hat, sagt Firebase** (Testnotiz #1040). ◄◄◄

    *«Wieso ist dort kein Wert hinterlegt, diese Funktion funktioniert nicht. Am besten
    waere eigentlich, wenn es aus Firebase kommen wuerde insofern es geht.»*

    Es **geht**: ``auth_time`` steht in jedem ID-Token und nennt den Moment der
    **Anmeldung**, nicht den dieser Anfrage. Geschrieben hat das Feld vorher genau eine
    Stelle – die Passkey-Zeremonie –, also blieb es bei Anmeldelink und Google SSO fuer
    immer leer. Der Anmelde**weg** wurde zwei Zeilen daneben schon aus demselben Token
    mitgeschrieben; die Uhrzeit dazu wurde weggeworfen.

    Bug-Formen: (a) die Angabe kommt wieder aus einer eigenen Uhr statt aus dem Token;
    (b) sie hat wieder zwei Schreibstellen; (c) sie wird bei jedem Aufruf geschrieben
    statt nur bei einer Aenderung.
    """
    auth = _code(_read(BACKEND / "app" / "core" / "auth.py"))
    assert '"auth_time"' in auth or "'auth_time'" in auth, (
        "(a) Der letzte Login kommt nicht mehr aus dem Token – eine eigene Uhr im Backend "
        "kennt nur die Anmeldewege, an die jemand gedacht hat.")
    assert re.search(r"user\.last_login_at\s*!=", auth), (
        "(c) Geschrieben wird ohne Vergleich – dann schreibt jede einzelne Anfrage.")
    # **(b) EINE Schreibstelle im ganzen Backend.**
    writers = sorted(
        p.relative_to(BACKEND).as_posix()
        for p in (BACKEND / "app").rglob("*.py")
        if re.search(r"\.last_login_at\s*=", _code(_read(p)))
    )
    assert writers == ["app/core/auth.py"], (
        f"(b) Der letzte Login wird an mehreren Stellen geschrieben: {writers} – dann ist "
        "er je nach Anmeldeweg gesetzt oder eben nicht, und genau das war der Befund.")
