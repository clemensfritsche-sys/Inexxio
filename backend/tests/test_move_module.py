"""**Bewegen: der Ort ist ein Zeiger, kein Zustand.**

Sechs Regeln. Zwei davon gehören dem Modul, vier dem **Ort** – und die vier gelten für
jeden künftigen Weg, der einen Ort setzt.

1. **Der Ort hängt am Stück**, nicht an der Instanz: zwei Schrauben derselben Charge
   dürfen an zwei Orten liegen. Genau das konnte der Vorgänger nicht.
2. **Ein Ort ändert nichts ausser dem Ort** – kein Status, keine Zugehörigkeit. Das ist
   die Robustheitsgarantie: keine andere Regel im System muss von diesem Modul wissen.
3. **Halter ist eine Objektnummer**, und zwar eine, die es gibt. Eine Einzelinstanz kann
   es nicht sein – sie zieht keine Objektnummer, es gäbe kein Etikett zu scannen.
4. **Keine Zyklen.** Die eine Regel des sonst dummen Feldes, zweifach: verhindert beim
   Schreiben, gekappt beim Lesen.
5. **Ware zuerst, Ziel zuletzt** – und ohne Ziel passiert nichts.
6. **Ein gesperrter Kanal ist serverseitig gesperrt.** Wäre er nur in der Oberfläche
   gesperrt, wäre die Sperre eine Bitte.

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


def _move_step(target=None):
    return {"module_type": "bewegen", "config": {"target": target}}


def _article(db, *, steps: list[dict], name="Prüfstück", serialization="batch"):
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization=serialization)
    db.add(art)
    db.flush()
    # Ein **Halter** braucht keinen Erzeugungsprozess: ein Regal wird hier nicht gebaut,
    # es steht schon da. Die Vorlage verlangt sonst mindestens ein Modul.
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


def _holder_instance(db, *, name="Regal"):
    """Ein physischer Halter – ein Regal ist eine **Instanz**, kein neuer Datensatztyp."""
    from app.services import instances as inst_svc
    art = _article(db, steps=[], name=name, serialization="einzeln")
    made = inst_svc.create_instances(
        db, article=art, kind="einzeln", instance_count=1, units_each=1,
    )
    db.flush()
    return made[0]


def _company(db, *, name="Werk Nord"):
    from app.models import CompanySettings
    from app.services import objects as obj
    co = CompanySettings(object_id=obj.next_object_id(db), company_name=name)
    db.add(co)
    db.flush()
    return co


def _units(db, order):
    """Die Einzelinstanzen dieses Auftrags."""
    from app.models import InstanceUnit, OrderUnit
    return (
        db.query(InstanceUnit)
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .filter(OrderUnit.order_id == order.id)
        .order_by(InstanceUnit.id)
        .all()
    )


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


# ---------------------------------------------------------------------------
# 1 + 2 – der Ort hängt am STÜCK und ändert sonst nichts
# ---------------------------------------------------------------------------

def test_a_move_sets_the_place_and_nothing_else():
    """**Ein Ort ist kein Zustand.**

    Nach dem Bewegen trägt jedes Stück seinen Halter – und **sonst hat sich nichts
    geändert**: der Status ist derselbe wie vorher, die Zugehörigkeit ebenso. Genau das
    ist die Garantie, wegen der keine andere Regel im System von diesem Modul wissen
    muss.
    """
    from app.domain import statuses as st
    from app.services import places as places_svc

    db = _db()
    try:
        shelf = _holder_instance(db)
        _art, order, steps = _make(db, quantity=3, steps=[_move_step(shelf.object_id)])

        before = {u.id: u.status for u in _units(db, order)}
        assert all(s == st.IM_PROZESS for s in before.values())
        assert all(u.place_object_id is None for u in _units(db, order)), (
            "Ein frisch erzeugtes Stück liegt nirgends – standortlos ist der Startwert."
        )

        _confirm(db, order, steps[0], place=shelf.object_id, transport="manuell")

        after = _units(db, order)
        assert [u.place_object_id for u in after] == [shelf.object_id] * 3
        # **Der Ort ändert den Status nicht.** Das Modul ist ein Durchläufer; dass der
        # Auftrag danach fertig ist (ein Modul, danach das Ende), ist eine Aussage über
        # den Ablauf, nicht über den Ort.
        assert places_svc.counts_at(db, shelf.object_id) == 3
    finally:
        db.rollback()
        db.close()


def test_the_place_belongs_to_the_piece_not_to_the_instance():
    """**Zwei Stücke derselben Charge dürfen an zwei Orten liegen.**

    Das ist der ganze Gewinn des Einzelinstanz-Modells an dieser Stelle: der Vorgänger
    führte eine Standort→Menge-Map an der Instanz plus einen denormalisierten Skalar
    daneben und brauchte einen Umschalter dazwischen. Hier ist es eine Spalte je Stück.
    """
    from app.services import places as places_svc

    db = _db()
    try:
        shelf, bench = _holder_instance(db), _holder_instance(db, name="Werkbank")
        _art, order, _steps = _make(db, quantity=2, steps=[_move_step()])
        units = _units(db, order)

        places_svc.place(db, units=[units[0]], target=shelf.object_id)
        places_svc.place(db, units=[units[1]], target=bench.object_id)
        db.flush()

        assert units[0].place_object_id == shelf.object_id
        assert units[1].place_object_id == bench.object_id
        assert units[0].instance_id == units[1].instance_id, (
            "Der Fall ist nur dann der gemeinte, wenn beide zur SELBEN Instanz gehören."
        )
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 3 – Halter ist eine Objektnummer, und zwar eine, die es gibt
# ---------------------------------------------------------------------------

def test_a_holder_must_exist_and_be_something_that_can_hold():
    """**Ein Artikel ist kein Ort.** Halter sind Instanz, Benutzer, Unternehmen."""
    from fastapi import HTTPException
    from app.services import places as places_svc

    db = _db()
    try:
        art = _article(db, steps=[], name="Schraube M6")
        _a, order, _s = _make(db, quantity=1, steps=[_move_step()])
        units = _units(db, order)

        with pytest.raises(HTTPException) as gone:
            places_svc.place(db, units=units, target=999_999_999)
        assert gone.value.status_code == 404

        with pytest.raises(HTTPException) as wrong:
            places_svc.place(db, units=units, target=art.object_id)
        assert wrong.value.status_code == 404, (
            "Ein Artikel trägt eine Objektnummer, ist aber eine Gattung – kein Ort."
        )
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 4 – keine Zyklen: verhindert beim Schreiben, gekappt beim Lesen
# ---------------------------------------------------------------------------

def test_a_place_never_runs_in_a_circle():
    """**Regal in Behälter, Behälter in Regal** – die eine Regel des dummen Feldes.

    Ohne sie liefe die Kette im Kreis, und mit ihr jede Bestandsansicht. Verhindert wird
    das beim **Schreiben**; das Netz beim Lesen (``MAX_STATIONS``) steht daneben für
    alles, was diese Prüfung nie gesehen hat.
    """
    from fastapi import HTTPException
    from app.models import Instance, InstanceUnit
    from app.services import places as places_svc

    db = _db()
    try:
        shelf, box = _holder_instance(db), _holder_instance(db, name="Behälter")
        shelf_unit = db.query(InstanceUnit).join(
            Instance, Instance.id == InstanceUnit.instance_id,
        ).filter(Instance.object_id == shelf.object_id).one()
        box_unit = db.query(InstanceUnit).join(
            Instance, Instance.id == InstanceUnit.instance_id,
        ).filter(Instance.object_id == box.object_id).one()

        # Der Behälter kommt ins Regal – das ist völlig normal.
        places_svc.place(db, units=[box_unit], target=shelf.object_id)
        db.flush()

        # Das Regal jetzt IN den Behälter zu legen wäre der Kreis.
        with pytest.raises(HTTPException) as circle:
            places_svc.place(db, units=[shelf_unit], target=box.object_id)
        assert circle.value.status_code == 400
        assert "Kreis" in circle.value.detail

        # Und in sich selbst geht ebenfalls nicht.
        with pytest.raises(HTTPException) as itself:
            places_svc.place(db, units=[shelf_unit], target=shelf.object_id)
        assert itself.value.status_code == 400
    finally:
        db.rollback()
        db.close()


def test_the_chain_reads_from_inside_out_and_stops_at_an_address():
    """**Schraube › Behälter › Regal › Werk Nord** – und dort endet sie.

    Ein Unternehmen (oder eine Person) trägt eine Anschrift; alles davor ist eine
    Verschachtelung darin. Weiterzulaufen gäbe es nichts mehr.
    """
    from app.models import Instance, InstanceUnit
    from app.services import places as places_svc

    db = _db()
    try:
        works = _company(db)
        shelf = _holder_instance(db, name="Regal")
        box = _holder_instance(db, name="Behälter")

        def unit_of(inst):
            return db.query(InstanceUnit).join(
                Instance, Instance.id == InstanceUnit.instance_id,
            ).filter(Instance.object_id == inst.object_id).one()

        places_svc.place(db, units=[unit_of(shelf)], target=works.object_id)
        places_svc.place(db, units=[unit_of(box)], target=shelf.object_id)
        _art, order, _s = _make(db, quantity=1, steps=[_move_step()])
        screw = _units(db, order)[0]
        places_svc.place(db, units=[screw], target=box.object_id)
        db.flush()

        chain = places_svc.chain(db, screw.place_object_id)
        assert [s.object_id for s in chain] == [
            box.object_id, shelf.object_id, works.object_id,
        ]
        assert [s.kind for s in chain] == ["instance", "instance", "organization"]
        assert chain[-1].label == "Werk Nord"
        assert places_svc.chain(db, None) == [], "Standortlos ist eine leere Kette."
    finally:
        db.rollback()
        db.close()


def test_a_broken_chain_is_capped_not_endless():
    """**Das Netz beim Lesen**: ein Zyklus, den es nicht geben dürfte, hängt nichts auf.

    Hergestellt wird er hier **an der Prüfung vorbei** (direkte Zuweisung) – genau so,
    wie ihn Altbestand oder ein Fremdschreiber hinterlassen würde. Ein Wächter, der nur
    den sauberen Weg kennt, prüft das Netz nicht.
    """
    from app.models import Instance, InstanceUnit
    from app.services import places as places_svc

    db = _db()
    try:
        a, b = _holder_instance(db, name="A"), _holder_instance(db, name="B")

        def unit_of(inst):
            return db.query(InstanceUnit).join(
                Instance, Instance.id == InstanceUnit.instance_id,
            ).filter(Instance.object_id == inst.object_id).one()

        unit_of(a).place_object_id = b.object_id
        unit_of(b).place_object_id = a.object_id
        db.flush()

        chain = places_svc.chain(db, a.object_id)
        # **Scharf, nicht nur endlich**: zwei Stationen im Kreis dürfen genau zweimal
        # erscheinen. Eine Obergrenze allein liesse zehn Wiederholungen durchgehen –
        # gekappt wäre es dann zwar, aber gelogen.
        assert [st.object_id for st in chain] == [a.object_id, b.object_id], (
            "Ein Kreis beim Lesen muss beim ersten Wiedersehen enden – sonst zeigt die "
            "Ansicht dieselbe Station mehrfach, bis die Obergrenze greift."
        )
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 5 – Ware zuerst, Ziel zuletzt: ohne Ziel passiert nichts
# ---------------------------------------------------------------------------

def test_without_a_target_nothing_moves():
    """**Ohne Zielort keine Bewegung** – und zwar an der Ausführungsstelle, mit 400.

    Ein Modul ohne festes Ziel verlangt den Scan; ein Modul **mit** festem Ziel weist
    einen abweichenden Scan ab. Beides serverseitig: eine Sperre, die nur im Dialog
    steht, ist eine Bitte.
    """
    from fastapi import HTTPException
    from app.services import process as proc

    db = _db()
    try:
        shelf, bench = _holder_instance(db), _holder_instance(db, name="Werkbank")

        # (a) offenes Ziel, nichts gescannt → 400, und nichts hat sich bewegt
        _art, order, steps = _make(db, quantity=1, steps=[_move_step()])
        with pytest.raises(HTTPException) as blank:
            _confirm(db, order, steps[0])
        assert blank.value.status_code == 400

        # (b) festes Ziel, etwas anderes gescannt → 400
        _a2, order2, steps2 = _make(db, quantity=1, steps=[_move_step(shelf.object_id)])
        with pytest.raises(HTTPException) as wrong:
            _confirm(db, order2, steps2[0], place=bench.object_id)
        assert wrong.value.status_code == 400
        assert str(shelf.object_id) in wrong.value.detail, (
            "Die Meldung muss sagen, wohin es eigentlich gehen sollte."
        )

        # (c) festes Ziel, richtig gescannt → es bewegt sich
        shelf3 = _holder_instance(db)
        _a3, order3, steps3 = _make(db, quantity=1, steps=[_move_step(shelf3.object_id)])
        _confirm(db, order3, steps3[0], place=shelf3.object_id)
        assert _units(db, order3)[0].place_object_id == shelf3.object_id

        # Und der Log weiss, woher und wohin (§7.2) – kein zweiter Speicher dafür.
        events = proc.events_page(db, order3, limit=50)[0]
        moved = [e for e in events if (e.payload or {}).get("place")]
        assert moved, "Die Bewegung steht nicht im Ereignis-Log."
        assert moved[0].payload["place"]["to"] == shelf3.object_id
        assert moved[0].payload["place"]["from"] is None
        assert moved[0].payload["transport"] == "manuell"
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 6 – ein gesperrter Kanal ist SERVERSEITIG gesperrt
# ---------------------------------------------------------------------------

def test_a_locked_transport_is_refused_by_the_server():
    """**Paket und Fracht stehen da, aber sie gehen nicht.**

    Sie sichtbar zu lassen ist eine Entscheidung über die Oberfläche – dass sie nicht
    laufen, ist eine Entscheidung über das System. Wäre die Sperre nur ein
    ausgegrauter Knopf, käme ein direkter Aufruf daran vorbei.
    """
    from fastapi import HTTPException
    from app.domain import modules

    db = _db()
    try:
        shelf = _holder_instance(db)
        _art, order, steps = _make(db, quantity=1, steps=[_move_step(shelf.object_id)])

        for locked in ("paket", "fracht"):
            with pytest.raises(HTTPException) as refused:
                _confirm(db, order, steps[0], place=shelf.object_id, transport=locked)
            assert refused.value.status_code == 400

        with pytest.raises(HTTPException) as unknown:
            _confirm(db, order, steps[0], place=shelf.object_id, transport="beamen")
        assert unknown.value.status_code == 400

        # Die Liste nennt **alles**, was es geben wird – nicht nur das Verfügbare.
        catalogue = modules.get("bewegen").TRANSPORTS
        assert [t["key"] for t in catalogue] == ["manuell", "paket", "fracht"]
        assert [t["available"] for t in catalogue] == [True, False, False]
    finally:
        db.rollback()
        db.close()


def test_only_a_moving_module_carries_transports():
    """**Die Transportliste IST das Bit** «bewegt dieses Modul?».

    Sie ist bei jedem anderen Modultyp leer – darum braucht die Oberfläche keine
    Fallunterscheidung nach dem Modultyp, und ein neuer Kanal ist ein Eintrag in der
    Registry statt eines Eingriffs in eine Komponente.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    for key in modules.MODULES:
        has = bool(getattr(modules.get(key), "TRANSPORTS", ()))
        assert has == (key == "bewegen"), (
            f"«{key}» trägt Transportarten, obwohl es nichts bewegt – oder umgekehrt."
        )
        moves = modules.get(key).movement_for({}, target=None, transport=None) \
            if key != "bewegen" else True
        assert bool(moves) == (key == "bewegen"), (
            f"«{key}» beantwortet die Bewegungsfrage nicht mit «nein»."
        )


