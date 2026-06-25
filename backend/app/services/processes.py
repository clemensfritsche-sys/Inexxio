"""Prozesse: eigenständige Objekte (Nummer + Name + Lebenszyklus) und ihre
Zuordnung zu Artikeln über die **Prozessstückliste** (``article_process_links``).

Ein Auftrag wählt EINEN Prozess; dessen ``source`` (konzeptuell der «Start-Knoten»)
bestimmt das **Subjekt** und was bei der Anlage gefragt wird:

    produce   → neues Subjekt entsteht (Produktion)         → «Menge?»
    stock     → FIFO-Zugriff auf Bestand (Verkauf, Entnahme) → «Menge?»
    instance  → wirkt auf eine konkrete Instanz (Wartung)    → «welche Instanz?»

Die ``source`` ist **keine** Richtungswahl – die Lager-Richtung wird aus den
Schritten abgeleitet (``stock_effect``).

Ein Prozess kann bei **mehreren** Artikeln in der Stückliste liegen (n:m). Standard-
Prozesse (``is_standard=True``) gelten für jeden Artikel automatisch (geerbt, ohne
expliziten Link).
"""

from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import ArticleProcessLink, ArticleProcessStep, Process

SOURCES = (event_types.PRODUCE, event_types.STOCK, event_types.INSTANCE)
SOURCE_LABELS = {
    "produce": "Neu – Produktion",
    "stock": "Bestand – FIFO",
    "instance": "Konkrete Instanz",
}

# Deklarierte Lager-Richtung (Aggregat der Schritt-Polaritäten, NICHT gewählt).
# ``mixed`` = ein Prozess mit erhöhenden UND mindernden Schritten.
STOCK_EFFECTS = ("increase", "decrease", "mixed", "neutral")


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


# ─── Prozessstückliste (Artikel ↔ Prozess) ──────────────────────────────────────

def linked_process_ids(db: Session, article_id: int) -> list[int]:
    """Prozess-IDs der Stückliste eines Artikels in Reihenfolge (aktive Links)."""
    rows = (
        db.query(ArticleProcessLink.process_id, ArticleProcessLink.position)
        .filter(ArticleProcessLink.article_id == article_id, ArticleProcessLink.is_active == True)
        .order_by(ArticleProcessLink.position, ArticleProcessLink.id)
        .all()
    )
    return [pid for pid, _ in rows]


def own_processes(db: Session, article_id: int) -> list[Process]:
    """Die Prozesse der Stückliste eines Artikels (ohne geerbte Standards),
    in Stücklisten-Reihenfolge."""
    ids = linked_process_ids(db, article_id)
    if not ids:
        return []
    procs = {
        p.id: p for p in db.query(Process).filter(Process.id.in_(ids), Process.is_active == True).all()
    }
    return [procs[i] for i in ids if i in procs]


def standard_processes(db: Session, released_only: bool = False) -> list[Process]:
    q = db.query(Process).filter(Process.is_standard == True, Process.is_active == True)
    if released_only:
        q = q.filter(Process.status == "released")
    return q.order_by(Process.position, Process.id).all()


def available_processes(db: Session, article) -> list[Process]:
    """Wählbare Prozesse eines Artikels (für die Auftrags-Anlage): die Prozesse der
    **Stückliste** + alle **freigegebenen Standardprozesse** (geerbt). Inaktive
    Prozesse fallen heraus."""
    own = own_processes(db, article.id)
    own_ids = {p.id for p in own}
    standards = [s for s in standard_processes(db, released_only=True) if s.id not in own_ids]
    return own + standards


def default_process(db: Session, article_id: int | None) -> Process | None:
    """Default-Prozess eines Artikels: der erste Prozess der Stückliste. Dient als
    Fallback für Aufträge ohne expliziten Prozess."""
    if not article_id:
        return None
    procs = own_processes(db, article_id)
    return procs[0] if procs else None


def process_for_order(db: Session, order) -> Process | None:
    """Der Prozess eines Auftrags: explizit gewählt, sonst Default-Entstehung.

    Ist ``process_id`` gesetzt, wird der Prozess **auch dann** geliefert, wenn er
    inzwischen deaktiviert wurde – ein laufender Auftrag behält seinen Prozess."""
    pid = getattr(order, "process_id", None)
    if pid:
        proc = db.query(Process).filter(Process.id == pid).first()
        if proc:
            return proc
    return default_process(db, order.article_id)


