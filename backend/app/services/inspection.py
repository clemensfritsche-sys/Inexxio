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
``_ok``). Das Ergebnis (passed/failed) leitet sich aus allen Proben ab und wird
auf die Instanzen (qc_status) übertragen.
"""

import hashlib

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Inspection, Instance, Order
from . import process
from .admin import log_audit
from .claims import auto_claim_from_inspection

# Synthetisches Bewertungsfeld, wenn keine Maske definiert ist (reines Gut/Schlecht).
DEFAULT_OK_FIELD = {"key": "_ok", "label": "Ergebnis", "type": "bool"}


def _inspection_step(db: Session, article_id: int) -> ArticleProcessStep | None:
    return (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article_id,
            ArticleProcessStep.step_type == "inspection",
            ArticleProcessStep.is_active == True,
        )
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .first()
    )


def required_count(db: Session, order: Order) -> int:
    step = _inspection_step(db, order.article_id) if order.article_id else None
    pct = step.sample_percent if step else None
    return process.required_sample(order.quantity, pct)


def eval_fields(step: ArticleProcessStep | None) -> list[dict]:
    """Bewertbare Felder – Maske der Definition oder synthetisches Gut/Schlecht."""
    fields = (step.capture_fields if step else None) or []
    return fields if fields else [dict(DEFAULT_OK_FIELD)]


def _order_instances(db: Session, order: Order) -> list[Instance]:
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


def _shuffle_key(object_id: int, seed: int) -> int:
    """Stabiler Pseudo-Zufall: gleiche Auswahl über alle Requests, je Auftrag anders."""
    return int(hashlib.md5(f"{seed}:{object_id}".encode()).hexdigest(), 16)


def sample_targets(db: Session, order: Order) -> list[dict]:
    """Konkrete Stichproben [{instance_id, slot}] gemäss Prüfumfang.

    Charge → eine Instanz mit mehreren Proben (slot 1..N); Einzelteil → N zufällig
    ausgewählte Instanzen (je slot 1)."""
    insts = _order_instances(db, order)
    need = required_count(db, order)
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


def record_inspection(db: Session, order: Order, data, actor_id: int) -> Inspection:
    if not process.is_step_active(db, order, "inspection"):
        raise HTTPException(409, detail="Datenerfassung ist (noch) nicht an der Reihe")

    step = _inspection_step(db, order.article_id) if order.article_id else None
    fields = eval_fields(step)
    targets = sample_targets(db, order)
    need = len(targets)

    submitted = {(s.instance_id, s.slot): (s.values or {}) for s in (data.samples or [])}
    stored: list[dict] = []
    all_ok = True
    for t in targets:
        vals = submitted.get((t["instance_id"], t["slot"]))
        if vals is None:
            raise HTTPException(400, detail="Bitte für jede aufgeführte Stichprobe die Daten erfassen")
        all_ok = all_ok and evaluate(fields, vals)
        stored.append({"instance_id": t["instance_id"], "slot": t["slot"], "values": vals})

    result = "passed" if all_ok else "failed"

    insp = (
        db.query(Inspection)
        .filter(Inspection.order_id == order.id, Inspection.is_active == True)
        .first()
    )
    if not insp:
        insp = Inspection(order_id=order.id, article_id=order.article_id)
        db.add(insp)
    insp.result = result
    insp.checked_count = need
    insp.note = (data.note or "").strip() or None
    insp.samples = stored
    insp.inspector_id = actor_id
    db.flush()

    # Stichprobenentscheid gilt für das ganze Los
    for inst in _order_instances(db, order):
        inst.qc_status = result

    log_audit(db, "inspections", "result", result, actor_id, object_id=order.object_id)
    # Bei Nichtbestehen automatisch eine interne Reklamation eröffnen (idempotent)
    if result == "failed":
        auto_claim_from_inspection(db, order, actor_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(insp)
    return insp
