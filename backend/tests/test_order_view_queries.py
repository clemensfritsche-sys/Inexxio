"""►►► **Ein Nachbar im Bild kostet wenig** – er wird gezeichnet, nicht bedient. ◄◄◄

Die Auftragsansicht zeigt neben dem Auftrag seine Abweichungen und Quell-Aufträge. Gezeichnet
werden sie ohne Inhalt (die Spalte ist blass, ohne Arbeit, Beleg oder Bedarf) – der Server
rechnet für sie darum nur, was das Bild liest: Schritte, Graph, Zustand. Bug-Form: je Nachbar
die volle Antwort eines Auftrags (Arbeitsliste, Bedarf, Beleg samt Nachziehen der Positionen).
"""

from app.services import order_view as orders_router
from tests.scenarios import World
from tests.test_feed_queries import _counted


def _with_deviation(db):
    w = World(db)
    art = w.article()
    parent = w.produce(art, 3)
    numbers = w.numbers(parent)
    child = w.take(art, numbers[:1], steps=[w.capture(), w.capture(), w.capture()],
                   from_order=parent.object_id)
    return parent, child


def test_a_neighbour_costs_only_what_the_picture_reads(db):
    from app.services import flow as flow_svc
    parent, child = _with_deviation(db)
    branches = flow_svc.build(db, parent).neighbours
    assert branches, "Die Abweichung steht als Nachbar am Elternauftrag."
    db.expire_all()
    with _counted(db) as full:
        orders_router.steps_view(db, child)
    db.expire_all()
    with _counted(db) as neighbour:
        orders_router.related(db, parent, branches, incoming=False)
    # Gezeichnet wird der Nachbar mit Schritten, Graph und Zustand – nie mit seiner vollen
    # Schrittliste (Arbeit, Bedarf, Beleg). Der Graph allein kostet mehr als nichts; die volle
    # Schrittliste kommt nicht noch einmal dazu.
    db.expire_all()
    with _counted(db) as graph:
        flow_svc.build(db, child)
    assert len(neighbour) < len(graph) + len(full), (len(full), len(graph), len(neighbour))
