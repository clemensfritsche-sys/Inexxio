"""**Verfügbarkeit ist eine MENGE – und es gibt genau eine Antwort darauf** (Testnotiz #647).

Gemeldet: ein Auftrag über 4 Stück «Ab Lager» meldete «nicht genügend Material», während der
Bestand-Reiter desselben Artikels reichlich zeigte. Zwei Ursachen, beide von derselben Art –
*es wurde über Datensätze geredet, wo Mengen gemeint waren*:

1. **Der Pool war gekappt.** Die Auswahl lud «die 500 neuesten Instanzen» über ALLE Artikel.
   Sobald mehr als 500 jüngere Instanzen existierten, war vom Bestand des gesuchten Artikels
   nichts dabei – die Oberfläche rechnete korrekt, nur über der leeren Menge.
2. **«Frei» war ein Zustand des Datensatzes.** Sie prüfte `quality == passed`,
   `disposition == in_stock` und den **denormalisierten** Reservierungs-Zeiger. Der ist eine
   Anzeige-Hilfe («wer hält das?»), kein Mengenwert: eine Charge à 500, von der EIN Stück für
   einen anderen Auftrag reserviert war, galt damit als vollständig belegt.

Die Regel dagegen ist eine Zeile: **was die Oberfläche als verfügbar zeigt, muss dasselbe
sein, was die FIFO-Allokation nehmen würde.** Beide lesen jetzt `inventory.ready_qty`.
"""

from decimal import Decimal


def _release_stock(db, art, user, qty):
    """Eine freigegebene Charge dieses Artikels erzeugen – über den echten Freigabe-Pfad."""
    from .conftest import _make_order
    from app.services import process
    from app.schemas.inspection import InspectionSample, InspectionUpdate
    from app.services import inspection as insp_svc, subject

    order, inst = _make_order(db, art, user, qty)
    step = process.order_step_defs(db, order)[0]
    insp_svc.record_inspection(db, order, InspectionUpdate(
        step_id=step.id,
        samples=[InspectionSample(instance_id=inst.object_id, slot=i + 1, values={"_ok": True})
                 for i in range(int(qty))]), user)
    db.commit()
    db.refresh(inst)
    assert subject.order_instances(db, order)          # existiert
    return inst


def test_the_surface_shows_the_quantity_fifo_would_take(db, world):
    """**Eine Frage, eine Antwort**: die Summe der angezeigten Verfügbarkeiten IST das,
    was die Allokation findet.

    Geprüft über die echten Pfade: der Endpunkt des Bestand-Reiters (``denorm``) und
    ``inventory.available`` – die Grösse, mit der die Freigabe rechnet."""
    from app.routers.instances import denorm
    from app.models import Instance
    from app.services import inventory
    from app.services.reservation import claim

    user, _ = world
    from .test_units import _art
    art = _art(db, "Verfügbar")
    a = _release_stock(db, art, user, 5)
    b = _release_stock(db, art, user, 5)

    rows = db.query(Instance).filter(Instance.article_id == art.id).all()
    shown = sum(r.available_quantity for r in denorm(db, rows))
    assert shown == float(inventory.available(db, art.id)) == 10.0, shown

    # **Ein Stück reserviert – neun bleiben.** Vorher galt die ganze Charge als belegt, weil
    # der Datensatz einen Reservierungs-Zeiger trug: aus 10 wurden 5.
    claim(a, 999_999, Decimal(1))
    db.commit()
    rows = db.query(Instance).filter(Instance.article_id == art.id).all()
    shown = sum(r.available_quantity for r in denorm(db, rows))
    assert shown == float(inventory.available(db, art.id)) == 9.0, (
        f"Reserviert ist EIN Stück, nicht die Charge (angezeigt {shown}, "
        f"Skalar-Zeiger: {a.reserved_for_order_id})")
    assert a.reserved_for_order_id is not None, (
        "Der Zeiger steht – genau darum darf die Oberfläche ihn nicht als «alles belegt» lesen.")

    # Und ein gesperrtes bzw. noch nicht freigegebenes Stück zählt nie mit (je Stück).
    from app.services import units
    units.mark_blocked(b, [1])
    db.commit()
    rows = db.query(Instance).filter(Instance.article_id == art.id).all()
    assert sum(r.available_quantity for r in denorm(db, rows)) == float(
        inventory.available(db, art.id)) == 8.0


def test_the_pick_pool_is_not_capped_by_age(db, world):
    """**Der Bestand eines Artikels hört nicht bei den 500 neuesten Objektnummern auf.**

    Genau das war der gemeldete Fehler: der Endpunkt, den die Auswahl las, war der
    **globale** Instanz-Feed mit Obergrenze – der Bestand-Reiter dagegen liest den Artikel.
    Beide müssen dieselbe Menge sehen, sonst sagt eine Ansicht «leer» und die andere «voll»."""
    from app.models import Instance

    user, _ = world
    from .test_units import _art
    art = _art(db, "Kappung")
    _release_stock(db, art, user, 3)
    # Danach entstehen viele jüngere Instanzen anderer Artikel …
    other = _art(db, "Jünger")
    for _ in range(5):
        _release_stock(db, other, user, 1)

    per_article = db.query(Instance).filter(Instance.article_id == art.id).all()
    newest_first = (db.query(Instance).order_by(Instance.object_id.desc()).limit(3).all())
    assert per_article, "Der Artikel hat Bestand …"
    assert not any(i.article_id == art.id for i in newest_first), (
        "… und er liegt NICHT unter den jüngsten Objektnummern – genau darum darf die "
        "Auswahl nicht über den gekappten Gesamt-Feed laden.")


def test_every_surface_names_the_same_free_stock(db, world):
    """**«Wie viel ist frei?» hat EINE Antwort – auch für die KI.**

    Das Werkzeug «Bestand» rechnete mit einem SQL-Aggregat
    (``sum(quantity − reserved_quantity)``). Dieselbe Frage, andere Antwort: seit der
    Instanz-Zustand die Projektion über die Stücke ist (#604), kann eine Charge «am Lager»
    stehen und trotzdem Stücke enthalten, die im Prozess oder gesperrt sind – das Aggregat
    zählte sie als frei, die Allokation nimmt sie nicht. Die KI hätte damit einem Menschen
    eine Zahl genannt, die das ERP nirgends zeigt."""
    from app.models import Instance
    from app.routers.instances import denorm
    from app.services import inventory, units
    from app.services.ai import tools as ai

    user, _ = world
    from .test_units import _art
    art = _art(db, "KI-Bestand")
    inst = _release_stock(db, art, user, 4)
    units.mark_blocked(inst, [1])          # ein Stück gesperrt → 3 frei
    db.commit()

    truth = float(inventory.available(db, art.id))
    assert truth == 3.0, truth
    rows = db.query(Instance).filter(Instance.article_id == art.id).all()
    assert sum(r.available_quantity for r in denorm(db, rows)) == truth

    p = ai.AiPrincipal(actor=user, on_behalf_of=user)
    detail = ai._t_get_article(db, p, {"object_id": art.object_id})
    listing = ai._t_inventory(db, p, {"article_object_id": art.object_id})
    assert float(detail["free_stock"]) == truth, detail["free_stock"]
    assert listing and float(listing[0]["free_stock"]) == truth, listing
