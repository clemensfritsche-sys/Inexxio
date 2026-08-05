"""**Ein Beleg gilt für die Menge, für die er ausgestellt wurde** (Testnotizen #587/#588).

Eine Tabelle wie die Unterdeckungs-Regel daneben, für die zweite Hälfte derselben Frage:
was geschieht mit der **Arbeit eines Moduls**, wenn ihm sein Material entzogen wird?

    Die Menge sinkt   → der Beleg fällt auf seine erste Stufe zurück («Angefragt»), und die
                        Zahlen, die die Vereinbarung ausdrücken, sind geräumt.
    Die Menge ist weg → der Beleg fällt auf seine letzte Stufe: **storniert**.
    Der Beleg ist durch → er bleibt. Vergangenheit wird nicht umgeschrieben.
    Der Typ hat keine Stufen → nichts passiert; seine Zeile IST die Handlung.

**Es ist EINE Regel mit zwei Enden**, kein zweiter Mechanismus – und die Stufen stehen in
der Registry, nicht im Code. Darum prüft diese Datei beides über **denselben** Weg: den
echten Dienst-Pfad, der auch die Menge kürzt.
"""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from .conftest import _make_deviation, _make_order, _num, _scrap


@dataclass(frozen=True)
class DocRule:
    id: str
    lage: str
    rest: str          # was dem Auftrag bleibt: teil | nichts-gekappt
    stufe: str         # Stand der Bestellung VOR dem Entzug
    erwartet: str      # Stand danach
    menge: str         # Menge des Belegs danach: 'neu' | 'unverändert'
    vereinbarung: str  # 'geräumt' | 'bleibt'
    warum: str


RULES: tuple[DocRule, ...] = (
    DocRule(
        id="beleg-menge-gesunken",
        lage="Auftrag über 4 Stück, Bestellung offeriert; 1 Stück wird verschrottet.",
        rest="teil", stufe="quoted", erwartet="requested", menge="neu",
        vereinbarung="geräumt",
        warum=(
            "Eine Offerte über 4 Stück ist keine über 3. Der Beleg fällt auf «Angefragt» "
            "zurück, damit die Vereinbarung neu getroffen wird – und die Bestellsumme wird "
            "geräumt, weil sie für die alte Menge galt. Bliebe sie stehen, sähe der "
            "Lieferant eine Summe für 4 Stück neben einer Menge von 3."
        ),
    ),
    DocRule(
        id="beleg-alles-weg",
        lage="Auftrag über 4 Stück, Bestellung offeriert; eine Abweichung nimmt alles und kappt.",
        rest="nichts-gekappt", stufe="quoted", erwartet="cancelled", menge="unverändert",
        vereinbarung="bleibt",
        warum=(
            "Der Auftrag ist damit abgebrochen – die Bestellung hat ihren Gegenstand "
            "verloren. Sie blieb bisher «Angefragt»/«Offeriert» stehen, und der Lieferant "
            "sah eine offene Anfrage für etwas, das es nicht mehr gibt (Testnotiz #587). "
            "«Storniert» ist dabei kein neues Wort: der Verkauf trägt es längst."
        ),
    ),
    DocRule(
        id="beleg-erledigt",
        lage="Auftrag über 4 Stück, Ware bereits eingetroffen; danach sinkt die Menge.",
        rest="teil", stufe="received", erwartet="received", menge="unverändert",
        vereinbarung="bleibt",
        warum=(
            "Eingetroffene Ware ist eingetroffen. Ein erledigter Schritt ist Vergangenheit, "
            "und die wird nicht umgeschrieben (ADR 007) – das ist dieselbe Grenze, an der "
            "auch die Fluss-Anzeige haltmacht."
        ),
    ),
)


def _supplier(db):
    from app.models import UserProfile
    u = UserProfile(firebase_uid=f"sup{_num(db)}", email=f"s{_num(db)}@test.ch",
                    role="supplier", object_id=_num(db))
    db.add(u)
    db.flush()
    return u


