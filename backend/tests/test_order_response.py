"""►►► **Eine Auftragsantwort kostet gleich viele Abfragen – bei 2 wie bei 40 Stück**
(Cleanup B-38). ◄◄◄

Gefahren über die echten Dienstpfade gegen echtes PostgreSQL und **gemessen**, nicht
gelesen: gezählt wird jede Anweisung, die die Antwort an die Datenbank schickt.
"""

from sqlalchemy import event

from app.core.database import engine
from app.routers import orders as router
from tests.runner import session
from tests.scenarios import World


def _queries(products: int) -> int:
    """Wie viele Abfragen kostet ``GET /orders/{id}`` für einen Auftrag mit so vielen
    Einzelinstanzen, nachdem das erste Modul sie alle bestätigt hat?"""
    w = World(session())
    try:
        holder = w.holder(name="Regal B")
        product = w.article(serialization="unit",
                            template=[World.capture(), World.move(holder.object_id)])
        order = w.release(lines=[{"article_object_id": product.object_id,
                                  "quantity": products, "origin": "neu", "units": []}])
        w.run_step(order, w.steps(order)[0])          # füllt den Log: start + step je Stück
        router._to_response(w.db, order)             # einmal warm
        seen = {"n": 0}

        def tally(*_a, **_k):
            seen["n"] += 1
        event.listen(engine, "before_cursor_execute", tally)
        try:
            router._to_response(w.db, order)
        finally:
            event.remove(engine, "before_cursor_execute", tally)
        return seen["n"]
    finally:
        w.db.rollback()
        w.db.close()


def test_an_order_response_does_not_grow_with_its_log():
    """Die Antwort committet, was ``sync_lines`` beim Anzeigen schreibt (``_keep``,
    #937). Mit dem Standard ``expire_on_commit`` war danach jedes schon geladene Objekt
    abgelaufen – die Log-Einträge, die nach den Modulen in die Antwort gehen, wurden
    **einzeln** nachgeladen: eine Abfrage je Eintrag, bis ``EVENT_LIMIT`` (gemessen: 312
    statt 112 Abfragen bei 50 Stück).

    Bug-Form: ``_keep`` committet mit Ablauf → die Zahl wächst mit den Stücken."""
    few, many = _queries(2), _queries(40)
    assert many == few, (
        f"Die Auftragsantwort kostet bei 40 Stück {many} Abfragen, bei 2 Stück {few} – "
        f"etwas wird je Log-Eintrag oder je Stück nachgeladen."
    )
