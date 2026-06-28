"""Bestandslogik: Verfügbarkeit, Reservierung (mengengenau) und FIFO-Allokation.

Reservierung ist **mengengenau**: bei der Auftragsfreigabe wird je Komponente nur
die **benötigte Menge** gesperrt. Übersteigt eine Charge den Bedarf, wird sie
geteilt – der reservierte Teil geht an den Auftrag, der Rest bleibt frei für
andere Aufträge (behebt das frühere Über-Sperren ganzer Chargen).

Verfügbarkeit wird per **SQL-Aggregat** (indiziert) berechnet, nicht durch Laden
und Summieren aller Instanzen (Punkt 6 der Architektur-Review).
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models import Instance


def claim_clauses(for_order_id: int | None) -> tuple:
    """Eine Instanz ist für eine **neue/laufende Allokation frei**, wenn sie nicht fest
    **reserviert** ist (``reserved_for_order_id``) – ausser für genau diesen Auftrag
    (``for_order_id``).

    Die Reservierung wird **erst bei der Freigabe** scharf (``_allocate_stock_subject``).
    Eine blosse Vormerkung im Entwurf (``subject_of_order_id``) blockiert den Bestand für
    andere Aufträge **nicht** – sie ist nur eine unverbindliche Auswahl. Wer zuerst
    freigibt, reserviert; ein später freigegebener Auftrag mit demselben Pin scheitert dann
    sauber an der Reservierungs-Prüfung. Die Reservierung wird bei Abschluss/Abbruch gelöst."""
    if for_order_id is None:
        return (Instance.reserved_for_order_id.is_(None),)
    return (
        or_(Instance.reserved_for_order_id.is_(None), Instance.reserved_for_order_id == for_order_id),
    )


def fifo_candidates(db: Session, article_db_id: int, for_order_id: int | None = None) -> list[Instance]:
    """Verbrauchbare/verkäufliche Instanzen eines Artikels: **freigegeben** (qc passed,
    am Lager), Restmenge > 0, **FIFO nach Freigabe** (``released_at``, ersatzweise
    ``created_at``), dann Objektnummer.

    Verfügbarkeit: ``for_order_id=None`` liefert nur **freie** Instanzen (weder reserviert
    noch gepinnt) – die Basis für eine neue Bindung. Mit ``for_order_id`` kommen zusätzlich
    die **für diesen Auftrag** reservierten/gebundenen Instanzen dazu und werden **zuerst**
    verbraucht (siehe ``claim_clauses``)."""
    q = db.query(Instance).filter(
        Instance.article_id == article_db_id,
        Instance.is_active == True,
        *in_stock_clauses(),
        *claim_clauses(for_order_id),
    )
    rows = q.all()
    rows.sort(key=lambda i: (
        0 if (for_order_id is not None and i.reserved_for_order_id == for_order_id) else 1,
        i.released_at or i.created_at, i.object_id or 0))
    return rows


def available_qty(candidates: list[Instance]) -> int:
    """Summe der Restmengen einer Kandidatenliste (Stück)."""
    return sum(c.quantity for c in candidates)


def in_stock_clauses() -> tuple:
    """SQLAlchemy-Bedingungen für „am Lager verfügbar" – die EINE Stelle, die die
    beiden Achsen kombiniert: qualitativ freigegeben (``quality=passed``) UND dispositiv
    am Lager (``disposition=in_stock``), Restmenge > 0. Verbaute/verkaufte/verschrottete
    Instanzen tragen eine andere ``disposition`` und fallen damit automatisch heraus."""
    return (
        Instance.quality == "passed",
        Instance.disposition == "in_stock",
        Instance.quantity > 0,
    )


def allocate(need: int, quantities: list[int]) -> list[int]:
    """FIFO-Allokation (rein/testbar): wie viel je Kandidat (in Reihenfolge) belegt
    wird, bis ``need`` gedeckt ist. Summe ≤ need; nie mehr als der Kandidat hat."""
    out: list[int] = []
    remaining = need
    for q in quantities:
        take = min(remaining, q) if remaining > 0 else 0
        out.append(take)
        remaining -= take
    return out


def available(db: Session, article_db_id: int, for_order_id: int | None = None) -> int:
    """Verfügbare Menge eines Artikels (SQL-Aggregat): freigegeben (``passed``),
    Restmenge > 0. ``for_order_id=None`` zählt nur unreservierten Bestand; mit
    ``for_order_id`` zusätzlich die für diesen Auftrag reservierte Menge."""
    q = db.query(func.coalesce(func.sum(Instance.quantity), 0)).filter(
        Instance.article_id == article_db_id,
        Instance.is_active == True,
        *in_stock_clauses(),
        *claim_clauses(for_order_id),
    )
    return int(q.scalar() or 0)


def on_hand(db: Session, article_db_id: int) -> int:
    """Gesamter freigegebener Lagerbestand eines Artikels (Stück, SQL-Aggregat)."""
    return int(
        db.query(func.coalesce(func.sum(Instance.quantity), 0)).filter(
            Instance.article_id == article_db_id,
            Instance.is_active == True,
            *in_stock_clauses(),
        ).scalar() or 0
    )
