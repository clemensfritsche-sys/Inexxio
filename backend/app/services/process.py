"""Generische Auftrags-Prozess-Engine.

Der Auftrag führt eine geordnete Liste von Prozessschritten (Definition in
``article_process_steps``). Der Ausführungsstand jedes Schritts wird aus der
jeweiligen Fachtabelle abgeleitet – KEINE eigene Orchestrierungstabelle:

    purchase       → purchase_orders.status   (erledigt = received, fehlgeschlagen = rejected)
    inspection     → inspections.result        (erledigt = passed, fehlgeschlagen = failed)
    movement       → movements vorhanden       (erledigt = Einlagerung bestätigt)
    resource       → resource_usages vorhanden (erledigt = Ressourcen gebucht)

**Mehr-Operationen-Routing:** Mehrere gleichartige Schritte (z. B. mehrere
``resource``-Operationen) sind hintereinander möglich. Jede Fachzeile trägt
deshalb die ``step_id`` ihrer Schritt-Definition; so wird der Ausführungsstand
**pro Schritt** und nicht pro Typ abgeleitet. Altdaten ohne ``step_id`` gehören
dem einzigen Schritt ihres Typs.

Die Bestands-Instanzen entstehen bereits bei der Auftragsfreigabe (kein eigener
Schritt mehr, siehe ``services/serialization.py``).

Ein Schritt ist «aktiv», sobald alle vorherigen erledigt sind. Der Auftrag wird
automatisch ``completed``, wenn alle definierten Schritte erledigt sind.
"""

from math import ceil

from sqlalchemy.orm import Session

from ..models import (
    ArticleProcessStep, Inspection, Movement, Order, PurchaseOrder, ResourceUsage,
)
from ..models.base import utcnow

STEP_LABELS = {
    "purchase": "Beschaffung",
    "inspection": "Datenerfassung",
    "movement": "Bewegung",
    "resource": "Ressource",
}

# Fachtabelle je Schritt-Typ (für die generische Routing-Auflösung)
_FACT_MODEL = {
    "purchase": PurchaseOrder,
    "inspection": Inspection,
    "movement": Movement,
    "resource": ResourceUsage,
}


def step_defs(db: Session, article_id: int) -> list[ArticleProcessStep]:
    """Aktive Prozessschritt-Definitionen des Artikels in Reihenfolge."""
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article_id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def _facts(db: Session, order: Order, step_type: str) -> list:
    model = _FACT_MODEL.get(step_type)
    if model is None:
        return []
    return (
        db.query(model)
        .filter(model.order_id == order.id, model.is_active == True)
        .all()
    )


def fact_for_step(db: Session, order: Order, step: ArticleProcessStep):
    """Fachzeile, die zu genau diesem Schritt gehört (Routing über ``step_id``).

    Exakter Treffer über ``step_id``; fehlt er (Altdaten), gehört eine Zeile ohne
    ``step_id`` dem **einzigen** Schritt seines Typs."""
    rows = _facts(db, order, step.step_type)
    for r in rows:
        if getattr(r, "step_id", None) == step.id:
            return r
    same_type = [d for d in step_defs(db, order.article_id) if d.step_type == step.step_type]
    if len(same_type) == 1:
        for r in rows:
            if getattr(r, "step_id", None) is None:
                return r
    return None


def _raw_status(db: Session, order: Order, step: ArticleProcessStep) -> str:
    """Roh-Status eines konkreten Schritts: 'done' | 'open' | 'failed'."""
    fact = fact_for_step(db, order, step)
    if step.step_type == "purchase":
        if not fact:
            return "open"
        if fact.status == "received":
            return "done"
        if fact.status == "rejected":
            return "failed"
        return "open"
    if step.step_type == "inspection":
        if fact and fact.result == "passed":
            return "done"
        if fact and fact.result == "failed":
            return "failed"
        return "open"
    if step.step_type in ("movement", "resource"):
        return "done" if fact else "open"
    return "open"


def order_step_infos(db: Session, order: Order) -> list[dict]:
    """Schrittliste für den Auftrag-Stepper: state ∈ done|active|locked|failed.

    Jeder Eintrag trägt die ``id`` der Schritt-Definition (eindeutiger Schlüssel
    für das Routing mehrerer gleichartiger Schritte)."""
    if not order.article_id:
        return []
    infos: list[dict] = []
    active_assigned = False
    for d in step_defs(db, order.article_id):
        raw = _raw_status(db, order, d)
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
            "id": d.id,
            "step_type": d.step_type,
            "position": d.position,
            "label": STEP_LABELS.get(d.step_type, d.step_type),
            "state": state,
        })
    return infos


def step_state(db: Session, order: Order, step_id: int) -> str | None:
    """Zustand eines konkreten Schritts (über die Definition-id)."""
    for i in order_step_infos(db, order):
        if i["id"] == step_id:
            return i["state"]
    return None


def is_step_active(db: Session, order: Order, step_type: str) -> bool:
    """Ist (irgend)ein Schritt dieses Typs aktiv? (Typ-basierte Kurzform)"""
    return any(i["step_type"] == step_type and i["state"] == "active"
               for i in order_step_infos(db, order))


def active_step_of_type(db: Session, order: Order, step_type: str) -> ArticleProcessStep | None:
    """Die aktive Schritt-Definition des Typs (für die Ausführung ohne explizite id)."""
    for i in order_step_infos(db, order):
        if i["step_type"] == step_type and i["state"] == "active":
            return (
                db.query(ArticleProcessStep)
                .filter(ArticleProcessStep.id == i["id"])
                .first()
            )
    return None


def resolve_exec_step(db: Session, order: Order, step_type: str, step_id: int | None) -> ArticleProcessStep:
    """Auszuführenden Schritt bestimmen: explizite ``step_id`` (muss aktiv sein)
    oder die aktive Schritt-Definition des Typs. Wirft, wenn nicht ausführbar."""
    from fastapi import HTTPException
    label = STEP_LABELS.get(step_type, step_type)
    if step_id is not None:
        if step_state(db, order, step_id) != "active":
            raise HTTPException(409, detail=f"{label} ist (noch) nicht an der Reihe")
        step = (
            db.query(ArticleProcessStep)
            .filter(ArticleProcessStep.id == step_id, ArticleProcessStep.is_active == True)
            .first()
        )
        if not step or step.step_type != step_type:
            raise HTTPException(404, detail="Prozessschritt nicht gefunden")
        return step
    step = active_step_of_type(db, order, step_type)
    if not step:
        raise HTTPException(409, detail=f"{label} ist (noch) nicht an der Reihe")
    return step


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
        if order.completed_at is None:
            order.completed_at = utcnow()


def required_sample(quantity: int | None, sample_percent: int | None) -> int:
    """Zu prüfende Stückzahl der Eingangskontrolle (mind. 1, wenn Menge > 0)."""
    qty = quantity or 0
    pct = sample_percent if sample_percent is not None else 100
    if qty <= 0 or pct <= 0:
        return 0
    return min(qty, max(1, ceil(qty * pct / 100)))
