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

from decimal import Decimal
from math import ceil

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import (
    ArticleProcessStep, Disposal, Document, Inspection, Instance, Movement, Order,
    PurchaseOrder, ResourceUsage, Sale,
)
from ..models.base import utcnow
from .events import emit
from .inventory import available, in_stock_clauses, is_blocked, unblocked_clauses
from .quantity import ONE, ZERO, to_qty
from .reservation import free_qty, release, reserve, reserved_for, take as take_qty

# Label & Fachtabelle je Schritt-Typ kommen aus der **deklarativen Registry**
# (``domain.event_types``) – EINE Quelle der Wahrheit statt verstreuter Dicts.
STEP_LABELS = {key: et.label for key, et in event_types.REGISTRY.items()}

_MODEL_BY_NAME = {
    "PurchaseOrder": PurchaseOrder, "Inspection": Inspection, "Movement": Movement,
    "Disposal": Disposal, "ResourceUsage": ResourceUsage, "Sale": Sale,
    "Document": Document,
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
    from .subject import is_fixed_subject
    custom = order_custom_steps(db, order.id)
    if custom:
        return custom
    # Abweichung ODER Retoure (Unter-Auftrag, reason='deviation'|'return'): NUR eigene Schritte
    # (die Auflösung/Rücknahme) – nie der Artikel-Prozess. Ohne eigene Schritte (noch) kein
    # Ablauf. Ein **Nachschub** (reason='supply') ist dagegen ein normaler Produktionsauftrag.
    if is_fixed_subject(order):
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
    """Roh-Status aus der (bereits aufgelösten) Fachzeile: 'done'|'open'|'failed'. Rein.

    **Die Regel ist EINE, die Werte stehen in der Registry** (``domain/event_types.py``):
    dort deklariert jeder Schritttyp, welches Feld seinen Stand trägt und welche Werte
    «erledigt» bzw. «fehlgeschlagen» bedeuten. Ohne ``status_field`` ist die blosse
    EXISTENZ der Fachzeile die Erledigung (Marker-Zeile: Bewegung, Ressource, Aussondern).

    Vorher stand hier eine if/elif-Kette über die Schritttypen – dieselbe Aussage, nur
    verteilt: ein neuer Typ musste in der Registry UND hier gepflegt werden, und beide
    konnten still auseinanderlaufen.

    Die eine Ausnahme ist bewusst **generisch** formuliert: ein Fehlschlag, den ein
    Folgeauftrag geklärt hat (``resolved_by_order_id``), gilt als erledigt – der Befund
    selbst bleibt fehlgeschlagen. Heute trägt nur die Datenerfassung dieses Feld; die
    Regel «geklärt ist erledigt» gilt aber für jeden Typ, der es bekommt."""
    et = event_types.REGISTRY.get(step_type)
    if not fact or et is None:
        return "open"
    if et.status_field is None:
        return "done"
    value = getattr(fact, et.status_field, None)
    if value in et.done:
        return "done"
    if value in et.failed:
        return "done" if getattr(fact, "resolved_by_order_id", None) else "failed"
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
            raise HTTPException(409, detail=_not_now(db, order, label))
        return match["step"]
    active = next((s for s in steps if s["step_type"] == step_type and s["state"] == "active"), None)
    if not active:
        raise HTTPException(409, detail=_not_now(db, order, label))
    return active["step"]


def _not_now(db: Session, order: Order, label: str) -> str:
    """Warum geht dieser Schritt gerade nicht? – **den echten Grund** nennen.

    «… ist (noch) nicht an der Reihe» stimmt zwar immer, hilft aber nicht, wenn der Auftrag
    ruht: dann liegt es nicht an der Reihenfolge, sondern an einer offenen Entscheidung."""
    if is_paused(db, order):
        return ("Der Prozess ruht, weil dem Auftrag etwas fehlt. Bitte zuerst entscheiden: "
                "Auftrag pausieren · Instanz ersetzen · Auftragsmenge reduzieren.")
    return f"{label} ist (noch) nicht an der Reihe"


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

def sold_amounts_for_order(db: Session, order_object_id: int | None) -> dict[int, Decimal]:
    """Bereits **durch diesen Auftrag verkaufte** Mengen je Instanz ({instanz_objektnr: menge}),
    rekonstruiert aus dem Event-Strom (der ökonomischen Wahrheit): ``sell_order_subjects``
    schreibt je Abgang ein ``inventory.decreased``-Event auf die Instanz mit ``payload.order``
    = Auftrags-Objektnummer (Verschrottung trägt ``reason='scrapped'`` und zählt NICHT).

    Zwei Nutzer: (a) ``_subject_shortfalls`` – eine von DIESEM Auftrag verkaufte Menge ist
    **geliefert**, nicht «verloren» (sonst meldete ein bezahlter Verkauf eine Phantom-
    Fehlmenge und Nachschub/Deckung würden doppelt produzieren); (b) die **Retoure** – eine
    voll konsumierte Chargen-Instanz (Menge 0) kennt ihre verkaufte Menge selbst nicht mehr."""
    from ..models import Event
    if not order_object_id:
        return {}
    out: dict[int, Decimal] = {}
    rows = (
        db.query(Event)
        .filter(Event.event_type == "inventory.decreased", Event.object_type == "instance",
                Event.payload["order"].astext == str(order_object_id))
        .all()
    )
    for ev in rows:
        payload = ev.payload or {}
        if payload.get("reason") or ev.object_id is None:
            continue   # Verschrottung u. ä. – kein Verkaufs-Abgang
        out[ev.object_id] = out.get(ev.object_id, ZERO) + to_qty(payload.get("quantity", 0))
    return out


def deviated_quantities(db: Session, order: Order) -> dict[int, Decimal]:
    """Instanzen dieses Auftrags, die gerade in einer **offenen Abweichung** stecken.

    **Eine Abweichung hat keinen eigenen Pause-Mechanismus – sie nimmt ihr Stück heraus.**
    Ein Stück in Klärung ist für den Eltern-Auftrag weder verloren noch gesichert, es ist
    schlicht **fehlend**: es zählt nicht mehr als gesichert, und der Auftrag hat damit eine
    Unterdeckung. Dass er darüber zum Stillstand kommt, ist die Folge der EINEN Pause-Regel
    (``is_paused``) und nicht eines zweiten Zustands neben ihr – es gibt kein «pausiert wegen
    Abweichung» getrennt von «es fehlt etwas», weil beides derselbe Sachverhalt ist.

    Genau das macht die Abweichung austauschbar mit jedem anderen Grund: eine Aussteuerung,
    ein Ausschuss oder eine weggenommene Reservierung erzeugen dieselbe Fehlmenge und damit
    dieselbe Pause – und werden mit denselben drei Antworten aufgelöst (pausieren · ersetzen ·
    Menge reduzieren).

    Geliefert wird **je Instanz die betroffene MENGE**, nicht bloss die Instanz: eine
    Abweichung an EINER Schraube einer 500er-Charge nimmt dem Auftrag genau eine, nicht
    fünfhundert. Die Menge steht dort, wo sie hingehört – im Anspruch der Abweichung
    (``instances.reservations``); fehlt er (Altbestand), gilt die ganze Instanz."""
    from .subject import order_instances
    # **Massgeblich ist die Instanz, nicht der Eltern-Zeiger.** Eine Abweichung kann an der
    # Instanz gemeldet worden sein und dabei an einem GANZ ANDEREN Auftrag hängen (dem
    # Herkunftsauftrag). Für diesen Auftrag zählt allein: steckt eines seiner Stücke gerade
    # in einer offenen Abweichung? Vorher wurden nur die eigenen Kinder gezählt – ein an der
    # Instanz gemeldeter Fehler liess den Auftrag ungerührt weiterlaufen (Testnotiz #348).
    from .reservation import reserved_for
    mine = [i for i in order_instances(db, order) if i.subject_of_order_id]
    if not mine:
        return {}
    # **Nur eine FREIGEGEBENE Abweichung nimmt etwas heraus** (Testnotiz #370): ein Entwurf
    # ist noch im Entstehen – Artikel, Menge und Instanzen können sich ändern. Er merkt vor
    # (``reservation.claim``: für FIFO ist das Stück gesprochen), aber er nimmt dem laufenden
    # Auftrag nichts weg und hält ihn nicht an. Das geschieht mit der Freigabe, und dort wird
    # auch gefragt, wie es beim anderen weitergeht.
    open_devs = {
        r[0] for r in db.query(Order.id).filter(
            Order.id.in_({i.subject_of_order_id for i in mine}),
            Order.reason == "deviation", Order.is_active == True,
            Order.status == "released").all()
    }
    # **Sich selbst zählt eine Abweichung nie.** Fragt die Abweichung nach ihren eigenen
    # «in Klärung» steckenden Stücken, sind das nicht ihre eigenen – sonst gäbe sie beim
    # Abschluss nichts frei (die Statusänderung ist zum Zeitpunkt der Abfrage noch nicht
    # geflusht, die Datenbank sieht sie also weiterhin als offen).
    open_devs.discard(order.id)
    out: dict[int, Decimal] = {}
    for i in mine:
        if i.subject_of_order_id not in open_devs:
            continue
        share = reserved_for(i, i.subject_of_order_id)
        out[i.id] = share if share > 0 else to_qty(i.quantity)
    return out


def _subject_shortfalls(db: Session, order: Order) -> dict[int, Decimal]:
    """Fehlmenge(n) des **Subjekts** je Artikel ({article_id: qty}) – **EINE Formel für
    ALLE Auftragsarten** (kein ``subject_kind``-Sonderpfad): ``Soll − Gesichert``.

    - **Soll** = Bestellmenge (Einzel-Artikel ``order.quantity``; Mehrpositionen je Position).
    - **Gesichert** = gute Einheiten, die der Auftrag bereits hat: (a) für ihn **reservierte**
      Bestands-Instanzen (FIFO ab Lager / gepinnt / gepeggter Nachschub) PLUS (b) **selbst
      erzeugte** gute Instanzen (Erzeugungsauftrag). Terminal verlorene (verschrottet/verkauft/
      verbaut), durchgefallene **oder in einer offenen Abweichung gebundene** zählen NICHT –
      letztere sind in Klärung, also weder verloren noch verfügbar (``deviated_quantities``).

    So reagiert ein **Erzeugungsauftrag auf Ausschuss** identisch wie ein **Bestands-Auftrag**
    auf eine ausgesteuerte Reservierung – dieselbe Unterdeckung, dieselben Deckungs-Wege, kein
    Sonderfall. Ausgenommen ist nur die **Abweichung**: ihr Subjekt sind fixierte Instanzen
    (``subject_of_order_id``), kein aus Lager/Produktion zu erfüllendes Soll."""
    from .subject import is_fixed_subject
    # **Nur ein LAUFENDER Auftrag kann etwas schulden.** Ein Entwurf hat noch nichts zugesagt
    # (und noch keine Instanzen), ein abgeschlossener/abgebrochener hat abgerechnet – dort
    # sind Reservierung und Subjekt-Bindung längst gelöst, «Soll − Gesichert» ergäbe die
    # volle Menge als Phantom-Fehlmenge (Testnotiz #347: «Es fehlt 1×» an einem fertigen
    # Auftrag). Die Fehlmenge ist eine Aussage über offene Arbeit, nicht über Geschichte.
    if order.status != "released":
        return {}
    if is_fixed_subject(order):
        return {}   # Abweichung/Retoure: Subjekt steht fest (gewählte/verkaufte Instanzen)
    targets = _subject_targets(db, order)
    if not targets:
        return {}
    secured = _secured_amounts(db, order)
    return {a: t - secured.get(a, ZERO) for a, t in targets.items() if t - secured.get(a, ZERO) > 0}


def _subject_targets(db: Session, order: Order) -> dict[int, Decimal]:
    """**Soll** je Artikel: die Bestellmenge – Einzel-Artikel am Auftrag, sonst je Position."""
    from .order_lines import lines_for
    if order.article_id and order.quantity:
        return {order.article_id: to_qty(order.quantity)}
    targets: dict[int, Decimal] = {}
    for line in lines_for(db, order):
        targets[line.article_id] = targets.get(line.article_id, ZERO) + to_qty(line.quantity)
    return targets


def _secured_amounts(db: Session, order: Order) -> dict[int, Decimal]:
    """**Gesichert** je Artikel – gute Einheiten, die der Auftrag bereits hat. Drei Quellen:
    für ihn **reservierte** Bestands-Instanzen, **selbst erzeugte** gute Instanzen und was er
    bereits **verkauft** hat (das ist geliefert, nicht verloren)."""
    from .subject import TERMINAL_DISPOSITIONS
    secured: dict[int, Decimal] = {}
    # **Was in Klärung steckt, zählt mengengenau** – nicht als ganze Instanz: eine
    # Abweichung an EINER Schraube einer 500er-Charge nimmt dem Auftrag genau eine.
    in_clarification = deviated_quantities(db, order)
    for inst in db.query(Instance).filter(
        Instance.reservations.has_key(str(order.id)), Instance.is_active == True  # noqa: W601
    ).all():
        # FIX: Durchgefallene zählen laut Kontrakt (Docstring) NICHT als «gesichert» – der
        # Filter fehlte aber: eine gesperrte reservierte Instanz deckte das Soll
        # scheinbar weiter, der Schritt blockierte nie und der Verkauf hätte still eine
        # durchgefallene Einheit unterschlagen (sell_order_subjects überspringt failed).
        if is_blocked(inst):
            continue
        # Der Anspruch selbst ist schon gekürzt, wenn eine Abweichung ihn übernommen hat
        # (``reservation.claim``) – hier bleibt nichts weiter abzuziehen.
        secured[inst.article_id] = secured.get(inst.article_id, ZERO) + reserved_for(inst, order.id)
    for inst in db.query(Instance).filter(
        Instance.order_id == order.id, Instance.is_active == True, *unblocked_clauses()
    ).all():
        if (inst.disposition or "") in TERMINAL_DISPOSITIONS:
            continue
        if (inst.reservations or {}).get(str(order.id)):
            continue   # schon über die Reservierung (oben) gezählt – nicht doppelt
        # Selbst erzeugte Stücke tragen keine Reservierung des Auftrags – hier greift die
        # Klärungs-Menge direkt: von 5 erzeugten ist bei einer Abweichung an 1 noch 4 gut.
        rest = to_qty(inst.quantity) - in_clarification.get(inst.id, ZERO)
        if rest > 0:
            secured[inst.article_id] = secured.get(inst.article_id, ZERO) + rest
    # FIX: was DIESER Auftrag bereits **verkauft** hat, ist GELIEFERT – nicht «verloren».
    # Ohne diesen Anteil meldete ein bezahlter Verkauf (Reservierung verbraucht, Ware sold)
    # die volle Menge als Fehlmenge: nicht-gesperrte Folgeschritte blockierten dauerhaft und
    # «Nachschub anlegen»/Shop-Retry hätten die schon gelieferte Menge NOCHMALS produziert.
    # (Ein durch eine Abweichung ausgesteuertes Teil bleibt dagegen ehrlich eine Fehlmenge:
    # Verschrottung zählt hier nicht, und fremdverkaufte Instanzen tragen einen anderen
    # ``payload.order``.)
    sold = sold_amounts_for_order(db, order.object_id)
    if sold:
        insts = {
            i.object_id: i
            for i in db.query(Instance).filter(Instance.object_id.in_(sold.keys())).all()
        }
        for obj_id, qty in sold.items():
            inst = insts.get(obj_id)
            # Eine NACH dem Verkauf verschrottete Instanz (Abweichung: Kundenware vor dem
            # Versand zerstört) ist NICHT geliefert – ihre Fehlmenge wird ehrlich wieder
            # sichtbar (Deckungs-Wege wie gehabt).
            if inst is None or inst.disposition == "scrapped":
                continue
            secured[inst.article_id] = secured.get(inst.article_id, ZERO) + qty
    return secured


def subject_shortfalls(db: Session, order: Order) -> dict[int, Decimal]:
    """Öffentliche Sicht auf die **Subjekt**-Fehlmengen eines Auftrags ({article_id: qty}) –
    Grundlage der Wiederherstellung nach einer Aussteuerung (aus Lager decken / Menge
    reduzieren, ``services/recovery.py``). Nur das Subjekt (Fertigware), NICHT die Komponenten."""
    return _subject_shortfalls(db, order)


def _component_needs(db: Session, order: Order) -> dict[int, Decimal]:
    """Offener Komponentenbedarf (consume) über alle Ressourcen-Schritte, je Artikel.
    **Bereits verbrauchte** Schritte (Fachzeile vorhanden) zählen nicht mehr mit – sonst
    entstünde nach dem Verbrauch ein Phantom-Bedarf (überflüssiger Nachschub)."""
    from .order_lines import effective_quantity
    needs: dict[int, Decimal] = {}
    resource_steps = [d for d in order_step_defs(db, order) if d.step_type in RESOURCE_STEP_TYPES]
    if not resource_steps:
        return needs
    qty = to_qty(effective_quantity(db, order))
    rows = _facts(db, order, "resource")
    sole = len(resource_steps) == 1
    for d in resource_steps:
        if _resolve_fact(d, rows, sole) is not None:
            continue   # bereits gebucht (verbraucht) → kein offener Bedarf mehr
        for line in (d.resource_lines or []):
            if (line.get("mode") or "consume") != "consume":
                continue
            aid = line["article_id"]
            needs[aid] = needs.get(aid, ZERO) + to_qty(line.get("quantity", 1)) * qty
    return needs


def _component_shortfall(db: Session, order: Order, step: ArticleProcessStep) -> dict[int, Decimal]:
    """Der **eigene** Material-Bedarf dieses Schritts, soweit ungedeckt ({article_id: qty}).

    Nur die Ressource hat einen: sie verbraucht Komponenten (need − verfügbar; verfügbar =
    frei am Lager + für diesen Auftrag reserviert). Jeder andere Schritttyp arbeitet am
    Subjekt des Auftrags und hat darum keinen eigenen."""
    if step.step_type not in RESOURCE_STEP_TYPES:
        return {}
    from .order_lines import effective_quantity
    out: dict[int, Decimal] = {}
    qty = to_qty(effective_quantity(db, order))
    for line in (step.resource_lines or []):
        if (line.get("mode") or "consume") != "consume":
            continue
        aid = line["article_id"]
        need = to_qty(line.get("quantity", 1)) * qty
        have = available(db, aid, order.id)
        if need > have:
            out[aid] = out.get(aid, ZERO) + (need - have)
    return out


def step_shortfalls(db: Session, order: Order, step: ArticleProcessStep) -> dict[int, Decimal]:
    """Woran hängt dieser Schritt? – die **Fehlmenge des Auftrags** (er ruht als Ganzes)
    plus sein **eigener** Material-Bedarf ({article_id: qty}); leer = frei.

    Die Aufteilung ist die Trennlinie zwischen den beiden Ebenen: **das Subjekt gehört dem
    Auftrag** (fehlt es, ruht er – siehe ``is_paused``), **das Material gehört dem Schritt**
    (fehlt es, wartet nur er). Welcher Schritttyp gerade dran ist, spielt dabei keine Rolle
    mehr – die frühere Liste ``SUBJECT_STEP_TYPES`` und das Registry-Flag ``hands_over``
    sind damit beide entfallen.

    Gebraucht wird die Zuordnung «welcher Schritt vermisst welchen Artikel» für die Spur
    (``blocked_step_for_article`` → Nachschub-Ursprung, Deckungs-Entscheid am Schritt)."""
    out = dict(_subject_shortfalls(db, order))
    for aid, missing in _component_shortfall(db, order, step).items():
        out[aid] = out.get(aid, ZERO) + missing
    return out


def blocked_step_for_article(db: Session, order: Order, article_id: int) -> int | None:
    """Der Schritt, dessen Fehlmenge genau diesen Artikel vermisst – oder ``None``.

    Zwei Nutzer, dieselbe Frage: der **Nachschub** merkt sich damit, aus welchem Schritt sein
    Bedarf stammt (``orders.origin_step_id``), und die **Deckung** schreibt ihre Spur an den
    Schritt, an dem entschieden wurde (``OrderStepInfo.resolutions``). Findet sich kein
    blockierter Schritt (Aktion von Hand angestossen), bleibt die Angabe leer."""
    for info in build_order_steps(db, order):
        if info["state"] != "blocked":
            continue
        step = info["step"]
        if any(a == article_id for a in step_shortfalls(db, order, step)):
            return step.id
    return None


def is_paused(db: Session, order: Order) -> bool:
    """**Ruht dieser Auftrag?** – ihm fehlt sein Subjekt, also geht KEIN Schritt weiter.

    Das ist die eine Pause-Regel des Systems, und sie hat **keinen eigenen Mechanismus**:
    Was einen Auftrag anhält, ist immer dasselbe – ihm fehlt etwas (``_subject_shortfalls``).
    Eine offene **Abweichung** nimmt ihr Stück heraus (``deviated_quantities``) und erzeugt
    damit genau diese Fehlmenge; eine Aussteuerung, ein Ausschuss oder eine weggenommene
    Reservierung tun dasselbe. Es gibt darum kein «pausiert wegen Abweichung» neben
    «blockiert wegen Fehlmenge» – es ist EIN Zustand mit EINER Ursache.

    Zwischenzeitlich hielt eine Fehlmenge nur die Schritte auf, die die Menge **weitergeben**
    (Verkauf/Ressource, Registry-Flag ``hands_over``) – erfassen/aussondern/bewegen liefen
    weiter. Das ist zurückgenommen (Testnotiz #354): solange eine Abweichung offen ist, DARF
    der Eltern-Prozess nicht weitergeführt werden. Der Grund ist nicht Vorsicht, sondern
    Reihenfolge – wer weiterarbeitet, während noch offen ist, ob ein Stück ausgesteuert wird,
    arbeitet womöglich am falschen Bestand. Und die Pause ist heute kein stiller Nebeneffekt
    mehr: sie ist **die gewählte Antwort** «Auftrag pausieren» aus der Unterdeckungs-Frage –
    wer nicht warten will, ersetzt oder reduziert die Menge und läuft sofort weiter.

    Zweiter, unabhängiger Grund: Material ist **unterwegs** (offene Bereitstellung) – es
    existiert, liegt nur noch nicht hier. Dort gibt es nichts zu entscheiden."""
    if _subject_shortfalls(db, order):
        return True
    from .provisioning import open_provisioning
    return bool(open_provisioning(db, order))


def _step_blocked(db: Session, order: Order, step: ArticleProcessStep) -> bool:
    """Hält eine Fehlmenge diesen Schritt auf? – zwei Ebenen, dieselbe Frage.

    Der Auftrag ruht (``is_paused``) → jeder Schritt ruht mit. Sonst wartet ein Schritt nur
    noch auf sein **eigenes** Material (Ressource). Dass dabei nichts still unterliefert
    wird, sichert die andere Hälfte derselben Regel: ein Auftrag mit offener Fehlmenge
    **schliesst nicht ab** (``recompute_completion``)."""
    return is_paused(db, order) or bool(_component_shortfall(db, order, step))


def is_stalled(db: Session, order: Order) -> bool:
    """**Steckt dieser Auftrag fest?** – er hat einen fehlgeschlagenen Schritt.

    Ein fehlgeschlagener Schritt ist nicht wiederholbar; ohne menschliche Klärung
    (Abweichung, Abbruch) liefert der Auftrag nichts mehr. Wer wissen will, ob eine
    Fehlmenge «schon unterwegs» ist, muss das berücksichtigen – sonst zeigt ein Auftrag
    für immer «wartet auf …» und blendet dabei die Wege aus, die ihn befreien würden.

    Die Regel gab es bereits einmal (Auto-Nachbestellung), fehlte aber dort, wo sie
    genauso zählt: bei der Nachschub-Idempotenz und bei «worauf wartet der Auftrag».
    Jetzt steht sie an EINER Stelle und alle drei lesen sie."""
    return any(s["state"] == "failed" for s in order_step_infos(db, order))


def order_shortfalls(db: Session, order: Order) -> dict[int, Decimal]:
    """Alle nicht gedeckten Bedarfe des Auftrags, je Artikel aggregiert ({article_id: qty}) –
    Grundlage für den Nachschub (``services/supply.py``)."""
    agg: dict[int, Decimal] = {}
    for aid, subj in _subject_shortfalls(db, order).items():
        agg[aid] = agg.get(aid, ZERO) + subj
    for aid, need in _component_needs(db, order).items():
        have = available(db, aid, order.id)
        if need > have:
            agg[aid] = agg.get(aid, ZERO) + (need - have)
    return agg


def _worked_on_by_a_running_order(db: Session, order: Order, rows: list[Instance]) -> set[int]:
    """Instanzen, an denen noch ein **anderer laufender** Auftrag arbeitet (Testnotiz #332).

    An einer Instanz hängen höchstens zwei Aufträge: der **erzeugende** (``order_id``) und
    der, der sie gerade als **festes Subjekt** führt (``subject_of_order_id`` – Abweichung,
    Retoure). Ist einer davon noch ``released``, ist das Teil **nicht fertig**, ganz gleich
    welcher der beiden gerade abschliesst:

    * Abweichung fertig, Erzeugung läuft weiter → das Teil ist geklärt, nicht produziert.
      (Vorher wurde es hier freigegeben und erschien am Lager, während sein Auftrag noch
      lief – der gemeldete Fall.)
    * Erzeugung abgebrochen (``inactive``), Abweichung führt sie fort → niemand läuft mehr,
      die Abweichung gibt frei. Genau das war der Fix aus Notiz #262, und er bleibt gültig,
      weil ein abgebrochener Auftrag nicht ``released`` ist.

    Eine Abfrage für alle Zeilen (kein N+1)."""
    others = {
        oid for inst in rows for oid in (inst.order_id, inst.subject_of_order_id)
        if oid is not None and oid != order.id
    }
    if not others:
        return set()
    running = {
        r[0] for r in db.query(Order.id).filter(
            Order.id.in_(others), Order.is_active == True, Order.status == "released").all()
    }
    if not running:
        return set()
    return {
        inst.id for inst in rows
        if inst.order_id in running or inst.subject_of_order_id in running
    }


def release_instances(db: Session, order: Order) -> None:
    """Bestands-Instanzen eines abgeschlossenen Auftrags freigeben (pending → passed).

    Erst ein abgeschlossener Auftrag bedeutet «fertig & ab Lager verfügbar»: die
    Instanzen werden zu «Freigegeben» und damit für den Ressource-Verbrauch (FIFO)
    nutzbar. ``released_at`` ist die FIFO-Basis. Bereits bewertete Instanzen
    (failed/consumed/passed) bleiben unverändert. **Terminale Teile** (verschrottet/verkauft/
    verbaut) werden NICHT ans Lager freigegeben – nur noch «im Prozess» befindliche.

    **Freigegeben wird von dem Auftrag, der zuletzt an der Instanz gearbeitet hat** – nicht
    nur vom erzeugenden (Testnotiz #262). Wird ein Auftrag abgebrochen und ein
    **Abweichungsauftrag** führt seine Instanzen fort (``subject_of_order_id``), bleibt deren
    ``order_id`` beim abgebrochenen Original: Nur auf den Erzeuger zu schauen hiess, dass
    diese Instanzen **nie** freigegeben werden – für immer «Im Prozess», unsichtbar für FIFO
    und Bestandszählung. Darum zählt hier BEIDES: erzeugt von diesem Auftrag **oder** von ihm
    als Subjekt verarbeitet.

    **Was in einer offenen Abweichung steckt, gibt dieser Auftrag NICHT frei.** Seit die
    Abweichung ihr Stück herausnimmt statt den Auftrag anzuhalten, kann der Eltern-Auftrag
    abschliessen, während die Klärung noch läuft – ein Teil in Klärung würde dabei sonst mit
    ans Lager freigegeben. Freigegeben wird es von dem Auftrag, der zuletzt daran arbeitet:
    der Abweichung.

    **Und umgekehrt genauso** (Testnotiz #332): schliesst die **Abweichung** ab, während der
    Erzeugungsauftrag noch läuft, ist das Teil nicht fertig – es ist bloss geklärt und geht
    zurück in den laufenden Prozess. «Zuletzt daran gearbeitet» heisst darum präzise: *es
    arbeitet kein anderer Auftrag mehr daran* (``_worked_on_by_a_running_order``)."""
    now = utcnow()
    in_clarification = deviated_quantities(db, order)
    rows = (
        db.query(Instance)
        .filter(
            or_(Instance.order_id == order.id, Instance.subject_of_order_id == order.id),
            Instance.is_active == True,
            Instance.quality == "pending", Instance.disposition == "in_process",
        )
        .all()
    )
    still_running = _worked_on_by_a_running_order(db, order, rows)
    total = ZERO
    for inst in rows:
        if inst.id in in_clarification or inst.id in still_running:
            continue
        inst.quality = "passed"          # QC-Verdikt: freigegeben
        inst.disposition = "in_stock"    # Verbleib: am Lager (ab jetzt verbrauchbar)
        if inst.released_at is None:
            inst.released_at = now
        total += to_qty(inst.quantity)
    # Bestands-Zugang als Domain-Event mit DEKLARIERTER Polarität festhalten – so wird
    # der Event-Strom zur ökonomischen Wahrheit (Bestand = Projektion über Events).
    if total:
        emit(db, "inventory.increased", object_type="order", object_id=order.object_id,
             payload={"article_id": order.article_id, "quantity": total,
                      "delta": total, "polarity": event_types.INCREASE})


def sell_order_subjects(db: Session, order: Order) -> None:
    """Bestands-Abgang eines Verkaufs buchen – **idempotent**, damit der Label-Wechsel dann
    passiert, **wann er wirklich geschieht**: aufgerufen (a) sobald der **Verkauf bezahlt** ist
    (der `sale`-Schritt ist durch → «verkauft») UND (b) beim Auftrags-Abschluss (deckt make-to-
    order, dessen Instanzen erst während des Prozesses entstehen).

    Enthält der Ablauf einen **Verkauf** (kind='sale'), verlässt die **für diesen Auftrag
    reservierte Menge** den Bestand – mengengenau (keine Teilung): eine vollständig verkaufte
    Instanz wird ``sold``, eine teilverkaufte Charge bleibt mit Restmenge am Lager. Eine
    **Retoure** (kind='credit') verkauft NICHT (reine Gutschrift). Durchgefallene bleiben."""
    from .subject import is_return
    if is_return(order):
        return   # Retoure/Erstattung ist eine Gutschrift – kein Verkaufs-Abgang
    if not any(d.step_type == "sale" for d in order_step_defs(db, order)):
        return
    # (a) Bestands-Verkauf (FIFO): die für diesen Auftrag **reservierte** Menge verlässt den
    #     Bestand (mengengenau). KEIN Artikel-Filter (Mehrpositionen-Verkauf). Idempotent –
    #     ist die Reservierung schon abgebucht, findet die Query nichts mehr.
    subjects = (
        db.query(Instance)
        .filter(Instance.reservations.has_key(str(order.id)),  # noqa: W601
                Instance.is_active == True)
        .all()
    )
    for inst in subjects:
        if is_blocked(inst):
            continue
        sold = reserved_for(inst, order.id)
        take_qty(inst, sold, by_order_id=order.id)   # Menge mindern + eigenen Anspruch lösen
        if to_qty(inst.quantity) <= 0:
            inst.disposition = "sold"            # vollständig verkauft
        emit(db, "inventory.decreased", object_type="instance", object_id=inst.object_id,
             payload={"quantity": sold, "delta": -sold, "polarity": event_types.DECREASE,
                      "order": order.object_id})
    # (b) Made-to-Order: die **unter diesem Auftrag erzeugten**, freigegebenen Instanzen werden
    #     direkt verkauft (idempotent – schon verkaufte sind nicht mehr in_stock).
    produced = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True,
                *in_stock_clauses())
        .all()
    )
    for inst in produced:
        inst.disposition = "sold"
        qty = to_qty(inst.quantity)
        emit(db, "inventory.decreased", object_type="instance", object_id=inst.object_id,
             payload={"quantity": qty, "delta": -qty,
                      "polarity": event_types.DECREASE, "order": order.object_id})


