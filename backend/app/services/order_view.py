"""►►► **Wie ein Auftrag gezeigt wird – die Ansicht hinter den Routen** (``routers/orders``). ◄◄◄

Die Module mit Zustand und Beleg (``steps_view``), wer was sieht (``involved`` ·
``visible_steps``), die Antwort (``response``), Nachbarn und Abweichungen (``related``), Feed und
Ereignisse, die Auswahl für den Entwurf (``fifo``, ``unit_option_rows``, ``preview_parents``).
Gelesen, nie geschrieben – ausser den Positionen des eigenen Belegs beim Anzeigen
(``voucher.sync_lines``, bewusst; ``keep``).
"""

from typing import Optional, Sequence
from sqlalchemy.orm import Session
from ..domain import modules, statuses as st
from ..models import (
    Article, InstanceUnit, Order, OrderUnit, UserProfile,
)
from ..schemas.voucher import (
    VoucherEmbed,
)
from ..schemas.place import PlaceRef
from ..schemas.order import (
    FlowGraph, JourneyNeighbour, LoopView, OrderLineResponse,
    OrderResponse, DRAFT_OBJECT_ID, NeedSource, ProcessEventResponse, ProcessStepResponse,
    RelatedOrder, StepNeed, StepWork, UnitOption,
)
from ..services import consumption as consumption_svc
from ..services import voucher as voucher_svc
from ..services import voucher_view
from ..services import flow as flow_svc
from ..services import places as places_svc
from ..services import journey as journey_svc
from ..services import loop as loop_svc
from ..services import order_state
from ..services import people
from ..services.instances import find_units, unit_number, unit_numbers
from ..domain.errors import NotFound


#: Wie viele Log-Einträge das Detail mitliefert; die Gesamtzahl steht daneben (``event_count``).
EVENT_LIMIT = 200


#: Wie viele Abweichungen die Spalte **vollständig** zeigt (je ihr echter Ablauf, nie
#: gruppiert); die wahre Zahl steht daneben (``deviation_total``).
RELATED_LIMIT = 3


def place_ref(db: Session, object_id) -> Optional[PlaceRef]:
    """Eine Objektnummer → ihr Halter. ``None`` bleibt ``None``."""
    return PlaceRef.of(places_svc.station_of(db, int(object_id))) if object_id else None


def steps_view(db: Session, order: Order, *, viewer: Optional[UserProfile] = None,
           only: Optional[set[int]] = None, drawn: bool = False) -> list[ProcessStepResponse]:
    """Die Module eines Auftrags – **mit ihrer Sperre**.

    Ob ein Modul laufen darf, entscheidet nicht das Modul: es steht hier als Auskunft am
    Schritt (``waiting_for``), und durchgesetzt wird es serverseitig in
    ``process.confirm_step``. Ein neuer Modultyp erbt beides, ohne etwas dafür zu tun.
    ``only`` beschränkt auf die Module, die ein Betrachter sehen darf. ``drawn``: nur, was
    das Bild eines **Nachbarn** liest (Modul, Farbe, Sperre) – er wird blass gezeichnet, ohne
    Arbeit, Bedarf oder Beleg; die volle Antwort holt sein eigener Datensatz.
    """
    pending = order_state.pending_returns(db, order)
    out: list[ProcessStepResponse] = []
    for s in order_state.steps_of(db, order):
        if only is not None and s.id not in only:
            continue
        row = ProcessStepResponse.model_validate(s)
        row.waiting_for = pending.get(s.id, [])
        if drawn:
            out.append(row)
            continue
        # **Die Arbeitsliste** – je wartender Instanz eine Zeile (Scan-Regel §3).
        row.work = [StepWork(**w) for w in order_state.step_work(db, order, s)]
        # **Was das Modul verbraucht** – gerechnet beim Erreichen gegen das, was davorsteht
        # (``services/consumption``).
        needs = consumption_svc.needs(db, s, products=order_state.units_before(db, order, s))
        # Alle Orte auf einmal benennen – nicht je Bedarf und je Kiste.
        named = places_svc.describe_all(
            db, [n.place for n in needs] + [src.place for n in needs for src in n.sources])
        row.needs = [
            StepNeed(
                article_object_id=n.article_object_id, article_name=n.article_name,
                per_unit=n.per_unit, required=n.required, available=n.available,
                here=n.here, place=PlaceRef.of(named.get(n.place) if n.place else None),
                sources=[NeedSource(
                    instance_object_id=src.instance_object_id, free=src.free,
                    here=src.here,
                    place=PlaceRef.of(named.get(src.place) if src.place else None))
                    for src in n.sources],
                missing=n.missing, misplaced=n.misplaced, plan=n.plan(),
            )
            for n in needs
        ]
        # **Wohin es geht** – aufgelöst zum Namen des Halters.
        row.target = place_ref(db, (s.config or {}).get("target"))
        # **Der Beleg** (nur Modul «Zahlung»). Eine Gegenpartei sieht nur ihre eigene
        # Angebotszeile und keine Zahl über Forderung und Geld – gefiltert hier.
        paper = voucher_view.embed_data(db, order=order, step=s, viewer=viewer)
        row.voucher = VoucherEmbed(**paper) if paper else None
        # **Warum es jetzt nicht abzuschliessen ist** – die Regel von ``confirm_step`` als
        # Auskunft.
        row.blocked = modules.get(s.module_type).passes_itself
        out.append(row)
    keep(db)
    return out


