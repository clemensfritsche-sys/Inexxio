"""Geschäftslogik für den Prozessschritt «Datenerfassung» (Eingangskontrolle).

Es wird IMMER konkret eine Instanz genannt, an der die Daten zu erfassen sind:
- Einzelteil: aus den N Instanzen werden gemäss Prüfumfang ``required`` Stück
  (stabil pseudo-zufällig) ausgewählt – je Stichprobe ein Wertesatz.
- Charge (batch): die eine Charge-Instanz wird genannt, die Erfassung muss aber
  ``required``-mal erfolgen (mehrere Proben aus der Charge).

Erfassungsmaske je Probe:
- measure: Soll-Ist-Vergleich mit Toleranz (ok, wenn |Ist−Soll| ≤ Toleranz)
- bool:    Gut/Schlecht
- text:    informativ (kein Pass/Fail)

Ohne definierte Maske wird je Probe ein Gut/Schlecht erfasst (synthetisches Feld
``_ok``). Das Ergebnis (passed/failed) leitet sich aus allen Proben ab; Durchfaller
werden auf der Instanz **gesperrt** (``quality='blocked'``, ``inventory.BLOCKED`` – derselbe
Zustand wie beim Schritt «Sperren»: vorhanden, aber nicht verwendbar; der Verbleib
``disposition`` bleibt unberührt).

**Fehlgeschlagen ist nicht terminal – aber nur ein Folgeauftrag löst es.** Eine
fehlgeschlagene Datenerfassung legt automatisch eine Abweichung an; schliesst dieser
Unter-Auftrag ab, gilt der Befund als geklärt (``Inspection.resolved_by_order_id``) und der
Schritt zählt als erledigt. Der aufgezeichnete Befund bleibt dabei **unverändert
fehlgeschlagen** – was gemessen wurde, wird nicht nachträglich schöngeschrieben; geklärt
wird es durch einen eigenen, nachvollziehbaren Vorgang.
"""

import hashlib

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Inspection, Order
from . import inventory, process
from .admin import log_audit
from .deviation import auto_deviation_from_inspection
from .events import emit
from .subject import order_active_instances

# Synthetisches Bewertungsfeld, wenn keine Maske definiert ist (reines Gut/Schlecht).
DEFAULT_OK_FIELD = {"key": "_ok", "label": "Ergebnis", "type": "bool"}


def _current_inspection(db: Session, order: Order, step: ArticleProcessStep | None) -> Inspection | None:
    """Datenerfassung dieses konkreten Schritts (Routing über ``step_id``)."""
    if not step:
        return None
    return process.fact_for_step(db, order, step)


def escalate_decision(currently_escalated: bool, step_percent: int | None, all_ok: bool) -> str:
    """Folgezustand der Datenerfassung: 'passed' | 'failed' | 'escalate'.

    Eine ungenügende Teil-Stichprobe stuft auf 100 % hoch ('escalate'); erst bei
    vollem Prüfumfang (bereits hochgestuft oder von Beginn 100 %) wird endgültig
    'failed'."""
    if all_ok:
        return "passed"
    pct = step_percent if step_percent else 100
    return "failed" if (currently_escalated or pct >= 100) else "escalate"


def inspected_quantity(db: Session, order: Order):
    """Menge, auf die sich der Prüfumfang bezieht: die **tatsächlich geprüften Instanzen**.

    Nicht ``order.quantity`` – das ist die *deklarierte* Menge und sagt bei einem Auftrag
    auf vorhandenen Instanzen etwas anderes aus. Eine Abweichung auf EINE Charge à 5 Stk
    trägt ``quantity=1`` (ein Subjekt), zu prüfen sind aber 5 Stück: bei «jede» kamen so
    statt fünf Proben nur eine. Die Stichprobe wird jetzt aus derselben Quelle bemessen,
    aus der auch die Proben gezogen und die Instanzen bewertet werden
    (``order_active_instances``) – Zahl und Ziele können nicht mehr auseinanderlaufen.
    Ohne Instanzen (Entwurf/Vorschau) bleibt die deklarierte Menge."""
    from .order_lines import effective_quantity
    from .quantity import qty_sum
    insts = order_active_instances(db, order)
    if insts:
        return qty_sum(i.quantity for i in insts)
    return effective_quantity(db, order)


def required_count(db: Session, order: Order, step: ArticleProcessStep | None) -> int:
    insp = _current_inspection(db, order, step)
    # Nach Hochstufung wird zu 100 % geprüft, sonst gemäss Stichprobenumfang.
    pct = 100 if (insp and insp.escalated) else (step.sample_percent if step else None)
    return process.required_sample(inspected_quantity(db, order), pct)


