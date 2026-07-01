"""Wiederherstellung nach einer **Aussteuerung** eines Auftrags-Subjekts.

Wird eine für einen Auftrag reservierte Instanz **ausgesteuert** (z. B. eine Abweichung
verschrottet ein bereits verkauftes Teil), löst das Verschrotten alle Reservierungen der
Instanz (``reservation.release_all``). Der Auftrag hat dann eine **ehrliche Fehlmenge**;
sein Subjekt-Schritt (Bewegung/Versand/Kontrolle) ist «blockiert» (abgeleitet aus dem
Bestand). Genau EIN Mechanismus, drei vom Nutzer wählbare Wege, den Bedarf wieder zu decken:

  1. **Nachschub** – produzieren/beschaffen (``services/supply.py``, unverändert).
  2. **Aus Lager decken** – freien Bestand FIFO reservieren (``cover_from_stock`` ohne
     Instanz-Auswahl) bzw. **gezielt eine andere Instanz** wählen (mit Auswahl).
  3. **Menge reduzieren** – die Anforderung auf das tatsächlich Vorhandene senken
     (``reduce_to_available``); der Auftrag wird mit weniger Stück fertig.

Diese drei bilden genau die Fälle ab, die je nach Subjektwahl sinnvoll sind: ein FIFO-
Auftrag kann jederzeit anderen Lagerbestand nutzen; ein gezielt auf Instanzen fixierter
Auftrag kann eine Ersatz-Instanz wählen ODER die Menge reduzieren; und wo gar nichts am
Lager ist, produziert der Nachschub.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, Order
from . import process
from .admin import log_audit
from .events import emit
from .inventory import allocate, fifo_candidates
from .order_lines import lines_for
from .reservation import free_qty, reserve
from .subject import record_link


def _fifo_cover(db: Session, order: Order, article_id: int, need: int) -> int:
    """``need`` Stück des Artikels aus **freiem** Lagerbestand FIFO für den Auftrag
    reservieren (+ als Subjekt markieren). Liefert die tatsächlich gedeckte Menge."""
    covered = 0
    cands = fifo_candidates(db, article_id, for_order_id=None)   # nur freie Restmengen
    for cand, take in zip(cands, allocate(need, [free_qty(c) for c in cands])):
        if take <= 0:
            continue
        reserve(cand, order.id, take)
        cand.subject_of_order_id = order.id
        record_link(db, cand.object_id, order.id)
        covered += take
    return covered


def cover_from_stock(db: Session, order: Order, actor_id: int,
                     instance_object_ids: list[int] | None = None) -> int:
    """Die offene **Subjekt-Fehlmenge** des Auftrags aus vorhandenem Lagerbestand decken.

    Ohne ``instance_object_ids`` → **FIFO** über den freien Bestand jeder Fehlmenge
    («Aus Lager decken»). Mit Auswahl → genau diese, **freigegebenen & freien** Instanzen
    reservieren («Andere Instanz wählen»). Partielle Deckung ist erlaubt; was offen bleibt,
    hält den Schritt weiter blockiert (Nachschub/Reduktion als weitere Wege). Committet NICHT."""
    short = process.subject_shortfalls(db, order)
    if not short:
        raise HTTPException(409, detail="Kein offener Bedarf – es ist nichts zu decken")
    covered = 0
    if instance_object_ids:
        chosen = list(dict.fromkeys(instance_object_ids))
        rows = {
            i.object_id: i for i in db.query(Instance).filter(
                Instance.object_id.in_(chosen), Instance.is_active == True).all()
        }
        for oid in chosen:
            inst = rows.get(oid)
            if not inst:
                raise HTTPException(400, detail=f"Instanz {oid} wurde nicht gefunden")
            rem = short.get(inst.article_id, 0)
            if rem <= 0:
                raise HTTPException(400, detail=f"Instanz {oid} passt zu keinem offenen Bedarf dieses Auftrags")
            if not (inst.quality == "passed" and inst.disposition == "in_stock"):
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
    if covered <= 0:
        raise HTTPException(
            409, detail="Kein freier Bestand verfügbar – bitte Nachschub anlegen oder Menge reduzieren")
    log_audit(db, "orders", None, f"{covered} Stück aus Lager gedeckt", actor_id,
              object_id=order.object_id)
    emit(db, "order.covered_from_stock", object_type="order", object_id=order.object_id,
         payload={"quantity": covered}, actor_id=actor_id)
    return covered


def reduce_to_available(db: Session, order: Order, actor_id: int) -> int:
    """Die **Anforderung** des Auftrags auf das tatsächlich Reservierte senken: die offene
    Subjekt-Fehlmenge wird von der Bestellmenge (Einzel-Artikel: ``order.quantity``;
    Mehrpositionen: je Position) abgezogen. Der Schritt ist danach nicht mehr blockiert und
    der Auftrag wird mit **weniger Stück** fertig. Liefert die reduzierte Gesamtmenge.

    Bleibt nichts zu liefern (Fehlmenge = ganze Menge), wird abgelehnt – dann ist «Abbrechen»
    der richtige Weg, nicht eine Reduktion auf null. Committet NICHT."""
    short = process.subject_shortfalls(db, order)
    if not short:
        raise HTTPException(409, detail="Kein offener Bedarf – es ist nichts zu reduzieren")
    reduced = 0
    if order.article_id is not None:
        s = short.get(order.article_id, 0)
        new_qty = (order.quantity or 0) - s
        if new_qty <= 0:
            raise HTTPException(
                409, detail="Es bliebe nichts mehr zu liefern – bitte stattdessen den Auftrag abbrechen")
        reduced = s
        order.quantity = new_qty
    else:
        lines = lines_for(db, order)
        for line in lines:
            s = short.get(line.article_id, 0)
            if s > 0:
                cut = min(s, line.quantity)      # tatsächlich weggeschnittene Menge dieser Position
                line.quantity = line.quantity - cut
                reduced += cut
        # Auf 0 gefallene Positionen deaktivieren (nichts mehr zu liefern), aber nie die letzte.
        active = [l for l in lines if l.quantity > 0]
        if not active:
            raise HTTPException(
                409, detail="Es bliebe nichts mehr zu liefern – bitte stattdessen den Auftrag abbrechen")
        for line in lines:
            if line.quantity <= 0:
                line.is_active = False
    log_audit(db, "orders", None, f"Bedarf um {reduced} Stück reduziert (Aussteuerung)", actor_id,
              object_id=order.object_id)
    emit(db, "order.demand_reduced", object_type="order", object_id=order.object_id,
         payload={"reduced": reduced}, actor_id=actor_id)
    # Ggf. abschliessen, falls der Auftrag jetzt vollständig gedeckt & alle Schritte erledigt sind.
    process.recompute_completion(db, order)
    return reduced
