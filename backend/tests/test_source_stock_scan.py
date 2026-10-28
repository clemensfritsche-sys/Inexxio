"""Quelltext-Wächter: Bestand, Scanner, Referenzfeld, Stück-Auswahl.
"""

import re

from tests._source import (
    _kit,
    BACKEND,
    FRONTEND,
    _body,
    _code,
    _expr,
    _read,
)


# ---------------------------------------------------------------------------
# #673 / #674 – Palette, Autosave, kein Bearbeiten, Drag & Drop
# ---------------------------------------------------------------------------


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
    fields = _kit()
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
    fields = _code(_kit())
    assert "zIndex: 60" in fields, "Der Detail-Dialog liegt nicht mehr unter dem Scanner."
    pin = _read(FRONTEND / "components" / "feedback" / "feedback-pin.tsx")
    assert "z-[2000]" in pin, "Das Notiz-Werkzeug liegt nicht mehr über dem Scanner."


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


# ---------------------------------------------------------------------------
# Datenerfassung – Scan-Pflicht, Stichprobe, Entscheidung
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# «Leer» ist eine Wahl, und der Scanner nennt die Nummer (Testnotizen #734–#737)
# ---------------------------------------------------------------------------


def test_nothing_is_a_choice_not_three_workarounds():
    """**«Kein Ziel» steht in der Liste, in der man wählt.**

    Bug-Form: dieselbe Aussage an drei Stellen – ein erklärender Platzhalter («leer lassen
    für …»), ein Erklärsatz darunter und ein X-Knopf daneben. Keine davon war die Liste,
    und der Knopf war eine Rücknahme, keine Wahl (Testnotizen #734/#735/#736).
    """
    fields = _code(_kit())
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
    fields = _code(_kit())
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
    fields = _code(_kit())

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
# ►► TESTNOTIZEN #1023–#1031 — weniger Beschriftung, EIN Suchfeld, EINE Nummer
# ---------------------------------------------------------------------------


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
    fields = _code(_kit())
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


def test_an_empty_stock_says_so_and_nothing_more():
    """**«Kein Bestand» ist die Auskunft** (Testnotiz #1030).

    Der Satz daneben erklärte, *woher* Einzelinstanzen kommen – eine Belehrung über das
    Datenmodell an der Stelle, an der jemand eine Zahl sucht.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "stock-view.tsx"))
    assert ">Kein Bestand<" in ui, "Die Auskunft fehlt."
    assert "entstehen mit der Freigabe" not in ui, "Die Belehrung steht wieder da."


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
# ►► TESTNOTIZEN #1046/#1047/#1049 — am Beleg
# ---------------------------------------------------------------------------


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
