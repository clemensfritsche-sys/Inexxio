"""Die eine Uhr (``core/clock``): «jetzt» und ein Tag, wie ein Mensch ihn liest – EINE Stelle."""

import pathlib
import re
from datetime import date, datetime, timezone

from app.core import clock

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
#: Eine zweite Uhr oder ein zweites Tagesformat neben ``core/clock``.
_SECOND = re.compile(r"datetime\.now\(|strftime\(\s*[\"']%d\.%m\.%Y")


def _hits(text: str) -> list[int]:
    return [n for n, line in enumerate(text.splitlines(), 1) if _SECOND.search(line)]


def test_there_is_one_clock():
    found = [f"{p.relative_to(APP)}:{n}" for p in APP.rglob("*.py") if p.name != "clock.py"
             for n in _hits(p.read_text())]
    assert not found, f"Zeit oder Tag ausserhalb von core/clock: {found}"


def test_the_guard_sees_the_bug_form():
    assert _hits('def _now():\n    return datetime.now(timezone.utc)\n') == [2]
    assert _hits('d.strftime("%d.%m.%Y")') == [1]


def test_a_day_and_a_stamp_read_in_zurich():
    late = datetime(2026, 10, 24, 22, 30, tzinfo=timezone.utc)     # in Zürich schon der 25.
    assert clock.day(late) == "25.10.2026" and clock.stamp(late) == "25.10.2026 00:30"
    assert clock.day(date(2026, 1, 2)) == "02.01.2026" and clock.day(None) == ""
    assert clock.utcnow().tzinfo is timezone.utc