def _purchase_world(db, world):
    """Ein Artikel, dessen Prozess **beschafft und danach prüft** – plus ein Lieferant.

    Der zweite Schritt ist kein Beiwerk: ohne ihn wäre der Auftrag mit dem Wareneingang
    fertig, und an einen abgeschlossenen Auftrag kommt keine Abweichung mehr heran. Genau
    der interessante Fall – Ware ist da, DANACH passiert etwas – braucht also einen Prozess,
    der noch weitergeht."""
    from app.models import Article, ArticleProcessStep
    user, _ = world
    sup = _supplier(db)
    art = Article(object_id=_num(db), name=f"Kaufteil {_num(db)}", unit="pcs",
                  serialization="batch", status="released")
    db.add(art)
    db.flush()
    db.add(ArticleProcessStep(article_id=art.id, step_type="purchase", position=0,
                              mode="supplier", supplier_id=sup.id))
    db.add(ArticleProcessStep(article_id=art.id, step_type="inspection", position=1,
                              sample_percent=100))
    db.commit()
    return user, art


def _po(db, order):
    from app.models import PurchaseOrder
    return (db.query(PurchaseOrder)
            .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
            .first())


def _drive(db, po, order, user, target: str):
    """Die Bestellung über den ECHTEN Dienst-Pfad auf eine Stufe bringen."""
    from app.schemas.purchase_order import PurchaseOrderUpdate
    from app.services import purchase as P
    for step in ("quoted", "ordered", "received"):
        P.apply_update(db, po, PurchaseOrderUpdate(
            status=step, **({"order_total": Decimal("400")} if step == "quoted" else {})), user)
        db.commit()
        if step == target:
            return
    raise AssertionError(target)


@pytest.mark.parametrize("r", RULES, ids=lambda r: r.id)
def test_a_document_is_valid_for_the_quantity_it_was_issued_for(db, world, r: DocRule):
    user, art = _purchase_world(db, world)
    order, inst = _make_order(db, art, user, 4)
    po = _po(db, order)
    assert po is not None and po.quantity == Decimal(4), "Der Beleg entsteht mit dem Soll."
    _drive(db, po, order, user, r.stufe)
    before_total = po.order_total

    if r.rest == "teil":
        dev = _make_deviation(db, order, inst, user, 1, steps=("scrap",))
        _scrap(db, dev, inst, user, 1)
    else:
        _make_deviation(db, order, inst, user, 4, steps=("scrap",), cut=True)
    db.refresh(po)
    db.refresh(order)

    assert po.status == r.erwartet, f"{r.id}: {r.warum}"
    if r.menge == "neu":
        assert po.quantity == Decimal(3), (
            "Die Menge wird nachgezogen – sonst stünde der Beleg beim nächsten Durchlauf "
            "wieder auf einer fremden Grundlage und fiele endlos zurück.")
    else:
        assert po.quantity == Decimal(4)
    if r.vereinbarung == "geräumt":
        assert po.order_total is None, "Die Bestellsumme galt für die alte Menge."
    else:
        assert po.order_total == before_total


def test_up_to_the_promise_the_system_decides_from_then_on_the_human_does(db, world):
    """**Ab «Bestellt» ist der Lieferant gebunden** (Testnotiz #587 / Entscheid des Nutzers).

    Bis dahin ist der Beleg nur unsere Absicht – das System zieht ihn selbst nach. Ab dort
    ist er eine Zusage: die Ware ist in aller Regel unterwegs, und man widerruft sie nicht
    einseitig, so wenig wie eine Internet-Bestellung eine Sekunde später. Es gibt aber die
    Ausnahme, die es in der Realität gibt: man ruft den Lieferanten an. Also fasst das System
    den Beleg nicht an, **meldet** die Abweichung und wartet auf die Bestätigung – und dann
    läuft dieselbe Änderung wie sonst automatisch.

    «Bleibt wie bestellt» ist bewusst KEINE Option: eine Überlieferung ist ein Fall, den man
    klärt, kein Zustand, den man wegklickt."""
    from app.services import rebase

    user, art = _purchase_world(db, world)
    order, inst = _make_order(db, art, user, 4)
    po = _po(db, order)
    _drive(db, po, order, user, "ordered")
    assert po.order_total is not None

    dev = _make_deviation(db, order, inst, user, 1, steps=("scrap",))
    _scrap(db, dev, inst, user, 1)
    db.refresh(po)
    db.refresh(order)

    assert order.quantity == Decimal(3), "Der Auftrag selbst kürzt sich wie immer."
    assert po.status == "ordered" and po.quantity == Decimal(4), (
        "Die Bestellung bleibt unangetastet – der Lieferant hat zugesagt.")
    open_points = rebase.clarifications(db, order, "purchase")
    assert open_points[art.id].ordered == Decimal(4)
    assert open_points[art.id].needed == Decimal(3), (
        "Und was zu klären ist, steht da: bestellt 4 · gebraucht 3.")

    # «Lieferant hat zugestimmt» – derselbe ``_apply`` wie die Automatik, anderer Auslöser.
    rebase.apply_clarified(db, order, "purchase", po, user.id)
    db.commit()
    db.refresh(po)
    assert po.status == "requested" and po.quantity == Decimal(3), (
        "Jetzt gilt die neue Grundlage – und die Vereinbarung wird neu getroffen.")
    assert po.order_total is None, "Die Bestellsumme galt für 4 Stück."
    assert not rebase.clarifications(db, order, "purchase"), (
        "Die Klärung ist abgeleitet – sie verschwindet, sobald jemand gehandelt hat.")


