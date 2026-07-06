"""Haltbarkeit / Ablaufdatum (E) – abgelaufener Bestand → Ausbuchung → Nachbestellung.

Das Ablaufdatum treibt NICHT selbst die Nachbestellung, sondern eine **Ausbuchung**: eine
über ihr ``expires_at`` gelaufene, noch verbrauchbare Instanz wird ausgesteuert
(``disposition='scrapped'``). Das senkt den Bestand → und füttert damit denselben
Meldebestands-Auslöser (``services/replenishment``). So komponieren beide Mechanismen.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from ..models import Article, Instance
from . import inventory, replenishment
from .admin import log_audit
from .events import emit
from .quantity import to_qty
from ..models.base import utcnow


def set_on_release(db: Session, instance: Instance, released_at) -> None:
    """Bei der Freigabe das Ablaufdatum setzen, wenn der Artikel eine Haltbarkeit trägt."""
    if instance.expires_at is not None or released_at is None:
        return
    art = db.query(Article).filter(Article.id == instance.article_id).first()
    days = getattr(art, "shelf_life_days", None) if art else None
    if days:
        instance.expires_at = released_at + timedelta(days=int(days))


def sweep(db: Session, actor_id: int | None) -> dict:
    """Abgelaufene, noch verbrauchbare Instanzen ausbuchen und betroffene Artikel
    nachbestellen. Committet NICHT (der Aufrufer schliesst ab)."""
    now = utcnow()
    expired = (
        db.query(Instance)
        .filter(Instance.is_active == True, Instance.expires_at.isnot(None),
                Instance.expires_at < now,
                Instance.quality == "passed", Instance.disposition == "in_stock")
        .all()
    )
    articles: set[int] = set()
    for inst in expired:
        inst.disposition = "scrapped"
        articles.add(inst.article_id)
        log_audit(db, "instances", None, f"Abgelaufen ({inst.expires_at:%d.%m.%Y}) – ausgebucht",
                  actor_id, object_id=inst.object_id)
        emit(db, "inventory.expired", object_type="instance", object_id=inst.object_id,
             payload={"article_id": inst.article_id, "quantity": float(to_qty(inst.quantity)),
                      "delta": float(-to_qty(inst.quantity)), "polarity": "decrease"},
             actor_id=actor_id)
    # Bestandsabgang → Meldebestand prüfen (nachbestellen).
    reordered = [o for a in articles if (o := replenishment.check_article(db, a, actor_id))]
    return {"expired": len(expired), "reordered": len(reordered)}
