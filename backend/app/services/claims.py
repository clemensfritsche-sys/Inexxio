"""Geschäftslogik für Reklamationen (RMA).

Eine Reklamation ist ein eigenständiges Objekt mit eigener Nummer und bezieht
sich auf genau eine Instanz. Artikel- und Auftragsbezug werden aus der Instanz
abgeleitet. Reklamationen können manuell angelegt werden oder automatisch aus
einer fehlgeschlagenen Datenerfassung (Eingangskontrolle) entstehen.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Claim, Instance, Order, UserProfile
from ..schemas.claim import ClaimCreate, ClaimResponse
from .admin import log_audit
from .objects import next_object_id

# Inhaltliche Felder sind nur in offenen/angenommenen Reklamationen änderbar.
_TERMINAL_STATUS = ("closed", "rejected")
_LOCKED_ALLOWED = {"status", "is_active"}


def _user_name(u: UserProfile | None) -> str | None:
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def _article_object_id(db: Session, article_db_id: int | None) -> int | None:
    if not article_db_id:
        return None
    art = db.query(Article).filter(Article.id == article_db_id).first()
    return art.object_id if art else None


def _order_object_id(db: Session, order_db_id: int | None) -> int | None:
    if not order_db_id:
        return None
    o = db.query(Order).filter(Order.id == order_db_id).first()
    return o.object_id if o else None


def ensure_claim_mutable(status: str, payload: dict) -> None:
    """Abgeschlossene/abgelehnte Reklamationen sind inhaltlich gesperrt."""
    if status in _TERMINAL_STATUS and (set(payload) - _LOCKED_ALLOWED):
        raise HTTPException(
            409,
            detail="Reklamation ist abgeschlossen/abgelehnt – Inhalte können nicht mehr geändert werden",
        )


def to_claim_response(db: Session, claim: Claim) -> ClaimResponse:
    """ClaimResponse inkl. denormalisiertem Artikelnamen, Instanz-Infos und Melder."""
    resp = ClaimResponse.model_validate(claim)
    if claim.instance_object_id:
        inst = (
            db.query(Instance)
            .filter(Instance.object_id == claim.instance_object_id)
            .first()
        )
        if inst:
            resp.instance_kind = inst.kind
            resp.instance_qc_status = inst.qc_status
    if claim.article_object_id:
        art = db.query(Article).filter(Article.object_id == claim.article_object_id).first()
        if art:
            resp.article_name = art.name
    if claim.reported_by_id:
        resp.reported_by_name = _user_name(
            db.query(UserProfile).filter(UserProfile.id == claim.reported_by_id).first()
        )
    return resp


def create_claim(db: Session, data: ClaimCreate, actor: UserProfile) -> Claim:
    """Manuelle Anlage: Instanz nachschlagen, Bezug ableiten, Nummer vergeben."""
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == data.instance_object_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Instanz nicht gefunden")

    claim = Claim(
        object_id=next_object_id(db),
        status="open",
        direction=data.direction or "internal",
        instance_object_id=inst.object_id,
        article_object_id=_article_object_id(db, inst.article_id),
        order_object_id=_order_object_id(db, inst.order_id),
        reason=data.reason or "defect",
        title=data.title,
        description=data.description,
        quantity=data.quantity,
        resolution="none",
        source="manual",
        reported_by_id=actor.id,
    )
    db.add(claim)
    db.flush()
    log_audit(db, "claims", None, "Reklamation angelegt", actor.id, object_id=claim.object_id)
    db.commit()
    db.refresh(claim)
    return claim


def auto_claim_from_inspection(db: Session, order: Order, actor_id: int | None) -> Claim | None:
    """Bei fehlgeschlagener Datenerfassung automatisch eine interne Reklamation
    anlegen. Idempotent: pro Auftrag entsteht höchstens eine Inspektions-Reklamation.
    Schreibt nur (flush) – der Aufrufer committet die Transaktion."""
    existing = (
        db.query(Claim)
        .filter(
            Claim.order_object_id == order.object_id,
            Claim.source == "inspection",
            Claim.is_active == True,
        )
        .first()
    )
    if existing:
        return None

    insts = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )
    failed = [i for i in insts if i.qc_status == "failed"] or insts
    inst_obj = failed[0].object_id if failed else None

    claim = Claim(
        object_id=next_object_id(db),
        status="open",
        direction="internal",
        instance_object_id=inst_obj,
        article_object_id=_article_object_id(db, order.article_id),
        order_object_id=order.object_id,
        reason="defect",
        title="Eingangskontrolle nicht bestanden",
        description=(
            f"Automatisch erstellt: Die Datenerfassung des Auftrags "
            f"{order.object_id} ist fehlgeschlagen. Betroffene Ware ist gesperrt."
        ),
        resolution="none",
        source="inspection",
        reported_by_id=actor_id,
    )
    db.add(claim)
    db.flush()
    log_audit(db, "claims", None, "Reklamation automatisch aus Eingangskontrolle erstellt",
              actor_id, object_id=claim.object_id)
    return claim