def return_subjects_to_stock(db: Session, order: Order) -> None:
    """Physischer Rückfluss einer **Retoure** – **idempotent**, aufgerufen (a) sobald die
    **Rückgabe-Bewegung** durch ist (die Ware ist wieder da → «freigegeben») UND (b) beim
    Abschluss. Eine verkaufte Subjekt-Instanz, die per **Bewegung** vom Kunden **weg**
    gebracht wurde, kommt in den Bestand zurück (sold → in_stock). Wurde NICHTS bewegt
    (Kulanz: der Kunde behält die Ware) → sie bleibt 'sold' (nur Geld zurück).
    Gesperrte (durchgefallen/ausgesetzt, z. B. defekt) bleiben gesperrt und werden verschrottet.

    Die Rückkehr wird daran erkannt, dass die Instanz **nicht mehr beim Kunden liegt** –
    nicht daran, an welchen Halter-Typ sie gebracht wurde. (Früher stand hier
    ``location_type == 'lagerplatz'``; mit dem Wegfall des Lagerplatz-Typs hätte diese
    Bedingung nie mehr zugetroffen und keine Retoure wäre je wieder eingebucht worden.)"""
    from .sale import customer_for_order
    from .subject import is_return, order_instances
    if not is_return(order):
        return
    # Der Kunde steht am **Original-Verkauf** (der Retoure-Auftrag selbst trägt nur
    # Gutschriften, ``kind='credit'`` – ``customer_for_order`` fände dort nichts).
    # Liegt die Instanz noch bei ihm, wurde nichts zurückbewegt (Kulanz). Ohne
    # auflösbaren Kunden gilt eine quittierte Rückgabe-Bewegung als Rückkehr.
    _parent = (
        db.query(Order).filter(Order.id == order.parent_order_id).first()
        if order.parent_order_id else None
    )
    _cust = customer_for_order(db, _parent) if _parent else None
    _cust_oid = _cust.object_id if _cust else None
    # Die zurückkommende Menge ist die unter dem ORIGINAL-Verkauf abgebuchte Menge
    # (Event-Strom) – nicht pauschal 1: eine 5-kg-Charge kam sonst als 1 kg zurück.
    # Fallback 1 deckt Einzelteile/Altdaten ohne Events (jede Einzelteil-Instanz = 1 Stück).
    sold_amounts = sold_amounts_for_order(db, order.parent_order_id)

    # Chargen-Slice (Teilmengen-Verkauf): erst buchen, wenn die Rückgabe-Bewegung
    # quittiert ist (die Ware ist physisch wieder da) – die Slice-Instanz selbst wird
    # dabei NICHT bewegt (sie war nie weg; die Teilmenge fliesst in sie zurück).
    movement_done = (
        db.query(Movement.id)
        .filter(Movement.order_id == order.id, Movement.is_active == True)
        .first() is not None
    )
    for inst in order_instances(db, order):
        if is_blocked(inst) or (inst.disposition or "") in ("scrapped", "consumed"):
            continue
        _restock_one(db, order, inst, _cust_oid, sold_amounts, movement_done)


