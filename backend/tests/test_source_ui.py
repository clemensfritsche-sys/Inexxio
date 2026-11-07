"""Quelltext-Wächter: Design-System, gemeinsame Bauteile, Datum, Layout-Regeln.
"""

import json
import re

from tests._source import (
    _feed,
    ERP_KIT,
    _kit,
    FRONTEND,
    ROOT,
    _at,
    _beleg,
    _body,
    _code,
    _frontend_sources,
    _read,
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
    # Dass niemand daneben `toLocaleString` ruft, prüft ESLint (`frontend/eslint.config.mjs`).
    money = _read(FRONTEND / "components" / "erp" / "module-ui.tsx")
    assert "formatAmount(value, decimals)" in money, (
        "Das Betrags-Bauteil formatiert nicht über `formatAmount`."
    )
    beleg = _beleg()
    assert "d.currency_decimals" in beleg, (
        "Der Beleg reicht die Nachkommastellen der Währung nicht durch."
    )


def test_the_header_is_defined_once_for_every_record_type():
    """**#697 — Layout, Raster, Farben, Schriften: global, nicht je Datensatztyp.**

    Was variieren darf, ist der **Inhalt**. Symbol, Farbfamilie und Eyebrow kommen darum
    aus der einen Quelle (``lib/erp-record.TYPE_META``) und werden **im Kopf** aufgelöst –
    vorher reichte jede Ansicht sie einzeln herein, drei davon mit hart getippten
    Hex-Werten und einem zweiten Mal ausgeschriebenem Namen.
    """
    fields = _kit()
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
    # ESLint 9 liest nur noch die Flat Config; eine `.eslintrc.json` daneben wäre eine
    # Regel, die niemand mehr ausführt – sie sähe scharf aus und prüfte nichts.
    root = FRONTEND.parent
    assert not (root / ".eslintrc.json").exists(), (
        "Neben der Flat Config liegt eine `.eslintrc.json` – ESLint 9 liest sie nicht."
    )
    cfg = _code(_read(root / "eslint.config.mjs"))
    # Die TypeScript-Fassung der Regel (sie kennt auch Typen); die Basisregel ist dafür aus.
    rule = re.search(
        r"'@typescript-eslint/no-unused-vars':\s*\[\s*'(\w+)'\s*,\s*\{([^}]*)\}", cfg)
    assert rule, "Die Regel gegen ungenutzte Variablen ist nicht eingeschaltet."
    # Das Plugin `@typescript-eslint` lädt `next/core-web-vitals` (für .ts/.tsx) – ohne
    # diese Grundlage nennte die Regel ein Plugin, das niemand lädt.
    assert "from 'eslint-config-next/core-web-vitals'" in cfg and "...nextVitals" in cfg, (
        "Die Regel nennt ein Plugin, das die Konfiguration nicht lädt."
    )
    assert rule.group(1) == "error", "Die Regel warnt nur – dann fällt nichts auf."
    # Die Hausregeln am Syntaxbaum (Datum, Zahl, Rolle, `busy`, Konto-Bausteine) prüft
    # ESLint statt einer Textsuche hier – sie müssen dort scharf bleiben.
    for name in ("no-restricted-syntax", "no-restricted-imports"):
        assert f"'{name}': ['error'" in cfg, f"«{name}» ist nicht als Fehler eingeschaltet."
    for selector in ("toLocaleString", "toLocale(Date|Time)String", "DateTimeFormat",
                     "employee", "Identifier[name='busy']", "^@/components/account/"):
        assert selector in cfg, f"Die Hausregel «{selector}» fehlt in eslint.config.mjs."
    assert "destructuredArrayIgnorePattern" in rule.group(2), (
        "Ohne diese Option bleibt die tote `useState`-Destrukturierung unbemerkt – "
        "und genau die war der tote Scan-Knopf."
    )
    # Und `npm run lint` führt ESLint selbst aus (`next lint` gibt es ab Next 16 nicht).
    scripts = json.loads(_read(root / "package.json"))["scripts"]
    assert scripts.get("lint", "").startswith("eslint"), (
        f"«npm run lint» führt ESLint nicht aus: {scripts.get('lint')!r}"
    )
    # Dass die CI sie ausführt, prüft ``test_ci.py``.

    feed = _feed()
    assert "feedCapture" not in feed, "Der tote Zustand hinter dem Scan-Knopf ist zurück."
    assert "onScan={openScanner}" in feed and "onClick={onScan}" in feed, "Der Scan-Knopf ist wieder ohne Wirkung."


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
    # (a) **Niemand formatiert selbst** – das prüft ESLint (`frontend/eslint.config.mjs`).
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
    # Die Kopfhöhe kommt mit dem Stylesheet des gemeinsamen Kopfs (WEBSITE_PLAN Entscheid
    # 60): `export-shell.mjs` schreibt sie als `--site-header-h` aus der Website-Angabe.
    defined |= set(re.findall(r"(--[a-z0-9-]+)\s*:",
                              _read(ROOT / "website" / "scripts" / "export-shell.mjs")))
    missing = sorted((n, f) for n, f in used.items() if n not in defined)
    assert not missing, (
        "Diese CSS-Variablen werden benutzt, aber nirgends definiert – sie erzeugen "
        f"stillschweigend nichts: {missing}"
    )


def test_the_money_module_mirror_is_named_after_its_source():
    """**Der Spiegel heisst wie seine Quelle** (F-30): `domain/voucher`, also `VOUCHER_*`.

    Das Modul `deal` ist gelöscht; ein `DEAL_DIRECTION` im Frontend schickt jeden, der den
    Spiegel sucht, an eine Datei, die es nicht gibt.

    Bug-Form: ein `DEAL_*`-Name oder `dealDirection` steht wieder im Code.
    """
    hits = [rel for rel, src in _frontend_sources(".ts", ".tsx")
            if re.search(r"\bDEAL_[A-Z]|\bdealDirection\b", _code(src))]
    assert not hits, f"Der Geldvorgang heisst wieder «deal»: {hits}"
    modules = _code(_read(FRONTEND / "lib" / "modules.ts"))
    for name in ("VOUCHER_DIRECTION", "VOUCHER_STAGE", "VOUCHER_PARTY", "voucherDirection"):
        assert name in modules, f"«{name}» fehlt in `lib/modules.ts`."



def test_autosave_is_one_module_with_one_delay():
    """**Ein Auto-Save, eine Vorgabe** (F-40) – die Hausregel sagt 3 s.

    Es gab zwei Hooks namens `useAutosave` mit verschiedener Signatur und verschiedener
    Vorgabe (3000 ↔ 1500 ms), dazu Aufrufer mit 2500 bzw. 1500.

    Bug-Formen: (a) ein zweiter Hook entsteht anderswo; (b) die Vorgabe ist nicht 3 s;
    (c) ein Hook nimmt wieder eine eigene Verzögerung an.
    """
    lib = _code(_read(FRONTEND / "lib" / "use-autosave.ts"))
    assert "export const AUTOSAVE_DELAY = 3000;" in lib, "(b)"
    for name in ("useAutosaveValue", "useAutosaveSignature"):
        head = lib[lib.index(f"export function {name}"):]
        head = head[:head.index("{\n")]
        assert "delay" not in head, f"«{name}» nimmt wieder eine eigene Verzögerung an (c)."
    for rel, src in _frontend_sources(".ts", ".tsx"):
        if rel == "lib/use-autosave.ts":
            continue
        assert not re.search(r"function useAutosave\w*\s*[(<]", src), f"«{rel}» (a)"


def test_card_has_one_home():
    """**`Card` steht EINMAL** (F-41) – in `detail-frame.tsx`.

    Konto und ERP-Benutzer bauten beide nach (wortgleich), und ein Kommentar behauptete
    das Gegenteil.

    Bug-Form: eine Datei definiert sie wieder selbst.
    """
    for rel, src in _frontend_sources(".tsx"):
        if rel == "components/erp/detail-frame.tsx":
            continue
        assert not re.search(r"\bfunction Card\s*\(", src), (
            f"«{rel}» baut `Card` nach – sie steht in `detail-frame.tsx`."
        )


def test_the_micro_label_is_written_once():
    """**Das Mikro-Label steht EINMAL** (F-43) – `fields.MICRO_LABEL` bzw. `fields.Label`.

    Neun Fassungen standen inline da (11/12 px, 600/700, .05/.06/.07 em), jede für sich
    richtig aussehend. Erlaubt ausserhalb von `fields.tsx` sind nur zwei bewusst andere
    Gattungen: der Abschnittskopf (`module-ui`, Overline-Register) und die Beschriftung im
    Zahlungsformular des Dienstes (`pay-online`, ein iframe ohne unsere Klassen).

    Bug-Form: eine Datei schreibt die Versalien wieder selbst.
    """
    allowed = {f"components/erp/{n}.tsx" for n in ERP_KIT} | {
        "components/erp/module-ui.tsx", "components/erp/pay-online.tsx"}
    hits = [rel for rel, src in _frontend_sources(".tsx", ".ts")
            if rel not in allowed and "textTransform: 'uppercase'" in _code(src)]
    assert not hits, f"Diese Dateien schreiben das Mikro-Label selbst: {hits}"


def test_staff_is_asked_in_one_place():
    """**«Ist das Personal?» fragt EINE Funktion** (F-46/F-65) – `record-status.isStaff`.

    Am ERP-Benutzer stand das Paar zweimal ausgeschrieben, und das Konto fragte nur
    `role === 'employee'`: ein Admin sah dort seine Anstellung nicht und konnte seine
    Gesellschaft ändern, die für Personal eine eigene sein muss.

    Bug-Formen: (a) eine Datei vergleicht die Rolle wieder selbst; (b) das Konto fragt
    nicht `isStaff`.
    """
    # (a) prüft ESLint (`frontend/eslint.config.mjs`, Vergleich mit 'employee').
    shell = _code(_read(FRONTEND / "components" / "account" / "account-shell.tsx"))
    assert "isStaff(profile.role)" in shell, "(b)"


def test_a_search_while_typing_is_one_hook():
    """**Tippen sucht – über EINEN Hook** (F-47, `lib/use-search.ts`).

    Entprellen und Veralterungs-Schutz standen an sieben Stellen ausgeschrieben.
    Ausgenommen ist der Instanz-Feed (`erp/page.tsx`): er lädt seitenweise, und eine leere
    Suche fragt sofort.

    Bug-Form: eine Datei baut wieder `setTimeout` + `stale = true` für eine Suche.
    """
    allowed = {"lib/use-search.ts", "app/(erp)/erp/page.tsx"}
    debounce = re.compile(r"let stale = false;\s*const t = (?:window\.)?setTimeout\(")
    hits = [rel for rel, src in _frontend_sources(".ts", ".tsx")
            if rel not in allowed and debounce.search(_code(src))]
    assert not hits, f"Diese Dateien suchen beim Tippen selbst: {hits}"
    for rel in ("components/erp/search-select.tsx", "components/erp/communication/composer.tsx",
                "components/scan/scan-dialog.tsx", "components/erp/article-detail.tsx"):
        assert "useSearch" in _read(FRONTEND / rel), f"«{rel}» nutzt die gemeinsame Suche nicht."


def test_a_date_is_not_rebuilt_from_its_own_output():
    """**Der Kalendertag ist eine Ausgabe von `lib/when`, keine Bastelei** (F-49).

    Der Verlauf baute aus `day(iso)` per `split('.')` wieder ein ISO-Datum, um `when()`
    zu füttern – er hing damit an der Schreibweise einer anderen Funktion.

    Bug-Form: eine Ausgabe von `day()` wird wieder zerlegt.
    """
    for rel, src in _frontend_sources(".ts", ".tsx"):
        assert not re.search(r"\bday\([^)]*\)\.split\(", _code(src)), f"«{rel}»"
    assert "export function whenDay" in _read(FRONTEND / "lib" / "when.ts")


def test_the_old_palette_is_gone_also_as_hex():
    """►►► **Die Alt-Palette ist weg – auch als Hex** (F-20/F-50/F-51). ◄◄◄

    Die «0 Vorkommen» galten nur für Klassennamen: als Hex-Literal lebten Tailwinds
    slate/gray/amber/green/red/sky weiter, im Konto und – über das Konto-Feld – in
    ERP-Formularen. Dazu das Markenrot in drei Schreibweisen (`#E51A14`, `--ix-red`,
    `--inexxio-red`) und der Rohtoken `--color-warning` neben `--warning`.

    Bug-Formen: (a) ein Alt-Hex steht wieder im Code; (b) das Rot steht als Hex oder als
    `--ix-*`-Alias; (c) die Warnfarbe kommt als Rohtoken.
    """
    old = re.compile(
        r"#(0F172A|1E293B|334155|475569|64748B|94A3B8|CBD5E1|E2E8F0|F1F5F9|F8FAFC|"
        r"111827|1F2937|374151|4B5563|6B7280|9CA3AF|D1D5DB|E5E7EB|F3F4F6|F9FAFB|"
        r"F59E0B|D97706|B45309|FFFBEB|16A34A|15803D|F0FDF4|BBF7D0|DC2626|FEF2F2|FCA5A5|"
        r"0284C7|F0F9FF|BAE6FD)\b", re.I)
    # Die Gebietskarte trägt eine eigene kategoriale Palette («welche Gesellschaft»,
    # keine Ampel) – das Design-System führt keine; sie ist bewusst ausgenommen.
    for rel, src in _frontend_sources(".ts", ".tsx", ".css"):
        if rel == "components/erp/territory-map.tsx":
            continue
        found = sorted({m.group(0) for m in old.finditer(_code(src))})
        assert not found, f"«{rel}» trägt die Alt-Palette als Hex (a): {found}"
        assert "#E51A14" not in src.upper() and "--ix-red" not in src, f"«{rel}» (b)"
        assert "var(--color-warning" not in src, f"«{rel}» (c)"


def test_a_dialog_closes_only_when_its_action_went_through():
    """Ein Dialog, der eine Handlung auslöst (Senden, Löschen), schliesst nur bei Erfolg –
    sonst wäre die Eingabe weg und der Grund stünde hinter dem geschlossenen Dialog. Die
    Handlung sagt es (`act` gibt `true` zurück); ein `.then(() => set…(false))` schliesst
    auch beim Fehler."""
    closing = re.compile(r"\bact\(\(\) => [^;{}]*?\)\)\s*\.then\(\(\)\s*=>\s*set\w+\(false\)\)")
    for rel, src in _frontend_sources(".tsx"):
        hit = closing.search(src)
        assert not hit, f"«{rel}» schliesst einen Dialog auch, wenn die Handlung scheitert."
    detail = _read(FRONTEND / "components" / "erp" / "document-detail.tsx")
    assert re.search(r"function act\(.*\):\s*Promise<boolean>", detail), (
        "`act` sagt nicht, ob die Handlung ging."
    )


#: Eine `ix-`-Klasse im Markup (`className="…"`, `` `…` ``, `'…'`).
_IX_CLASS = re.compile(r"(?<![\w-])(ix-[\w-]+)")
_CLASS_ATTR = re.compile(r"className=(?:\"([^\"]*)\"|\{`([^`]*)`\}|\{[^}]*?'([^']*)')")


def _ix_classes_without_css(markup: str, css: str) -> set[str]:
    used = set()
    for m in _CLASS_ATTR.finditer(markup):
        used |= set(_IX_CLASS.findall(" ".join(x for x in m.groups() if x)))
    # `ix-shell` legt der Website-Build als eigenes Stylesheet ab (`scripts/site-shell.mjs`).
    return {c for c in used - {"ix-shell"} if not re.search(rf"\.{re.escape(c)}(?![\w-])", css)}


def test_every_ix_class_in_the_markup_exists():
    """Eine Klasse, die es nicht gibt, erzeugt still nichts – die Rückkehrseite der Anmeldung
    trug `.ix-login-bg`/`.ix-login-lightbox` und sah darum nicht aus wie der Dialog. Jede
    `ix-`-Klasse im Markup steht in einem Stylesheet (Frontend oder Website)."""
    css = "".join(p.read_text(encoding="utf-8") for p in sorted(FRONTEND.rglob("*.css")))
    css += "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "website" / "src").rglob("*"))
                   if p.suffix in (".css", ".astro"))
    assert _ix_classes_without_css('<div className="ix-login-lightbox" />', css) == {"ix-login-lightbox"}
    for rel, src in _frontend_sources(".tsx"):
        missing = _ix_classes_without_css(src, css)
        assert not missing, f"«{rel}» trägt Klassen ohne Stil: {sorted(missing)}"


