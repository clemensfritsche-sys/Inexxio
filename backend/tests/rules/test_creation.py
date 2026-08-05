"""**Instanzen entstehen ausschliesslich aus dem Prozess des Artikels** (Testnotiz #622).

Der gemeldete Fall war schwerwiegend: ein regulärer Auftrag, im Bedarf ausdrücklich
**«Ab Lager»** (FIFO, 2 Stück), mit einem eigenen Ablauf aus «Datenerfassung + Beschaffen».
Die Freigabe legte **zwei neue Instanzen** an, statt vorhandene zu binden – aus dem Nichts
entstand Bestand, den niemand hergestellt hatte.

Die Ursache war eine **zweite Aussage über dieselbe Sache**: jeder Schritttyp deklarierte
zusätzlich eine «Subjekt-Rolle», und ein Beschaffungs-Schritt trug ``produce``. Über die
Vorrangordnung ``stock ≻ produce ≻ instance`` gewann er gegen die Wahl des Menschen – die
unsichtbare Ableitung schlug die sichtbare Eingabe.

Die Regel hat heute genau EINE Bedingung: *hat der Auftrag einen eigenen Ablauf?*

    eigener Ablauf   → ``stock``    er greift auf vorhandenen Bestand zu, er erzeugt nie.
                                    Was fehlt, ist eine **Unterdeckung** (sichtbar, mit
                                    Nachschub-Unter-Auftrag) – nicht stille Erzeugung.
    kein Ablauf      → ``produce``  er fährt den Prozess des ARTIKELS, und nur DER erzeugt.

Diese Datei prüft die **Wirkung** über die echten Dienst-Pfade – und zwar für JEDEN
Schritttyp einzeln, weil die alte Regel ja gerade typ-abhängig war.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from .conftest import _make_order, _num


def _stocked_article(db, user, qty: int = 10):
    """Ein freigegebener Artikel mit **freiem Bestand** am Lager."""
    from app.models import Article, ArticleProcessStep

    art = Article(object_id=_num(db), name=f"Zange {_num(db)}", unit="pcs",
                  serialization="batch", status="released")
    db.add(art)
    db.flush()
    db.add(ArticleProcessStep(article_id=art.id, step_type="inspection", position=0,
                              sample_percent=100))
    db.flush()
    _, inst = _make_order(db, art, user, qty)
    inst.quality, inst.disposition = "passed", "in_stock"
    inst.released_at = datetime.now(timezone.utc)
    inst.reserved_quantity, inst.reservations = Decimal(0), None
    db.commit()
    return art, inst


def _order_with_own_steps(db, art, user, qty: int, *steps: str):
    """Ein regulärer Auftrag «Ab Lager» mit einem EIGENEN Ablauf – über den Router-Pfad."""
    from app.models import ArticleProcessStep, Order
    from app.routers import orders as R

    order = Order(object_id=_num(db), article_id=art.id, quantity=Decimal(qty),
                  status="draft")
    db.add(order)
    db.flush()
    for pos, kind in enumerate(steps):
        db.add(ArticleProcessStep(
            order_id=order.id, step_type=kind, position=pos,
            **({"mode": "scrap"} if kind in ("scrap", "block") else
               {"sample_percent": 100} if kind == "inspection" else
               {"mode": "webshop", "webshop_url": "https://example.test"} if kind == "purchase" else
               # Ein Ressourcen-Schritt ohne Zeile hat nichts zu holen und lässt sich
               # seit Testnotiz #635 nicht mehr freigeben – hier zählt der Subjekt-Typ,
               # also bekommt er eine (als Betriebsmittel, das nichts verbraucht).
               {"resource_lines": [{"article_id": art.id, "quantity": 1, "mode": "tool"}]}
               if kind == "resource" else {})))
    db.flush()
    R._do_release(db, order, user.id)
    db.commit()
    db.refresh(order)
    return order


def _created_by(db, order):
    from app.models import Instance
    return db.query(Instance).filter(Instance.order_id == order.id).all()


def test_the_reported_case_binds_stock_instead_of_creating_it(db, world):
    """Der gemeldete Fall: «Ab Lager» + eigener Ablauf «Datenerfassung + Beschaffen»."""
    from app.services.subject import order_instances, subject_kind

    user, _ = world
    art, stock = _stocked_article(db, user, 10)
    order = _order_with_own_steps(db, art, user, 2, "inspection", "purchase")

    assert subject_kind(db, order) == "stock", (
        "Ein Auftrag mit eigenem Ablauf greift zu – die Rolle seiner Schritte entscheidet "
        "das nicht mehr (ein Beschaffungs-Schritt trug früher `produce` und schlug damit "
        "die ausdrückliche Wahl «Ab Lager»).")
    assert _created_by(db, order) == [], (
        "Kein Stück darf hier entstehen: Instanzen kommen ausschliesslich aus dem Prozess "
        "des Artikels.")
    subjects = order_instances(db, order)
    assert [i.id for i in subjects] == [stock.id], (
        "Stattdessen bindet er den vorhandenen Bestand (FIFO).")


@pytest.mark.parametrize("kind", ["purchase", "resource", "document", "inspection",
                                  "movement", "scrap", "block", "sale"])
def test_no_step_type_turns_an_order_into_a_producer(db, world, kind):
    """**Für JEDEN Schritttyp** – die alte Regel war typ-abhängig, die neue ist es nicht.

    Beschaffung, Ressource und Dokument trugen ``produce``; genau sie kippten einen
    Bestands-Auftrag still in eine Erzeugung."""
    from app.services.subject import subject_kind

    user, _ = world
    art, _stock = _stocked_article(db, user, 10)
    order = _order_with_own_steps(db, art, user, 1, kind)

    assert subject_kind(db, order) == "stock", f"«{kind}» am Auftrag ist ein Zugriff, keine Erzeugung."
    assert _created_by(db, order) == [], f"«{kind}» am Auftrag darf keine Instanz erzeugen."


def test_without_own_steps_the_article_process_creates(db, world):
    """Die Gegenprobe – sonst hiesse «nichts erzeugt» nur «nichts funktioniert»."""
    from app.services.subject import subject_kind

    user, _ = world
    art, _stock = _stocked_article(db, user, 10)
    order, inst = _make_order(db, art, user, 3)

    assert subject_kind(db, order) == "produce"
    assert [i.id for i in _created_by(db, order)] == [inst.id], (
        "Ohne eigenen Ablauf fährt der Auftrag den Prozess des Artikels – und DER erzeugt.")
    assert inst.quantity == Decimal(3)


def test_the_creation_itself_refuses_an_order_with_its_own_flow(db, world):
    """Der zweite Riegel: die Erzeugung prüft es selbst.

    Ein Wächter allein an der Ableitung liesse jeden künftigen zweiten Aufrufer durch –
    und genau ein solcher Pfad hat den gemeldeten Schaden angerichtet."""
    from fastapi import HTTPException

    from app.services import serialization

    user, _ = world
    art, _stock = _stocked_article(db, user, 10)
    order = _order_with_own_steps(db, art, user, 1, "inspection")

    with pytest.raises(HTTPException) as ex:
        serialization.create_instances_for_order(db, order, user.id)
    assert "eigenen Ablauf" in str(ex.value.detail)
    db.rollback()
