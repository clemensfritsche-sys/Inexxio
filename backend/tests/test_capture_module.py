"""**Die Datenerfassung: Stichprobe, Scan-Pflicht, und was ein «schlecht» auslöst.**

Drei Regeln, die keine Modulregeln sind, sondern **Prozessregeln** — sie stehen an der
einen Ausführungsstelle (``process.confirm_step``), und jedes künftige Modul erbt sie:

1. **Ein Vorgang ist eine Instanz.** Der Scan verifiziert das physische Ding, und das
   ist die Instanz — die Einzelinstanz hat bewusst keine Objektnummer. Charge = ein
   Scan, Einzelserialisierung = n Scans, ohne eine einzige Abfrage nach der
   Serialisierung.
2. **Erfasst wird die Stichprobe.** Gezogen bei der Ankunft, zufällig, eingefroren im
   Log. Der Rest läuft ohne Erfassung durch — sichtbar, nicht stillschweigend.
3. **«Nicht bestanden» rückt nicht vor.** Die Stücke bleiben stehen, bis ein Mensch
   entscheidet; das System legt nichts von selbst an.

Geprüft wird über die **echten** Dienstpfade gegen echtes PostgreSQL – nicht gegen
nachgestellte Zustände: die interessanten Fehler entstehen zwischen den Schritten.
"""

import os
import pathlib

import pytest

from tests.support import per_unit

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _db():
    """Eine Sitzung gegen echtes PostgreSQL – oder ein Skip **mit Grund**."""
    import sys
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    try:
        from app.core.database import Base, SessionLocal, engine
        import app.main as main
        Base.metadata.create_all(engine)
        main._ensure_columns()
        return SessionLocal()
    except Exception as exc:  # pragma: no cover - reine Umgebungsfrage
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regeln wirklich laufen.")


def _order(db, *, serialization: str, quantity: int, sample=None, points=None):
    """Ein freigegebener Auftrag mit **einem** Datenerfassungs-Modul."""
    from app.models import Article, ProcessStep
    from app.services import article_process as tpl, objects as obj, process as proc

    config = {
        "points": points or [{"label": "OK", "type": "bool"}],
        **({"sample": sample} if sample else {}),
    }
    art = Article(object_id=obj.next_object_id(db), name="Prüfstück", unit="stk",
                  serialization=serialization, status="released")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, [{"module_type": "datenerfassung", "config": config}])
    db.flush()
    order = proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=[], actor_id=None,
    )
    db.flush()
    step = db.query(ProcessStep).filter(ProcessStep.order_id == order.id).one()
    return order, step


# ---------------------------------------------------------------------------
# §3 – der Scan verifiziert die Instanz
# ---------------------------------------------------------------------------

def test_one_scan_per_instance_falls_out_of_the_numbering():
    """**Charge = ein Scan, Einzelserialisierung = n Scans** – ohne Fallunterscheidung.

    Das physische Etikett klebt am physischen Ding, und das Ding ist die **Instanz**.
    Eine Einzelinstanz zieht bewusst keine Objektnummer (``models/instance_unit``), es
    kann für sie also gar kein Etikett geben – die Regel ist damit nicht die elegantere
    Variante, sondern die einzig mögliche.

    Der Unterschied ergibt sich allein aus ``materialize.plan``: Charge 3 → (1, 3),
    Einzelserialisierung 3 → (3, 1).
    """
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=3)
        assert len(proc.step_work(db, order, step)) == 1, (
            "Eine Charge braucht mehr als einen Scan – das Etikett klebt an der Kiste."
        )
        order2, step2 = _order(db, serialization="unit", quantity=3)
        assert len(proc.step_work(db, order2, step2)) == 3, (
            "Einzelserialisierung: jedes Stück ist eine eigene Instanz, also ein eigener Scan."
        )
    finally:
        db.rollback()
        db.close()


