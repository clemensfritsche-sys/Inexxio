"""**Aussondern: verschrotten oder sperren — ein Modul, zwei Ausprägungen.**

Vier Regeln, und keine davon ist eine Modulregel: sie stehen im Prozess-Framework, und
jedes künftige terminale Modul erbt sie.

1. **Zwei Zustände, eine Eigenschaft.** «Gibt es einen Weg zurück?» steht am Status
   (``selectable``), nicht als Liste in der Freigabe – und die Farbe folgt daraus.
2. **Ein terminales Modul ist ein Ausgang.** Das Stück verlässt den Auftrag dort; hinter
   ihm kann kein Modul mehr stehen, und das Ende-Objekt passiert es nie.
3. **Damit endet auch eine geplante Rückführung** – ohne eine Zeile Wartelogik: gezählt
   wird über die **offene** Zugehörigkeit, und die gibt es nicht mehr.
4. **Der Grund ist Pflicht beim Sperren**, nicht beim Verschrotten.

Geprüft über die **echten** Dienstpfade gegen echtes PostgreSQL.
"""

import os
import pathlib

import pytest

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


def _capture_step():
    return {"module_type": "datenerfassung",
            "config": {"points": [{"label": "OK", "type": "bool"}]}}


def _disposal_step(mode: str):
    return {"module_type": "aussondern", "config": {"mode": mode}}


def _article(db, *, steps: list[dict], serialization: str = "batch"):
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name="Prüfstück", unit="stk",
                  serialization=serialization, status="released")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, steps)
    db.flush()
    return art


def _make(db, *, quantity: int, steps: list[dict]):
    """Ein freigegebener Erzeugungsauftrag mit genau diesem Ablauf."""
    from app.models import ProcessStep
    from app.services import process as proc
    art = _article(db, steps=steps)
    order = proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=[], actor_id=None,
    )
    db.flush()
    rows = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position).all())
    return art, order, rows


def _confirm(db, order, step, values=None):
    """Bestätigen – je wartender Instanz einmal, wie die Scan-Regel es verlangt."""
    from app.services import process as proc
    out = []
    for row in proc.step_work(db, order, step):
        out.append(proc.confirm_step(
            db, order=order, step_id=step.id, values=values or {}, actor_id=None,
            instance_object_id=row["instance_object_id"], verification="scan",
        ))
    db.flush()
    return out


# ---------------------------------------------------------------------------
# §2.3 – zwei Zustände, und der Weg zurück ist eine EIGENSCHAFT
# ---------------------------------------------------------------------------

