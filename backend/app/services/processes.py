"""Prozess = die geordnete Schrittliste eines **Artikels** (wie etwas entsteht) oder
eines **Auftrags** (individueller Ablauf auf bestehenden Instanzen).

Es gibt KEIN eigenständiges Prozess-Objekt mehr (keine Objektnummer, kein eigener
Lebenszyklus, keine n:m-Verknüpfung). Ein Schritt (``ArticleProcessStep``) hängt
entweder am Artikel (``article_id``) oder am Auftrag (``order_id``).
"""

from sqlalchemy.orm import Session

from ..models import ArticleProcessStep


def article_steps(db: Session, article_id: int | None) -> list[ArticleProcessStep]:
    """Die aktiven Schritte des Artikel-Prozesses (wie der Artikel entsteht)."""
    if not article_id:
        return []
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article_id,
                ArticleProcessStep.order_id.is_(None),
                ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def order_custom_steps(db: Session, order_id: int | None) -> list[ArticleProcessStep]:
    """Die aktiven Schritte des individuellen Auftrags-Prozesses (CUSTOM-Modus)."""
    if not order_id:
        return []
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.order_id == order_id,
                ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def has_custom_steps(db: Session, order) -> bool:
    """CUSTOM-Modus? – der Auftrag trägt eigene Prozessschritte (auf vorhandene Instanzen)."""
    return (
        db.query(ArticleProcessStep.id)
        .filter(ArticleProcessStep.order_id == order.id,
                ArticleProcessStep.is_active == True)
        .first()
        is not None
    )
