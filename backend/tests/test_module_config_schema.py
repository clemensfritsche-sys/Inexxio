"""►►► **Ein Modul beschreibt seine Einstellungen – und die Beschreibung stimmt.** ◄◄◄

Was ein Modul einstellen lässt, prüft ``Module.clean_config``; was die Route darüber sagt (und
was die KI daraus liest), steht in ``Module.config_schema`` direkt daneben. Zwei Formen einer
Regel – darum dieser Wächter: **was ``clean_config`` liest, ist beschrieben, und was beschrieben
ist, liest ``clean_config``**. Gemessen wird, nicht gelesen: ``clean_config`` bekommt die
Beispiele der Beschreibung in einem Wörterbuch, das jeden gelesenen Schlüssel festhält.

Bug-Formen: (a) ein Modul bekommt eine Einstellung, die die Beschreibung nicht nennt – die KI
kennt sie nicht; (b) die Beschreibung nennt eine, die ``clean_config`` gar nicht liest – die KI
schickt sie, und sie verschwindet still; (c) ein Beispiel der Beschreibung ist nicht gültig;
(d) die Route, die Schritte nimmt, sagt der KI nicht, welche Module es gibt und was sie brauchen.
"""

import json
from typing import Any, Optional

import pytest

from app.domain import capture_types, modules
from app.domain.errors import Invalid


class _Read(dict):
    """Ein Wörterbuch, das festhält, welche Schlüssel gelesen werden (Pfad wie ``lines[].article``)."""

    def __init__(self, data: dict[str, Any], seen: set[str], at: str = ""):
        super().__init__({k: _wrap(v, seen, f"{at}{k}") for k, v in data.items()})
        self._seen, self._at = seen, at

    def _mark(self, key: Any) -> None:
        self._seen.add(f"{self._at}{key}")

    def get(self, key: Any, default: Any = None) -> Any:
        self._mark(key)
        return super().get(key, default)

    def __getitem__(self, key: Any) -> Any:
        self._mark(key)
        return super().__getitem__(key)

    def __contains__(self, key: Any) -> bool:
        self._mark(key)
        return super().__contains__(key)


def _wrap(value: Any, seen: set[str], at: str) -> Any:
    if isinstance(value, dict):
        return _Read(value, seen, f"{at}.")
    if isinstance(value, list):
        return [_wrap(v, seen, f"{at}[]") for v in value]
    return value


def _described(schema: dict[str, Any], at: str = "") -> set[str]:
    """Jeder Pfad, den eine Beschreibung nennt – Objekte mit ``.``, Listen mit ``[]``."""
    out: set[str] = set()
    for key, field in (schema.get("properties") or {}).items():
        out.add(f"{at}{key}")
        out |= _described(field, f"{at}{key}.")
        items = field.get("items")
        if isinstance(items, dict):
            out |= _described(items, f"{at}{key}[].")
    return out


def _read(module: modules.Module, examples: list[dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    for example in examples:
        module.clean_config(_Read(example, seen))
    return seen


def drift(module: modules.Module) -> list[str]:
    """Was Beschreibung und ``clean_config`` verschieden sehen – leer heisst: sie stimmen."""
    schema = module.config_schema()
    examples = schema.get("examples") or []
    problems: list[str] = []
    for i, example in enumerate(examples):
        try:
            module.clean_config(example)
        except Invalid as e:
            problems.append(f"Beispiel {i + 1} ist ungültig: {e}")
    if problems:
        return problems
    described, read = _described(schema), _read(module, examples)
    problems += [f"liest «{p}», beschreibt es nicht" for p in sorted(read - described)]
    problems += [f"beschreibt «{p}», liest es nie" for p in sorted(described - read)]
    return problems


@pytest.mark.parametrize("key", modules.KEYS)
def test_every_module_describes_exactly_what_it_reads(key):
    """(a)(b)(c) Jedes Modul der Registry – ein neues ist von selbst dabei."""
    assert drift(modules.get(key)) == []


def test_every_capture_type_describes_exactly_what_it_reads():
    """Ein Erfassungstyp mit eigenen Feldern (Soll-Ist) beschreibt sie – auch ein neuer Typ."""
    for t in capture_types.ALL:
        seen: set[str] = set()
        t.clean(_Read({"label": t.label, "type": t.key, **t.EXAMPLE}, seen))
        assert seen - {"label", "type"} == set(t.FIELDS), t.key
        assert set(t.REQUIRED) <= set(t.FIELDS), t.key


# ─── Gegenprobe: der Wächter schlägt an ─────────────────────────────────────────

class _Undescribed(modules.Bewegen):
    """(a) liest eine Einstellung, die die Beschreibung nicht nennt."""

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        return {**super().clean_config(raw), "speed": (raw or {}).get("speed")}


class _Unread(modules.Bewegen):
    """(b) beschreibt eine Einstellung, die niemand liest."""

    def config_schema(self) -> dict[str, Any]:
        schema = super().config_schema()
        return {**schema, "properties": {**schema["properties"], "speed": {"type": "integer"}}}


class _Invalid(modules.Aussondern):
    """(c) ein Beispiel, das ``clean_config`` abweist."""

    def config_schema(self) -> dict[str, Any]:
        return {**super().config_schema(), "examples": [{"mode": "scrap"}]}


def test_the_guard_bites_on_each_bug_form():
    assert drift(_Undescribed("x", "X", "slate")) == ["liest «speed», beschreibt es nicht"]
    assert drift(_Unread("x", "X", "slate")) == ["beschreibt «speed», liest es nie"]
    assert drift(_Invalid("x", "X", "slate"))[0].startswith("Beispiel 1 ist ungültig")


# ─── (d) Was die KI aus der Route liest ─────────────────────────────────────────

@pytest.mark.parametrize("key", ["POST /api/v1/erp/orders", "POST /api/v1/erp/articles"])
def test_the_ai_reads_every_module_and_its_settings_from_the_route(key):
    """Die KI bekommt die Felder einer Handlung über das Werkzeug ``handlung`` – aus der Route.
    Darin stehen alle Modultypen und je Typ, was er braucht."""
    from app.services import ai_tools
    tool = next(t for t in ai_tools.erp_tools(lambda *a: (None, None)) if t.name == "handlung")
    text = tool.run({"handlung": key})
    schema = json.loads(text.split("Werte (JSON-Schema): ", 1)[1])
    step = schema["properties"]["steps"]["items"]
    assert step["properties"]["module_type"]["enum"] == list(modules.KEYS)
    by_type = step["properties"]["config"]["x-config-by-module-type"]
    assert set(by_type) == set(modules.KEYS)
    assert "reason" in by_type[modules.AUSSONDERN]["required"]
    assert set(by_type[modules.AUSSONDERN]["properties"]["mode"]["enum"]) == {"scrap", "block"}
    assert "lines" in by_type[modules.VERBRAUCH]["properties"]
    points = by_type[modules.DATENERFASSUNG]["properties"]["points"]["items"]
    assert points["properties"]["type"]["enum"] == list(capture_types.KEYS)
    assert {"target", "unit"} <= set(points["properties"])
    assert {"direction", "parties", "prices"} <= set(by_type[modules.BELEG]["properties"])
