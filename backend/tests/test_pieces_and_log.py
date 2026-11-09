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
from app.domain.errors import Rejected
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


def test_a_group_has_no_state_of_its_own():
    """**Nur das Stück hat einen Zustand** – Auftrag und Instanz leiten ab, gespeichert wird er
    dort nie (#675: eine Charge mit gemischten Stücken hätte keine richtige Antwort). Die
    Spalten ``orders.status``/``instances.status`` standen einmal da und schrieb niemand."""
    from app.models import Instance, Order
    from app.schemas.instance import InstanceResponse, InstanceSummary, InstanceUnitResponse

    for model in (Order, Instance):
        assert "status" not in model.__table__.columns, f"«{model.__tablename__}» speichert einen Zustand."
    for schema in (InstanceResponse, InstanceSummary):
        assert "status" not in schema.model_fields, f"{schema.__name__} behauptet einen Zustand."
    assert "status" in InstanceUnitResponse.model_fields


def test_the_start_of_a_piece_is_read_from_the_log(db):
    """**Wann ein Stück in einen Auftrag eintrat, sagt der Log** – je Auftrag, ohne Spalte."""
    from app.services import order_state

    w = World(db)
    article = w.article()
    parent = w.produce(article, 2)
    numbers = w.numbers(parent)
    child = w.take(article, numbers[:1], steps=[World.capture()], from_order=parent.object_id)
    ids = [w.unit(n).id for n in numbers]
    assert set(order_state.started_at(db, parent, ids)) == set(ids)
    assert set(order_state.started_at(db, child, ids)) == {ids[0]}, (
        "Ein Stück, das diesen Auftrag nie betrat, hat hier keinen Start.")


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
        with pytest.raises(Rejected):
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
            "SELECT status_after FROM process_log WHERE instance_unit_id = :u "
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
        if path.startswith("/api/v1/erp/articles/{"):
            assert not methods & {"POST", "PATCH", "PUT", "DELETE"}, (
                f"«{path}» schreibt an einen freigegebenen Artikel ({methods}) – geändert wird "
                f"er nie; eine Änderung ist ein neuer Artikel, der ihn ersetzt.")
        if path.startswith("/api/v1/erp/instances"):
            assert not methods & {"POST", "PATCH", "PUT", "DELETE"}, (
                f"«{path}» schreibt eine Instanz ({methods}) – sie entsteht nur über einen "
                f"Auftrag und verschwindet nie.")


def test_the_order_process_is_a_stamped_copy_of_the_template(db):
    from app.models import ProcessStep

    w = World(db)
    article = w.article()
    order = w.produce(article, 1)
    from app.services.article_process import steps_of

    def shape(rows):
        return [(r.module_type, r.status_before, r.status_after, r.config or None) for r in rows]

    steps = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
             .order_by(ProcessStep.position).all())
    assert steps and shape(steps) == shape(steps_of(db, article)), (
        "Der Prozess im Auftrag ist keine Kopie der Vorlage des Artikels.")
