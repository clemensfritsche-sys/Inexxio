"""Auftrag – Feed, Freigabe, Detail, Schritt bestätigen.

Es gibt **keinen** Entwurfs-Endpunkt: ein Auftragsentwurf lebt im Browser, bis er
freigebbar ist. Erst ``POST`` legt ihn an – und dieser eine Aufruf ist zugleich die
Freigabe. ``/validate`` sagt der Oberfläche vorher, ob es reichen würde, ohne etwas
anzulegen und ohne eine Nummer zu ziehen.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import DB
from ..models import (
    Article, Instance, InstanceUnit, Order, ProcessStep, UserProfile,
)
from ..schemas.voucher import (
    PaperOut, PapersOut, VoucherCorrectable, VoucherUpdate,
)
from ..schemas.instance import stock_states
from ..schemas.order import (
    ArticleOption, OrderCreate, OrderResponse, OrderSummary, OrderUnitPage, OrderUnitResponse, OrderValidation,
    UnitChoices,
)
from ..schemas.process import (
    CaptureTypeInfo, HoldNumbers, ModuleCatalog, ModuleTypeInfo, PaymentSetup,
    StepConfirm, StepRecord, TransferInfo,
)
from ..domain import capture_types, modules, statuses as st
from ..services import log
from ..services import article_process as tpl_svc
from ..services import articles as articles_svc
from ..services import voucher as voucher_svc
from ..services import voucher_actions, voucher_money, voucher_view
from ..services import voucher_docs
from ..services import flow as flow_svc
from ..services import lookup
from ..services import consumption as consumption_svc
from ..services import record as record_svc
from ..services import orders as orders_svc
from ..services import loop as loop_svc
from ..services import order_state
from ..services import process as process_svc
from ..services import stripe_pay
from ..services.instances import unit_number_matches, unit_numbers
from ..domain.errors import NotFound
from ..services import order_view as view

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# Antwort zusammensetzen
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Endpunkte
# ---------------------------------------------------------------------------

@router.get("", response_model=list[OrderSummary])
def list_orders(
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
    db: Session = DB,
    user: UserProfile = Depends(get_current_user),
):
    """Der Feed – **ohne** Schritte, Stücke und Historie (die kommen mit dem Detail).

    **Eine Gegenpartei sieht die Aufträge, an denen sie beteiligt ist** – dieselbe eine
    Frage wie im Detail (``involved``), damit Liste und Datensatz nicht auseinanderlaufen
    können.

    Der Status wird für alle Zeilen in **einer** Abfrage abgeleitet: er steht nirgends
    gespeichert, und ihn je Zeile einzeln zu holen wäre ein N+1 über den ganzen Feed.
    """
    query = db.query(Order)
    involved = view.involved(db, user)
    if involved is not None:
        query = query.filter(Order.id.in_({order_id for order_id, _ in involved} or {0}))
    rows = query.order_by(Order.object_id.desc()).limit(limit).offset(offset).all()
    states = order_state.order_statuses(db, [o.id for o in rows])
    flags = order_state.deviation_flags(db, [o.id for o in rows])
    return [
        OrderSummary(
            id=o.id, object_id=o.object_id, name=o.name, status=states[o.id],
            created_at=o.created_at, updated_at=o.updated_at,
            is_deviation=flags.get(o.id, False),
        )
        for o in rows
    ]


@router.get("/article-options", response_model=list[ArticleOption])
def article_options(
    search: Optional[str] = Query(None, description="Objektnummer-Teil oder Name"),
    object_id: Optional[int] = Query(None, description="Genau diesen Artikel auflösen"),
    limit: int = Query(20, le=300),
    db: Session = DB,
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
    q = db.query(Article).filter(Article.object_id.isnot(None))
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
            ModuleTypeInfo(key=m.key, label=m.label, tone=m.tone, terminal=m.terminal)
            for m in modules.MODULES.values()
        ],
        # Keine Steuersätze im Modul-Katalog: der Satz hängt an der Sache
        # (``VoucherEmbed.vat_rates``).
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
    db: Session = DB,
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
    base = (
        db.query(InstanceUnit, Instance, Article)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .outerjoin(Article, Article.id == Instance.article_id)
    )
    if article is not None:
        base = base.filter(Article.object_id == article)

    # ── Die Aufstellung: über ALLE Stücke dieses Artikels, nicht über die Seite ──
    counts = {
        s: int(n)
        for s, n in db.query(InstanceUnit.status, func.count(InstanceUnit.id))
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .outerjoin(Article, Article.id == Instance.article_id)
        .filter(*((Article.object_id == article,) if article is not None else ()))
        .group_by(InstanceUnit.status)
        .all()
    }

    q = base
    if status:
        q = q.filter(InstanceUnit.status.in_(status))
    if search and search.strip():
        # Die Form der Nummer kennt `services/instances` («-7» Suffix, «00123» Instanz).
        q = q.filter(unit_number_matches(search, Instance.object_id, InstanceUnit.suffix))

    total = q.with_entities(func.count(InstanceUnit.id)).order_by(None).scalar() or 0
    rows = q.order_by(InstanceUnit.id).limit(limit).offset(offset).all()

    return UnitChoices(
        units=view.unit_option_rows(db, rows),
        total=int(total),
        states=stock_states(counts),
        # FIFO an der einen Stelle – im Regal, frei, älteste zuerst.
        preselect=consumption_svc.free_numbers(db, article, preselect,
                                               statuses=st.IN_STOCK_UNIT_STATUSES),
    )


@router.post("/validate", response_model=OrderValidation)
def validate_order(
    data: OrderCreate,
    db: Session = DB,
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
    return OrderValidation(missing=missing, parents=view.preview_parents(db, draft))


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = DB,
    user: UserProfile = Depends(require_employee),
):
    """Anlegen **ist** Freigeben – ein Aufruf, eine Transaktion (§6.3)."""
    order = orders_svc.create_order(db, data.model_dump(), actor_id=user.id, actor=user)
    db.flush()
    db.refresh(order)
    return view.response(db, order)


@router.post("/{object_id}/loop/end", response_model=OrderResponse)
def end_loop(
    object_id: int,
    db: Session = DB,
    _: UserProfile = Depends(require_employee),
):
    """**Die Wiederholung beenden** – am neuesten Auftrag der Kette, auch wenn er abgeschlossen
    ist; endgültig. Der Auftrag selbst ändert sich nicht (``loop.end`` → ``loop.ended``)."""
    order = orders_svc.get(db, object_id)
    loop_svc.end(db, order)
    db.flush()
    return view.response(db, order)


@router.get("/{object_id}", response_model=OrderResponse)
def get_order(
    object_id: int,
    db: Session = DB,
    user: UserProfile = Depends(get_current_user),
):
    """Der Auftrag – und für eine Gegenpartei **derselbe, nur ihr Modul**."""
    return view.response(db, orders_svc.get(db, object_id), viewer=user)


@router.get("/{object_id}/units", response_model=OrderUnitPage)
def list_units(
    object_id: int,
    edge: str = Query(..., description="Die Kante des Prozessbildes, deren Stücke gemeint sind."),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = DB,
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
    rows, total = order_state.units_page(
        db, order, membership_ids=flow_svc.units_on(db, order, edge),
        limit=limit, offset=offset,
    )
    numbers = unit_numbers(db, [u for _, u in rows])
    started = order_state.started_at(db, order, [u.id for _, u in rows])
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
    db: Session = DB,
    user: UserProfile = Depends(require_employee),
):
    """«Bestätigen» – der **eine** Ausführungs-Endpunkt, für jedes Modul derselbe.

    Was im Rumpf steht, entscheidet der Modultyp: bei der Datenerfassung die erfassten
    Werte. Ein Endpunkt je Modul wäre ein zweiter Ausführungspfad – und damit eine
    zweite Stelle, an der ein Statuswechsel geschrieben wird.
    """
    order = orders_svc.get(db, object_id)
    process_svc.confirm_step(
        db, order=order, step_id=step_id, values=data.values,
        instance_object_id=data.instance_object_id, verification=data.verification,
        sources=data.sources, place=data.place,
        actor_id=user.id)
    db.flush()
    db.refresh(order)
    return view.response(db, order)


@router.get("/{object_id}/steps/{step_id}/hold", response_model=HoldNumbers)
def hold_numbers(
    object_id: int,
    step_id: int,
    instance: int = Query(..., description="Objektnummer der betroffenen Instanz"),
    group: str = Query(..., description="sample – die gezogenen Stücke"),
    db: Session = DB,
    _: UserProfile = Depends(require_employee),
):
    """Die Nummern der gezogenen Stücke einer Instanz – **erst auf Klick** (§9.3).

    Für jedes ist ein Wertesatz zu erfassen. Nicht in der Auftrags-Antwort, weil die
    Stichprobe einer 6000er-Charge tausende Nummern wären – mitgeliefert bei jedem Öffnen.
    """
    order = orders_svc.get(db, object_id)
    step = process_svc.step_of(db, order, step_id)
    return HoldNumbers(numbers=order_state.held_numbers(
        db, order, step, instance_object_id=instance, group=group))


@router.get("/{object_id}/steps/{step_id}/record", response_model=StepRecord)
def step_record(
    object_id: int,
    step_id: int,
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
    db: Session = DB,
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
    step = process_svc.step_of(db, order, step_id)
    entries, total = record_svc.step_record(db, order, step, limit=limit, offset=offset)
    return StepRecord(total=total, entries=entries)


# ---------------------------------------------------------------------------
# ►►► DER BELEG — das Modul «Zahlung» (docs/history/2026-09-neuaufbau-zahlungsmodul.md)
# ---------------------------------------------------------------------------
#
# Eigene Wege statt einer Verzweigung in einem geteilten Endpunkt.

def _voucher_step(db: Session, order, step_id: int, user: UserProfile):
    """**Der Beleg eines Moduls – und ob dieser Betrachter ihn sieht.**

    Viermal dieselbe Vorrede (Handeln · Vorbereiten · Erstatten · Überweisen);
    ausgeschrieben wäre sie viermal dieselbe Chance, eine der beiden Prüfungen zu
    vergessen.
    """
    mine = view.visible_steps(db, order, user)
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None or (mine is not None and step.id not in mine):
        raise NotFound("Diesen Prozessschritt gibt es nicht.")
    row = voucher_svc.of_step(db, step.id)
    if row is None:
        raise NotFound("Dieses Modul hat keinen Beleg.")
    return step, row


@router.post("/{object_id}/steps/{step_id}/voucher", response_model=OrderResponse)
def update_voucher(
    object_id: int,
    step_id: int,
    data: VoucherUpdate,
    db: Session = DB,
    user: UserProfile = Depends(get_current_user),
):
    """**Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle (``voucher_actions.VERBS``).

    **``POST``, nicht ``PATCH``**: das ist ein Befehl, kein Feld-Update – derselbe Grund
    wie bei ``/confirm``. Was an welcher Stufe **und für welche Rolle** erlaubt ist, sagt
    ``voucher_actions.can``, und dieselbe Tabelle ist Auskunft und Tor.

    **Nur gesendete Felder wirken** (``VoucherUpdate.changes``): wer den Betrag ändert,
    soll nicht die Notiz verlieren, weil er sie nicht mitgeschickt hat.

    **Auch für die Gegenpartei offen** – und das geht, weil die Antwort verengt wird:
    ``visible_steps`` zeigt ihr nur ihr Modul, ``voucher_view.embed_data`` nur ihre eigene
    Angebotszeile und keine Zahl über Forderung und Geld.
    """
    order = orders_svc.get(db, object_id)
    step, _row = _voucher_step(db, order, step_id, user)
    row = voucher_actions.apply(db, order=order, step=step, action=data.action,
                            payload=data.changes(), actor=user)
    # Die Handlung selbst (das Verb) – was sie an Zeilen änderte, schreibt die Datenbank.
    log.event(db, "voucher.action", order.object_id,
              {"action": data.action, "step": step.id, "stage": row.stage},
              table="vouchers", row=row.id)
    db.flush()
    db.refresh(order)
    return view.response(db, order, viewer=user)


@router.post("/{object_id}/steps/{step_id}/voucher/preview", response_model=PapersOut)
def preview_voucher(
    object_id: int,
    step_id: int,
    data: VoucherUpdate,
    db: Session = DB,
    user: UserProfile = Depends(require_employee),
):
    """►►► **Vorschau → Freigeben**: das Papier, das diese Handlung hinausgäbe – gerechnet von
    derselben Handlung in einem Savepoint, danach zurückgerollt (``voucher_docs.preview``).
    Erst «Freigeben» ruft die Handlung wirklich (``/voucher``)."""
    order = orders_svc.get(db, object_id)
    step, _row = _voucher_step(db, order, step_id, user)
    papers = voucher_docs.preview(db, order=order, step=step, action=data.action,
                                  payload=data.changes(), actor=user)
    db.rollback()
    return PapersOut(papers=[PaperOut(**p) for p in papers])


@router.post("/{object_id}/steps/{step_id}/voucher/payment",
             response_model=PaymentSetup)
def prepare_voucher_payment(
    object_id: int,
    step_id: int,
    db: Session = DB,
    user: UserProfile = Depends(get_current_user),
):
    """►►► **Eine Zahlung über den offenen Betrag vorbereiten** – für UNSERE Karte. ◄◄◄

    Kein Verb am Beleg, weil sie **nichts** an ihm ändert: sie erzeugt eine Absicht beim
    Zahlungsdienst und gibt zurück, was das Formular im Browser braucht. Gebucht wird
    erst, wenn das Geld wirklich da ist – und das meldet der Webhook, nicht der Browser
    des Zahlenden. Das Verb steht trotzdem in ``can``: «was darf ich hier tun» ist EINE
    Frage, und dieselbe Liste ist auch hier das **Tor**.

    **Auch für die Gegenpartei offen** – das ist der Sinn: der Kunde bezahlt bei uns,
    nicht auf einer fremden Seite.
    """
    order = orders_svc.get(db, object_id)
    _step, row = _voucher_step(db, order, step_id, user)
    return PaymentSetup(**stripe_pay.prepare(db, row=row, order=order, viewer=user))


@router.post("/{object_id}/steps/{step_id}/voucher/refund",
             response_model=OrderResponse)
def refund_voucher_payment(
    object_id: int,
    step_id: int,
    body: VoucherUpdate,
    db: Session = DB,
    user: UserProfile = Depends(require_employee),
):
    """►►► **Geld zurück — über den Dienst, der es eingezogen hat.** ◄◄◄

    Bar und per Überweisung ist die Erstattung eine gewöhnliche negative Zahlung (die es
    längst gibt); eine **Karte** erstattet der Dienst, der sie belastet hat. **Gebucht
    wird auch hier nicht hier** – der Webhook schreibt die negative Zeile.

    **Personal-only**: eine Erstattung ist unsere Aussage über unser Konto.
    """
    order = orders_svc.get(db, object_id)
    _step, row = _voucher_step(db, order, step_id, user)
    stripe_pay.refund(db, row=row, entry_id=body.entry, amount=body.amount, viewer=user)
    # Gebucht wird erst vom Webhook – **wer** die Erstattung ausgelöst hat, steht nur hier.
    log.event(db, "voucher.refund_requested", order.object_id,
              {"entry": body.entry, "amount": body.amount, "step": step_id},
              table="vouchers", row=row.id)
    db.flush()
    return view.response(db, order, viewer=user)


@router.get("/{object_id}/steps/{step_id}/voucher/transfer",
            response_model=TransferInfo)
def voucher_transfer_details(
    object_id: int,
    step_id: int,
    db: Session = DB,
    user: UserProfile = Depends(get_current_user),
):
    """**Wie man diese Rechnung überweist** – Bankverbindung und QR-Rechnung.

    Eine **Auskunft**, keine Buchung: sie darf jeder sehen, der den Beleg sieht – der
    Zahlende zuerst. Nur an einer Rechnung, deren Geld zu uns kommt (``transfer_info``).
    **Erst auf Klick**: der Code ist ein paar Kilobyte SVG.
    """
    order = orders_svc.get(db, object_id)
    _step, row = _voucher_step(db, order, step_id, user)
    return TransferInfo(**voucher_money.transfer_info(db, row))


@router.get("/{object_id}/steps/{step_id}/voucher/correctable",
            response_model=list[VoucherCorrectable])
def voucher_correctable(
    object_id: int,
    step_id: int,
    search: str = "",
    db: Session = DB,
    user: UserProfile = Depends(require_employee),
):
    """►►► **Welche Rechnung mindert dieser Beleg?** – sie darf in einem anderen Auftrag
    stehen (``voucher_view.correctable``). ◄◄◄

    Gesucht, nicht mitgeliefert: ``search`` ist ein Teil der Rechnungsnummer. **Personal
    only** – es ist eine Liste fremder Belege desselben Partners.
    """
    order = orders_svc.get(db, object_id)
    step, row = _voucher_step(db, order, step_id, user)
    return [VoucherCorrectable(**r)
            for r in voucher_view.correctable(db, row, step, search=search)]