def test_no_entry_without_verification():
    """**Ohne Bestätigung der Instanz passiert nichts** – serverseitig, nicht ausgegraut.

    Ein deaktivierter Knopf ist eine Bitte. Geprüft wird darum am Dienst, und zwar in
    beiden Formen: gar keine Angabe, und eine Instanz, die es nicht gibt.
    """
    from fastapi import HTTPException
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=2)

        with pytest.raises(HTTPException) as without:
            proc.confirm_step(db, order=order, step_id=step.id, values={"ok": True},
                              actor_id=None)
        assert without.value.status_code == 400

        with pytest.raises(HTTPException) as unknown:
            proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=999_999_999,
                            values={"ok": True}),
            instance_object_id=999_999_999, verification="scan", actor_id=None)
        assert unknown.value.status_code == 404

        # **Die Tastatur ist die Alternative, nicht die Umgehung** – und sie wird als
        # solche vermerkt.
        work = proc.step_work(db, order, step)[0]
        out = proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=work["instance_object_id"],
                            values={"ok": True}),
            instance_object_id=work["instance_object_id"], verification="manual", actor_id=None)
        assert out["moved"] == 2
        assert _verifications(db, order) == {"manual"}, (
            "Wie verifiziert wurde, steht nicht im Log – dann ist die Scan-Pflicht "
            "hinterher nicht nachweisbar."
        )
    finally:
        db.rollback()
        db.close()


def _verifications(db, order) -> set:
    from app.models import ProcessEvent
    from app.models.process_event import KIND_CAPTURE

    return {
        (e.payload or {}).get("verification")
        for e in db.query(ProcessEvent).filter(
            ProcessEvent.order_id == order.id, ProcessEvent.kind == KIND_CAPTURE).all()
    }


# ---------------------------------------------------------------------------
# §2 – die Stichprobe
# ---------------------------------------------------------------------------

def test_the_sample_is_drawn_once_and_frozen():
    """**Einmal gezogen, dann eingefroren** – und der Rest läuft ohne Erfassung durch.

    Der Wert einer Stichprobe liegt nicht im Algorithmus, sondern darin, dass hinterher
    dasteht, wer gezogen wurde. Darum steht sie im append-only Log und wird nicht bei
    jeder Ansicht neu gewürfelt – sonst wäre sie bei jedem Blick eine andere.
    """
    from app.services import process as proc, sampling

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=10,
                             sample={"percent": 30})
        work = proc.step_work(db, order, step)[0]
        assert (work["waiting"], work["sample"], work["rest"]) == (10, 3, 7), (
            "Die Stichprobe stimmt nicht – oder der ungeprüfte Rest ist unsichtbar."
        )

        # Zweimal fragen, dieselbe Antwort. Ein zweites Ziehen wäre eine zweite Wahrheit.
        units = [u for _, u in proc._units_at(db, order, step.id)]
        first = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
        sampling.ensure(db, order=order, step=step, actor_id=None)
        db.flush()
        again = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
        assert first == again and len(first) == 3, "Die Ziehung ist nicht eingefroren."

        # Erfasst wird NUR die Stichprobe; die übrigen laufen ohne Erfassung durch.
        out = proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=work["instance_object_id"],
                            values={"ok": True}),
            instance_object_id=work["instance_object_id"], verification="scan", actor_id=None)
        assert out["moved"] == 10, "Der ungeprüfte Rest bleibt stehen – er soll durchlaufen."
        assert _captures(db, order) == 3, (
            "Es wurde für mehr Stücke erfasst als gezogen wurden."
        )
    finally:
        db.rollback()
        db.close()


def test_the_sample_is_a_share_of_the_whole_not_of_each_instance():
    """**Die Bezugsgrösse ist die Gesamtmenge** – alles, was am Modul wartet.

    Vier Instanzen zu je einem Stück, Regel «die Hälfte»: gezogen werden **zwei**. Je
    Instanz gerechnet wären es vier (aus einem Stück muss mindestens eines gezogen
    werden), also die volle Menge – und «50 %» stünde am Bildschirm, während in
    Wirklichkeit alles geprüft wird.
    """
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="unit", quantity=4,
                             sample={"percent": 50})
        rows = proc.step_work(db, order, step)
        assert len(rows) == 4, "Vier Instanzen zu je einem Stück – ein Vorgang je Instanz."
        assert sum(r["sample"] for r in rows) == 2, (
            f"Gezogen wurde je Instanz statt über die Gesamtmenge: "
            f"{[r['sample'] for r in rows]}"
        )
        assert sum(r["rest"] for r in rows) == 2
    finally:
        db.rollback()
        db.close()