def _already_restocked(db: Session, order: Order, inst) -> bool:
    """Idempotenz-Marker: der Rückfluss DIESER Retoure in DIESE Instanz wurde bereits
    gebucht (das ``inventory.increased``-Event mit reason='return' ist der Beleg)."""
    from ..models import Event
    for ev in db.query(Event).filter(
        Event.event_type == "inventory.increased", Event.object_type == "instance",
        Event.object_id == inst.object_id,
        Event.payload["order"].astext == str(order.object_id),
    ).all():
        if (ev.payload or {}).get("reason") == "return":
            return True
    return False


def _restock_one(db: Session, order: Order, inst, cust_oid: int | None,
                 sold_amounts: dict, movement_done: bool) -> None:
    """Eine einzelne Subjekt-Instanz einer Retoure zurückbuchen – **ganz oder als Teilmenge**.

    Ganz verkauft → Rückkehr heisst «liegt nicht mehr beim Kunden»; Chargen-Slice → die
    verkaufte Teilmenge fliesst mengengenau in die (nie verschwundene) Original-Charge
    zurück. Beides bucht nur bei quittierter Rückgabe-Bewegung; wurde nichts bewegt
    (Kulanz), bleibt die Ware beim Kunden."""
    if inst.disposition == "sold":
        # Ganz verkaufte Instanz: Rückkehr = sie liegt nicht mehr beim Kunden.
        still_at_customer = (
            cust_oid is not None
            and inst.location_type == "user" and inst.location_id == cust_oid
        )
        if still_at_customer or not movement_done:
            return   # nicht zurückbewegt → Ware bleibt beim Kunden (sold)
        # **Zurück kommt, was hinausging.** Massgeblich ist die beim Verkauf abgebuchte
        # Menge (Event-Strom); erst wenn es die nicht gibt (Altdaten), zählt die Menge
        # auf der Instanz, und ganz zuletzt «ein Stück» für ein Einzelteil ohne beides.
        # Vorher stand hier ein ``max(…, ONE)`` – dieser feste Boden machte aus einer
        # ganz verkauften 0.5-kg-Charge bei der Rückgabe **1 kg**: der Bestand wuchs bei
        # jeder Retoure einer Bruchmenge. Eine Menge hat keinen Mindestwert von 1;
        # genau diese Verwechslung von «Stück zählen» und «Menge messen» bewacht
        # ``tests/test_quantity_rules.py``.
        back = sold_amounts.get(inst.object_id) or to_qty(inst.quantity) or ONE
        inst.quantity = back
    else:
        # **Chargen-Slice**: der Original-Verkauf hat eine TEILMENGE dieser (weiterhin
        # bestehenden) Instanz abgebucht – die Teilmenge hat keine eigene Instanz. Die
        # Rückgabe bucht sie mengengenau in die Original-Charge zurück (Objektnummer
        # bleibt die physische Wahrheit). Event-idempotent (Abschluss ruft erneut).
        back = sold_amounts.get(inst.object_id, ZERO)
        if back <= 0 or not movement_done or _already_restocked(db, order, inst):
            return
        inst.quantity = to_qty(inst.quantity) + back
    inst.disposition = "in_stock"
    inst.quality = "passed"
    inst.released_at = utcnow()          # FIFO-Basis: ab jetzt wieder am Lager
    emit(db, "inventory.increased", object_type="instance", object_id=inst.object_id,
         payload={"quantity": back, "delta": back, "polarity": event_types.INCREASE,
                  "reason": "return", "order": order.object_id})


