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

def test_the_process_logic_is_gone_from_both_sides():
    """Der Auftrag und seine Prozesslogik sind ersatzlos entfernt – nicht auskommentiert,
    nicht deaktiviert, nicht als Vorlage aufbewahrt."""
    for gone in ("process.py", "subject.py", "orders.py", "reservation.py", "ledger.py",
                 "units.py", "recovery.py", "supply.py", "deviation.py", "provisioning.py"):
        assert not (BACKEND / "app" / "services" / gone).exists(), (
            f"services/{gone} ist wieder da – die Prozesslogik wird neu gebaut, nicht "
            f"wiederverwendet."
        )
    for gone in ("order-flow.tsx", "flow-line.tsx", "process-steps.tsx", "order-detail.tsx"):
        assert not (FRONTEND / "components" / "erp" / gone).exists(), (
            f"components/erp/{gone} ist wieder da."
        )
    assert not (FRONTEND / "lib" / "process.ts").exists()
    assert not (FRONTEND / "lib" / "order.ts").exists()


def test_the_feed_no_longer_knows_an_order():
    """Der Datensatztyp «Auftrag» ist aus dem Feed verschwunden – er kommt mit der neuen
    Prozesslogik zurück."""
    types = _read(FRONTEND / "types" / "index.ts")
    m = re.search(r"export type ErpRecordType = ([^;]+);", types)
    assert m, "ErpRecordType fehlt."
    assert "'order'" not in m.group(1), "Der Feed kennt weiterhin einen Auftrag."

    meta = _read(FRONTEND / "lib" / "erp-record.ts")
    assert "order:" not in meta, "TYPE_META trägt weiterhin einen Auftrag."


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
    from app.services import capture

    assert capture.evaluate([{"key": "n", "type": "text"}], {"n": "x"}) is None
    assert capture.evaluate([{"key": "l", "type": "measure"}], {"l": 5}) is None
    assert capture.evaluate(
        [{"key": "l", "type": "measure", "target": 10, "tolerance": 1}], {"l": 10.5}) == "passed"
    assert capture.evaluate(
        [{"key": "l", "type": "measure", "target": 10, "tolerance": 1}], {"l": 12}) == "failed"
