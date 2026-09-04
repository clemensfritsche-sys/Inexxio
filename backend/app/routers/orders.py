"""Auftrag – Feed, Freigabe, Detail, Schritt bestätigen.

Es gibt **keinen** Entwurfs-Endpunkt: ein Auftragsentwurf lebt im Browser, bis er
freigebbar ist. Erst ``POST`` legt ihn an – und dieser eine Aufruf ist zugleich die
Freigabe. ``/validate`` sagt der Oberfläche vorher, ob es reichen würde, ohne etwas
anzulegen und ohne eine Nummer zu ziehen.
"""

from typing import Optional, Sequence, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..domain import statuses as st
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderUnit, ProcessStep, UserProfile,
)
from ..schemas.deal import DealEmbed, DealParty, DealUpdate
from ..schemas.instance import stock_states
from ..schemas.place import PlaceRef
from ..schemas.order import (
    ArticleOption, FlowGraph, JourneyNeighbour, OrderCreate, OrderLineResponse,
    OrderResponse, OrderSummary, OrderUnitPage, OrderUnitResponse, OrderValidation,
    DRAFT_OBJECT_ID, NeedSource, ProcessEventResponse, ProcessStepResponse,
    RelatedOrder, StepNeed, StepWork, UnitOption, UnitChoices,
)
from ..schemas.process import (
    CaptureTypeInfo, HoldNumbers, ModuleCatalog, ModuleTypeInfo, PaymentSetup,
    RecordEntry, RecordValue, StepConfirm, StepRecord,
)
from ..domain import capture_types, modules
from ..services import article_process as tpl_svc
from ..services import articles as articles_svc
from ..services import consumption as consumption_svc
from ..services import deal as deal_svc
from ..services import flow as flow_svc
from ..services import lookup
from ..services import places as places_svc
from ..services import record as record_svc
from ..services import journey as journey_svc
from ..services import orders as orders_svc
from ..services import process as process_svc
from ..services import stripe_pay
from ..services.admin import log_audit
from ..services.instances import find_unit, unit_number, unit_number_matches

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])

#: Wie viele Log-Einträge das Detail mitliefert. Bei 5000 Stück hat der Log 10 000
#: Einträge; alle mitzuschicken machte die Antwort megabytegross, ohne dass jemand sie
#: liest. Die Gesamtzahl steht daneben (``event_count``) – gekappt, aber nicht verschwiegen.
EVENT_LIMIT = 200

#: Wie viele Abweichungen die Spalte daneben **vollständig** zeigt.
#:
#: Sie zeigen ihren echten Ablauf, nicht ein Symbol – bei zwanzig Abweichungen wären das
#: zwanzig vollständige Prozesse in einer Antwort und in einer Spalte. Gruppieren wäre
#: hier falsch: zwei Abweichungen sind zwei **verschiedene** Abläufe, eine Gruppe daraus
#: sagte nichts. Also ehrlich abschneiden und die wahre Zahl daneben nennen
#: (``deviation_total``) – wer mehr sehen will, öffnet sie einzeln.
RELATED_LIMIT = 3


# ---------------------------------------------------------------------------
# Antwort zusammensetzen
# ---------------------------------------------------------------------------

def _place_ref(db: Session, object_id) -> Optional[PlaceRef]:
    """Eine Objektnummer → ihr Halter. ``None`` bleibt ``None``."""
    return PlaceRef.of(places_svc.station_of(db, int(object_id))) if object_id else None


def _steps(db: Session, order: Order, *,
           viewer: Optional[UserProfile] = None) -> list[ProcessStepResponse]:
    """Die Module eines Auftrags – **mit ihrer Sperre**.

    Ob ein Modul laufen darf, entscheidet nicht das Modul: es steht hier als Auskunft am
    Schritt (``waiting_for``), und durchgesetzt wird es serverseitig in
    ``process.confirm_step``. Ein neuer Modultyp erbt beides, ohne etwas dafür zu tun.
    """
    pending = process_svc.pending_returns(db, order)
    out: list[ProcessStepResponse] = []
    for s in process_svc.steps_of(db, order):
        row = ProcessStepResponse.model_validate(s)
        row.waiting_for = pending.get(s.id, [])
        # **Die Arbeitsliste** – je wartender Instanz eine Zeile. Sie steht am Schritt,
        # weil ein Vorgang eine Instanz ist (Scan-Regel §3): was zu scannen ist, ist
        # dieselbe Liste wie das, was zu tun ist.
        row.work = [StepWork(**w) for w in process_svc.step_work(db, order, s)]
        # **Was das Modul verbraucht** – gerechnet gegen das, was jetzt davorsteht
        # (``services/consumption``). Die Zahl entsteht beim Erreichen, also hier und
        # nicht in der Definition; ein Modul ohne Stückliste liefert eine leere Liste.
        row.needs = [
            StepNeed(
                article_object_id=n.article_object_id, article_name=n.article_name,
                per_unit=n.per_unit, required=n.required, available=n.available,
                here=n.here, place=PlaceRef.of(places_svc.describe(db, n.place)),
                sources=[NeedSource(
                    instance_object_id=src.instance_object_id, free=src.free,
                    here=src.here,
                    place=PlaceRef.of(places_svc.describe(db, src.place)))
                    for src in n.sources],
            )
            for n in consumption_svc.needs(
                db, s, products=process_svc.units_before(db, order, s))
        ]
        # **Wohin es geht** – aufgelöst, nicht als nackte Zahl. Die Oberfläche zeigt den
        # Namen des Halters; ihn dort nachzuschlagen wäre eine Abfrage je Schritt.
        row.target = _place_ref(db, (s.config or {}).get("target"))
        # **Der Geldvorgang** – dieselbe Bauart, eigene Maschine (``services/deal``).
        # ``None`` bei jedem anderen Modultyp. Eine **Gegenpartei** sieht ihn, aber nur
        # ihre eigene Angebotszeile und keine Zahl über Forderung und Geld: gefiltert
        # wird beim Aufbau der Antwort, nicht in der Oberfläche.
        money = deal_svc.embed_data(db, order=order, step=s, viewer=viewer)
        row.deal = DealEmbed(**money) if money else None
        out.append(row)
    return out


