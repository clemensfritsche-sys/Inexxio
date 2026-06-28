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

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import (
    ArticleProcessStep, Inspection, Instance, Movement, Order, PurchaseOrder,
    ResourceUsage, Sale,
)
from ..models.base import utcnow
from .events import emit
from .reservation import consume as consume_qty, release, reserved_for

# Label & Fachtabelle je Schritt-Typ kommen aus der **deklarativen Registry**
# (``domain.event_types``) – EINE Quelle der Wahrheit statt verstreuter Dicts.
STEP_LABELS = {key: et.label for key, et in event_types.REGISTRY.items()}

_MODEL_BY_NAME = {
    "PurchaseOrder": PurchaseOrder, "Inspection": Inspection, "Movement": Movement,
    "ResourceUsage": ResourceUsage, "Sale": Sale,
}
# Fachtabelle je Schritt-Typ (für die generische Routing-Auflösung).
_FACT_MODEL = {key: _MODEL_BY_NAME[et.fact] for key, et in event_types.REGISTRY.items()}

# Schritttypen, die über die Ressourcen-Logik laufen (Verbrauch + Betriebsmittel;
# der Modus lebt pro Zeile). Die Alt-Aliase consume/tool sind entfernt.
RESOURCE_STEP_TYPES = event_types.RESOURCE_TYPES


def order_step_defs(db: Session, order: Order) -> list[ArticleProcessStep]:
    """Die Prozessschritte eines Auftrags in Reihenfolge (kein Modus-Flag):

    • trägt der Auftrag **eigene** Schritte → diese (individueller Ablauf, Bestands-Operation);
    • sonst → der **Prozess des Artikels** (Herstellung/Beschaffung, erzeugt Instanzen).

    Massgeblich ist allein, ob **eigene** Schritte vorliegen (konsistent zu
    ``subject.subject_kind``). Eine blosse Pin-Auswahl ohne Schritte kippt den Auftrag
    NICHT – er bleibt eine Herstellung über den Artikel-Prozess."""
    from .processes import article_steps, order_custom_steps
    custom = order_custom_steps(db, order.id)
    if custom:
        return custom
    return article_steps(db, order.article_id)


def _facts(db: Session, order: Order, step_type: str) -> list:
    model = _FACT_MODEL.get(step_type)
    if model is None:
        return []
    return (
        db.query(model)
        .filter(model.order_id == order.id, model.is_active == True)
        .all()
    )


def _fact_status(step_type: str, fact) -> str:
    """Roh-Status aus der (bereits aufgelösten) Fachzeile: 'done'|'open'|'failed'. Rein."""
    if step_type == "purchase":
        if not fact:
            return "open"
        if fact.status == "received":
            return "done"
        if fact.status == "rejected":
            return "failed"
        return "open"
    if step_type == "inspection":
        if fact and fact.result == "passed":
            return "done"
        if fact and fact.result == "failed":
            return "failed"
        return "open"
    if step_type == "sale":
        if not fact:
            return "open"
        if fact.status == "paid":
            return "done"
        if fact.status == "cancelled":
            return "failed"
        return "open"
    if step_type in ("movement", "resource"):
        return "done" if fact else "open"
    return "open"


def _resolve_fact(step: ArticleProcessStep, rows: list, sole_of_type: bool):
    """Fachzeile zu diesem Schritt (rein): exakt über ``step_id``; sonst – beim
    einzigen Schritt seines Typs – eine Altzeile ohne ``step_id``."""
    for r in rows:
        if getattr(r, "step_id", None) == step.id:
            return r
    if sole_of_type:
        for r in rows:
            if getattr(r, "step_id", None) is None:
                return r
    return None


def build_order_steps(db: Session, order: Order) -> list[dict]:
    """Schritte des Auftrags mit Zustand UND aufgelöster Fachzeile.

    Definitionen und Fachzeilen werden **je einmal** geladen (kein O(K²) je
    Schritt). Jeder Eintrag: id/step_type/position/label/state + ``step`` (Def) und
    ``fact`` (aufgelöste Fachzeile) für die Weiterverwendung im Embed-Aufbau."""
    defs = order_step_defs(db, order)
    if not defs:
        return []
    counts: dict[str, int] = {}
    for d in defs:
        counts[d.step_type] = counts.get(d.step_type, 0) + 1
    facts_by_type = {t: _facts(db, order, t) for t in counts}

    out: list[dict] = []
    active_assigned = False
    for d in defs:
        fact = _resolve_fact(d, facts_by_type.get(d.step_type, []), counts[d.step_type] == 1)
        raw = _fact_status(d.step_type, fact)
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
        out.append({
            "id": d.id, "step_type": d.step_type, "position": d.position,
            "label": STEP_LABELS.get(d.step_type, d.step_type), "state": state,
            "step": d, "fact": fact,
        })
    return out


