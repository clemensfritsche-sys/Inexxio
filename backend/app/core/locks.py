"""►►► **Jede Sperre – EINE Stelle** (Advisory-Locks: die Räume, die Schlüssel, zwei Arten). ◄◄◄

* **bis zum Ende der Transaktion** (``xact``): Start, ein Handgriff, ein Gespräch.
* **über Commits hinweg** (``hold`` · ``let_go``): eine Aufgabe des Takts, eine Aufnahme –
  siehe unten.

Die Zahlen der Räume bleiben, wie sie sind: während eines Deploys laufen alte und neue Fassung
nebeneinander, eine neue Zahl hiesse zwei Sperren für dieselbe Sache.


Eine Sitzung gibt ihre Verbindung beim Commit an den Pool zurück; eine Sitzungs-Sperre bliebe
dann an einer fremden Verbindung hängen. Darum hält ``hold`` die Sperre auf einer **eigenen**
Verbindung, bis ``let_go`` sie freigibt – und gibt eine Verbindung nie mit halber Sperre in den
Pool zurück (dann wird sie verworfen). Leser: der Takt (``services/tick``, je Aufgabe) und das
Abschreiben einer Aufnahme (``services/recordings``, je Aufnahme).
"""

from typing import Any, Optional

from sqlalchemy import text

# ─── Die Räume (zwei Schlüssel: Raum, Nummer) ────────────────────────────────────────────
TICK = 778_899          # eine Aufgabe des Takts (``services/tick``)
RECORDING = 778_900     # eine Aufnahme (``services/recordings``)
HANDGRIFF = 5051        # «dieser Handgriff läuft gerade» (``services/handgriff``)
TALK = 5052             # «die KI antwortet in diesem Gespräch» – Stream und Takt nie beide
# ─── Einzelne Schlüssel (ein Schlüssel; überschneiden sich nie mit den Räumen) ─────────
STARTUP = 778_899_001   # der Start (``main``): Trigger einer nach dem anderen
SEAL = 778_899_003      # das Siegel des Logs (im SQL von ``domain/log``)


def key(number: int) -> int:
    """Eine Nummer (Objekt, Zeile) als Schlüssel – passt in die 31 Bit eines Raums."""
    return number & 0x7FFF_FFFF


def xact(db: Any, space: int, number: Optional[int] = None, wait: bool = True) -> bool:
    """►► Die Sperre bis zum Ende der Transaktion. ``wait=False``: ``False``, wenn sie jemand
    hält. Ohne ``number`` ist ``space`` ein einzelner Schlüssel (``STARTUP``). ◄◄"""
    fn = "pg_advisory_xact_lock" if wait else "pg_try_advisory_xact_lock"
    if number is None:
        got = db.execute(text(f"SELECT {fn}(:s)"), {"s": space}).scalar()
    else:
        got = db.execute(text(f"SELECT {fn}(:s, :k)"), {"s": space, "k": key(number)}).scalar()
    return True if wait else bool(got)


def hold(space: int, key: int) -> Optional[Any]:
    """Die Sperre ``(space, key)`` – ihre Verbindung, oder ``None``, wenn sie gerade jemand hält."""
    from .database import engine
    con = engine.connect()
    try:
        got = con.execute(text("SELECT pg_try_advisory_lock(:s, :k)"),
                          {"s": space, "k": key}).scalar()
        con.commit()
    except BaseException:
        con.invalidate()
        con.close()
        raise
    if got:
        return con
    con.close()
    return None


def let_go(con: Any, space: int, key: int) -> None:
    """Die Sperre freigeben und die Verbindung zurückgeben – scheitert das, wird sie verworfen."""
    try:
        con.execute(text("SELECT pg_advisory_unlock(:s, :k)"), {"s": space, "k": key})
        con.commit()
    except Exception:       # noqa: BLE001 – die Verbindung nie mit der Sperre zurückgeben
        con.invalidate()
    finally:
        con.close()