def eval_fields(step: ArticleProcessStep | None) -> list[dict]:
    """Bewertbare Felder – Maske der Definition oder synthetisches Gut/Schlecht."""
    fields = (step.capture_fields if step else None) or []
    return fields if fields else [dict(DEFAULT_OK_FIELD)]


def _apply_per_instance_qc(db: Session, order: Order, fields: list[dict], stored: list[dict]) -> None:
    """Bei 100 %-Prüfung je Instanz bewerten (Einzelteil); Charge als Ganzes.

    Es werden nur **Durchfaller gesperrt** (``inventory.BLOCKED``) – derselbe Zustand, den
    auch der Schritt «Sperren» setzt: vorhanden, aber nicht verwendbar. Bestandene bleiben
    ``pending`` («In Arbeit») und werden erst beim Auftrags-Abschluss freigegeben
    (`process.release_instances`) – «Freigegeben» heisst immer: Auftrag fertig.

    **Eine Sperre ist rücknehmbar** (Nacharbeit): besteht eine zuvor gesperrte Instanz die
    Erfassung eines **Folgeauftrags**, geht sie zurück auf ``pending``. Ohne das wäre ein
    Durchfaller endgültig verloren – auch wenn die Abweichung ihn nachweislich in Ordnung
    gebracht hat. Terminale Instanzen (verschrottet/verkauft/verbaut) bleiben unangetastet:
    dort ist nichts mehr zu bewerten."""
    insts = order_active_instances(db, order)
    reworkable = "in_process"

    def verdict(inst, ok: bool) -> None:
        if not ok:
            inst.quality = inventory.BLOCKED
        elif inventory.is_blocked(inst) and inst.disposition == reworkable:
            inst.quality = "pending"      # Nacharbeit bestanden → Sperre gelöst

    if len(insts) == 1 and insts[0].kind == "batch":
        verdict(insts[0], all(evaluate(fields, s.get("values") or {}) for s in stored))
        return
    ok_by_inst: dict[int, bool] = {}
    for s in stored:
        ok = evaluate(fields, s.get("values") or {})
        iid = s.get("instance_id")
        ok_by_inst[iid] = ok_by_inst.get(iid, True) and ok
    for inst in insts:
        verdict(inst, ok_by_inst.get(inst.object_id, False))


def resolve_failed_by(db: Session, parent: Order, resolver: Order) -> int:
    """Fehlgeschlagene Datenerfassungen des Eltern-Auftrags als **geklärt** vermerken.

    Aufgerufen, wenn eine **Abweichung** abschliesst – der Unter-Auftrag IST die Klärung
    (nachgearbeitet, ersetzt, ausgesondert). Ohne diesen Schritt bliebe der fehlgeschlagene
    Schritt für immer ``failed``, der Eltern-Auftrag könnte nie abschliessen und seine
    Instanzen nie freigegeben werden – sie hingen dauerhaft in «In Arbeit».

    **Nur ein Folgeauftrag klärt.** Es gibt bewusst keinen Knopf «erneut erfassen» am
    fehlgeschlagenen Schritt: was gemessen wurde, wird nicht überschrieben, und wer den
    Befund aus der Welt schaffen will, muss den Vorgang durchlaufen, der ihn behandelt.
    (Der Knopf war ohnehin eine Sackgasse: ``resolve_exec_step`` lässt nur einen *aktiven*
    Schritt ausführen, ein fehlgeschlagener ist es nicht – der Server hätte mit 409 geantwortet.)

    Idempotent: bereits geklärte Befunde bleiben bei ihrem ursprünglichen Klärer."""
    rows = (
        db.query(Inspection)
        .filter(Inspection.order_id == parent.id, Inspection.is_active == True,
                Inspection.result == "failed", Inspection.resolved_by_order_id.is_(None))
        .all()
    )
    for insp in rows:
        insp.resolved_by_order_id = resolver.object_id
        log_audit(db, "inspections", "resolved_by_order_id", str(resolver.object_id), None,
                  object_id=parent.object_id)
        emit(db, "inspection.resolved", object_type="order", object_id=parent.object_id,
             payload={"resolved_by": resolver.object_id, "inspection_id": insp.id})
    return len(rows)


def _shuffle_key(object_id: int, seed: int) -> int:
    """Stabiler Pseudo-Zufall: gleiche Auswahl über alle Requests, je Auftrag anders."""
    return int(hashlib.md5(f"{seed}:{object_id}".encode()).hexdigest(), 16)