def test_dialogs_tabs_and_chips_say_what_they_are():
    """Ein Bildschirmleser hört, was ein Bauteil ist: der Dialog ist ein modaler Dialog mit
    Titel, nimmt den Fokus und gibt ihn zurück (Escape schliesst); die Reiter sind eine
    Reiterliste mit gewähltem Reiter; ein Filter-Chip sagt, ob er gedrückt ist; ein Knopf
    nur mit Symbol hat einen Namen."""
    fields = _kit()
    start = fields.index("export function Dialog(")
    dialog = fields[start: fields.index("\n}\n", start)]
    for need in ('role="dialog"', 'aria-modal="true"', "aria-labelledby={titleId}", "'Escape'",
                 ".focus()", "before?.focus"):
        assert need in dialog, f"Der Dialog: «{need}» fehlt."
    tabs = _read(FRONTEND / "components" / "erp" / "detail-tabs.tsx")
    for need in ('role="tablist"', 'role="tab"', "aria-selected="):
        assert need in tabs, f"Die Reiter: «{need}» fehlt."
    page = _feed()
    chip = page[page.index("FILTER_TYPES.filter"):]
    chip = chip[: chip.index("</button>")]
    assert "aria-pressed={active}" in chip and "aria-label=" in chip, "Der Filter-Chip sagt nicht, was er ist."
    territory = _read(FRONTEND / "components" / "erp" / "territory-map.tsx")
    close = territory[: territory.index("<X size={14}")]
    assert "aria-label=" in close[close.rindex("<button"):], "Das × der Gebietskarte hat keinen Namen."


