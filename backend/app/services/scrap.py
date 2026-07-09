"""Geschäftslogik für den Prozessschritt «Verschrotten».

Verschrotten ist die definierte **Auflösung** einer Abweichung (oder eines regulären
Bestands-Auftrags): ein defektes/nicht mehr benötigtes Teil verlässt den Bestand. Die
gewählten Instanzen werden auf ``disposition='scrapped'`` gesetzt; ein ``Disposal``-
Datensatz markiert den Abschluss des Schritts (analog zur Bewegung – keine eigene Nummer).

So gibt es keine „herumliegenden, undefinierten Teile": ein physisch vorhandenes Teil
bekommt einen ehrlichen Endzustand (verschrottet) statt einfach zu verschwinden.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Disposal, Order
from . import location_split, process
from .admin import log_audit
from .events import emit
from .quantity import to_qty
from .reservation import reduce_quantity, release_all
from .subject import order_instances


def record_scrap(db: Session, order: Order, data, actor_id: int) -> Disposal:
    """Die gewählten Instanzen des Auftrags verschrotten + den Schritt abschliessen."""
    step = process.resolve_exec_step(db, order, "scrap", getattr(data, "step_id", None))

    instances = order_instances(db, order)
    if not instances:
        raise HTTPException(409, detail="Keine Instanzen zum Verschrotten vorhanden")

    by_obj = {i.object_id: i for i in instances}
    # Auswahl vereinheitlichen: {instance_object_id: menge|None} (None = ganze Restmenge).
    # ``items`` (mit Teilmenge) und die Kurzform ``instance_ids`` (ganze Instanzen) werden
    # zusammengeführt; ``items`` gewinnt bei Überschneidung. Menge als Decimal (Bruchmenge).
    chosen: dict[int, Decimal | None] = {}
    for oid in (data.instance_ids or []):
        chosen.setdefault(oid, None)
    for it in (data.items or []):
        chosen[it.instance_id] = to_qty(it.quantity) if it.quantity is not None else None
    if not chosen:
        raise HTTPException(400, detail="Bitte mindestens eine Instanz zum Verschrotten wählen")

    scrapped = 0
    touched_articles: set[int] = set()
    for oid, qty in chosen.items():
        inst = by_obj.get(oid)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {oid} gehört nicht zu diesem Auftrag")
        if inst.disposition == "scrapped":
            continue                                # idempotent: schon verschrottet
        whole = qty is None or qty >= to_qty(inst.quantity)
        if not whole and qty <= 0:
            raise HTTPException(400, detail=f"Ungültige Menge für Instanz {oid}")
        if whole:
            old = inst.disposition
            old_loc = f"{inst.location_type}:{inst.location_id}" if inst.location_type else None
            cut = to_qty(inst.quantity)
            inst.disposition = "scrapped"
            # ALLE Reservierungen lösen (nicht nur die dieses Auftrags): ein verschrottetes Teil
            # verlässt den Bestand endgültig und kann KEINEN Auftrag mehr beliefern. Hing es an
            # einem anderen Auftrag (z. B. eine Abweichung steuert eine für den Eltern-Verkauf
            # reservierte Instanz aus), wird dessen Fehlmenge dadurch **ehrlich** wieder sichtbar
            # → sein Subjekt-Schritt wird «blockiert» (abgeleitet), statt still unterzuliefern.
            release_all(inst)
            # **Standortlos machen**: ein Standort ist immer ein realer Halter (Lagerplatz/Person/
            # Instanz); Ausschuss hat keinen mehr. Der Endzustand `scrapped` IST die «Wo»-Aussage –
            # kein Schrottplatz-Lagerort, keine „herrenlosen" Referenzen (references/„wer liegt hier"
            # finden ein verschrottetes Teil dann korrekt nicht mehr).
            if inst.location_type is not None or inst.locations:
                location_split.clear(inst)
                log_audit(db, "instances", "location", None, actor_id,
                          object_id=inst.object_id, old_value=old_loc)
            log_audit(db, "instances", "disposition", "scrapped", actor_id,
                      object_id=inst.object_id, old_value=old)
        else:
            # Teil-Verschrottung einer Charge: nur die Menge sinkt (keine Teilung/neue Nummer),
            # überschüssige Reservierungen werden getrimmt (Recovery) – analog Ressourcen-Teilentnahme.
            cut = reduce_quantity(inst, qty)
            # Verteilte Charge: nach dem Mengen-Abgang die Standort-Verteilung nachziehen
            # (grösste Teilmenge zuerst gekürzt), damit die Summe wieder = quantity ist.
            location_split.reconcile(inst)
            log_audit(db, "instances", "quantity", str(inst.quantity), actor_id,
                      object_id=inst.object_id,
                      old_value=f"{(inst.quantity or 0) + cut} (− {cut} verschrottet)")
        emit(db, "inventory.decreased", object_type="instance", object_id=inst.object_id,
             payload={"quantity": cut, "delta": -cut,
                      "polarity": event_types.DECREASE, "reason": "scrapped",
                      "order": order.object_id})
        touched_articles.add(inst.article_id)
        scrapped += 1

    disp = process.fact_for_step(db, order, step)
    if not disp:
        disp = Disposal(order_id=order.id, step_id=step.id)
        db.add(disp)
    disp.note = (data.note or "").strip() or None
    disp.scrapped_by_id = actor_id
    db.flush()

    log_audit(db, "disposals", None, f"{scrapped} Instanz(en) verschrottet", actor_id,
              object_id=order.object_id)
    emit(db, "scrap.recorded", object_type="order", object_id=order.object_id,
         payload={"count": scrapped}, actor_id=actor_id)
    process.recompute_completion(db, order)
    # Bestandsabgang → Meldebestand prüfen (Auto-Nachbestellung, E). Verschrottung ist ein
    # klarer Stock-Drop; sinkt der freie Bestand unter den Meldebestand, entsteht Nachschub.
    from .replenishment import check_article
    for art_id in touched_articles:
        check_article(db, art_id, actor_id)
    db.commit()
    db.refresh(disp)
    return disp
