"""Geschäftslogik für den Prozessschritt «Datenerfassung» (Eingangskontrolle).

Stichprobenprüfung mit konfigurierbarer Erfassungsmaske:
- measure: Soll-Ist-Vergleich mit Toleranz (ok, wenn |Ist−Soll| ≤ Toleranz)
- bool:    Gut/Schlecht
- text:    informativ (kein Pass/Fail)

Das Ergebnis (passed/failed) leitet sich aus den erfassten Werten ab; ohne
Maske wird es direkt gesetzt. Das Ergebnis wird auf die Instanzen übertragen.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Inspection, Instance, Order
from . import process
from .admin import log_audit


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
    fields = (step.capture_fields if step else None) or []
    need = required_count(db, order)
    checked = data.checked_count
    values = data.values or {}

    if fields:
        all_ok = evaluate(fields, values)
        if not all_ok:
            result = "failed"
        else:
            if (checked or 0) < need:
                raise HTTPException(400, detail=f"Für die Freigabe müssen mindestens {need} Stück geprüft sein")
            result = "passed"
    else:
        if data.result not in ("passed", "failed"):
            raise HTTPException(400, detail="Ergebnis muss 'passed' oder 'failed' sein")
        result = data.result
        if result == "passed" and (checked or 0) < need:
            raise HTTPException(400, detail=f"Für die Freigabe müssen mindestens {need} Stück geprüft sein")

    insp = (
        db.query(Inspection)
        .filter(Inspection.order_id == order.id, Inspection.is_active == True)
        .first()
    )
    if not insp:
        insp = Inspection(order_id=order.id, article_id=order.article_id)
        db.add(insp)
    insp.result = result
    insp.checked_count = checked
    insp.note = (data.note or "").strip() or None
    insp.values = values or None
    insp.inspector_id = actor_id
    db.flush()

    for inst in db.query(Instance).filter(Instance.order_id == order.id, Instance.is_active == True).all():
        inst.qc_status = result

    log_audit(db, "inspections", "result", result, actor_id, object_id=order.object_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(insp)
    return insp
