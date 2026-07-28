"""Bereitstellung – «Bewegung wird ABGELEITET, nicht geplant».

**Das Problem, das dieses Modul löst.** Beim Modellieren eines Prozesses weiss niemand,
ob eine Bewegung nötig sein wird: ob die Schraube schon am Band liegt oder in Halle B,
entscheidet sich erst zur **Laufzeit**. Jedes vorgeplante Bewegungs-Modul rät deshalb –
mal ist es überflüssig (das Teil liegt längst richtig), mal fehlt es (das Teil liegt
woanders, aber niemand hat den Schritt eingeplant). Genau darum sind die früheren
Zwangs-Bewegungen rund um Beschaffung und Verkauf gescheitert.

**Der Grundsatz:** *Geplant wird, was der Nutzer will. Angelegt wird, was die Physik
verlangt.* Der Nutzer modelliert nur die fachlichen Schritte (kaufen, verbauen,
verkaufen). Jeden physischen Transport, der daraus zwingend folgt, leitet dieses Modul
zur Laufzeit ab.

**Die vier Regeln:**

1. Jeder Schritttyp deklariert in ``domain/event_types.py``, **wo sein Material sein muss**
   (``provisioning``) – Beschaffung → im Betrieb, Verkauf → beim Kunden, Ressource → an
   der Produkt-Instanz.
2. Ist ein Schritt an der Reihe (oder gerade erledigt), wird **Ist ↔ Soll** verglichen.
3. Stimmt es → **nichts passiert** (der häufigste Fall, komplett unsichtbar).
4. Stimmt es nicht → ein **Bereitstellungs-Unter-Auftrag** (``reason='provisioning'``)
   holt genau diese Instanzen an ihren Soll-Ort.

**Warum ein Unter-Auftrag und kein Schritt im Auftrag selbst.** Ein Bewegungs-Schritt
bewegt immer die Instanzen **seines** Auftrags (``movement.movable_instances``). Die
Komponente, die aus Halle B geholt werden muss, gehört aber nicht zum Subjekt des
Auftrags – sie ist eine Ressourcen-Zeile. Der Schritt könnte sie gar nicht greifen. Ein
Unter-Auftrag kann es, weil er ein **eigenes fixiertes Subjekt** trägt
(``Instance.subject_of_order_id``) – exakt wie Abweichung und Retoure.

Damit ist die Systematik der Unter-Aufträge symmetrisch:

===================  ======================  =========================
Lage                 Unter-Auftrag           blockiert
===================  ======================  =========================
nichts da            ``supply``              den Schritt
**falscher Ort**     **``provisioning``**    **den Schritt**
kaputt               ``deviation``           den ganzen Auftrag
===================  ======================  =========================

**Abstufung nach Distanz** (dieselbe Mechanik, andere Konsequenz): Eine Bewegung
**innerhalb derselben Adresse** ist trivial – der Unter-Auftrag bucht sich sofort selbst
ab und ist nur noch Protokoll. Eine Bewegung **über Adressgrenzen** ist echte Logistik
(Paket/Fracht) – der Unter-Auftrag bleibt offen und wartet auf Tarifwahl, Label und
Quittierung. Zwanzig Meter durch die Halle brauchen kein Formular, ein LKW braucht ein
Label.

**Ehrlichkeit über die automatische Buchung:** Eine systemseitig gebuchte Bewegung ist
eine *Behauptung*, keine Beobachtung – niemand hat gescannt. Das Audit-Log hält sie
darum ausdrücklich als ``systemseitig zugewiesen, nicht quittiert`` fest.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import ArticleProcessStep, Instance, Order
from ..models.base import utcnow
from . import location_split
from .admin import log_audit
from .events import emit
from .objects import next_object_id

REASON = "provisioning"

# Schritttypen, deren Material VOR der Ausführung am Soll-Ort sein muss. Alle übrigen
# (Beschaffung, Verkauf) stellen ihr Ergebnis DANACH bereit – die Ware kommt an bzw.
# geht hinaus, nachdem der kaufmännische Vorgang abgeschlossen ist.
_STAGE_BEFORE = ("resource",)


def is_companion(step) -> bool:
    """Alt-Bestand: eine früher automatisch **gesäte** Begleit-Bewegung (Wareneingang /
    Versand zum Kunden, Spalte ``companion``).

    Das System legt seit Juli 2026 **keine** Prozessschritte mehr an – physisch nötige
    Transporte entstehen zur Laufzeit als Bereitstellungs-Unter-Auftrag. Bestehende
    Begleiter bleiben aber gültige Schritte und behalten ihre Fachwirkung: festes Ziel
    «Kunde des Verkaufs» und **Ausnahme von der Fehlmengen-Prüfung** (ohne sie wäre der
    Versand blockiert, sobald der Verkauf bezahlt ist – die Ware gilt dann als verkauft,
    aus Sicht des freien Bestands weg)."""
    return bool(getattr(step, "companion", False))


def reconcile_to(inst: Instance, to_type: str, to_id: int) -> bool:
    """Die GANZE Instanz an (``to_type``, ``to_id``) bringen. **No-op**, wenn sie
    (ausschliesslich) schon dort liegt. Gibt zurück, ob tatsächlich bewegt wurde.

    Das ist der eine «Ist ↔ Soll»-Abgleich auf Instanz-Ebene: eine verteilte Charge wird
    dabei am Ziel wieder zusammengeführt (``location_split.set_single``). Teilmengen-
    Bewegungen laufen bewusst NICHT hierüber, sondern auftragsgetrieben über den
    Bewegungs-Schritt."""
    to_id = int(to_id)
    if (inst.location_type, inst.location_id) == (to_type, to_id) and not inst.locations:
        return False   # schon am Ziel → no-op
    location_split.set_single(inst, to_type, to_id)
    return True


# ─── 1) Soll-Ort: die Deklaration in eine konkrete Adresse auflösen ──────────────

def target_for(db: Session, order: Order, step: ArticleProcessStep) -> tuple[str | None, int | None]:
    """Wohin muss das Material dieses Schritts physisch? ``(None, None)`` = kein fester Ort.

    Löst die **deklarierte** Absicht (``event_types.provisioning``) in eine konkrete
    Objektnummer auf. Das ist die EINE Stelle, die das tut – wer einen neuen Schritttyp
    baut, deklariert seinen Bereitstellungsort und ist fertig."""
    kind = event_types.provisioning(step.step_type)

    if kind == event_types.PROV_RECEIVING:
        from .locations import company_location
        return company_location(db)

    if kind == event_types.PROV_CUSTOMER:
        from .sale import customer_for_order
        cust = customer_for_order(db, order)
        return ("user", cust.object_id) if cust and cust.object_id else (None, None)

    if kind == event_types.PROV_PRODUCT:
        # Arbeitsort = physischer Standort der Produkt-Instanzen dieses Auftrags. Stehen
        # sie (noch) nirgends, gibt es keinen Soll-Ort – dann wird nichts bereitgestellt.
        from .locations import resolve_physical_location
        from .subject import order_active_instances
        for prod in order_active_instances(db, order):
            pt, pid = resolve_physical_location(db, prod.location_type, prod.location_id)
            if pt and pid:
                return pt, pid
        return (None, None)

    # PROV_NONE (Datenerfassung/Bewegung/Dokument) und PROV_NOWHERE (Verschrotten):
    # kein Bereitstellungsort. Verschrottetes verliert seinen Halter (services/scrap.py).
    return (None, None)


# ─── 2) Subjekte: welche Instanzen dieser Schritt an seinem Soll-Ort braucht ──────

def subjects_for(db: Session, order: Order, step: ArticleProcessStep) -> list[Instance]:
    """Die Instanzen, die für diesen Schritt am Soll-Ort liegen müssen.

    * **Ressource** (Verbrauch): die Komponenten, die der Schritt verbrauchen wird –
      dieselbe FIFO-Vorschau, die auch das Panel zeigt. **Betriebsmittel** (``mode='tool'``)
      bleiben bewusst aussen vor: welches Werkzeug genommen wird, wählt der Mensch erst
      beim Ausführen; ``resource._use_tool`` bringt es dann an den Arbeitsplatz.
    * **Verkauf**: NUR die tatsächlich verkauften (``sold``) Instanzen. Eine teilverkaufte
      Charge bleibt ``in_stock`` (der Verkauf hat nur die Menge abgebucht) und wird darum
      **nicht** automatisch bewegt – sonst wanderte der unverkaufte Rest mit zum Kunden und
      stünde danach als freier Bestand bei ihm. Solche Teilmengen bewegt der Mensch über
      einen Bewegungs-Schritt, der die Menge kennt (``location_split.move``).
    * **sonst** (Beschaffung/…): die Instanzen des Auftrags selbst."""
    from .subject import order_active_instances, order_instances
    if step.step_type == "resource":
        return _component_candidates(db, order, step)
    if event_types.provisioning(step.step_type) == event_types.PROV_CUSTOMER:
        # ACHTUNG: ``sold`` ist eine **terminale** Disposition – ``order_active_instances``
        # blendet sie aus. Für den Kundenversand ist aber genau sie die gesuchte Menge, also
        # hier über die volle Liste gehen. (Mit der aktiven Liste löste der Versand NIE aus.)
        return [i for i in order_instances(db, order) if (i.disposition or "") == "sold"]
    return order_active_instances(db, order)


def _component_candidates(db: Session, order: Order, step: ArticleProcessStep) -> list[Instance]:
    """FIFO-Vorschau der zu verbrauchenden Komponenten (ohne Lock – reine Anzeige/Planung).

    Genau so viele Kandidaten, wie der Bedarf verlangt: eine Charge deckt oft alles, dann
    ist es EINE Instanz. Reicht der Bestand nicht, greift ohnehin der Nachschub
    (``supply.ensure_supply``) – Menge ist nicht die Zuständigkeit dieses Moduls."""
    from .inventory import fifo_candidates
    from .order_lines import effective_quantity
    from .quantity import to_qty

    qty = to_qty(effective_quantity(db, order))
    out: list[Instance] = []
    for line in (step.resource_lines or []):
        if (line.get("mode") or "consume") != "consume":
            continue          # Betriebsmittel: Auswahl erst beim Ausführen
        need = to_qty(line.get("quantity", 1)) * qty
        for cand in fifo_candidates(db, line["article_id"], order.id):
            if need <= Decimal(0):
                break
            out.append(cand)
            need -= to_qty(cand.quantity)
    return out


# ─── 3) Ist ↔ Soll ───────────────────────────────────────────────────────────────

def misplaced(db: Session, order: Order, step: ArticleProcessStep) -> tuple[list[Instance], str | None, int | None]:
    """Welche Instanzen dieses Schritts liegen NICHT an ihrem Soll-Ort?

    Verglichen wird der **physische** Standort (eine in einem Behälter liegende Instanz
    ist dort, wo der Behälter steht) – sonst gälte jede korrekt eingeräumte Instanz als
    fehlplatziert."""
    t_type, t_id = target_for(db, order, step)
    if not t_type or not t_id:
        return [], None, None

    from .locations import resolve_physical_location
    out = []
    for inst in subjects_for(db, order, step):
        if (inst.disposition or "") in ("scrapped", "consumed"):
            continue          # raus aus dem Bestand – kein Bereitstellungsfall mehr
        pt, pid = resolve_physical_location(db, inst.location_type, inst.location_id)
        if (pt, pid) != (t_type, int(t_id)):
            out.append(inst)
    return out, t_type, int(t_id)


# ─── 4) Der Bereitstellungs-Unter-Auftrag ────────────────────────────────────────

def open_provisioning(db: Session, parent: Order, step_id: int | None = None) -> list[Order]:
    """Offene Bereitstellungen eines Auftrags (optional für genau einen Schritt)."""
    if not parent.object_id:
        return []
    q = db.query(Order).filter(
        Order.parent_order_id == parent.object_id, Order.reason == REASON,
        Order.is_active == True, Order.status.in_(("draft", "released")))
    rows = q.order_by(Order.object_id).all()
    if step_id is None:
        return rows
    return [o for o in rows if o.origin_step_id == step_id]


def sub_orders_for_step(db: Session, parent: Order, step_id: int) -> list[Order]:
    """ALLE (noch gültigen) Bereitstellungen eines Schritts – offen wie erledigt.

    ``open_provisioning`` beantwortet «hält gerade etwas auf?»; das hier beantwortet «was ist
    an dieser Stelle im Ablauf passiert?». Abgebrochene bleiben aussen vor: sie sind die
    ausdrückliche Aussage «das mache ich von Hand» und sollen den Ablauf nicht mehr belasten."""
    if not parent.object_id:
        return []
    return (
        db.query(Order)
        .filter(Order.parent_order_id == parent.object_id, Order.reason == REASON,
                Order.origin_step_id == step_id, Order.is_active == True,
                Order.status.in_(("draft", "released", "completed")))
        .order_by(Order.object_id)
        .all()
    )


def cancelled_for_step(db: Session, parent: Order, step_id: int) -> bool:
    """Wurde die Bereitstellung dieses Schritts **von Hand abgebrochen**?

    Eine Bereitstellung entsteht automatisch – also muss der Mensch sie auch wieder
    loswerden können, sonst ist ein Auftrag, dessen Bereitstellung nicht durchläuft, tot
    (sie blockiert den Schritt UND den Abschluss). Der Abbruch ist die ausdrückliche
    Aussage «das mache ich von Hand» bzw. «das liegt längst richtig».

    Damit das hält, darf die nächste Auswertung sie nicht sofort neu anlegen. Der Marker
    dafür ist der **abgebrochene Unter-Auftrag selbst** (Status ``inactive`` zu genau diesem
    Schritt) – kein zusätzliches Feld, keine zweite Wahrheit, und im Audit steht, wer die
    Bereitstellung wann übersprungen hat."""
    if not parent.object_id:
        return False
    return db.query(Order.id).filter(
        Order.parent_order_id == parent.object_id, Order.reason == REASON,
        Order.origin_step_id == step_id, Order.status == "inactive",
    ).first() is not None


def ensure_provisioning(db: Session, order: Order, actor_id: int | None) -> list[Order]:
    """Für jeden Schritt, der dran ist oder gerade war, die nötige Bereitstellung anlegen.

    Idempotent (ein offener Bereitstellungs-Auftrag je Schritt) und **nicht rekursiv**:
    ein Bereitstellungs-Auftrag stellt selbst nichts bereit – er IST die Bereitstellung.
    Committet NICHT (der Aufrufer schliesst ab)."""
    if order.reason == REASON or order.status != "released":
        return []

    from .process import build_order_steps

    # Nebenläufigkeits-Schutz: ohne Sperre ist der Idempotenz-Check unten ein
    # Check-then-Act – zwei gleichzeitige Auslöser (Schritt-Abschluss + Webhook) legen
    # sonst zwei Bereitstellungen für denselben Schritt an.
    db.query(Order).filter(Order.id == order.id).with_for_update().first()

    created: list[Order] = []
    for info in build_order_steps(db, order):
        step, state = info["step"], info["state"]
        # **Der Zeitpunkt entscheidet, und er ist je Schritttyp verschieden:**
        #   • Ressource stellt VOR der Ausführung bereit (die Komponente muss da sein,
        #     bevor verbaut wird) → relevant, solange der Schritt offen ist;
        #   • Beschaffung/Verkauf stellen DANACH bereit (die Ware kommt an bzw. geht
        #     hinaus, nachdem der kaufmännische Vorgang durch ist) → erst bei ``done``.
        # Ohne diese Trennung würde eine erst BESTELLTE Ware (Schritt aktiv, noch beim
        # Lieferanten) sofort in den Betrieb gebucht – sie wäre buchhalterisch da, bevor
        # sie geliefert ist.
        before = step.step_type in _STAGE_BEFORE
        if before and state not in ("active", "blocked"):
            continue
        if not before and state != "done":
            continue
        if open_provisioning(db, order, step.id):
            continue          # läuft bereits
        if cancelled_for_step(db, order, step.id):
            continue          # bewusst übersprungen – nicht gegen den Menschen neu anlegen
        insts, t_type, t_id = misplaced(db, order, step)
        if not insts:
            continue
        created.append(_create(db, order, step, insts, t_type, t_id, actor_id))
    return created


def _create(db: Session, parent: Order, step: ArticleProcessStep, insts: list[Instance],
            t_type: str, t_id: int, actor_id: int | None) -> Order:
    """Bereitstellungs-Unter-Auftrag anlegen: Subjekt = genau diese Instanzen, Inhalt =
    EIN Bewegungs-Schritt mit dem Soll-Ort als Ziel."""
    from .subject import record_link

    sub = Order(
        object_id=next_object_id(db, "order"), status="released",
        article_id=parent.article_id, quantity=len(insts),
        parent_order_id=parent.object_id, reason=REASON,
        origin_step_id=step.id,
        title=f"Bereitstellung für {event_types.label(step.step_type)} · Auftrag {parent.object_id}",
    )
    # Direkt freigegeben statt über ``orders.release_order``: es gibt nichts zu entscheiden
    # und nichts zu materialisieren – das Subjekt steht fest, Instanzen werden weder erzeugt
    # noch reserviert. Ein Entwurf, den jemand freigeben müsste, wäre genau die manuelle
    # Interaktion, die dieser Mechanismus vermeidet.
    sub.released_at = utcnow()
    db.add(sub)
    db.flush()

    # **Nur die Historien-Verknüpfung, NICHT ``subject_of_order_id``.** Die Instanz gehört
    # weiterhin dem Eltern-Auftrag – eine Bereitstellung transportiert sie bloss. Würde die
    # Bindung umgehängt, verlöre der Eltern sein Subjekt (anders als bei Abweichung/Retoure,
    # wo der Übergang gewollt ist). ``order_instances`` löst den Unter-Auftrag über die
    # Links auf, das genügt für Bewegung und Anzeige.
    for inst in insts:
        record_link(db, inst.object_id, sub.id)

    mv = ArticleProcessStep(order_id=sub.id, step_type="movement", position=1,
                            target_location_type=t_type, target_location_id=t_id)
    db.add(mv)
    db.flush()

    log_audit(db, "orders", None,
              f"Bereitstellung zu {parent.object_id} angelegt ({len(insts)} Instanz(en) → {t_type}:{t_id})",
              actor_id, object_id=sub.object_id)
    emit(db, "order.provisioning_opened", object_type="order", object_id=sub.object_id,
         payload={"parent": parent.object_id, "step_id": step.id, "target": f"{t_type}:{t_id}",
                  "instances": [i.object_id for i in insts]}, actor_id=actor_id)

    if _is_internal(db, sub, mv, insts):
        _settle(db, sub, mv, insts, t_type, t_id, actor_id)
    return sub


def _is_internal(db: Session, sub: Order, mv: ArticleProcessStep, insts: list[Instance]) -> bool:
    """Innerbetrieblich = keine Adressgrenze überschritten. Dann ist die Bewegung trivial
    («zwanzig Meter durch die Halle») und wird sofort gebucht; sonst ist es echte Logistik
    (Paket/Fracht) und ein Mensch quittiert.

    Genutzt wird die bestehende, adress-basierte Klassifikation (ADR 005) – dieselbe, die
    auch Paket/Fracht empfiehlt. Kein zweites Regelwerk."""
    from . import logistics
    try:
        return logistics.classify_movement(db, sub, mv, insts).get("transport_class") != "outside"
    except Exception:
        return False      # im Zweifel den Menschen fragen, nicht still buchen


def _settle(db: Session, sub: Order, mv: ArticleProcessStep, insts: list[Instance],
            t_type: str, t_id: int, actor_id: int | None) -> None:
    """Innerbetriebliche Bereitstellung sofort vollziehen und abschliessen.

    Bewusst **ohne** ``movement.record_movement``: das dortige Quittieren ist der Beleg
    einer *beobachteten* Übergabe (Scan, Versandbeleg, Tracking). Hier bucht das System –
    das Audit-Log sagt das ausdrücklich, damit «bezeugt» und «behauptet» unterscheidbar
    bleiben."""
    from ..models import Movement

    for inst in insts:
        old = f"{inst.location_type}:{inst.location_id}"
        if reconcile_to(inst, t_type, t_id):
            log_audit(db, "instances", "location", f"{t_type}:{t_id}", actor_id,
                      object_id=inst.object_id,
                      old_value=f"{old} (systemseitig zugewiesen, nicht quittiert)")

    db.add(Movement(order_id=sub.id, step_id=mv.id, moved_by_id=actor_id,
                    note="Systemseitig bereitgestellt (innerbetrieblich, nicht quittiert)"))
    sub.status = "completed"
    sub.completed_at = utcnow()
    db.flush()
    emit(db, "order.completed", object_type="order", object_id=sub.object_id, actor_id=actor_id)
