"""►►► **Eine Sperre über Commits hinweg** – ein Advisory-Lock auf einer eigenen Verbindung. ◄◄◄

Eine Sitzung gibt ihre Verbindung beim Commit an den Pool zurück; eine Sitzungs-Sperre bliebe
dann an einer fremden Verbindung hängen. Darum hält ``hold`` die Sperre auf einer **eigenen**
Verbindung, bis ``let_go`` sie freigibt – und gibt eine Verbindung nie mit halber Sperre in den
Pool zurück (dann wird sie verworfen). Leser: der Takt (``services/tick``, je Aufgabe) und das
Abschreiben einer Aufnahme (``services/recordings``, je Aufnahme).
"""

from typing import Any, Optional

from sqlalchemy import text


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
