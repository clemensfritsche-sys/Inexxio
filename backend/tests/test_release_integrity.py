"""**Freigabe und Bestätigen halten unter Gleichzeitigkeit – und der Entwurf sagt dasselbe.**

Drei Regeln, je gegen ihre Bug-Form gegengeprüft:

* Was die Freigabe abweist, meldet der Entwurf mit **demselben** Satz
  (``process._checked`` ist die eine Prüfung).
* Zwei gleichzeitige Freigaben auf dasselbe freie Stück: eine gewinnt, die andere bekommt
  ein **409 mit einem Satz**, nicht eine rohe Datenbankmeldung.
* Zwei gleichzeitige Bestätigungen am selben Auftrag ziehen die Stichprobe des nächsten
  Moduls **einmal**, nicht zweimal.

Die beiden letzten brauchen zwei echte Sitzungen, also festgeschriebene Daten; sie legen
dafür einen kleinen, in sich stimmigen Bestand an (Aufträge, die zu Ende gelaufen sind).
"""

import threading
import time

from tests.runner import session
from tests.scenarios import World, free_stock


def _draft(article, numbers, steps):
    return {
        "lines": [{"article_object_id": article.object_id, "quantity": len(numbers),
                   "origin": "lager", "units": [{"number": n} for n in numbers]}],
        "steps": steps,
    }


def test_the_draft_reports_what_the_release_refuses():
    """**Ein Entwurf, den die Freigabe abweist, ist nicht «freigebbar».**

    Bug-Form (gegengeprüft): der Entwurf prüfte nur Zeilen und Grundbedingungen – eine
    Kette, die hinter einem Ausgang weitergeht, galt als freigebbar und scheiterte erst
    beim Klick.
    """
    import pytest
    from fastapi import HTTPException
    from app.services import orders as orders_svc, process as proc

    w = World(session())
    try:
        article, numbers = free_stock(w, quantity=1)
        draft = _draft(article, numbers, [World.dispose("scrap", "Ausschuss"), World.capture()])
        attempt = w.db.begin_nested()
        with pytest.raises(HTTPException) as refused:
            proc.release(w.db, lines=draft["lines"], steps=draft["steps"], actor_id=None)
        attempt.rollback()
        assert orders_svc.validate_draft(w.db, draft) == [refused.value.detail], (
            "Der Entwurf sagt etwas anderes als die Freigabe.")
    finally:
        w.db.rollback()
        w.db.close()


def test_the_log_refuses_every_change_and_every_delete():
    """**Der Ereignis-Log ist append-only – in der Datenbank, nicht als Absicht.**

    Bug-Form (gegengeprüft): ohne den Trigger liess sich ein Eintrag umschreiben oder
    löschen, und jede Ableitung daraus (Bild, Protokoll, Stückliste) wäre eine Behauptung.
    """
    import pytest
    from sqlalchemy import text

    w = World(session())
    try:
        order = w.produce(w.article(), 1)
        event_id = w.db.execute(text("SELECT id FROM process_events WHERE order_id=:o LIMIT 1"),
                                {"o": order.id}).scalar()
        for sql in ("UPDATE process_events SET status_after='verschrottet' WHERE id=:i",
                    "DELETE FROM process_events WHERE id=:i"):
            attempt = w.db.begin_nested()
            with pytest.raises(Exception) as err:  # noqa: PT011 - DBAPI-Fehlerklasse
                w.db.execute(text(sql), {"i": event_id})
            attempt.rollback()
            assert "Ereignis-Log" in str(err.value), f"Durchgelassen: {sql}"
    finally:
        w.db.rollback()
        w.db.close()


def _committed_stock(serialization="unit", quantity=1, template=None):
    db = session()
    w = World(db)
    article = w.article(serialization=serialization, template=template)
    numbers = w.stock(article, quantity)
    db.commit()
    return db, article, numbers


def _in_thread(fn):
    """``fn`` in einem eigenen Faden – zurück kommt, was es lieferte oder warf."""
    out: dict = {}

    def run():
        try:
            out["value"] = fn()
        except Exception as exc:                                   # noqa: BLE001
            out["error"] = exc
    thread = threading.Thread(target=run)
    thread.start()
    return thread, out


