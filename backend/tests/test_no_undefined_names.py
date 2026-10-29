"""Zwei Fehler, die erst zur Laufzeit fliegen: ein Modul, das sich nicht importieren lässt,
und ein ``log_audit`` mit vertauschten Argumenten. Undefinierte Namen meldet ``ruff``
(F821, ``backend/ruff.toml``) im Gate."""

import ast
import importlib
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def _module_name(path: pathlib.Path) -> str:
    name = ".".join(path.relative_to(APP.parent).with_suffix("").parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def test_every_module_under_app_is_importable():
    """Ein Modul, das niemand beim Start importiert, scheitert sonst erst, wenn sein Pfad
    läuft."""
    findings = []
    for path in sorted(APP.rglob("*.py")):
        try:
            importlib.import_module(_module_name(path))
        except Exception as exc:                                   # noqa: BLE001
            findings.append(f"{_module_name(path)}: {type(exc).__name__}: {exc}")
    assert not findings, "Nicht importierbar:\n" + "\n".join(findings)


def test_the_audit_log_is_never_called_with_shuffled_arguments():
    """Jeder ``log_audit``-Aufruf passt zur Signatur — statisch geprüft.

    ``user_id`` steht an fünfter Stelle; vertauscht fliegt es erst in der Datenbank
    («invalid input syntax for type bigint»). Zwei Merkmale genügen: ``table_name`` ist
    immer ein Text**literal**, und ``user_id`` ist nie eines.
    """
    findings: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "log_audit"):
                continue
            where = f"{path.relative_to(APP.parent)}:{node.lineno}"
            args = node.args
            if len(args) >= 2 and not (
                isinstance(args[1], ast.Constant) and isinstance(args[1].value, str)
            ):
                findings.append(f"{where}: 2. Argument ist nicht der Tabellenname (Text)")
            if len(args) >= 5 and isinstance(args[4], ast.Constant) and isinstance(args[4].value, str):
                findings.append(f"{where}: 5. Argument ist Text – dort steht die user_id")

    assert not findings, (
        "Vertauschte Argumente bei log_audit (fliegt erst in der Datenbank):\n"
        + "\n".join(findings)
    )