def sample_targets(db: Session, order: Order, step: ArticleProcessStep | None) -> list[dict]:
    """Konkrete Stichproben [{instance_id, slot}] gemäss Prüfumfang.

    Charge → eine Instanz mit mehreren Proben (slot 1..N); Einzelteil → N zufällig
    ausgewählte Instanzen (je slot 1)."""
    insts = order_active_instances(db, order)
    need = required_count(db, order, step)
    if not insts or need <= 0:
        return []
    if len(insts) == 1 and insts[0].kind == "batch":
        charge = insts[0]
        return [{"instance_id": charge.object_id, "slot": k + 1} for k in range(need)]
    chosen = sorted(insts, key=lambda i: _shuffle_key(i.object_id or 0, order.id or 0))[:need]
    chosen.sort(key=lambda i: i.object_id or 0)
    return [{"instance_id": i.object_id, "slot": 1} for i in chosen]


def field_ok(field: dict, value) -> bool:
    """Bewertet ein einzelnes Erfassungsfeld."""
    ftype = field.get("type")
    if ftype == "measure":
        if value is None or value == "":
            return False
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        target = field.get("target")
        if target is None:
            return True  # nur erfasst, kein Soll → informativ
        tol = field.get("tolerance") or 0
        return abs(v - float(target)) <= float(tol)
    if ftype == "bool":
        return value is True or value == "true" or value == 1
    return True  # text → informativ


def evaluate(fields: list[dict], values: dict) -> bool:
    """True, wenn alle bewertbaren Felder in Ordnung sind."""
    return all(field_ok(f, (values or {}).get(f.get("key"))) for f in (fields or []))


def record_inspection(db: Session, order: Order, data, actor) -> Inspection:
    actor_id = actor.id
    step = process.resolve_exec_step(db, order, "inspection", getattr(data, "step_id", None))

    fields = eval_fields(step)
    # Bild-/Unterschrift-Felder sind EIGENE Erfassungsfelder (Feldtyp), keine übergeordnete
    # Option: sie müssen je Stichprobe erfasst sein (Präsenz), zählen aber nicht ins Pass/Fail.
    media_keys = [f.get("key") for f in fields if f.get("type") in ("photo", "signature")]
    targets = sample_targets(db, order, step)
    need = len(targets)

    submitted = {(s.instance_id, s.slot): (s.values or {}) for s in (data.samples or [])}
    stored: list[dict] = []
    all_ok = True
    for t in targets:
        vals = submitted.get((t["instance_id"], t["slot"]))
        if vals is None:
            raise HTTPException(400, detail="Bitte für jede aufgeführte Stichprobe die Daten erfassen")
        for mk in media_keys:
            if not (str(vals.get(mk) or "")).strip():
                raise HTTPException(400, detail="Bitte alle verlangten Bild-/Unterschrift-Felder erfassen")
        all_ok = all_ok and evaluate(fields, vals)
        stored.append({"instance_id": t["instance_id"], "slot": t["slot"], "values": vals})

    insp = _current_inspection(db, order, step)
    if not insp:
        insp = Inspection(order_id=order.id, article_id=order.article_id, step_id=step.id)
        db.add(insp)

    step_pct = step.sample_percent
    decision = escalate_decision(insp.escalated, step_pct, all_ok)

    insp.checked_count = need
    insp.note = (data.note or "").strip() or None
    insp.samples = stored
    insp.inspector_id = actor_id

    # Ungenügende Teil-Stichprobe → auf 100 % hochstufen, noch NICHT abschliessen.
    if decision == "escalate":
        insp.escalated = True
        insp.result = "pending"
        db.flush()
        log_audit(db, "inspections", "escalated", "100", actor_id, object_id=order.object_id)
        db.commit()
        db.refresh(insp)
        return insp

    insp.result = "passed" if decision == "passed" else "failed"
    db.flush()
    # Je Instanz bewerten – IMMER, nicht nur beim Nichtbestehen: Bestehen sperrt nichts,
    # löst aber eine frühere Sperre (Nacharbeit). Bei Bestehen wird NICHT vorzeitig
    # freigegeben – «Freigegeben» folgt erst beim Auftrags-Abschluss
    # (process.release_instances).
    _apply_per_instance_qc(db, order, fields, stored)

    log_audit(db, "inspections", "result", insp.result, actor_id, object_id=order.object_id)
    emit(db, f"inspection.{insp.result}", object_type="order", object_id=order.object_id,
         payload={"checked": need, "step_id": step.id}, actor_id=actor_id)
    # Bei Nichtbestehen automatisch eine **Abweichung** auf die durchgefallenen Instanzen
    # eröffnen (idempotent) – ersetzt die frühere Auto-Reklamation. Sie NIMMT die Durchfaller
    # aus dem Eltern-Auftrag heraus (Unterdeckung), statt ihn anzuhalten: die guten Stück
    # laufen weiter.
    if insp.result == "failed":
        auto_deviation_from_inspection(db, order, actor_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(insp)
    return insp