def test_a_later_module_draws_from_the_whole_order_not_from_the_first_wave():
    """**Gezogen wird über den Bestand des Auftrags, nicht über die erste Welle.**

    Die Stücke erreichen ein späteres Modul in Wellen – ein Vorgang ist eine Instanz.
    Zöge man je Welle, wäre «die Hälfte» in Wirklichkeit «die Hälfte aus jeder Kiste»:
    genau die Regel je Instanz, nur an anderer Stelle. Also zählt, was der Auftrag zu
    diesem Zeitpunkt noch hält – auch das, was noch am Modul davor steht.
    """
    from app.models import Article, ProcessEvent, ProcessStep
    from app.models.process_event import KIND_SAMPLE
    from app.services import article_process as tpl, objects as obj, process as proc

    db = _db()
    try:
        art = Article(object_id=obj.next_object_id(db), name="Prüfstück", unit="stk",
                      serialization="unit", status="released")
        db.add(art)
        db.flush()
        tpl.create_steps(db, art, [
            {"module_type": "datenerfassung",
             "config": {"points": [{"label": "OK", "type": "bool"}]}},
            {"module_type": "datenerfassung",
             "config": {"points": [{"label": "Zweite", "type": "bool"}],
                        "sample": {"percent": 50}}},
        ])
        db.flush()
        order = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": 4,
                    "origin": "neu", "units": []}],
            steps=[], actor_id=None,
        )
        db.flush()
        first, second = (db.query(ProcessStep)
                         .filter(ProcessStep.order_id == order.id)
                         .order_by(ProcessStep.position).all())

        # Genau EINE Instanz geht durch – am zweiten Modul steht damit ein Viertel.
        one = proc.step_work(db, order, first)[0]
        proc.confirm_step(
            db, order=order, step_id=first.id,
            values=per_unit(db, order=order, step=first,
                            instance_object_id=one["instance_object_id"]),
            instance_object_id=one["instance_object_id"],
            verification="scan", actor_id=None)
        db.flush()

        rows = proc.step_work(db, order, second)
        assert len(rows) == 1, "Nur die erste Instanz ist angekommen."
        assert sum(r["sample"] for r in rows) <= 2, (
            "Am zweiten Modul wurde über die erste Welle gezogen statt über den ganzen "
            "Auftrag – dann ist «die Hälfte» in Wahrheit «die Hälfte aus jeder Kiste»."
        )
        drawn = (db.query(ProcessEvent)
                 .filter(ProcessEvent.order_id == order.id,
                         ProcessEvent.step_id == second.id,
                         ProcessEvent.kind == KIND_SAMPLE).count())
        assert drawn == 2, (
            f"Die Ziehung am zweiten Modul umfasst {drawn} Stück – erwartet sind 2 "
            f"(die Hälfte der vier, die der Auftrag hält)."
        )
    finally:
        db.rollback()
        db.close()


def test_the_sample_is_never_empty_and_never_larger_than_the_lot():
    """Aufgerundet, mindestens eines, höchstens alle — die Regel als Zahl.

    «0 von 5» ist keine Prüfung, sondern ihr Ausfall; «12 von 5» ist keine Menge.
    """
    from app.domain import sampling as rule

    assert rule.size({"percent": 100}, 7) == 7
    assert rule.size(None, 7) == 7                     # ohne Angabe: alle
    assert rule.size({"percent": 10}, 5) == 1          # 0.5 → 1, aufgerundet
    assert rule.size({"percent": 10}, 6000) == 600     # dieselbe Regel bei 6000
    assert rule.size({"percent": 50}, 3) == 2          # 1.5 → 2
    assert rule.size({"percent": 25}, 3) == 1          # 0.75 → 1
    assert rule.size({"percent": 10}, 0) == 0          # nichts da, nichts gezogen
    # **Altbestand wird gelesen, nicht geschrieben**: eine Definition aus der Zeit der
    # Regel «je Instanz» meint jetzt dieselbe Zahl über die Gesamtmenge.
    assert rule.size({"mode": "count", "value": 12}, 5) == 5
    assert rule.size({"mode": "percent", "value": 10}, 5) == 1
    assert rule.size({"mode": "all", "value": None}, 7) == 7


def _captures(db, order) -> int:
    from app.models import Capture

    return db.query(Capture).filter(Capture.order_id == order.id).count()


# ---------------------------------------------------------------------------
# §4 – «nicht bestanden» hält an
# ---------------------------------------------------------------------------