def keep(db: Session) -> None:
    """**Was eine Ansicht schreibt, bleibt** – gespeichert am Ende der Anfrage (``get_db``).

    Der Beleg zieht seine Positionen beim Anzeigen aus dem Prozess nach
    (``voucher.sync_lines``) – der einzige Schreibvorgang auf einem Lesepfad, und er ist
    Absicht: die Positionen brauchen eine Id, damit man sie bepreisen kann. ``flush`` gibt sie
    ihr, ohne die geladenen Objekte zu verwerfen.
    """
    db.flush()


def involved(db: Session, viewer: UserProfile) -> Optional[set[tuple[int, int]]]:
    """►►► **Woran ist dieser Betrachter beteiligt?** – (Auftrag, Modul) je Zeile. ◄◄◄

    Ein Modul hat Aussenwirkung: der **Geldvorgang**. Beteiligt ist, wer in einem
    vorkommt; ``None`` heisst «Personal, sieht alles».

    Sie steht **hier** und wird von Feed **und** Detail gelesen. Vorher fragte der Feed
    eine andere Quelle als das Detail: die Gegenpartei eines Geldvorgangs hatte
    ERP-Zugang, sah ihren Auftrag aber in **keiner Liste** – erreichbar nur über die
    direkte Adresse. Zwei Ableitungen derselben Frage laufen genau so auseinander.
    """
    papers = voucher_svc.mine(db, viewer)
    if papers is None:
        # **Personal sieht alles** – das Modul antwortet darauf mit ``None``.
        return None
    return {(r.order_id, r.step_id) for r in papers}


def visible_steps(db: Session, order: Order, viewer: UserProfile) -> Optional[set[int]]:
    """Die Module dieses Auftrags, die der Betrachter sehen darf. ``None`` = alle.

    Ist er an diesem Auftrag gar nicht beteiligt, gibt es ihn für ihn nicht – **404**,
    nicht 403: ein «du darfst nicht» bestätigt, dass es ihn gibt.
    """
    rows = involved(db, viewer)
    if rows is None:
        return None
    steps = {step_id for order_id, step_id in rows if order_id == order.id}
    if not steps:
        raise NotFound(f"Auftrag {order.object_id} nicht gefunden.")
    return steps


def response(db: Session, order: Order, *,
                 viewer: Optional[UserProfile] = None) -> OrderResponse:
    """Der Auftrag als Antwort – **und für eine Gegenpartei derselbe, nur ihr Teil**.

    Die Verengung steht hier und nicht an den Aufrufstellen: wer sie dort formulierte,
    hätte sie beim zweiten Endpunkt nicht. ``viewer=None`` heisst «interner Aufruf»
    (Personal-only-Endpunkte) und ändert nichts.

    **Eine Gegenpartei sieht ihren Beleg**, nicht die Reise des Materials: nur ihre
    Module, kein Prozess-Graph, keine Historie, keine Nachbar-Aufträge, keine Positionen.
    Darum wird zuerst gefragt, wer schaut – und der interne Teil (``internal_view``) nur für
    das Personal gerechnet, nicht gerechnet und dann weggeworfen.
    """
    mine = visible_steps(db, order, viewer) if viewer is not None else None
    active = order_state.active_step_id(db, order)
    resp = OrderResponse(
        id=order.id,
        object_id=order.object_id,
        name=order.name,
        status=order_state.order_status(db, order),
        created_at=order.created_at,
        updated_at=order.updated_at,
        date_kind=order.date_kind,
        date_on=order.date_on,
        steps=steps_view(db, order, viewer=viewer, only=mine),
        active_step_id=active if mine is None or active in mine else None,
        is_deviation=order_state.deviation_flags(db, [order.id]).get(order.id, False),
    )
    return resp if mine is not None else resp.model_copy(update=internal_view(db, order))


