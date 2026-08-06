"""Ein **echtes PostgreSQL** für die Regel-Tabelle – oder eine ehrliche Übersprung-Meldung.

Die Regeln lassen sich nicht gegen SQLite prüfen: das ERP rechnet mit JSONB-Ansprüchen
(``instances.reservations``), ``has_key``-Filtern und Zeilensperren. Ein Ersatz-Backend
würde eine Wahrheit prüfen, die es nicht gibt.

Darum: liegt eine PostgreSQL-URL vor (``RULES_DATABASE_URL`` oder ``DATABASE_URL``), läuft
die Tabelle gegen die echten Dienste; sonst überspringt sie **mit Grund**. In der CI ist
die Datenbank da (der Postgres-Service baut ohnehin das Schema auf), also läuft sie dort
bei jedem Push – genau dann, wenn es zählt.
"""

import os
from decimal import Decimal

import pytest

from .table import Rule

_URL = os.environ.get("RULES_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
_IS_PG = _URL.startswith("postgres")
if _IS_PG:
    # Die App liest ihre URL beim Import aus den Settings – also VOR dem ersten Import
    # setzen, sonst verbindet sie sich gegen den Default (localhost:5432).
    os.environ["DATABASE_URL"] = _URL


@pytest.fixture(scope="session")
def db():
    """Frisches Schema, eine Session – die Regel-Tabelle baut ihre Lagen selbst auf."""
    if not _IS_PG:
        pytest.skip("Regel-Tabelle braucht echtes PostgreSQL "
                    "(RULES_DATABASE_URL/DATABASE_URL setzen) – lokal übersprungen.")
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    from sqlalchemy import text

    from app.core.database import Base, SessionLocal, engine
    from app import models  # noqa: F401  – registriert alle Tabellen

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS object_id_seq START 100000001"))
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ─── Bausteine einer Lage – EINE Stelle, von allen Regel-Tests benutzt ─────────

def _num(db):
    from app.services.objects import next_object_id
    return next_object_id(db)


@pytest.fixture(scope="session")
def world(db):
    """Ein Benutzer und ein freigegebener Artikel mit einem Prozessschritt."""
    from app.models import Article, ArticleProcessStep, UserProfile

    user = UserProfile(firebase_uid="rules", email="rules@test.ch", role="admin",
                       object_id=_num(db))
    db.add(user)
    db.flush()
    art = Article(object_id=_num(db), name="Prüfstück", unit="pcs",
                  serialization="batch", status="released")
    db.add(art)
    db.flush()
    db.add(ArticleProcessStep(article_id=art.id, step_type="inspection", position=0,
                              sample_percent=100))
    db.commit()
    return user, art


def _make_order(db, art, user, qty: int):
    """Ein regulärer Erzeugungsauftrag – über den EINEN Freigabe-Pfad."""
    from app.models import Instance, Order
    from app.services.orders import release_order

    order = Order(object_id=_num(db), article_id=art.id, quantity=Decimal(qty),
                  status="draft")
    db.add(order)
    db.flush()
    release_order(db, order, user.id)
    db.commit()
    inst = (db.query(Instance).filter(Instance.order_id == order.id)
            .order_by(Instance.id.desc()).first())
    return order, inst


def _make_deviation(db, parent, inst, user, qty: int, *, steps=("inspection",),
                    step_kwargs: dict | None = None, cut: bool = False):
    """Eine Abweichung auf einen Anteil – über den echten Router-Pfad (Auswahl + Freigabe).

    ``cut`` = «die Rückführung ist gekappt» (Testnotiz #563)."""
    from app.models import ArticleProcessStep, Order
    from app.routers import orders as R
    from app.schemas.order import InstancePick

    dev = Order(object_id=None, article_id=parent.article_id, quantity=Decimal(qty),
                status="draft", returns_nothing=cut)
    db.add(dev)
    db.flush()
    R._set_chosen_instances(db, dev, [InstancePick(
        instance_object_id=inst.object_id, quantity=qty,
        from_order_object_id=parent.object_id)])
    for pos, kind in enumerate(steps):
        db.add(ArticleProcessStep(order_id=dev.id, step_type=kind, position=pos,
                                  **(step_kwargs or {}),
                                  **({"mode": "scrap"} if kind == "scrap" else
                                     {"sample_percent": 100} if kind == "inspection" else {})))
    db.flush()
    R._do_release(db, dev, user.id)
    db.commit()
    db.refresh(dev)
    return dev


def _scrap(db, order, inst, user, qty: int):
    """Verschrotten über den Fachdienst – inklusive aller Buchungen und Freigaben."""
    from app.models import ArticleProcessStep
    from app.schemas.disposal import ScrapUpdate
    from app.services import scrap as scrap_svc

    step = (db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.order_id == order.id,
                    ArticleProcessStep.step_type == "scrap").first())
    scrap_svc.record_scrap(db, order, ScrapUpdate(
        items=[{"instance_id": inst.object_id, "quantity": qty}],
        note="Regel-Tabelle", step_id=step.id), user.id)
    db.commit()


