"""Hilfen rund um den Auftrag: Response-Aufbau (mit eingebettetem Prozess) und
rollenabhängige Sichtbarkeit (Lieferant sieht nur seine Aufträge)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from ..domain import event_types
from ..models import (
    Article, ArticleProcessStep, AuditLog, Disposal, Inspection,
    Instance, InstanceOrderLink, Movement, Order, OrderLine, PurchaseOrder, Sale, UserProfile,
)
from ..schemas.article_process_step import CaptureField
from ..schemas.disposal import DisposalEmbed
from ..schemas.document import DocumentEmbed
from ..schemas.inspection import InspectionEmbed, InspectionSample
from ..schemas.instance import InstanceEmbed, MaterialMoveView
from ..schemas.movement import MovementEmbed
from ..schemas.order import (
    FlowEdge, FlowLot, FlowNode, OrderDeviationInfo, OrderLineInfo,
    OrderOrigin, OrderResponse,
    OrderStepInfo, OrderSummary, ShortfallInstance, StepResolution, SubOrderStep,
    StepShortfall,
)
from ..schemas.purchase_order import PurchaseEmbed, PurchaseHistoryEntry
from ..models.base import utcnow
from ..schemas.sale import SaleEmbed
from . import people, process, recovery
from .article_fields import normalize_shared_fields
from .inspection import eval_fields, required_count, sample_targets
from .locations import location_label, location_labels, physical_location_labels
from .resource import build_resource_embed
from .subject import TERMINAL_DISPOSITIONS, held_quantity, order_instances, subject_kind

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
    from . import document as document_svc, process, sale as sale_svc, subject
    from .events import emit as _emit
    from .purchase import instantiate_for_order as instantiate_purchase
    from .resource import reserve_resources
    if order.status != "draft":
        return
    # **Erst schreiben lassen, dann lesen.** Die Session läuft mit ``autoflush=False``; wer
    # Auswahl und Freigabe in EINEM Aufruf erledigt (der Normalfall seit Notiz #386, ebenso
    # Nachschub/Bereitstellung/Wiederkehr), hätte die eben gesetzte Subjekt-Bindung sonst
    # noch nicht in der Datenbank – ``chosen_subjects`` fände nichts und die Freigabe liefe
    # ins Leere. Einmal hier, weil dies der EINE Freigabe-Pfad ist.
    db.flush()
    # Nebenläufigkeits-Schutz (Doppelklick/Request-Retry): den Auftrag sperren und den
    # Status unter der Sperre FRISCH lesen (nur die Spalte – KEIN ``refresh``, das bei
    # autoflush=False ungeflushte Feld-Änderungen des Aufrufers verwerfen würde). Ohne
    # Lock sahen zwei gleichzeitige Freigaben beide «draft» und ein produce-Auftrag
    # erzeugte seine Instanzen DOPPELT (``create_instances_for_order`` prüft nur
    # committete Zeilen; kein Unique-Key auf order_id).
    committed = db.query(Order.status).filter(Order.id == order.id).with_for_update().first()
    if committed is not None and committed[0] != "draft":
        db.expire(order, ["status"])   # Spiegel: nächster Zugriff liest den echten Stand
        return
    order.status = "released"
    # **Hier – und nur hier – entsteht die Objektnummer** (Testnotiz #386). Ein Auftrag ist
    # erst mit der Freigabe ein Geschäftsvorfall; vorher lebt der Entwurf im Browser und
    # verbraucht keine Nummer. Systemseitig angelegte Aufträge (Wiederkehr, Nachschub,
    # Kunden-Retoure) bringen ihre Nummer schon mit – dann ist das hier ein No-op.
    if order.object_id is None:
        from .objects import next_object_id
        order.object_id = next_object_id(db, "order")
        db.flush()
    if order.released_at is None:
        order.released_at = utcnow()   # Start der Durchlaufzeit
    # **Zuerst die Freigabe, dann ihre Folgen** (Testnotiz #517): das Protokoll las sich
    # verkehrt herum – «Bestellung angefragt» stand VOR «Auftrag freigegeben», obwohl die
    # Bestellung erst aus der Freigabe entsteht. Der Zeitstempel entscheidet die Reihenfolge,
    # also wird der Auslöser zuerst festgehalten; fachlich ändert sich nichts (alles liegt
    # in derselben Transaktion).
    _emit(db, "order.released", object_type="order", object_id=order.object_id,
          payload={"article_id": order.article_id, "quantity": order.quantity}, actor_id=actor_id)
    subject.materialize_subject(db, order, actor_id)
    instantiate_purchase(db, order, actor_id)        # Beschaffungs-Schritte → Bestellungen
    sale_svc.instantiate_for_order(db, order, actor_id)  # Verkaufs-Schritte → Belege
    document_svc.instantiate_for_order(db, order, actor_id)  # Dokument-Schritte → leere Fachzeile (wird ausgeführt)
    reserve_resources(db, order, actor_id)           # Komponenten mengengenau reservieren
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
            names[lg.user_id] = people.name_by_id(db, lg.user_id)
        out.append(PurchaseHistoryEntry(
            status=status, at=lg.changed_at_utc,
            by=names.get(lg.user_id) if lg.user_id is not None else None,
        ))
    return out


def _receiving_label(db: Session, po: PurchaseOrder) -> str | None:
    """Lieferadresse für den Lieferanten: die **Firmenadresse**.

    Früher stand hier die Objektnummer eines Lagerplatzes – damit konnte ein Lieferant
    nichts anfangen. Wohin die Ware im Betrieb wandert, entscheidet ohnehin erst die
    Pflicht-Bewegung «Wareneingang» nach der Beschaffung.

    Gemeint ist der **Hauptsitz** – nicht irgendeine Standort-Zeile. (Eine Bestellung an
    einen Nebenstandort liefern zu lassen, ist ein späterer Schritt: dafür bräuchte der
    Beschaffungs-Schritt einen eigenen Wareneingangs-Standort.)"""
    from . import address
    from .sites import find_primary
    return address.one_line(address.of_company(find_primary(db)))


def _purchase_embed(db: Session, order: Order, step: ArticleProcessStep,
                    po: PurchaseOrder, history: list[PurchaseHistoryEntry] | None = None) -> PurchaseEmbed:
    emb = PurchaseEmbed.model_validate(po)
    if po.supplier_id:
        emb.supplier_name = people.name_by_id(db, po.supplier_id)
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
        se.customer_name = people.name_by_id(db, sale.customer_id)
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
    ie.fields = [CaptureField(**f) for f in eval_fields(step)]
    # **Erfasst ist erfasst** (Testnotiz #402): eine abgeschlossene Prüfung ist eine
    # Tatsache – ihre Proben stehen in ``insp.samples`` und werden NICHT aus einer
    # beweglichen Grundlage neu gerechnet. Der Plan («wie viele Proben brauche ich?») hängt
    # daran, wie viel der Auftrag gerade hält; nach seinem Abschluss ist die Reservierung
    # gelöst, und aus 2 erfassten Proben wurden wieder 4 angezeigte.
    #
    # Solange die Prüfung LÄUFT ist umgekehrt der Plan massgeblich: nach einer Hochstufung
    # auf 100 % müssen die zusätzlichen Proben ja erst noch erfasst werden.
    finished = bool(insp and insp.result in ("passed", "failed") and insp.samples)
    if finished:
        ie.samples = [
            InspectionSample(instance_id=s["instance_id"], slot=s.get("slot", 1),
                             values=s.get("values") or {})
            for s in insp.samples
        ]
        ie.required_count = len(ie.samples)
    else:
        stored = {(s.get("instance_id"), s.get("slot", 1)): (s.get("values") or {})
                  for s in (insp.samples or [])} if insp else {}
        ie.samples = [
            InspectionSample(instance_id=t["instance_id"], slot=t["slot"],
                             values=stored.get((t["instance_id"], t["slot"]), {}))
            for t in sample_targets(db, order, step)
        ]
        ie.required_count = required_count(db, order, step)
    if insp and insp.inspector_id:
        ie.inspector_name = people.name_by_id(db, insp.inspector_id)
    return ie


def _movement_embed(db: Session, order: Order, step: ArticleProcessStep,
                    mv: Movement | None, instances: list | None = None) -> MovementEmbed:
    me = MovementEmbed(id=mv.id if mv else 0, done=mv is not None, note=mv.note if mv else None)
    me.mode = step.mode                      # 'customer' = Pflicht-Versand (nur dann sold bewegbar)
    me.target_location_type = step.target_location_type
    me.target_location_id = step.target_location_id
    # **Pflicht-Versand zum Kunden** (mode='customer'): das Ziel ist NICHT frei wählbar, sondern
    # FIX der Kunde des Verkaufs. So erzwingt das Panel (fester Zielort) die richtige Person UND
    # muss keine Personen-/Instanz-Listen laden (schnell). Fällt der Kunde noch (Verkauf nicht
    # bestätigt), bleibt das Ziel offen – die Bewegung ist ohnehin erst nach dem Verkauf aktiv.
    if step.mode == "customer":
        from .sale import customer_for_order
        cust = customer_for_order(db, order)
        if cust:
            me.target_location_type = "user"
            me.target_location_id = cust.object_id
    me.target_location_label = location_label(db, me.target_location_type, me.target_location_id)
    if mv and mv.moved_by_id:
        me.moved_by_name = people.name_by_id(db, mv.moved_by_id)
    # Versand (ADR 005): abgeleitete Transportklasse + Versand-Beleg dieses Schritts.
    # EXAKT dieselbe Instanz-Auswahl wie die Ausführung (movement.movable_instances).
    if instances is None:
        from .movement import movable_instances
        instances = movable_instances(db, order, step)
    from . import logistics
    me.shipment = logistics.build_embed(db, order, step, instances)
    return me


def _disposal_embed(db: Session, order: Order, disp: Disposal | None,
                    scrapped_count: int) -> DisposalEmbed:
    de = DisposalEmbed(id=disp.id if disp else 0, done=disp is not None,
                       note=disp.note if disp else None, scrapped_count=scrapped_count)
    if disp and disp.scrapped_by_id:
        de.scrapped_by_name = people.name_by_id(db, disp.scrapped_by_id)
    return de


def _doc_content_visible(db: Session, step: ArticleProcessStep, doc, viewer) -> bool:
    """**Sichtbarkeit als Lese-Zugriffsfilter** (nicht mehr nur Deklaration): darf dieser
    Betrachter den Dokument-INHALT sehen? Personal (und interne Aufrufer ohne Viewer)
    immer; sonst nach ``doc_visibility``: public → jeder | parties → benannte
    Freigabe-Parteien + Anerkennungs-Publikum | internal (Default) → nur Personal."""
    if viewer is None or viewer.role in _STAFF_ROLES:
        return True
    # Eine benannte Freigabe-Partei liest IMMER (man kann nicht unterschreiben, was man
    # nicht sieht) – unabhängig von der deklarierten Sichtbarkeitsstufe.
    if doc is not None:
        from .document import signoffs_for
        if any(r.signer_object_id == viewer.object_id for r in signoffs_for(db, doc)):
            return True
    vis = getattr(step, "doc_visibility", None) or "internal"
    if vis == "public":
        return True
    if vis == "parties":
        from .consent import _in_audience
        return _in_audience(viewer, step)
    return False


def _document_embed(db: Session, order: Order, step: ArticleProcessStep,
                    doc, viewer=None) -> DocumentEmbed:
    """Eingebetteter Stand des Dokument-Schritts. Der Inhalt wird während der Ausführung
    verfasst; Nummer (= Instanz-Objektnummer) und Datum (= Instanz-Freigabe) kommen aus der
    vom Auftrag erzeugten Instanz. Vor der Freigabe existiert noch keine Fachzeile → leerer,
    editierbarer Entwurf. Für Nicht-Personal filtert ``doc_visibility`` den Inhalt."""
    from .document import _enrich_embed, creator_name, normalize_content, render_meta
    obj_nr, doc_date = render_meta(db, order)
    if doc is not None:
        emb = DocumentEmbed.model_validate(doc)   # coerce content (dict) → DocumentContent
        emb.created_by_name = creator_name(db, doc)
        emb.object_number = obj_nr
        emb.document_date = doc_date
        _enrich_embed(db, doc, emb)               # Freigabe-Parteien + Sichtbarkeit/Reihenfolge
        if not _doc_content_visible(db, step, doc, viewer):
            emb.content = None                    # Inhalt (und Parteien-Detail) verbergen
            emb.signoffs = []
        return emb
    # Vorgabe-Deklaration schon im leeren Entwurf zeigen (Sichtbarkeit/Reihenfolge vom Schritt).
    return DocumentEmbed(
        id=0, done=False, issued=False, content=normalize_content(None),
        object_number=obj_nr, document_date=doc_date,
        sign_sequential=bool(getattr(step, "sign_sequential", False)),
        visibility=getattr(step, "doc_visibility", None) or "internal",
    )


def _purchase_received(po_embed: PurchaseEmbed) -> tuple[str | None, object]:
    """Wer/Wann den Wareneingang bestätigt hat (aus dem Bestell-Verlauf)."""
    for h in po_embed.history:
        if h.status == "received":
            return h.by, h.at
    return None, None


def _terminal_amounts(db: Session, sub: Order) -> dict[int, dict[str, Decimal]]:
    """**Was dieser Auftrag dem Bestand endgültig entzogen hat** – je Instanz-Objektnummer
    **und je Art des Abgangs** (``{objektnr: {scrapped|sold|consumed: menge}}``).

    Aus dem Event-Strom (``inventory.decreased``) – dauerhaft und exakt, auch lange nachdem
    Reservierungen gelöst sind. Verschrottet, verkauft oder verbaut kehrt nicht zurück.

    **Die Art gehört dazu, nicht nur die Summe.** Eine Charge hat ihren Zustand **pro
    Menge**, nicht als Ganzes: von 4 Stück können 3 in Arbeit und 1 verschrottet sein. Ohne
    die Art wüsste die Materialzeile zwar, DASS etwas weg ist, aber nicht, in welchem
    Zustand – und müsste weiterhin den skalaren Instanz-Status für die ganze Menge
    behaupten (Testnotizen #483/#485). Altbestand ohne ``reason`` ist ein Verkauf: nur das
    Aussondern hat die Angabe je geschrieben.

    **Und der Zeitpunkt gehört dazu** (Testnotiz #488): eine Kante des Flusses zeigt den
    Zustand, den die Menge **damals** hatte – ein Abgang, der später passiert ist, gab es
    dort noch nicht. Ohne die Uhrzeit liesse sich das nicht unterscheiden, und jede
    durchlaufene Kante trüge rückwirkend den heutigen Zustand."""
    from ..models import Event
    from .quantity import ZERO, to_qty
    if not sub.object_id:
        return {}
    out: dict[int, dict[tuple[str, object], Decimal]] = {}
    for e in (db.query(Event)
              .filter(Event.event_type == "inventory.decreased", Event.object_type == "instance")
              .order_by(Event.id).all()):
        p = e.payload or {}
        if p.get("order") != sub.object_id or e.object_id is None:
            continue
        key = (str(p.get("reason") or "sold"), e.created_at)
        row = out.setdefault(e.object_id, {})
        row[key] = row.get(key, ZERO) + to_qty(p.get("quantity") or 0)
    return out


def _lot_meta(db: Session, insts: list) -> dict[int, dict]:
    """**Die Angaben, die eine Materialzeile nachvollziehbar machen** (Notiz #426) – je
    Instanz-Objektnummer, batch aufgelöst.

    Instanz, **Artikel** (Nummer + Name + Einheit) und **Standort**: damit beantwortet eine
    Kante des Flusses «welches Stück, wovon, wo, wie viel», ohne dass man drei Datensätze
    öffnen muss. Eine Stelle für beide Leser – die Hauptachse (was der Auftrag hält) und die
    Abzweige (was hineinging/zurückkam)."""
    if not insts:
        return {}
    arts = {a.id: a for a in db.query(Article)
            .filter(Article.id.in_({i.article_id for i in insts})).all()}
    loc = location_labels(db, [(i.location_type, i.location_id) for i in insts])
    out: dict[int, dict] = {}
    for i in insts:
        if not i.object_id:
            continue
        art = arts.get(i.article_id)
        out[i.object_id] = dict(
            instance_object_id=i.object_id, article_id=i.article_id,
            article_object_id=(art.object_id if art else None),
            article_name=(art.name if art else None), unit=(art.unit if art else None),
            location_label=loc.get((i.location_type, i.location_id)))
    return out


def order_material(db: Session, order: Order,
                   insts: list | None = None) -> tuple[list[FlowLot], list[FlowLot]]:
    """**Das Material eines Auftrags – und was davon endgültig weg ist.** EINE Stelle.

    **Quelle ist das Material-Journal** (ADR 007, Ausbaustufe 2): alles, was je in diesen
    Auftrag hineingebucht wurde, ist genau einmal da – als noch gehaltener Topf, als
    terminaler Topf (ihm zugeschrieben, mit Zeitpunkt) oder als abgegebene Menge (im
    Zustand, in dem sie ging). Kein ``held_quantity``, keine Links-Menge, keine
    Reservierungs-Map mehr im Lesepfad – die Grössen, die sich bewegen, können die
    Vergangenheit nicht mehr umschreiben.

    **Die Menge schrumpft nicht, der Zustand ändert sich** (Testnotiz #481): nach dem
    Verschrotten steht dort weiterhin «1 Stk» – nur rot, mit dem Zeitpunkt aus der Buchung.
    **Der Zustand hängt an der MENGE** (#483/#485): eine Charge zerfällt in ihre Töpfe.
    **Und er ist eine Aussage über das Material, nie über den Betrachter** (#495):
    gebunden = gehalten UND am Lager – dieselbe Antwort aus jeder Blickrichtung.

    Alt-Aufträge ohne Buchungen fallen auf die bisherige Ableitung zurück (tolerant lesen,
    streng schreiben)."""
    from . import ledger
    view = ledger.order_view(db, order.id) if order.id else None
    if view is None:
        return _order_material_legacy(db, order, insts)
    lots = _view_lots(db, view.material, order.id)
    return lots, _view_lots(db, view.terminal)


def _view_lots(db: Session, rows: list, holder: int | None = None) -> list[FlowLot]:
    """Journal-Zeilen (``ledger.ViewRow``) zu Materialzeilen – **eine Stelle, eine Regel**.

    **Die Nummern kommen von dem, der die Menge JETZT hält** (Testnotizen #536/#537/#539/
    #540): das ist der Auftrag selbst, oder – wenn die Menge in einen Abzweig gegangen ist –
    genau dieser Abzweig (``ViewRow.to_order``). Damit trägt jede Zeile ihre Stücke, egal
    aus welcher Richtung man sie ansieht; vorher blieben abgegebene Mengen ohne Zusatz, und
    dieselbe Kante zeigte eine Pille mit und eine ohne Nummern.

    **Eine Menge in einem Zustand ist EINE Zeile** – Zeilen derselben Instanz im selben
    Zustand werden verschmolzen (Mengen summiert, Nummern vereinigt). Zwei Pillen für
    dieselbe Sache sind keine zwei Informationen (#539).

    Was den Bestand endgültig verlassen hat (verschrottet), trägt keine Nummern mehr – sie
    sind entwertet. Eine geratene Zuordnung wäre schlimmer als keine."""
    from . import units as U
    from .shares import UNIT_PREVIEW
    oids = {r.instance_object_id for r in rows}
    meta_insts = (db.query(Instance)
                  .filter(Instance.object_id.in_(oids)).all()) if oids else []
    meta = _lot_meta(db, meta_insts)
    by_oid = {i.object_id: i for i in meta_insts}

    def to_lot(r) -> FlowLot:
        base = meta.get(r.instance_object_id) or dict(instance_object_id=r.instance_object_id)
        lot = FlowLot(quantity=float(r.quantity), quality=r.quality,
                      disposition=r.disposition, reserved=r.reserved, at=r.at, **{
                          k: v for k, v in base.items() if k != "instance_object_id"},
                      instance_object_id=r.instance_object_id)
        inst = by_oid.get(r.instance_object_id)
        if inst is None:
            return lot
        # **Die Nummern stehen in der BUCHUNG** (Testnotizen #543/#544). Vorher wurden sie
        # aus dem heutigen Halter abgeleitet – gab ein Abzweig beim Abschluss alles zurück,
        # hielt er nichts mehr, und die Vergangenheit zeigte plötzlich ALLE Nummern statt
        # der richtigen. Eine abgeleitete Antwort kann keine Vergangenheit sein.
        recorded = getattr(r, "units", ()) or ()
        if recorded and U.covers(inst, recorded, r.quantity):
            lot.units = U.rows_for(inst, recorded, limit=UNIT_PREVIEW)
            lot.unit_count = len(recorded)
            return lot
        # Altbestand ohne aufgezeichnete Nummern (Buchungen vor Migration 100) und
        # **gehaltene** Zeilen (die sind die Gegenwart): aus der Karte ableiten – über
        # ``owned_by``, also Anspruch ODER unbeanspruchter Rest (dieselbe Regel wie bei den
        # Anteilen). Ein blosser Anspruchs-Filter hielte «nichts», sobald ein Abzweig
        # zurückgegeben hat.
        owner = r.to_order if getattr(r, "to_order", None) is not None else holder
        if owner is not None and (r.disposition or "") not in TERMINAL_OUT:
            U.ensure(inst)
            mine = U.owned_by(inst, owner)
            lot.units = U.rows_for(inst, [u.index for u in mine], limit=UNIT_PREVIEW)
            lot.unit_count = len(mine)
        return lot

    return _merge_lots([to_lot(r) for r in rows])


#: Verbleibe, aus denen nichts mehr herauskommt – ihre Nummern sind entwertet.
TERMINAL_OUT = ("scrapped", "sold", "consumed")


def _by_number(units: list) -> list:
    """Stücke aufsteigend nach ihrer laufenden Nummer – überall dieselbe Ordnung."""
    def key(u):
        part = u.number.split("-")
        return int(part[1]) if len(part) > 1 and part[1].isdigit() else 0
    return sorted(units, key=key)


def _merge_lots(lots: list[FlowLot]) -> list[FlowLot]:
    """**Eine Menge, ein Zustand, EINE Zeile** (Testnotiz #539/#520).

    Zwei Zeilen derselben Instanz im selben Zustand sind keine zwei Informationen – sie
    lesen sich als zwei verschiedene Dinge. Mengen werden summiert, Nummern vereinigt (ohne
    Dubletten), der Zeitpunkt bleibt der früheste."""
    out: list[FlowLot] = []
    seen: dict[tuple, FlowLot] = {}
    for l in lots:
        key = (l.instance_object_id, l.quality, l.disposition)
        cur = seen.get(key)
        if cur is None:
            seen[key] = l
            out.append(l)
            continue
        cur.quantity += l.quantity
        have = {u.number for u in cur.units}
        # Aufsteigend nach Nummer – dieselbe Ordnung wie im Instanz-Detail (#531).
        cur.units = _by_number(cur.units + [u for u in l.units if u.number not in have])
        cur.unit_count = max(cur.unit_count, len(cur.units))
        cur.reserved = cur.reserved or l.reserved
        if l.at is not None and (cur.at is None or l.at < cur.at):
            cur.at = l.at
    return out


def _order_material_legacy(db: Session, order: Order,
                           insts: list | None = None) -> tuple[list[FlowLot], list[FlowLot]]:
    """Die Ableitung VOR dem Journal (Links + Event-Strom + Reservierungs-Map) – nur noch
    Lesepfad für Alt-Aufträge ohne Buchungen."""
    from ..models import InstanceOrderLink
    from .quantity import ZERO, to_qty
    insts = order_instances(db, order) if insts is None else insts
    if not insts:
        return [], []
    taken = {
        row.instance_object_id: row.quantity
        for row in db.query(InstanceOrderLink)
        .filter(InstanceOrderLink.order_id == order.id, InstanceOrderLink.is_active == True).all()
        if row.quantity is not None
    }
    lost = _terminal_amounts(db, order)
    meta = _lot_meta(db, insts)
    material: list[FlowLot] = []
    gone: list[FlowLot] = []
    for i in insts:
        base = meta.get(i.object_id or 0)
        if base is None:
            continue
        qty = to_qty(taken.get(i.object_id) if taken.get(i.object_id) is not None
                     else held_quantity(order, i))
        # **Der Zustand hängt an der MENGE, nicht an der Instanz** (Testnotizen #483/#485).
        # Bei Einzelserialisierung fällt beides zusammen (eine Instanz = 1 Stück = ein
        # Zustand); bei einer Charge nicht: von 4 Stück können 3 in Arbeit und 1
        # verschrottet sein. Die übernommene Menge zerfällt darum in Teile – was dieser
        # Auftrag ausgesteuert hat (je Art), und der lebende Rest.
        left = qty
        for (kind, at), amount in sorted((lost.get(i.object_id) or {}).items(),
                                         key=lambda kv: (str(kv[0][1]), kv[0][0])):
            part = min(to_qty(amount), left)
            if part <= ZERO:
                continue
            left -= part
            material.append(FlowLot(quantity=float(part), disposition=kind,
                                    quality=i.quality, at=at, **base))
            gone.append(FlowLot(quantity=float(part), disposition=kind, at=at, **base))
        # **Der Zustand ist eine Aussage über das MATERIAL, nie über den betrachtenden
        # Auftrag** (Testnotiz #495). ``reserved`` hiess «der Auftrag, den ich gerade ansehe,
        # läuft noch» – damit sah dasselbe Stück im selben Moment verschieden aus: gelb
        # («Reserviert») vom laufenden Eltern aus, grün («Freigegeben», also frei am Lager)
        # vom abgeschlossenen Abzweig aus, obwohl es die ganze Zeit dem Eltern gehörte. Das
        # war nie eine Eigenschaft der Menge, sondern der Blickrichtung.
        #
        # Jetzt sagt es, was es behauptet: **beansprucht ein Auftrag diese Menge?**
        # (``instances.reserved_quantity``, die Summe der Ansprüche). Damit ist der Zustand
        # überall derselbe – dieselbe Frage, dieselbe Antwort wie am Instanz-Detail.
        if left > ZERO:
            bound = min(left, to_qty(i.reserved_quantity))
            for amount, is_bound in ((bound, True), (left - bound, False)):
                if amount > ZERO:
                    material.append(FlowLot(quantity=float(amount), quality=i.quality,
                                            disposition=i.disposition, reserved=is_bound, **base))
    return material, gone


def returning_material(material: list[FlowLot]) -> list[FlowLot]:
    """**Was aus einem Auftrag zurückkommt** – die EINE Ableitung dafür.

    Was er übernommen hat, minus dem, was den Bestand endgültig verlassen hat: übrig bleiben
    genau die Zeilen, die **nicht** terminal sind. ``order_material`` zerlegt die übernommene
    Menge ohnehin schon in Abgänge und den lebenden Rest – hier wird nur der Rest gelesen,
    statt die Differenz ein zweites Mal zu rechnen."""
    return [l for l in material if l.disposition not in TERMINAL_DISPOSITIONS]


def _sub_info(db: Session, sub: Order, cache: dict[int, list[SubOrderStep]],
              instance_object_ids: list[int] | None = None,
              stage: str = "before") -> OrderDeviationInfo:
    """**Die Kurzinfo eines Unter-Auftrags – an EINER Stelle gebaut.**

    Denselben Abzweig gibt es in zwei Listen (am Auftrag und an seinem Schritt); wurden sie
    getrennt zusammengesetzt, konnte der eine Teaser mehr wissen als der andere. Jetzt eine
    Quelle: Name, Zustand, sein Ablauf **und** der Materialfluss durch ihn (#413)."""
    material, gone = order_material(db, sub)
    back = _flow_back(db, sub, material)
    return OrderDeviationInfo(
        object_id=sub.object_id, status=sub.status, reason=sub.reason,
        instance_count=len(instance_object_ids or []),
        instance_object_ids=instance_object_ids or [],
        title=sub.title, abort_into_id=sub.abort_into_id, stage=stage,
        name=_order_ref_name(db, sub),
        steps=_sub_order_steps(db, sub, cache),
        flow_in=material, flow_lost=gone,
        flow_back=back,
        # Dieselbe Frage, dieselbe Antwort wie am Rückweg-Knoten im Unter-Auftrag selbst –
        # der Abzweig darf im Eltern nicht anders aussehen als beim Öffnen (#492). Darum
        # liest diese Stelle die EINE Ableitung (``returns_material``) statt selbst zu
        # rechnen: sie kannte das Kappen nicht und zeichnete eine Rückgabe-Linie, die es
        # nicht gibt. ``flow_back`` daneben sagt, was tatsächlich schon zurück ist.
        returns_material=returns_material(db, sub, material))


def _flow_back(db: Session, sub: Order, material: list[FlowLot]) -> list[FlowLot]:
    """**Was diesen Auftrag tatsächlich verlassen hat** (Testnotizen #496/#497) – aus dem
    Material-Journal (ADR 007): die Rückgabe-Buchungen (returned/released), keine Vorhersage.

    Solange der Auftrag läuft, gibt es schlicht keine solchen Buchungen – die frühere
    Fallunterscheidung «leer, solange er läuft» löst sich damit auf: sie war die Simulation
    eines Journals, das es jetzt gibt. Alt-Aufträge ohne Journal fallen auf die bisherige
    Ableitung zurück (Übernommenes minus endgültig Verlorenes, erst nach Abschluss)."""
    from . import ledger
    departed = ledger.departed_of(db, sub.id)
    if not departed:
        return ([] if sub.status in ("draft", "released")
                else returning_material(material))
    from . import units as U
    meta = {m.instance_object_id: m for m in material}
    insts = {i.object_id: i for i in db.query(Instance).filter(
        Instance.object_id.in_({k[0] for k in departed}))} if departed else {}
    out: list[FlowLot] = []
    for (oid, quality, disposition), back in sorted(departed.items()):
        base = meta.get(oid)
        row = (base.model_copy(update={"quantity": float(back.quantity), "at": None,
                                       "quality": quality, "disposition": disposition,
                                       "reserved": False})
               if base else FlowLot(instance_object_id=oid, quantity=float(back.quantity),
                                    quality=quality, disposition=disposition))
        # **Die zurückgegebenen Stücke sind die der BUCHUNG** – nicht die, die einmal
        # hineingingen (Testnotiz #559): wer 2 übernimmt, 1 weiterreicht und 1 zurückgibt,
        # nennt sonst beide Nummern zu einer Menge von 1.
        inst = insts.get(oid)
        if inst is not None and back.units:
            row.units = U.rows_for(inst, back.units)
            row.unit_count = len(back.units)
        elif inst is not None:
            row.units, row.unit_count = [], 0
        out.append(row)
    return out


def _sub_order_steps(db: Session, sub: Order,
                     cache: dict[int, list[SubOrderStep]]) -> list[SubOrderStep]:
    """**Der Ablauf eines Unter-Auftrags, angeteasert** (Notiz #409) – dieselbe Ableitung wie
    für den Auftrag selbst (``process.build_order_steps``), nur auf Modul + Zustand
    eingedampft. Kein zweites Regelwerk: ein Schritt ist im Teaser genau so weit wie im
    Unter-Auftrag, weil es dieselbe Rechnung ist.

    ``cache``: derselbe Unter-Auftrag erscheint sowohl in der Auftrags-Liste als auch am
    Schritt, aus dem er hervorging – ohne Merker liefe die Ableitung zweimal."""
    if sub.id not in cache:
        cache[sub.id] = [
            SubOrderStep(id=s["id"], step_type=s["step_type"], state=s["state"],
                         status=_fact_status_label(s))
            for s in process.build_order_steps(db, sub)
        ]
    return cache[sub.id]


def _fact_status_label(step: dict) -> str | None:
    """Der fachliche Zwischenstand eines Schritts (Beschaffung/Verkauf) – für die Modul-Karte.

    Nur diese beiden Typen haben einen; alles andere trägt seinen Zustand ohnehin im Symbol.
    Ein **erledigter** Schritt zeigt ihn nicht (Notiz #279): dass er durch ist, sagt der Haken."""
    if step.get("state") == "done":
        return None
    facts = step.get("facts") or ([step["fact"]] if step.get("fact") else [])
    if step.get("step_type") not in ("purchase", "sale") or not facts:
        return None
    return getattr(facts[0], "status", None)


def _order_sub_orders(db: Session, order: Order,
                      steps_cache: dict[int, list[SubOrderStep]] | None = None) -> tuple[
        list[OrderDeviationInfo], list[OrderDeviationInfo], list[OrderDeviationInfo],
        list[OrderDeviationInfo]]:
    """Unter-Aufträge eines Auftrags, getrennt nach Grund: **Abweichung** (nimmt ihr Stück
    aus dem Auftrag heraus → Unterdeckung), **Nachschub** (deckt Bedarf), **Retoure**
    (Rücknahme + Gutschrift eines abgeschlossenen Verkaufs), **Bereitstellung**.

    Keiner davon hält den Eltern-Auftrag an: was fehlt, blockiert den Schritt, der es
    braucht – EIN Mechanismus (Unterdeckung) statt Pause + Unterdeckung."""
    if not order.object_id:
        return [], [], [], []
    cache = steps_cache if steps_cache is not None else {}
    children = (
        db.query(Order)
        .filter(Order.parent_order_id == order.object_id, Order.is_active == True)
        .order_by(Order.object_id)
        .all()
    )
    deviations: list[OrderDeviationInfo] = []
    supplies: list[OrderDeviationInfo] = []
    returns: list[OrderDeviationInfo] = []
    provisionings: list[OrderDeviationInfo] = []
    for c in children:
        ids = [
            row[0] for row in
            db.query(InstanceOrderLink.instance_object_id)
            .filter(InstanceOrderLink.order_id == c.id, InstanceOrderLink.is_active == True)
            .all()
        ]
        info = _sub_info(db, c, cache, instance_object_ids=ids)
        # **Explizit je Grund**, kein Sammel-Else: sonst landet jeder neue Unter-Auftrags-Grund
        # stillschweigend im Abweichungs-Topf und erscheint dem Nutzer als «Abweichung».
        bucket = {"supply": supplies, "return": returns,
                  "provisioning": provisionings}.get(c.reason or "", deviations)
        bucket.append(info)
    # **Ein Unter-Auftrag gehört genau EINEM Auftrag – seinem Eltern** (Testnotiz #397).
    # Vorher wurden zusätzlich *fremde* Abweichungen hereingezogen, die dieselbe Instanz
    # betreffen (die Klammer sei die Instanz, nicht der Eltern-Zeiger, #350). In der Kette
    # Auftrag → Abweichung → Abweichung stand damit die zweite auch im Hauptauftrag, obwohl
    # sie dort nichts zu suchen hat: sie hat der ERSTEN etwas weggenommen, nicht ihm.
    # Dass ein anderer Auftrag betroffen ist, sagt ihm heute die Unterdeckungs-Frage bei der
    # Freigabe – jeder Betroffene wird gefragt. Dafür braucht es keinen Fremd-Knoten mehr.
    deviations.sort(key=lambda d: d.object_id)
    return deviations, supplies, returns, provisionings


def _sub_order_stage(reason: str | None, step_type: str) -> str:
    """**Wo steht ein Unter-Auftrag relativ zu seinem Schritt?** – EINE Deklaration.

    «vorher» heisst: er hält den Schritt auf – erst das hier, dann dieser Schritt. Das gilt
    für alles, was fehlt oder erst herbeigeschafft werden muss (Abweichung, Nachschub, und
    eine Bereitstellung, deren Material vor der Ausführung da sein muss).
    «nachher» heisst: er folgt aus dem Schritt – die Ware kommt an, nachdem bestellt wurde.

    Für die Bereitstellung ist die Antwort längst deklariert (``provisioning._STAGE_BEFORE``,
    nach Schritttyp); alles andere ist ein Hindernis und steht immer davor."""
    from .provisioning import _STAGE_BEFORE, REASON as PROVISIONING
    if reason == PROVISIONING:
        return "before" if step_type in _STAGE_BEFORE else "after"
    return "before"


def _fill_step_sub_orders(db: Session, order: Order, step: ArticleProcessStep,
                          si: OrderStepInfo,
                          steps_cache: dict[int, list[SubOrderStep]] | None = None) -> None:
    """**Die Unter-Aufträge dieses Schritts als Knoten im Ablauf** – alle drei Arten in EINER
    Liste, jede mit ihrer eigenen Position.

    Ein Unter-Auftrag ist kein Prozessschritt, aber er findet **zwischen** zwei Schritten
    statt – und genau dort gehört er in die Darstellung. Welcher Schritt das ist, hält
    ``orders.origin_step_id`` fest (``deviation.interrupted_step_id``); wo genau, sagt
    ``_sub_order_stage``. Auch abgeschlossene bleiben stehen – sie sind Teil der Geschichte
    des Schritts.

    Vorher standen Bereitstellung und Abweichung/Nachschub in zwei getrennten Listen plus
    einem Stufen-Feld daneben, und das Frontend setzte sie mit einer Fallunterscheidung
    wieder zusammen. Es ist dieselbe Sache – also eine Liste."""
    subs = (
        db.query(Order).filter(
            Order.parent_order_id == order.object_id,
            Order.origin_step_id == step.id, Order.is_active == True,
            # Ein **zurückgenommener** Unter-Auftrag belastet den Ablauf nicht mehr: er ist
            # die ausdrückliche Aussage «das erledige ich anders». Erledigte bleiben.
            Order.status != "inactive",
        ).order_by(Order.object_id).all()
    )
    cache = steps_cache if steps_cache is not None else {}
    si.sub_orders = [
        _sub_info(db, o, cache, stage=_sub_order_stage(o.reason, step.step_type))
        for o in subs if o.object_id
    ]


# Entscheidungen, die eine Unterdeckung an diesem Schritt aufgelöst haben (Notiz #281).
# **Was an einem Schritt entschieden wurde bzw. ihm widerfahren ist** – drei Ereignisse,
# eine Spur: gedeckt · Menge reduziert · **Anteil entzogen** (ein anderer Auftrag hat sich
# ein Stück geholt; genau das erklärt später, warum hier plötzlich etwas fehlt).
_RESOLUTION_EVENTS = ("order.covered_from_stock", "order.quantity_confirmed", "order.share_taken")


def _fill_step_resolutions(db: Session, order: Order, step: ArticleProcessStep,
                           si: OrderStepInfo) -> None:
    """**Was hier entschieden wurde** – aus dem Event-Strom, nicht aus einem neuen Feld.

    Der Schritt zeigt damit auch dann noch, wie eine frühere Unterdeckung aufgelöst wurde
    (ersetzt bzw. ohne Ersatz weiter), wenn er längst wieder läuft. Der Nachschub selbst
    braucht hier nichts: er ist ein Unter-Auftrag und steht bereits als Pille am Schritt."""
    from ..models import Event
    rows = (
        db.query(Event)
        .filter(Event.event_type.in_(_RESOLUTION_EVENTS), Event.object_type == "order",
                Event.object_id == order.object_id)
        .order_by(Event.id)
        .all()
    )
    rows = [e for e in rows if (e.payload or {}).get("step_id") == step.id]
    if not rows:
        return
    art_ids = {(e.payload or {}).get("article_id") for e in rows}
    arts = {a.id: a for a in db.query(Article).filter(Article.id.in_(art_ids)).all()}
    actors = _actor_names(db, [e.actor_id for e in rows])
    for e in rows:
        p = e.payload or {}
        art = arts.get(p.get("article_id"))
        si.resolutions.append(StepResolution(
            kind=e.event_type.split(".", 1)[1],
            article_object_id=(art.object_id if art else None),
            article_name=(art.name if art else None),
            quantity=p.get("quantity"), quantity_from=p.get("from"), quantity_to=p.get("to"),
            instance_object_ids=[i for i in (p.get("instances") or []) if i]
                                or ([p["instance"]] if p.get("instance") else []),
            other_order_object_id=p.get("to_order"),
            at=e.created_at, by=actors.get(e.actor_id),
        ))


def _actor_names(db: Session, ids: list) -> dict:
    """Anzeigenamen der Handelnden – EINE Abfrage, kein N+1."""
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    return {u.id: u.display_name
            for u in db.query(UserProfile).filter(UserProfile.id.in_(wanted)).all()}


def _return_target(db: Session, order: Order) -> Order | None:
    """**Wohin gibt dieser Unter-Auftrag beim Abschluss zurück?**

    Gelesen wird genau die Ableitung, die es auch TUT – keine zweite Behauptung daneben:
    ein Auftrag mit **festem Subjekt** (Abweichung/Retoure/Bereitstellung) leiht seine Stücke
    und gibt sie an den nächsten **laufenden** Verleiher zurück (``subject.lender_of``, folgt
    der Kette über abgebrochene Zwischenstufen hinweg, Notiz #404); ein **Nachschub** pinnt
    seine Stück an den Eltern (``process._peg_supply_to_parent``). Alles andere gibt nichts
    zurück – ein gewöhnlicher Auftrag schuldet niemandem etwas."""
    from .subject import is_fixed_subject, lender_of
    # **Kommt überhaupt etwas zurück?** – EINE Frage, EINE Antwort (Testnotizen #492/#563):
    # gekappt oder nichts mehr da. Sonst zeigte derselbe Abzweig zwei verschiedene Bilder,
    # weil diese Stelle nur fragte, WEM er zurückgäbe, nicht OB.
    if not returns_material(db, order):
        return None
    if is_fixed_subject(order):
        return lender_of(db, order)
    if order.reason == "supply" and order.parent_order_id:
        parent = db.query(Order).filter(Order.object_id == order.parent_order_id).first()
        return parent if parent is not None and parent.status == "released" else None
    return None


def returns_material(db: Session, order: Order,
                     material: list[FlowLot] | None = None) -> bool:
    """**Kommt aus diesem Auftrag überhaupt etwas zurück?** – EINE Stelle (Testnotiz #492).

    Zwei Gründe, warum nichts zurückkommt, und beide gehören hierher:

    - **gekappt** (``returns_nothing``, Testnotiz #563): der Mensch hat gesagt, dass dieser
      Auftrag sein Material zu Ende führt. Der Verleiher ist dadurch abgebrochen; eine
      Rückgabe-Linie würde einen Weg zeigen, den es nicht mehr gibt.
    - **nichts mehr da**: was er übernommen hat, minus dem, was den Bestand endgültig
      verlassen hat. Bleibt nichts, führt die Linie gar nicht erst zurück – die einfachste
      denkbare Darstellung für «alles verschrottet» bzw. «Menge reduziert» (#481).

    Sie steht hier, weil sie an **zwei** Oberflächen gebraucht wird: am Abzweig im
    Eltern-Auftrag und am Rückweg-Knoten im Unter-Auftrag selbst. Wurden sie getrennt
    hergeleitet, zeigte derselbe Vorgang zwei verschiedene Bilder – genau so ist das Kappen
    zuerst nur an EINER der beiden angekommen. ``material`` reicht eine bereits berechnete
    Materialliste durch (der Abzweig hat sie ohnehin), spart also die zweite Abfrage."""
    if order.returns_nothing:
        return False
    if material is None:
        material, _ = order_material(db, order)
    return sum(x.quantity for x in returning_material(material)) > 0


def _order_ref_name(db: Session, o: Order) -> str:
    """Der Name eines referenzierten Auftrags – **dieselbe** Ableitung wie im Feed
    (``order_display_name`` über ``to_order_summaries``), damit derselbe Datensatz nicht
    an zwei Stellen zwei Namen trägt."""
    rows = to_order_summaries(db, [o])
    return rows[0].name if rows else (o.title or "Auftrag")


def _fill_origin(db: Session, order: Order, resp: OrderResponse) -> None:
    """**Woher dieser Unter-Auftrag kam – und wohin er zurückgibt** (Notiz #409).

    Der Eltern zeigt den Abzweig längst an seiner Stelle im Ablauf; hier steht die
    Gegenrichtung, damit man in beide Richtungen sieht, ohne zu suchen: aus welchem
    Auftrag und aus welchem **Schritt** dieser Vorgang hervorgegangen ist – und an wen
    seine Stücke beim Abschluss zurückgehen.

    Beides ist vorhandenes Wissen von der anderen Seite gelesen (``parent_order_id`` +
    ``origin_step_id`` bzw. ``_return_target``), kein neues Feld."""
    if not order.parent_order_id:
        return
    parent = db.query(Order).filter(Order.object_id == order.parent_order_id).first()
    if parent is None or not parent.object_id:
        return
    origin = OrderOrigin(order_object_id=parent.object_id, order_status=parent.status,
                         order_reason=parent.reason,
                         order_name=_order_ref_name(db, parent))
    # (Die Brotkrumen-Kette ist entfallen, Notiz #428: der aktuelle Auftrag steht im Kopf des
    #  Fensters, der Eltern im Herkunfts-Teaser des Flusses – sie sagte beides ein zweites Mal.)
    back = _return_target(db, order)
    if back is not None and back.object_id:
        origin.returns_to_object_id = back.object_id
        origin.returns_to_name = (origin.order_name if back.id == parent.id
                                  else _order_ref_name(db, back))
        # **Was zurück IST, nicht was zurückgehen wird** (Testnotiz #554) – dieselbe eine
        # Ableitung, die der Eltern für seinen Abzweig liest.
        origin.returned_lots = _flow_back(db, order, order_material(db, order)[0])
    resp.origin = origin


def _fill_affected(db: Session, order: Order, resp: OrderResponse) -> None:
    """**Wem nimmt die Auswahl dieses Entwurfs etwas weg?** (Testnotiz #387)

    Ein Entwurf, der **gebundene** Instanzen wählt, greift auf laufende Aufträge zu. Bisher
    erfuhr man das erst als Fehlertext bei der Freigabe – eine Aufzählung von Objektnummern.
    Hier steht es als Datensatz-Liste am Entwurf: Name, Nummer, Artikel, **Verlust** – und ob
    dieser Betroffene überhaupt eine Entscheidung braucht.

    **Gerechnet wird an EINER Stelle** (``shares.affected``). Vorher stand hier eine zweite
    Fassung, die meldete, was der Halter überhaupt **hält** statt was er **verliert** – bei
    2 Stück aus einer 4er-Charge also «verliert 4» (Testnotiz #391).

    Nur am Entwurf: danach ist die Frage beantwortet und der Zugriff vollzogen."""
    from .shares import affected, affected_rows
    from .subject import chosen_subjects
    if order.status != "draft" or not order.id:
        return
    picked = chosen_subjects(db, order)
    if not picked:
        return
    resp.affects = affected_rows(db, affected(db, order, picked))


def _fill_order_shortfall(db: Session, order: Order, resp: OrderResponse) -> None:
    """**Was fehlt diesem Auftrag – und wartet er schon darauf?**

    Die Fehlmenge gehört dem **Auftrag**, nicht einem Schritt: sie ist «Soll − Gesichert»
    und dieselbe Aussage, egal welcher Schritt gerade dran ist. Vorher hing sie an jedem
    Subjekt-Schritt: dieselbe Zahl mehrfach berechnet (samt FIFO-Abfrage je Schritt) – und
    in einem Prozess **ohne** Subjekt-Schritt (reine Beschaffung) war sie gar nicht
    sichtbar, weshalb ein Auftrag über 4 Stück still mit 3 gelieferten abschloss.

    Zwei Arten, ein Feld: ``subject`` = die Fertigware, die der Auftrag schuldet (dafür gibt
    es «Ohne Ersatz weiter») · ``component`` = Material eines Ressourcen-Schritts (das kann
    man nicht wegbestätigen). Beides deckt «Ersetzen» (``recovery.cover_shortfall``)."""
    from .inventory import fifo_candidates
    from .reservation import free_qty
    from .supply import covering_sub_orders

    subject_short = process.subject_shortfalls(db, order)
    everything = process.order_shortfalls(db, order)
    # **Ruht der Prozess?** Dieselbe Regel wie im Ablauf – nicht hier nachgebaut.
    resp.paused = process.is_paused(db, order)
    if not everything:
        return
    arts = {a.id: a for a in db.query(Article).filter(Article.id.in_(everything.keys())).all()}
    for aid, qty in everything.items():
        # Freie, freigegebene Instanzen dieses Artikels am Lager – womit sich der Bedarf ohne
        # Nachschub decken liesse («Ersetzen» / «Bestimmte Instanz wählen»).
        free = [c for c in fifo_candidates(db, aid, for_order_id=None) if free_qty(c) > 0]
        resp.shortfall.append(StepShortfall(
            article_object_id=(arts[aid].object_id if aid in arts else None),
            article_name=(arts[aid].name if aid in arts else None), quantity=qty,
            kind="subject" if aid in subject_short else "component",
            replaceable=recovery.is_replaceable(db, order, aid in subject_short),
            available_quantity=sum(free_qty(c) for c in free),
            available_instances=[
                ShortfallInstance(object_id=c.object_id, quantity=free_qty(c))
                for c in free if c.object_id is not None
            ],
        ))
    # **«Wartet» ist ein Zustand, kein Knopf.** Ist die Fehlmenge bereits in einer offenen
    # Abweichung (das Stück ist in Klärung) oder einem laufenden Nachschub gebunden, ist die
    # Entscheidung längst getroffen – dann sagt die Oberfläche nur noch, worauf gewartet wird.
    resp.waiting_for = [o.object_id for o in covering_sub_orders(db, order, set(everything.keys()))]


def _fill_demand(db: Session, order: Order, resp: OrderResponse) -> None:
    """Bedarf denormalisieren: **entweder** der eine Anker-Artikel **oder** die Positionen
    eines Mehrpositionen-Auftrags (``order.article_id`` ist dann NULL) – nie beides."""
    if order.article_id:
        art = db.query(Article).filter(Article.id == order.article_id).first()
        if not art:
            return
        resp.article_name = art.name
        resp.article_object_id = art.object_id
        resp.article_size = art.size
        resp.article_unit = art.unit
        resp.article_weight_kg = art.weight_kg
        resp.article_serialization = art.serialization
        resp.article_supplier_article_number = art.supplier_article_number
        return
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


def _instance_embeds(db: Session, order: Order, instances: list) -> list[InstanceEmbed]:
    """Subjekt-Instanzen als Embeds – Standort-Labels **batch** aufgelöst (statt einem
    Query je Instanz, N+1)."""
    from . import units as U
    from .quantity import to_qty
    from .reservation import reserved_for

    from .shares import UNIT_PREVIEW, shares_for

    loc_keys = [(i.location_type, i.location_id) for i in instances]
    loc_labels = location_labels(db, loc_keys)
    phys_labels = physical_location_labels(db, [k for k in loc_keys if k[0] == "instance"])
    # **Wo liegt der Rest?** Ist ein Anteil dieser Instanz gerade bei einem anderen Auftrag
    # (Abweichung, Nachschub), soll man das hier sehen – und dort spiegelbildlich, woher er
    # kam. Dieselbe Ableitung wie im Instanz-Detail, EINE Batch-Abfrage.
    share_map = shares_for(db, instances)
    src_ids = {
        o.id: o.object_id
        for o in db.query(Order).filter(
            Order.id.in_({int(v) for v in (order.pick_sources or {}).values() if v})).all()
    } if order.pick_sources else {}
    out: list[InstanceEmbed] = []
    for i in instances:
        emb = InstanceEmbed.model_validate(i)
        emb.shares = share_map.get(i.id, [])
        src = (order.pick_sources or {}).get(str(i.object_id))
        emb.pick_source_object_id = src_ids.get(int(src)) if src is not None else None
        emb.location_label = loc_labels.get((i.location_type, i.location_id))
        if i.location_type == "instance":
            emb.physical_location_label = phys_labels.get((i.location_type, i.location_id))
        # **Der Anteil DIESES Auftrags an dieser Instanz** – immer gesetzt, nicht nur bei
        # einer Teilmenge: jede Aussage eines Auftrags über «diese Instanz» meint seinen
        # Anteil (bewegen, verschrotten, anzeigen). Eine Stelle, alle Leser.
        emb.held_quantity = float(held_quantity(order, i))
        # **Welche Stücke** das sind – die Nummern, nicht nur die Menge. Hält der Auftrag
        # den unbeanspruchten Rest (Erzeuger), sind es die freien.
        held_units = U.rows(i, holder=order.id, limit=UNIT_PREVIEW)
        emb.unit_count = U.count(i, holder=order.id)
        if not held_units and emb.held_quantity > 0:
            held_units = U.rows(i, holder=None, limit=UNIT_PREVIEW)
            emb.unit_count = U.count(i, holder=None)
        emb.units = held_units
        out.append(emb)
    return out


def _attach_step_embed(db: Session, order: Order, s: dict, si: OrderStepInfo,
                       first: dict, *, instances: list,
                       viewer: UserProfile | None) -> tuple[str | None, object | None]:
    """Den zum Schritttyp passenden Ausführungs-Embed an ``si`` hängen (Mehr-Operationen-
    Routing) und «wer/wann» für einen erledigten Schritt zurückgeben.

    ``first`` sammelt je Typ das erste Embed – ``OrderResponse.purchase``/``sale``/… sind
    die Kurzform für die Lieferanten-/Kunden-Sicht (beim Einzel-Artikel-Auftrag identisch
    mit dem einzigen Schritt-Embed)."""
    step, fact, done = s["step"], s["fact"], s["state"] == "done"
    kind = step.step_type

    if kind == "purchase":
        # EIN Schritt kann mehrere Bestellungen tragen (eine je Artikel/Position eines
        # Mehrpositionen-Auftrags) – ``purchases`` ist die vollständige Liste.
        facts = s["facts"]
        hist = _purchase_history(db, order) if facts else None
        embs = [_purchase_embed(db, order, step, f, history=hist) for f in facts]
        if not embs:
            return None, None
        si.purchases, si.purchase = embs, embs[0]
        first.setdefault("purchase", embs[0])
        return _purchase_received(embs[0]) if done else (None, None)

    if kind == "sale":
        # EIN `sale`-Schritt, ZWEI Modi (aus dem Subjekt abgeleitet): Verkauf (kind='sale')
        # oder Gutschrift/Erstattung (kind='credit', Retoure). Mehrere Belege je Position
        # teilen sich den Schritt.
        facts = s["facts"]
        embs = [_sale_embed(db, order, f) for f in facts] or [_sale_embed(db, order, None)]
        si.sales, si.sale = embs, embs[0]
        first.setdefault("sale", embs[0])
        if done and facts:
            return embs[0].customer_name, max((f.paid_at for f in facts if f.paid_at), default=None)
        return None, None

    # Einzel-Beleg-Schritte: Embed bauen, ablegen, «wer» aus dem jeweiligen Feld lesen.
    if kind == "inspection":
        si.inspection = emb = _inspection_embed(db, order, step, fact)
        who = emb.inspector_name
    elif kind == "movement":
        si.movement = emb = _movement_embed(db, order, step, fact)
        who = emb.moved_by_name
    elif kind == "scrap":
        scrapped = sum(1 for i in instances if i.disposition == "scrapped")
        si.disposal = emb = _disposal_embed(db, order, fact, scrapped)
        who = emb.scrapped_by_name
    elif kind == "document":
        si.document = emb = _document_embed(db, order, step, fact, viewer=viewer)
        who = emb.created_by_name
    elif kind in process.RESOURCE_STEP_TYPES:
        si.resource = emb = build_resource_embed(db, order, step, usage=fact)
        who = emb.used_by_name if emb else None
    else:
        return None, None

    if emb is not None:
        first.setdefault(_EMBED_SLOT[kind], emb)
    if done and emb is not None:
        return who, (fact.updated_at if fact else None)
    return None, None


# Schritttyp → Feldname der Kurzform an der OrderResponse (Lieferanten-/Kunden-Sicht).
_EMBED_SLOT = {"inspection": "inspection", "movement": "movement", "scrap": "disposal",
               "document": "document", "resource": "resource"}


def _as_of(lots: list[FlowLot], cutoff) -> list[FlowLot]:
    """**Der Zustand von damals** (Testnotiz #488) – jetzt SERVER-seitig, als pure Funktion.

    Zeilen mit einem Zeitpunkt NACH dem Stichtag gab es an dieser Stelle noch nicht: ihre
    Menge fällt in den gehaltenen Zustand zurück («Im Prozess»). ``cutoff=None`` heisst
    «vor dem ersten Schritt» – dort ist ALLES noch gehalten. Vorher lebte diese
    Zeitmaschine als React-Code in der Oberfläche; sie ist Fachlogik und gehört hierher."""
    out: list[FlowLot] = []
    back: dict[int, float] = {}
    for l in lots:
        if l.at is not None and (cutoff is None or l.at > cutoff):
            back[l.instance_object_id] = back.get(l.instance_object_id, 0.0) + l.quantity
        else:
            out.append(l)
    for oid, qty in back.items():
        # **Zurückgedrehtes verschmilzt mit dem, was ohnehin gehalten wird** (Notiz #520).
        # Ohne das stand dieselbe Instanz im selben Zustand ZWEIMAL auf einer Kante –
        # «3 Stk × 613» und «1 Stk × 613» statt «4 Stk × 613». Eine Zeile beschreibt EINE
        # Menge in EINEM Zustand; zwei Zeilen mit demselben Zustand sind keine.
        same = next((l for l in out if l.instance_object_id == oid
                     and (l.disposition or "in_process") == "in_process"), None)
        if same is not None:
            same.quantity += qty
            continue
        src = next((l for l in lots if l.instance_object_id == oid), None)
        if src is None:
            continue
        out.append(src.model_copy(update={
            "quantity": qty, "quality": None, "disposition": "in_process",
            "reserved": False, "at": None}))
    return out


def _minus(above: list[FlowLot], take: list[FlowLot]) -> list[FlowLot]:
    """Material abziehen, das ein Abzweig übernommen hat – lebende Zeilen zuerst (eine
    Teilung nimmt keine bereits ausgesonderte Menge mit). Nur noch für die Bypass-Anzeige
    der Vergangenheit bzw. für Alt-Aufträge ohne Journal."""
    gone = ("scrapped", "sold", "consumed")
    rows = [l.model_copy(update={"units": list(l.units)}) for l in above]
    for t in take:
        left = t.quantity
        # **Die Nummern gehen mit der Menge** (Testnotiz #544): wird eine Menge abgezogen,
        # verschwinden genau ihre Stücke – sonst zeigte der Bypass «3 Stk» und dazu alle
        # vier Nummern.
        drop = {u.number for u in t.units}
        for l in sorted((x for x in rows if x.instance_object_id == t.instance_object_id),
                        key=lambda x: x.disposition in gone):
            if left <= 0:
                break
            cut = min(left, l.quantity)
            l.quantity -= cut
            left -= cut
            keep = [u for u in l.units if u.number not in drop]
            # Nennt der Abzweig seine Stücke nicht (Altbestand), fallen die letzten weg –
            # die Anzahl stimmt dann, die Auswahl ist eine Näherung.
            l.units = keep if drop else l.units[:max(0, len(l.units) - int(cut))]
            l.unit_count = len(l.units)
    return [l for l in rows if l.quantity > 0]


def _returned_from(db: Session, order: Order, branch_object_ids: list[int]) -> list[FlowLot]:
    """Was aus **diesen** Ästen an den Auftrag zurückgebucht wurde (Journal). Es liegt
    wieder auf seiner Achse – aber es ist nicht am Abzweig **vorbei**gekommen, sondern
    durch ihn hindurch; der Bypass darf es darum nicht mitzählen."""
    from . import ledger
    if not branch_object_ids or not order.id:
        return []
    ids = {row[0] for row in db.query(Order.id)
           .filter(Order.object_id.in_(branch_object_ids)).all()}
    out: dict[int, float] = {}
    nums: dict[int, list[int]] = {}
    for m in ledger.moves_of(db, order.id):
        if m.kind == "returned" and m.src_order_id in ids and m.dst_order_id == order.id:
            out[m.instance_object_id] = out.get(m.instance_object_id, 0.0) + float(m.quantity)
            # **Welche** Stücke zurückkamen – aus der Buchung, damit der Bypass genau sie
            # abzieht statt irgendwelche (#544).
            nums.setdefault(m.instance_object_id, []).extend(m.units or ())
    insts = {i.object_id: i for i in db.query(Instance).filter(
        Instance.object_id.in_(out.keys())).all()} if out else {}
    from . import units as U
    return [FlowLot(instance_object_id=oid, quantity=q,
                    units=(U.rows_for(insts[oid], nums[oid])
                           if oid in insts and nums.get(oid) else []))
            for oid, q in out.items()]


def _waves(db: Session, branches: list) -> list[list]:
    """**Parallel ist nur, was gleichzeitig läuft** (Testnotiz #548).

    Zwei Abzweige aus demselben Schritt sind eine Teilung in zwei Richtungen, solange beide
    offen sind. War der erste aber längst **abgeschlossen**, als der zweite entstand, ist das
    keine Parallelität, sondern eine **Abfolge**: erst der eine, dann der andere. Vorher
    landeten alle Abzweige eines Schritts in EINER Teilung – zwei Äste nebeneinander, obwohl
    der erste sein Material längst zurückgegeben hatte, und der Bypass rechnete beide ab.

    Gruppiert wird darum nach **Lebenszeit**: ein Abzweig kommt in die laufende Welle, wenn
    er sich mit JEDEM darin überschneidet – sonst beginnt eine neue. Ohne Zeitstempel
    (Altbestand) gilt «überschneidet sich», damit nichts auseinanderfällt."""
    if not branches:
        return []
    rows = {o.object_id: o for o in db.query(Order).filter(
        Order.object_id.in_([b.object_id for b in branches])).all()}

    def overlaps(a, b) -> bool:
        oa, ob = rows.get(a.object_id), rows.get(b.object_id)
        if oa is None or ob is None:
            return True
        first, second = (oa, ob) if (oa.object_id or 0) <= (ob.object_id or 0) else (ob, oa)
        done, born = first.completed_at, second.released_at
        return done is None or born is None or done > born

    out: list[list] = []
    for b in sorted(branches, key=lambda x: x.object_id):
        for wave in out:
            if all(overlaps(b, other) for other in wave):
                wave.append(b)
                break
        else:
            out.append([b])
    return out


def _fill_flow_view(db: Session, order: Order, resp: OrderResponse) -> None:
    """**Die Prozess-Achse fertig rechnen – das Frontend zeichnet nur noch** (ADR 007).

    Baut aus den Schritten und ihren Abzweigen die Knotenliste (dieselbe Ordnung, die die
    Oberfläche jahrelang selbst konstruierte), bestimmt Fortschritt und Prozess-Punkt und
    legt an jede Kante ihr Material – im Zustand von damals (#488), an der lebenden Kante
    die aktuellen Zahlen. Der Bypass einer Teilung ist **gehalten + ausgesteuert** aus dem
    Journal («was HIER ist»), nicht mehr Subtraktions-Arithmetik im Client."""
    from . import ledger
    claimed = {d.object_id for s in resp.steps for d in (s.sub_orders or [])}
    loose = [x for x in (resp.deviations + resp.supply_orders + resp.provisionings)
             if x.object_id not in claimed]
    nodes: list[dict] = []
    for wave in _waves(db, loose):
        nodes.append(dict(kind="split", branches=wave, res_step=None))
    for s in resp.steps:
        subs = s.sub_orders or []
        before = [x for x in subs if x.stage == "before"]
        after = [x for x in subs if x.stage == "after"]
        for wave in _waves(db, before):
            nodes.append(dict(kind="split", branches=wave, res_step=s.id))
        nodes.append(dict(kind="step", step=s, res_step=None if before else s.id))
        for wave in _waves(db, after):
            nodes.append(dict(kind="split", branches=wave, res_step=None))

    is_open = lambda b: b.status in ("draft", "released")            # noqa: E731
    node_done = (lambda n: n["step"].state == "done" if n["kind"] == "step"
                 else all(not is_open(b) for b in n["branches"]))
    walked = 0
    while walked < len(nodes) and node_done(nodes[walked]):
        walked += 1

    cutoffs: list = [None] * (len(nodes) + 1)
    last = None
    for i, n in enumerate(nodes):
        cutoffs[i] = last
        if n["kind"] == "step" and n["step"].state == "done" and n["step"].completed_at:
            last = n["step"].completed_at
    cutoffs[len(nodes)] = last

    running = order.status == "released"
    here = (None if not running
            else (len(nodes), False) if walked == len(nodes)
            else (walked, nodes[walked]["kind"] == "split"))
    material = resp.flow_lots
    view = ledger.order_view(db, order.id) if order.id else None

    # **Was in einen Abzweig ging, liegt unterhalb seiner Teilung nicht mehr auf der
    # Achse** – es steht in SEINER Spur, und was zurückkam, ist wieder gehalten (die
    # Rückkehr hat ihre Abgabe-Zeile verzehrt). Die Journal-Zeile weiss, wohin sie ging
    # (``ViewRow.to_order``); je Kante wird nur gefiltert, nichts subtrahiert.
    branch_oids = {b.object_id for n in nodes if n["kind"] == "split" for b in n["branches"]}
    branch_db = (dict(db.query(Order.object_id, Order.id)
                      .filter(Order.object_id.in_(branch_oids)).all()) if branch_oids else {})
    gone_above: list[set[int]] = [set()]
    for n in nodes:
        nxt = set(gone_above[-1])
        if n["kind"] == "split":
            nxt |= {branch_db[b.object_id] for b in n["branches"] if b.object_id in branch_db}
        gone_above.append(nxt)

    # **Der Stichtag gilt für das, was OBERHALB des Prozess-Punktes liegt** (#488): dort ist
    # der Zustand eingefroren. Am Prozess-Punkt und darunter gilt der aktuelle – nach ihm ist
    # ja noch nichts passiert. Bei einem nicht mehr laufenden Auftrag ist nur das ENDE
    # aktuell: seine letzte Kante zeigt das Ergebnis, nicht den Stand vor der
    # Abschluss-Freigabe.
    current_from = here[0] if here is not None else len(nodes)

    def axis_lots(i: int, current: bool) -> list[FlowLot]:
        # **Was hier noch auf der Achse liegt, liegt hier NOCH** (Testnotiz #537). Eine
        # Menge, die erst weiter unten abzweigt, war an dieser Stelle unverändert beim
        # Auftrag – sie darf oberhalb ihres Splits nicht schon als abgegeben erscheinen.
        # Genau das war der gemeldete Fall: über dem Split standen zwei Pillen (3 gehalten
        # + 1 abgegeben) statt der einen Wahrheit «4, alle hier». Die Nummern kommen
        # trotzdem vom künftigen Halter – es sind ja dieselben Stücke.
        rows = []
        for r in view.material:
            if r.to_order is not None and r.to_order in gone_above[i]:
                continue
            rows.append(r if r.to_order is None else r._replace(at=None, reserved=True))
        lots = _view_lots(db, rows, order.id)
        return lots if current else _as_of(lots, cutoffs[i])

    def edge(i: int) -> FlowEdge:
        # **Keine Prognosen** (Testnotiz #521): eine Kante unterhalb des Prozess-Punktes
        # trägt kein Material. Was ein Modul einmal führen WIRD, ist nicht vorhersehbar –
        # es kann verschrottet, abgezweigt oder ersetzt werden, bevor es dort ankommt.
        # (#505 wollte «vor und nach jedem Modul» sehen; die eigentliche Lücke dort war
        # eine fehlende Rückgabe-Buchung, nicht die Regel – die ist behoben.)
        reached = i <= walked
        current = i >= current_from
        lots: list[FlowLot] = []
        if reached:
            lots = (axis_lots(i, current) if view is not None
                    else (material if current else _as_of(material, cutoffs[i])))
        return FlowEdge(lots=lots, reached=reached,
                        live=here is not None and here == (i, False))

    resp.flow_edges = [edge(i) for i in range(len(nodes) + 1)]
    for i, n in enumerate(nodes):
        node = FlowNode(
            kind=n["kind"], reached=i <= walked, passed=i < walked,
            step_id=(n["step"].id if n["kind"] == "step" else n["res_step"]),
            branch_object_ids=[b.object_id for b in n.get("branches", [])])
        if n["kind"] == "split":
            live_b = here is not None and here == (i, True)
            # **Neben der Teilung liegt, was NICHT abgezweigt ist** – auch dann noch, wenn
            # der Ast längst zurückgegeben hat: was durch den Abzweig gelaufen ist, kam
            # nicht hier vorbei. Darum die Achse UNTERHALB der Teilung (dort ist das
            # Abgezweigte schon herausgefiltert) minus dem, was aus GENAU diesen Ästen
            # zurückkam.
            below = i + 1
            if view is not None:
                lots = axis_lots(below, below >= current_from or live_b)
                back = _returned_from(db, order, [b.object_id for b in n["branches"]])
                if back:
                    lots = _minus(lots, back)
            else:
                base = material if below >= current_from else _as_of(material, cutoffs[below])
                lots = _minus(base, [l for b in n["branches"] for l in (b.flow_in or [])])
            # **Keine Prognosen – auch nicht neben einer Teilung** (Testnotizen #521/#538):
            # eine Teilung, die der Prozess noch nicht erreicht hat, weiss nicht, was
            # neben ihr liegen wird. Die Kanten halten sich längst daran; der Bypass tat
            # es nicht und behauptete Material an einer Stelle, an der noch nichts war.
            node.bypass = FlowEdge(lots=(lots if i <= walked else []),
                                   reached=i <= walked, live=live_b)
        resp.flow_nodes.append(node)


def _order_history_views(db: Session, order: Order) -> list[MaterialMoveView]:
    """**Was mit dem Material dieses Auftrags passiert ist** – die Journalzeilen (ADR 007).

    Dieselbe Zeile wie am Instanz-Detail, nur aus der anderen Richtung gelesen: hier ist
    der Chip die **Instanz** (welche Menge), dort der Auftrag. Chronologisch, unveränderlich
    – die dritte der drei Fragen, direkt am Auftrag."""
    from . import ledger
    if not order.id:
        return []
    return [
        MaterialMoveView(
            at=m.at, kind=m.kind, quantity=float(m.quantity),
            quality=m.dst_quality, disposition=m.dst_disposition,
            instance_object_id=m.instance_object_id, note=m.note)
        for m in ledger.moves_of(db, order.id)
    ]


def to_order_response(db: Session, order: Order, viewer: UserProfile | None = None) -> OrderResponse:
    """OrderResponse inkl. denormalisiertem Artikel, Instanzen und – pro Schritt –
    dem passenden Ausführungs-Embed (Mehr-Operationen-Routing).

    ``viewer``: der anfragende Nutzer, wenn der Endpoint auch Nicht-Personal bedient
    (Lieferant/Kunde) – filtert dann den Dokument-Inhalt nach ``doc_visibility``.
    ``None`` = interner/Personal-Aufruf (ungefiltert)."""
    resp = OrderResponse.model_validate(order)
    # Derselbe Unter-Auftrag erscheint in der Auftrags-Liste UND am Schritt, aus dem er
    # hervorging – sein Teaser-Ablauf wird darum je Antwort nur einmal abgeleitet.
    sub_steps: dict[int, list[SubOrderStep]] = {}
    (resp.deviations, resp.supply_orders, resp.returns,
     resp.provisionings) = _order_sub_orders(db, order, sub_steps)
    _fill_origin(db, order, resp)
    # Vorgänger (Ersetzen-Kette): wessen Nachfolger ist dieser Auftrag?
    if order.object_id:
        pred = db.query(Order.object_id).filter(Order.replaced_by_id == order.object_id).first()
        resp.replaces_id = pred[0] if pred else None
    _fill_demand(db, order, resp)
    _fill_order_shortfall(db, order, resp)
    _fill_affected(db, order, resp)
    resp.recurrence_due = recurrence_due(order)

    instances = order_instances(db, order)
    resp.instances = _instance_embeds(db, order, instances)
    # **Das Material auf den Kanten seiner Achse** (Notiz #426) – aus **derselben** Quelle wie
    # am Abzweig (``order_material``), damit derselbe Vorgang nicht je nach Blickrichtung zwei
    # Zahlen trägt (#479/#480/#482).
    resp.flow_lots, resp.flow_lost = order_material(db, order, instances)
    # **Der Prozessbaum** (Notiz #493): woher dasselbe Material kam, wohin es weiterging.
    # **Was ist passiert** (ADR 007): das Journal dieses Auftrags – nur fürs Personal (die
    # Lieferanten-/Kunden-Sicht ist auf ihren Ausschnitt beschränkt).
    if viewer is None or (viewer.role or "") in _STAFF_ROLES:
        resp.history = _order_history_views(db, order)

    # Auftrag-Stepper: je Schritt der passende Ausführungs-Embed + Abschluss-Info.
    # Das oberste Embed je Typ bleibt für Rückwärtskompatibilität (Lieferanten-Sicht)
    # zusätzlich gesetzt.
    steps: list[OrderStepInfo] = []
    first: dict[str, object] = {}
    # build_order_steps lädt Definitionen + Fachzeilen je EINMAL und liefert die
    # aufgelöste Fachzeile gleich mit (kein erneutes Nachladen je Schritt).
    for s in process.build_order_steps(db, order):
        step = s["step"]
        si = OrderStepInfo(id=s["id"], step_type=s["step_type"], position=s["position"],
                           label=s["label"], state=s["state"])
        _fill_step_sub_orders(db, order, step, si, sub_steps)
        _fill_step_resolutions(db, order, step, si)
        by_name, at = _attach_step_embed(db, order, s, si, first,
                                         instances=instances, viewer=viewer)
        if s["state"] == "done":
            si.completed_by = by_name
            si.completed_at = at
        steps.append(si)

    # Dieselbe Ableitung wie im Feed – hier stehen die Subjekt-Instanzen bereits als Embed
    # bereit (kein zusätzlicher Zugriff nötig).
    resp.name = order_display_name(
        order, resp.article_name,
        [l.article_name for l in (resp.order_lines or [])],
        _subject_article_names(db, resp.instances))

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
    # Seller of Record NUR bei einem Verkauf/einer Retoure (dann existiert ein Kunde und
    # eine fakturierende Gesellschaft) – ein Produktions-/Beschaffungsauftrag zeigt keinen
    # «Fakturiert durch». Lokaler Import: `sale` importiert `orders` (Zyklus vermeiden).
    if first.get("sale") is not None:
        from . import sale as sale_svc
        seller = sale_svc.seller_company_for_order(db, order)
        if seller is not None:
            resp.seller_company_object_id = seller.object_id
            resp.seller_company_name = seller.company_name
    # **Die fertig gerechnete Achse** – zuletzt, denn sie liest Schritte, Abzweige und
    # Material aus der Antwort selbst (eine Ableitung, ein Moment).
    _fill_flow_view(db, order, resp)
    return resp


def _subject_article_names(db: Session, instances: list[InstanceEmbed]) -> list[str]:
    """Artikelnamen der Subjekt-Instanzen (für den Namen eines Unter-Auftrags), ohne
    Dubletten und in stabiler Reihenfolge."""
    ids = list(dict.fromkeys(i.article_id for i in instances if i.article_id))
    if not ids:
        return []
    by_id = {a.id: a.name for a in db.query(Article).filter(Article.id.in_(ids)).all()}
    return [by_id[i] for i in ids if i in by_id]


def order_display_name(order: Order, article_name: Optional[str],
                       line_names: Optional[list[str]] = None,
                       subject_names: Optional[list[str]] = None) -> str:
    """**Der EINE Name eines Auftrags** – im Feed wie im Detail, für jede Auftragsart.

    Ein Datensatz zeigt im ERP immer dasselbe: Name · Objektnummer · Status; **welcher Typ**
    er ist, sagt sein Symbol. Darum darf im Namensfeld nie das Wort «Auftrag» als Platzhalter
    für den Typ stehen (Notiz #177).

    **Der Name benennt die SACHE, nicht die Herkunft** (Notiz #205): ein Unter-Auftrag hiess
    «Bereitstellung für Beschaffung · Auftrag 100000500» – das ist eine Beschreibung seiner
    Entstehung, kein Name. Worum es geht, ist der Artikel bzw. die Instanz. Der ``title``
    bleibt als Rückfall für Aufträge, die gar kein Subjekt tragen. Die Reihenfolge:

    1. der **Artikel** des Auftrags (Einzel-Artikel-Auftrag);
    2. bei mehreren Positionen der erste Artikel + wie viele noch dazugehören;
    3. der Artikel der **fixierten Subjekt-Instanzen** (Abweichung/Bereitstellung/Retoure);
    4. ``title`` – ein bewusst vergebener Name für Aufträge ohne Subjekt;
    5. «Auftrag» nur, wenn es wirklich nichts zu benennen gibt (Entwurf ohne Bedarf).
    """
    if article_name:
        return article_name
    for group in (line_names, subject_names):
        names = [n for n in (group or []) if n]
        if names:
            return names[0] if len(names) == 1 else f"{names[0]} +{len(names) - 1}"
    return order.title or "Auftrag"


def to_order_summaries(db: Session, orders: list[Order]) -> list[OrderSummary]:
    """Schlanke Feed-Sicht – Artikel-Infos und Beschaffungsstatus **batch**-geladen
    (zwei Zusatz-Queries für die ganze Liste statt je Auftrag ein Embed-Aufbau)."""
    if not orders:
        return []
    art_ids = {o.article_id for o in orders if o.article_id}
    arts = {a.id: a for a in db.query(Article).filter(Article.id.in_(art_ids)).all()} if art_ids else {}
    order_ids = [o.id for o in orders]
    # Positions-Artikelnamen für Mehrpositionen-Aufträge – EINE Batch-Abfrage für die ganze
    # Liste (der Name eines Auftrags darf nicht je Zeile eine eigene Query kosten).
    line_names: dict[int, list[str]] = {}
    multi = [o.id for o in orders if o.article_id is None]
    if multi:
        rows = (
            db.query(OrderLine.order_id, Article.name)
            .join(Article, Article.id == OrderLine.article_id)
            .filter(OrderLine.order_id.in_(multi), OrderLine.is_active == True)
            .order_by(OrderLine.order_id, OrderLine.position, OrderLine.id)
            .all()
        )
        for oid, name in rows:
            line_names.setdefault(oid, []).append(name)
    # Unter-Aufträge (Abweichung/Bereitstellung/Retoure) tragen ihr Subjekt als **fixierte
    # Instanzen** statt als Artikel/Positionen – auch sie sollen nach ihrer Sache heissen.
    subject_names: dict[int, list[str]] = {}
    fixed = [o.id for o in orders if o.article_id is None and o.id not in line_names]
    if fixed:
        seen: set[tuple[int, str]] = set()
        for oid, name in (
            db.query(Instance.subject_of_order_id, Article.name)
            .join(Article, Article.id == Instance.article_id)
            .filter(Instance.subject_of_order_id.in_(fixed), Instance.is_active == True)
            .order_by(Instance.subject_of_order_id, Instance.object_id)
            .all()
        ):
            if (oid, name) in seen:
                continue
            seen.add((oid, name))
            subject_names.setdefault(oid, []).append(name)
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
        s.name = order_display_name(o, s.article_name, line_names.get(o.id), subject_names.get(o.id))
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