def is_available_for(db: Session, article_id: int | None, process: Process) -> bool:
    """Darf dieser Prozess für diesen Artikel verwendet werden? – Standard (geerbt)
    oder in der Stückliste des Artikels verlinkt."""
    if process.is_standard:
        return True
    if not article_id:
        return False
    return process.id in set(linked_process_ids(db, article_id))


def linked_article_ids(db: Session, process_id: int) -> list[int]:
    rows = (
        db.query(ArticleProcessLink.article_id)
        .filter(ArticleProcessLink.process_id == process_id, ArticleProcessLink.is_active == True)
        .all()
    )
    return [aid for (aid,) in rows]


def linked_article_count(db: Session, process_id: int) -> int:
    return (
        db.query(ArticleProcessLink.id)
        .filter(ArticleProcessLink.process_id == process_id, ArticleProcessLink.is_active == True)
        .count()
    )


def link_process(db: Session, article_id: int, process_id: int, position: int | None = None) -> ArticleProcessLink:
    """Prozess der Stückliste eines Artikels hinzufügen (idempotent: reaktiviert
    einen vorhandenen, inaktiven Link). Schreibt nur (flush)."""
    link = (
        db.query(ArticleProcessLink)
        .filter(ArticleProcessLink.article_id == article_id,
                ArticleProcessLink.process_id == process_id)
        .first()
    )
    if position is None:
        from sqlalchemy import func
        max_pos = (
            db.query(func.max(ArticleProcessLink.position))
            .filter(ArticleProcessLink.article_id == article_id, ArticleProcessLink.is_active == True)
            .scalar()
        )
        position = (max_pos or 0) + 1
    if link:
        link.is_active = True
        link.position = position
    else:
        link = ArticleProcessLink(article_id=article_id, process_id=process_id, position=position)
        db.add(link)
    db.flush()
    return link


def unlink_process(db: Session, article_id: int, process_id: int) -> bool:
    """Prozess aus der Stückliste eines Artikels entfernen (nur den Link – das
    Prozess-Objekt bleibt für andere Artikel bestehen)."""
    link = (
        db.query(ArticleProcessLink)
        .filter(ArticleProcessLink.article_id == article_id,
                ArticleProcessLink.process_id == process_id,
                ArticleProcessLink.is_active == True)
        .first()
    )
    if not link:
        return False
    link.is_active = False
    db.flush()
    return True


# ─── Quelle & Richtung – DEKLARIERT je Ereignistyp (domain.event_types) ──────────
#
# Es gibt KEINE manuelle Wahl. Subjektart (``source``) und Lager-Richtung
# (``stock_effect``) ergeben sich aus den Schritt-Typen – aber über die **deklarative
# Registry** statt einer versteckten if-Kette:
#
#   - ``source``       = Vorrang-Aggregat der ``subject_role`` je Schritt
#                        (stock ≻ produce ≻ instance). Gespeichert in ``processes.source``,
#                        damit die SQL-Filter in weight.py/deactivation.py weiter greifen.
#   - ``stock_effect`` = Aggregat der **Polaritäten** der Schritte (increase/decrease/
#                        mixed/neutral) – ehrlich auch bei gemischten Prozessen.

def derive_source(step_types: set[str]) -> str:
    """Subjektart eines Prozesses – delegiert an die deklarative Registry. Als dünner
    Wrapper erhalten, weil Services/Tests diesen Pfad importieren."""
    return event_types.derive_subject_mode(step_types)


def _active_step_types(db: Session, process_id: int) -> set[str]:
    rows = (
        db.query(ArticleProcessStep.step_type)
        .filter(ArticleProcessStep.process_id == process_id,
                ArticleProcessStep.is_active == True)
        .all()
    )
    return {t for (t,) in rows}


def recompute_source(db: Session, process_id: int) -> str:
    """Quelle (Subjektart) des Prozesses aus seinen aktiven Schritten ableiten und
    speichern. Wird nach jeder Schritt-Strukturänderung aufgerufen (schreibt nur)."""
    proc = db.query(Process).filter(Process.id == process_id).first()
    if not proc:
        return "instance"
    proc.source = derive_source(_active_step_types(db, process_id))
    return proc.source


def stock_effect(db: Session, process: Process | None) -> str:
    """Bestands-Richtung des Prozesses = **Aggregat der deklarierten Polaritäten**
    seiner Schritte (increase | decrease | mixed | neutral). Nicht mehr ein 1:1-Spiegel
    der Subjektart, sondern aus den tatsächlichen Schritten berechnet – damit ein
    Prozess mit Zu- UND Abgang ehrlich als ``mixed`` erscheint."""
    if not process:
        return "neutral"
    return event_types.aggregate_stock_effect(_active_step_types(db, process.id))
