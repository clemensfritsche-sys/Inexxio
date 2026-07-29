"""Unterdeckung: **eine Frage, drei Antworten.**

Ein Auftrag ist unterdeckt, wenn sein Soll nicht (mehr) gesichert ist – weil eine
reservierte Instanz ausgesteuert wurde, weil ein Erzeugungsauftrag Ausschuss hatte oder
weil ein Stück gerade in einer offenen **Abweichung** in Klärung ist. Der betroffene
Subjekt-Schritt ist dann «blockiert» (abgeleitet aus dem Bestand, kein stilles
Unterliefern).

Der Mensch beantwortet genau EINE Frage – *was soll mit der Fehlmenge geschehen?* – und es
gibt drei ehrliche Antworten:

1. **Wartet** – kein Knopf, sondern ein **Zustand**: ist die Fehlmenge bereits in einer
   offenen Abweichung oder einem laufenden Nachschub gebunden, ist die Entscheidung längst
   getroffen. Das System sagt nur, worauf gewartet wird (``orders._fill_step_shortfall``).
2. **Ersetzen** (``cover_shortfall``) – EIN Weg statt zweier: was am Lager frei ist, wird
   FIFO reserviert (oder gezielt gewählte Instanzen), und was danach offen bleibt, deckt ein
   **Nachschub**-Unter-Auftrag. Ob produziert oder ab Lager genommen wird, ist eine
   Verfügbarkeitsfrage – keine zweite Entscheidung für den Menschen.
3. **Menge bestätigen** (``confirm_quantity``) – der Auftrag wird mit weniger fertig. Das
   Soll sinkt auf das Gesicherte, der Schritt ist frei, der Auftrag läuft normal zu Ende.
   Fehlte diese Antwort, blieb nur «warten oder ersetzen» – bei einem Erzeugungsauftrag mit
   einem schlechten von fünf Stück beides falsch.

**Geld bleibt ehrlich:** eine bereits **bezahlte** Verkaufsposition lässt sich hier NICHT
kürzen – dafür gibt es die Retoure/Gutschrift (``sale``-Kredit-Modus mit Stripe-Refund).
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, Order
from . import process
from .admin import log_audit
from .events import emit
from . import inventory
from .inventory import allocate, fifo_candidates
from .quantity import ZERO, to_qty
from .reservation import free_qty, reserve
from .subject import record_link


def _fifo_cover(db: Session, order: Order, article_id: int, need) -> Decimal:
    """``need`` (Menge) des Artikels aus **freiem** Lagerbestand FIFO für den Auftrag
    reservieren (+ als Subjekt markieren). Liefert die tatsächlich gedeckte Menge."""
    covered = ZERO
    cands = fifo_candidates(db, article_id, for_order_id=None, lock=True)   # nur freie Restmengen
    for cand, take in zip(cands, allocate(need, [free_qty(c) for c in cands])):
        if take <= 0:
            continue
        reserve(cand, order.id, take)
        cand.subject_of_order_id = order.id
        record_link(db, cand.object_id, order.id)
        covered += take
    return covered


def _cover_from_stock(db: Session, order: Order,
                      instance_object_ids: list[int] | None) -> Decimal:
    """Soviel der offenen **Subjekt**-Fehlmenge wie möglich aus vorhandenem Lagerbestand
    decken. Ohne ``instance_object_ids`` → FIFO über den freien Bestand; mit Auswahl → genau
    diese freigegebenen & freien Instanzen. Liefert die gedeckte Menge (0 = nichts frei)."""
    short = process.subject_shortfalls(db, order)
    if not short:
        return ZERO
    covered = ZERO
    if instance_object_ids:
        chosen = list(dict.fromkeys(instance_object_ids))
        # Row-Lock auch im «bestimmte Instanz wählen»-Pfad – wie in JEDEM anderen
        # Allokations-Schreibpfad (``fifo_candidates(lock=True)``). Ohne Sperre ist
        # ``free_qty``-Prüfung + ``reserve`` ein Check-then-Act: zwei gleichzeitige
        # Deckungen derselben Instanz reservieren doppelt (Überverkauf).
        rows = {
            i.object_id: i for i in db.query(Instance).filter(
                Instance.object_id.in_(chosen), Instance.is_active == True)
            .with_for_update().all()
        }
        for oid in chosen:
            inst = rows.get(oid)
            if not inst:
                raise HTTPException(400, detail=f"Instanz {oid} wurde nicht gefunden")
            rem = short.get(inst.article_id, ZERO)
            if rem <= 0:
                raise HTTPException(400, detail=f"Instanz {oid} passt zu keinem offenen Bedarf dieses Auftrags")
            if not inventory.is_in_stock(inst):
                raise HTTPException(409, detail=f"Instanz {oid} ist nicht freigegeben/am Lager")
            take = min(free_qty(inst), rem)
            if take <= 0:
                raise HTTPException(409, detail=f"Instanz {oid} ist bereits reserviert")
            reserve(inst, order.id, take)
            inst.subject_of_order_id = order.id
            record_link(db, inst.object_id, order.id)
            short[inst.article_id] = rem - take
            covered += take
    else:
        for aid, need in short.items():
            covered += _fifo_cover(db, order, aid, need)
    return covered


def cover_shortfall(db: Session, order: Order, actor_id: int,
                    instance_object_ids: list[int] | None = None) -> dict:
    """**«Ersetzen»** – die Fehlmenge decken, egal woher.

    EIN Weg statt zweier Knöpfe: erst der **freie Lagerbestand** (FIFO bzw. gezielt gewählte
    Instanzen), für den Rest ein **Nachschub**-Unter-Auftrag (produzieren/beschaffen,
    rekursiv über die Stückliste). Ob das eine, das andere oder beides greift, ist eine
    Verfügbarkeitsfrage – der Mensch entscheidet nur, DASS ersetzt werden soll.

    Deckt auch den reinen **Komponenten**-Bedarf ab (Ressource): dort gibt es keinen
    Subjekt-Lagerweg, ``ensure_supply`` übernimmt ihn vollständig. Committet NICHT."""
    from .supply import ensure_supply
    covered = _cover_from_stock(db, order, instance_object_ids)
    created = ensure_supply(db, order, actor_id)
    if covered <= 0 and not created:
        raise HTTPException(409, detail="Nichts zu decken – der Bedarf ist bereits gedeckt")
    if covered > 0:
        log_audit(db, "orders", None, f"{covered} Stück aus Lager gedeckt", actor_id,
                  object_id=order.object_id)
        emit(db, "order.covered_from_stock", object_type="order", object_id=order.object_id,
             payload={"quantity": covered}, actor_id=actor_id)
    return {"covered": covered, "supply_object_ids": [o.object_id for o in created]}


def confirm_quantity(db: Session, order: Order, actor_id: int) -> dict:
    """**«Menge bestätigen»** – der Auftrag wird mit weniger fertig.

    Das Soll sinkt auf das **Gesicherte**: aus «5 bestellt, 1 in Klärung» wird «4 bestellt».
    Der blockierte Schritt ist damit frei und der Auftrag läuft normal zu Ende – ohne dass
    jemand Ersatz beschaffen muss, den niemand haben will. Die Kürzung wird je Position
    vorgenommen (Einzel-Artikel: ``order.quantity``; Mehrpositionen: die Positionsmenge).

    **Nicht bei bezahlter Ware:** eine Position, deren Verkauf schon bezahlt ist, darf hier
    nicht stillschweigend schrumpfen – das wäre eine Kürzung ohne Gutschrift. Dafür ist die
    Retoure/Erstattung da (``sale``-Kredit-Modus, inkl. Stripe-Refund). Committet NICHT."""
    from .order_lines import lines_for
    short = process.subject_shortfalls(db, order)
    if not short:
        raise HTTPException(409, detail="Keine Fehlmenge – es gibt nichts zu bestätigen")
    _assert_not_paid(db, order)
    changed: dict[int, Decimal] = {}
    if order.article_id:
        gap = short.get(order.article_id, ZERO)
        rest = to_qty(order.quantity or 0) - gap
        if rest <= 0:
            raise HTTPException(
                409, detail="Nichts gesichert – hier ist der Abweichungsauftrag der Weg, nicht die Mengenbestätigung")
        order.quantity = rest
        changed[order.article_id] = rest
    else:
        for line in lines_for(db, order):
            gap = short.get(line.article_id, ZERO)
            if gap <= 0:
                continue
            rest = to_qty(line.quantity) - gap
            if rest <= 0:
                raise HTTPException(
                    409, detail="Nichts gesichert – hier ist der Abweichungsauftrag der Weg, nicht die Mengenbestätigung")
            line.quantity = rest
            changed[line.article_id] = rest
    log_audit(db, "orders", None,
              "Menge bestätigt: " + ", ".join(f"Artikel {a} → {q}" for a, q in changed.items()),
              actor_id, object_id=order.object_id)
    emit(db, "order.quantity_confirmed", object_type="order", object_id=order.object_id,
         payload={"quantities": {str(a): float(q) for a, q in changed.items()}}, actor_id=actor_id)
    return {"quantities": {a: q for a, q in changed.items()}}


def _assert_not_paid(db: Session, order: Order) -> None:
    """Bezahlte Verkaufspositionen dürfen nicht per Mengenbestätigung schrumpfen – Geld
    zurück geht über die Retoure/Gutschrift, nicht über eine stille Kürzung."""
    from ..models import Sale
    paid = (
        db.query(Sale.id)
        .filter(Sale.order_id == order.id, Sale.is_active == True,
                Sale.kind == "sale", Sale.status == "paid")
        .first()
    )
    if paid:
        raise HTTPException(
            409,
            detail="Bezahlte Position – die Menge wird über eine Retoure/Gutschrift korrigiert, nicht hier.")
