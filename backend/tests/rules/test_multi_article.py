"""**Jedes Modul kann mehrere Artikel** (Testnotiz #593).

Der gemeldete Fall: zwei Schweisskonstruktionen gehen mit EINEM Auftrag zum Verzinken – ein
Beschaffungs-Modul, zwei Artikel, darunter je ihre Instanzen. Die Frage war, ob das trägt.

Die Antwort ist **ja**, und sie hat zwei Formen, die beide richtig sind:

    eigene Fachzeile je Position   Beschaffung und Verkauf tragen einen **Beleg je Artikel**
                                   (gleicher ``step_id``). Bei der Beschaffung schreitet jede
                                   Bestellung EIGENSTÄNDIG fort (eigener Lieferant, eigene
                                   Lieferzeit); beim Verkauf ist es EIN Vorgang mit einem
                                   Beleg je Position (ein Kunde, eine Zahlung).
    artikel-unabhängig             Bewegung, Aussondern und Datenerfassung arbeiten auf den
                                   **Instanzen** des Auftrags – sie fragen gar nicht nach dem
                                   Artikel. Die Ressource hat ihre eigenen Zeilen und skaliert
                                   über die Summe der Positionsmengen.

Beides ist «mehrartikel-fähig»; ein Modul, das nichts vom Artikel wissen muss, braucht dafür
keinen Mechanismus. Diese Datei prüft die Wirkung über die echten Dienst-Pfade – damit die
Aussage nicht bei der nächsten Änderung still kippt.
"""

from decimal import Decimal

from .conftest import _make_order, _num


def _two_article_world(db, world, step_kind: str, **step_kw):
    """Ein Auftrag über ZWEI Artikel mit genau EINEM Schritt des gefragten Typs."""
    from app.models import Article, ArticleProcessStep, Order, OrderLine
    from app.routers import orders as R
    user, _ = world
    arts = []
    for n in (1, 2):
        a = Article(object_id=_num(db), name=f"Schweisskonstruktion {n} {_num(db)}",
                    unit="pcs", serialization="batch", status="released")
        db.add(a)
        db.flush()
        arts.append(a)
    order = Order(object_id=None, article_id=None, quantity=None, status="draft")
    db.add(order)
    db.flush()
    for a, qty in zip(arts, (3, 2)):
        db.add(OrderLine(order_id=order.id, article_id=a.id, quantity=Decimal(qty)))
    db.add(ArticleProcessStep(order_id=order.id, step_type=step_kind, position=0, **step_kw))
    db.flush()
    R._do_release(db, order, user.id)
    db.commit()
    db.refresh(order)
    return order, arts


def test_procurement_carries_one_order_per_article(db, world):
    """**Beschaffung: ein Beleg je Artikel, ein Schritt.**

    Zwei Konstruktionen zum Verzinken → zwei Bestellungen unter demselben Schritt, jede mit
    ihrer eigenen Menge. Sie schreiten unabhängig fort: die eine kann geliefert sein, während
    die andere noch offeriert wird."""
    from app.models import PurchaseOrder, UserProfile
    from app.services import process

    sup = UserProfile(firebase_uid=f"s{_num(db)}", email=f"s{_num(db)}@t.ch",
                      role="supplier", object_id=_num(db))
    db.add(sup)
    db.flush()
    order, arts = _two_article_world(db, world, "purchase", mode="supplier", supplier_id=sup.id)

    pos = db.query(PurchaseOrder).filter(PurchaseOrder.order_id == order.id).all()
    assert {p.article_id for p in pos} == {a.id for a in arts}, (
        "Jede Position bekommt ihre eigene Bestellung (#593).")
    assert {p.quantity for p in pos} == {Decimal(3), Decimal(2)}, (
        "…mit ihrer eigenen Menge – nicht der des Auftrags.")
    assert len({p.step_id for p in pos}) == 1, (
        "…und alle unter EINEM Schritt: ein Beschaffungs-Modul, nicht zwei.")
    steps = process.build_order_steps(db, order)
    assert len([s for s in steps if s["step_type"] == "purchase"]) == 1


def test_instance_modules_do_not_ask_for_an_article(db, world):
    """**Bewegung · Aussondern · Datenerfassung arbeiten auf Instanzen.**

    Sie brauchen keinen Mehrartikel-Mechanismus, weil sie den Artikel gar nicht lesen – ihre
    Fachzeile hat schlicht keine Artikel-Spalte bzw. eine optionale. Das ist die zweite,
    ebenso gültige Form von «mehrartikel-fähig»."""
    from app.models import Disposal, Inspection, Movement

    assert not hasattr(Movement, "article_id")
    assert not hasattr(Disposal, "article_id")
    # Die Datenerfassung trägt eine **optionale** Artikel-Spalte: sie bleibt EINE Fachzeile
    # über alle Instanzen des Auftrags, auch wenn diese zu verschiedenen Artikeln gehören.
    assert Inspection.__table__.c.article_id.nullable, (
        "Eine Datenerfassung über mehrere Artikel darf nicht an einer Artikel-Pflicht scheitern.")


def test_every_module_scales_with_the_positions(db, world):
    """**Wer eine Menge braucht, nimmt die Summe der Positionen** – nicht ``order.quantity``.

    Bei einem Mehrpositionen-Auftrag ist die Anker-Menge NULL; ein Modul, das sie liest,
    rechnete mit nichts. ``order_lines.effective_quantity`` ist die eine Antwort darauf."""
    import inspect

    from app.services import inspection as insp, order_lines, resource

    order, _ = _two_article_world(db, world, "inspection", sample_percent=100)
    assert order.quantity is None, "Ein Mehrpositionen-Auftrag hat keine Anker-Menge."
    assert order_lines.effective_quantity(db, order) == Decimal(5), (
        "Die wirksame Menge ist die Summe der Positionen (3 + 2).")
    for mod in (insp, resource):
        assert "effective_quantity" in inspect.getsource(mod), (
            f"{mod.__name__} muss die Positionsmengen lesen, nicht die Anker-Menge (#593).")
