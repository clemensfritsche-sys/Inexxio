"""Hilfen rund um den Auftrag: Response-Aufbau (mit eingebettetem Prozess) und
rollenabhängige Sichtbarkeit (Lieferant sieht nur seine Aufträge)."""

from datetime import date, timedelta

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from ..domain import event_types
from ..models import (
    Article, ArticleProcessStep, AuditLog, CompanySettings, Disposal, Inspection,
    InstanceOrderLink, Movement, Order, PurchaseOrder, Sale, UserProfile,
)
from ..schemas.article_process_step import CaptureField
from ..schemas.disposal import DisposalEmbed
from ..schemas.document import DocumentEmbed
from ..schemas.inspection import InspectionEmbed, InspectionSample
from ..schemas.instance import InstanceEmbed
from ..schemas.movement import MovementEmbed
from ..schemas.order import (
    OrderDeviationInfo, OrderLineInfo, OrderResponse, OrderStepInfo, OrderSummary,
    ShortfallInstance, StepShortfall,
)
from ..schemas.purchase_order import PurchaseEmbed, PurchaseHistoryEntry
from ..models.base import utcnow
from ..schemas.sale import SaleEmbed
from . import process
from .article_fields import normalize_shared_fields
from .inspection import eval_fields, required_count, sample_targets
from .locations import location_label, location_labels, physical_location_labels
from .resource import build_resource_embed
from .subject import order_instances, subject_kind

_STAFF_ROLES = ("admin", "employee")


def release_order(db: Session, order: Order, actor_id: int | None) -> None:
    """**Einheitliche Auftrags-Freigabe** (draft → released) – EIN Pfad für ERP-Freigabe,
    Shop-Zahlung und Nachschub (kein Sonderpfad):

    Subjekt herstellen (``materialize_subject``: produce erzeugt Instanzen | stock reserviert
    FIFO, **ggf. nur teilweise** | deviation bindet die gewählten Instanzen), Beschaffung +
    Verkauf instanziieren, Komponenten reservieren, Freigabe-Event. Idempotent (No-op, wenn
    nicht im Entwurf). Committet NICHT.

    Eine **Fehlmenge** (Subjekt/Komponente) ist KEIN Fehler mehr – der betroffene Schritt ist
    danach «blockiert» und wird über einen Nachschub-Unter-Auftrag gedeckt (``services/supply``)."""
    from . import deviation, document as document_svc, process, sale as sale_svc, subject
    from .events import emit as _emit
    from .purchase import instantiate_for_order as instantiate_purchase
    from .resource import reserve_resources
    if order.status != "draft":
        return
    order.status = "released"
    if order.released_at is None:
        order.released_at = utcnow()   # Start der Durchlaufzeit
    subject.materialize_subject(db, order, actor_id)
    instantiate_purchase(db, order, actor_id)        # Beschaffungs-Schritte → Bestellungen
    sale_svc.instantiate_for_order(db, order, actor_id)  # Verkaufs-Schritte → Belege
    document_svc.instantiate_for_order(db, order, actor_id)  # Dokument-Schritte → leere Fachzeile (wird ausgeführt)
    reserve_resources(db, order, actor_id)           # Komponenten mengengenau reservieren
    _emit(db, "order.released", object_type="order", object_id=order.object_id,
          payload={"article_id": order.article_id, "quantity": order.quantity}, actor_id=actor_id)
    # Abbruch-Folgeauftrag: mit seiner Freigabe das Original endgültig abbrechen (self-guard;
    # No-op für normale Aufträge und Nachschub).
    if order.parent_order_id is not None:
        deviation.apply_abort_on_release(db, order, actor_id)
    # Abschluss neu bewerten: Schritte, die schon bei der Freigabe «done» sind (das eingefrorene
    # Dokument), schliessen den Auftrag sofort ab. No-op für Aufträge mit noch offenen Schritten
    # (Beschaffung/Verkauf starten in 'requested', also nicht «done»).
    process.recompute_completion(db, order)


