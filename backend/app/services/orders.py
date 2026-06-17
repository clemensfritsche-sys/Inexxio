"""Hilfen rund um den Auftrag: Response-Aufbau (mit eingebettetem Prozess) und
rollenabhängige Sichtbarkeit (Lieferant sieht nur seine Aufträge)."""

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from ..models import (
    Article, ArticleProcessStep, AuditLog, Inspection, Instance, Movement, Order,
    PurchaseOrder, UserProfile,
)
from ..schemas.article_process_step import CaptureField
from ..schemas.inspection import InspectionEmbed, InspectionSample
from ..schemas.instance import InstanceEmbed
from ..schemas.movement import MovementEmbed
from ..schemas.order import OrderResponse, OrderStepInfo
from ..schemas.purchase_order import PurchaseEmbed, PurchaseHistoryEntry
from . import process
from .article_fields import normalize_shared_fields
from .inspection import eval_fields, required_count, sample_targets
from .locations import location_label

_STAFF_ROLES = ("admin", "employee")
# alte Statuswerte → verschlanktes Modell (für Audit-Verlauf)
_STATUS_ALIASES = {"approved": "ordered", "confirmed": "ordered"}


def _purchase_shared_fields(db: Session, article_id: int) -> list[str]:
    """Vom purchase-Schritt des Artikels freigegebene Stammdaten (Pflicht inkl.)."""
    step = (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article_id,
            ArticleProcessStep.step_type == "purchase",
            ArticleProcessStep.is_active == True,
        )
        .order_by(ArticleProcessStep.id)
        .first()
    )
    return normalize_shared_fields(step.shared_fields if step else None)


def _supplier_name(u: UserProfile | None) -> str | None:
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def _purchase_history(db: Session, order: Order) -> list[PurchaseHistoryEntry]:
    """Audit-Verlauf der Bestellung (Statuswechsel mit Wer/Wann) für den Stepper."""
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.object_id == order.object_id, AuditLog.table_name == "purchase_orders")
        .order_by(AuditLog.changed_at_utc)
        .all()
    )
    names: dict[int, str | None] = {}
    out: list[PurchaseHistoryEntry] = []
    for lg in logs:
        if lg.field_name == "status":
            status = lg.new_value
        elif lg.field_name is None:
            status = "requested"   # Anlage = «Angefragt»
        else:
            continue
        if not status:
            continue
        status = _STATUS_ALIASES.get(status, status)
        if lg.user_id is not None and lg.user_id not in names:
            names[lg.user_id] = _supplier_name(
                db.query(UserProfile).filter(UserProfile.id == lg.user_id).first()
            )
        out.append(PurchaseHistoryEntry(
            status=status, at=lg.changed_at_utc,
            by=names.get(lg.user_id) if lg.user_id is not None else None,
        ))
    return out


def to_order_response(db: Session, order: Order) -> OrderResponse:
    """OrderResponse inkl. denormalisiertem Artikel und eingebettetem Beschaffungsschritt."""
    resp = OrderResponse.model_validate(order)
    if order.article_id:
        art = db.query(Article).filter(Article.id == order.article_id).first()
        if art:
            resp.article_name = art.name
            resp.article_object_id = art.object_id
            resp.article_size = art.size
            resp.article_unit = art.unit
            resp.article_weight_kg = art.weight_kg
            resp.article_serialization = art.serialization
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .first()
    )
    if po:
        emb = PurchaseEmbed.model_validate(po)
        if po.supplier_id:
            emb.supplier_name = _supplier_name(
                db.query(UserProfile).filter(UserProfile.id == po.supplier_id).first()
            )
        if order.article_id:
            emb.shared_fields = _purchase_shared_fields(db, order.article_id)
        emb.history = _purchase_history(db, order)
        resp.purchase = emb

    # Serialisierung: erzeugte Instanzen (inkl. aktuellem Standort)
    instances = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )
    instance_embeds: list[InstanceEmbed] = []
    for i in instances:
        emb = InstanceEmbed.model_validate(i)
        emb.location_label = location_label(db, i.location_type, i.location_id)
        instance_embeds.append(emb)
    resp.instances = instance_embeds

    # Datenerfassung: Embed sobald der Schritt definiert ist (auch ohne Erfassung,
    # damit Prüfumfang + konkrete Stichproben vorab sichtbar sind)
    insp_step = _step(db, order.article_id, "inspection")
    if insp_step:
        insp = (
            db.query(Inspection)
            .filter(Inspection.order_id == order.id, Inspection.is_active == True)
            .first()
        )
        ie = (InspectionEmbed.model_validate(insp) if insp
              else InspectionEmbed(id=0, result="pending", checked_count=None, note=None))
        ie.sample_percent = insp_step.sample_percent
        ie.required_count = required_count(db, order)
        ie.fields = [CaptureField(**f) for f in eval_fields(insp_step)]
        # Konkrete Stichproben (Instanz + Probe-Nr.) inkl. bereits erfasster Werte
        stored = {(s.get("instance_id"), s.get("slot", 1)): (s.get("values") or {})
                  for s in (insp.samples or [])} if insp else {}
        ie.samples = [
            InspectionSample(instance_id=t["instance_id"], slot=t["slot"],
                             values=stored.get((t["instance_id"], t["slot"]), {}))
            for t in sample_targets(db, order)
        ]
        if insp and insp.inspector_id:
            ie.inspector_name = _supplier_name(
                db.query(UserProfile).filter(UserProfile.id == insp.inspector_id).first()
            )
        resp.inspection = ie

    # Bewegung: Embed sobald der Schritt definiert ist (Vorgabe-Ziel + Abschluss)
    mv_step = _step(db, order.article_id, "movement")
    if mv_step:
        mv = (
            db.query(Movement)
            .filter(Movement.order_id == order.id, Movement.is_active == True)
            .first()
        )
        me = MovementEmbed(id=mv.id if mv else 0, done=mv is not None,
                           note=mv.note if mv else None)
        me.target_location_type = mv_step.target_location_type
        me.target_location_id = mv_step.target_location_id
        me.target_location_label = location_label(
            db, mv_step.target_location_type, mv_step.target_location_id)
        if mv and mv.moved_by_id:
            me.moved_by_name = _supplier_name(
                db.query(UserProfile).filter(UserProfile.id == mv.moved_by_id).first()
            )
        resp.movement = me

    # Auftrag-Stepper
    resp.steps = [OrderStepInfo(**i) for i in process.order_step_infos(db, order)]
    return resp


def _step(db: Session, article_id: int | None, step_type: str) -> ArticleProcessStep | None:
    if not article_id:
        return None
    return (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article_id,
            ArticleProcessStep.step_type == step_type,
            ArticleProcessStep.is_active == True,
        )
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .first()
    )


def visible_orders(db: Session, user: UserProfile) -> Query:
    """Mitarbeiter/Admin sehen alle Aufträge, Lieferanten nur ihre, sonst keine."""
    q = db.query(Order).filter(Order.is_active == True)
    if user.role in _STAFF_ROLES:
        return q
    if user.role == "supplier":
        sub = (
            db.query(PurchaseOrder.order_id)
            .filter(PurchaseOrder.supplier_id == user.id, PurchaseOrder.is_active == True)
        )
        return q.filter(Order.id.in_(sub))
    return q.filter(false())
