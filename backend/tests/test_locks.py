"""Jede Sperre an EINER Stelle (``core/locks``): die Räume, die Schlüssel, zwei Arten."""

import pathlib
import re

from app.core import locks

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
_SQL = re.compile(r"pg_(?:try_)?advisory")
#: Wo das SQL selbst stehen darf: die Sperren und der Trigger des Siegels (läuft in PostgreSQL).
_HOME = {"core/locks.py", "domain/log.py"}


def _hits(text: str) -> list[int]:
    return [n for n, line in enumerate(text.splitlines(), 1) if _SQL.search(line)]


def test_no_lock_outside_the_one_place():
    found = [f"{p.relative_to(APP)}:{n}" for p in APP.rglob("*.py")
             if p.relative_to(APP).as_posix() not in _HOME for n in _hits(p.read_text())]
    assert not found, f"Advisory-Lock ausserhalb von core/locks: {found}"


def test_the_guard_sees_the_bug_form():
    assert _hits('db.execute(text("SELECT pg_advisory_xact_lock(:s, :k)"))') == [1]


def test_every_space_is_its_own():
    spaces = [locks.TICK, locks.RECORDING, locks.HANDGRIFF, locks.TALK]
    singles = [locks.STARTUP, locks.SEAL]
    assert len(set(spaces)) == len(spaces) and len(set(singles)) == len(singles)
    assert all(0 < s < 2**31 for s in spaces) and locks.key(2**40 + 7) == 7