#: Ein selbst gebauter Punkt: 5–8 px, rund (`borderRadius: 999` oder `rounded-full`).
_HAND_DOT = re.compile(
    r"width: [5-8], height: [5-8],[^}]*?(?:borderRadius: 999|background)"
    r"|rounded-full\" style=\{\{\s*width: [5-8], height: [5-8]")
#: Punkte, die kein Zustand sind – mit Grund.
_NOT_A_STATE = {
    "components/erp/territory-map.tsx": "die Farbe einer Gesellschaft auf der Karte",
    "components/erp/time/time-calendar.tsx": "eine Markierung in der Ecke eines Kalendertags",
    "components/erp/fields.tsx": "StatusDot selbst",
    "components/erp/controls.tsx": "die Empfehlung am Schieber (IconSwitch.mark)",
}


def test_a_state_dot_is_one_component():
    """«Status als Punkt + Wort» – ein Bauteil (`fields.StatusDot`), nicht acht Eigenbauten
    mit 6, 7 und 8 px."""
    for rel, src in _frontend_sources(".tsx"):
        if rel in _NOT_A_STATE:
            continue
        hit = _HAND_DOT.search(src)
        assert not hit, f"«{rel}» baut einen Zustandspunkt selbst: {hit.group(0)[:60]} – dafür gibt es StatusDot."
    assert _HAND_DOT.search("<span style={{ width: 7, height: 7, borderRadius: 999, flex: 'none' }} />")


