"""Generische Auftrags-Prozess-Engine.

Der Auftrag führt eine geordnete Liste von Prozessschritten (Definition in
``article_process_steps``). Der Ausführungsstand jedes Schritts wird aus der
jeweiligen Fachtabelle abgeleitet – KEINE eigene Orchestrierungstabelle:

    purchase       → purchase_orders.status   (erledigt = received, fehlgeschlagen = rejected)
    inspection     → inspections.result        (erledigt = passed, fehlgeschlagen = failed)
    movement       → movements vorhanden       (erledigt = Einlagerung bestätigt)

Die Bestands-Instanzen entstehen bereits bei der Auftragsfreigabe (kein eigener
Schritt mehr, siehe ``services/serialization.py``).

Ein Schritt ist «aktiv», sobald alle vorherigen erledigt sind. Der Auftrag wird
automatisch ``completed``, wenn alle definierten Schritte erledigt sind.
"""

from math import ceil

from sqlalchemy.orm import Session

from ..models import (
    ArticleProcessStep, Inspection, Movement, Order, PurchaseOrder,
)

STEP_LABELS = {
    "purchase": "Beschaffung",
    "inspection": "Datenerfassung",
    "movement": "Bewegung",
}


def step_defs(db: Session, article_id: int) -> list[ArticleProcessStep]:
    """Aktive Prozessschritt-Definitionen des Artikels in Reihenfolge."""
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article_id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def _purchase(db: Session, order: Order) -> PurchaseOrder | None:
    return (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .first()
    )


def _inspection(db: Session, order: Order) -> Inspection | None:
    return (
        db.query(Inspection)
        .filter(Inspection.order_id == order.id, Inspection.is_active == True)
        .first()
    )


def _movement(db: Session, order: Order) -> Movement | None:
    return (
        db.query(Movement)
        .filter(Movement.order_id == order.id, Movement.is_active == True)
        .first()
    )


def _raw_status(db: Session, order: Order, step_type: str) -> str:
    """Roh-Status eines Schritts: 'done' | 'open' | 'failed'."""
    if step_type == "purchase":
        po = _purchase(db, order)
        if not po:
            return "open"
        if po.status == "received":
            return "done"
        if po.status == "rejected":
            return "failed"
        return "open"
    if step_type == "inspection":
        insp = _inspection(db, order)
        if insp and insp.result == "passed":
            return "done"
        if insp and insp.result == "failed":
            return "failed"
        return "open"
    if step_type == "movement":
        return "done" if _movement(db, order) else "open"
    return "open"


def order_step_infos(db: Session, order: Order) -> list[dict]:
    """Schrittliste für den Auftrag-Stepper: state ∈ done|active|locked|failed."""
    if not order.article_id:
        return []
    infos: list[dict] = []
    active_assigned = False
    for d in step_defs(db, order.article_id):
        raw = _raw_status(db, order, d.step_type)
        if raw == "done":
            state = "done"
        elif raw == "failed":
            state = "failed"
            active_assigned = True
        elif not active_assigned:
            state = "active"
            active_assigned = True
        else:
            state = "locked"
        infos.append({
            "step_type": d.step_type,
            "position": d.position,
            "label": STEP_LABELS.get(d.step_type, d.step_type),
            "state": state,
        })
    return infos


def is_step_active(db: Session, order: Order, step_type: str) -> bool:
    return any(i["step_type"] == step_type and i["state"] == "active"
               for i in order_step_infos(db, order))


def all_steps_done(db: Session, order: Order) -> bool:
    infos = order_step_infos(db, order)
    return bool(infos) and all(i["state"] == "done" for i in infos)


def has_step(db: Session, order: Order, step_type: str) -> bool:
    if not order.article_id:
        return False
    return any(d.step_type == step_type for d in step_defs(db, order.article_id))


def recompute_completion(db: Session, order: Order) -> None:
    """Auftrag automatisch abschliessen, wenn alle Prozessschritte erledigt sind."""
    if order.status != "completed" and all_steps_done(db, order):
        order.status = "completed"


def required_sample(quantity: int | None, sample_percent: int | None) -> int:
    """Zu prüfende Stückzahl der Eingangskontrolle (mind. 1, wenn Menge > 0)."""
    qty = quantity or 0
    pct = sample_percent if sample_percent is not None else 100
    if qty <= 0 or pct <= 0:
        return 0
    return min(qty, max(1, ceil(qty * pct / 100)))
