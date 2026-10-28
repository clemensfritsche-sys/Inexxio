"""Quelltext-Wächter: Design-System, gemeinsame Bauteile, Datum, Layout-Regeln.
"""

import json
import re

from tests._source import (
    FRONTEND,
    ROOT,
    _at,
    _beleg,
    _body,
    _code,
    _component,
    _frontend_sources,
    _read,
)


# ---------------------------------------------------------------------------
# #673 / #674 – Palette, Autosave, kein Bearbeiten, Drag & Drop
# ---------------------------------------------------------------------------


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
    # **Und überall, nicht nur im Beleg** (F-48): das Gewicht am Artikel formatierte selbst
    # und schrieb ab 1000 kg den typografischen Trenner. Eine Zahl hat eine Schreibweise.
    for path in sorted(FRONTEND.rglob("*.ts*")):
        if path.name in ("utils.ts", "api.ts") and path.parent.name in ("lib", "types"):
            continue
        assert "toLocaleString(" not in _code(_read(path)), (
            f"{path.name} formatiert selbst – dann gilt die Regel dort nicht."
        )
    money = _read(FRONTEND / "components" / "erp" / "module-ui.tsx")
    assert "formatAmount(value, decimals)" in money, (
        "Das Betrags-Bauteil formatiert nicht über `formatAmount`."
    )
    beleg = _beleg()
    assert "d.currency_decimals" in beleg, (
        "Der Beleg reicht die Nachkommastellen der Währung nicht durch."
    )


# ---------------------------------------------------------------------------
# Testrunde 7.8.2026 nachmittags (#689–#700)
# ---------------------------------------------------------------------------


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

    feed = _read(FRONTEND / "app" / "(erp)" / "erp" / "page.tsx")
    assert "feedCapture" not in feed, "Der tote Zustand hinter dem Scan-Knopf ist zurück."
    assert "onClick={openScanner}" in feed, "Der Scan-Knopf ist wieder ohne Wirkung."