#: **Was nur das Personal sieht** – der interne Lauf des Auftrags.
#:
#: Ein Lieferant sieht **seinen Beleg**, nicht die Reise des Materials: nicht den
#: Prozess-Graphen, nicht die Historie, nicht die Nachbar-Aufträge, nicht die Positionen.
#: Als **Liste** und nicht als Bedingungskette, damit die Antwort für ihn buchstäblich
#: die des Personals ist, aus der etwas herausgenommen wurde – zwei getrennt gebaute
#: Antworten liefen beim ersten neuen Feld auseinander.
_INTERNAL_FIELDS = (
    "lines", "flow", "events", "event_count", "journey_in", "journey_out",
    "parents", "deviations", "deviation_total", "waiting_for_return",
)


def _mine_only(resp: OrderResponse, steps: set[int]) -> OrderResponse:
    """Derselbe Auftrag – **nur sein Teil davon** (``deal.mine``)."""
    blank = {
        name: OrderResponse.model_fields[name].get_default(call_default_factory=True)
        for name in _INTERNAL_FIELDS
    }
    return resp.model_copy(update={
        **blank,
        "steps": [s for s in resp.steps if s.id in steps],
        "active_step_id": resp.active_step_id if resp.active_step_id in steps else None,
    })


def _involved(db: Session, viewer: UserProfile) -> Optional[set[tuple[int, int]]]:
    """►►► **Woran ist dieser Betrachter beteiligt?** – (Auftrag, Modul) je Zeile. ◄◄◄

    Ein Modul hat Aussenwirkung: der **Geldvorgang**. Beteiligt ist, wer in einem
    vorkommt; ``None`` heisst «Personal, sieht alles».

    Sie steht **hier** und wird von Feed **und** Detail gelesen. Vorher fragte der Feed
    eine andere Quelle als das Detail: die Gegenpartei eines Geldvorgangs hatte
    ERP-Zugang, sah ihren Auftrag aber in **keiner Liste** – erreichbar nur über die
    direkte Adresse. Zwei Ableitungen derselben Frage laufen genau so auseinander.
    """
    deals = deal_svc.mine(db, viewer)
    if deals is None:
        return None
    return {(r.order_id, r.step_id) for r in deals}


def _visible(db: Session, order: Order, viewer: UserProfile) -> Optional[set[int]]:
    """Die Module dieses Auftrags, die der Betrachter sehen darf. ``None`` = alle.

    Ist er an diesem Auftrag gar nicht beteiligt, gibt es ihn für ihn nicht – **404**,
    nicht 403: ein «du darfst nicht» bestätigt, dass es ihn gibt.
    """
    rows = _involved(db, viewer)
    if rows is None:
        return None
    steps = {step_id for order_id, step_id in rows if order_id == order.id}
    if not steps:
        raise HTTPException(status_code=404, detail=f"Auftrag {order.object_id} nicht gefunden.")
    return steps


