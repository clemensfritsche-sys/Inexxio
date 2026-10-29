"""Quelltext-Wächter: Bestand, Scanner, Referenzfeld, Stück-Auswahl.
"""

import re

from tests._source import (
    _feed,
    BACKEND,
    FRONTEND,
    _body,
    _code,
    _read,
)


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
    # Gefragt ist das TOR vor der Suche: ein eingeschränkter oder verifizierender Schritt
    # gibt der gemeinsamen Suche (`useSearch`) gar keine Quelle.
    assert re.search(r"step\?\.restrict \|\| step\?\.expected != null \? null : step\?\.suggest",
                     dialog) and "useSearch(query, ask" in dialog, (
        "Ein eingeschränkter oder verifizierender Schritt bekommt breitere Vorschläge – "
        "dann bietet er an, was er gar nicht annimmt."
    )
    # **Und jeder Schritt hat eine Vorschlagsmenge**, ohne dass ein Aufrufer sie mitgibt:
    # sie ist abgeleitet aus dem, was er ANNIMMT. Genau daran fehlte es im Modul – dort
    # gab es keine Liste, also blieb die Suche leer und nur die volle Nummer ging durch.
    assert "export function offersFor" in lib, "Die Vorschläge sind wieder eine Bringschuld."
    assert "offersFor(step)" in dialog, "Der Dialog leitet die Vorschläge nicht ab."
    # Der Veralterungs-Schutz steht EINMAL, in der gemeinsamen Suche.
    search = _code(_read(FRONTEND / "lib" / "use-search.ts"))
    assert "stale = true" in search, "Eine ältere Antwort kann eine neuere überholen."

    # Und der Feed gibt seine EIGENE Suche herein, keine nachgebaute.
    page = _code(_feed())
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
    feed = _code(_feed())
    assert "exists: (id) => api.resolveObject(id)" in feed, (
        "Der Feed reicht die Frage nicht herein – dort trifft sie am häufigsten zu."
    )


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


def test_the_object_registry_claims_only_what_it_can_serve():
    """Ein Typ, den kein Endpunkt liefern kann, ist eine Behauptung.

    ``document`` stammte aus dem entfernten Dokumentmodul – jede Auflösung einer unbekannten
    Nummer durchsuchte eine Tabelle, die es nicht mehr gab. Seit den Dokumenten (Oktober
    2026) gibt es den Typ wieder, und er hat seine Seite (``routers/documents``). **Der Nummernraum ist davon
    getrennt**: jede Nummer trägt sich mit ihrem Typ in die Registry ein (ohne Typ keine
    Nummer), und die Sequence vergibt nie rückwärts.
    """
    src = _read(BACKEND / "app" / "services" / "objects.py")
    models = src.split("_TYPE_MODELS = {")[1].split("}")[0]
    served = _read(BACKEND / "app" / "routers" / "documents.py")
    assert '"document"' not in models or '@router.get("/{object_id}"' in served, (
        "Der Scan löst auf einen Typ auf, den kein Endpunkt liefert.")
    assert "def next_object_id(db: Session, object_type: str)" in src, (
        "Eine Nummer ohne Typ fiele aus der Registry – die Auflösung fände sie nicht.")


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


def test_the_scanner_hangs_at_the_root_not_at_the_erp():
    """►►► **Ein Referenzfeld trägt die Kamera – also braucht JEDE Seite den Scanner.** ◄◄◄

    Der ``ScanProvider`` hing am ERP-Layout. Seit die Firmenwahl auch im Konto steht
    (``CompanyField`` → ``ObjectSelect`` → ``useScan``), stürzte das Konto beim ersten
    Rendern ab («Application error»). Er steht jetzt genau einmal an der Wurzel.

    Bug-Formen: (a) der Provider fehlt an der Wurzel; (b) er steht zusätzlich in einem
    Unter-Layout (zwei Dialoge, und die Wurzel wirkt wie entbehrlich).
    """
    root = _code(_read(FRONTEND / "app" / "layout.tsx"))
    assert "<ScanProvider>" in root, "Der Scanner fehlt am Wurzel-Layout (a)."
    others = [p for p in (FRONTEND / "app").rglob("*.tsx")
              if p != FRONTEND / "app" / "layout.tsx"
              and "<ScanProvider" in _code(_read(p))]
    assert not others, f"Ein zweiter Scanner steht in {others} (b)."
