"""**Die Stück-Auswahl: die richtige Frage, und sie skaliert.**

Zwei Testnotizen, eine Datei — sie hängen an derselben Stelle (``GET /erp/orders/
unit-options`` und der Picker darüber).

**#739 — die richtige Frage.** Die Vorauswahl schlug **verbaute** Stücke vor. Kein
Zielkonflikt, sondern eine verwechselte Eigenschaft: der Katalog führt seit jeher zwei
getrennte Antworten, und die Auswahl las die falsche.

    «Gibt es einen Weg zurück?»   ``Status.terminal``   Verbaut: **ja**  → greifbar
    «Liegt es im Regal?»          ``Status.stock``      Verbaut: **nein** → kein FIFO
    «Hat es sein Ziel erreicht?»  ``Status.tone``       Verbaut: **grün**

**#740 — und sie skaliert.** Bei zehntausend Schrauben war eine flache Liste an drei
Stellen falsch: die Vorauswahl kam aus einer gekappten Seite (sind die ersten Stücke
verbaut, findet sie **nichts**), die Zähler kamen aus derselben Seite, und die
Herkunfts-Map las **jede** offene Zugehörigkeit des Systems.

Gefahren wird über den **echten** Router-Pfad gegen echtes PostgreSQL – gegen SQLite wäre
die geprüfte Wahrheit eine andere.
"""

import os
import pathlib

import pytest
from sqlalchemy import event, text

from tests.runner import session
from tests.scenarios import World, free_stock

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _pg() -> None:
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("Diese Regeln gelten gegen echtes PostgreSQL – "
                    "DATABASE_URL setzen, damit sie wirklich laufen.")


def _choices(db, article_nr, **kw):
    """Der **echte** Router-Pfad – nicht die Dienst-Funktion darunter."""
    from app.routers import orders as R
    params = dict(article=article_nr, search=None, status=None, preselect=0,
                  limit=60, offset=0)
    params.update(kw)
    return R.unit_options(db=db, _=None, **params)


def _scene(w, *, quantity=6, built=0):
    """Ein Artikel mit ``quantity`` Stücken, davon die **ältesten** ``built`` verbaut."""
    from app.domain import statuses as st
    from app.models import Instance, InstanceUnit

    article, _numbers = free_stock(w, serialization="batch", quantity=quantity)
    units = (
        w.db.query(InstanceUnit)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .filter(Instance.article_id == article.id)
        .order_by(InstanceUnit.id)
        .all()
    )
    for u in units[:built]:
        u.status = st.VERBAUT
    w.db.flush()
    return article, units


def _numbers(db, units):
    from app.services import process as proc
    return [proc.unit_numbers(db, [u])[u.id] for u in units]


# ---------------------------------------------------------------------------
# #739 · Zwei Fragen, nicht eine
# ---------------------------------------------------------------------------

def test_the_picker_asks_two_questions_not_one():
    """**Greifbar und «liegt im Regal» sind zwei Eigenschaften.**

    Bug-Form: nur ``available`` (= ``is_selectable``) liefern. Dann ist ein verbautes
    Stück von einem freigegebenen nicht zu unterscheiden – und FIFO schlägt es vor.
    """
    _pg()
    from app.domain import statuses as st

    w = World(session())
    try:
        article, units = _scene(w, quantity=4, built=1)
        page = _choices(w.db, article.object_id)
        built = [u for u in page.units if u.status == st.VERBAUT][0]

        assert built.available is True, (
            "Ein verbautes Stück muss greifbar bleiben – das Greifen IST der Ausbau."
        )
        assert built.in_stock is False, (
            "…und es liegt trotzdem nicht im Regal: es steckt in einem anderen Stück. "
            "Genau diese zweite Antwort fehlte (#739)."
        )
        assert all(u.in_stock for u in page.units if u.status == st.FREIGEGEBEN)
    finally:
        w.db.rollback()
        w.db.close()


def test_fifo_never_proposes_a_piece_that_is_not_in_stock():
    """**Die Vorauswahl fragt «liegt es im Regal?».**

    Der gemeldete Fall: das **älteste** Stück ist verbaut, also nimmt FIFO es zuerst.
    Bug-Form: nach ``available`` filtern – dann steht es im Vorschlag.
    """
    _pg()
    w = World(session())
    try:
        article, units = _scene(w, quantity=6, built=1)
        page = _choices(w.db, article.object_id, preselect=3)
        gone = _numbers(w.db, units[:1])[0]

        assert gone not in page.preselect, (
            f"Das verbaute Stück steht im Vorschlag ({page.preselect}) – es müsste erst "
            f"ausgebaut werden."
        )
        assert page.preselect == _numbers(w.db, units[1:4]), (
            "Vorgeschlagen werden die ältesten Stücke, die im Regal liegen."
        )
        # …und es verschwindet nicht: sichtbar bleibt es, nur eben nicht vorgewählt.
        assert gone in [u.number for u in page.units]
    finally:
        w.db.rollback()
        w.db.close()