def _to_response(db: Session, order: Order, *,
                 viewer: Optional[UserProfile] = None) -> OrderResponse:
    """Der Auftrag als Antwort – **und für einen Lieferanten derselbe, nur sein Teil**.

    Die Verengung steht hier und nicht an den Aufrufstellen: wer sie dort formulierte,
    hätte sie beim zweiten Endpunkt nicht. ``viewer=None`` heisst «interner Aufruf»
    (Personal-only-Endpunkte) und ändert nichts.
    """
    mine = _visible(db, order, viewer) if viewer is not None else None
    lines = process_svc.lines_of(db, order)
    articles = {
        a.id: a
        for a in db.query(Article).filter(Article.id.in_([ln.article_id for ln in lines])).all()
    } if lines else {}
    events, event_count = process_svc.events_page(db, order, limit=EVENT_LIMIT)
    numbers = _event_numbers(db, events)
    actors = _actor_names(db, {e.actor_id for e in events if e.actor_id})
    came_from, went_to = journey_svc.neighbours(db, order)
    # **Ein Graph, ein Bild.** Die Spalten daneben und die Linien dorthin kommen aus
    # derselben Kantenliste: ein Nachbar steht genau dann im Bild, wenn es seine
    # Abzweigung gibt. Zwei Ableitungen ergaben sonst den Abzweigepunkt ohne seinen
    # Nachbarn – ein Punkt, an dem eine Linie ins Nichts führt.
    graph = flow_svc.build(db, order)
    branches = graph.neighbours

    resp = OrderResponse(
        id=order.id,
        object_id=order.object_id,
        name=order.name,
        status=process_svc.order_status(db, order),
        end_status=order.end_status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        is_active=order.is_active,
        lines=[
            OrderLineResponse(
                id=ln.id,
                position=ln.position,
                quantity=ln.quantity,
                origin=ln.origin,
                article_object_id=articles[ln.article_id].object_id if ln.article_id in articles else None,
                article_name=articles[ln.article_id].name if ln.article_id in articles else None,
            )
            for ln in lines
        ],
        steps=_steps(db, order, viewer=viewer),
        flow=FlowGraph(**flow_svc.as_dict(graph)),
        events=[
            ProcessEventResponse(
                id=e.id,
                kind=e.kind,
                step_id=e.step_id,
                unit_number=numbers.get(e.instance_unit_id, str(e.instance_unit_id)),
                status_before=e.status_before,
                status_after=e.status_after,
                actor=actors.get(e.actor_id),
                created_at=e.created_at,
            )
            for e in events
        ],
        event_count=event_count,
        journey_in=[JourneyNeighbour(**n) for n in came_from],
        journey_out=[JourneyNeighbour(**n) for n in went_to],
        active_step_id=process_svc.active_step_id(db, order),
        is_deviation=process_svc.deviation_flags(db, [order.id]).get(order.id, False),
        parents=_related(db, order, journey_svc.parents(db, order), incoming=True),
        deviations=_related(db, order, branches[:RELATED_LIMIT], incoming=False),
        deviation_total=len(branches),
        waiting_for_return=process_svc.waiting_counts(db, [order.id]).get(order.id, 0),
    )
    return resp if mine is None else _mine_only(resp, mine)


def _related(db: Session, order: Order,
             counts: Sequence[Union[journey_svc.Related, flow_svc.Neighbour]],
             *, incoming: bool) -> list[RelatedOrder]:
    """Nachbar-Aufträge mit **ihrem eigenen Ablauf** – dieselben Felder wie die Mitte.

    Sie werden daneben mit derselben Komponente gerendert; darum liefert der Server auch
    dieselben Angaben. Eine gekürzte Sonderform wäre eine zweite Darstellung derselben
    Sache, und die läuft irgendwann von der ersten weg.

    Die Liste kommt für Abweichungen aus dem **Graph** (dort steht die Abzweigung) und
    für übergeordnete Aufträge aus dem **Log** (dort steht die Übernahme) – beide nennen
    einen Auftrag über seine ``order_id``, mehr braucht es hier nicht.
    """
    if not counts:
        return []
    wanted = _order_ids(db, counts)
    rows = {o.id: o for o in db.query(Order).filter(Order.id.in_(wanted)).all()}
    states = process_svc.order_statuses(db, list(rows))
    # Wer gibt zurück: bei Abweichungen die Verbindung des Nachbarn zu mir, bei einem
    # übergeordneten Auftrag meine eigene zu ihm.
    if incoming:
        mine = {m.return_to_order_id for m in db.query(OrderUnit).filter(
            OrderUnit.order_id == order.id, OrderUnit.return_to_order_id.isnot(None)).all()}
        returning = {oid for oid in rows if oid in mine}
    else:
        returning = journey_svc.returning_to(db, order, list(rows))

    out: list[RelatedOrder] = []
    for rel, oid in zip(counts, wanted):
        row = rows.get(oid)
        if row is None:
            continue
        out.append(RelatedOrder(
            object_id=row.object_id,
            name=row.name,
            status=states.get(oid, st.IM_PROZESS),
            end_status=row.end_status,
            steps=_steps(db, row),
            flow=FlowGraph(**flow_svc.as_dict(flow_svc.build(db, row))),
            active_step_id=process_svc.active_step_id(db, row),
            unit_count=rel.unit_count,
            returns=oid in returning,
        ))
    return out


def _order_ids(db: Session,
               counts: Sequence[Union[journey_svc.Related, flow_svc.Neighbour]]) -> list[int]:
    """Die internen ``id``s der Nachbarn – gleich, aus welcher Quelle sie kommen.

    Der Graph kennt einen Auftrag über seine **Objektnummer** (nach aussen ist das seine
    Identität), der Log über die interne ``id``. Hier wird das **einmal** übersetzt, in
    einer Abfrage – statt die eine Quelle der anderen anzupassen.
    """
    objs = [r.object_id for r in counts if isinstance(r, flow_svc.Neighbour)]
    known = {
        int(o): int(i)
        for o, i in db.query(Order.object_id, Order.id).filter(Order.object_id.in_(objs)).all()
    } if objs else {}
    return [
        known.get(r.object_id, -1) if isinstance(r, flow_svc.Neighbour) else r.order_id
        for r in counts
    ]


