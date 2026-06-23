"""Hilfen rund um den Auftrag: Response-Aufbau (mit eingebettetem Prozess) und
rollenabhängige Sichtbarkeit (Lieferant sieht nur seine Aufträge)."""

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from ..models import (
    Article, ArticleProcessStep, AuditLog, CompanySettings, Inspection,
    Movement, Order, Process, PurchaseOrder, Sale, UserProfile,
)
from ..schemas.article_process_step import CaptureField
from ..schemas.inspection import InspectionEmbed, InspectionSample
from ..schemas.instance import InstanceEmbed
from ..schemas.movement import MovementEmbed
from ..schemas.order import OrderResponse, OrderStepInfo, OrderSummary
from ..schemas.purchase_order import PurchaseEmbed, PurchaseHistoryEntry
from ..schemas.sale import SaleEmbed
from . import process, processes
from .article_fields import normalize_shared_fields
from .inspection import eval_fields, required_count, sample_targets
from .locations import location_label, physical_location_label
from .resource import build_resource_embed
from .subject import order_instances

_STAFF_ROLES = ("admin", "employee")
# alte Statuswerte → verschlanktes Modell (für Audit-Verlauf)
_STATUS_ALIASES = {"approved": "ordered", "confirmed": "ordered"}


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


def _receiving_label(db: Session, po: PurchaseOrder) -> str | None:
    """Lieferadresse/Wareneingang: gesetzter Lagerort (nach Wareneingang) oder die
    in der Systemkonfiguration hinterlegte Vorgabe-Lieferadresse."""
    recv = po.receiving_location_id
    if not recv:
        st = db.query(CompanySettings).first()
        recv = st.default_receiving_location_id if st else None
    return location_label(db, "lagerplatz", recv) if recv else None


def _purchase_embed(db: Session, order: Order, step: ArticleProcessStep,
                    po: PurchaseOrder) -> PurchaseEmbed:
    emb = PurchaseEmbed.model_validate(po)
    if po.supplier_id:
        emb.supplier_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == po.supplier_id).first())
    emb.receiving_location_label = _receiving_label(db, po)
    emb.shared_fields = normalize_shared_fields(step.shared_fields if step else None)
    emb.history = _purchase_history(db, order)
    return emb


def _sale_embed(db: Session, order: Order, sale: Sale | None) -> SaleEmbed:
    """Verkaufs-Embed (Spiegel des Beschaffungs-Embeds)."""
    se = (SaleEmbed.model_validate(sale) if sale
          else SaleEmbed(id=0, status="requested"))
    if sale and sale.customer_id:
        se.customer_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == sale.customer_id).first())
    return se


def _inspection_embed(db: Session, order: Order, step: ArticleProcessStep,
                      insp: Inspection | None) -> InspectionEmbed:
    ie = (InspectionEmbed.model_validate(insp) if insp
          else InspectionEmbed(id=0, result="pending", checked_count=None, note=None))
    ie.sample_percent = step.sample_percent
    ie.required_count = required_count(db, order, step)
    ie.fields = [CaptureField(**f) for f in eval_fields(step)]
    stored = {(s.get("instance_id"), s.get("slot", 1)): (s.get("values") or {})
              for s in (insp.samples or [])} if insp else {}
    ie.samples = [
        InspectionSample(instance_id=t["instance_id"], slot=t["slot"],
                         values=stored.get((t["instance_id"], t["slot"]), {}))
        for t in sample_targets(db, order, step)
    ]
    if insp and insp.inspector_id:
        ie.inspector_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == insp.inspector_id).first())
    return ie


def _movement_embed(db: Session, order: Order, step: ArticleProcessStep,
                    mv: Movement | None) -> MovementEmbed:
    me = MovementEmbed(id=mv.id if mv else 0, done=mv is not None, note=mv.note if mv else None)
    me.target_location_type = step.target_location_type
    me.target_location_id = step.target_location_id
    me.target_location_label = location_label(db, step.target_location_type, step.target_location_id)
    if mv and mv.moved_by_id:
        me.moved_by_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == mv.moved_by_id).first())
    return me


def _purchase_received(po_embed: PurchaseEmbed) -> tuple[str | None, object]:
    """Wer/Wann den Wareneingang bestätigt hat (aus dem Bestell-Verlauf)."""
    for h in po_embed.history:
        if h.status == "received":
            return h.by, h.at
    return None, None


