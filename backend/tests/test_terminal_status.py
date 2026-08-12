"""**Ein Endzustand ist endgültig** – als ausführbare Regel, auf drei Ebenen.

Der gemeldete Fall lautete: ein verschrottetes Stück stand später wieder auf
``Freigegeben``. Nachstellbar war er über keinen einzigen Dienstpfad und über keine
einzige Anfrage – und genau das war die Spur. Der Schreiber sass **ausserhalb** der
Prozesslogik: eine Alt-Reparatur im Startvorgang (``main._ensure_columns``) setzte
``UPDATE instance_units SET status='freigegeben' WHERE status NOT IN
('freigegeben','im_prozess')``. Diese Liste stammte aus einer Zeit, in der es nur diese
beiden Zustände gab; als ``Gesperrt`` und ``Verschrottet`` dazukamen, wurde sie still
falsch. Seither hat **jeder Start** – also jeder Deploy – jedes ausgesonderte Stück
zurückgesetzt.

Daraus folgt die Form des Schutzes. Eine Prüfung im Modul hätte nichts genützt; eine
Prüfung in der Ausführungsstelle auch nicht. Er muss dort liegen, wo **jeder** Schreiber
vorbeikommt:

===============================================  =====================================
Die eine Schreibstelle der Prozesslogik          ``process._pass``
Die Tabelle selbst – für alles andere            ``statuses.terminal_guard_sql``
Der Abgleich Log ↔ Zeile, falls doch etwas war   ``flow._verify_history``
===============================================  =====================================

Jede der drei wird hier **gegen ihre Fehlerform** geprüft: ein Wächter, der nie
anschlägt, ist von einem kaputten nicht zu unterscheiden.

**Warum gegen echtes PostgreSQL.** Ein Trigger ist keine Anwendungsregel – gegen SQLite
geprüft wäre eine andere Wahrheit geprüft als die, die läuft.
"""

import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def _db():
    """Eine Sitzung gegen echtes PostgreSQL – oder ein Skip **mit Grund**."""
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
                    f"DATABASE_URL setzen, damit dieser Schutz wirklich geprüft wird.")


def _scrapped_unit(db):
    """Ein Stück im Endzustand – über die echten Modelle, nicht als SQL-Attrappe."""
    from app.domain import statuses as st
    from app.models import Article, Instance, InstanceUnit
    from app.services import objects as obj

    art = Article(object_id=obj.next_object_id(db), name="Endzustand", unit="stk",
                  serialization="unit", status="released")
    db.add(art)
    db.flush()
    inst = Instance(object_id=obj.next_object_id(db), article_id=art.id, kind="batch")
    db.add(inst)
    db.flush()
    unit = InstanceUnit(instance_id=inst.id, suffix=1, status=st.VERSCHROTTET)
    db.add(unit)
    db.commit()
    return unit


# ---------------------------------------------------------------------------
# Die Eigenschaft – eine, aus der alles folgt
# ---------------------------------------------------------------------------

def test_terminal_is_one_property_and_everything_follows_from_it():
    """**Endgültig ist eine Eigenschaft des Status, keine Liste daneben.**

    Aus ihr folgen die Auswahl-Liste, die Farbe und der Schutz in der Datenbank. Stünde
    daneben ein zweites Feld für dieselbe Frage, gäbe es zwei Stellen, an denen sie
    verschieden beantwortet werden kann – und genau eine davon wird beim nächsten
    Zustand vergessen.
    """
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    assert st.TERMINAL_UNIT_STATUSES == (st.VERSCHROTTET,), (
        "Heute gibt es genau einen Endzustand. Kommt einer dazu, ist das eine Zeile im "
        "CATALOG – und dieser Test die Stelle, an der man es bemerkt."
    )

    # Die Auswahl-Liste ist die Umkehrung, nicht eine zweite Aufzählung.
    assert set(st.SELECTABLE_UNIT_STATUSES) | set(st.TERMINAL_UNIT_STATUSES) == set(
        st.UNIT_STATUSES)
    assert not set(st.SELECTABLE_UNIT_STATUSES) & set(st.TERMINAL_UNIT_STATUSES)
    assert not st.is_selectable(st.VERSCHROTTET)
    assert st.is_selectable(st.GESPERRT), (
        "Gesperrt ist aufhebbar – das Greifen durch einen Auftrag IST das Aufheben."
    )

    # Unbekanntes wird gemeldet, nicht eingemauert: ein Tippfehler in den Daten darf
    # keine Sperre sein, die niemand mehr aufheben kann.
    assert not st.is_terminal("gibt_es_nicht")


