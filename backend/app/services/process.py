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
    ArticleProcessStep, Disposal, Inspection, Instance, Movement, Order, PurchaseOrder,
    ResourceUsage, Sale,
)
from ..models.base import utcnow
from .events import emit
from .inventory import available
from .reservation import consume as consume_qty, free_qty, release, reserve, reserved_for

# Label & Fachtabelle je Schritt-Typ kommen aus der **deklarativen Registry**
# (``domain.event_types``) – EINE Quelle der Wahrheit statt verstreuter Dicts.
STEP_LABELS = {key: et.label for key, et in event_types.REGISTRY.items()}

_MODEL_BY_NAME = {
    "PurchaseOrder": PurchaseOrder, "Inspection": Inspection, "Movement": Movement,
    "Disposal": Disposal, "ResourceUsage": ResourceUsage, "Sale": Sale,
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
    from .subject import is_deviation
    custom = order_custom_steps(db, order.id)
    if custom:
        return custom
    # Abweichung (Unter-Auftrag, reason='deviation'): NUR eigene Schritte (die Auflösung) –
    # nie der Artikel-Prozess. Ohne eigene Schritte hat sie (noch) keinen Ablauf. Ein
    # **Nachschub** (reason='supply') ist dagegen ein normaler Produktionsauftrag → Artikel-Prozess.
    if is_deviation(order):
        return []
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
    if step_type in ("movement", "resource", "scrap"):
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


def _resolve_facts_multi(step: ArticleProcessStep, rows: list, sole_of_type: bool) -> list:
    """Wie ``_resolve_fact``, aber liefert ALLE passenden Fachzeilen statt nur der ersten –
    für «Verkauf»/«Beschaffung» bei einem Mehrpositionen-Auftrag: mehrere Belege (einer
    je Artikel/Position) teilen sich denselben Schritt (``step_id``)."""
    matched = [r for r in rows if getattr(r, "step_id", None) == step.id]
    if matched:
        return matched
    if sole_of_type:
        return [r for r in rows if getattr(r, "step_id", None) is None]
    return []


# Schritttypen, die bei einem Mehrpositionen-Auftrag EINEN Schritt mit MEHREREN
# Fachzeilen abbilden (eine je Artikel/Position, gemeinsame ``step_id``) – ihr
# Fachmodell hat ein eigenes ``article_id`` (``Sale``/``PurchaseOrder``). Andere Typen
# (movement/resource/inspection/scrap) wirken artikel-unabhängig auf die GESAMTE
# Instanzmenge des Auftrags und bleiben bei genau EINER Fachzeile je Schritt.
MULTI_FACT_STEP_TYPES = {"sale", "purchase"}


def _aggregate_status(step_type: str, facts: list) -> str:
    """Aggregierter Rohstatus eines Schritts mit MEHREREN Fachzeilen (eine je Artikel/
    Position): 'done' erst, wenn JEDE einzeln 'done' ist; 'failed', wenn JEDE 'failed'
    ist – eine gemeinsame Aktion schliesst alle zusammen ab bzw. storniert sie zusammen
    (siehe ``sale.apply_update_bulk``/``purchase.apply_update_bulk``)."""
    if not facts:
        return "open"
    statuses = [_fact_status(step_type, f) for f in facts]
    if all(s == "done" for s in statuses):
        return "done"
    if all(s == "failed" for s in statuses):
        return "failed"
    return "open"


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
        if d.step_type in MULTI_FACT_STEP_TYPES:
            # EIN Schritt kann mehrere Belege tragen (ein Artikel/Position je Beleg,
            # Mehrpositionen-Auftrag) – Status ist das Aggregat über alle.
            facts = _resolve_facts_multi(d, facts_by_type.get(d.step_type, []), counts[d.step_type] == 1)
            fact = facts[0] if facts else None
            raw = _aggregate_status(d.step_type, facts)
        else:
            fact = _resolve_fact(d, facts_by_type.get(d.step_type, []), counts[d.step_type] == 1)
            raw = _fact_status(d.step_type, fact)
            facts = [fact] if fact else []
        if raw == "done":
            state = "done"
        elif raw == "failed":
            state = "failed"
            active_assigned = True
        elif not active_assigned:
            # An der Reihe – aber „blockiert", wenn der Schritt einen (noch) nicht gedeckten
            # Bedarf hat (Subjekt/Komponente fehlt). Abgeleitet aus dem Bestand, kein Status.
            state = "blocked" if _step_blocked(db, order, d) else "active"
            active_assigned = True
        else:
            state = "locked"
        out.append({
            "id": d.id, "step_type": d.step_type, "position": d.position,
            "label": STEP_LABELS.get(d.step_type, d.step_type), "state": state,
            "step": d, "fact": fact, "facts": facts,
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


def facts_for_step(db: Session, order: Order, step: ArticleProcessStep) -> list:
    """ALLE Fachzeilen zu diesem Schritt statt nur der ersten (``fact_for_step``) – für
    «Verkauf»: bei einem Mehrpositionen-Auftrag teilen sich mehrere ``Sale``-Belege
    (ein Artikel/Position je Beleg) denselben Schritt. Für jeden anderen Typ höchstens
    ein Eintrag (identisch zu ``fact_for_step``, nur als Liste)."""
    rows = _facts(db, order, step.step_type)
    same_type = [d for d in order_step_defs(db, order) if d.step_type == step.step_type]
    return _resolve_facts_multi(step, rows, len(same_type) == 1)


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


# ─── Bedarf & Verfügbarkeit (Bedarf-/Nachschub-Modell) ───────────────────────────
#
# Ein Auftrag hat **Bedarfe**: ein stock-Auftrag braucht sein **Subjekt** (Fertigware ab
# Lager), ein produce-Auftrag **Komponenten** (consume-Zeilen). Ist ein Bedarf nicht
# gedeckt, ist der zugehörige Schritt **blockiert** – ABGELEITET aus dem Bestand, kein
# gesetzter Status, kein Auto-Trigger. Die Fehlmenge deckt ein Nachschub-Unter-Auftrag
# (``services/supply.py``); pinnt er bei Abschluss seine Stück an den Eltern, wird der
# Schritt bei der nächsten Auswertung von selbst wieder ``active``.

def _subject_shortfalls(db: Session, order: Order) -> dict[int, int]:
    """Fehlmenge(n) des **Subjekts** je Artikel ({article_id: qty}) – **EINE Formel für
    ALLE Auftragsarten** (kein ``subject_kind``-Sonderpfad): ``Soll − Gesichert``.

    - **Soll** = Bestellmenge (Einzel-Artikel ``order.quantity``; Mehrpositionen je Position).
    - **Gesichert** = gute Einheiten, die der Auftrag bereits hat: (a) für ihn **reservierte**
      Bestands-Instanzen (FIFO ab Lager / gepinnt / gepeggter Nachschub) PLUS (b) **selbst
      erzeugte** gute Instanzen (Erzeugungsauftrag). Terminal verlorene (verschrottet/verkauft/
      verbaut) oder durchgefallene zählen NICHT.

    So reagiert ein **Erzeugungsauftrag auf Ausschuss** identisch wie ein **Bestands-Auftrag**
    auf eine ausgesteuerte Reservierung – dieselbe Unterdeckung, dieselben Deckungs-Wege, kein
    Sonderfall. Ausgenommen ist nur die **Abweichung**: ihr Subjekt sind fixierte Instanzen
    (``subject_of_order_id``), kein aus Lager/Produktion zu erfüllendes Soll."""
    from .order_lines import lines_for
    from .subject import TERMINAL_DISPOSITIONS, is_deviation
    if is_deviation(order):
        return {}
    # Soll je Artikel
    targets: dict[int, int] = {}
    if order.article_id and order.quantity:
        targets[order.article_id] = order.quantity
    else:
        for line in lines_for(db, order):
            targets[line.article_id] = targets.get(line.article_id, 0) + line.quantity
    if not targets:
        return {}
    # Gesichert je Artikel
    secured: dict[int, int] = {}
    for inst in db.query(Instance).filter(
        Instance.reservations.has_key(str(order.id)), Instance.is_active == True  # noqa: W601
    ).all():
        secured[inst.article_id] = secured.get(inst.article_id, 0) + reserved_for(inst, order.id)
    for inst in db.query(Instance).filter(
        Instance.order_id == order.id, Instance.is_active == True, Instance.quality != "failed"
    ).all():
        if (inst.disposition or "") in TERMINAL_DISPOSITIONS:
            continue
        if (inst.reservations or {}).get(str(order.id)):
            continue   # schon über die Reservierung (oben) gezählt – nicht doppelt
        secured[inst.article_id] = secured.get(inst.article_id, 0) + (inst.quantity or 0)
    return {a: t - secured.get(a, 0) for a, t in targets.items() if t - secured.get(a, 0) > 0}


def subject_shortfalls(db: Session, order: Order) -> dict[int, int]:
    """Öffentliche Sicht auf die **Subjekt**-Fehlmengen eines Auftrags ({article_id: qty}) –
    Grundlage der Wiederherstellung nach einer Aussteuerung (aus Lager decken / Menge
    reduzieren, ``services/recovery.py``). Nur das Subjekt (Fertigware), NICHT die Komponenten."""
    return _subject_shortfalls(db, order)


def _component_needs(db: Session, order: Order) -> dict[int, int]:
    """Offener Komponentenbedarf (consume) über alle Ressourcen-Schritte, je Artikel.
    **Bereits verbrauchte** Schritte (Fachzeile vorhanden) zählen nicht mehr mit – sonst
    entstünde nach dem Verbrauch ein Phantom-Bedarf (überflüssiger Nachschub)."""
    from .order_lines import effective_quantity
    needs: dict[int, int] = {}
    resource_steps = [d for d in order_step_defs(db, order) if d.step_type in RESOURCE_STEP_TYPES]
    if not resource_steps:
        return needs
    qty = effective_quantity(db, order)
    rows = _facts(db, order, "resource")
    sole = len(resource_steps) == 1
    for d in resource_steps:
        if _resolve_fact(d, rows, sole) is not None:
            continue   # bereits gebucht (verbraucht) → kein offener Bedarf mehr
        for line in (d.resource_lines or []):
            if (line.get("mode") or "consume") != "consume":
                continue
            aid = line["article_id"]
            needs[aid] = needs.get(aid, 0) + line.get("quantity", 1) * qty
    return needs


SUBJECT_STEP_TYPES = ("movement", "inspection", "scrap", "sale")


def step_shortfalls(db: Session, order: Order, step: ArticleProcessStep) -> dict[int, int]:
    """Fehlmengen, die genau diesen Schritt **blockieren** ({article_id: qty}); leer = frei.

    sale/movement/inspection/scrap → brauchen das **Subjekt** (Fertigware): fehlt es (z. B.
    weil eine reservierte Instanz per Abweichung ausgesteuert wurde ODER ein Erzeugungsauftrag
    Ausschuss hatte), blockiert der Schritt. **Auch «Verkauf»** ist ein Subjekt-Schritt – man
    kann nicht verkaufen, was nicht (mehr) gesichert ist; sonst reagierte ein Verkaufsauftrag
    nicht, wenn sein Bestand ausgesteuert wird.
    resource(consume) → braucht seine **Komponenten** (need − verfügbar; verfügbar = frei am
    Lager + für diesen Auftrag reserviert)."""
    out: dict[int, int] = {}
    if step.step_type in SUBJECT_STEP_TYPES:
        out.update(_subject_shortfalls(db, order))
    elif step.step_type in RESOURCE_STEP_TYPES:
        from .order_lines import effective_quantity
        qty = effective_quantity(db, order)
        for line in (step.resource_lines or []):
            if (line.get("mode") or "consume") != "consume":
                continue
            aid = line["article_id"]
            need = line.get("quantity", 1) * qty
            have = available(db, aid, order.id)
            if need > have:
                out[aid] = out.get(aid, 0) + (need - have)
    return out


def _step_blocked(db: Session, order: Order, step: ArticleProcessStep) -> bool:
    """Blockiert, weil ein Bedarf dieses Schritts (noch) nicht gedeckt ist?"""
    return bool(step_shortfalls(db, order, step))


def order_shortfalls(db: Session, order: Order) -> dict[int, int]:
    """Alle nicht gedeckten Bedarfe des Auftrags, je Artikel aggregiert ({article_id: qty}) –
    Grundlage für den Nachschub (``services/supply.py``)."""
    agg: dict[int, int] = {}
    for aid, subj in _subject_shortfalls(db, order).items():
        agg[aid] = agg.get(aid, 0) + subj
    for aid, need in _component_needs(db, order).items():
        have = available(db, aid, order.id)
        if need > have:
            agg[aid] = agg.get(aid, 0) + (need - have)
    return agg


def release_instances(db: Session, order: Order) -> None:
    """Bestands-Instanzen eines abgeschlossenen Auftrags freigeben (pending → passed).

    Erst ein abgeschlossener Auftrag bedeutet «fertig & ab Lager verfügbar»: die
    Instanzen werden zu «Freigegeben» und damit für den Ressource-Verbrauch (FIFO)
    nutzbar. ``released_at`` ist die FIFO-Basis. Bereits bewertete Instanzen
    (failed/consumed/passed) bleiben unverändert. **Terminale Teile** (verschrottet/verkauft/
    verbaut) werden NICHT ans Lager freigegeben – nur noch «im Prozess» befindliche."""
    now = utcnow()
    rows = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True,
                Instance.quality == "pending", Instance.disposition == "in_process")
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
    # (a) Bestands-Verkauf (FIFO): die für diesen Auftrag **reservierte** Menge verlässt
    #     den Bestand (mengengenau, keine Teilung). KEIN Artikel-Filter – ein Auftrag kann
    #     mehrere Artikel/Instanzen verkaufen (Mehrpositionen-Verkaufsauftrag); alle für
    #     diesen Auftrag reservierten Instanzen werden verkauft.
    subjects = (
        db.query(Instance)
        .filter(Instance.reservations.has_key(str(order.id)),  # noqa: W601
                Instance.is_active == True)
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
    # (b) Made-to-Order-Verkauf: die **unter diesem Auftrag erzeugten** Instanzen werden
    #     direkt verkauft (sie wurden gerade via ``release_instances`` freigegeben). Kein
    #     FIFO/keine Reservierung – sie gehören dem Kunden dieses Auftrags.
    produced = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True,
                Instance.quality != "failed", Instance.disposition == "in_stock")
        .all()
    )
    for inst in produced:
        inst.disposition = "sold"
        emit(db, "inventory.decreased", object_type="instance", object_id=inst.object_id,
             payload={"quantity": inst.quantity or 0, "delta": -(inst.quantity or 0),
                      "polarity": event_types.DECREASE, "order": order.object_id})


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


def _is_paused_by_deviation(db: Session, order: Order) -> bool:
    """Pausiert der Auftrag wegen einer offenen Abweichung oder eines ausstehenden Abbruchs?
    Solange darf er NICHT abschliessen – erst muss die Abweichung geklärt sein."""
    if getattr(order, "abort_into_id", None) is not None:
        return True
    if not order.object_id:
        return False
    # NUR Abweichungen pausieren den Eltern; ein Nachschub (reason='supply') blockiert nur
    # den betroffenen Schritt – der restliche Prozess darf weiterlaufen.
    return db.query(Order.id).filter(
        Order.parent_order_id == order.object_id, Order.is_active == True,
        Order.reason == "deviation", Order.status.in_(("draft", "released")),
    ).first() is not None


def recompute_completion(db: Session, order: Order) -> None:
    """Auftrag automatisch abschliessen, wenn alle Prozessschritte erledigt sind – aber NICHT,
    solange eine Abweichung offen oder ein Abbruch ausstehend ist (der Auftrag pausiert)."""
    if _is_paused_by_deviation(db, order):
        return
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
        _peg_supply_to_parent(db, order)     # Nachschub: erzeugte Stück an den Eltern pinnen
        emit(db, "order.completed", object_type="order", object_id=order.object_id)
        # War das eine Abweichung? Dann den Eltern-Auftrag neu bewerten: er ist jetzt nicht
        # mehr pausiert und schliesst automatisch ab, falls er nur noch auf diese Abweichung
        # gewartet hat (sonst läuft er einfach normal weiter).
        if order.parent_order_id is not None:
            parent = db.query(Order).filter(Order.object_id == order.parent_order_id).first()
            if parent and parent.status == "released":
                recompute_completion(db, parent)


def _peg_supply_to_parent(db: Session, order: Order) -> None:
    """**Nachschub-Pegging**: Schliesst ein Nachschub-Unter-Auftrag (``reason='supply'``) ab,
    werden seine soeben freigegebenen Stück dem **Eltern-Auftrag** zugeordnet (reserviert) –
    bis zu dessen Restbedarf für diesen Artikel. So „klaut" kein fremder Auftrag den Nachschub
    per FIFO, und der blockierte Schritt des Eltern wird bei der nächsten Auswertung ``active``.

    Ist der Artikel das **Subjekt** des Eltern (dessen Output-Artikel – gleich ob Bestands-
    Verkauf oder Erzeugungsauftrag), werden die Stück zusätzlich als Subjekt markiert
    (``subject_of_order_id`` + Verarbeitungs-Historie), damit Bewegung/Abschluss sie sehen.
    Für **Komponenten** genügt die Reservierung (der Verbrauch-Schritt findet sie FIFO unter
    der Auftragsnummer). No-op für normale Aufträge."""
    if getattr(order, "reason", None) != "supply" or not order.parent_order_id:
        return
    parent = (
        db.query(Order)
        .filter(Order.object_id == order.parent_order_id, Order.is_active == True)
        .first()
    )
    if not parent or parent.status not in ("draft", "released"):
        return
    remaining = order_shortfalls(db, parent).get(order.article_id, 0)
    if remaining <= 0:
        return
    from .order_lines import lines_for
    from .subject import record_link
    # Ist das Nachschub-Ergebnis das **Subjekt** des Eltern (dessen Output-Artikel – Einzel-
    # Artikel ODER eine Position), wird es zusätzlich als Subjekt markiert (``subject_of_order_id``
    # + Historie), damit Bewegung/Abschluss es sehen. Das gilt **unabhängig von der Auftragsart**:
    # ein Bestands-Verkauf, der Nachschub desselben Artikels bekommt, EBENSO wie ein
    # Erzeugungsauftrag, der nach Ausschuss ein Stück nachfertigen lässt. Nur ein reiner
    # **Komponenten**-Nachschub (anderer Artikel) bleibt bloss reserviert (der Verbrauch-Schritt
    # findet ihn FIFO unter der Auftragsnummer). No-op für normale Aufträge.
    is_subject = (
        order.article_id == parent.article_id
        or any(l.article_id == order.article_id for l in lines_for(db, parent))
    )
    produced = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True,
                Instance.quality == "passed", Instance.disposition == "in_stock")
        .order_by(Instance.object_id)
        .all()
    )
    for inst in produced:
        if remaining <= 0:
            break
        take = min(free_qty(inst), remaining)
        if take <= 0:
            continue
        reserve(inst, parent.id, take)
        if is_subject:
            inst.subject_of_order_id = parent.id
            record_link(db, inst.object_id, parent.id)
        remaining -= take
    emit(db, "supply.pegged", object_type="order", object_id=parent.object_id,
         payload={"supply": order.object_id, "article_id": order.article_id})


def required_sample(quantity: int | None, sample_percent: int | None) -> int:
    """Zu prüfende Stückzahl der Eingangskontrolle (mind. 1, wenn Menge > 0)."""
    qty = quantity or 0
    pct = sample_percent if sample_percent is not None else 100
    if qty <= 0 or pct <= 0:
        return 0
    return min(qty, max(1, ceil(qty * pct / 100)))