def test_a_failed_capture_holds_and_nothing_is_created():
    """**Erfasst, nicht bestanden, nichts vorgerückt** – und das System legt nichts an.

    Drei Dinge müssen gleichzeitig gelten: die Feststellung ist geloggt (sonst wäre sie
    verloren), die Stücke stehen still (sonst laufen sie stillschweigend weiter), und es
    entsteht **kein** Folgeauftrag (den bestellt ein Mensch, nicht das System).
    """
    from app.models import Order
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=4,
                             sample={"percent": 25})
        before = db.query(Order).count()
        work = proc.step_work(db, order, step)[0]

        out = proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=work["instance_object_id"],
                            values={"ok": False}),
            instance_object_id=work["instance_object_id"], verification="scan", actor_id=None)
        db.flush()

        assert out == {"moved": 0, "held": 4, "result": "failed"}
        assert db.query(Order).count() == before, (
            "Das System hat einen Auftrag angelegt – die Entscheidung trifft ein Mensch."
        )
        # Die Feststellung steht im Log, obwohl sich nichts bewegt hat.
        assert _captures(db, order) == 1

        after = proc.step_work(db, order, step)[0]
        assert after["held"] is True and after["waiting"] == 4, (
            "Nach dem Durchfaller steht nicht mehr die ganze Instanz still."
        )
        assert len(after["failed_numbers"]) == 1
        # Und der ungeprüfte Rest ist der «Rest» für die 100 %-Kontrolle (§4.1) –
        # **nur** die Stücke dieses Auftrags an diesem Modul.
        assert after["rest"] == 3
        rest = proc.held_numbers(db, order, step,
                                 instance_object_id=work["instance_object_id"], group="rest")
        failed = proc.held_numbers(db, order, step,
                                   instance_object_id=work["instance_object_id"], group="failed")
        assert len(rest) == 3 and len(failed) == 1
        assert not set(rest) & set(failed), "Rest und Durchfaller überschneiden sich."
    finally:
        db.rollback()
        db.close()


def test_the_flow_splits_between_instances():
    """**Gute laufen weiter, schlechte warten** – die Teilung geht entlang der Instanzen.

    Sie kann gar nicht feiner sein: ein Wertesatz gilt für einen Vorgang, und ein Vorgang
    ist eine Instanz. Bei Einzelserialisierung ist das jedes Stück einzeln – also genau
    die Granularität, die die Qualitätssicherung braucht.
    """
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="unit", quantity=2)
        work = proc.step_work(db, order, step)
        assert len(work) == 2

        good = proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=work[0]["instance_object_id"],
                            values={"ok": True}),
            instance_object_id=work[0]["instance_object_id"], verification="scan", actor_id=None)
        bad = proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=work[1]["instance_object_id"],
                            values={"ok": False}),
            instance_object_id=work[1]["instance_object_id"], verification="scan", actor_id=None)
        db.flush()

        assert good["moved"] == 1 and bad["held"] == 1
        left = proc.step_work(db, order, step)
        assert [w["instance_object_id"] for w in left] == [work[1]["instance_object_id"]], (
            "Am Modul steht nicht mehr genau die durchgefallene Instanz."
        )
        assert left[0]["held"] is True
    finally:
        db.rollback()
        db.close()


def test_a_later_good_capture_clears_the_hold():
    """Der Hold hängt an der **letzten** Erfassung, nicht an irgendeiner.

    Sonst wäre er eine Sackgasse: ein einmal durchgefallenes Stück käme auch nach
    geklärter Abweichung und erneuter Erfassung nie mehr weiter.
    """
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=2)
        work = proc.step_work(db, order, step)[0]
        instance = work["instance_object_id"]

        proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=instance,
                            values={"ok": False}),
            instance_object_id=instance, verification="scan", actor_id=None)
        db.flush()
        assert proc.step_work(db, order, step)[0]["held"] is True

        out = proc.confirm_step(
            db, order=order, step_id=step.id,
            values=per_unit(db, order=order, step=step, instance_object_id=instance,
                            values={"ok": True}),
            instance_object_id=instance, verification="scan", actor_id=None)
        db.flush()
        assert out["moved"] == 2, "Die erneute, bestandene Erfassung bewegt nichts."
        assert proc.step_work(db, order, step) == [], "Am Modul steht noch etwas."
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# Die Aussenkante – die Regeln müssen auch über HTTP gelten
# ---------------------------------------------------------------------------

