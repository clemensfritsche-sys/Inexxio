"""Quelltext-Wächter: das Modul «Datenerfassung» (Scan, Stichprobe, Erfassungspunkte).
"""

from tests._source import (
    BACKEND,
    FRONTEND,
    _body,
    _code,
    _read,
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


# ---------------------------------------------------------------------------
# Testrunde 7.8.2026 nachmittags (#689–#700)
# ---------------------------------------------------------------------------


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


def test_the_scan_button_hangs_on_the_sample():
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


# ---------------------------------------------------------------------------
# Testnotizen #726–#733 – die Runde nach dem Bewegen-Modul
# ---------------------------------------------------------------------------


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


def test_only_the_export_proof_is_uploaded_and_in_one_call():
    """**Der Ausfuhrnachweis wird hochgeladen (PDF oder Bild), jedes Foto bleibt eine
    Aufnahme** – und ein Upload meldet Nummer und Link in EINEM Aufruf (Chrome-Test).

    Bug-Formen: (a) der Ausfuhrnachweis verlangt wieder die Kamera; (b) die Aufnahme bekommt
    einen Dateidialog; (c) Nummer und Link kommen in zwei Aufrufen – der zweite schrieb auf
    den alten Formularstand, die Nummer ging verloren, «Buchen» blieb gesperrt.
    """
    invoice = _code(_read(FRONTEND / "components" / "erp" / "beleg" / "invoice.tsx"))
    proof = invoice[invoice.index("function ExportProof"):]
    proof = proof[: proof.index("\nfunction ", 1)]
    assert "<FileUpload" in proof and "<PhotoShot" not in proof, "(a)"
    upload = _code(_read(FRONTEND / "components" / "erp" / "file-upload.tsx"))
    assert 'type="file"' in upload and "application/pdf" in upload, "(a)"
    shot = _code(_read(FRONTEND / "components" / "erp" / "photo-capture.tsx"))
    assert 'type="file"' not in shot, "(b)"
    for src in (shot, invoice):
        assert "onStored" not in src, "(c)"


def test_the_draft_keeps_its_work_and_its_place():
    """**Ein Entwurf verliert nichts, und was man bearbeitet, bleibt stehen** (Chrome-Test).

    Bug-Formen: (a) eine Nummer im Entwurf öffnet ihren Datensatz – der Entwurf (nur im
    Browser) ist ohne Warnung weg; (b) die Stückauswahl schliesst nicht beim Klick daneben;
    (c) die Auswahl wächst über die verlangte Menge («2 von 1»); (d) eine Handlung am Beleg
    lässt den bearbeiteten Abschnitt wegrutschen.
    """
    page = _code(_read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx"))
    draft = page[page.index("<ErpNavContext.Provider value={null}>"):]
    draft = draft[: draft.index("</ErpNavContext.Provider>")]
    assert "creating === 'order'" in draft and "creating === 'article'" in draft, "(a)"
    lines = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    picker = lines[lines.index("function StockPicker"):]
    assert "'pointerdown'" in picker and "setTouched(false)" in picker, "(b)"
    assert "chosen.length >= quantity" in picker, "(c)"
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "holdPlace(" in work and "onAction={onAction}" not in work, "(d)"