def test_the_in_stock_rule_lives_in_the_catalog():
    """**Die Regel gehört dem Statuskatalog, nicht dem Router.**

    Bug-Form: die Liste der «zählt zum Lager»-Zustände im Endpunkt ausschreiben. Dann
    gehört ein neuer Zustand ihr nicht automatisch an – und niemand merkt es.
    """
    from app.domain import statuses as st

    assert st.FREIGEGEBEN in st.IN_STOCK_UNIT_STATUSES
    assert st.GESPERRT in st.IN_STOCK_UNIT_STATUSES, (
        "Gesperrt liegt im Regal – es ist da, nur nicht verwendbar."
    )
    for gone in (st.VERBAUT, st.VERSCHROTTET):
        assert gone not in st.IN_STOCK_UNIT_STATUSES, (
            f"«{st.label(gone)}» zählt zur Historie und darf nie FIFO-Vorschlag sein."
        )
    assert st.IN_STOCK_UNIT_STATUSES == tuple(
        s.value for s in st.CATALOG
        if st.UNIT in s.axes and s.stock == st.LIVE and not s.terminal
    ), "Die Liste ist abgeleitet, nicht aufgezählt."

    router = (BACKEND / "app" / "routers" / "orders.py").read_text(encoding="utf-8")
    assert "IN_STOCK_UNIT_STATUSES" in router and "s.stock == st.LIVE" not in router, (
        "Der Router leitet die Liste wieder selbst ab – zwei Stellen für eine Regel."
    )


def test_a_bound_piece_is_selectable_but_never_preselected():
    """**Gebunden ist nicht frei.** Es zu nehmen ist eine Entscheidung, keine Vorgabe."""
    _pg()
    w = World(session())
    try:
        article, units = _scene(w, quantity=4)
        first = _numbers(w.db, units[:1])[0]
        w.release(lines=[{"article_object_id": article.object_id, "quantity": 1,
                          "origin": "lager",
                          "units": [{"number": first, "from_order": None}]}],
                  steps=[World.capture()])

        page = _choices(w.db, article.object_id, preselect=3)
        bound = [u for u in page.units if u.number == first][0]
        assert bound.available is True and bound.in_order is not None
        assert first not in page.preselect, (
            "Ein Stück aus einem laufenden Auftrag wurde vorgewählt – daraus würde still "
            "eine Abweichung, die einem anderen Auftrag sein Material entzieht."
        )
    finally:
        w.db.rollback()
        w.db.close()


# ---------------------------------------------------------------------------
# #740 · Eine Seite, und sie weiss, was sie nicht zeigt
# ---------------------------------------------------------------------------

def test_fifo_finds_free_pieces_beyond_the_first_page():
    """**Der eigentliche Skalierungsfehler.**

    40 Stücke, die ersten 35 verbaut, Seite = 10. Bug-Form: die Vorauswahl aus der
    geladenen Seite ziehen – dann sind alle zehn verbaut und die Oberfläche schlägt
    **nichts** vor, obwohl fünf freie da sind.
    """
    _pg()
    w = World(session())
    try:
        article, units = _scene(w, quantity=40, built=35)
        page = _choices(w.db, article.object_id, preselect=3, limit=10)

        assert len(page.units) == 10, "Die Seite ist begrenzt."
        assert page.preselect == _numbers(w.db, units[35:38]), (
            f"Die Vorauswahl findet nichts jenseits der ersten Seite ({page.preselect})."
        )
        assert page.total == 40, "Die Gesamtzahl kennt alles, nicht nur die Seite."
    finally:
        w.db.rollback()
        w.db.close()


def test_the_counters_come_from_the_whole_article_not_the_page():
    """**«Am Lager 60», wo fünfzigtausend liegen**, ist schlimmer als keine Zahl."""
    _pg()
    from app.domain import statuses as st

    w = World(session())
    try:
        article, _units = _scene(w, quantity=40, built=35)
        page = _choices(w.db, article.object_id, limit=5)

        counts = {s.status: s.quantity for s in page.states}
        assert counts == {st.FREIGEGEBEN: 5, st.VERBAUT: 35}, (
            f"Die Aufstellung kommt aus der Seite statt aus dem Artikel: {counts}"
        )
        assert sum(counts.values()) > len(page.units), (
            "Die Aufstellung muss mehr wissen als die Seite zeigt – sonst zählt sie sie."
        )
    finally:
        w.db.rollback()
        w.db.close()