def test_the_endpoints_carry_the_rules_to_the_outside():
    """**Was der Dienst verlangt, verlangt auch der Endpunkt.**

    Die Regeln stehen in ``process``; hier wird die Verdrahtung geprüft – dass die
    Bestätigung Instanz und Art wirklich weiterreicht, dass die Ablehnung als saubere
    400 herauskommt und dass die Nummern-Gruppen ihre Auskunft geben. Genau hier fällt
    ein falscher Query-Name oder ein vergessenes Feld auf, und **nur** hier: die
    Dienst-Tests rufen die Funktion direkt.
    """
    db = _db()
    from fastapi.testclient import TestClient
    from app.core.auth import get_current_user
    from app.main import app
    from app.models import UserProfile
    from app.services import objects as obj, process as proc

    order, step = _order(db, serialization="batch", quantity=10,
                         sample={"percent": 30})
    # **Wiederverwendbar, nicht neu angelegt.** Der Test muss committen (der TestClient
    # öffnet seine eigene Sitzung und sähe sonst nichts) – ein zweiter Lauf kollidierte
    # sonst mit der eindeutigen E-Mail.
    staff = db.query(UserProfile).filter(UserProfile.firebase_uid == "probe").first()
    if staff is None:
        staff = UserProfile(object_id=obj.next_object_id(db), firebase_uid="probe",
                            email="probe@example.com", role="employee")
        db.add(staff)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: staff
    try:
        client = TestClient(app)
        base = f"/api/v1/erp/orders/{order.object_id}/steps/{step.id}"
        work = proc.step_work(db, order, step)
        instance = work[0]["instance_object_id"]

        # **Ohne Bestätigung keine Eingabe** – und zwar als Fehler, nicht als leerer Erfolg.
        refused = client.post(f"{base}/confirm", json={"values": {}})
        assert refused.status_code == 400, refused.text
        assert "bestätigt" in refused.json()["detail"], refused.json()

        # Die Arbeitsliste reist mit der Antwort – sie IST die Liste der zu scannenden Dinge.
        detail = client.get(f"/api/v1/erp/orders/{order.object_id}").json()
        row = next(s for s in detail["steps"] if s["id"] == step.id)
        assert row["sample"] == "30 % der Gesamtmenge", row["sample"]
        assert [w["instance_object_id"] for w in row["work"]] == [instance]
        assert (row["work"][0]["sample"], row["work"][0]["rest"]) == (3, 7)

        # **Welche Stücke sind zu erfassen?** – erst auf Klick, dieselbe Gruppe, die der
        # Server danach verlangt. Genau drei, wie die Vorschau eine Zeile höher sagt.
        drawn = client.get(f"{base}/hold", params={"instance": instance, "group": "sample"})
        assert drawn.status_code == 200, drawn.text
        numbers = drawn.json()["numbers"]
        assert len(numbers) == 3, numbers

        # **Ein Scan, drei Erfassungen.** Ein flacher Wertesatz wird abgewiesen: er wäre
        # eine Messung, aus der drei würden.
        flat = client.post(f"{base}/confirm", json={
            "values": {"ok": False}, "instance_object_id": instance,
            "verification": "manual",
        })
        assert flat.status_code == 422, flat.text

        luecke = client.post(f"{base}/confirm", json={
            "values": {numbers[0]: {"ok": False}}, "instance_object_id": instance,
            "verification": "manual",
        })
        assert luecke.status_code == 400, luecke.text
        assert "je Stück" in luecke.json()["detail"], luecke.json()

        ok = client.post(f"{base}/confirm", json={
            "values": {n: {"ok": False} for n in numbers},
            "instance_object_id": instance, "verification": "manual",
        })
        assert ok.status_code == 200, ok.text

        after = client.get(f"/api/v1/erp/orders/{order.object_id}").json()
        row = next(s for s in after["steps"] if s["id"] == step.id)
        assert row["work"][0]["held"] is True, "Ein «nicht bestanden» rückt vor."
        assert len(row["work"][0]["failed_numbers"]) == 3

        # Die Vorauswahl der Entscheidung – zwei Gruppen, beide erst auf Klick.
        failed = client.get(f"{base}/hold", params={"instance": instance, "group": "failed"})
        rest = client.get(f"{base}/hold", params={"instance": instance, "group": "rest"})
        assert len(failed.json()["numbers"]) == 3, failed.text
        assert len(rest.json()["numbers"]) == 7, rest.text
        assert not set(failed.json()["numbers"]) & set(rest.json()["numbers"]), (
            "Ein Stück steht in beiden Gruppen – die Vorauswahl wäre doppelt."
        )
        assert client.get(f"{base}/hold",
                          params={"instance": instance, "group": "alles"}).status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        db.close()


