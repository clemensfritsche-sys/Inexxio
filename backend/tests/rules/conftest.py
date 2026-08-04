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
                    step_kwargs: dict | None = None):
    """Eine Abweichung auf einen Anteil – über den echten Router-Pfad (Auswahl + Freigabe)."""
    from app.models import ArticleProcessStep, Order
    from app.routers import orders as R
    from app.schemas.order import InstancePick

    dev = Order(object_id=None, article_id=parent.article_id, quantity=Decimal(qty),
                status="draft")
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
    R._do_release(db, dev, {str(parent.object_id): "wait"}, user.id)
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
    """Baut die Lage EINER Regel-Zeile und liefert den Auftrag, der geprüft wird."""
    user, art = world
    if r.art == "regular":
        order, inst = _make_order(db, art, user, 4)
        if r.rest == "teil":
            # Ein Stück geht über eine Abweichung verloren (der übliche Weg).
            dev = _make_deviation(db, order, inst, user, 1, steps=("scrap",))
            _scrap(db, dev, inst, user, 1)
        elif r.rest == "nichts":
            _make_deviation(db, order, inst, user, 4)      # läuft weiter, hält alles
        return order
    # festes Subjekt: eine Abweichung, die selbst etwas verliert
    parent, inst = _make_order(db, art, user, 4)
    if r.rest == "nichts":
        dev = _make_deviation(db, parent, inst, user, 1)
        _make_deviation(db, dev, inst, user, 1)            # nimmt ihr das einzige Stück
        return dev
    dev = _make_deviation(db, parent, inst, user, 4)
    if r.rest == "teil":
        sub = _make_deviation(db, dev, inst, user, 1, steps=("scrap",))
        _scrap(db, sub, inst, user, 1)
    return dev