def _finalize_subjects(db: Session, order: Order) -> None:
    """Verbleib der Subjekt-Instanzen beim Abschluss – Sicherheitsnetz für beide Richtungen
    (Verkauf → sold, Retoure → in_stock). Beide Helfer sind idempotent; der Wechsel passiert
    i. d. R. schon früher (bei Zahlung bzw. Rückgabe-Bewegung), hier wird nur nachgezogen."""
    sell_order_subjects(db, order)
    return_subjects_to_stock(db, order)


def _spawn_recurrence(db: Session, order: Order, subject_object_ids: list[int] | None = None) -> None:
    """Wiederkehrenden Auftrag fortschreiben: ist der abgeschlossene Auftrag als
    wiederkehrend markiert, wird der **nächste** (Entwurf) erzeugt – Termin =
    bisheriger Anker + Periode. Die Wiederkehr wandert auf den neuen Auftrag (Kette).
    Kein eigenes Objekt, kein Cron – ein abgeschlossener Auftrag zieht den nächsten nach.

    Der Folge-Auftrag erbt zusätzlich den **individuellen Auftrags-Prozess** (die eigenen
    Schritte werden kopiert) und – bei einem Auftrag auf **gewählte Instanzen** (z. B. die
    zu wartende Maschine) – **dieselben Subjekt-Instanzen** (``subject_object_ids``, vor dem
    Lösen der Bindung erfasst): sie werden auf den Kind-Auftrag gepinnt und bei dessen
    Freigabe erneut reserviert (``subject.materialize_subject``). So läuft eine wiederkehrende
    Wartung mit Prozess-im-Auftrag vollständig weiter, statt leer herauszukommen. Ein reiner
    Produce-Auftrag (keine eigenen Schritte, keine gewählten Instanzen) verhält sich
    unverändert – er fährt beim nächsten Mal wieder den Artikel-Prozess."""
    if not getattr(order, "recurrence_active", False) or not order.recurrence_interval_days:
        return
    from datetime import timedelta

    from .deactivation import _copy_steps
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
    # (1) Individueller Auftrags-Prozess: die eigenen Schritte auf den Nachfolger kopieren.
    #     Ein Auftrag ohne eigene Schritte (Erzeugung über den Artikel-Prozess) kopiert nichts.
    _copy_steps(db, src_order_id=order.id, dst_order_id=child.id)
    # (2) Subjekt (gewählte Instanzen, z. B. die zu wartende Maschine) mitnehmen: auf den
    #     Kind-Auftrag pinnen – seine Freigabe reserviert sie dann erneut.
    if subject_object_ids:
        for inst in db.query(Instance).filter(
            Instance.object_id.in_(subject_object_ids), Instance.is_active == True,
        ).all():
            inst.subject_of_order_id = child.id
    order.recurrence_active = False   # Staffelstab an den Nachfolger
    emit(db, "order.recurrence_spawned", object_type="order", object_id=child.object_id,
         payload={"parent": order.object_id})


