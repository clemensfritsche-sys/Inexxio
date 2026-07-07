"""Meldebestand → Auto-Nachbestellung (E) – «Nicht die Zeit soll bestellen, sondern der Bestand».

Fällt der **freie** Bestand eines Artikels unter seinen **Meldebestand** (``safety_stock``),
legt das System einen eigenständigen **Nachschub-Auftrag** (``reason='replenishment'``, ohne
Eltern) an und gibt ihn frei – er fährt den ganz normalen Artikel-Prozess (produzieren oder
beschaffen) und füllt den Bestand bis ``reorder_target`` (bzw. – wenn leer – zurück auf den
Meldebestand) auf.

Wiederverwendung statt neuer Maschinerie: dieselbe Freigabe (``orders.release_order``) und
derselbe Artikel-Prozess wie beim Shop-Nachschub (ADR 003) – nur ohne Eltern-Pegging.

Auslöser (bewusst reaktiv, kein blinder Zeit-Cron):
  * nach einem Bestandsabgang (Verschrottung/Ablauf) – ``check_article``;
  * periodisch über ``evaluate_all`` (Wartungs-Endpoint / künftiger Cloud Scheduler),
    das auch Verkäufe u. a. abdeckt.
Idempotent: solange ein Nachschub (draft/released) für den Artikel offen ist, wird kein
zweiter angelegt.
"""

from sqlalchemy.orm import Session

from ..models import Article, Order
from . import inventory
from .admin import log_audit
from .events import emit
from .objects import next_object_id
from .processes import article_steps
from decimal import Decimal

from .quantity import to_qty, ZERO


def _can_supply(db: Session, article: Article) -> bool:
    """Nachbestellbar nur, wenn der Artikel **freigegeben** ist UND einen **Prozess** hat."""
    return article.status == "released" and bool(article_steps(db, article.id))


def _open_replenishment(db: Session, article_id: int) -> Order | None:
    """Läuft bereits ein Nachschub für diesen Artikel? (Idempotenz)."""
    return (
        db.query(Order)
        .filter(Order.reason == "replenishment", Order.article_id == article_id,
                Order.is_active == True, Order.status.in_(("draft", "released")))
        .first()
    )


def _reorder_qty(article: Article, free) -> Decimal:
    """Bestellmenge = Ziel − Frei, mindestens die MOQ (nie ≤ 0)."""
    point = to_qty(article.safety_stock)
    target = to_qty(article.reorder_target) if article.reorder_target is not None else point
    if target < point:
        target = point
    qty = target - to_qty(free)
    moq = to_qty(article.min_order_qty) if article.min_order_qty is not None else ZERO
    if qty < moq:
        qty = moq
    return qty


def check_article(db: Session, article_id: int, actor_id: int | None) -> Order | None:
    """Einen Artikel prüfen und – falls unter Meldebestand – Nachschub anlegen/freigeben.

    Committet NICHT (der Aufrufer schliesst ab). Liefert den neuen Auftrag oder None."""
    from .orders import release_order

    # ``with_for_update``: parallele Auslöser (Doppel-Sweep, Sweep + Verschrottung)
    # serialisieren am Artikel – sonst legt der Check-then-Act (``_open_replenishment``)
    # zwei Nachbestellungen für denselben Artikel an.
    article = (
        db.query(Article)
        .filter(Article.id == article_id, Article.is_active == True)
        .with_for_update()
        .first()
    )
    if not article or article.safety_stock is None:
        return None                     # kein Meldebestand gepflegt → nichts zu tun
    if not _can_supply(db, article):
        return None                     # kein freigegebener Prozess → nicht automatisch beschaffbar
    if _open_replenishment(db, article_id):
        return None                     # läuft bereits (idempotent)
    free = inventory.available(db, article.id)
    if to_qty(free) >= to_qty(article.safety_stock):
        return None                     # Bestand ausreichend
    qty = _reorder_qty(article, free)
    if to_qty(qty) <= 0:
        return None
    order = Order(
        object_id=next_object_id(db, "order"), status="draft",
        article_id=article.id, quantity=qty, reason="replenishment",
        title=f"Nachbestellung {article.name}",
    )
    db.add(order)
    db.flush()
    log_audit(db, "orders", None,
              f"Auto-Nachbestellung {qty}× {article.name} (frei {free} < Meldebestand {article.safety_stock})",
              actor_id, object_id=order.object_id)
    emit(db, "order.replenishment_opened", object_type="order", object_id=order.object_id,
         payload={"article_id": article.id, "quantity": float(to_qty(qty)), "free": float(to_qty(free))},
         actor_id=actor_id)
    release_order(db, order, actor_id)
    return order


def evaluate_all(db: Session, actor_id: int | None) -> list[Order]:
    """Alle freigegebenen Artikel mit Meldebestand prüfen (Wartungs-/Scheduler-Lauf)."""
    arts = (
        db.query(Article)
        .filter(Article.status == "released", Article.is_active == True,
                Article.safety_stock.isnot(None))
        .all()
    )
    created: list[Order] = []
    for art in arts:
        order = check_article(db, art.id, actor_id)
        if order is not None:
            created.append(order)
    return created