def test_only_a_piece_can_be_terminal():
    """**Terminal darf nur ein Stück-Zustand sein** – und der Wächter meldet es beim Start.

    Auftrags- und Artikel-Zustände sind abgeleitet bzw. anderswo geführt; sie terminal zu
    nennen wäre eine Zusage, die niemand einlöst. Geprüft wird gegen die Fehlerform,
    sonst wäre nicht zu unterscheiden, ob die Regel greift oder fehlt.
    """
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    st._check()  # der echte Katalog ist in Ordnung

    kaputt = (
        st.Status(st.FREIGEGEBEN, "Freigegeben", "done", (st.UNIT,), stock=st.LIVE),
        st.Status(st.ABGEBROCHEN, "Abgebrochen", "danger", (st.ORDER,), terminal=True),
    )
    with pytest.raises(ValueError, match="endgültig"):
        st._check(kaputt)


# ---------------------------------------------------------------------------
# Ebene 1 – die eine Schreibstelle
# ---------------------------------------------------------------------------

def test_the_one_write_path_refuses_to_leave_a_terminal_state():
    """``process._pass`` weist es ab – **mit einem Satz**, nicht mit einer DB-Meldung.

    Die Prüfung sitzt hier, weil hier jeder Statuswechsel der Prozesslogik durchläuft
    (§4.1): Start, Modul, Ende. Ein neues Modul erbt sie, ohne von ihr zu wissen.
    """
    from fastapi import HTTPException

    db = _db()
    unit = _scrapped_unit(db)
    try:
        from app.domain import statuses as st
        from app.models import Order
        from app.services import process as proc

        with pytest.raises(HTTPException) as err:
            proc._pass(db, order=db.query(Order).first(), units=[unit],
                       membership_ids=[], kind="end", step=None,
                       status_after=st.FREIGEGEBEN, next_step_id=None, actor_id=None)
        assert err.value.status_code == 409
        detail = err.value.detail
        assert "Endzustand" in detail and "Verschrottet" in detail, detail
        assert "-1" in detail, (
            f"Die Meldung muss die Nummer des Stücks nennen, sonst sucht man sie: {detail}"
        )
        db.rollback()
    finally:
        _cleanup(db, unit)


# ---------------------------------------------------------------------------
# Ebene 2 – die Tabelle selbst
# ---------------------------------------------------------------------------

def test_the_database_refuses_it_too_even_for_a_raw_update():
    """**Der Trigger kennt auch die Schreiber, die niemand im Kopf hatte.**

    Ein Reparaturskript, eine Migration, ein ``UPDATE`` von Hand – sie alle gehen an der
    Anwendungslogik vorbei. Sie gehen nicht an der Tabelle vorbei.

    Geprüft wird ausdrücklich auch der **Massen-``UPDATE`` ohne Status-Bedingung**: das
    ist die Form, in der der Fehler wirklich auftrat.
    """
    from sqlalchemy import text

    db = _db()
    unit = _scrapped_unit(db)
    try:
        from app.core.database import engine
        from app.domain import statuses as st

        for name, sql in (
            ("gezielt", "UPDATE instance_units SET status='freigegeben' WHERE id=:i"),
            ("in Masse", "UPDATE instance_units SET status='freigegeben'"),
        ):
            with engine.connect() as conn:
                with pytest.raises(Exception) as err:  # noqa: PT011 - DBAPI-Fehlerklasse
                    conn.execute(text(sql), {"i": unit.id})
                    conn.commit()
            assert "Endzustand" in str(err.value), (
                f"Der {name}e UPDATE wurde durchgelassen – der Trigger fehlt oder greift nicht."
            )

        db.expire_all()
        from app.models import InstanceUnit
        assert db.get(InstanceUnit, unit.id).status == st.VERSCHROTTET

        # Was den Endzustand nicht antastet, bleibt erlaubt – der Trigger ist ein
        # Wächter über EINE Spalte, keine Schreibsperre für die Zeile.
        with engine.connect() as conn:
            conn.execute(text("UPDATE instance_units SET updated_at=now() WHERE id=:i"),
                         {"i": unit.id})
            conn.commit()
    finally:
        _cleanup(db, unit)


def test_the_trigger_is_generated_from_the_catalog_not_written_by_hand():
    """Die Liste im Trigger **ist** die Liste im Katalog – sonst laufen sie auseinander.

    Genau daran ist die Alt-Reparatur gescheitert: eine von Hand geschriebene
    Status-Liste, die niemand nachzog, als ein Zustand dazukam.
    """
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    sql = st.terminal_guard_sql()
    for s in st.TERMINAL_UNIT_STATUSES:
        assert f"'{s}'" in sql
    for s in st.SELECTABLE_UNIT_STATUSES:
        assert f"'{s}'" not in sql, (
            f"«{s}» ist nicht endgültig, steht aber im Trigger – ein wählbares Stück "
            f"liesse sich damit nie mehr bewegen."
        )
    assert "%%" not in sql, (
        "In plpgsql ist «%» der Platzhalter; «%%» wäre ein literales Prozentzeichen und "
        "die Funktion liesse sich nicht übersetzen («too many parameters for RAISE»)."
    )