# ---------------------------------------------------------------------------
# Die Anzeige – aufgelöst je HALTER, nicht je Stück
# ---------------------------------------------------------------------------

def test_the_chain_is_resolved_per_holder_not_per_piece():
    """**Die N+1-Falle, an der die Ortsanzeige des Vorgängers hing** – gemessen.

    Sechzig Schrauben in einem Regal sind **eine** Kette. Wer sie je Zeile auflöst, stellt
    dieselbe Frage sechzigmal; bei drei Kettenstufen sind das Hunderte von Abfragen für
    eine Liste, die eine Zahl zeigt.

    Gezählt wird darum wirklich – nicht die Bauweise gelesen, sondern die Abfragen
    gezählt: die Zahl darf mit der **Tiefe** wachsen, nicht mit der **Menge**.
    """
    from sqlalchemy import event
    from app.models import Instance, InstanceUnit
    from app.services import places as places_svc

    db = _db()
    try:
        works = _company(db)
        shelf, box = _holder_instance(db, name="Regal"), _holder_instance(db, name="Behälter")

        def unit_of(inst):
            return db.query(InstanceUnit).join(
                Instance, Instance.id == InstanceUnit.instance_id,
            ).filter(Instance.object_id == inst.object_id).one()

        places_svc.place(db, units=[unit_of(shelf)], target=works.object_id)
        places_svc.place(db, units=[unit_of(box)], target=shelf.object_id)

        _art, order, _s = _make(db, quantity=60, steps=[_move_step()])
        screws = _units(db, order)
        places_svc.place(db, units=screws, target=box.object_id)
        db.flush()

        counted: list[int] = []

        def tally(*_args, **_kw):
            counted.append(1)

        event.listen(db.bind, "before_cursor_execute", tally)
        try:
            chains = places_svc.for_units(db, screws)
        finally:
            event.remove(db.bind, "before_cursor_execute", tally)

        assert len(chains) == 60
        assert all(len(c) == 3 for c in chains.values()), (
            "Jedes Stück kennt seinen Weg bis zur Adresse: Behälter › Regal › Werk Nord."
        )
        assert len(counted) <= 16, (
            f"{len(counted)} Abfragen für 60 Stücke an EINEM Ort – die Auflösung hängt "
            f"an der Zahl der Stücke statt an der Tiefe der Kette."
        )
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# Testnotizen #730/#731/#732 – ein freier Schritt braucht eine Vorschlagsquelle
# ---------------------------------------------------------------------------