def order_step_infos(db: Session, order: Order) -> list[dict]:
    """Öffentliche Schrittliste (ohne interne ``step``/``fact``-Objekte)."""
    return [{k: s[k] for k in ("id", "step_type", "position", "label", "state")}
            for s in build_order_steps(db, order)]


def fact_for_step(db: Session, order: Order, step: ArticleProcessStep):
    """Fachzeile zu genau diesem Schritt (Ausführungs-Pfad/Services).

    Exakter Treffer über ``step_id``; fehlt er (Altdaten), gehört eine Zeile ohne
    ``step_id`` dem **einzigen** Schritt seines Typs."""
    rows = _facts(db, order, step.step_type)
    for r in rows:
        if getattr(r, "step_id", None) == step.id:
            return r
    same_type = [d for d in order_step_defs(db, order) if d.step_type == step.step_type]
    return _resolve_fact(step, rows, len(same_type) == 1)


def active_step_of_type(db: Session, order: Order, step_type: str) -> ArticleProcessStep | None:
    """Die aktive Schritt-Definition des Typs (für die Ausführung ohne explizite id)."""
    for s in build_order_steps(db, order):
        if s["step_type"] == step_type and s["state"] == "active":
            return s["step"]
    return None


def resolve_exec_step(db: Session, order: Order, step_type: str, step_id: int | None) -> ArticleProcessStep:
    """Auszuführenden Schritt bestimmen: explizite ``step_id`` (muss aktiv sein)
    oder die aktive Schritt-Definition des Typs. Wirft, wenn nicht ausführbar."""
    label = STEP_LABELS.get(step_type, step_type)
    steps = build_order_steps(db, order)
    if step_id is not None:
        match = next((s for s in steps if s["id"] == step_id), None)
        if not match or match["step"].step_type != step_type:
            raise HTTPException(404, detail="Prozessschritt nicht gefunden")
        if match["state"] != "active":
            raise HTTPException(409, detail=f"{label} ist (noch) nicht an der Reihe")
        return match["step"]
    active = next((s for s in steps if s["step_type"] == step_type and s["state"] == "active"), None)
    if not active:
        raise HTTPException(409, detail=f"{label} ist (noch) nicht an der Reihe")
    return active["step"]


def resolve_resource_step(db: Session, order: Order, step_id: int | None) -> ArticleProcessStep:
    """Den auszuführenden Ressourcen-Schritt bestimmen – consume **oder** tool (über
    ``step_id`` eindeutig; sonst der aktive Ressourcen-Schritt). Der Schritttyp legt
    fest, ob verbraucht oder genutzt wird."""
    steps = build_order_steps(db, order)
    if step_id is not None:
        match = next((s for s in steps if s["id"] == step_id), None)
        if not match or match["step"].step_type not in RESOURCE_STEP_TYPES:
            raise HTTPException(404, detail="Prozessschritt nicht gefunden")
        if match["state"] != "active":
            raise HTTPException(409, detail="Schritt ist (noch) nicht an der Reihe")
        return match["step"]
    active = next((s for s in steps if s["step_type"] in RESOURCE_STEP_TYPES and s["state"] == "active"), None)
    if not active:
        raise HTTPException(409, detail="Schritt ist (noch) nicht an der Reihe")
    return active["step"]


def all_steps_done(db: Session, order: Order) -> bool:
    infos = order_step_infos(db, order)
    return bool(infos) and all(i["state"] == "done" for i in infos)


def has_step(db: Session, order: Order, step_type: str) -> bool:
    return any(d.step_type == step_type for d in order_step_defs(db, order))


def release_instances(db: Session, order: Order) -> None:
    """Bestands-Instanzen eines abgeschlossenen Auftrags freigeben (pending → passed).

    Erst ein abgeschlossener Auftrag bedeutet «fertig & ab Lager verfügbar»: die
    Instanzen werden zu «Freigegeben» und damit für den Ressource-Verbrauch (FIFO)
    nutzbar. ``released_at`` ist die FIFO-Basis. Bereits bewertete Instanzen
    (failed/consumed/passed) bleiben unverändert."""
    now = utcnow()
    rows = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True,
                Instance.quality == "pending")
        .all()
    )
    total = 0
    for inst in rows:
        inst.quality = "passed"          # QC-Verdikt: freigegeben
        inst.disposition = "in_stock"    # Verbleib: am Lager (ab jetzt verbrauchbar)
        if inst.released_at is None:
            inst.released_at = now
        total += inst.quantity or 0
    # Bestands-Zugang als Domain-Event mit DEKLARIERTER Polarität festhalten – so wird
    # der Event-Strom zur ökonomischen Wahrheit (Bestand = Projektion über Events).
    if total:
        emit(db, "inventory.increased", object_type="order", object_id=order.object_id,
             payload={"article_id": order.article_id, "quantity": total,
                      "delta": total, "polarity": event_types.INCREASE})