def internal_view(db: Session, order: Order) -> dict:
    """**Was nur das Personal sieht** – der interne Lauf des Auftrags."""
    lines = order_state.lines_of(db, order)
    articles = {
        a.id: a
        for a in db.query(Article).filter(Article.id.in_([ln.article_id for ln in lines])).all()
    } if lines else {}
    events, event_count = order_state.events_page(db, order, limit=EVENT_LIMIT)
    numbers = event_numbers(db, events)
    actors = people.names(db, {e.actor_id for e in events if e.actor_id})
    came_from, went_to = journey_svc.neighbours(db, order)
    # **Ein Graph, ein Bild.** Spalten und Linien kommen aus derselben Kantenliste.
    graph = flow_svc.build(db, order)
    branches = graph.neighbours
    return {
        "lines": [
            OrderLineResponse(
                id=ln.id, position=ln.position, quantity=ln.quantity, origin=ln.origin,
                article_object_id=(articles[ln.article_id].object_id
                                   if ln.article_id in articles else None),
                article_name=articles[ln.article_id].name if ln.article_id in articles else None,
            )
            for ln in lines
        ],
        "flow": FlowGraph(**flow_svc.as_dict(graph)),
        "events": [
            ProcessEventResponse(
                id=e.id, kind=e.kind, step_id=e.step_id,
                unit_number=numbers.get(e.instance_unit_id, str(e.instance_unit_id)),
                status_before=e.status_before, status_after=e.status_after,
                actor=actors.get(e.actor_id), created_at=e.created_at,
            )
            for e in events
        ],
        "event_count": event_count,
        "journey_in": [JourneyNeighbour(**n) for n in came_from],
        "journey_out": [JourneyNeighbour(**n) for n in went_to],
        "parents": related(db, order, journey_svc.parents(db, order)[:RELATED_LIMIT],
                            incoming=True),
        "deviations": related(db, order, branches[:RELATED_LIMIT], incoming=False),
        "deviation_total": len(branches),
        # **Die Schlaufe** – abgeleitet aus dem Log (``services/loop``).
        "loop": loop_view(db, order),
    }


def loop_view(db: Session, order: Order) -> Optional[LoopView]:
    found = loop_svc.view(db, order)
    return LoopView(**found) if found is not None else None


def related(db: Session, order: Order, counts: Sequence[flow_svc.Neighbour],
            *, incoming: bool) -> list[RelatedOrder]:
    """Nachbar-Aufträge mit **ihrem eigenen Ablauf** – dieselbe Form wie die Mitte.

    Sie werden daneben mit derselben Komponente gezeichnet, aber blass und ohne Inhalt der
    Module: geliefert wird, was das Bild liest (``steps_view(drawn=True)``, Graph, Zustand). Die
    volle Antwort – Arbeitsliste, Bedarf, Beleg – kostete je Nachbar so viel wie ein ganzer
    Auftrag und zog dabei dessen Belegpositionen nach (gemessen, ``test_order_view_queries``).

    Die Liste kommt für Abweichungen aus dem **Graph** (dort steht die Abzweigung) und
    für übergeordnete Aufträge aus dem **Log** (dort steht die Übernahme) – beide nennen
    einen Auftrag gleich: mit seiner Objektnummer (``flow.Neighbour``).
    """
    if not counts:
        return []
    rows = {int(o.object_id): o for o in db.query(Order).filter(
        Order.object_id.in_([n.object_id for n in counts])).all()}
    ids = [o.id for o in rows.values()]
    states = order_state.order_statuses(db, ids)
    # Wer gibt zurück: bei Abweichungen die Verbindung des Nachbarn zu mir, bei einem
    # übergeordneten Auftrag meine eigene zu ihm.
    if incoming:
        mine = {m.return_to_order_id for m in db.query(OrderUnit).filter(
            OrderUnit.order_id == order.id, OrderUnit.return_to_order_id.isnot(None)).all()}
        returning = {oid for oid in ids if oid in mine}
    else:
        returning = journey_svc.returning_to(db, order, ids)

    out: list[RelatedOrder] = []
    for rel in counts:
        row = rows.get(rel.object_id)
        if row is None:
            continue
        out.append(RelatedOrder(
            object_id=row.object_id,
            name=row.name,
            status=states.get(row.id, st.IM_PROZESS),
            steps=steps_view(db, row, drawn=True),
            flow=FlowGraph(**flow_svc.as_dict(flow_svc.build(db, row))),
            active_step_id=order_state.active_step_id(db, row),
            unit_count=rel.unit_count,
            returns=row.id in returning,
        ))
    return out


