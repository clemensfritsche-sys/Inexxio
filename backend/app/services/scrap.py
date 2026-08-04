"""Geschäftslogik für «Verschrotten» und «Sperren» – die zwei Wege, eine Instanz aus dem
verwendbaren Bestand zu nehmen.

Beide teilen sich die Marker-Fachzeile ``Disposal`` (``mode``) und die Instanz-Auswahl,
unterscheiden sich aber in der **Achse**, auf der sie wirken – und damit in der Umkehrbarkeit:

* **Verschrotten** wirkt auf ``disposition`` → ``scrapped``: endgültig, die Instanz verliert
  ihren Standort (ein Standort ist immer ein realer Halter, den Ausschuss nicht mehr hat).
* **Sperren** wirkt auf ``quality`` → ``blocked``: vorübergehend, der Standort bleibt. Eine
  defekte Maschine steht weiter da, wo sie steht – sie darf nur nicht verwendet werden. Die
  Sperre ist an der Instanz wieder aufhebbar (``unblock``).

Warum die Qualitäts-Achse: sie beantwortet «darf man das verwenden?», genau die Frage einer
Sperre. ``disposition`` beantwortet «wo ist es» – und daran ändert eine Sperre nichts. Weil
``inventory.in_stock_clauses()`` beides verlangt (passed UND in_stock), fällt eine gesperrte
Instanz automatisch aus FIFO, Verfügbarkeit und Bestandszählung – ohne eine einzige weitere
Abfrage.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Disposal, Order
from . import inventory, ledger, location_split, process
from .admin import log_audit
from .events import emit
from .quantity import to_qty
from . import units as units_svc
from .reservation import release_all, take
from .subject import held_quantity, order_instances


def _chosen_quantities(data) -> dict[int, Decimal | None]:
    """Auswahl vereinheitlichen: ``{instance_object_id: menge|None}`` (None = ganze Restmenge).

    ``items`` (mit Teilmenge) und die Kurzform ``instance_ids`` (ganze Instanzen) werden
    zusammengeführt; ``items`` gewinnt bei Überschneidung. Menge als Decimal (Bruchmenge)."""
    chosen: dict[int, Decimal | None] = {}
    for oid in (data.instance_ids or []):
        chosen.setdefault(oid, None)
    for it in (data.items or []):
        chosen[it.instance_id] = to_qty(it.quantity) if it.quantity is not None else None
    if not chosen:
        raise HTTPException(400, detail="Bitte mindestens eine Instanz wählen")
    return chosen


def _scrap_one(db: Session, inst, qty: Decimal | None, actor_id: int, order: Order) -> Decimal:
    """**Den ANTEIL dieses Auftrags an einer Instanz verschrotten** – ganz oder als Teilmenge.
    Gibt die abgehende Menge zurück.

    Der Anteil ist der Massstab, nicht die Instanz (Testnotizen #412/#414): eine
    4er-Charge kann zu 2 diesem Auftrag und zu 2 einer Abweichung gehören. «Alles»
    heisst dann **die eigenen 2**, nicht die ganze Charge – sonst zerstört eine
    Abweichung aus dem Nichts fremdes Material, und der Eltern-Auftrag steht mit einer
    Fehlmenge da, die niemand verursacht hat. Dieselbe Regel wie beim Prüfumfang
    (``subject.held_quantity``, Notiz #399): wie viel dieser Instanz gehört DIESEM Auftrag?

    **Ganz:** Endzustand ``scrapped``; ALLE Reservierungen werden gelöst (nicht nur die des
    auslösenden Auftrags) – ein verschrottetes Teil verlässt den Bestand endgültig und kann
    KEINEN Auftrag mehr beliefern. Hing es an einem anderen Auftrag (z. B. eine Abweichung
    steuert eine für den Eltern-Verkauf reservierte Instanz aus), wird dessen Fehlmenge
    dadurch **ehrlich** wieder sichtbar → sein Subjekt-Schritt wird «blockiert», statt still
    unterzuliefern. Zusätzlich wird die Instanz **standortlos**: ein Standort ist immer ein
    realer Halter, den Ausschuss nicht mehr hat – der Endzustand IST die «Wo»-Aussage, und
    «wer liegt hier» findet ein verschrottetes Teil korrekt nicht mehr.

    **Teilmenge:** nur die Menge sinkt (keine Teilung, keine neue Objektnummer) – über
    dieselbe Entnahme-Regel wie Verbrauch und Verkauf (``reservation.take``): der eigene
    Anspruch des verschrottenden Auftrags ist damit erfüllt und wird gelöst, fremde
    Ansprüche werden auf die Restmenge gedeckelt; eine verteilte Charge wird nachgezogen."""
    held = held_quantity(order, inst)
    if qty is not None and qty > held:
        raise HTTPException(
            400,
            detail=f"Instanz {inst.object_id}: der Auftrag hält nur {held} – mehr kann er "
                   "nicht aussondern.")
    # «Ganz» heisst: der Auftrag hält die ganze Instanz UND gibt sie ganz ab. Hält er nur
    # einen Anteil, ist auch «alles» eine Teilmenge der Instanz – die Restmenge gehört
    # jemand anderem und bleibt unberührt.
    whole = (qty is None or qty >= held) and held >= to_qty(inst.quantity)
    cut_qty = held if qty is None else qty
    if not whole and cut_qty <= 0:
        raise HTTPException(400, detail=f"Ungültige Menge für Instanz {inst.object_id}")

    if not whole:
        gone: list[int] = []
        cut = take(inst, cut_qty, state="scrapped", by_order_id=order.id, gone=gone)
        location_split.reconcile(inst)
        # Journal (ADR 007): die Teilmenge geht in den terminalen «scrapped»-Topf –
        # zugeschrieben dem Auftrag, der ausgesondert hat.
        ledger.post(db, inst, cut, kind="scrapped", holder=order.id,
                    disposition="scrapped", src_holder=order.id, units=gone,
                    actor_id=actor_id)
        log_audit(db, "instances", "quantity", str(inst.quantity), actor_id,
                  object_id=inst.object_id,
                  old_value=f"{(inst.quantity or 0) + cut} (− {cut} verschrottet)")
        return cut

    old = inst.disposition
    old_loc = f"{inst.location_type}:{inst.location_id}" if inst.location_type else None
    cut = to_qty(inst.quantity)
    # Die Nummern VOR dem Lösen festhalten – danach kennt sie niemand mehr.
    gone_all = [u.index for u in units_svc.of(inst)]
    inst.disposition = "scrapped"
    ledger.post(db, inst, cut, kind="scrapped", holder=order.id,
                disposition="scrapped", src_holder=order.id, units=gone_all,
                actor_id=actor_id)
    release_all(inst)
    if inst.location_type is not None or inst.locations:
        location_split.clear(inst)
        log_audit(db, "instances", "location", None, actor_id,
                  object_id=inst.object_id, old_value=old_loc)
    log_audit(db, "instances", "disposition", "scrapped", actor_id,
              object_id=inst.object_id, old_value=old)
    return cut


def record_scrap(db: Session, order: Order, data, actor_id: int) -> Disposal:
    """Die gewählten Instanzen des Auftrags verschrotten + den Schritt abschliessen."""
    step = process.resolve_exec_step(db, order, "scrap", getattr(data, "step_id", None))

    instances = order_instances(db, order)
    if not instances:
        raise HTTPException(409, detail="Keine Instanzen zum Verschrotten vorhanden")

    by_obj = {i.object_id: i for i in instances}
    chosen = _chosen_quantities(data)

    scrapped = 0
    touched_articles: set[int] = set()
    for oid, qty in chosen.items():
        inst = by_obj.get(oid)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {oid} gehört nicht zu diesem Auftrag")
        if inst.disposition == "scrapped":
            continue                                # idempotent: schon verschrottet
        cut = _scrap_one(db, inst, qty, actor_id, order)
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
    disp.mode = "scrap"
    disp.note = (data.note or "").strip() or None
    disp.scrapped_by_id = actor_id
    db.flush()

    log_audit(db, "disposals", None, f"{scrapped} Instanz(en) verschrottet", actor_id,
              object_id=order.object_id)
    emit(db, "scrap.recorded", object_type="order", object_id=order.object_id,
         payload={"count": scrapped}, actor_id=actor_id)
    # Bestandsabgang → Meldebestand prüfen (Auto-Nachbestellung, E) – bewusst VOR
    # ``recompute_completion``: schliesst der Scrap DIESEN Auftrag ab und ist er selbst die
    # Nachbestellung des Artikels, sähe der Idempotenz-Check ihn sonst nicht mehr als «offen»
    # und legte direkt eine weitere Nachbestellung an (Kette bei Prozessen mit Scrap-Schritt).
    from .replenishment import check_article
    for art_id in touched_articles:
        check_article(db, art_id, actor_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(disp)
    return disp


# ─── Sperren (reversibel) ────────────────────────────────────────────────────────

def _restore_quality(inst) -> str:
    """Zustand nach dem Entsperren: war die Instanz schon einmal freigegeben
    (``released_at`` gesetzt), ist sie es wieder – sonst zurück in die Prüfung.

    Bewusst **abgeleitet** statt gemerkt: einen «Zustand vor der Sperre» zu speichern
    wäre ein verstecktes drittes Feld, das mit der Wirklichkeit auseinanderlaufen kann."""
    return "passed" if getattr(inst, "released_at", None) else "pending"


def record_block(db: Session, order: Order, data, actor_id: int) -> Disposal:
    """Die gewählten Instanzen **sperren** (quality='blocked') + den Schritt abschliessen.

    Anders als beim Verschrotten bleibt alles andere unangetastet: Standort, Menge,
    Reservierungen. Gesperrt heisst «vorübergehend nicht verwendbar», nicht «weg»."""
    step = process.resolve_exec_step(db, order, "block", getattr(data, "step_id", None))

    instances = order_instances(db, order)
    if not instances:
        raise HTTPException(409, detail="Keine Instanzen zum Sperren vorhanden")

    by_obj = {i.object_id: i for i in instances}
    chosen = _chosen_quantities(data)

    blocked = 0
    for oid in chosen:
        inst = by_obj.get(oid)
        if not inst:
            raise HTTPException(400, detail=f"Instanz {oid} gehört nicht zu diesem Auftrag")
        if inst.disposition == "scrapped":
            raise HTTPException(409, detail=f"Instanz {oid} ist verschrottet – Sperren sinnlos")
        if inventory.is_blocked(inst):
            continue                                # idempotent: schon gesperrt
        old = inst.quality
        inst.quality = inventory.BLOCKED
        # Journal (ADR 007): Sperren ist reversibel – die Menge bleibt lebend, nur ihre
        # Qualität wechselt. Halter/Verbleib bleiben, wie sie sind.
        ledger.post(db, inst, held_quantity(order, inst), kind="blocked",
                    holder=ledger.KEEP, quality=inventory.BLOCKED,
                    src_holder=order.id, actor_id=actor_id)
        log_audit(db, "instances", "quality", inventory.BLOCKED, actor_id,
                  object_id=inst.object_id, old_value=old)
        emit(db, "instance.blocked", object_type="instance", object_id=inst.object_id,
             payload={"order": order.object_id}, actor_id=actor_id)
        blocked += 1

    disp = process.fact_for_step(db, order, step)
    if not disp:
        disp = Disposal(order_id=order.id, step_id=step.id)
        db.add(disp)
    disp.mode = "block"
    disp.note = (data.note or "").strip() or None
    disp.scrapped_by_id = actor_id
    db.flush()

    log_audit(db, "disposals", None, f"{blocked} Instanz(en) gesperrt", actor_id,
              object_id=order.object_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(disp)
    return disp


def unblock(db: Session, inst, actor_id: int):
    """Sperre einer Instanz aufheben (z. B. Maschine nach der Wartung wieder freigeben)."""
    if not inventory.is_blocked(inst):
        raise HTTPException(409, detail="Diese Instanz ist nicht gesperrt")
    inst.quality = _restore_quality(inst)
    # Journal (ADR 007): Entsperren – dieselbe Menge, derselbe Halter, Qualität abgeleitet.
    ledger.post(db, inst, inst.quantity, kind="unblocked",
                holder=ledger.KEEP, quality=inst.quality, actor_id=actor_id)
    log_audit(db, "instances", "quality", inst.quality, actor_id,
              object_id=inst.object_id, old_value=inventory.BLOCKED)
    emit(db, "instance.unblocked", object_type="instance", object_id=inst.object_id,
         payload={"quality": inst.quality}, actor_id=actor_id)
    db.commit()
    db.refresh(inst)
    return inst
