"""**Stück, Nummer und Log – als Verhalten geprüft, nicht am Quelltext.**

* Die Menge ist die Anzahl der Einzelinstanzen – keine Spalte.
* Eine Einzelinstanz zieht keine Objektnummer: ihre Nummer ist ``<Instanz>-<Suffix>``,
  der Suffix zählt ab 1 je Instanz.
* Eine abgewiesene Freigabe verbraucht keine Objektnummer und legt nichts an.
* Jeder Statuswechsel steht im Log: der Zustand eines Stücks ist der letzte Eintrag.
* Die Exklusivität ist ein partieller Unique-Index in der Datenbank.
* Auftrag und Instanz haben keinen Änderungs- oder Löschpfad.
* Der Prozess eines Auftrags ist eine Kopie der Vorlage, mit Herkunftsstempel.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from tests.scenarios import World, free_stock


def _nextval(db) -> int:
    return int(db.execute(text("SELECT nextval('object_id_seq')")).scalar())


def _drawn(db, fn) -> int:
    """Wie viele Objektnummern ``fn`` gezogen hat (die Messung selbst zieht zwei)."""
    before = _nextval(db)
    fn()
    return _nextval(db) - before - 1


def test_a_quantity_is_never_a_stored_field():
    from app.models import Instance, InstanceUnit

    for model in (Instance, InstanceUnit):
        stored = [c for c in model.__table__.columns.keys() if "quantity" in c]
        assert not stored, f"«{model.__tablename__}» speichert eine Menge: {stored}."


@pytest.mark.parametrize("serialization, instances", [("unit", 3), ("batch", 1)])
def test_a_piece_draws_no_object_number_and_counts_within_its_instance(db, serialization,
                                                                       instances):
    w = World(db)
    article = w.article(serialization=serialization)
    made = {}
    drawn = _drawn(db, lambda: made.setdefault("order", w.produce(article, 3)))
    assert drawn == 1 + instances, (
        f"Die Freigabe zog {drawn} Objektnummern – erwartet sind Auftrag + {instances} "
        f"Instanz(en); eine Einzelinstanz zieht keine.")
    order = made["order"]
    expected = sorted(f"{inst}-{suffix}" for inst in w.instances(order)
                      for suffix in range(1, 3 // instances + 1))
    assert sorted(w.numbers(order)) == expected, (
        "Die Stücknummer ist nicht <Instanznummer>-<Suffix> mit Suffix ab 1 je Instanz.")


def test_a_refused_release_draws_no_number_and_creates_nothing(db):
    from app.models import Order

    w = World(db)
    article, numbers = free_stock(w, quantity=2)
    orders = db.query(Order).count()

    def refused():
        attempt = db.begin_nested()
        with pytest.raises(HTTPException):
            w.take(article, numbers,
                   steps=[World.dispose("scrap", "Ausschuss"), World.capture()])
        attempt.rollback()

    assert _drawn(db, refused) == 0, "Eine abgewiesene Freigabe hat eine Objektnummer verbraucht."
    assert db.query(Order).count() == orders, "Eine abgewiesene Freigabe hat einen Auftrag angelegt."


def test_every_status_change_stands_in_the_log(db):
    from app.models import InstanceUnit

    w = World(db)
    article = w.article(template=[World.capture(), World.dispose("block", "Prüfen")])
    order = w.produce(article, 2)
    w.run_all(order)
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(
        [w.unit(n).id for n in w.numbers(order)])).all()
    assert {u.status for u in units} != {"Freigegeben"}, "Der Fall ändert keinen Zustand."
    for u in units:
        last = db.execute(text(
            "SELECT status_after FROM process_events WHERE instance_unit_id = :u "
            "ORDER BY id DESC LIMIT 1"), {"u": u.id}).scalar()
        assert last == u.status, (
            f"Einzelinstanz #{u.id} steht auf «{u.status}», der Log sagt «{last}» – der "
            f"Zustand wurde ausserhalb der einen Schreibstelle gesetzt.")


def test_the_exclusivity_is_a_partial_unique_index_in_the_database(db):
    row = db.execute(text(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_order_units_active'")).scalar()
    assert row, "Der partielle Unique-Index auf der offenen Zugehörigkeit fehlt."
    assert "UNIQUE" in row and "released_at IS NULL" in row, row


def test_orders_and_instances_have_no_path_to_change_or_delete():
    from app.main import app
    from tests._routes import api_routes

    for path, methods in api_routes(app):
        if path.startswith("/api/v1/erp/orders"):
            assert not methods & {"PATCH", "PUT", "DELETE"}, (
                f"«{path}» ändert oder löscht einen Auftrag ({methods}) – was an einem "
                f"Auftrag geschieht, ist eine Handlung (POST) mit Eintrag im Log.")
        if path.startswith("/api/v1/erp/instances"):
            assert not methods & {"POST", "PATCH", "PUT", "DELETE"}, (
                f"«{path}» schreibt eine Instanz ({methods}) – sie entsteht nur über einen "
                f"Auftrag und verschwindet nie.")


def test_the_order_process_is_a_stamped_copy_of_the_template(db):
    from app.models import ProcessStep

    w = World(db)
    article = w.article()
    order = w.produce(article, 1)
    steps = db.query(ProcessStep).filter(ProcessStep.order_id == order.id).all()
    assert steps and all(s.source_article_id == article.id for s in steps), (
        "Der Auftrag trägt nicht die Herkunft seiner Schritte.")
    assert all(s.source_version is not None for s in steps), "Der Versionsstempel fehlt."