def test_one_page_costs_a_handful_of_queries():
    """**Gezählt, nicht geschätzt.**

    Die Herkunfts-Map las **jede** offene Zugehörigkeit des Systems, um bei einer Seite
    nachzuschlagen – die schwerste Stelle des alten Endpunkts, und die einzige, die bei
    kleinen Datenmengen unauffällig bleibt. Sie fragt jetzt nach genau den Stücken, die
    auf der Seite stehen.
    """
    _pg()
    w = World(session())
    seen: list[str] = []

    def watch(conn, cursor, statement, *rest):
        seen.append(statement)

    try:
        article, _units = _scene(w, quantity=40, built=35)
        engine = w.db.get_bind()
        event.listen(engine, "before_cursor_execute", watch)
        try:
            _choices(w.db, article.object_id, preselect=3)
        finally:
            event.remove(engine, "before_cursor_execute", watch)

        assert seen, "Es wurde gar nichts gemessen – der Zähler hängt nicht."
        assert len(seen) <= 6, (
            f"Eine Seite kostet {len(seen)} Abfragen – erwartet sind höchstens sechs "
            f"(Aufstellung · Gesamtzahl · Seite · Herkunft · Vorauswahl)."
        )
        # **Genau die Herkunfts-Abfrage**, nicht irgendeine über ``order_units``: die
        # Vorauswahl fragt dieselbe Tabelle und trägt ohnehin ein ``NOT IN`` – ein
        # Wächter, der nur nach «IN» sucht, wäre davon schon zufrieden (gemessen: er war
        # es, und liess die Bug-Form durch).
        holder = [q for q in seen if "order_units" in q and " orders " in q.lower()]
        assert holder, "Die Herkunft wird gar nicht mehr gefragt."
        assert all("instance_unit_id IN (" in q for q in holder), (
            "Die Herkunfts-Map liest wieder alle offenen Zugehörigkeiten des Systems "
            "statt nur die Stücke dieser Seite:\n  "
            + "\n  ".join(q.replace("\n", " ")[:160] for q in holder)
        )
    finally:
        w.db.rollback()
        w.db.close()


def test_the_page_can_be_searched_and_filtered():
    """**Suchen und blättern statt scrollen** – bei zehntausend Stücken die einzige Form."""
    _pg()
    from app.domain import statuses as st
    from app.models import Instance

    w = World(session())
    try:
        article, units = _scene(w, quantity=12, built=8)
        inst = w.db.query(Instance).filter(Instance.article_id == article.id).first()

        by_number = _choices(w.db, article.object_id, search=str(inst.object_id)[-4:])
        assert by_number.total == 12, "Die Instanznummer trifft alle ihre Stücke."

        # **Die Trennung IST die Aussage**: «-9» meint den Suffix, nicht «irgendwo eine 9».
        by_suffix = _choices(w.db, article.object_id, search="-9")
        assert by_suffix.total == 1, f"«-9» trifft genau ein Stück ({by_suffix.total})."

        full = _choices(w.db, article.object_id, search=f"{inst.object_id}-9")
        assert full.total == 1, f"Die volle Stücknummer trifft eines ({full.total})."

        only_built = _choices(w.db, article.object_id, status=[st.VERBAUT])
        assert only_built.total == 8
        assert all(u.status == st.VERBAUT for u in only_built.units)

        page2 = _choices(w.db, article.object_id, limit=5, offset=5)
        assert len(page2.units) == 5 and page2.total == 12
    finally:
        w.db.rollback()
        w.db.close()


def test_the_index_for_the_preselect_is_in_migration_and_in_the_net():
    """**Ein Index ist erst fertig, wenn er an beiden Stellen steht** (Lehre aus 090).

    Die Migration ist die Wahrheit, das Lifespan-Netz der zweite Weg – und beim Ausfall
    zählt nur der zweite.
    """
    name = "ix_instance_units_instance_status"
    migration = (BACKEND / "alembic" / "versions" / "113_die_auswahl_blaettert.py")
    assert migration.exists(), "Migration 113 fehlt."
    src = migration.read_text(encoding="utf-8")
    assert name in src and "IF NOT EXISTS" in src, (
        "Der Index fehlt oder ist nicht idempotent – ein Deploy, bei dem das Netz zuerst "
        "griff, liefe sonst auf «existiert bereits» auf."
    )
    net = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    assert name in net, "Der Index steht nicht im Lifespan-Netz."