def test_two_releases_of_one_free_piece_one_wins_the_other_gets_a_sentence():
    """**Ein Stück, zwei gleichzeitige Freigaben** – die zweite wartet und erfährt warum.

    Bug-Form (gegengeprüft): ohne Sperre lasen beide «frei», die zweite lief in den
    partiellen Unique-Index und bekam eine ``IntegrityError`` – ein 500 ohne Satz.
    """
    from fastapi import HTTPException
    from app.services import process as proc

    setup, article, numbers = _committed_stock()
    draft = _draft(article, numbers, [World.capture()])
    setup.close()
    first, second = session(), session()
    try:
        proc.release(first, lines=draft["lines"], steps=draft["steps"], actor_id=None)
        first.flush()
        thread, out = _in_thread(lambda: proc.release(
            second, lines=draft["lines"], steps=draft["steps"], actor_id=None))
        time.sleep(1.0)                     # die zweite Freigabe läuft auf die Sperre
        first.commit()
        thread.join(timeout=30)
        assert not thread.is_alive(), "Die zweite Freigabe hängt."
        err = out.get("error")
        assert isinstance(err, HTTPException) and err.status_code == 409, (
            f"Die zweite Freigabe endet nicht mit einem 409: {out}")
        detail = err.detail if isinstance(err.detail, str) else err.detail["message"]
        assert numbers[0] in detail, f"Der Satz nennt das Stück nicht: {detail}"
    finally:
        second.rollback()
        second.close()
        first.close()


def test_two_confirms_on_one_order_draw_the_next_sample_once():
    """**Die Stichprobe wird einmal gezogen** – auch wenn zwei Menschen gleichzeitig scannen.

    Zwei Instanzen stehen vor dem ersten Modul, zwei Menschen bestätigen je eine. Beide
    erreichen damit das zweite Modul, und dort wird beim Erreichen gezogen.

    Bug-Form (gegengeprüft): ohne die Sperre am Auftrag sahen beide «noch nicht gezogen»
    und zogen beide – zwei Stichproben an einem Modul.
    """
    from app.models import ProcessEvent
    from app.models.process_event import KIND_SAMPLE
    from app.services import process as proc

    db = session()
    w = World(db)
    article = w.article(serialization="unit", template=[
        World.capture(), World.capture(sample={"percent": 50})])
    order = w.produce(article, 2)
    db.commit()
    order_id = order.id
    instances = w.instances(order)
    first_step = w.steps(order)[0]
    db.close()

    def confirm(s, instance):
        from app.models import Order
        from tests.support import per_unit
        mine = s.get(Order, order_id)
        payload = per_unit(s, order=mine, step=first_step, instance_object_id=instance,
                           values=World.GOOD)
        return proc.confirm_step(s, order=mine, step_id=first_step.id, values=payload,
                                 instance_object_id=instance, verification="scan",
                                 actor_id=None)

    a, b = session(), session()
    try:
        confirm(a, instances[0])
        a.flush()
        thread, out = _in_thread(lambda: confirm(b, instances[1]))
        time.sleep(1.0)
        a.commit()
        thread.join(timeout=30)
        assert not thread.is_alive(), "Die zweite Bestätigung hängt."
        assert "error" not in out, f"Die zweite Bestätigung scheiterte: {out}"
        b.commit()
        second_step = sorted({e.step_id for e in b.query(ProcessEvent).filter(
            ProcessEvent.order_id == order_id, ProcessEvent.kind == KIND_SAMPLE)})
        assert len(second_step) == 2, "Die Prämisse fehlt: am zweiten Modul wurde nicht gezogen."
        drawn = b.query(ProcessEvent).filter(
            ProcessEvent.order_id == order_id, ProcessEvent.kind == KIND_SAMPLE,
            ProcessEvent.step_id == second_step[1]).count()
        assert drawn == 1, f"Am zweiten Modul wurde {drawn}-mal gezogen statt einmal."
    finally:
        b.rollback()
        b.close()
        a.close()