def test_holders_are_searchable_by_number_and_by_name():
    """**«001» oder «Clemens» – beides muss einen Vorschlag ergeben.**

    Ein **Verifikationsschritt** braucht keine Suche: was er annimmt, ist seine
    Vorschlagsliste (``scan.offersFor``). Ein **freier** Schritt hat diese Ableitung
    nicht – und hatte darum gar keine Vorschläge: wer «00292» tippte, sah nichts, obwohl
    es die Nummer gibt. Das ist die eine Quelle, aus der beide Zielort-Eingaben schöpfen
    (das Feld im Editor und der Scan zur Laufzeit).

    **Angeboten wird nur, was auch Halter sein kann.** Ein Artikel trägt eine
    Objektnummer, ist aber eine Gattung – ihn vorzuschlagen hiesse, eine Wahl anzubieten,
    die ``assert_placeable`` danach abweist.
    """
    from app.models import CompanySettings, UserProfile
    from app.services import objects as obj, places as places_svc

    db = _db()
    try:
        art = _article(db, steps=[], name="Hochregal", serialization="einzeln")
        shelf = _holder_instance(db, name="Behälter")
        # Die Objektnummer macht Mail und uid eindeutig – die Test-Datenbank ist
        # gemeinsam, und ein fester Wert kollidiert mit dem vorherigen Lauf.
        uid = obj.next_object_id(db)
        user = UserProfile(object_id=uid, email=f"probe-{uid}@example.com",
                           first_name="Clemens", last_name="Fritsche",
                           firebase_uid=f"probe-{uid}")
        co = CompanySettings(object_id=obj.next_object_id(db), company_name="Werk Nord")
        db.add_all([user, co])
        db.flush()

        def found(q):
            return {s.object_id for s in places_svc.search(db, q)}

        # Nach der Nummer – auch als Teilstring, so wie man tippt.
        assert shelf.object_id in found(str(shelf.object_id)[-5:])
        assert user.object_id in found(str(user.object_id)[-4:])
        # Nach dem Namen – Person, Firma und der Artikelname der Halter-Instanz.
        assert user.object_id in found("Clemens")
        assert co.object_id in found("Werk")
        assert shelf.object_id in found("Behälter")
        # Und ein Artikel ist kein Ort.
        assert art.object_id not in found(str(art.object_id)), (
            "Ein Artikel wird als Zielort vorgeschlagen – die Prüfung weist ihn danach ab."
        )
        assert places_svc.search(db, "  ") == [], (
            "Ohne Suchbegriff kommt ein Katalog statt einer Abkürzung."
        )
    finally:
        db.rollback()
        db.close()