def _situation(db, world, r: Rule):
    """Baut die Lage EINER Regel-Zeile.

    Liefert den geprüften Auftrag **und die Menge, auf die er eröffnet wurde** – ohne sie
    liesse sich «gekürzt» nicht von «war schon immer so» unterscheiden, und genau das ist
    seit der automatischen Entscheidung die eigentliche Konsequenz (#556)."""
    user, art = world
    if r.art == "regular":
        order, inst = _make_order(db, art, user, 4)
        if r.rest == "teil":
            # Ein Stück geht über eine Abweichung verloren (der übliche Weg).
            dev = _make_deviation(db, order, inst, user, 1, steps=("scrap",))
            _scrap(db, dev, inst, user, 1)
        elif r.rest == "nichts":
            _make_deviation(db, order, inst, user, 4)      # läuft weiter, hält alles
        elif r.rest == "gekappt":
            # Alles weg UND die Rückführung gekappt – er endet hier (#563).
            _make_deviation(db, order, inst, user, 4, cut=True)
        elif r.rest == "teil-gekappt":
            # Nur 1 Stück gekappt: er behält 3 und läuft damit weiter.
            _make_deviation(db, order, inst, user, 1, cut=True)
        elif r.rest == "nie-gedeckt":
            # **Ab Lager mehr verlangt, als es gibt** (#649): der Bestand des Artikels wird
            # freigegeben (1 Stück), der Auftrag will 2. Bei der Freigabe wird die Zusage
            # auf das Machbare festgelegt – sonst ruhte er für immer.
            return _stock_order(db, art, user, want=2), 2
        elif r.rest == "kaskade":
            # Die Abweichung gäbe noch zurück; erst IHRE Abweichung kappt – und das
            # schlägt über sie hinweg bis nach oben durch.
            dev = _make_deviation(db, order, inst, user, 4)
            _make_deviation(db, dev, inst, user, 4, cut=True)
        return order, 4
    # festes Subjekt: eine Abweichung, die selbst etwas verliert
    parent, inst = _make_order(db, art, user, 4)
    if r.rest == "erledigt":
        # Sie steuert ihr Stück SELBST aus – das ist ihre Erledigung, kein Verlust (#555).
        dev = _make_deviation(db, parent, inst, user, 1, steps=("scrap",))
        _scrap(db, dev, inst, user, 1)
        return dev, 1
    if r.rest == "nichts":
        dev = _make_deviation(db, parent, inst, user, 1)
        _make_deviation(db, dev, inst, user, 1)            # nimmt ihr das einzige Stück
        return dev, 1
    dev = _make_deviation(db, parent, inst, user, 4)
    if r.rest == "teil":
        sub = _make_deviation(db, dev, inst, user, 1, steps=("scrap",))
        _scrap(db, sub, inst, user, 1)
    return dev, 4




def _stock_order(db, art, user, *, want: int):
    """Ein Auftrag **ab Lager** über ``want`` Stück – mit weniger Bestand, als er verlangt.

    Gebaut wie im Betrieb: ein Erzeugungsauftrag über EIN Stück läuft durch (Datenerfassung
    → freigegeben, am Lager), danach greift ein Auftrag mit **eigenem Ablauf** über ``want``
    Stück per FIFO zu (``subject_kind == 'stock'`` – ein eigener Ablauf erzeugt nie)."""
    from app.models import ArticleProcessStep, Order
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc, process
    from app.services.orders import release_order

    made, inst = _make_order(db, art, user, 1)
    step = process.order_step_defs(db, made)[0]
    insp_svc.record_inspection(db, made, InspectionUpdate(
        step_id=step.id,
        samples=[InspectionSample(instance_id=inst.object_id, slot=1, values={"_ok": True})]),
        user)
    db.commit()

    order = Order(object_id=_num(db), article_id=art.id, quantity=Decimal(want),
                  status="draft")
    db.add(order)
    db.flush()
    db.add(ArticleProcessStep(order_id=order.id, step_type="movement", position=0))
    db.flush()
    release_order(db, order, user.id)
    db.commit()
    db.refresh(order)
    return order