def recurrence_due(order: Order) -> bool:
    """Wiederkehrender Auftrag (Entwurf) ist «fällig», wenn Termin − Vorlaufzeit
    erreicht ist (oder kein Termin gesetzt). Für das Feed-Badge."""
    if not getattr(order, "recurrence_active", False) or order.status != "draft":
        return False
    if order.recurrence_anchor is None:
        return True
    return (order.recurrence_anchor - timedelta(days=order.recurrence_lead_time_days or 0)) <= date.today()


def _supplier_name(u: UserProfile | None) -> str | None:
    return u.display_name if u else None


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
                    po: PurchaseOrder, history: list[PurchaseHistoryEntry] | None = None) -> PurchaseEmbed:
    emb = PurchaseEmbed.model_validate(po)
    if po.supplier_id:
        emb.supplier_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == po.supplier_id).first())
    emb.receiving_location_label = _receiving_label(db, po)
    emb.shared_fields = normalize_shared_fields(step.shared_fields if step else None)
    # Der Verlauf ist je AUFTRAG identisch (Audit nach Auftragsnummer) – bei mehreren
    # Bestellungen einmal berechnen und hereinreichen statt je Position neu zu scannen.
    emb.history = history if history is not None else _purchase_history(db, order)
    # Artikel dieser Position denormalisieren – bei einem Mehrpositionen-Auftrag trägt
    # jede Bestellung einen ANDEREN Artikel (``order.article_id`` ist dann NULL).
    if po.article_id:
        art = db.query(Article).filter(Article.id == po.article_id).first()
        if art:
            emb.article_object_id = art.object_id
            emb.article_name = art.name
            # FIX: Die «Für Lieferant sichtbar»-Karte las die Stammdaten vom AUFTRAG – bei
            # einem Mehrpositionen-Auftrag (order.article_* = NULL) war jede Spezifikation
            # leer («—»). Die Werte gehören zur POSITION (jede Bestellung ein anderer Artikel).
            emb.article_unit = art.unit
            emb.article_size = art.size
            emb.article_weight_kg = art.weight_kg
            emb.article_serialization = art.serialization
            emb.article_supplier_article_number = art.supplier_article_number
    return emb


def _sale_embed(db: Session, order: Order, sale: Sale | None) -> SaleEmbed:
    """Verkaufs-Embed (Spiegel des Beschaffungs-Embeds)."""
    se = (SaleEmbed.model_validate(sale) if sale
          else SaleEmbed(id=0, status="requested"))
    if sale and sale.customer_id:
        se.customer_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == sale.customer_id).first())
    # Artikel dieser Position denormalisieren – bei einem Mehrpositionen-Auftrag trägt
    # jeder Sale-Beleg einen ANDEREN Artikel (``order.article_id`` ist dann NULL).
    art_id = sale.article_id if sale else order.article_id
    if art_id:
        art = db.query(Article).filter(Article.id == art_id).first()
        if art:
            se.article_object_id = art.object_id
            se.article_name = art.name
    # Fehlte der Preis bei der Freigabe (Artikel noch ohne Preis) und wurde er NACHTRÄGLICH
    # hinterlegt, zeigt das Embed den ableitbaren Betrag als Vorschau – so ist der Verkauf im
    # Panel nicht mehr blockiert (die Bestätigung zieht ihn dann fest, siehe sale._apply_transition).
    if sale and sale.order_total is None and art_id and sale.status not in ("paid", "cancelled"):
        from .sale import price_from_article
        view = price_from_article(db, art_id, sale.quantity)
        if view:
            se.order_total = view["order_total"]
            se.vat_rate = view["vat_rate"]
            se.currency = view["currency"]
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
    me.mode = step.mode                      # 'customer' = Pflicht-Versand (nur dann sold bewegbar)
    me.target_location_type = step.target_location_type
    me.target_location_id = step.target_location_id
    # **Pflicht-Versand zum Kunden** (mode='customer'): das Ziel ist NICHT frei wählbar, sondern
    # FIX der Kunde des Verkaufs. So erzwingt das Panel (fester Zielort) die richtige Person UND
    # muss keine Lagerplatz-/Personen-Listen laden (schnell). Fällt der Kunde noch (Verkauf nicht
    # bestätigt), bleibt das Ziel offen – die Bewegung ist ohnehin erst nach dem Verkauf aktiv.
    if step.mode == "customer":
        from .sale import customer_for_order
        cust = customer_for_order(db, order)
        if cust:
            me.target_location_type = "user"
            me.target_location_id = cust.object_id
    me.target_location_label = location_label(db, me.target_location_type, me.target_location_id)
    if mv and mv.moved_by_id:
        me.moved_by_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == mv.moved_by_id).first())
    return me


