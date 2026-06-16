"""Geschäftslogik für den Prozessschritt «Eingangskontrolle».

Stichprobenprüfung: Aus der Prozessdefinition kommt der Prüfumfang in % der
Menge. Der Prüfer erfasst die geprüfte Anzahl + Ergebnis (passed/failed); das
Ergebnis wird auf die Instanzen (qc_status) übertragen.
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


def record_inspection(db: Session, order: Order, data, actor_id: int) -> Inspection:
    if not process.is_step_active(db, order, "inspection"):
        raise HTTPException(409, detail="Eingangskontrolle ist (noch) nicht an der Reihe")

    result = data.result
    if result not in ("passed", "failed"):
        raise HTTPException(400, detail="Ergebnis muss 'passed' oder 'failed' sein")

    need = required_count(db, order)
    checked = data.checked_count if data.checked_count is not None else None
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
    insp.inspector_id = actor_id
    db.flush()

    # Ergebnis auf die Instanzen übertragen
    for inst in db.query(Instance).filter(Instance.order_id == order.id, Instance.is_active == True).all():
        inst.qc_status = result

    log_audit(db, "inspections", "result", result, actor_id, object_id=order.object_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(insp)
    return insp