def test_two_states_and_the_way_back_is_a_property_not_a_colour():
    """**Die Farbe folgt der Frage «gibt es einen Weg zurück?», nicht umgekehrt.**

    Beide Zustände sind erreichbar, beide bleiben Datensätze. Der Unterschied steht an
    **einer** Eigenschaft: ``selectable``. Daraus folgt die Farbe (rot ↔ gelb), daraus
    folgt die Bestands-Zugehörigkeit, und daraus folgt, was die Freigabe erlaubt – nicht
    aus drei Listen, die jemand nachzieht.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    assert st.VERSCHROTTET in st.UNIT_STATUSES and st.GESPERRT in st.UNIT_STATUSES

    # Endgültig: rot, nicht wählbar, zählt zur Historie.
    assert not st.is_selectable(st.VERSCHROTTET)
    assert st.stock_kind(st.VERSCHROTTET) == st.HISTORY
    assert st.STATUS_LABELS[st.VERSCHROTTET] == "Verschrottet"

    # Aufhebbar: gelb, wählbar – und es liegt weiterhin im Regal, zählt also zum Bestand.
    assert st.is_selectable(st.GESPERRT)
    assert st.stock_kind(st.GESPERRT) == st.LIVE, (
        "Ein gesperrtes Stück ist physisch da – es aus dem Bestand zu nehmen hiesse, "
        "ihn kleiner zu melden, als er ist."
    )

    tones = {s.value: s.tone for s in st.CATALOG}
    assert tones[st.VERSCHROTTET] == "danger" and tones[st.GESPERRT] == "pending"

    # Und die Wählbarkeit ist EINE Ableitung, keine zweite Liste.
    assert st.VERSCHROTTET not in st.SELECTABLE_UNIT_STATUSES
    assert {st.FREIGEGEBEN, st.IM_PROZESS, st.GESPERRT} <= set(st.SELECTABLE_UNIT_STATUSES)


def test_a_blocked_piece_comes_back_through_an_ordinary_order():
    """**Das Greifen IST das Aufheben** – kein zweiter Mechanismus (§2.3).

    Ein gesperrtes Stück wird von einem ganz gewöhnlichen Auftrag aufgenommen; das
    Start-Objekt setzt es auf «Im Prozess» wie jedes andere. Ein verschrottetes wird
    abgewiesen – es gibt das Ding nicht mehr.
    """
    from fastapi import HTTPException
    from app.domain import statuses as st
    from app.services import process as proc

    db = _db()
    try:
        for mode, expected in (("block", st.GESPERRT), ("scrap", st.VERSCHROTTET)):
            art, order, rows = _make(db, quantity=2, steps=[_disposal_step(mode)])
            _confirm(db, order, rows[0],
                     values={"grund_der_sperre": "Lack blättert"} if mode == "block" else {})
            from app.models import InstanceUnit, OrderUnit
            pieces = (db.query(InstanceUnit)
                      .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
                      .filter(OrderUnit.order_id == order.id).all())
            assert {u.status for u in pieces} == {expected}, [u.status for u in pieces]
            picked = sorted(proc.unit_numbers(db, pieces).values())[:1]

            take = dict(
                lines=[{"article_object_id": art.object_id, "quantity": 1,
                        "origin": "lager",
                        "units": [{"number": picked[0], "from_order": None}]}],
                steps=[_capture_step()], actor_id=None,
            )
            if mode == "block":
                back = proc.release(db, **take)
                db.flush()
                again = db.query(InstanceUnit).filter(
                    InstanceUnit.id == pieces[0].id).one()
                assert again.status == st.IM_PROZESS, (
                    "Ein gesperrtes Stück muss ein gewöhnlicher Auftrag greifen können – "
                    "das ist das Aufheben der Sperre."
                )
                assert back is not None
            else:
                with pytest.raises(HTTPException) as e:
                    proc.release(db, **take)
                assert e.value.status_code == 409
                assert "Verschrottet" in str(e.value.detail)
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# §3 – ein terminales Modul ist ein AUSGANG
# ---------------------------------------------------------------------------

def test_nothing_can_stand_behind_a_terminal_module():
    """**Hinter einem Ausgang steht nichts** – gemeldet bei der Freigabe, nicht zur Laufzeit.

    Ein Modul hinter dem Aussondern bekäme nie eine Einzelinstanz: was ankommt, verlässt
    den Auftrag. Eine tote Definition durchzulassen wäre schlimmer als ein Fehler, denn
    sie sieht aus wie ein Prozess.
    """
    from fastapi import HTTPException
    from app.services import process as proc

    db = _db()
    try:
        # Erlaubt: das Aussondern als letztes Modul – die Kette endet dort.
        _make(db, quantity=1, steps=[_capture_step(), _disposal_step("scrap")])

        with pytest.raises(HTTPException) as e:
            _article(db, steps=[_disposal_step("scrap"), _capture_step()])
        assert "kein Modul mehr stehen" in str(e.value.detail), e.value.detail
    finally:
        db.rollback()
        db.close()


def test_disposal_ends_the_journey_and_the_parent_stops_waiting():
    """**Aussondern schneidet eine geplante Rückführung ab – ohne eigene Wartelogik** (§3).

    Der Abweichungsauftrag nimmt beide Stücke *mit* Rückführung. Sondert er sie aus,
    kehren sie nicht zurück: die Zugehörigkeit ist geschlossen, und der Quell-Auftrag
    zählt seine Ausleihen über die **offene** Zeile. Er wartet nicht mehr, sein Modul ist
    nicht mehr gesperrt – genau wie bei einer gekappten Rückführung, nur ausgelöst durch
    die Aussonderung statt bei der Definition.

    ``return_to_order_id`` bleibt dabei **unangetastet**: die Absicht war da, sie ist
    Historie. Sie nachträglich zu löschen hiesse, die Vergangenheit umzuschreiben.
    """
    from app.domain import statuses as st
    from app.models import OrderUnit, ProcessStep
    from app.services import process as proc

    db = _db()
    try:
        art, parent, p_steps = _make(db, quantity=2, steps=[_capture_step(), _capture_step()])
        from app.models import InstanceUnit
        pieces = (db.query(InstanceUnit)
                  .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
                  .filter(OrderUnit.order_id == parent.id).all())
        numbers = sorted(proc.unit_numbers(db, pieces).values())

        dev = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": 2, "origin": "lager",
                    "returns": True,
                    "units": [{"number": n, "from_order": parent.object_id}
                              for n in numbers]}],
            steps=[_disposal_step("scrap")], actor_id=None,
        )
        db.flush()
        assert proc.waiting_counts(db, [parent.id]).get(parent.id) == 2
        assert proc.pending_returns(db, parent), "Vorher muss das Modul gesperrt sein."

        d_step = db.query(ProcessStep).filter(ProcessStep.order_id == dev.id).one()
        moved = _confirm(db, dev, d_step)
        assert sum(m["moved"] for m in moved) == 2

        # Die Reise endet hier: kein Zustandspunkt mehr, Zugehörigkeit geschlossen.
        rows = db.query(OrderUnit).filter(OrderUnit.order_id == dev.id).all()
        assert all(m.released_at is not None and m.current_step_id is None for m in rows)
        assert {u.status for u in pieces} == {st.VERSCHROTTET}

        # …und der Eltern wartet nicht mehr – ohne dass jemand etwas gekappt hätte.
        assert proc.waiting_counts(db, [parent.id]).get(parent.id, 0) == 0
        assert proc.pending_returns(db, parent) == {}
        parent_rows = db.query(OrderUnit).filter(OrderUnit.order_id == parent.id).all()
        assert all(m.return_to_order_id is None for m in parent_rows)
        dev_rows = db.query(OrderUnit).filter(OrderUnit.order_id == dev.id).all()
        assert all(m.return_to_order_id == parent.id for m in dev_rows), (
            "Die Absicht «kehrt zurück» ist Historie und wird nicht nachträglich gelöscht."
        )

        # §4: der Aussonderungs-Auftrag hat getan, wozu er da war; der Eltern hat nichts
        # mehr, mit dem er sein Ziel erreichen könnte.
        assert proc.order_status(db, dev) == st.ABGESCHLOSSEN
        assert proc.order_status(db, parent) == st.ABGEBROCHEN
    finally:
        db.rollback()
        db.close()


def test_the_order_status_needs_no_new_value():
    """**§4 – die bestehende Regel trägt beide Fälle des Auftrags.**

    «9 ausgesondert, 1 im Ziel» → Abgeschlossen · «alle ausgesondert» → der Auftrag, der
    sie verliert, ist Abgebrochen. Beides fällt aus ``_derive`` heraus, ohne einen vierten
    Auftragsstatus: was zählt, ist «hat noch etwas ein Ziel erreicht oder ist unterwegs».
    """
    from app.domain import statuses as st
    from app.models import InstanceUnit, OrderUnit, ProcessStep
    from app.services import process as proc

    db = _db()
    try:
        art, parent, p_steps = _make(db, quantity=3, steps=[_capture_step(), _capture_step()])
        pieces = (db.query(InstanceUnit)
                  .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
                  .filter(OrderUnit.order_id == parent.id).all())
        numbers = sorted(proc.unit_numbers(db, pieces).values())

        # Zwei Stücke gehen in eine Abweichung, die sie sperrt; eines läuft durch.
        dev = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": 2, "origin": "lager",
                    "returns": True,
                    "units": [{"number": n, "from_order": parent.object_id}
                              for n in numbers[:2]]}],
            steps=[_disposal_step("block")], actor_id=None,
        )
        db.flush()
        d_step = db.query(ProcessStep).filter(ProcessStep.order_id == dev.id).one()
        _confirm(db, dev, d_step, values={"grund_der_sperre": "Wartet auf Labor"})

        for step in p_steps:
            _confirm(db, parent, step, values={"ok": True})

        assert proc.order_status(db, parent) == st.ABGESCHLOSSEN, (
            "Eines hat das Ziel erreicht – der Auftrag ist abgeschlossen."
        )
        assert proc.order_status(db, dev) == st.ABGESCHLOSSEN
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# §5 – was das Modul anbietet
# ---------------------------------------------------------------------------

def test_blocking_asks_for_a_reason_and_scrapping_does_not():
    """**Der Grund ist Pflicht beim Sperren – und nur dort.**

    Eine Sperre ohne Begründung ist in drei Monaten wertlos: niemand weiss mehr, ob man
    sie aufheben darf. Beim Verschrotten ist der Scan die Bestätigung; ein zweites Feld
    macht den Fall nicht häufiger richtig, sondern nur länger.

    Der Grund ist dabei **kein neuer Mechanismus**, sondern ein gewöhnlicher
    Erfassungspunkt – deklariert vom Modul, nicht vom Anwender: wäre er konfigurierbar,
    könnte man ihn wegkonfigurieren, und genau er ist der Sinn der Sperre.
    """
    from fastapi import HTTPException
    from app.domain import modules
    from app.models import Capture, ProcessStep

    db = _db()
    try:
        block = modules.get("aussondern").clean_config({"mode": "block"})
        assert [p["label"] for p in block["points"]] == ["Grund der Sperre"]
        assert modules.get("aussondern").clean_config({"mode": "scrap"})["points"] == []

        # Sperren ohne Grund: abgelehnt, mit Namen.
        _, order, rows = _make(db, quantity=1, steps=[_disposal_step("block")])
        with pytest.raises(HTTPException) as e:
            _confirm(db, order, rows[0])
        assert "Grund der Sperre" in str(e.value.detail)

        # Mit Grund: erfasst, am Stück hinterlegt.
        _confirm(db, order, rows[0], values={"grund_der_sperre": "Riss im Lack"})
        got = db.query(Capture).filter(Capture.order_id == order.id).all()
        assert [c.values["grund_der_sperre"] for c in got] == ["Riss im Lack"]

        # Verschrotten: keine Erfassung, keine leere Zeile.
        _, scrap_order, scrap_rows = _make(db, quantity=1, steps=[_disposal_step("scrap")])
        _confirm(db, scrap_order, scrap_rows[0])
        assert db.query(Capture).filter(Capture.order_id == scrap_order.id).count() == 0, (
            "Eine leere Erfassung wäre ein Nachweis über nichts."
        )

        # Und das Verb sagt, was passiert – aus der Registry, nicht aus der Oberfläche.
        step = db.query(ProcessStep).filter(ProcessStep.order_id == scrap_order.id).one()
        assert modules.get(step.module_type).action_for(step.config) == "Verschrotten"
        assert modules.get("aussondern").action_for({"mode": "block"}) == "Sperren"
    finally:
        db.rollback()
        db.close()


def test_the_scan_requirement_is_inherited_not_rebuilt():
    """**Teil B gilt hier, ohne eine Zeile dafür** – die Regel steht im Framework.

    Das Aussondern hat nie etwas über Verifikation gesagt; es erbt sie von ``Module``.
    Genau das ist der Sinn: ein künftiges Modul bekommt sie ebenso geschenkt.
    """
    from fastapi import HTTPException
    from app.domain import modules
    from app.services import process as proc

    db = _db()
    try:
        assert modules.get("aussondern").requires_verification is True

        _, order, rows = _make(db, quantity=1, steps=[_disposal_step("scrap")])
        with pytest.raises(HTTPException) as e:
            proc.confirm_step(db, order=order, step_id=rows[0].id, values={},
                              actor_id=None)
        assert e.value.status_code == 400
        assert "bestätigt" in str(e.value.detail)
    finally:
        db.rollback()
        db.close()


def test_the_stock_view_carries_the_new_states_by_itself():
    """**§6 – der Bestand führt sie automatisch mit**, weil die Zuordnung am Status hängt.

    Kein Eingriff in die Bestandsansicht: `stock_kind` beantwortet je Zustand, ob er zum
    Bestand oder zur Historie zählt, und die Leiste summiert darüber. Ein gesperrtes
    Stück liegt im Regal (Bestand), ein verschrottetes nicht mehr (Historie) – und beide
    bleiben als Datensatz sichtbar (§2.2).
    """
    from app.services import instances as inst_svc
    from app.schemas.instance import stock_states

    def states_of(article):
        rows = stock_states(inst_svc.article_states(db, article_id=article.id))
        return {r.status: r for r in rows}

    db = _db()
    try:
        art, order, rows = _make(db, quantity=4, steps=[_disposal_step("block")])
        _confirm(db, order, rows[0], values={"grund_der_sperre": "Laborprüfung offen"})

        blocked = states_of(art)["gesperrt"]
        assert blocked.quantity == 4
        assert blocked.stock == "live", (
            "Ein gesperrtes Stück liegt im Regal – es gehört in den Bestands-Block."
        )

        art2, order2, rows2 = _make(db, quantity=2, steps=[_disposal_step("scrap")])
        _confirm(db, order2, rows2[0])
        scrapped = states_of(art2)["verschrottet"]
        assert scrapped.quantity == 2, "Verschrottete Stücke verschwinden nicht (§2.2)."
        assert scrapped.stock == "history", (
            "Ein verschrottetes Stück ist kein Material mehr – aber es bleibt sichtbar."
        )
    finally:
        db.rollback()
        db.close()