def test_every_input_has_the_one_form():
    """Ein Eingabefeld hat EINE Form (`fields.inputClass`): Radius, Rahmen, Polsterung,
    Schrift, Fokus. Die Felder der Konto-Bausteine im ERP, der Zeiterfassung und der
    Spezifikation führen darauf zurück; eine zweite Fassung daneben läuft auseinander."""
    fields = _kit()
    assert "rounded-ds-md" in re.search(r"const INPUT_FORM = '([^']+)'", fields).group(1)
    for rel in ("components/form/field.tsx", "components/erp/time/time-ui.tsx",
                "components/erp/article-detail.tsx"):
        src = _read(FRONTEND / rel)
        assert "inputClass(" in src or "inputCls" in src, f"«{rel}» baut sein Eingabefeld selbst."
        assert "FIN_CLS" not in src and "style.borderColor" not in src, f"«{rel}»: zweite Feldform."
        assert not re.search(r"<input[^>]*?style=\{\{\s*padding: '8px 12px'", src, re.S), (
            f"«{rel}» trägt die Form des Feldes inline."
        )


def test_the_composer_holds_one_draft():
    """Die Eingabe der Kommunikation ist EIN Zustand (`Draft`) – derselbe, den «Rückgängig»
    wiederherstellt. Dreizehn einzelne `useState` liefen beim Wiederherstellen und Leeren
    auseinander (jede Stelle musste alle dreizehn kennen)."""
    src = _read(FRONTEND / "components" / "erp" / "communication" / "composer.tsx")
    body = src[src.index("export function Composer("):]
    assert body.count("useState<Draft>(") == 1, "Die Eingabe ist nicht EIN Zustand."
    for part in ("useState<Person[]>", "useState<Mode>", "useState<Delivery>", "useState<Message | null>"):
        assert part not in body, f"Ein Teil der Eingabe lebt in einem eigenen Zustand: {part}"
