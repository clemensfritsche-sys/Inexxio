"""Quelltext-Wächter: Datenmodell, Prozesslogik, Prozessbild, Editor, Abweichung,
Aussondern, Bewegen, Verbrauch.
"""

import re

from tests._source import (
    _feed,
    _diagram,
    _kit,
    BACKEND,
    FRONTEND,
    ROOT,
    _beleg,
    _body,
    _code,
    _read,
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
    for name in ("flow-column.tsx", "module-card.tsx", "order-detail.tsx", "stock-view.tsx",
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
    diagram = _code(_diagram())
    assert "statusCfg" in diagram, "Das Diagramm färbt nicht über die zentrale Zuordnung."


def test_the_process_diagram_is_one_component_with_two_modes():
    """EINE Komponente für Definition und Ausführung (§8.1).

    Zweimal zu bauen wäre an dieser Stelle der teuerste Fehler: der Artikel-Reiter
    «Erzeugungsprozess» ist dieselbe Darstellung, und ein zweites Bauteil liefe beim
    ersten Design-Wechsel auseinander.
    """
    src = _diagram()
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
    diagram = _diagram()
    assert "GraphUnits" in diagram and "g.count" in diagram
    # Der Deckel steht dort, wo die Historie jetzt steht: **am Prozessobjekt** (§5).
    assert "von ${total} Einträgen" in diagram, "Der Deckel der Historie wird verschwiegen."


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
    for name in ("flow-column.tsx", "module-card.tsx", "process-designer.tsx", "order-detail.tsx"):
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
    diagram = _diagram()
    log = _body(diagram, "historyTip", kind="export function")
    assert "e.step_id === node.at" in log, (
        "Die Historie löst den Schritt nicht über seine ID auf."
    )
    assert "s.name" not in log, "Die Historie beschriftet wieder über einen Namen."
    assert "EventLog" not in _read(FRONTEND / "components" / "erp" / "order-detail.tsx"), (
        "Die History-Box ist zurück – sie sollte am Objekt stehen, nicht darunter."
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
    assert "touchedBy(path)" in hook and "invalidateQueries" in hook, (
        "Der Feed hört nicht auf die Meldung – oder lädt ohne Blick auf den Pfad."
    )
    assert "detail: { path }" in api, "Die Meldung nennt den Pfad nicht."
    feed = _feed()
    assert "inexxio:data-changed" not in feed and "DATA_CHANGED" not in feed, (
        "Der Feed hört selbst auf die Meldung – das ist der zweite Weg."
    )
    for kind in ("UserProfile", "Article", "OrderSummary", "InstanceSummary",
                 "CompanySettings", "DocumentSummary"):
        assert f"useState<{kind}[]>" not in feed, (
            f"Die Liste «{kind}» lebt neben React Query in einem eigenen Zustand."
        )
    # Und kein zweiter Melde-Weg in den Detailfenstern.
    for name in ("order-detail.tsx", "article-detail.tsx", "instance-detail.tsx", "documents.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        assert "inexxio:data-changed" not in src and "DATA_CHANGED" not in src, (
            f"{name} hört selbst auf Schreibvorgänge – das ist der zweite Weg."
        )


#: Eine lesende Anfrage, deren Antwort in einen eigenen Zustand geht (`.then(setX)` oder
#: `.then((r) => { … setX(r) })`) – die Form der zweiten Datenquelle neben React Query.
_READ_INTO_STATE = re.compile(
    r"\bapi\.(?:get\w+|documentsOf|paymentsOf|personNewsletter|messageChannels|mailboxes"
    r"|validate\w+|stepRecord|timeView|timePreview)\([^;]*?\)\s*"
    r"\.then\(\s*(?:set[A-Z]\w*\s*\)|\(?\w*\)?\s*=>[^;]*?\bset[A-Z])")


def test_a_detail_view_reads_through_react_query_only():
    """Die Detailansichten lesen über React Query (`lib/queries.ts`), invalidiert an EINER
    Stelle (`lib/feed.TOUCHES`). Eine Antwort, die in einen eigenen Zustand geht, ist die
    zweite Datenquelle: sie veraltet nach einem Schreibvorgang, und eine ältere Antwort kann
    eine neuere überholen. Ebenso eine Liste eines API-Typs in `useState` – sie lebt neben
    der Query."""
    for path in sorted((FRONTEND / "components" / "erp").glob("*-detail.tsx")):
        src = _read(path)
        hit = _READ_INTO_STATE.search(src)
        assert not hit, (
            f"{path.name}: «{hit.group(0)[:60]}…» legt eine Antwort in einen eigenen Zustand – "
            "das gehört in eine Query (lib/queries.ts)."
        )
        m = re.search(r"import type \{([^}]*)\} from '@/types'", src)
        api_types = {t.strip().split(" as ")[-1] for t in (m.group(1).split(",") if m else []) if t.strip()}
        for t in api_types:
            assert f"useState<{t}[]>" not in src, (
                f"{path.name}: die Liste «{t}» lebt neben React Query in einem eigenen Zustand."
            )


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

    diagram = _diagram()
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
    fields = _kit()
    assert "export function RecordIcon(" in fields
    assert "deviation" in _body(fields, "RecordIcon", kind="function")

    page = _feed()
    assert "<RecordIcon" in page, "Der Feed baut das Symbol selbst."
    assert "Abweichung" not in _code(page), "Im Feed steht das Label noch als Text."

    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert re.search(r"deviation=\{\w+\?\.is_deviation", detail), "Der Kopf trägt das Zeichen nicht."


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
    page = _feed()
    assert "onCreate('order', { articleObjectId })" in page and "onCreate: startCreate" in page
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
    diagram = _diagram()
    assert "startedAt" in diagram, "Der Hover zeigt den Zeitpunkt nicht."


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
    diagram = _code(_diagram())
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
    diagram = _code(_diagram())
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
    diagram = _code(_diagram())
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
