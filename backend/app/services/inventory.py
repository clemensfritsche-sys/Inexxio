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
    )
    if for_order_id is None:
        q = q.filter(Instance.reserved_for_order_id.is_(None))
    else:
        q = q.filter(or_(Instance.reserved_for_order_id.is_(None),
                         Instance.reserved_for_order_id == for_order_id))
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