def _disposal_embed(db: Session, order: Order, disp: Disposal | None,
                    scrapped_count: int) -> DisposalEmbed:
    de = DisposalEmbed(id=disp.id if disp else 0, done=disp is not None,
                       note=disp.note if disp else None, scrapped_count=scrapped_count)
    if disp and disp.scrapped_by_id:
        de.scrapped_by_name = _supplier_name(
            db.query(UserProfile).filter(UserProfile.id == disp.scrapped_by_id).first())
    return de


def _document_embed(db: Session, order: Order, step: ArticleProcessStep,
                    doc) -> DocumentEmbed:
    """Eingebetteter Stand des Dokument-Schritts. Der Inhalt wird während der Ausführung
    verfasst; Nummer (= Instanz-Objektnummer) und Datum (= Instanz-Freigabe) kommen aus der
    vom Auftrag erzeugten Instanz. Vor der Freigabe existiert noch keine Fachzeile → leerer,
    editierbarer Entwurf."""
    from .document import creator_name, normalize_content, render_meta
    obj_nr, doc_date = render_meta(db, order)
    if doc is not None:
        emb = DocumentEmbed.model_validate(doc)   # coerce content (dict) → DocumentContent
        emb.created_by_name = creator_name(db, doc)
        emb.object_number = obj_nr
        emb.document_date = doc_date
        return emb
    return DocumentEmbed(
        id=0, done=False, content=normalize_content(None),
        object_number=obj_nr, document_date=doc_date,
    )


def _purchase_received(po_embed: PurchaseEmbed) -> tuple[str | None, object]:
    """Wer/Wann den Wareneingang bestätigt hat (aus dem Bestell-Verlauf)."""
    for h in po_embed.history:
        if h.status == "received":
            return h.by, h.at
    return None, None


def _order_sub_orders(db: Session, order: Order) -> tuple[list[OrderDeviationInfo], list[OrderDeviationInfo], list[OrderDeviationInfo], bool]:
    """Unter-Aufträge eines Auftrags, getrennt nach Grund: **Abweichungen** (pausieren den
    Eltern), **Nachschub** (deckt Bedarf, blockiert nur Schritte), **Retouren** (Rücknahme +
    Gutschrift eines abgeschlossenen Verkaufs, pausieren NICHT) + Pause-Zustand."""
    if not order.object_id:
        return [], [], [], False
    children = (
        db.query(Order)
        .filter(Order.parent_order_id == order.object_id, Order.is_active == True)
        .order_by(Order.object_id)
        .all()
    )
    deviations: list[OrderDeviationInfo] = []
    supplies: list[OrderDeviationInfo] = []
    returns: list[OrderDeviationInfo] = []
    for c in children:
        ids = [
            row[0] for row in
            db.query(InstanceOrderLink.instance_object_id)
            .filter(InstanceOrderLink.order_id == c.id, InstanceOrderLink.is_active == True)
            .all()
        ]
        info = OrderDeviationInfo(
            object_id=c.object_id, status=c.status, reason=c.reason, instance_count=len(ids),
            instance_object_ids=ids, title=c.title)
        bucket = supplies if c.reason == "supply" else returns if c.reason == "return" else deviations
        bucket.append(info)
    return deviations, supplies, returns, process._is_paused_by_deviation(db, order)


