"""**Der Lieferant sieht den Auftrag durch SEIN Modul** (Testnotiz #594).

Die Runde davor (#592) hatte ihm den vollständigen Prozess gezeigt und nur die Bedienung
beschränkt – der Ablauf sei schliesslich ehrlich. Der Nutzer hat das zurückgenommen: was
intern mit dem Material geschieht, geht ihn nichts an.

Geprüft wird die **Wirkung** über den echten Antwort-Aufbau, nicht die Formulierung im
Code: was in der Antwort steht, ist das, was am Bildschirm ankommt. Ein Filter in der
Oberfläche wäre eine Bitte – die Grenze muss hier halten.
"""

from decimal import Decimal

from .conftest import _make_order, _num


def _supplier(db, name: str):
    from app.models import UserProfile
    u = UserProfile(firebase_uid=f"{name}{_num(db)}", email=f"{name}{_num(db)}@test.ch",
                    role="supplier", object_id=_num(db))
    db.add(u)
    db.flush()
    return u


def _two_supplier_order(db, world):
    """Ein Auftrag mit ZWEI Beschaffungen (verschiedene Lieferanten) + einer Datenerfassung."""
    from app.models import Article, ArticleProcessStep, Order, OrderLine
    from app.routers import orders as R
    user, _ = world
    a, b = _supplier(db, "sa"), _supplier(db, "sb")
    arts = []
    for n in (1, 2):
        art = Article(object_id=_num(db), name=f"Kaufteil {n} {_num(db)}", unit="pcs",
                      serialization="batch", status="released")
        db.add(art)
        db.flush()
        arts.append(art)
    order = Order(object_id=None, article_id=None, quantity=None, status="draft")
    db.add(order)
    db.flush()
    for art in arts:
        db.add(OrderLine(order_id=order.id, article_id=art.id, quantity=Decimal(2)))
    # Zwei Beschaffungs-Schritte (je ein Lieferant) + ein internes Modul.
    db.add(ArticleProcessStep(order_id=order.id, step_type="purchase", position=0,
                              mode="supplier", supplier_id=a.id))
    db.add(ArticleProcessStep(order_id=order.id, step_type="purchase", position=1,
                              mode="supplier", supplier_id=b.id))
    db.add(ArticleProcessStep(order_id=order.id, step_type="inspection", position=2,
                              sample_percent=100))
    db.flush()
    R._do_release(db, order, user.id)
    db.commit()
    db.refresh(order)
    return order, a, b


def _produced_order(db, world):
    """Ein Erzeugungsauftrag, dessen Artikel beschafft und danach geprüft wird.

    Anders als der Mehrpositionen-Auftrag oben erzeugt er bei der Freigabe Instanzen – und
    damit gibt es überhaupt ein Journal, dessen Zurückhalten sich prüfen lässt."""
    from app.models import Article, ArticleProcessStep
    user, _ = world
    sup = _supplier(db, "sp")
    art = Article(object_id=_num(db), name=f"Kaufteil {_num(db)}", unit="pcs",
                  serialization="batch", status="released")
    db.add(art)
    db.flush()
    db.add(ArticleProcessStep(article_id=art.id, step_type="purchase", position=0,
                              mode="supplier", supplier_id=sup.id))
    db.add(ArticleProcessStep(article_id=art.id, step_type="inspection", position=1,
                              sample_percent=100))
    db.commit()
    order, _inst = _make_order(db, art, user, 4)
    return order, sup


def test_a_supplier_only_sees_his_own_procurement(db, world):
    """**Sein Modul – und zwar SEINES.**

    Das interne Modul (Datenerfassung) war der gemeldete Befund; die Beschaffung des
    ANDEREN Lieferanten wäre derselbe Fehler eine Stufe schlimmer (er sähe, bei wem sein
    Kunde sonst noch bestellt). Massgeblich ist darum der **Beleg**, nicht der Schritttyp."""
    from app.services.orders import to_order_response

    order, a, b = _two_supplier_order(db, world)

    staff_view = to_order_response(db, order)
    assert {s.step_type for s in staff_view.steps} == {"purchase", "inspection"}, (
        "Das Personal sieht den ganzen Ablauf.")
    assert len([s for s in staff_view.steps if s.step_type == "purchase"]) == 2

    for who, other in ((a, b), (b, a)):
        view = to_order_response(db, order, viewer=who)
        assert [s.step_type for s in view.steps] == ["purchase"], (
            "Der Lieferant sieht genau ein Modul: seine Beschaffung (#594).")
        got = {p.supplier_id for s in view.steps for p in (s.purchases or [])}
        assert got == {who.id}, (
            f"…und zwar seine eigene – nicht die des anderen Lieferanten "
            f"{other.object_id} (#594).")


def test_what_describes_the_internal_course_stays_with_the_staff(db, world):
    """Der Lauf des Auftrags ist intern: Verlauf, Material auf den Kanten und die
    Unter-Aufträge. Wie viel er zu liefern hat, steht in **seinem** Beleg – dafür braucht
    es weder das Journal noch den Bestand seines Kunden."""
    from app.services.orders import to_order_response

    order, a = _produced_order(db, world)
    staff, sup = to_order_response(db, order), to_order_response(db, order, viewer=a)

    assert staff.history, "Das Personal sieht den Verlauf…"
    assert not sup.history, "…der Lieferant nicht (#594)."
    assert not sup.flow_lots and not sup.flow_lost, (
        "Kein Material auf den Kanten – das ist der Bestand seines Kunden.")
    assert all(not e.lots for e in sup.flow_edges), (
        "Auch nicht über die fertig gerechnete Achse – sonst wäre die Grenze halb.")
    for empty in (sup.deviations, sup.supply_orders, sup.returns, sup.provisionings):
        assert empty == [], "Unter-Aufträge beschreiben den internen Lauf."


def test_a_customer_sees_no_step_at_all(db, world):
    """Ein Kunde kommt gar nicht an einen ERP-Auftrag (``visible_orders``) – und wenn doch
    jemand die Antwort für ihn baut, ist sie leer. Die Regel ist «woran bin ich beteiligt»,
    nicht «bin ich zufällig kein Personal»."""
    from app.models import UserProfile
    from app.services.orders import to_order_response

    order, _, _ = _two_supplier_order(db, world)
    cust = UserProfile(firebase_uid=f"c{_num(db)}", email=f"c{_num(db)}@test.ch",
                       role="customer", object_id=_num(db))
    db.add(cust)
    db.flush()
    assert to_order_response(db, order, viewer=cust).steps == []