# ---------------------------------------------------------------------------
# §3 + §9.3 – der Scan gehört der Instanz, die Erfassung der Einzelinstanz
# ---------------------------------------------------------------------------

def test_one_scan_gives_one_capture_per_piece_not_one_per_scan():
    """►►► **Der Scan verifiziert die Instanz. Die Erfassung gilt der Einzelinstanz.** ◄◄◄

    Zwei verschiedene Dinge, und sie dürfen nie gekoppelt sein. Vorher hingen sie
    aneinander: **ein** Wertesatz je Bestätigung, kopiert auf jedes gezogene Stück. Bei
    einer Charge über zwei Stück entstanden damit zwei Messwerte, gemessen wurde einer –
    ein Nachweis mit mehr Zeilen als Messungen.

    Geprüft wird die Zahl **und** der Inhalt: dass die Werte je Stück verschieden sein
    können, ist der ganze Punkt. Wären sie gleich, wäre die Kopie nicht auffällig.
    """
    from app.services import process as proc
    from app.models import Capture

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=2,
                             points=[{"label": "Mass", "type": "measure",
                                      "target": 10, "tolerance": 5}])
        work = proc.step_work(db, order, step)
        assert len(work) == 1, "Eine Charge ist EIN Scan."
        inst = work[0]["instance_object_id"]
        assert work[0]["sample"] == 2, "Bei «alle» sind beide Stücke zu erfassen."

        numbers = proc.held_numbers(db, order, step, instance_object_id=inst,
                                    group="sample")
        assert len(numbers) == 2, numbers

        out = proc.confirm_step(
            db, order=order, step_id=step.id,
            values={numbers[0]: {"mass": 9}, numbers[1]: {"mass": 11}},
            instance_object_id=inst, verification="scan", actor_id=None)
        assert out["moved"] == 2

        rows = db.query(Capture).filter(Capture.order_id == order.id).all()
        assert len(rows) == 2, "Ein Scan, zwei Stücke – also zwei Erfassungen."
        assert sorted(r.values["mass"] for r in rows) == [9, 11], (
            "Die Werte sind gleich – dann wurde einer kopiert statt zweimal gemessen."
        )
    finally:
        db.rollback()
        db.close()


def test_the_capture_count_follows_the_draw_not_the_number_of_scans():
    """**1 Scan → 1500 Erfassungen**: die Zahl kommt aus der Ziehung, nicht aus dem Scan.

    Das ist die Skalen-Aussage der Regel. Hier klein gemessen (¼ von 8 = 2), aber es ist
    dieselbe Rechnung: die Erfassungsanzahl darf nirgends aus der Zahl der Scans folgen,
    sonst hätte eine Charge immer genau eine – unabhängig davon, wie viel gezogen wurde.
    """
    from app.services import process as proc
    from app.models import Capture

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=8,
                             sample={"percent": 25})
        work = proc.step_work(db, order, step)[0]
        inst = work["instance_object_id"]
        assert (work["waiting"], work["sample"]) == (8, 2), work

        numbers = proc.held_numbers(db, order, step, instance_object_id=inst,
                                    group="sample")
        assert len(numbers) == work["sample"], (
            "Die Vorschau nennt eine andere Zahl als die Liste – zwei Quellen."
        )
        proc.confirm_step(
            db, order=order, step_id=step.id,
            values={n: {"ok": True} for n in numbers},
            instance_object_id=inst, verification="scan", actor_id=None)

        assert db.query(Capture).filter(Capture.order_id == order.id).count() == 2, (
            "Erfasst wurde nicht je gezogener Einzelinstanz."
        )
    finally:
        db.rollback()
        db.close()


