"""Bedarf → Nachschub: deckt nicht vorrätige Bedarfe eines Auftrags über Unter-Aufträge.

**EIN Mechanismus** für ERP (Knopf «Nachschub anlegen») und Shop (auto bei «auf Bestellung»):
für jeden offenen Bedarf eines Auftrags (Subjekt fehlt / Komponente fehlt, siehe
``process.order_shortfalls``) wird ein **Nachschub-Unter-Auftrag** (``reason='supply'``)
angelegt und freigegeben, der die Fehlmenge **produziert/beschafft** (der ganz normale
Artikel-Prozess) und sie bei Abschluss an den Eltern **pinnt** (``process._peg_supply_to_
parent``). Der betroffene Schritt des Eltern ist bis dahin «blockiert» – abgeleitet aus dem
Bestand, kein Auto-Trigger.

**Rekursiv & zyklensicher:** fehlt dem Nachschub selbst Material, deckt es ein weiterer
Nachschub (mehrstufige Stückliste, derselbe Mechanismus). Eine zirkuläre Stückliste
(A braucht B braucht A) wird über die Artikel-Kette erkannt und nicht weiter expandiert.
"""

from sqlalchemy.orm import Session

from ..models import Article, Order
from . import process
from .admin import log_audit
from .events import emit
from .objects import next_object_id
from .processes import article_steps


def _can_supply(db: Session, article: Article) -> bool:
    """Nachschub ist nur möglich, wenn der Artikel **freigegeben** ist UND einen **Prozess**
    hat (produzierbar oder – mit purchase-Schritt – beschaffbar). Sonst kann das System
    nichts herstellen → der Bedarf bleibt blockiert (manuelle Klärung)."""
    return article.status == "released" and bool(article_steps(db, article.id))


def _existing_open_supply(db: Session, parent: Order, article_id: int) -> Order | None:
    """Läuft bereits ein Nachschub dieses Eltern für diesen Artikel? (Idempotenz)."""
    return (
        db.query(Order)
        .filter(Order.parent_order_id == parent.object_id, Order.reason == "supply",
                Order.article_id == article_id, Order.is_active == True,
                Order.status.in_(("draft", "released")))
        .first()
    )


def _blocked_step_id(db: Session, order: Order, article_id: int) -> int | None:
    """Der Schritt, dessen Fehlmenge diesen Nachschub auslöst – für die Anzeige im Ablauf.

    Gesucht wird der erste blockierte Schritt, der genau diesen Artikel vermisst. Findet
    sich keiner (z. B. Nachschub von Hand angestossen), bleibt die Angabe leer und der
    Nachschub erscheint – wie eine Abweichung ohne Ursprung – am Anfang des Ablaufs."""
    for info in process.build_order_steps(db, order):
        if info["state"] != "blocked":
            continue
        step = info["step"]
        if any(a == article_id for a in process.step_shortfalls(db, order, step)):
            return step.id
    return None


def ensure_supply(db: Session, order: Order, actor_id: int | None,
                  _chain: set | None = None) -> list[Order]:
    """Für jeden ungedeckten Bedarf des Auftrags einen Nachschub-Unter-Auftrag anlegen +
    freigeben (rekursiv, idempotent, zyklensicher). Committet NICHT (der Aufrufer schliesst
    ab). Liefert die neu angelegten Nachschub-Aufträge (auch der tieferen Ebenen)."""
    from .orders import release_order

    # Nebenläufigkeits-Schutz: den Eltern-Auftrag sperren, damit parallele Auslöser
    # (Shop-Webhook + ERP-Knopf «Nachschub anlegen») serialisieren – der Idempotenz-Check
    # ``_existing_open_supply`` ist sonst ein Check-then-Act und legt doppelten Nachschub an.
    db.query(Order).filter(Order.id == order.id).with_for_update().first()

    # ``chain`` = Artikel, die ein **Vorfahre bereits produziert** (Nachschub-Kette). Den
    # eigenen Artikel NICHT vorab eintragen: ein Verkauf von P braucht legitim Nachschub von P.
    chain = set(_chain or ())
    created: list[Order] = []
    for art_id, qty in process.order_shortfalls(db, order).items():
        if qty <= 0:
            continue
        if art_id in chain:
            # Zirkuläre Stückliste (A braucht B braucht A) – nicht weiter explodieren.
            log_audit(db, "orders", None,
                      f"Nachschub übersprungen: zirkulärer Bedarf (Artikel {art_id})",
                      actor_id, object_id=order.object_id)
            continue
        art = db.query(Article).filter(Article.id == art_id).first()
        if not art or not _can_supply(db, art):
            continue   # kein freigegebener Prozess → nicht automatisch beschaffbar (bleibt blockiert)
        if _existing_open_supply(db, order, art_id):
            continue   # läuft bereits
        sup = Order(
            object_id=next_object_id(db, "order"), status="draft",
            article_id=art_id, quantity=qty,
            parent_order_id=order.object_id, reason="supply",
            # Aus WELCHEM Schritt der Bedarf stammt – dieselbe generische Angabe wie bei
            # Abweichung und Bereitstellung (``orders.origin_step_id``). Damit steht der
            # Nachschub im Ablauf an seiner Stelle statt in einer Liste daneben (#259/#260).
            origin_step_id=_blocked_step_id(db, order, art_id),
            title=f"Nachschub für {order.object_id}: {art.name}",
        )
        db.add(sup)
        db.flush()
        log_audit(db, "orders", None, f"Nachschub für {order.object_id} ({qty}× {art.name})",
                  actor_id, object_id=sup.object_id)
        emit(db, "order.supply_opened", object_type="order", object_id=sup.object_id,
             payload={"parent": order.object_id, "article_id": art_id, "quantity": qty},
             actor_id=actor_id)
        release_order(db, sup, actor_id)             # produziert/beschafft (erzeugt Instanzen)
        created.append(sup)
        # Tiefer: dieser Nachschub produziert ``art_id`` → in die Kette (Zyklus-Schutz).
        created.extend(ensure_supply(db, sup, actor_id, chain | {art_id}))
    return created
