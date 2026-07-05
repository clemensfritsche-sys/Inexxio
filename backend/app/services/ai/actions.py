"""Vorschlagen ≠ Ausführen (ADR 004): kritische KI-Aktionen mit menschlichem Gate.

Die KI legt für kritische Vorgänge einen ``AiAction``-Vorschlag an; der Mensch
bestätigt ihn im Chat. Erst die Bestätigung führt den **echten, autorisierten
Service-Pfad** aus – exakt einmal (Idempotenz über den Status: ein zweiter Klick
liefert das vorhandene Ergebnis statt einer Doppel-Ausführung). Ablehnung ist
gleichwertig dokumentiert. Alles landet im Audit-Log + Event-Strom."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...models import AiAction, Order, UserProfile
from ..admin import log_audit
from ..events import emit
from .principal import AiPrincipal

# Kritische Aktionstypen und ihre Ausführung über die bestehenden Service-Pfade.
CRITICAL_ACTIONS = ("release_order", "release_article")


def create_proposal(db: Session, p: AiPrincipal, action_type: str, *,
                    payload: dict, summary: str, target_object_id: int | None) -> AiAction:
    action = AiAction(
        action_type=action_type,
        summary=summary[:500],
        payload=payload,
        status="proposed",
        proposed_by_ai_id=p.actor.id,
        requested_by_id=p.on_behalf_of.id if p.on_behalf_of else None,
        target_object_id=target_object_id,
    )
    db.add(action)
    db.flush()
    emit(db, "ai.action_proposed", object_type="ai_action", object_id=target_object_id,
         payload={"action_id": action.id, "action_type": action_type, "summary": action.summary},
         actor_id=p.actor.id)
    db.commit()
    db.refresh(action)
    return action


def _get(db: Session, action_id: int) -> AiAction:
    action = db.query(AiAction).filter(AiAction.id == action_id, AiAction.is_active == True).first()
    if not action:
        raise HTTPException(404, detail="KI-Vorschlag nicht gefunden")
    return action


def _execute_release_order(db: Session, action: AiAction, ai_actor_id: int) -> int | None:
    from ..orders import release_order
    oid = int((action.payload or {}).get("object_id"))
    order = db.query(Order).filter(Order.object_id == oid, Order.is_active == True).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht mehr vorhanden")
    if order.status != "draft":
        raise HTTPException(409, detail=f"Auftrag ist inzwischen '{order.status}' – Vorschlag hinfällig")
    release_order(db, order, actor_id=ai_actor_id)
    return order.object_id


def _execute_release_article(db: Session, action: AiAction, ai_actor_id: int) -> int | None:
    from ...models import Article
    from ..processes import article_steps
    oid = int((action.payload or {}).get("object_id"))
    a = db.query(Article).filter(Article.object_id == oid, Article.is_active == True).first()
    if not a:
        raise HTTPException(404, detail="Artikel nicht mehr vorhanden")
    if a.status != "draft":
        raise HTTPException(409, detail=f"Artikel ist inzwischen '{a.status}' – Vorschlag hinfällig")
    if not article_steps(db, a.id):
        raise HTTPException(400, detail="Artikel hat keinen Prozessschritt – nicht freigebbar")
    log_audit(db, "articles", "status", "released", ai_actor_id, object_id=a.object_id, old_value="draft")
    a.status = "released"
    return a.object_id


_EXECUTORS = {
    "release_order": _execute_release_order,
    "release_article": _execute_release_article,
}


def confirm(db: Session, action_id: int, user: UserProfile) -> AiAction:
    """Menschliche Bestätigung → Ausführung über den autorisierten Pfad (einmalig)."""
    action = _get(db, action_id)
    if action.status == "executed":
        return action                      # idempotent: Doppelklick ≠ Doppel-Ausführung
    if action.status != "proposed":
        raise HTTPException(409, detail=f"Vorschlag ist bereits '{action.status}'")
    executor = _EXECUTORS.get(action.action_type)
    if not executor:
        raise HTTPException(400, detail=f"Unbekannter Aktionstyp '{action.action_type}'")
    try:
        result_oid = executor(db, action, action.proposed_by_ai_id)
    except HTTPException as e:
        action.status = "failed"
        action.error = str(e.detail)
        action.decided_by_id = user.id
        action.decided_at = datetime.now(timezone.utc)
        db.commit()
        raise
    action.status = "executed"
    action.decided_by_id = user.id
    action.decided_at = datetime.now(timezone.utc)
    action.target_object_id = result_oid or action.target_object_id
    log_audit(db, "ai_actions", "status", "executed", user.id,
              object_id=action.target_object_id, old_value="proposed")
    emit(db, "ai.action_executed", object_type="ai_action", object_id=action.target_object_id,
         payload={"action_id": action.id, "action_type": action.action_type,
                  "confirmed_by": user.id},
         actor_id=action.proposed_by_ai_id)
    db.commit()
    db.refresh(action)
    return action


def reject(db: Session, action_id: int, user: UserProfile) -> AiAction:
    action = _get(db, action_id)
    if action.status == "rejected":
        return action
    if action.status != "proposed":
        raise HTTPException(409, detail=f"Vorschlag ist bereits '{action.status}'")
    action.status = "rejected"
    action.decided_by_id = user.id
    action.decided_at = datetime.now(timezone.utc)
    log_audit(db, "ai_actions", "status", "rejected", user.id,
              object_id=action.target_object_id, old_value="proposed")
    emit(db, "ai.action_rejected", object_type="ai_action", object_id=action.target_object_id,
         payload={"action_id": action.id, "action_type": action.action_type},
         actor_id=action.proposed_by_ai_id)
    db.commit()
    db.refresh(action)
    return action
