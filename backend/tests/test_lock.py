"""**Die Sperrdatei passt zu requirements.txt** – Docker und CI installieren aus
``requirements.lock`` (jede Abhängigkeit mit Prüfsumme). Wer in ``requirements.txt`` eine
Version ändert und die Sperrdatei nicht neu erzeugt, bekäme im Build die alte – das fängt
dieser Wächter. Neu erzeugen::

    cd backend && uv pip compile requirements.txt --python-version 3.12 \\
        --python-platform x86_64-unknown-linux-gnu --generate-hashes --no-header -o requirements.lock
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def _pins(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?==([^\s;\\]+)", line.strip())
        if m:
            out[re.sub(r"[-_.]+", "-", m.group(1)).lower()] = m.group(3)
    return out


def test_every_direct_pin_is_locked_with_the_same_version():
    wanted = _pins((HERE / "requirements.txt").read_text())
    locked = _pins((HERE / "requirements.lock").read_text())
    wrong = {n: (v, locked.get(n)) for n, v in wanted.items() if locked.get(n) != v}
    assert not wrong, f"requirements.lock ist veraltet (gewollt, gesperrt): {wrong}"


def test_every_locked_package_has_a_hash():
    text = (HERE / "requirements.lock").read_text()
    blocks = re.split(r"\n(?=[A-Za-z0-9])", text.strip())
    bare = [b.split()[0] for b in blocks if "==" in b.split()[0] and "--hash=" not in b]
    assert not bare, f"ohne Prüfsumme: {bare}"