def recompute_completion(db: Session, order: Order) -> None:
    """Auftrag automatisch abschliessen, wenn alle Prozessschritte erledigt sind.

    Eine offene **Abweichung** hält den Auftrag NICHT mehr an (``deviated_quantities``):
    ihr Stück ist aus dem Auftrag herausgenommen und erscheint als Unterdeckung. Was noch
    in Klärung ist, gibt dieser Auftrag darum auch nicht frei."""
    # Bereitstellung ableiten: Jeder Schritt, der dran ist oder gerade war, bekommt sein
    # Material an den Ort, den er verlangt – als Unter-Auftrag, falls es woanders liegt.
    # Hier, weil ``recompute_completion`` nach JEDEM Schritt-Abschluss läuft: sobald der
    # nächste Schritt aktiv wird, ist die Bereitstellung fällig. Ein Bereitstellungs-
    # Auftrag selbst löst keine weitere aus (Rekursions-Schutz in ``ensure_provisioning``).
    from .provisioning import ensure_provisioning, open_provisioning
    ensure_provisioning(db, order, None)
    # Ein Auftrag ist nicht fertig, solange Material noch unterwegs ist – auch wenn alle
    # Schritte fachlich erledigt sind (z. B. Verkauf bezahlt, Ware aber noch nicht beim
    # Kunden). Sonst schlösse der Auftrag ab, bevor die Lieferung raus ist.
    if open_provisioning(db, order):
        return
    # **Kein Auftrag geht «fertig», solange ihm etwas fehlt.** Das ist die zweite Hälfte der
    # Unterdeckungs-Regel und der eigentliche Schutz gegen stilles Unterliefern: vorher hing
    # er zufällig daran, ob der Prozess einen blockierenden Schritt enthielt – ein Auftrag
    # über 4 Stück mit reiner Beschaffung schloss mit 3 gelieferten Stück ab, ohne Hinweis.
    # Der Mensch entscheidet über die drei Wege (Ersetzen · gezielt decken · ohne Ersatz
    # weiter); erst danach ist der Auftrag durch.
    if order.status != "completed" and all_steps_done(db, order) and not _subject_shortfalls(db, order):
        order.status = "completed"
        if order.completed_at is None:
            order.completed_at = utcnow()
        # Wiederkehrend: die (evtl.) gewählten Subjekt-Instanzen JETZT erfassen – bevor die
        # Bindung unten gelöst wird – damit sie auf den Nachfolge-Auftrag wandern können
        # (z. B. dieselbe Maschine erneut warten). Leer bei Erzeugungs-/Abo-Aufträgen.
        recurring_subjects = (
            [i.object_id for i in db.query(Instance).filter(
                Instance.subject_of_order_id == order.id, Instance.is_active == True).all()
             if i.object_id]
            if getattr(order, "recurrence_active", False) else []
        )
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
        _spawn_recurrence(db, order, recurring_subjects)   # wiederkehrend: nächsten Auftrag nachziehen
        _peg_supply_to_parent(db, order)     # Nachschub: erzeugte Stück an den Eltern pinnen
        emit(db, "order.completed", object_type="order", object_id=order.object_id)
        # War das eine Abweichung? Dann den Eltern-Auftrag neu bewerten: seine Fehlmenge
        # kann sich soeben geschlossen haben (das Stück ist geklärt zurück), womit er
        # weiterläuft bzw. abschliesst.
        if order.parent_order_id is not None:
            parent = db.query(Order).filter(Order.object_id == order.parent_order_id).first()
            if parent and parent.status == "released":
                # Die Abweichung IST die Klärung: ein fehlgeschlagener Befund am Eltern gilt
                # damit als erledigt (sonst hinge der Eltern-Auftrag für immer an einem
                # Schritt, den nichts mehr weiterbringen kann).
                if (order.reason or "") == "deviation":
                    from .inspection import resolve_failed_by
                    resolve_failed_by(db, parent, order)
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
    remaining = order_shortfalls(db, parent).get(order.article_id, ZERO)
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
                *in_stock_clauses())
        .order_by(Instance.object_id)
        .all()
    )
    pegged = ZERO
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
        pegged += take
    # FIX: Das Event nur ausgeben, wenn tatsächlich etwas gepinnt wurde – sonst meldete der
    # Event-Strom «supply.pegged» auch bei 0 verfügbaren Stück (irreführende Wahrheit).
    if pegged:
        emit(db, "supply.pegged", object_type="order", object_id=parent.object_id,
             payload={"supply": order.object_id, "article_id": order.article_id,
                      "quantity": pegged})


def required_sample(quantity, sample_percent: int | None) -> int:
    """Zu prüfende Stück-/Probenzahl der Datenerfassung (ganze Zahl, mind. 1 bei Menge > 0).

    Bruchmengen-fähig: eine Charge von 2.5 kg ergibt bei 100 % ``ceil(2.5)`` = 3 Proben;
    nie mehr als (aufgerundet) die Menge (Einzelteil: nicht mehr Proben als Instanzen)."""
    qty = to_qty(quantity)
    pct = sample_percent if sample_percent is not None else 100
    if qty <= 0 or pct <= 0:
        return 0
    n = ceil(qty * Decimal(pct) / Decimal(100))
    return int(min(ceil(qty), max(1, n)))
