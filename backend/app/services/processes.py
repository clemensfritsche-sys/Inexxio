"""Prozesse: benannte Schrittlisten – Artikel-eigene **und** globale Standardprozesse.

Ein Auftrag wählt EINEN Prozess; dessen ``source`` (konzeptuell der «Start-Knoten»)
bestimmt das Verhalten und was bei der Anlage gefragt wird:

    produce   → neue Instanzen entstehen (Produktion)        → «Menge?»
    stock     → FIFO-Zugriff auf Bestand (Verkauf, Entnahme) → «Menge?»
    instance  → wirkt auf eine konkrete Instanz (Wartung)    → «welche Instanz?»

Standardprozesse (``is_standard=True``, ohne Artikel) gelten **für jeden Artikel
automatisch** (geerbt) – ohne Duplikate, einmal zentral gepflegt.
"""

from sqlalchemy.orm import Session

from ..models import Article, Process

SOURCES = ("produce", "stock", "instance")
SOURCE_LABELS = {
    "produce": "Neu – Produktion",
    "stock": "Bestand – FIFO",
    "instance": "Konkrete Instanz",
}


def get_process(db: Session, process_id: int | None) -> Process | None:
    if not process_id:
        return None
    return (
        db.query(Process)
        .filter(Process.id == process_id, Process.is_active == True)
        .first()
    )


def get_process_by_object_id(db: Session, object_id: int) -> Process | None:
    return (
        db.query(Process)
        .filter(Process.object_id == object_id, Process.is_active == True)
        .first()
    )


def default_process(db: Session, article_id: int | None) -> Process | None:
    """Default-«Entstehung» eines Artikels: erster aktiver produce-Prozess.

    Dient als Rückwärtskompatibilität für Aufträge ohne expliziten Prozess
    (Produktion) – diesen Prozess legt der Backfill je Artikel an."""
    if not article_id:
        return None
    return (
        db.query(Process)
        .filter(
            Process.article_id == article_id,
            Process.is_active == True,
            Process.source == "produce",
        )
        .order_by(Process.position, Process.id)
        .first()
    )


def process_for_order(db: Session, order) -> Process | None:
    """Der Prozess eines Auftrags: explizit gewählt, sonst Default-Entstehung."""
    proc = get_process(db, getattr(order, "process_id", None))
    if proc:
        return proc
    return default_process(db, order.article_id)


def own_processes(db: Session, article_id: int) -> list[Process]:
    return (
        db.query(Process)
        .filter(Process.article_id == article_id, Process.is_active == True)
        .order_by(Process.position, Process.id)
        .all()
    )


def standard_processes(db: Session, released_only: bool = False) -> list[Process]:
    q = db.query(Process).filter(
        Process.is_standard == True, Process.article_id.is_(None), Process.is_active == True
    )
    if released_only:
        q = q.filter(Process.status == "released")
    return q.order_by(Process.position, Process.id).all()


def available_processes(db: Session, article: Article) -> list[Process]:
    """Wählbare Prozesse eines Artikels (für die Auftrags-Anlage): die **eigenen**
    Prozesse + alle **freigegebenen Standardprozesse** (geerbt)."""
    rows = own_processes(db, article.id) + standard_processes(db, released_only=True)
    rows.sort(key=lambda p: (0 if not p.is_standard else 1, p.position, p.id))
    return rows