def event_numbers(db: Session, events) -> dict[int, str]:
    """Nummern nur für die Stücke, die in den gezeigten Einträgen vorkommen."""
    ids = {e.instance_unit_id for e in events}
    if not ids:
        return {}
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(ids)).all()
    return unit_numbers(db, units)


def unit_option_rows(db: Session, rows: Sequence[tuple]) -> list[UnitOption]:
    """Die geladenen Stücke als Antwort. Wo ein Stück läuft, sagt ``order_state.holders`` –
    gefragt nur für die Stücke dieser Seite."""
    running = order_state.holders(db, [u.id for u, _i, _a in rows])
    return [
        UnitOption(
            number=unit_number(instance, unit),
            status=unit.status,
            article_object_id=art.object_id if art else None,
            article_name=art.name if art else None,
            # Dieselbe Frage wie in der Freigabe (``statuses.is_selectable``): nicht nehmen
            # lässt sich nur, was es physisch nicht mehr gibt.
            available=st.is_selectable(unit.status),
            # Und die Frage von FIFO: liegt es im Regal? Verbaut heisst nein.
            in_stock=st.stock_kind(unit.status) == st.LIVE,
            in_order=running.get(unit.id),
        )
        for unit, instance, art in rows
    ]


def preview_parents(db: Session, draft: dict) -> list[RelatedOrder]:
    """Die Quell-Aufträge des Entwurfs – **mit der Abzweigung, die entstehen würde**.

    Woher ein Stück kommt, sagt die Auswahl selbst (``UnitPick.from_order``): sie ist die
    **Absicht** des Menschen und wird bei der Freigabe gegen die Wirklichkeit geprüft.
    Genau diese Absicht wird hier gezeichnet – nicht der heutige Aufenthaltsort, sonst
    zeigte die Vorschau etwas anderes, als die Freigabe täte.

    Der Zustandspunkt steht an der Zeile des Quell-Auftrags (``current_step_id``); dort
    entsteht der Abzweigepunkt, und dorthin kehrt das Stück zurück (§12.4).
    """
    want: dict[int, bool] = {}          # Objektnummer des Quell-Auftrags → kehrt zurück?
    picked: list[str] = []
    for ln in draft.get("lines") or []:
        for u in ln.get("units") or []:
            src = u.get("from_order")
            if src is None:
                continue
            want[int(src)] = want.get(int(src), False) or bool(ln.get("returns", True))
            picked.append(str(u.get("number") or "").strip())
    if not want:
        return []

    rows = db.query(Order).filter(Order.object_id.in_(list(want))).all()
    if not rows:
        return []
    # Die offene Zeile des Quell-Auftrags sagt, an welchem Punkt die Stücke hängen; die
    # Nummer löst `instances.find_units` auf.
    chosen = {u.id for u in find_units(db, picked).values()}
    holds = {
        (m.order_id, m.instance_unit_id): m.current_step_id
        for m in db.query(OrderUnit).filter(
            OrderUnit.order_id.in_([o.id for o in rows]),
            OrderUnit.released_at.is_(None),
        ).all()
    }

    out: list[RelatedOrder] = []
    for row in rows:
        points = {step for (oid, uid), step in holds.items()
                  if oid == row.id and uid in chosen}
        plan = [
            flow_svc.Planned(at=at, target=DRAFT_OBJECT_ID, returns=want[row.object_id])
            for at in sorted(points, key=lambda x: (x is None, x))
        ]
        taken = sum(1 for (oid, uid), _ in holds.items()
                    if oid == row.id and uid in chosen)
        out.append(RelatedOrder(
            object_id=row.object_id,
            name=row.name,
            status=order_state.order_status(db, row),
            steps=steps_view(db, row, drawn=True),
            flow=FlowGraph(**flow_svc.as_dict(flow_svc.build(db, row, planned=plan))),
            active_step_id=order_state.active_step_id(db, row),
            unit_count=taken,
            returns=want[row.object_id],
        ))
    return out