def test_a_capture_covers_exactly_the_drawn_pieces():
    """**Zu viel und zu wenig sind beide ein Fehler** – und beide mit einem Satz.

    Ein Satz für ein nicht gezogenes Stück wäre ein Nachweis über etwas, das hier nie
    geprüft werden sollte; ein fehlender wäre eine Lücke, die hinterher aussieht wie
    «durchgelaufen, nichts gemessen».
    """
    from fastapi import HTTPException
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=4,
                             sample={"percent": 50})
        work = proc.step_work(db, order, step)[0]
        inst = work["instance_object_id"]
        drawn = proc.held_numbers(db, order, step, instance_object_id=inst, group="sample")
        rest = proc.held_numbers(db, order, step, instance_object_id=inst, group="rest")
        assert len(drawn) == 2 and len(rest) == 2

        with pytest.raises(HTTPException) as zu_wenig:
            proc.confirm_step(db, order=order, step_id=step.id,
                              values={drawn[0]: {"ok": True}},
                              instance_object_id=inst, verification="scan", actor_id=None)
        assert zu_wenig.value.status_code == 400
        assert "je Stück" in str(zu_wenig.value.detail)

        with pytest.raises(HTTPException) as zu_viel:
            proc.confirm_step(
                db, order=order, step_id=step.id,
                values={**{n: {"ok": True} for n in drawn}, rest[0]: {"ok": True}},
                instance_object_id=inst, verification="scan", actor_id=None)
        assert zu_viel.value.status_code == 400
        assert "nicht gezogen" in str(zu_viel.value.detail)
    finally:
        db.rollback()
        db.close()


def test_one_bad_piece_holds_the_whole_instance():
    """**Das Urteil hängt am Stück, der Halt an der Instanz** (§4.1).

    Jede Zeile trägt ihr eigenes Ergebnis – das ist die Genauigkeit, die aus der
    Erfassung je Stück folgt. Was daraus für den Prozess folgt, bleibt unverändert: eine
    durchgefallene Stichprobe ist nicht mehr repräsentativ, also bleibt die **ganze**
    Instanz stehen, auch ihr ungeprüfter Rest.
    """
    from app.services import process as proc
    from app.models import Capture

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=3)
        work = proc.step_work(db, order, step)[0]
        inst = work["instance_object_id"]
        numbers = proc.held_numbers(db, order, step, instance_object_id=inst,
                                    group="sample")

        out = proc.confirm_step(
            db, order=order, step_id=step.id,
            values={numbers[0]: {"ok": True}, numbers[1]: {"ok": False},
                    numbers[2]: {"ok": True}},
            instance_object_id=inst, verification="scan", actor_id=None)
        assert out["result"] == "failed" and out["moved"] == 0, out

        rows = {r.instance_unit_id: r.result
                for r in db.query(Capture).filter(Capture.order_id == order.id).all()}
        assert sorted(rows.values()) == ["failed", "passed", "passed"], (
            "Das Urteil wurde über alle Stücke gleichgezogen – dann ist es keines je Stück."
        )
    finally:
        db.rollback()
        db.close()


