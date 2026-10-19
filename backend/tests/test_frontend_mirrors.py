"""Spiegel über die API-Grenze – was auf beiden Seiten steht, darf nicht auseinanderlaufen.

Das Frontend pflegt einige Aufzählungen von Hand (schnell, ohne Generierung). Damit sie
nicht still von den Backend-Quellen abweichen, vergleicht dieser Wächter beide Seiten.
Die Quelltext-Wächter der einzelnen Bereiche stehen in ``test_source_*.py``.
"""

import re

from tests._source import (
    BACKEND,
    FRONTEND,
    _body,
    _code,
    _read,
)


# ---------------------------------------------------------------------------
# Das Datenmodell
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Das Modul «Datenerfassung»
# ---------------------------------------------------------------------------


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
# #673 / #674 – Palette, Autosave, kein Bearbeiten, Drag & Drop
# ---------------------------------------------------------------------------


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
    Konstante (`VOUCHER_PARTY` ↔ `deal.PARTY`). Singular = Plural: damit ist das
    «Kundeen»-Problem *strukturell* erledigt statt durch einen zweiten gepflegten Wert.

    Bug-Formen: (a) eine Richtung fehlt; (b) ein Wort läuft auseinander; (c) die
    Rollen-Wörter kommen je Richtung zurück – dann gibt es wieder die falsche Wahl.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm

    src = _read(FRONTEND / "lib" / "modules.ts")
    block = _body(src, "VOUCHER_DIRECTION", kind="const")
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
    assert f"VOUCHER_PARTY = '{dm.PARTY}'" in src, (
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

    block = _body(_read(FRONTEND / "lib" / "modules.ts"), "VOUCHER_STAGE", kind="const")
    for key in (*dm.STAGES, dm.DONE, dm.CANCELLED):
        assert f"{key}: '{key}'" in block, f"Die Stufe «{key}» fehlt in der Zuordnung."

    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "VOUCHER_STAGE." in work, "Die Karte liest die Stufen nicht aus der Zuordnung."
    # Geprüft wird die REGEL («kein Stufen-Wort im Rumpf»), nicht die Form der Lösung:
    # WELCHE Stufen die Karte nennt, ist ihre Sache – `agreed` ist heute die Ableitung
    # «nicht mehr Angebot», und ein Wächter, der eine bestimmte Zeile verlangt, verbietet
    # die bessere Fassung.
    for key in (*dm.STAGES, dm.DONE, dm.CANCELLED):
        assert f"'{key}'" not in work, (
            f"Die Karte vergleicht gegen '{key}' statt gegen VOUCHER_STAGE.{key} – ein "
            f"zweiter Ort für denselben Schlüssel."
        )
    for german in ("'angebot'", "'zusage'", "'abgeschlossen'", "'storniert'"):
        assert german not in work, (
            f"Die Karte vergleicht gegen {german} – das ist eine **Beschriftung**, und "
            f"die hängt an der Richtung."
        )


def test_the_module_keys_are_the_same_on_both_sides():
    """**Die Oberfläche kennt genau die Modultypen, die das Backend führt.**

    Ein Modultyp, den nur noch eine Hälfte kennt, ist genau die Form, in der eine
    Oberfläche einen Vorgang rendert, den es nicht mehr gibt – oder ein Dienst einen
    Schlüssel annimmt, den niemand mehr schickt. Dass die entfernten Module (Beschaffen,
    Verkauf, Ausliefern, «Zahlung (alt)») weg bleiben, prüft ``test_removed.py``.

    Bug-Formen: (a) ein entfernter Schlüssel kommt zurück; (c) die Oberfläche kennt einen
    Modultyp, den das Backend nicht führt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    assert set(modules.KEYS) == {
        "datenerfassung", "aussondern", "bewegen", "beleg", "verbrauch",
    }, f"Die Modultypen sind nicht die erwarteten: {sorted(modules.KEYS)} (a)."

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