def test_a_binding_document_of_a_dead_order_is_still_only_clarified(db, world):
    """Auch der Abbruch hebt eine Zusage nicht auf: die Bestellung bleibt «Bestellt» und
    wird als Klärung gemeldet («gebraucht: nichts mehr»). Erst die Bestätigung storniert
    sie – dann aber auf die letzte Stufe, nicht auf die erste."""
    from app.services import rebase

    user, art = _purchase_world(db, world)
    order, inst = _make_order(db, art, user, 4)
    po = _po(db, order)
    _drive(db, po, order, user, "ordered")
    _make_deviation(db, order, inst, user, 4, steps=("scrap",), cut=True)
    db.refresh(po)
    db.refresh(order)

    assert order.status == "inactive", "Der Auftrag ist abgebrochen…"
    assert po.status == "ordered", "…die Zusage an den Lieferanten bleibt trotzdem stehen."
    assert rebase.clarifications(db, order, "purchase")[art.id].needed == Decimal(0)

    rebase.apply_clarified(db, order, "purchase", po, user.id)
    db.commit()
    db.refresh(po)
    assert po.status == "cancelled", "Der Auftrag braucht nichts mehr – also storniert."


def test_a_module_without_stages_is_untouched(db, world):
    """**Wer keine Stufen hat, ist nicht ausgenommen – er hat schlicht nichts zurückzunehmen.**

    Bewegung, Ressource und Aussondern schreiben ihre Zeile erst, wenn die Handlung geschehen
    ist. Sie ist damit Vergangenheit. Die Regel gilt für alle Module; dass sie hier nichts
    tut, ist ihr Ergebnis, keine Ausnahme."""
    from app.domain import event_types
    from app.services.rebase import STAGED

    for key in ("movement", "resource", "scrap", "block", "inspection", "document"):
        assert key not in STAGED, (
            f"«{event_types.label(key)}» hat keine Stufen – ein Reset wäre eine erfundene "
            f"Rückabwicklung.")
    assert set(STAGED) == {"purchase", "sale"}, (
        "Wer Stufen deklariert, bekommt die Regel geschenkt – die Liste wird nicht gepflegt.")


def test_the_two_ends_are_one_function(db, world):
    """**«Menge reduzieren» und «alles entzogen» sind derselbe Vorgang.**

    Der Nutzer hat ausdrücklich nach der Vereinheitlichung gefragt. Sie steht nicht in einer
    Absicht, sondern in der Form: EINE Funktion ohne Modus-Parameter, die am Auftrag abliest,
    welches Ende gilt – und zwei Stufen, die in der Registry stehen."""
    import inspect

    from app.services import rebase

    src = inspect.getsource(rebase.rebase_documents)
    assert "voided" not in inspect.signature(rebase.rebase_documents).parameters, (
        "Kein Modus-Parameter – der Aufrufer sagt nicht, welches Ende gilt.")
    assert "_stage_of(order, et)" in src, "Die Stufe wird abgeleitet, nicht übergeben."
    stage = inspect.getsource(rebase._stage_of)
    assert 'et.reset if (order.status or "") == "released" else et.voided' in stage, (
        "Genau hier – und nur hier – unterscheiden sich die beiden Enden.")