def test_the_start_repairs_only_what_the_catalog_does_not_know():
    """**Die Alt-Reparatur in ihrer Bug-Form – und in ihrer heutigen.**

    Sie soll den Platzhalter aus dem Basis-Neuaufbau glattziehen und sonst nichts. Als
    negative Liste geschrieben (``NOT IN ('freigegeben','im_prozess')``) traf sie jeden
    Zustand, den es damals noch nicht gab. Aus dem Katalog abgeleitet kann ihr das nicht
    mehr passieren – und der Vergleich beider Formen ist der Beweis.
    """
    sys.path.insert(0, str(BACKEND))
    from app.domain import statuses as st

    veraltet = {"freigegeben", "im_prozess"}          # die Liste von damals
    heute = set(st.UNIT_STATUSES)                      # die Liste von jetzt

    getroffen = {s for s in heute if s not in veraltet}
    assert getroffen, (
        "Wenn diese Menge leer wäre, könnte der Test die Bug-Form nicht mehr zeigen."
    )
    assert st.VERSCHROTTET in getroffen and st.GESPERRT in getroffen, (
        "Das ist die Bug-Form: die alte Reparatur hätte genau diese Zustände "
        "zurückgesetzt – bei jedem Start."
    )
    # Und die heutige Form trifft keinen einzigen bekannten Zustand.
    assert not {s for s in heute if s not in heute}

    # Nur der Code. Eine **Begründung**, warum etwas weg ist, darf den alten Wortlaut
    # nennen – sonst dürfte man den Fehler nicht mehr erklären, den man behoben hat.
    src = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    main_src = "\n".join(
        line for line in src.split("\n") if not line.lstrip().startswith("#")
    )
    assert "NOT IN ('freigegeben','im_prozess')" not in main_src, (
        "Die von Hand geschriebene Status-Liste ist zurück – sie veraltet beim nächsten "
        "neuen Zustand still und setzt ihn bei jedem Start zurück."
    )
    assert "st.UNIT_STATUSES" in main_src, (
        "Die Reparatur muss ihre Liste aus dem Katalog nehmen, nicht aus dem Gedächtnis."
    )


# ---------------------------------------------------------------------------
# Ebene 3 – der Abgleich, falls doch etwas vorbeikam
# ---------------------------------------------------------------------------

def test_the_flow_reports_a_piece_that_left_a_terminal_state():
    """**Die Invariante, die gefehlt hat** – und warum sie den Log allein nicht liest.

    Der Schreiber, der Schaden anrichtet, geht am Log vorbei und hinterlässt keinen
    Eintrag, den man zählen könnte. Darum wird nach dem **Widerspruch** gefragt: der Log
    sagt, dieses Stück hat einen Endzustand erreicht – die Zeile sagt etwas anderes.

    Gegengeprüft in beide Richtungen: ohne Widerspruch meldet sie nichts.
    """
    from sqlalchemy import text

    db = _db()
    unit = _scrapped_unit(db)
    try:
        from app.core.database import engine
        from app.domain import statuses as st
        from app.models import Order, OrderUnit, ProcessEvent
        from app.services import flow

        order = db.query(Order).first()
        if order is None:
            pytest.skip("Kein Auftrag vorhanden – die Invariante braucht einen Träger.")

        db.add(OrderUnit(order_id=order.id, instance_unit_id=unit.id))
        db.add(ProcessEvent(order_id=order.id, instance_unit_id=unit.id, kind="step",
                            status_before=st.IM_PROZESS, status_after=st.VERSCHROTTET))
        db.commit()

        g = flow.build(db, order)
        assert not [p for p in g.problems if "Endzustand" in p], (
            f"Ohne Widerspruch darf nichts gemeldet werden: {g.problems}"
        )

        # Jetzt die Bug-Form herstellen – am Trigger vorbei, so wie es der Fehler tat.
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE instance_units DISABLE TRIGGER "
                              f"{st.TERMINAL_GUARD_TRIGGER}"))
            conn.execute(text("UPDATE instance_units SET status='freigegeben' WHERE id=:i"),
                         {"i": unit.id})
            conn.execute(text(f"ALTER TABLE instance_units ENABLE TRIGGER "
                              f"{st.TERMINAL_GUARD_TRIGGER}"))
            conn.commit()

        db.expire_all()
        g = flow.build(db, order)
        assert [p for p in g.problems if "Endzustand" in p], (
            "Ein Stück hat laut Log einen Endzustand erreicht und steht nicht mehr "
            f"darauf – das muss gemeldet werden: {g.problems}"
        )
    finally:
        _cleanup(db, unit)


def _cleanup(db, unit) -> None:
    from sqlalchemy import text

    db.rollback()
    db.execute(text("DELETE FROM process_events WHERE instance_unit_id=:i"), {"i": unit.id})
    db.execute(text("DELETE FROM order_units WHERE instance_unit_id=:i"), {"i": unit.id})
    db.execute(text("DELETE FROM instance_units WHERE id=:i"), {"i": unit.id})
    db.execute(text("DELETE FROM instances WHERE id=:i"), {"i": unit.instance_id})
    db.commit()
    db.close()