def _event_numbers(db: Session, events) -> dict[int, str]:
    """Nummern nur für die Stücke, die in den gezeigten Einträgen vorkommen."""
    ids = {e.instance_unit_id for e in events}
    if not ids:
        return {}
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(ids)).all()
    return process_svc.unit_numbers(db, units)


def _actor_names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {
        u.id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.id.in_(ids)).all()
    }


# ---------------------------------------------------------------------------
# Endpunkte
# ---------------------------------------------------------------------------

@router.get("", response_model=list[OrderSummary])
def list_orders(
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Der Feed – **ohne** Schritte, Stücke und Historie (die kommen mit dem Detail).

    **Eine Gegenpartei sieht die Aufträge, an denen sie beteiligt ist** – dieselbe eine
    Frage wie im Detail (``_involved``), damit Liste und Datensatz nicht auseinanderlaufen
    können. Genau das war einmal nicht so: der Feed fragte nur den Beschaffungs-Beleg,
    also stand der Auftrag eines **Geldvorgangs** in keiner Liste.

    Der Status wird für alle Zeilen in **einer** Abfrage abgeleitet: er steht nirgends
    gespeichert, und ihn je Zeile einzeln zu holen wäre ein N+1 über den ganzen Feed.
    """
    query = db.query(Order)
    involved = _involved(db, user)
    if involved is not None:
        query = query.filter(Order.id.in_({order_id for order_id, _ in involved} or {0}))
    rows = query.order_by(Order.object_id.desc()).limit(limit).offset(offset).all()
    states = process_svc.order_statuses(db, [o.id for o in rows])
    flags = process_svc.deviation_flags(db, [o.id for o in rows])
    return [
        OrderSummary(
            id=o.id, object_id=o.object_id, name=o.name, status=states[o.id],
            created_at=o.created_at, updated_at=o.updated_at, is_active=o.is_active,
            is_deviation=flags.get(o.id, False),
        )
        for o in rows
    ]


@router.get("/article-options", response_model=list[ArticleOption])
def article_options(
    search: Optional[str] = Query(None, description="Objektnummer-Teil oder Name"),
    object_id: Optional[int] = Query(None, description="Genau diesen Artikel auflösen"),
    limit: int = Query(20, le=300),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Welche Artikel kann ich in eine Definitionszeile nehmen?

    ``template_steps`` fährt mit, damit die Oberfläche «Neu» sperren **und begründen**
    kann. Sie in zwei Aufrufen zu holen hiesse, die Zeile erst leer und dann korrigiert
    zu zeigen.

    **Gesucht wird, nicht geladen** (Testnotiz #738). Vorher lieferte dieser Endpunkt bis
    zu 300 Artikel am Stück, und die Oberfläche machte daraus ein natives Dropdown: nicht
    durchsuchbar, und bei tausend Artikeln tausend Knoten je Zeile. Jetzt liefert er, was
    zur Eingabe passt (`services/lookup` – dieselbe Bedingung wie überall), plus auf
    Wunsch genau **den einen** gewählten (``object_id``), damit im Feld sein Name steht
    und nicht seine Ziffern.
    """
    q = db.query(Article).filter(
        Article.is_active.is_(True), Article.object_id.isnot(None))
    if object_id is not None:
        q = q.filter(Article.object_id == object_id)
    else:
        q = q.filter(lookup.matches(search or "", Article.object_id, Article.name))
    rows = q.order_by(Article.object_id.desc()).limit(limit).all()
    counts = tpl_svc.step_counts(db, [a.id for a in rows])
    return [
        ArticleOption(
            object_id=a.object_id,
            name=a.name,
            serialization=a.serialization,
            unit=a.unit,
            template_steps=counts.get(a.id, 0),
            # **Dieselbe Regel wie in der Freigabe** (``articles.may_create``) – nicht
            # nachgebaut, sondern gefragt.
            create_problem=articles_svc.may_create(a),
        )
        for a in rows
    ]


@router.get("/deal-parties", response_model=list[DealParty])
def deal_parties(
    search: str = Query("", description="Objektnummer-Teilstring oder Name"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """**Wer kommt als Gegenpartei eines Geldvorgangs in Frage?**

    Dieselbe Suchbedingung wie überall (``services/lookup``: Nummer **oder** Name) und
    **ohne Rollenfilter**: eine Rolle sagt, was jemand *für uns* tut, nicht ob wir mit
    ihm Geld austauschen dürfen. Wer einschränken will, nennt die zugelassenen
    Gegenparteien in der **Definition** – dort gehört eine solche Freigabe hin, und dort
    gilt sie dann auch beim Ausführen (``deal._party``).

    **Vor** ``/{object_id}`` deklariert – sonst schluckt der Pfad-Parameter den Namen und
    die Suche endet als «100000xyz ist keine Zahl».
    """
    return [
        DealParty(object_id=u.object_id, name=u.display_name)
        for u in deal_svc.search_parties(db, search=search, limit=limit)
    ]


@router.get("/module-catalog", response_model=ModuleCatalog)
def module_catalog(_: UserProfile = Depends(require_employee)):
    """Was sich modellieren lässt – Modultypen und Erfassungspunkt-Typen.

    Beides sind **geschlossene Listen** im Backend (``domain/modules``,
    ``domain/capture_types``). Die Oberfläche holt sie hier, statt sie nachzubauen: eine
    zweite Aufzählung liefe beim ersten neuen Typ auseinander, und der Fehler zeigte sich
    erst, wenn jemand ihn auswählt.
    """
    return ModuleCatalog(
        modules=[
            ModuleTypeInfo(key=m.key, label=m.label, tone=m.tone, terminal=m.terminal,
                           status_before=m.status_before, status_after=m.status_after)
            for m in modules.MODULES.values()
        ],
        # ►►► **Die Steuersätze stehen hier NICHT mehr** (Testnotiz #851). ◄◄◄
        #
        # Sie waren die Vorgabe eines Modul-Feldes, und das Feld ist entfallen: der Satz
        # hängt an der **Sache**, nicht am Modul. Gefragt wird er je Position an der
        # Ausführungsstelle, und dorthin reist der Katalog mit dem Vorgang
        # (``DealEmbed.vat_rates``). Ein zweiter Weg zur selben Liste wäre die Stelle,
        # die beim nächsten Satzwechsel jemand vergisst.
        capture_types=[CaptureTypeInfo(key=t.key, label=t.label) for t in capture_types.ALL],
    )


@router.get("/unit-options", response_model=UnitChoices)
def unit_options(
    article: Optional[int] = Query(None, description="Objektnummer des Artikels"),
    search: Optional[str] = Query(None, description="Teil einer Stück- oder Instanznummer"),
    status: Optional[list[str]] = Query(None, description="Nur diese Zustände"),
    preselect: int = Query(0, ge=0, le=500, description="Wie viele FIFO vorschlagen"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Welche Einzelinstanzen kann ich in eine ``Lager``-Zeile nehmen?

    **Eine Seite, nicht die Liste** (Testnotiz #740). Vorher lieferte dieser Endpunkt bis
    zu 300 Stücke am Stück, und die Oberfläche machte daraus alles Weitere. Bei
    zehntausend Schrauben war das an drei Stellen falsch:

    * die **Vorauswahl** kam aus der gekappten Liste – sind die ersten 300 verbaut, findet
      sie nichts, obwohl freie da sind. Sie kommt jetzt von hier (``preselect``): FIFO ist
      eine Regel, keine Anzeige.
    * die **Zähler** kamen aus der Seite und zeigten «300», wo fünfzigtausend liegen. Sie
      kommen jetzt aus einem Aggregat über den ganzen Artikel (``states``).
    * die **Herkunfts-Map** las **alle** offenen Zugehörigkeiten des Systems, um bei 300
      Zeilen nachzuschlagen. Sie ist jetzt auf die Seite eingeschränkt.

    **FIFO fragt «liegt es im Regal?»**, nicht «lässt es sich nehmen?» – zwei
    Eigenschaften, die der Katalog getrennt führt (``UnitOption``). Ein **verbautes**
    Stück steht darum weiterhin in der Liste (das Greifen IST der Ausbau), aber nie im
    Vorschlag: es steckt in etwas anderem und müsste erst ausgebaut werden.
    """
    mine = (
        InstanceUnit.is_active.is_(True),
        Instance.is_active.is_(True),
    )
    base = (
        db.query(InstanceUnit, Instance, Article)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .outerjoin(Article, Article.id == Instance.article_id)
        .filter(*mine)
    )
    if article is not None:
        base = base.filter(Article.object_id == article)

    # ── Die Aufstellung: über ALLE Stücke dieses Artikels, nicht über die Seite ──
    counts = {
        s: int(n)
        for s, n in db.query(InstanceUnit.status, func.count(InstanceUnit.id))
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .outerjoin(Article, Article.id == Instance.article_id)
        .filter(*mine, *( (Article.object_id == article,) if article is not None else () ))
        .group_by(InstanceUnit.status)
        .all()
    }

    q = base
    if status:
        q = q.filter(InstanceUnit.status.in_(status))
    if search and search.strip():
        # **Die Form der Nummer kennt `services/instances`**, nicht dieser Endpunkt:
        # «-7» meint den Suffix, «00123» die Instanz, «100000123-7» beides. Hier
        # ausgeschrieben träfe «9» jede Instanz mit einer 9 in der Nummer.
        q = q.filter(unit_number_matches(search, Instance.object_id, InstanceUnit.suffix))

    total = q.with_entities(func.count(InstanceUnit.id)).order_by(None).scalar() or 0
    rows = q.order_by(InstanceUnit.id).limit(limit).offset(offset).all()

    return UnitChoices(
        units=_unit_options(db, rows),
        total=int(total),
        states=stock_states(counts),
        preselect=_fifo(db, base, preselect),
    )


def _unit_options(db: Session, rows: Sequence[tuple]) -> list[UnitOption]:
    """Die geladenen Stücke als Antwort – **eine** Zusatzabfrage für die Seite.

    Die Herkunfts-Map war die schwerste Stelle des alten Endpunkts: sie las jede offene
    Zugehörigkeit des Systems. Sie fragt jetzt nach genau den Stücken, die auf dieser
    Seite stehen (``ix_order_units_instance_unit_id``).
    """
    ids = [u.id for u, _i, _a in rows]
    running = {
        m.instance_unit_id: o.object_id
        for m, o in db.query(OrderUnit, Order)
        .join(Order, Order.id == OrderUnit.order_id)
        .filter(OrderUnit.released_at.is_(None), OrderUnit.instance_unit_id.in_(ids))
        .all()
    } if ids else {}
    return [
        UnitOption(
            number=unit_number(instance, unit),
            status=unit.status,
            article_object_id=art.object_id if art else None,
            article_name=art.name if art else None,
            # **Dieselbe Frage wie in der Freigabe** (``statuses.is_selectable``): frei,
            # in einem laufenden Auftrag, gesperrt oder verbaut – all das lässt sich
            # nehmen. Nicht nehmen lässt sich, was es physisch nicht mehr gibt.
            available=st.is_selectable(unit.status),
            # **Und die zweite, die FIFO stellt**: liegt es im Regal? Verbaut heisst nein.
            in_stock=st.stock_kind(unit.status) == st.LIVE,
            in_order=running.get(unit.id),
        )
        for unit, instance, art in rows
    ]


def _fifo(db: Session, base, want: int) -> list[str]:
    """Die **Vorauswahl**: die ältesten Stücke, die im Regal liegen und frei sind.

    Älteste zuerst heisst aufsteigende ``id`` – Nummern werden aufsteigend vergeben, und
    ein Stück entsteht mit seiner Instanz; ein zweites Datum gibt es nicht.

    **Gebunden ist nicht frei**: ein Stück, das in einem laufenden Auftrag läuft, lässt
    sich zwar nehmen – daraus wird eine Abweichung, die einem anderen Auftrag sein
    Material entzieht. Das darf nie die Voreinstellung sein, also steht es hier nicht.

    **Sie ignoriert Suche und Zustandsfilter** – bewusst: ``base`` trägt nur den Artikel.
    Der Vorschlag ist eine Aussage über den Bestand, keine über den gerade gewählten
    Ausschnitt; wer nach «verbaut» filtert, bekäme sonst eine Vorauswahl, die sich beim
    Zurücksetzen des Filters wieder ändert.
    """
    if want <= 0:
        return []
    busy = db.query(OrderUnit.instance_unit_id).filter(OrderUnit.released_at.is_(None))
    rows = (
        base.filter(InstanceUnit.status.in_(st.IN_STOCK_UNIT_STATUSES),
                    InstanceUnit.id.notin_(busy))
        .order_by(InstanceUnit.id)
        .limit(want)
        .all()
    )
    return [unit_number(instance, unit) for unit, instance, _a in rows]


@router.post("/validate", response_model=OrderValidation)
def validate_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Wäre dieser Entwurf freigebbar? Legt **nichts** an, zieht **keine** Nummer.

    Dazu die **Vorschau** (Auftrag §2): die laufenden Aufträge, aus denen der Entwurf
    Stücke nähme, jeder mit dem Bild, das er nach der Freigabe hätte. Sie kommt aus
    derselben Ableitung wie das echte Bild (``flow.build`` mit ``planned``) – ein
    Nachbau im Browser wäre eine zweite Wahrheit, und die läuft von der ersten weg.
    """
    draft = data.model_dump()
    missing = orders_svc.validate_draft(db, draft)
    return OrderValidation(saveable=not missing, missing=missing,
                           parents=_preview_parents(db, draft))


def _preview_parents(db: Session, draft: dict) -> list[RelatedOrder]:
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
    # An welchem Punkt hängen die gewählten Stücke? Die offene Zeile des Quell-Auftrags
    # sagt es – eine Abfrage, keine Rekonstruktion.
    # Nummer → Einzelinstanz über die **eine** Auflösung (`instances.find_unit`); eine
    # eigene Abfrage hier wäre eine zweite Lesart derselben Schreibweise.
    chosen = {u.id for u in (find_unit(db, n) for n in picked) if u is not None}
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
            status=process_svc.order_status(db, row),
            end_status=row.end_status,
            steps=_steps(db, row),
            flow=FlowGraph(**flow_svc.as_dict(flow_svc.build(db, row, planned=plan))),
            active_step_id=process_svc.active_step_id(db, row),
            unit_count=taken,
            returns=want[row.object_id],
        ))
    return out


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Anlegen **ist** Freigeben – ein Aufruf, eine Transaktion (§6.3)."""
    order = orders_svc.create_order(db, data.model_dump(), actor_id=user.id)
    log_audit(db, "orders", "release", str(order.object_id),
              user_id=user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return _to_response(db, order)


@router.get("/{object_id}", response_model=OrderResponse)
def get_order(
    object_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Der Auftrag – und für einen Lieferanten **derselbe, nur sein Modul**."""
    return _to_response(db, orders_svc.get(db, object_id), viewer=user)


@router.get("/{object_id}/units", response_model=OrderUnitPage)
def list_units(
    object_id: int,
    edge: str = Query(..., description="Die Kante des Prozessbildes, deren Stücke gemeint sind."),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Die einzelnen Stücke **einer Position** – erst wenn jemand aufklappt.

    **Gefragt wird nach der Kante**, nicht nach «Schritt X, aktiv» (Befund 2.1). Die
    gröbere Frage war eine zweite Quelle: an einem Punkt mit Teilung zählte die Pille
    die Gruppe, die Liste kannte die Teilung nicht und zeigte beide – «1 Stk», und im
    Aufklappen zwei Nummern. Jetzt beantwortet die Zuordnung im Graph beide Fragen
    (``flow.units_on``).
    """
    order = orders_svc.get(db, object_id)
    rows, total = process_svc.units_page(
        db, order, membership_ids=flow_svc.units_on(db, order, edge),
        limit=limit, offset=offset,
    )
    numbers = process_svc.unit_numbers(db, [u for _, u in rows])
    started = process_svc.started_at(db, order, [u.id for _, u in rows])
    return OrderUnitPage(
        units=[
            OrderUnitResponse(
                instance_unit_id=u.id,
                number=numbers[u.id],
                status=u.status,
                current_step_id=m.current_step_id,
                active=m.released_at is None,
                started_at=started.get(u.id),
            )
            for m, u in rows
        ],
        total=total,
    )


@router.post("/{object_id}/steps/{step_id}/confirm", response_model=OrderResponse)
def confirm_step(
    object_id: int,
    step_id: int,
    data: StepConfirm,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """«Bestätigen» – der **eine** Ausführungs-Endpunkt, für jedes Modul derselbe.

    Was im Rumpf steht, entscheidet der Modultyp: bei der Datenerfassung die erfassten
    Werte. Ein Endpunkt je Modul wäre ein zweiter Ausführungspfad – und damit eine
    zweite Stelle, an der ein Statuswechsel geschrieben wird.
    """
    order = orders_svc.get(db, object_id)
    outcome = process_svc.confirm_step(
        db, order=order, step_id=step_id, values=data.values,
        instance_object_id=data.instance_object_id, verification=data.verification,
        sources=data.sources, place=data.place,
        actor_id=user.id)
    log_audit(db, "process_steps", "confirm",
              f"{outcome['moved']} bewegt, {outcome['held']} angehalten",
              user_id=user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return _to_response(db, order)


@router.post("/{object_id}/steps/{step_id}/deal", response_model=OrderResponse)
def update_deal(
    object_id: int,
    step_id: int,
    data: DealUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """**Eine Handlung am Geldvorgang** – ein Endpunkt, acht Verben.

    ``ask`` · ``quote`` · ``decline`` · ``agree`` · ``revoke`` · ``charge`` · ``pay`` ·
    ``reverse``. Das letzte **storniert** eine Geld-Zeile durch eine Gegenbuchung; einen
    Löschweg gibt es nicht (Testnotizen #823/#824).

    **``POST``, nicht ``PATCH``**: das ist ein Befehl, kein Feld-Update – derselbe Grund
    wie bei ``/confirm``. Was an welcher Stufe **und für welche Rolle**
    erlaubt ist, sagt ``services/deal.can``, und dieselbe Tabelle ist Auskunft und Tor.

    **Nur gesendete Felder wirken** (``DealUpdate.changes``): wer den Betrag ändert, soll
    nicht die Notiz verlieren, weil er sie nicht mitgeschickt hat.

    **Auch für die Gegenpartei offen** (``get_current_user``) – und das geht erst, seit
    die Antwort verengt wird: ``_visible`` zeigt ihr nur ihr Modul, ``deal.embed_data``
    nur ihre eigene Angebotszeile und keine Zahl über Forderung und Geld. Was sie **tun**
    darf, sagt ``can`` (``Direction.party_actions`` – wer den Preis nennt, offeriert;
    wer ihn empfängt, nimmt an oder lehnt ab), und ``apply`` weist
    alles andere ab. Wer ohnehin ins ERP darf, sieht unverändert den ganzen Auftrag.
    """
    order = orders_svc.get(db, object_id)
    # **Dieselbe eine Frage wie beim Lesen**: wer den Auftrag nicht sieht, handelt auch
    # nicht an ihm – und wer nur sein Modul sieht, nur an diesem.
    mine = _visible(db, order, user)
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None or (mine is not None and step.id not in mine):
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    row = deal_svc.apply(db, order=order, step=step, action=data.action,
                         payload=data.changes(), actor=user)
    log_audit(db, "deals", data.action,
              f"Geldvorgang zu Modul {step.id} → {row.stage}",
              user_id=user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return _to_response(db, order, viewer=user)


@router.get("/{object_id}/steps/{step_id}/hold", response_model=HoldNumbers)
def hold_numbers(
    object_id: int,
    step_id: int,
    instance: int = Query(..., description="Objektnummer der betroffenen Instanz"),
    group: str = Query(..., description="sample | failed"),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Die Nummern einer Gruppe – **erst auf Klick** (§4/§4.1).

    ``sample`` sind die gezogenen Stücke (für jedes ist ein Wertesatz zu erfassen),
    ``failed`` die durchgefallenen. Letztere gehen als Vorauswahl in einen ganz
    gewöhnlichen Auftragsentwurf – die Abweichung ist kein eigener Mechanismus, sondern
    dieselbe Anlage mit anderer Vorbelegung.

    Die frühere dritte Gruppe ``rest`` ist ersatzlos entfallen (§4.1, Testnotiz #713).

    Nicht in der Auftrags-Antwort, weil die Stichprobe einer 6000er-Charge tausende
    Nummern wären – mitgeliefert bei jedem Öffnen.
    """
    order = orders_svc.get(db, object_id)
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    return HoldNumbers(numbers=process_svc.held_numbers(
        db, order, step, instance_object_id=instance, group=group))


@router.get("/{object_id}/steps/{step_id}/record", response_model=StepRecord)
def step_record(
    object_id: int,
    step_id: int,
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """►►► **Was ist an diesem Modul passiert?** ◄◄◄ — lückenlos, je Einzelinstanz.

    Die Regel gilt für **alle** Module (Testnotiz #717) und steht darum an **einer**
    Stelle (``services/record``): sie liest den Ereignis-Log, und den schreibt jedes
    Modul über dieselbe Schreibstelle. Ein neuer Modultyp erbt sein Protokoll, ohne eine
    Zeile dafür.

    **Erst auf Klick, nie auf Vorrat**: bei einer 6000er-Charge wären das tausende
    Einträge in jeder Auftrags-Antwort. Gekappt wird seitenweise, die Gesamtzahl steht
    daneben.
    """
    order = orders_svc.get(db, object_id)
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    entries, total = record_svc.step_record(db, order, step, limit=limit, offset=offset)
    return StepRecord(
        total=total,
        entries=[
            RecordEntry(
                number=e.number, at=e.at, actor=e.actor, verification=e.verification,
                status_after=e.status_after, result=e.result, sampled=e.sampled,
                into=e.into,
                values=[RecordValue(key=v.key, label=v.label, type=v.type,
                                    value=v.value, ok=v.ok)
                        for v in e.values],
            )
            for e in entries
        ],
    )


@router.post("/{object_id}/steps/{step_id}/deal/payment", response_model=PaymentSetup)
def prepare_payment(
    object_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """►►► **Eine Zahlung über den offenen Betrag vorbereiten** – für UNSERE Karte. ◄◄◄

    Kein Verb am Vorgang, weil sie **nichts** an ihm ändert: sie erzeugt eine Absicht beim
    Zahlungsdienst und gibt zurück, was das Formular im Browser braucht. Gebucht wird
    erst, wenn das Geld wirklich da ist – und das meldet der Webhook, nicht der Browser
    des Zahlenden.

    **Ein eigener Weg statt eines Verbs an ``…/deal``**: der gibt den Auftrag zurück, hier
    kommt ein Geheimnis für genau diese eine Zahlung. Zwei verschiedene Antworten sind
    zwei Endpunkte; das Verb steht trotzdem in ``can`` – «was darf ich hier tun» ist EINE
    Frage, und dieselbe Liste ist auch hier das **Tor**.

    **Auch für die Gegenpartei offen** (``get_current_user``) – das ist der Sinn: der
    Kunde bezahlt bei uns, nicht auf einer fremden Seite. Was sie darf, sagt
    ``deal.can`` (``Direction.party_actions``); wer den Auftrag nicht sieht, bekommt
    ``404`` wie überall.

    Ohne eingerichteten Dienst gibt es diesen Weg nicht (``404`` aus ``stripe_pay._api``)
    – und der Knopf erscheint dann gar nicht erst, weil ``can`` das Verb nicht führt.
    """
    order = orders_svc.get(db, object_id)
    # **Dieselbe eine Frage wie beim Lesen** (wie bei ``…/deal``): wer den Auftrag nicht
    # sieht, zahlt auch nicht an ihm – und wer nur sein Modul sieht, nur an diesem.
    mine = _visible(db, order, user)
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None or (mine is not None and step.id not in mine):
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    row = deal_svc.of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404,
                            detail="Dieses Modul hat keinen Geldvorgang.")
    # ►►► **Dieselbe Tabelle, die den Knopf zeigt, lässt hier durch.** ◄◄◄ Eine eigene
    # Prüfung daneben wäre ein zweiter Massstab – und der bekäme die nächste Bedingung
    # nicht mit.
    deal_svc.assert_allowed(db, row, "pay_online", user)
    return PaymentSetup(**stripe_pay.prepare(db, deal=row, order=order))
