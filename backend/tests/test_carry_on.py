"""**Was von selbst weiterzieht, fragt EINE Stelle** (``process.carry_on``).

Zwei Gründe lassen Stücke ohne Klick weiterziehen: die Stichprobe ist durch
(``_run_through``), ein Zahlungsmodul darf durchlassen (``advance_payments``). Wer an einer
Stelle nur einen davon fragt, lässt Stücke stehen, die weiter dürften. Darum ruft beide nur
``carry_on`` – und ``advance_payments`` den Durchlauf über ``confirm_step``.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
PRIVATE = {"_run_through", "advance_payments"}
#: (Datei, Funktion), die einen der beiden rufen darf.
ALLOWED = {("services/process.py", "carry_on")}


def _callers(tree: ast.AST, rel: str) -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if name in PRIVATE:
                    found.add((rel, fn.name, name))
    return found


def offenders(sources: dict[str, str]) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for rel, text in sources.items():
        out |= {c for c in _callers(ast.parse(text), rel) if (c[0], c[1]) not in ALLOWED}
    # Eine Funktion steckt in sich selbst nicht (ast.walk geht in verschachtelte hinein).
    return {c for c in out if c[1] != c[2]}


def test_only_carry_on_asks():
    sources = {str(p.relative_to(APP)): p.read_text() for p in APP.rglob("*.py")}
    assert offenders(sources) == set(), (
        "Nur process.carry_on fragt, was von selbst weiterzieht – sonst bleibt an einer "
        "Stelle stehen, was ein Zahlungsmodul oder die Stichprobe durchliesse."
    )


def test_guard_sees_the_bug_form():
    """Gegenprobe: ein Ort, der nur den Durchlauf fragt, schlägt an."""
    bug = "def take(db):\n    _run_through(db, order=o, step=s, actor_id=None)\n"
    assert offenders({"services/release.py": bug}) == {
        ("services/release.py", "take", "_run_through")}


def test_a_payment_without_voucher_lets_nothing_through():
    """**Ohne Beleg zieht nichts durch.** Der Kern erkennt ein Modul, das von selbst
    durchlässt, an seiner Eigenschaft (``Module.passes_itself``), nicht mehr an einer Abfrage
    nach dem Beleg. Fehlt der Beleg doch einmal, muss die Auskunft «nein» sein – sonst liefen
    die Stücke ohne Zusage und ohne Geld durch."""
    from types import SimpleNamespace

    from app.domain import modules
    from app.services import voucher
    from tests.runner import session

    assert modules.get(modules.BELEG).passes_itself, "Die Zahlung lässt nicht von selbst durch."
    assert all(not modules.get(k).passes_itself for k in modules.KEYS if k != modules.BELEG)
    db = session()
    try:
        assert voucher.pass_problem(db, step=SimpleNamespace(id=-1)), (
            "Ein Zahlungsmodul ohne Beleg lässt die Stücke durch.")
    finally:
        db.close()