def to_order_response(db: Session, order: Order) -> OrderResponse:
    """OrderResponse inkl. denormalisiertem Artikel, Instanzen und – pro Schritt –
    dem passenden Ausführungs-Embed (Mehr-Operationen-Routing)."""
    resp = OrderResponse.model_validate(order)
    # Vorgänger (Ersetzen-Kette): wessen Nachfolger ist dieser Auftrag?
    if order.object_id:
        pred = db.query(Order.object_id).filter(Order.replaced_by_id == order.object_id).first()
        resp.replaces_id = pred[0] if pred else None
    if order.article_id:
        art = db.query(Article).filter(Article.id == order.article_id).first()
        if art:
            resp.article_name = art.name
            resp.article_object_id = art.object_id
            resp.article_size = art.size
            resp.article_unit = art.unit
            resp.article_weight_kg = art.weight_kg
            resp.article_serialization = art.serialization
            resp.article_supplier_article_number = art.supplier_article_number

    # Prozess-Info (welcher Prozess kommt zur Anwendung + Subjekt-Quelle).
    proc = processes.process_for_order(db, order)
    if proc:
        resp.process_id = proc.id
        resp.process_name = proc.name
        resp.process_source = proc.source
        resp.process_object_id = proc.object_id
    resp.subject_instance_id = order.subject_instance_id

    # Subjekt-Instanzen: worauf der Auftrag wirkt (produce/stock/instance einheitlich).
    instances = order_instances(db, order)
    instance_embeds: list[InstanceEmbed] = []
    for i in instances:
        emb = InstanceEmbed.model_validate(i)
        emb.location_label = location_label(db, i.location_type, i.location_id)
        if i.location_type == "instance":
            emb.physical_location_label = physical_location_label(db, i.location_type, i.location_id)
        instance_embeds.append(emb)
    resp.instances = instance_embeds

    # Auftrag-Stepper: je Schritt der passende Ausführungs-Embed + Abschluss-Info.
    # Das oberste Embed je Typ bleibt für Rückwärtskompatibilität (Lieferanten-Sicht)
    # zusätzlich gesetzt.
    steps: list[OrderStepInfo] = []
    first: dict[str, object] = {}
    # build_order_steps lädt Definitionen + Fachzeilen je EINMAL und liefert die
    # aufgelöste Fachzeile gleich mit (kein erneutes Nachladen je Schritt).
    for s in process.build_order_steps(db, order):
        step = s["step"]
        fact = s["fact"]
        si = OrderStepInfo(id=s["id"], step_type=s["step_type"], position=s["position"],
                           label=s["label"], state=s["state"])
        done = s["state"] == "done"
        by_name: str | None = None
        at = None
        if step.step_type == "purchase" and fact:
            emb = _purchase_embed(db, order, step, fact)
            si.purchase = emb
            first.setdefault("purchase", emb)
            if done:
                by_name, at = _purchase_received(emb)
        elif step.step_type == "sale":
            emb = _sale_embed(db, order, fact)
            si.sale = emb
            first.setdefault("sale", emb)
            if done and fact:
                by_name, at = emb.customer_name, fact.paid_at
        elif step.step_type == "inspection":
            emb = _inspection_embed(db, order, step, fact)
            si.inspection = emb
            first.setdefault("inspection", emb)
            if done:
                by_name, at = emb.inspector_name, (fact.updated_at if fact else None)
        elif step.step_type == "movement":
            emb = _movement_embed(db, order, step, fact)
            si.movement = emb
            first.setdefault("movement", emb)
            if done:
                by_name, at = emb.moved_by_name, (fact.updated_at if fact else None)
        elif step.step_type == "resource":
            emb = build_resource_embed(db, order, step, usage=fact)
            si.resource = emb
            first.setdefault("resource", emb)
            if done and emb:
                by_name, at = emb.used_by_name, (fact.updated_at if fact else None)
        if done:
            si.completed_by = by_name
            si.completed_at = at
        steps.append(si)

    resp.steps = steps
    resp.purchase = first.get("purchase")          # Lieferanten-Sicht / Kurzform
    resp.sale = first.get("sale")
    resp.inspection = first.get("inspection")
    resp.movement = first.get("movement")
    resp.resource = first.get("resource")
    return resp


def to_order_summaries(db: Session, orders: list[Order]) -> list[OrderSummary]:
    """Schlanke Feed-Sicht – Artikel-Infos und Beschaffungsstatus **batch**-geladen
    (zwei Zusatz-Queries für die ganze Liste statt je Auftrag ein Embed-Aufbau)."""
    if not orders:
        return []
    art_ids = {o.article_id for o in orders if o.article_id}
    arts = {a.id: a for a in db.query(Article).filter(Article.id.in_(art_ids)).all()} if art_ids else {}
    order_ids = [o.id for o in orders]
    po_status: dict[int, str] = {}
    for po in (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id.in_(order_ids), PurchaseOrder.is_active == True)
        .all()
    ):
        po_status[po.order_id] = po.status
    proc_ids = {o.process_id for o in orders if o.process_id}
    procs = ({p.id: p for p in db.query(Process).filter(Process.id.in_(proc_ids)).all()}
             if proc_ids else {})
    out: list[OrderSummary] = []
    for o in orders:
        s = OrderSummary.model_validate(o)
        art = arts.get(o.article_id)
        if art:
            s.article_name = art.name
            s.article_object_id = art.object_id
            s.article_unit = art.unit
        s.purchase_status = po_status.get(o.id)
        p = procs.get(o.process_id)
        if p:
            s.process_name = p.name
            s.process_source = p.source
        out.append(s)
    return out


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