def _finalize_subjects(db: Session, order: Order) -> None:
    """Verbleib der vom Auftrag bearbeiteten Bestands-Instanzen bei Abschluss.

    Enthält der individuelle Ablauf einen **Verkauf**, verlässt die **für diesen Auftrag
    reservierte Menge** den Bestand: die Instanz wird **mengengenau gemindert** (keine
    Teilung!) – eine vollständig verkaufte Instanz wird ``sold``, eine teilweise verkaufte
    Charge bleibt mit der Restmenge am Lager. Sonst (Wartung/Bewegung/Kontrolle) bleibt der
    Verbleib unverändert. MAKE-Aufträge (neue Instanzen) laufen über ``release_instances``."""
    if not any(d.step_type == "sale" for d in order_step_defs(db, order)):
        return
    subjects = (
        db.query(Instance)
        .filter(Instance.reservations.has_key(str(order.id)),  # noqa: W601
                Instance.article_id == order.article_id, Instance.is_active == True)
        .all()
    )
    for inst in subjects:
        if inst.quality == "failed":
            continue
        sold = reserved_for(inst, order.id)
        consume_qty(inst, order.id, sold)        # Menge mindern + Reservierung lösen
        if (inst.quantity or 0) <= 0:
            inst.disposition = "sold"            # vollständig verkauft
        emit(db, "inventory.decreased", object_type="instance", object_id=inst.object_id,
             payload={"quantity": sold, "delta": -sold, "polarity": event_types.DECREASE,
                      "order": order.object_id})


def _spawn_recurrence(db: Session, order: Order) -> None:
    """Wiederkehrenden Auftrag fortschreiben: ist der abgeschlossene Auftrag als
    wiederkehrend markiert, wird der **nächste** (Entwurf) erzeugt – Termin =
    bisheriger Anker + Periode. Die Wiederkehr wandert auf den neuen Auftrag (Kette).
    Kein eigenes Objekt, kein Cron – ein abgeschlossener Auftrag zieht den nächsten nach."""
    if not getattr(order, "recurrence_active", False) or not order.recurrence_interval_days:
        return
    from datetime import timedelta

    from .objects import next_object_id
    base = order.recurrence_anchor or (order.completed_at.date() if order.completed_at else utcnow().date())
    new_anchor = base + timedelta(days=order.recurrence_interval_days)
    child = Order(
        object_id=next_object_id(db, "order"), status="draft",
        article_id=order.article_id, quantity=order.quantity,
        desired_delivery_date=new_anchor,
        recurrence_active=True, recurrence_interval_days=order.recurrence_interval_days,
        recurrence_lead_time_days=order.recurrence_lead_time_days,
        recurrence_anchor=new_anchor, recurring_parent_id=order.object_id,
    )
    db.add(child)
    db.flush()
    order.recurrence_active = False   # Staffelstab an den Nachfolger
    emit(db, "order.recurrence_spawned", object_type="order", object_id=child.object_id,
         payload={"parent": order.object_id})


def recompute_completion(db: Session, order: Order) -> None:
    """Auftrag automatisch abschliessen, wenn alle Prozessschritte erledigt sind."""
    if order.status != "completed" and all_steps_done(db, order):
        order.status = "completed"
        if order.completed_at is None:
            order.completed_at = utcnow()
        release_instances(db, order)        # produzierte Instanzen freigeben (verbrauchbar)
        _finalize_subjects(db, order)        # Verkauf: reservierte Menge mengengenau abbuchen
        # Restliche Reservierungen dieses Auftrags lösen (Auftrag fertig): ein neutral
        # gebliebenes Subjekt (Bewegung/Kontrolle) wird so wieder frei verfügbar; die
        # Subjekt-Markierung wird entfernt. Historie bleibt über ``instance_order_links``.
        for inst in db.query(Instance).filter(
            or_(Instance.reservations.has_key(str(order.id)),  # noqa: W601
                Instance.subject_of_order_id == order.id),
            Instance.is_active == True,
        ).all():
            release(inst, order.id)
            inst.subject_of_order_id = None
        _spawn_recurrence(db, order)         # wiederkehrend: nächsten Auftrag nachziehen
        emit(db, "order.completed", object_type="order", object_id=order.object_id)


def required_sample(quantity: int | None, sample_percent: int | None) -> int:
    """Zu prüfende Stückzahl der Eingangskontrolle (mind. 1, wenn Menge > 0)."""
    qty = quantity or 0
    pct = sample_percent if sample_percent is not None else 100
    if qty <= 0 or pct <= 0:
        return 0
    return min(qty, max(1, ceil(qty * pct / 100)))
