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


def covering_sub_orders(db: Session, parent: Order, article_ids: set | None = None) -> list[Order]:
    """**Wer deckt gerade eine Fehlmenge dieses Auftrags?** – die EINE Antwort.

    Zwei Arten von Unter-Auftrag decken: die **Abweichung** (das Stück ist in Klärung) und
    der **Nachschub** (die Menge wird beschafft/produziert). Beides bedeutet für den Eltern
    dasselbe: die Entscheidung ist getroffen, es läuft.

    **Steckengebliebene zählen nicht.** Ein Unter-Auftrag mit fehlgeschlagenem Schritt
    liefert ohne Klärung nie mehr etwas (``process.is_stalled``) – ihn als «läuft» zu führen
    war die Sackgasse: der Eltern zeigte «wartet auf …», blendete darum die Deckungs-Wege
    aus, und ein zweiter Nachschub galt als überflüssig. Kein Weg nach vorn.

    **Die Kette zählt, nicht nur das direkte Kind** (Testnotiz #406). Nimmt eine Abweichung
    der Abweichung alles, wird die mittlere gegenstandslos und **abgebrochen** – gehalten
    wird die Menge dann von der untersten. Wer nur die direkten Kinder ansieht, findet
    niemanden mehr und stellt die Frage erneut: eine **tote Entscheidung**, obwohl längst
    entschieden ist und es läuft. Gesucht ist der Auftrag, der die Menge **wirklich** hält –
    darum wird die Kette nach unten verfolgt (zyklensicher, begrenzt).

    Zwei Leser, eine Definition: die Anzeige «worauf wartet der Auftrag»
    (``orders._fill_step_shortfall``) und die Idempotenz von ``ensure_supply``."""
    if not parent.object_id:
        return []
    out: list[Order] = []
    seen: set[int] = {parent.id}
    frontier = [parent.object_id]
    for _ in range(10):                              # Tiefen-Schranke statt Endlosschleife
        if not frontier:
            break
        rows = (
            db.query(Order)
            .filter(Order.parent_order_id.in_(frontier), Order.is_active == True,
                    Order.reason.in_(("deviation", "supply")))
            .order_by(Order.object_id)
            .all()
        )
        frontier = []
        for o in rows:
            if o.id in seen:
                continue
            seen.add(o.id)
            if o.status in ("draft", "released"):
                if ((o.reason == "deviation" or article_ids is None or o.article_id in article_ids)
                        and not process.is_stalled(db, o)):
                    out.append(o)
            elif o.status == "inactive" and o.object_id:
                # Abgebrochen: er hält nichts mehr, aber SEIN Nachfolger tut es.
                frontier.append(o.object_id)
    return sorted(out, key=lambda o: o.object_id or 0)


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
        if any(o.reason == "supply" for o in covering_sub_orders(db, order, {art_id})):
            continue   # läuft bereits (ein steckengebliebener zählt NICHT als «läuft»)
        sup = Order(
            object_id=next_object_id(db, "order"), status="draft",
            article_id=art_id, quantity=qty,
            parent_order_id=order.object_id, reason="supply",
            # Aus WELCHEM Schritt der Bedarf stammt – dieselbe generische Angabe wie bei
            # Abweichung und Bereitstellung (``orders.origin_step_id``). Damit steht der
            # Nachschub im Ablauf an seiner Stelle statt in einer Liste daneben (#259/#260).
            origin_step_id=process.blocked_step_for_article(db, order, art_id),
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