# ---------------------------------------------------------------------------
# EIN Referenzfeld, überall (Testnotiz #738)
# ---------------------------------------------------------------------------


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
    work = _code(_beleg())
    assert "erp-actbtn-icon" not in work, (
        "Der Vorgang baut seine Symbol-Knöpfe wieder selbst, statt `ActionButton` zu "
        "benutzen."
    )
    assert not re.search(r"erp-actbtn[^\"]*\"[^>]*style=\{\{[^}]*width:", work + ui), (
        "Eine Inline-Breite am Symbol-Knopf ist zurück – genau daran verschob sich das "
        "Symbol, statt zentriert zu sein."
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


# ---------------------------------------------------------------------------
# Testnotizen #868–#875 – der Verlauf, die Wörter und was ein Knopf verspricht
# ---------------------------------------------------------------------------


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
    work = _code(_beleg())
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


# ---------------------------------------------------------------------------
# ►► Testnotizen #897–#901 — der Geldvorgang ist EIN Beleg
# ---------------------------------------------------------------------------




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
    assert "data-fb-section" in _code(_component(
        _read(FRONTEND / "components" / "erp" / "beleg" / "shared.tsx"), "Section")), (
        "Der Abschnitt eines Moduls benennt sich nicht."
    )


# ---------------------------------------------------------------------------
# Der Beleg — Testnotizen #936–#947
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #975–#978
# ---------------------------------------------------------------------------


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
    assert "{taken && <Note" in head, (
        "Die Angabe steht wieder unter der Kopfzeile (b) statt neben dem Betrag."
    )
    # **Die Tatsache steht im Hover** – seit #1052 liefert sie `happened(…).title`, die
    # eine Form für «Zeit + Vorgang». Gefragt ist, dass sie **da** ist, nicht welcher
    # Helfer sie baut: ein Wächter auf den Namen verbietet die bessere Fassung.
    assert re.search(r"happened\(q\.agreed_at", row) and "tip={taken.title}" in head, (
        "Die Tatsache fehlt im Hover (c)."
    )
    # (d) **Ein Bauteil, drei Aufrufstellen** – wann offeriert, wann angenommen, wie
    # bestellt. Dreimal dieselben vier Werte wären dreimal die Chance, dass einer abweicht.
    assert src.count("<Note ") + src.count("<Note>") >= 3, (
        "Die Auskünfte bauen ihre Form wieder je selbst (d)."
    )


# ---------------------------------------------------------------------------
# ►► DER UMBAU VON «RECHNUNG & ZAHLUNG» + TESTNOTIZEN #979/#981/#982
# ---------------------------------------------------------------------------


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
    work = _code(_beleg())
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


# ---------------------------------------------------------------------------
# ►► Testnotizen #995–#1003 — eine Zeilen-Grammatik, und der Saldo ist eine Farbe
# ---------------------------------------------------------------------------


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






# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #1023–#1031 — weniger Beschriftung, EIN Suchfeld, EINE Nummer
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Testnotizen #1032-#1036
# ---------------------------------------------------------------------------


def test_the_definition_line_does_not_explain_the_data_model():
    """►►► **Wie das System zaehlt, ist keine Auskunft** (Testnotiz #1033). ◄◄◄"""
    ui = _code(_read(FRONTEND / "components" / "erp" / "definition-lines.tsx"))
    for word in ("Einzelinstanzen (", "mit je einer Einzelinstanz", "Eine Instanz mit"):
        assert word not in ui, (
            f"Die Menge wird wieder in Datensaetze uebersetzt («{word}»)."
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


# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #1046/#1047/#1049 — am Beleg
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# ►► Cleanup Oktober 2026, Pakete 8–10 (Frontend): Namen · eine Regel, eine Stelle ·
# ---------------------------------------------------------------------------


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


def test_the_form_parts_live_outside_the_account():
    """**Gemeinsame Bausteine wohnen nicht unter «account»** (F-32/F-33).

    Feld, Speicher-Anzeige und Auto-Save lagen in `components/account/`, obwohl das ERP
    sie öfter importiert als das Konto; die Ampeltöne in einer Datei namens «status-flow»
    (einen Lebenszyklus gibt es dort nicht).

    Bug-Formen: (a) eine ERP-Datei importiert aus `components/account/`; (b) ein
    Baustein liegt wieder dort; (c) `status-flow` ist zurück.
    """
    for rel, src in _frontend_sources(".ts", ".tsx"):
        if rel.startswith(("components/account/", "app/(account)/")):
            continue
        assert "@/components/account/" not in src, f"«{rel}» importiert aus dem Konto (a)."
    account = FRONTEND / "components" / "account"
    for gone in ("field.tsx", "save-status.tsx", "use-autosave.ts",
                 "sections/system-config-section.tsx"):
        assert not (account / gone).exists(), f"«account/{gone}» liegt wieder dort (b)."
    assert not (FRONTEND / "lib" / "status-flow.ts").exists(), "(c)"
    assert (FRONTEND / "lib" / "status-tone.ts").exists(), "(c) – die Ampeltöne fehlen."


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
    """**`Card` steht EINMAL** (F-41) – in `fields.tsx`.

    Konto und ERP-Benutzer bauten beide nach (wortgleich), und ein Kommentar behauptete
    das Gegenteil.

    Bug-Form: eine Datei definiert sie wieder selbst.
    """
    for rel, src in _frontend_sources(".tsx"):
        if rel == "components/erp/fields.tsx":
            continue
        assert not re.search(r"\bfunction Card\s*\(", src), (
            f"«{rel}» baut `Card` nach – sie steht in `fields.tsx`."
        )


def test_the_micro_label_is_written_once():
    """**Das Mikro-Label steht EINMAL** (F-43) – `fields.MICRO_LABEL` bzw. `fields.Label`.

    Neun Fassungen standen inline da (11/12 px, 600/700, .05/.06/.07 em), jede für sich
    richtig aussehend. Erlaubt ausserhalb von `fields.tsx` sind nur zwei bewusst andere
    Gattungen: der Abschnittskopf (`module-ui`, Overline-Register) und die Beschriftung im
    Zahlungsformular des Dienstes (`pay-online`, ein iframe ohne unsere Klassen).

    Bug-Form: eine Datei schreibt die Versalien wieder selbst.
    """
    allowed = {"components/erp/fields.tsx", "components/erp/module-ui.tsx",
               "components/erp/pay-online.tsx"}
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
    for rel, src in _frontend_sources(".ts", ".tsx"):
        if rel == "lib/record-status.ts":
            continue
        assert not re.search(r"role\s*===\s*'employee'", _code(src)), f"«{rel}» (a)"
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
    for rel in ("components/erp/fields.tsx", "components/erp/communication.tsx",
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
