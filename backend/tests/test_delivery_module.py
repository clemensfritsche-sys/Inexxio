"""**Ausliefern: das Stück gehört jetzt jemand anderem — und sonst nichts.**

Fünf Regeln. Keine davon ist neu: jede ist eine, die das Prozess-Framework längst
kennt – und genau das ist der Punkt. Dieses Modul ist das Ergebnis davon, dass aus dem
früheren Verkaufs-Modul der **Beleg** herausgenommen wurde; was übrig blieb, ist die
eine Aussage, die kein anderes Modul machen kann.

1. **Ein Scan, ein Statuswechsel.** Man liefert nicht blind aus.
2. **Es ist ein AUSGANG** (``terminal``) – jedes ankommende Stück verlässt den Auftrag.
   Und **``Verkauft`` bleibt trotzdem umkehrbar**: das sind zwei verschiedene Fragen.
3. **Der Ort fällt weg** – ohne eine Zeile in diesem Modul: ``Verkauft`` zählt zur
   Historie, und ``process._pass`` räumt den Ort für jeden solchen Zustand.
4. **Die Retoure ist ein ganz gewöhnlicher Auftrag** – kein Retouren-Modul, kein
   «zurücknehmen»-Endpunkt: das Greifen IST die Rücknahme, und weil der Start vom
   Regelstart abweicht, ist sie **automatisch** eine dokumentierte Abweichung.
5. **Es hat keine Konfiguration.** An wen geliefert wird, steht im Geldvorgang desselben
   Auftrags; was geliefert wird, sagen die Stücke davor.

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


def _deliver_step():
    return {"module_type": "ausliefern", "config": {}}


def _capture_step():
    return {"module_type": "datenerfassung",
            "config": {"points": [{"label": "OK", "type": "bool"}]}}


def _article(db, *, steps: list[dict], name="Welle", serialization="batch"):
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization=serialization)
    db.add(art)
    db.flush()
    if steps:
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


def _confirm(db, order, step, **kw):
    """Bestätigen – je wartender Instanz einmal, wie die Scan-Regel es verlangt."""
    from app.services import process as proc
    out = []
    for row in proc.step_work(db, order, step):
        out.append(proc.confirm_step(
            db, order=order, step_id=step.id, actor_id=None, values={},
            instance_object_id=row["instance_object_id"], verification="scan", **kw,
        ))
    db.flush()
    return out


def _units(db, order):
    from app.models import InstanceUnit, OrderUnit
    return (
        db.query(InstanceUnit)
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .filter(OrderUnit.order_id == order.id)
        .order_by(InstanceUnit.id)
        .all()
    )


# ---------------------------------------------------------------------------
# 1 + 3 – ein Scan, ein Statuswechsel, und der Ort fällt weg
# ---------------------------------------------------------------------------

def test_delivering_sets_sold_and_takes_the_place_away():
    """**Der eine Statuswechsel – und der Ort verschwindet, ohne eine Zeile dafür.**

    ``Verkauft`` zählt zur **Historie** (``Status.stock``), und ``process._pass`` räumt
    den Ort für jeden Zustand, der das tut. Wo das Stück beim Kunden liegt, ist nicht
    unsere Auskunft.

    Bug-Formen: (a) das Modul setzt einen anderen Zustand oder gar keinen; (b) der Ort
    bleibt stehen – dann läge ein verkauftes Stück weiterhin in unserem Regal, und die
    Ortskette behauptete etwas über fremdes Eigentum.
    """
    from app.domain import statuses as st
    from app.services import places as places_svc

    db = _db()
    try:
        shelf_art = _article(db, steps=[], name="Regal", serialization="einzeln")
        from app.services import instances as inst_svc
        shelf = inst_svc.create_instances(
            db, article=shelf_art, kind="einzeln", instance_count=1, units_each=1)[0]

        _art, order, steps = _make(db, quantity=3, steps=[
            {"module_type": "bewegen", "config": {"target": shelf.object_id}},
            _deliver_step(),
        ])
        _confirm(db, order, steps[0], place=shelf.object_id)
        assert all(u.place_object_id == shelf.object_id for u in _units(db, order)), (
            "Die Szene ist nur dann die gemeinte, wenn die Stücke vorher irgendwo liegen."
        )

        _confirm(db, order, steps[1])

        after = _units(db, order)
        assert {u.status for u in after} == {st.VERKAUFT}, (
            "Das Modul setzt nicht «Verkauft» (a) – dann sagt der einzige Satz, den es "
            "zu sagen hat, nichts."
        )
        assert all(u.place_object_id is None and u.place_unit_id is None for u in after), (
            "Der Ort steht noch da (b) – ein verkauftes Stück liegt nicht mehr bei uns."
        )
        assert places_svc.counts_at(db, shelf.object_id) == 0
    finally:
        db.rollback()
        db.close()


def test_delivering_needs_the_scan():
    """**Man liefert nicht blind aus** – der Scan ist die Bestätigung.

    Dieselbe Regel wie beim Verschrotten, und sie steht am Modultyp
    (``requires_verification``), nicht in der Ausführungsstelle: die Oberfläche fragt die
    Eigenschaft, nie den Modultyp.

    Bug-Form: ``requires_verification`` fällt auf ``False`` – dann geht die Bestätigung
    ohne Etikett durch, und der Nachweis, WAS hinausging, ist keiner.
    """
    from app.domain import modules

    assert modules.get("ausliefern").requires_verification is True, (
        "Die Auslieferung verlangt keine Verifikation mehr – dann bestätigt ein Klick "
        "die Übergabe von etwas, das niemand angesehen hat."
    )


# ---------------------------------------------------------------------------
# 2 – es ist ein AUSGANG
# ---------------------------------------------------------------------------

def test_delivering_is_an_exit_and_the_chain_says_so():
    """►►► **Ein Ausgang — und die Kettenregel lässt gar nichts anderes zu.** ◄◄◄

    ``Module.terminal`` beantwortet «verlassen ALLE ankommenden Stücke den Auftrag
    hier?» – beim Ausliefern **ja**: was übergeben ist, gehört uns nicht mehr.

    *Die erste Fassung dieses Moduls stand auf ``terminal = False``, mit dem Verweis auf
    den Verbrauch (der ``Verbaut`` setzt und kein Ausgang ist). Die Kettenregel hat es
    sofort gemeldet, und der Unterschied ist die **Reichweite**: beim Verbrauch bleiben
    die durchlaufenden Stücke auf ``Im Prozess``, hier wechselt jedes ankommende. Ein
    nicht-terminales Modul, das den Zustand aller Stücke ändert, kann es gar nicht geben
    – es bräche die Kette am Modul dahinter oder am Ende-Objekt.*

    Bug-Formen: (a) ``terminal`` fällt auf ``False`` – dann lässt sich mit diesem Modul
    kein Prozess mehr freigeben, an keiner Position; (b) jemand «repariert» das, indem er
    ``status_after`` auf ``Im Prozess`` zieht – dann sagt das Modul gar nichts mehr.
    """
    from app.domain import chain, modules, statuses as st
    from fastapi import HTTPException

    mod = modules.get("ausliefern")
    assert mod.terminal is True, (
        "Die Auslieferung ist kein Ausgang mehr (a) – dann bricht die Kette an jeder "
        "Position, an der sie stehen kann."
    )
    assert mod.status_after == st.VERKAUFT, (
        "Das Modul setzt keinen eigenen Zustand mehr (b) – dann ist es ein Durchgang, "
        "und die eine Aussage, die es zu machen hat, fehlt."
    )
    assert not st.is_terminal(st.VERKAUFT), (
        "«Verkauft» ist endgültig geworden – dann gäbe es keine Retoure mehr. "
        "`Module.terminal` und `Status.terminal` sind zwei verschiedene Fragen."
    )

    # **Die Kette endet dort** – und hinter ihm ist Schluss, mit einem Satz, der es sagt.
    chain.assert_closes([{"module_type": "ausliefern",
                          "status_before": st.IM_PROZESS, "status_after": st.VERKAUFT}])
    with pytest.raises(HTTPException) as behind:
        chain.assert_closes([
            {"module_type": "ausliefern",
             "status_before": st.IM_PROZESS, "status_after": st.VERKAUFT},
            {"module_type": "datenerfassung",
             "status_before": st.IM_PROZESS, "status_after": st.IM_PROZESS},
        ])
    assert behind.value.status_code == 400
    assert "kein Modul" in behind.value.detail


# ---------------------------------------------------------------------------
# 4 – die Retoure ist ein ganz gewöhnlicher Auftrag
# ---------------------------------------------------------------------------

def test_a_return_is_an_ordinary_order_and_is_automatically_a_deviation():
    """►►► **Das Greifen IST die Rücknahme** – kein Retouren-Modul, kein Endpunkt. ◄◄◄

    Ein verkauftes Stück ist greifbar (``Verkauft`` ist nicht endgültig), und weil sein
    Start vom **Regelstart** abweicht (``Freigegeben``), ist der Auftrag automatisch eine
    dokumentierte Abweichung – ohne eine Zeile dafür.

    ►►► **Die Farbe spielt dabei keine Rolle.** ◄◄◄ ``Verkauft`` ist **grün** (es hat
    sein Ziel erreicht) und löst trotzdem eine Abweichung aus: ``deviation_flags``
    vergleicht mit dem Regelstart und nennt weder Farbe noch Status. Eine Regel, die nach
    der Farbe fragte, liesse ausgerechnet die Retoure aus dem Nachweis fallen.

    Bug-Formen: (a) ein verkauftes Stück ist nicht mehr greifbar; (b) der Auftrag, der es
    greift, ist keine Abweichung.
    """
    from app.domain import statuses as st
    from app.services import process as proc

    db = _db()
    try:
        _art, order, steps = _make(db, quantity=2, steps=[_deliver_step()])
        _confirm(db, order, steps[0])
        sold = _units(db, order)
        assert {u.status for u in sold} == {st.VERKAUFT}

        # (a) **greifbar** – die Auswahl-Liste sagt es, und sie sagt dasselbe wie die
        #     Freigabe (`pick_problem` ↔ `unpickable`, zwei Formen einer Regel).
        assert proc.pick_problem(sold[0], str(sold[0].id)) is None, (
            "Ein verkauftes Stück gilt als nicht greifbar (a) – dann gäbe es keinen Weg "
            "zurück, und «Verkauft» wäre in der Praxis endgültig."
        )

        from app.models import Article, Instance
        from app.services.instances import unit_number
        inst = db.get(Instance, sold[0].instance_id)
        art = db.get(Article, inst.article_id)
        back = proc.release(
            db,
            lines=[{"article_object_id": art.object_id,
                    "quantity": 1, "origin": "lager",
                    "units": [{"number": unit_number(inst, sold[0])}]}],
            steps=[_capture_step()], actor_id=None,
        )
        db.flush()
        # (b) **automatisch eine Abweichung** – niemand trägt sie ein.
        assert proc.deviation_flags(db, [back.id])[back.id], (
            "Die Retoure ist keine Abweichung (b) – dann fehlt genau der Nachweis, "
            "warum ein verkauftes Stück wieder im Haus ist."
        )
        assert st._BY_VALUE[st.VERKAUFT].tone == "done", (
            "«Verkauft» ist nicht mehr grün – die Abweichung hängt am Regelstart, nicht "
            "an der Farbe, und dieser Wächter prüft genau diese Unabhängigkeit."
        )
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 5 – es hat keine Konfiguration
# ---------------------------------------------------------------------------

def test_the_module_has_nothing_to_configure():
    """**An wen, was und wann stehen woanders** – hier gibt es kein Feld.

    ``clean_config`` nimmt nichts an: **an wen** geliefert wird, steht im Geldvorgang
    desselben Auftrags (ein Feld hier wäre die zweite Stelle für dieselbe Angabe), **was**
    sagen die Einzelinstanzen davor, **wann** sagt der Log.

    Bug-Form: ein durchgereichtes Feld (ein Kunde, ein Preis, eine Adresse) landet in der
    Konfiguration – dann gibt es die Angabe zweimal, und die hier getippte gewinnt.
    """
    from app.domain import modules

    clean = modules.get("ausliefern").clean_config({
        "party": 100000001, "amount": "99.00", "target": 100000002,
        "points": [{"label": "Unterschrift", "type": "signature"}],
    })
    assert set(clean) == {"points", "sample"}, (
        f"Die Auslieferung nimmt Konfiguration an: {sorted(clean)}."
    )
    assert clean["points"] == [], (
        "Erfassungspunkte sind durchgekommen – dann ist die Übergabe ein zweites "
        "Datenerfassungs-Modul, und dafür gibt es das Datenerfassungs-Modul."
    )
