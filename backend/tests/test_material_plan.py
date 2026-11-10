"""**Welche Kiste zuerst, und wo liegt sie?** – zwei Fehler aus der Prüfung der Module.

1. **Älteste zuerst** (``consumption.Need.plan``): die Oberfläche wählte ohne Ortsvorgabe die
   *grösste* Kiste, und der Server folgte ihrer Wahl – FIFO galt nie. Jetzt sagt der Server,
   aus welchen Kisten er nähme, und die Oberfläche liest es.
2. **Eine verschrottete Kiste bricht die Ortskette nicht** (``places._places_of_instances``):
   sie hat keinen Ort mehr; zählte sie mit, lag die ganze Charge «nirgends», und Material darin
   galt nicht mehr als «am Ort».
"""

from app.domain import statuses as st
from app.services import consumption, places
from tests.runner import session
from tests.scenarios import World, free_stock


def test_the_plan_takes_the_oldest_box_first_not_the_biggest():
    need = consumption.Need(
        article_object_id=1, article_name="Schraube", per_unit=1, required=3, available=12,
        here=12, sources=[consumption.Source(instance_object_id=100000001, free=2, here=2),
                          consumption.Source(instance_object_id=100000002, free=10, here=10)])
    assert need.plan() == [100000001, 100000002], (
        "Der Plan nimmt nicht die älteste Kiste zuerst – sondern die grösste.")
    assert need.plan(2) == [100000001]


def test_a_scrapped_box_does_not_break_the_chain():
    w = World(session())
    try:
        crate, crate_numbers = free_stock(w, serialization="batch", quantity=2)
        _, material = free_stock(w)
        shelf = w.unit(free_stock(w)[1][0])          # irgendein Halter: ein Stück als Träger
        boxes = [w.unit(n) for n in crate_numbers]
        places.place_in(w.db, units=boxes, carrier=shelf)
        from app.models import Instance
        holder = (places.OBJECT, w.db.get(Instance, boxes[0].instance_id).object_id)
        mat = w.unit(material[0])
        places.place(w.db, units=[mat], target=holder[1])
        # Eine Kiste der Charge wird verschrottet – sie verliert ihren Ort.
        boxes[0].status = st.VERSCHROTTET
        places.forget(w.db, [boxes[0]])
        w.db.flush()
        assert places.within(w.db, [places.place_of(mat)], (places.UNIT, shelf.id)), (
            "Die verschrottete Kiste hat die Kette der Charge abgebrochen.")
    finally:
        w.db.rollback()
        w.db.close()
