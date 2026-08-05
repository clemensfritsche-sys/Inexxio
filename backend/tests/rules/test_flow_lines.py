"""**Die Prozesslinie sagt, was passiert ist – nicht, was geplant war** (Testnotizen
#586/#589/#590).

Drei Befunde aus derselben Kette, und alle drei haben dieselbe Wurzel: eine Aussage über
den **Fortschritt der Achse** wurde als Aussage über **geflossenes Material** gelesen.

    Auftrag → Abweichung A → Abweichung B → Abweichung C (Rückführung gekappt)

C nimmt B sein einziges Stück und führt es zu Ende; B ist damit gegenstandslos und wird
abgebrochen. Im Eltern-Auftrag A stand danach trotzdem «1 Stk kam zurück» nach einem Modul,
das nie ausgeführt wurde – und eine **volle schwarze** Rückgabe-Linie, obwohl durch sie nie
etwas geflossen ist. In B selbst war das Bild korrekt: dieselbe Frage, zwei Antworten
(genau die Fehlerklasse aus #492).

Diese Datei prüft die **Wirkung** über die echten Dienst-Pfade – nicht die Schreibweise.
"""

from decimal import Decimal

from .conftest import _make_deviation, _make_order, _scrap


def _resp(db, order):
    from app.services.orders import to_order_response
    return to_order_response(db, order)


def _branch(resp, object_id):
    """Der Teaser EINES Abzweigs – egal, ob er am Auftrag oder an seinem Schritt hängt."""
    rows = list(resp.deviations) + [b for s in resp.steps for b in (s.sub_orders or [])]
    hit = [b for b in rows if b.object_id == object_id]
    assert hit, f"Abzweig {object_id} steht nicht im Fluss"
    return hit[0]


def _finish_inspection(db, order, inst, user, samples: int = 1):
    """Einen Auftrag über seine Datenerfassung zu Ende bringen – der echte Fachpfad."""
    from app.models import ArticleProcessStep
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc

    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == order.id,
                    ArticleProcessStep.step_type == "inspection").first())
    insp_svc.record_inspection(db, order, InspectionUpdate(
        samples=[InspectionSample(instance_id=inst.object_id, slot=n + 1,
                                  values={"_ok": True}) for n in range(samples)],
        step_id=step.id), user)
    db.commit()
    db.refresh(order)


def test_an_ended_branch_returns_what_it_gave_back_not_what_it_held(db, world):
    """**Läuft er noch → der Plan; ist er zu Ende → die Tatsache** (Testnotiz #590).

    Der abgebrochene Abzweig hat sein Stück **nach unten weitergereicht**, nicht nach oben
    zurückgegeben. Weitergeben ist nicht terminal – die alte Ableitung «Übernommenes minus
    endgültig Verlorenes» las es darum als Rückgabe und erfand eine Menge, die den Eltern
    nie wieder erreicht hat."""
    user, art = world
    top, inst = _make_order(db, art, user, 4)
    a = _make_deviation(db, top, inst, user, 3, steps=("inspection", "movement"))
    b = _make_deviation(db, a, inst, user, 1, steps=("movement",))
    c = _make_deviation(db, b, inst, user, 1, cut=True)          # kappt die Rückführung
    db.refresh(b)
    assert b.status == "inactive" and b.abort_into_id == c.object_id, (
        "Wer sein letztes Stück verliert und dessen Rückführung gekappt ist, endet hier.")

    # Beide Oberflächen sagen dasselbe – das ist der Kern des Befunds.
    teaser = _branch(_resp(db, a), b.object_id)
    assert teaser.flow_back == [], (
        "Was ein Abzweig weiterreicht, hat den Eltern nie erreicht – es darf nicht als "
        "Rückgabe erscheinen (#590).")
    assert teaser.returns_material is False, (
        "…und eine Rückgabe-Linie zeigt einen Weg, den es nicht gibt.")
    assert _resp(db, b).origin.returns_to_object_id is None, (
        "Die eigene Ansicht des Abzweigs sagt dasselbe – EINE Regel, zwei Oberflächen (#492).")


def test_a_branch_that_really_gives_back_still_says_so(db, world):
    """**Gegenprobe** – ohne sie wäre der Wächter von einem kaputten nicht zu unterscheiden.

    Ein Abzweig, der sein Stück zurückgibt, meldet die Rückgabe mit Menge; einer, der noch
    läuft, meldet sie noch nicht (das wäre eine Vorhersage), zeigt die Linie aber – geplant,
    nur eben dünn."""
    user, art = world
    top, inst = _make_order(db, art, user, 4)
    running = _make_deviation(db, top, inst, user, 1)
    teaser = _branch(_resp(db, top), running.object_id)
    assert teaser.returns_material is True and teaser.flow_back == [], (
        "Solange er läuft: die Linie ist geplant, geflossen ist noch nichts.")

    _finish_inspection(db, running, inst, user)
    assert running.status == "completed"
    teaser = _branch(_resp(db, top), running.object_id)
    assert teaser.returns_material is True, "Zurückgegeben heisst: die Linie führt zurück."
    assert sum(l.quantity for l in teaser.flow_back) == 1, (
        "…und sie trägt die Menge, die tatsächlich zurückgekommen ist.")


def test_the_line_is_strong_where_something_flowed(db, world):
    """**Erreicht ≠ geflossen** (Testnotizen #586/#589).

    Zweigt an einer Stelle ALLES ab, ist der Weg darunter erreicht – und trotzdem leer. Eine
    volle Linie behauptete dort, es sei etwas durchgegangen, und liess an der Einmündung
    einen schwarzen Stummel auf einer Haarlinie stehen."""
    user, art = world
    top, inst = _make_order(db, art, user, 4)
    # Der Auftrag verliert ALLES an eine Abweichung, deren Rückführung gekappt ist.
    _make_deviation(db, top, inst, user, 4, cut=True)
    db.refresh(top)

    resp = _resp(db, top)
    split = [n for n in resp.flow_nodes if n.kind == "split"]
    assert split, "Die Abweichung steht als Teilung im Fluss."
    assert resp.flow_edges[0].flowed is True, (
        "Über der Teilung ist das Material geflossen – dorthin führt eine volle Linie.")
    assert split[0].bypass is not None and split[0].bypass.flowed is False, (
        "Neben der Teilung liegt nichts – der Bypass ist ein Weg, den nichts genommen hat.")
    assert all(e.flowed is False for e in resp.flow_edges[1:]), (
        "Und darunter ebenso: erreicht, aber leer (#589).")
    assert all(e.flowed is (e.reached and bool(e.lots)) for e in resp.flow_edges), (
        "«Geflossen» ist genau «erreicht UND es lag etwas darauf» – eine Regel, eine Stelle.")


def test_a_regular_order_keeps_its_strong_line(db, world):
    """Und der Normalfall bleibt, wie er war: wo Material liegt, ist die Linie voll –
    sonst hätte die neue Regel den Fortschritt still unsichtbar gemacht."""
    user, art = world
    top, inst = _make_order(db, art, user, 4)
    dev = _make_deviation(db, top, inst, user, 1, steps=("scrap",))
    _scrap(db, dev, inst, user, 1)
    db.refresh(top)

    resp = _resp(db, top)
    assert resp.flow_edges[0].flowed is True, "Über der Teilung liegen 4 Stück."
    split = [n for n in resp.flow_nodes if n.kind == "split"][0]
    assert split.bypass is not None and split.bypass.flowed is True, (
        "Neben der Teilung bleiben 3 – dort ist etwas vorbeigekommen.")
    assert sum(l.quantity for l in split.bypass.lots) == Decimal(3)
