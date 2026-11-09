"""EINE Meldestelle für den Betrieb (``core/report``, Änderungsakte V7)."""

import json
import pathlib
import re

from app.core import report

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def test_every_operator_message_goes_through_the_one_place():
    """Bug-Form: ein ``print`` daneben – ohne Stufe, Google macht daraus keinen Alarm."""
    hits = [f"{p.relative_to(APP)}:{n}" for p in APP.rglob("*.py") if p.name != "report.py"
            for n, line in enumerate(p.read_text().splitlines(), 1) if re.search(r"(?<![\w.])print\(", line)]
    assert not hits, f"Meldungen ohne Meldestelle: {hits}"


def test_a_message_is_one_json_line_with_its_severity(capsys):
    report.error("Takt gescheitert", task="mail")
    line = json.loads(capsys.readouterr().out.strip())
    assert line == {"severity": "ERROR", "message": "Takt gescheitert", "task": "mail"}
