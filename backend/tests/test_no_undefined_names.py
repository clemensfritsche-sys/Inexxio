"""Ein Fehler, der erst zur Laufzeit fliegt: ein Modul, das sich nicht importieren lässt.
Undefinierte Namen meldet ``ruff``
(F821, ``backend/ruff.toml``) im Gate."""

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