def _fill_step_shortfall(db: Session, order: Order, step: ArticleProcessStep, si: OrderStepInfo) -> None:
    """Einen blockierten Schritt mit seinen Fehlmengen (Artikel + Menge) und den laufenden
    Nachschub-Unteraufträgen anreichern (für «Nachschub anlegen» / Verlinkung im Frontend)."""
    shortfalls = process.step_shortfalls(db, order, step)
    if not shortfalls:
        return
    from .inventory import fifo_candidates
    from .reservation import free_qty

    arts = {a.id: a for a in db.query(Article).filter(Article.id.in_(shortfalls.keys())).all()}
    si.shortfall = []
    for aid, qty in shortfalls.items():
        # Freie, freigegebene Instanzen dieses Artikels am Lager – womit sich der Bedarf ohne
        # Nachschub decken liesse («Aus Lager decken» / «Andere Instanz wählen»).
        free = [c for c in fifo_candidates(db, aid, for_order_id=None) if free_qty(c) > 0]
        si.shortfall.append(StepShortfall(
            article_object_id=(arts[aid].object_id if aid in arts else None),
            article_name=(arts[aid].name if aid in arts else None), quantity=qty,
            available_quantity=sum(free_qty(c) for c in free),
            available_instances=[
                ShortfallInstance(object_id=c.object_id, quantity=free_qty(c))
                for c in free if c.object_id is not None
            ],
        ))
    si.supply_order_object_ids = [
        r[0] for r in
        db.query(Order.object_id).filter(
            Order.parent_order_id == order.object_id, Order.reason == "supply",
            Order.is_active == True, Order.status.in_(("draft", "released")),
            Order.article_id.in_(shortfalls.keys()))
        .all()
    ]