def test_a_hold_is_never_a_dead_end():
    """►►► **Ein Halt hat immer einen Ausgang – und der ist erreichbar.** ◄◄◄

    Der gemeldete Fall, Schritt für Schritt: ein Stück fällt durch, der Mensch legt die
    angebotene Abweichung an, lässt sie durchlaufen, das Stück kommt zurück – und der
    Prozess muss weitergehen können.

    Genau das ging nicht. Nicht weil der Dienst es verhindert hätte (er hat es nie
    getan), sondern weil die **Oberfläche** bei einem Halt ausschliesslich die
    Entscheidung anbot und nie die Erfassung. Die erfundene Sperre hatte keinen
    Schlüssel: jeder Anlauf legte die nächste Abweichung an, im Bild eine Teilung mehr,
    im Prozess kein Schritt.

    Geprüft wird darum der **ganze Weg**, nicht die Meldung: nach der Rückkehr muss eine
    erneute Erfassung möglich sein und die Stücke vorrücken lassen.
    """
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=2)
        inst = proc.step_work(db, order, step)[0]["instance_object_id"]
        drawn = proc.held_numbers(db, order, step, instance_object_id=inst, group="sample")

        # 1. Einer fällt durch – nichts rückt vor, die ganze Instanz steht.
        out = proc.confirm_step(
            db, order=order, step_id=step.id,
            values={drawn[0]: {"ok": False}, drawn[1]: {"ok": True}},
            instance_object_id=inst, verification="scan", actor_id=None)
        db.flush()
        assert out["moved"] == 0 and out["result"] == "failed"
        assert proc.step_work(db, order, step)[0]["held"] is True

        # 2. Die angebotene Abweichung – ein ganz gewöhnlicher Auftrag.
        failed = proc.held_numbers(db, order, step, instance_object_id=inst, group="failed")
        assert failed == [drawn[0]]
        dev = proc.release(
            db,
            lines=[{"article_object_id": _article_of(db, order), "quantity": 1,
                    "origin": "lager",
                    "units": [{"number": failed[0], "from_order": order.object_id}],
                    "returns": True}],
            steps=[{"module_type": "datenerfassung",
                    "config": {"points": [{"label": "OK", "type": "bool"}]}}],
            actor_id=None)
        db.flush()
        assert proc.deviation_flags(db, [dev.id])[dev.id] is True, (
            "Der Folgeauftrag greift ein Stück, das nicht regulär verfügbar war – "
            "er ist eine Abweichung und muss es auch heissen."
        )

        # 3. Die Abweichung läuft durch, das Stück kommt zurück.
        d_step = proc.steps_of(db, dev)[0]
        d_inst = proc.step_work(db, dev, d_step)[0]["instance_object_id"]
        d_drawn = proc.held_numbers(db, dev, d_step, instance_object_id=d_inst,
                                    group="sample")
        proc.confirm_step(db, order=dev, step_id=d_step.id,
                          values={n: {"ok": True} for n in d_drawn},
                          instance_object_id=d_inst, verification="scan", actor_id=None)
        db.flush()
        work = proc.step_work(db, order, step)[0]
        assert work["waiting"] == 2, "Das Stück ist nicht zurückgekommen."

        # 4. ►► Und jetzt muss es weitergehen. ◄◄
        again = proc.held_numbers(db, order, step, instance_object_id=inst, group="sample")
        moved = proc.confirm_step(
            db, order=order, step_id=step.id,
            values={n: {"ok": True} for n in again},
            instance_object_id=inst, verification="scan", actor_id=None)
        db.flush()
        assert moved["moved"] == 2, (
            f"Der Prozess kommt nicht weiter – das ist die Sackgasse: {moved}"
        )
        assert proc.step_work(db, order, step) == [], "Am Modul steht immer noch etwas."
        assert proc.order_status(db, order) == "abgeschlossen"
    finally:
        db.rollback()
        db.close()


def _article_of(db, order) -> int:
    from app.models import Article, Instance, InstanceUnit, OrderUnit

    row = db.query(OrderUnit).filter(OrderUnit.order_id == order.id).first()
    unit = db.get(InstanceUnit, row.instance_unit_id)
    inst = db.get(Instance, unit.instance_id)
    return db.get(Article, inst.article_id).object_id


def test_the_verdict_in_the_log_belongs_to_its_own_piece():
    """Jede Log-Zeile trägt **ihr** Urteil, nicht das der Instanz.

    Der Eintrag stand einmal mit dem zusammengefassten Ergebnis da: fiel ein Stück durch,
    trugen **alle** Zeilen «failed» – auch die der guten. Ein Nachweis, der die Guten
    mitverurteilt, ist keiner.
    """
    from app.models import ProcessEvent
    from app.models.process_event import KIND_CAPTURE
    from app.services import process as proc

    db = _db()
    try:
        order, step = _order(db, serialization="batch", quantity=2)
        inst = proc.step_work(db, order, step)[0]["instance_object_id"]
        drawn = proc.held_numbers(db, order, step, instance_object_id=inst, group="sample")
        proc.confirm_step(db, order=order, step_id=step.id,
                          values={drawn[0]: {"ok": False}, drawn[1]: {"ok": True}},
                          instance_object_id=inst, verification="scan", actor_id=None)
        db.flush()

        results = sorted(
            (e.payload or {}).get("result")
            for e in db.query(ProcessEvent).filter(
                ProcessEvent.order_id == order.id,
                ProcessEvent.kind == KIND_CAPTURE).all()
        )
        assert results == ["failed", "passed"], (
            f"Der Log verurteilt die Guten mit: {results}"
        )
    finally:
        db.rollback()
        db.close()