def to_order_response(db: Session, order: Order) -> OrderResponse:
    """OrderResponse inkl. denormalisiertem Artikel, Instanzen und – pro Schritt –
    dem passenden Ausführungs-Embed (Mehr-Operationen-Routing)."""
    resp = OrderResponse.model_validate(order)
    resp.deviations, resp.supply_orders, resp.returns, resp.paused = _order_sub_orders(db, order)
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
    else:
        # Mehrpositionen-Auftrag: kein einzelner Artikel – die Positionen stehen einzeln.
        from .order_lines import lines_for
        lines = lines_for(db, order)
        arts = {a.id: a for a in db.query(Article).filter(
            Article.id.in_({l.article_id for l in lines})).all()} if lines else {}
        resp.order_lines = [
            OrderLineInfo(
                id=l.id, article_id=l.article_id, quantity=l.quantity, position=l.position,
                article_object_id=arts[l.article_id].object_id if l.article_id in arts else None,
                article_name=arts[l.article_id].name if l.article_id in arts else None,
                article_unit=arts[l.article_id].unit if l.article_id in arts else None,
            )
            for l in lines
        ]

    resp.recurrence_due = recurrence_due(order)

    # Subjekt-Instanzen: worauf der Auftrag wirkt (MAKE: erzeugt | CUSTOM: ausgewählt).
    # Standort-Labels **batch** auflösen (statt einem Query je Instanz, N+1).
    instances = order_instances(db, order)
    loc_keys = [(i.location_type, i.location_id) for i in instances]
    loc_labels = location_labels(db, loc_keys)
    phys_labels = physical_location_labels(db, [k for k in loc_keys if k[0] == "instance"])
    instance_embeds: list[InstanceEmbed] = []
    for i in instances:
        emb = InstanceEmbed.model_validate(i)
        emb.location_label = loc_labels.get((i.location_type, i.location_id))
        if i.location_type == "instance":
            emb.physical_location_label = phys_labels.get((i.location_type, i.location_id))
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
        if s["state"] == "blocked":
            _fill_step_shortfall(db, order, step, si)
        done = s["state"] == "done"
        by_name: str | None = None
        at = None
        if step.step_type == "purchase":
            # EIN Schritt kann mehrere Bestellungen tragen (ein Artikel/Position je
            # Bestellung, Mehrpositionen-Auftrag) – ``purchases`` ist die vollständige
            # Liste, ``purchase`` bleibt das erste Embed (Rückwärtskompatibilität; beim
            # Einzel-Artikel-Auftrag identisch).
            facts = s["facts"]
            hist = _purchase_history(db, order) if facts else None
            embs = [_purchase_embed(db, order, step, f, history=hist) for f in facts]
            if embs:
                si.purchases = embs
                si.purchase = embs[0]
                first.setdefault("purchase", embs[0])
                if done:
                    by_name, at = _purchase_received(embs[0])
        elif step.step_type == "sale":
            # EIN `sale`-Schritt, ZWEI Modi (aus dem Subjekt abgeleitet): Verkauf (kind='sale')
            # oder Gutschrift/Erstattung (kind='credit', Retoure). Mehrere Belege je Artikel/
            # Position teilen sich den Schritt – ``sales`` ist die vollständige Liste.
            facts = s["facts"]
            embs = [_sale_embed(db, order, f) for f in facts] or [_sale_embed(db, order, None)]
            si.sales = embs
            si.sale = embs[0]
            first.setdefault("sale", embs[0])
            if done and facts:
                by_name = embs[0].customer_name
                at = max((f.paid_at for f in facts if f.paid_at), default=None)
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
        elif step.step_type == "scrap":
            scrapped_count = sum(1 for i in instances if i.disposition == "scrapped")
            emb = _disposal_embed(db, order, fact, scrapped_count)
            si.disposal = emb
            first.setdefault("disposal", emb)
            if done:
                by_name, at = emb.scrapped_by_name, (fact.updated_at if fact else None)
        elif step.step_type == "document":
            emb = _document_embed(db, order, step, fact)
            si.document = emb
            first.setdefault("document", emb)
            if done:
                by_name, at = emb.created_by_name, (fact.updated_at if fact else None)
        elif step.step_type in process.RESOURCE_STEP_TYPES:
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
    # Subjektart aus der Auftragsgestalt (produce | stock) und Bestandswirkung als
    # Aggregat der Schritt-Polaritäten – EINE Quelle der Wahrheit (REA-Registry).
    resp.subject_role = subject_kind(db, order)
    resp.stock_effect = event_types.aggregate_stock_effect({s.step_type for s in steps})
    resp.purchase = first.get("purchase")          # Lieferanten-Sicht / Kurzform
    resp.sale = first.get("sale")
    resp.inspection = first.get("inspection")
    resp.movement = first.get("movement")
    resp.resource = first.get("resource")
    resp.disposal = first.get("disposal")
    resp.document = first.get("document")
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
    # FIX: deterministisch (nach id) statt unsortiert – bei einem Mehrpositionen-Auftrag
    # zeigte das Feed-Badge sonst je nach Query-Plan mal die eine, mal die andere Bestellung.
    for po in (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id.in_(order_ids), PurchaseOrder.is_active == True)
        .order_by(PurchaseOrder.id)
        .all()
    ):
        po_status[po.order_id] = po.status
    out: list[OrderSummary] = []
    for o in orders:
        s = OrderSummary.model_validate(o)
        art = arts.get(o.article_id)
        if art:
            s.article_name = art.name
            s.article_object_id = art.object_id
            s.article_unit = art.unit
        s.purchase_status = po_status.get(o.id)
        s.recurrence_due = recurrence_due(o)
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
