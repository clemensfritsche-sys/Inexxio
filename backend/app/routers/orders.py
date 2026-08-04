from decimal import Decimal
from typing import NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, OrderLine, UserProfile
from ..schemas.diagnostics import OrderDiagnostics
from ..schemas.disposal import ScrapUpdate
from ..schemas.document import DocumentUpdate, SignerSubstitution, SignoffAction
from ..schemas.inspection import InspectionUpdate
from ..schemas.movement import MovementUpdate
from ..schemas.shipment import ShipmentBuyRequest, ShipmentQuoteRequest, ShipmentUpdate
from ..schemas.order import (
    OrderCoverStock, OrderCreate, OrderLineCreate, OrderLinePins, OrderResponse,
    OrderSummary, OrderUpdate,
)
from ..schemas.purchase_order import PurchaseOrderUpdate
from ..schemas.resource import ResourceUpdate
from ..schemas.sale import SaleUpdate
from ..services import deactivation, deviation, diagnostics, inventory, order_lines as order_lines_svc, process, processes as processes_svc, recovery, refund as refund_svc, sale as sale_svc, shares, subject
from ..services.admin import log_audit
from ..services.document import (
    act_on_signoff, get_signoff, record_document, substitute_signer, withdraw_issuance,
)
from ..services.inspection import record_inspection
from ..services.lifecycle import ensure_mutable, ensure_version
from ..services import logistics
from ..services.movement import record_movement
from ..services.scrap import record_block, record_scrap
from ..services.orders import release_order, to_order_response, to_order_summaries, visible_orders
from ..services.purchase import apply_update_bulk as apply_purchase_update_bulk, instantiate_for_order as instantiate_purchase
from ..services.quantity import qty_sum, to_qty
from ..services.reservation import claim, free_qty, release as release_reservation, reserved_for
from ..services.resource import record_resource

router = APIRouter(prefix="/api/v1/erp/orders", tags=["orders"])


def _get_staff_order(db: Session, object_id: int) -> Order:
    order = (
        db.query(Order)
        .filter(Order.object_id == object_id, Order.is_active == True)
        .first()
    )
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    return order


def _validate_article(db: Session, article_id: int | None) -> None:
    """Im Auftrag dürfen nur freigegebene Artikel referenziert werden."""
    if article_id is None:
        return
    art = db.query(Article).filter(Article.id == article_id, Article.is_active == True).first()
    if not art:
        raise HTTPException(400, detail="Artikel nicht gefunden")
    if art.status != "released":
        raise HTTPException(400, detail="Nur freigegebene Artikel können in einem Auftrag referenziert werden")


def _assert_quantity_serialization(db: Session, article_id: int | None, quantity) -> None:
    """Einzelteil-Artikel (``serialization='unit'``) dürfen nur GANZE Stück tragen – 2.5
    Schrauben gibt es nicht (jede Instanz ist ein Stück). Chargen (``batch``) dürfen
    Bruchmengen tragen (2.5 kg, 0.75 m²). Die Prüfung braucht den Artikel, darum hier im
    Router statt im Schema."""
    from ..services.quantity import is_whole
    if article_id is None or quantity is None:
        return
    art = db.query(Article).filter(Article.id == article_id).first()
    if art and art.serialization == "unit" and not is_whole(quantity):
        raise HTTPException(
            400,
            detail=f"«{art.name}» wird als Einzelteil geführt – die Menge muss eine ganze Zahl sein "
                   "(Bruchmengen nur bei Chargen-Artikeln, z. B. kg/m²/l).")


def _resolve_picks(db: Session, order: Order, picks: list) -> tuple[list[Instance], dict[int, Decimal], dict[int, int]]:
    """Die gewählten **Anteile** auflösen: Instanzen, beanspruchte Menge je Instanz und –
    das Neue – **wem** der Anteil weggenommen wird.

    Eine Instanz ist eine Menge, und ihre Menge ist immer vollständig aufgeteilt: jeder
    Anteil gehört genau einem Auftrag oder ist frei. Wer auswählt, klickt darum eine
    **Zeile** an (Instanz · Menge · Halter) – und damit ist auch beantwortet, wer verliert.
    Ohne diese Angabe müsste die Freigabe raten, sobald eine Charge mehrere Ansprüche trägt.

    **Jede aktive Instanz ist wählbar** – was daraus folgt, sagt ``subject.classify_pick``:
    frei am Lager → normaler Auftrag · verkauft → Retoure · gebunden → **Abweichung**.

    Liefert ``(instanzen, {objektnr: menge}, {objektnr: quell_auftrag_db_id})``; ein Anteil
    ohne Quelle war frei und taucht in der dritten Map nicht auf."""
    # Kein Vorab-Flag mehr, das entscheidet, ob die Bestands-Prüfungen greifen: damit wäre
    # die Art des Auftrags eine *Voraussetzung* der Auswahl statt ihre *Folge*. EIN Weg:
    # Anteile wählen – das Tag ergibt sich.
    insts: list[Instance] = []
    wanted: dict[int, Decimal] = {}
    sources: dict[int, int] = {}
    for pick in picks:
        oid = pick.instance_object_id
        i = db.query(Instance).filter(Instance.object_id == oid, Instance.is_active == True).first()
        if not i:
            raise HTTPException(400, detail=f"Instanz {oid} nicht gefunden")
        if order.article_id and i.article_id != order.article_id:
            raise HTTPException(400, detail="Es sind nur Instanzen desselben Artikels wählbar")
        if (i.disposition or "") == "scrapped":
            raise HTTPException(400, detail=f"Instanz {oid} ist verschrottet – daran ist nichts mehr zu tun")
        want = to_qty(i.quantity) if pick.quantity is None else to_qty(pick.quantity)
        if want <= 0:
            raise HTTPException(400, detail=f"Menge für Instanz {oid} muss grösser als 0 sein")
        if want > to_qty(i.quantity):
            raise HTTPException(
                400, detail=f"Instanz {oid} hat nur {i.quantity} – mehr lässt sich nicht wählen")
        # **Jeder Anteil bekommt seinen Halter – auch der freie** (``None``). Der Eintrag
        # steht darum IMMER; genannt hat Vorrang, sonst wird er abgeleitet:
        #
        #   der Anteil ist **frei** (``subject.is_bound`` sagt nein) → niemand verliert etwas
        #   sonst                                                    → der erste Halter
        #
        # Die Ableitung ist der Rückfall für alles, was (noch) keine Zeile anklickt – die
        # systemseitige Abweichung ebenso wie ein Aufruf ohne Angabe. Genannt wird es dort,
        # wo es mehrdeutig ist: bei einer Charge, an der mehrere Aufträge hängen.
        src = pick.from_order_object_id
        if src is not None:
            holder = db.query(Order).filter(Order.object_id == src, Order.is_active == True).first()
            if not holder:
                raise HTTPException(400, detail=f"Auftrag {src} nicht gefunden")
            # «Halten» heisst dasselbe wie überall (``subject.holding_orders``): einen
            # **Anspruch** haben, es als Subjekt gebunden haben ODER es selbst **erzeugt**
            # haben. Der dritte Weg ist der eines Erzeugungsauftrags – dort steht nichts in
            # der Reservierungs-Map, das Stück gehört ihm trotzdem.
            if holder.id not in {h.id for h in subject.holding_orders(db, i)}:
                raise HTTPException(
                    409, detail=f"Auftrag {src} hält an Instanz {oid} nichts (mehr) – bitte neu auswählen")
            holder_id = holder.id
        elif not subject.is_bound(order, i, want):
            holder_id = None                                    # freier Anteil
        else:
            # Ohne Angabe trifft es den **gewöhnlichen** Auftrag, nicht eine laufende
            # Abweichung: deren Anteil ist genau das, worauf man ausdrücklich zeigen muss.
            others = subject.holding_orders(db, i, exclude_id=order.id)
            plain = [h for h in others if not subject.is_fixed_subject(h)]
            holder_id = (plain or others)[0].id if others else None
        # **Mehrere Anteile DERSELBEN Instanz sind EIN Anspruch.** Eine Charge à 6, an der
        # zwei Aufträge hängen, erscheint in der Auswahl als zwei Zeilen – beide dürfen
        # angeklickt werden. Beide Mengen zählen dann zusammen; vorher überschrieb die zweite
        # Zeile die erste **still** (aus «3 von A und 2 von B» wurde «2 von B»): der Auftrag
        # war plötzlich kleiner und A wurde nie gefragt.
        if oid in wanted:
            wanted[oid] += want
            # Genannt bleibt der ERSTE Halter – er hat den Vorrang bei der Durchsetzung
            # (``shares.losses``); den Rest verteilt sie nach ihrer Rangfolge weiter.
            if sources.get(oid) is None:
                sources[oid] = holder_id
            continue
        sources[oid] = holder_id
        insts.append(i)
        wanted[oid] = want
    for oid, want in wanted.items():
        i = next(x for x in insts if x.object_id == oid)
        if want > to_qty(i.quantity):
            raise HTTPException(
                400, detail=f"Instanz {oid} hat nur {i.quantity} – mehr lässt sich nicht wählen")
    return insts, wanted, sources


def _clear_derived_marker(order: Order) -> None:
    """Das aus der Auswahl **abgeleitete** Tag wieder aufheben.

    Abweichung und Retoure sind keine Eigenschaften, die man setzt, sondern Folgen der
    Auswahl – also müssen sie auch wieder verschwinden, wenn die Auswahl sich ändert. Wer
    eine gebundene Instanz gegen eine freie tauscht, hat danach einen gewöhnlichen Auftrag.
    Vorher galt das nur für die Retoure; das Abweichungs-Tag blieb kleben (Praxis-Durchlauf
    zu Testnotiz #371). Systemseitige Gründe (Nachschub/Bereitstellung) bleiben unberührt –
    sie stammen nicht aus einer Instanz-Auswahl."""
    if order.reason in ("return", "deviation"):
        order.reason = None
        order.parent_order_id = None
        order.origin_step_id = None


def _make_deviation(db: Session, order: Order, insts: list[Instance],
                    wanted: dict[int, Decimal]) -> None:
    """Die Auswahl greift auf **gebundene** Instanzen zu – damit trägt dieser Auftrag das
    Tag «Abweichung». Mehr passiert hier nicht.

    Zwei Dinge werden **abgeleitet**, nicht eingegeben:

    * **Das Tag** ``reason='deviation'`` – siehe ``subject.classify_pick``.
    * **Der Eltern-Auftrag** ist der, der das Stück gerade in der Hand hat
      (``subject.holding_order``). Läuft keiner mehr (späte Reklamation an fertiger Ware),
      steht die Abweichung allein – das ist erlaubt und braucht keinen Eltern.
    * **Die Stelle im Ablauf** ist der Schritt, an dem der Eltern gerade steht
      (``deviation.interrupted_step_id``) – dieselbe eine Regel wie bei der systemseitigen
      Anlage. Ohne sie stand die Abweichung im Fluss ganz vorne, also **vor** einem längst
      abgeschlossenen Schritt (Testnotiz #377).

    **Und der Eltern merkt davon noch nichts** (Testnotiz #370). Ein Entwurf nimmt niemandem
    etwas weg: die Auswahl wird nur **vorgemerkt** (``reservation.claim``, ohne fremde
    Ansprüche anzutasten). Die Frage «was geschieht mit dem laufenden Auftrag?» stellt sich
    erst bei der **Freigabe** – bis dahin lassen sich Artikel, Menge und Instanzen ja noch
    ändern, und eine jetzt getroffene Entscheidung könnte gleich wieder falsch sein."""
    order.reason = "deviation"
    # Menge = das, worauf die Abweichung tatsächlich wirkt (Summe der beanspruchten
    # Teilmengen) – bei einem Stück aus einer 500er-Charge also 1, nicht 500.
    if order.article_id:
        order.quantity = qty_sum(wanted.values())
    holders = shares.affected(db, order, insts, wanted)
    # Eltern = wer das Stück hält. Mehrere Halter → der erste (die übrigen stehen über die
    # Instanz-Klammer ohnehin im Bild, ``deviation.deviations_touching``).
    parent = holders[0].order if holders else None
    order.parent_order_id = parent.object_id if parent else None
    order.origin_step_id = deviation.interrupted_step_id(db, parent) if parent else None


def _answer_for(answers: dict[str, str] | None, holder: Order) -> str | None:
    """Die Antwort für GENAU DIESEN Halter – die eine Auflösung, die Prüfung und Anwendung
    teilen. Der Schlüssel ist seine Objektnummer (JSON-Schlüssel sind Strings)."""
    return (answers or {}).get(str(holder.object_id))


def _assert_answered(db: Session, answers: dict[str, str] | None,
                     holders: list[shares.Affected]) -> None:
    """Ohne Entscheid geht es nicht weiter – gefragt wird bei der **Freigabe**.

    Vorher stand die Frage schon beim Auswählen. Das war zu früh (Testnotiz #370): danach
    definiert man den Auftrag ja erst fertig – Artikel, Menge und Instanzen können sich
    noch ändern, und die Entscheidung über den anderen Auftrag wäre womöglich gleich wieder
    falsch. Mit der Freigabe steht die Auswahl fest, und im selben Moment wird der Zugriff
    scharf (``reservation.enforce``) – erst dort verliert der andere Auftrag wirklich etwas.

    **JEDER Betroffene braucht seine eigene Antwort.** Wer aus zwei laufenden Aufträgen
    Stücke nimmt, kann den einen warten lassen und den anderen reduzieren wollen – eine
    Antwort über alle wäre eine Entscheidung, die so niemand getroffen hat. Fehlt auch nur
    eine, wird die Frage für ALLE gestellt (die Oberfläche zeigt sie zusammen)."""
    open_ = [h for h in holders if _answer_for(answers, h.order) is None]
    if not open_:
        return
    raise HTTPException(
        409,
        detail={
            "code": "shortfall_decision_required",
            # Der Text bleibt lesbar (Log, ältere Clients); die Liste ist das, womit die
            # Oberfläche die Frage stellt – sie kennt den Entwurf nicht mehr als Datensatz
            # (Notiz #386), also muss der Fehler selbst sagen, wen es trifft.
            "message": "Diese Instanzen sind in Arbeit – der laufende Auftrag "
                       + ", ".join(str(h.order.object_id) for h in open_)
                       + " verliert sie dadurch. Bitte entscheiden, wie es dort weitergeht: "
                         "warten · ersetzen · ohne Ersatz weiter.",
            "affects": [a.model_dump() for a in shares.affected_rows(db, holders)],
        },
    )


def _enforce_claims(db: Session, order: Order, answers: dict[str, str] | None,
                    actor_id: int | None) -> list[shares.Affected]:
    """Die vorgemerkte Auswahl **scharf machen** – der Moment der Freigabe.

    Bis hierhin hat der Entwurf nur beansprucht (``reservation.claim``), ohne jemandem etwas
    wegzunehmen. Gleich setzt sich der Anspruch durch (``reservation.enforce``, in der
    Freigabe selbst – damit auch die systemseitig angelegte Abweichung scharf wird): wer
    dadurch zu viel hätte, verliert entsprechend, und **genau daraus** entsteht seine
    Unterdeckung. Hier wird nur **gefragt**, solange sich noch etwas ändern liesse.

    Vorher stand die Frage schon beim Auswählen; das war zu früh, weil sich Artikel, Menge
    und Instanzen danach noch ändern konnten (Testnotiz #370). Liefert die betroffenen
    laufenden Aufträge, damit die gewählte Antwort nach der Freigabe auf sie wirken kann."""
    picked = subject.chosen_subjects(db, order)
    if not picked:
        return []
    holders = shares.affected(db, order, picked)
    # **Gefragt wird JEDER, dem etwas weggenommen wird** – auch eine Abweichung (Notiz #397).
    # Vorher war ein festes Subjekt ausgenommen: es schrumpfte lautlos mit und wurde
    # abgebrochen, wenn nichts blieb. Damit gab es zwei Logiken für dieselbe Lage, und die
    # Abweichung an einer Abweichung endete ohne jede Rückfrage im Abbruch der ersten. Jetzt
    # ist es EINE Frage mit denselben drei Antworten – wer keine Fehlmenge hat, taucht in
    # ``holders`` ohnehin nicht auf.
    if holders:
        _assert_answered(db, answers, holders)
    return holders


def _apply_shortfall_answer(db: Session, holders: list[shares.Affected],
                            answers: dict[str, str] | None,
                            actor_id: int | None, into: Order | None = None) -> None:
    """Die gewählte Antwort auf die Unterdeckung der Eltern anwenden – dieselben drei Wege
    wie am laufenden Auftrag (``recovery``), nur früher gestellt.

    ``wait`` tut nichts: die Fehlmenge bleibt offen und der Eltern wird nicht fertig, bis
    sie gedeckt ist – das IST die Pause, nur ohne eigenen Mechanismus.

    ``accept`` («Auftragsmenge reduzieren») ist zugleich der **Abbruch**, wenn dem Eltern
    ALLES entzogen wurde: ``into`` ist dann der Auftrag, der ihn fortführt. Damit braucht der
    reale Fall «Auftrag verwerfen und neu aufsetzen» keinen eigenen Knopf mehr (Notiz #366).

    **Je Halter seine eigene Antwort**: der eine wartet, der andere reduziert – im Fluss ist
    das schlicht die Rückgabe-Linie, die zu ihm führt oder eben nicht.

    **Und sie gilt für JEDEN Betroffenen** (Notiz #397) – auch für ein festes Subjekt
    (Abweichung/Retoure/Bereitstellung). Dessen «Soll» sind die Stücke, die es behandeln
    sollte; nimmt man ihm eines weg, fehlt ihm genau das (``process._held_amounts``). Bleibt
    ihm gar nichts, IST «Menge reduzieren» sein Abbruch – dieselbe Mechanik wie beim Eltern
    (Notiz #366), nur eben **entschieden** statt automatisch. Der frühere Sonderweg
    (``recovery.retire_if_subjectless``) ist damit entfallen: eine Regel weniger."""
    from ..services import recovery
    for a in holders:
        answer = _answer_for(answers, a.order)
        if answer == "replace":
            recovery.cover_shortfall(db, a.order, actor_id)
        elif answer == "accept":
            recovery.confirm_quantity(db, a.order, actor_id, into=into)


def _set_chosen_instances(db: Session, order: Order, picks: list) -> None:
    """Die gewählten **Anteile** eines Entwurfs neu setzen: bisherige lösen, neue prüfen und
    beanspruchen.

    **Ein Anteil ist eine Menge mit einem Namen darauf**: WELCHE Instanz, WIE VIEL davon und
    WEM sie gerade gehört. Von einer Charge à 500 lässt sich genau eine Schraube wählen –
    und ab jetzt auch, aus wessen Anteil. Damit tut die Hand-Auswahl exakt das, was die
    FIFO-Allokation längst tut (mengengenau reservieren); der Unterschied ist nur, wer die
    Instanz bestimmt.

    **Die Auswahl bestimmt die ART des Auftrags** (``subject.classify_pick``) – ein Tag, kein
    zweiter Weg: verkaufte Anteile → **Retoure/Erstattung** · gebundene (in Arbeit,
    reserviert, gesperrt) → **Abweichung** · freie → gewöhnlicher Auftrag. Frei, gebunden und
    verkauft lassen sich nicht mischen: ein Auftrag beantwortet EINE Frage – *woher kommt das
    Material?*

    **Der Eltern merkt hier noch nichts.** Die Auswahl wird nur vorgemerkt; ob und wie ein
    laufender Auftrag dadurch etwas verliert, entscheidet sich erst bei der **Freigabe**
    (``_enforce_claims``, Testnotiz #370)."""
    # Die bisherige Auswahl vollständig lösen – Bindung UND Anspruch. Ohne das bliebe ein
    # abgewählter Anspruch als Reservierung stehen und hielte fremden Bestand fest.
    for prev in (
        db.query(Instance)
        .filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
        .all()
    ):
        prev.subject_of_order_id = None
        release_reservation(prev, order.id)
    order.pick_sources = None
    if not picks:
        _clear_derived_marker(order)
        return
    insts, wanted, sources = _resolve_picks(db, order, picks)
    order.pick_sources = {str(k): v for k, v in sources.items()} or None   # v=None ⇒ freier Anteil
    kind = subject.classify_pick(order, insts, wanted, sources)

    if kind == subject.PICK_RETURN:
        if any((i.disposition or "") != "sold" for i in insts):
            raise HTTPException(
                400, detail="Bitte entweder verkaufte Instanzen (Retoure/Erstattung) ODER Lager-Instanzen "
                            "wählen – nicht gemischt")
        # Retoure: Original-Verkauf ableiten (Grundlage der Gutschrift) + Auftrag markieren.
        parent = refund_svc.original_sale_order(db, insts)
        order.reason = "return"
        order.parent_order_id = parent.object_id
        art_ids = {i.article_id for i in insts}
        if len(art_ids) == 1:
            order.article_id = next(iter(art_ids))
            # Summe der Mengen, nicht die Zahl der Zeilen: eine retournierte Charge à 5 Stk
            # ist EINE Instanz und FÜNF Stück.
            order.quantity = qty_sum(wanted.values())
    elif kind == subject.PICK_DEVIATION:
        # **Kein Mischmasch** (Testnotiz #355): freie und gebundene Stücke in EINEM Auftrag
        # wären zwei Vorgänge in einem – der freie Teil wäre ein gewöhnlicher Bedarf, der
        # gebundene nimmt einem laufenden Auftrag etwas weg. Dieselbe Regel und dieselbe
        # Form wie beim Verkauft/Lager-Mix darüber; das Frontend blendet die jeweils andere
        # Sorte aus, sobald die erste gewählt ist.
        if any(not subject.is_bound(order, i, wanted[i.object_id], sources.get(i.object_id))
               for i in insts):
            raise HTTPException(
                400, detail="Bitte entweder gebundene Instanzen (Abweichung) ODER freie Lager-Instanzen "
                            "wählen – nicht gemischt")
        _make_deviation(db, order, insts, wanted)
    else:
        _clear_derived_marker(order)
        pinned_qty = qty_sum(wanted.values())
        if order.quantity and pinned_qty > order.quantity:
            raise HTTPException(
                400, detail=f"Es sind mehr Instanzen fixiert ({pinned_qty}) als die Auftragsmenge ({order.quantity})")

    for i in insts:
        # Bindung **und** Anspruch: die Objektnummer sagt WELCHE Instanz, die Menge WIE VIEL
        # davon – dieselbe Map, in die auch die FIFO-Allokation schreibt. Beansprucht die
        # Auswahl mehr, als noch frei ist, kürzt ``claim`` den fremden Anspruch: genau so
        # entsteht die Unterdeckung beim Auftrag, dem das Stück entzogen wird.
        i.subject_of_order_id = order.id
        claim(i, order.id, wanted[i.object_id])


@router.get("", response_model=list[OrderSummary])
async def list_orders(
    limit: int = Query(0, ge=0, le=1000, description="0 = keine Begrenzung; sonst Seitengröße"),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Schlanker Auftrags-Feed (ohne Prozess-Embeds). Das Detail kommt aus
    ``GET /orders/{id}``. Optional server-seitig paginierbar (limit/offset)."""
    q = visible_orders(db, user).order_by(Order.object_id.desc())
    if limit:
        q = q.offset(offset).limit(limit)
    return to_order_summaries(db, q.all())


def _pin_line_instances(db: Session, order: Order, article_id: int, quantity, picks: list) -> None:
    """Gewählte **Anteile** EINER Position eines Mehrpositionen-Auftrags vormerken – wie
    ``_set_chosen_instances`` für den Einzel-Artikel-Auftrag, nur gegen die Menge/den
    Artikel DIESER Position statt des ganzen Auftrags geprüft (mehrere Artikel können
    unter demselben Sammel-Auftrag je eigene Anteile tragen). Löst zuerst die bisherige
    Auswahl dieser Position (idempotent, wie beim Einzel-Artikel-Auftrag)."""
    for prev in db.query(Instance).filter(
        Instance.subject_of_order_id == order.id, Instance.article_id == article_id,
        Instance.is_active == True,
    ).all():
        prev.subject_of_order_id = None
        release_reservation(prev, order.id)
    if not picks:
        return
    insts, wanted, sources = _resolve_picks(db, order, picks)
    for i in insts:
        if i.article_id != article_id:
            raise HTTPException(400, detail="Es sind nur Instanzen desselben Artikels wie die Position wählbar")
        if not inventory.is_in_stock(i):
            raise HTTPException(400, detail=f"Instanz {i.object_id} ist nicht am Lager verfügbar")
        if free_qty(i) + reserved_for(i, order.id) < wanted[i.object_id]:
            raise HTTPException(409, detail=f"Instanz {i.object_id} ist bereits für einen anderen Auftrag reserviert")
    pinned_qty = qty_sum(wanted.values())
    if pinned_qty > to_qty(quantity):
        raise HTTPException(
            400, detail=f"Es sind mehr Instanzen fixiert ({pinned_qty}) als die Positionsmenge ({quantity})")
    order.pick_sources = {**(order.pick_sources or {}), **{str(k): v for k, v in sources.items()}} or None
    for i in insts:
        i.subject_of_order_id = order.id
        claim(i, order.id, wanted[i.object_id])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """**Auftrag erteilen** – anlegen und freigeben in EINEM Aufruf (Testnotiz #386).

    Alles, was der Entwurf im Browser gesammelt hat, kommt hier zusammen an: Artikel +
    Menge, weitere Positionen, der auftragseigene Ablauf, die Instanz-Auswahl und – falls
    die Auswahl einem laufenden Auftrag etwas wegnimmt – die Antwort darauf. Erst danach
    bekommt der Auftrag seine **Objektnummer** (in ``release_order``).

    Scheitert irgendetwas, wird die Transaktion verworfen: kein halber Auftrag, keine
    verbrauchte Nummer. Ein Entwurf existiert damit **nie** in der Datenbank – «freigegeben
    oder es hat ihn nie gegeben»."""
    order = Order(
        status="draft",
        desired_delivery_date=data.desired_delivery_date,
        recurrence_active=bool(data.recurrence_active),
        recurrence_interval_days=data.recurrence_interval_days,
        recurrence_lead_time_days=data.recurrence_lead_time_days or 0,
        recurrence_anchor=data.recurrence_anchor,
    )
    # Anker ist IMMER der Artikel + Menge. Was damit geschieht (Erzeugung vs. Operation
    # am Bestand, FIFO/fixiert) ergibt sich aus dem **Ablauf**, der mitgeliefert wird –
    # nicht aus der Anlage.
    _validate_article(db, data.article_id)             # nur freigegebene Artikel
    _assert_quantity_serialization(db, data.article_id, data.quantity)  # unit → ganze Zahl
    order.article_id = data.article_id
    order.quantity = data.quantity
    db.add(order)
    db.flush()
    # **Vorauswahl statt Fixierung** (Testnotiz #371): kommt der Auftrag über den Abkürzungs-
    # Knopf einer Instanz, ist sie hier schon eingetragen – wie von Hand gewählt. Ob daraus
    # eine Abweichung wird, sagt die Auswahl (``subject.classify_pick``), nicht der Einstieg.
    # Sie wird gesetzt, solange der Artikel noch der **Anker** ist: die erste zusätzliche
    # Position wandelt ihn gleich in Position 0 um (Bindung/Anspruch bleiben unberührt).
    if data.picks:
        _set_chosen_instances(db, order, data.picks)
    # Weitere Positionen (Mehrpositionen-Auftrag) – derselbe Dienst wie der Einzel-Endpunkt,
    # jede Position mitsamt ihrer eigenen Instanz-Auswahl.
    for line in data.lines or []:
        _add_line(db, order, line, current_user.id)
    # Der auftragseigene Ablauf – über denselben EINEN Weg wie der Schritt-Editor
    # (``article_process._create``): gleiche Prüfungen, gleiche Normalisierung.
    if data.steps:
        from .article_process import _create as create_step, _order_owner_for
        owner = _order_owner_for(order)
        for step in data.steps:
            create_step(db, owner, step, current_user, commit=False)
    _do_release(db, order, data.shortfall_responses, current_user.id)
    # **Ein Vorgang, EIN Protokoll-Eintrag** (Testnotizen #507/#517): «Auftrag freigegeben»
    # schreibt ``release_order`` selbst – und zwar als ERSTES, vor allem, was daraus folgt.
    # «draft → released» war zusätzlich der Fussabdruck einer INTERNEN Zwischenstufe: ein
    # Auftrag entsteht als Ganzes (#386), er war nie ein gespeicherter Entwurf.
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/lines", response_model=OrderResponse, status_code=201)
async def add_order_line(
    object_id: int,
    data: OrderLineCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Eine weitere Position zu einem **Entwurf** hinzufügen – jederzeit möglich, auch
    nachdem der Auftrag schon gespeichert wurde (nicht nur bei der Anlage). Macht den
    Auftrag (falls noch nicht) zu einem **Mehrpositionen**-Auftrag: «Herstellen» scheidet
    dann aus (``subject.subject_kind`` erzwingt ``stock``); Ablauf/Ziel-Karten bleiben
    sonst unverändert (nur «Aus Lager»/«Instanz wählen», jetzt über mehrere Artikel)."""
    order = _get_staff_order(db, object_id)
    if order.status != "draft":
        raise HTTPException(400, detail="Weitere Positionen sind nur im Entwurf möglich")
    _add_line(db, order, data, current_user.id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


def _add_line(db: Session, order: Order, data: OrderLineCreate, actor_id: int | None) -> None:
    """**Eine weitere Position** – die EINE Implementierung, geteilt von der Auftrags-Anlage
    (alle Positionen auf einmal) und dem Einzel-Endpunkt. Committet NICHT."""
    _validate_article(db, data.article_id)
    _assert_quantity_serialization(db, data.article_id, data.quantity)  # unit → ganze Zahl
    existing_lines = order_lines_svc.lines_for(db, order)
    # FIX: Doppelte Positionen desselben Artikels zerlegen die gesamte Mehrpositionen-Logik,
    # die je Auftrag nach ``article_id`` schlüsselt: die FIFO-Allokation zählte die Instanzen
    # der ersten Position bei der zweiten als «gepinnt» mit (Unter-Reservierung), und
    # Beschaffung/Verkauf legen je Artikel nur EINE Fachzeile an – die zweite Position wäre
    # still weder bestellt noch verrechnet worden. Menge stattdessen an der Position anpassen.
    existing_article_ids = {l.article_id for l in existing_lines} | (
        {order.article_id} if order.article_id else set())
    if data.article_id in existing_article_ids:
        raise HTTPException(
            400, detail="Dieser Artikel ist bereits eine Position – bitte dort die Menge anpassen")

    # Die Abo-Mischungsregel betrifft nur den VERKAUF (Stripe: ein Checkout ist entweder
    # Einmalkauf oder Abo) – sie gehört daher ans Hinzufügen des Sales-Prozessschritts
    # (``article_process.py: _create``), NICHT hierher: eine weitere Position anzulegen,
    # die z. B. nur bewegt oder geprüft werden soll, hat mit Verkaufspreisen nichts zu tun
    # und darf nicht blockiert werden. Existiert für diesen Auftrag aber BEREITS ein
    # Verkaufsschritt, würde die neue Position ihn sonst nachträglich unbemerkt kaputt
    # machen – dagegen sichert dieser Check gezielt ab.
    if process.has_step(db, order, "sale"):
        sale_svc.assert_sale_compatible(db, existing_article_ids | {data.article_id})

    if order.article_id is not None:
        # Erste zusätzliche Position: den bisherigen Einzel-Artikel-Anker in eine
        # gewöhnliche Position umwandeln (die Instanzen-/Reservierungs-Historie bleibt
        # unangetastet – nur die Bedarfs-Darstellung wechselt).
        db.add(OrderLine(order_id=order.id, article_id=order.article_id,
                         quantity=order.quantity, position=0))
        order.article_id = None
        order.quantity = None
        db.flush()
        existing_lines = order_lines_svc.lines_for(db, order)
    next_pos = (max((l.position for l in existing_lines), default=-1)) + 1
    line = OrderLine(order_id=order.id, article_id=data.article_id, quantity=data.quantity, position=next_pos)
    db.add(line)
    db.flush()
    new_art = db.query(Article).filter(Article.id == data.article_id).first()
    log_audit(db, "orders", None,
              f"Position hinzugefügt ({data.quantity}× Artikel {new_art.object_id if new_art else data.article_id})",
              actor_id, object_id=order.object_id)
    # Bringt die Position ihre Auswahl mit («Instanz wählen» statt FIFO), gilt derselbe
    # Weg wie beim nachträglichen ``PATCH .../lines/{id}`` – eine Implementierung.
    if data.picks:
        _pin_line_instances(db, order, data.article_id, data.quantity, data.picks)


@router.delete("/{object_id}/lines/{line_id}", response_model=OrderResponse)
async def remove_order_line(
    object_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Eine Position eines Mehrpositionen-Auftrags entfernen (nur im Entwurf)."""
    order = _get_staff_order(db, object_id)
    if order.status != "draft":
        raise HTTPException(400, detail="Positionen lassen sich nur im Entwurf entfernen")
    line = db.query(OrderLine).filter(
        OrderLine.id == line_id, OrderLine.order_id == order.id, OrderLine.is_active == True).first()
    if not line:
        raise HTTPException(404, detail="Position nicht gefunden")
    remaining = order_lines_svc.lines_for(db, order)
    if len(remaining) <= 1:
        raise HTTPException(400, detail="Die letzte Position kann nicht entfernt werden – bitte den Auftrag abbrechen")
    for inst in db.query(Instance).filter(
        Instance.subject_of_order_id == order.id, Instance.article_id == line.article_id,
        Instance.is_active == True,
    ).all():
        inst.subject_of_order_id = None
    line.is_active = False
    db.flush()
    # Bleibt nur noch EINE Position, wird der Auftrag wieder ein gewöhnlicher Einzel-Artikel-
    # Auftrag (symmetrisch zur ersten Zusatz-Position, die den Anker in eine Position umwandelt):
    # ``article_id``/``quantity`` zurück an den Auftrag, die verbleibende Position auflösen. So
    # aktualisieren sich die Ziel-Karten korrekt (Herstellen wieder möglich, kein `stock`-Zwang).
    left = order_lines_svc.lines_for(db, order)
    if len(left) == 1:
        anchor = left[0]
        order.article_id = anchor.article_id
        order.quantity = anchor.quantity
        anchor.is_active = False   # gepinnte Instanzen bleiben (subject_of_order_id = order.id)
    log_audit(db, "orders", None, "Position entfernt", current_user.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/lines/{line_id}", response_model=OrderResponse)
async def set_order_line_pins(
    object_id: int,
    line_id: int,
    data: OrderLinePins,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Fixierte Instanzen EINER Position setzen (statt FIFO) – «Instanz wählen» je Artikel
    eines Mehrpositionen-Auftrags, analog ``picks`` am Einzel-Artikel-Auftrag."""
    order = _get_staff_order(db, object_id)
    if order.status != "draft":
        raise HTTPException(400, detail="Instanzen lassen sich nur im Entwurf fixieren")
    line = db.query(OrderLine).filter(
        OrderLine.id == line_id, OrderLine.order_id == order.id, OrderLine.is_active == True).first()
    if not line:
        raise HTTPException(404, detail="Position nicht gefunden")
    _pin_line_instances(db, order, line.article_id, line.quantity, data.picks)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


def _ensure_step_facts(db: Session, order: Order, user: UserProfile) -> None:
    """Selbstheilung beim Lesen: fehlende **Beschaffungs-/Verkaufsbelege** eines freigegebenen
    Auftrags idempotent nachziehen, damit die Prozessschritt-Details IMMER erscheinen (kein
    leeres Panel, falls ein Beleg aus irgendeinem Grund nicht bei der Freigabe entstand).
    Nur Personal; nur purchase/sale (diese werden bei der Freigabe instanziiert – die übrigen
    Fachzeilen entstehen erst bei der Ausführung und fehlen legitim)."""
    if order.status != "released" or user.role not in ("admin", "employee"):
        return
    created = instantiate_purchase(db, order, user.id)
    created += sale_svc.instantiate_for_order(db, order, user.id)
    if created:
        db.commit()


@router.get("/{object_id}", response_model=OrderResponse)
async def get_order(
    object_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    order = visible_orders(db, user).filter(Order.object_id == object_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    _ensure_step_facts(db, order, user)   # fehlende Beschaffungs-/Verkaufsbelege nachziehen
    return to_order_response(db, order, viewer=user)


@router.get("/{object_id}/diagnostics", response_model=OrderDiagnostics)
async def get_order_diagnostics(
    object_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """**Systemprotokoll eines Auftrags** – Befund + Chronologie für die Fehlersuche.

    Personal-only und **on demand**: eine Diagnose gehört nicht in jede Auftrags-Antwort
    (sie ist um Grössenordnungen umfangreicher und interessiert nur, wenn etwas nicht
    stimmt). Sie erfindet keine Wahrheit, sondern stellt die drei bestehenden Ströme
    (Audit · Ereignisse · Material-Journal) neben den abgeleiteten Zustand."""
    order = db.query(Order).filter(Order.object_id == object_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    return diagnostics.order_diagnostics(db, order)


def _assert_status_transition(current: str, new: str | None) -> None:
    """Zustandsmaschine des Auftrags-Status – **erlaubt ist nur, was hier steht.**

    Ohne diese Prüfung fiel jeder nicht explizit abgefangene Wechsel in die generische
    ``setattr``-Schleife: ein Entwurf liess sich direkt auf «completed» setzen (ohne Schritte,
    ohne ``completed_at``), und ein abgeschlossener/inaktiver Auftrag auf «draft» zurückholen
    und danach erneut freigeben – die Umgehung von «kein Reaktivieren».

    Manuell erlaubt sind NUR draft→released (Freigabe) und draft/released→inactive (der
    Aufrufer regelt Letzteres über «Abbrechen»); «completed» leitet ausschliesslich das System
    ab (``process.recompute_completion``)."""
    if not new or new == current:
        return
    if new == "released" and current == "inactive":
        raise HTTPException(409, detail="Auftrag kann nicht reaktiviert werden – bitte neuen Auftrag anlegen")
    if new == "completed":
        raise HTTPException(400, detail="«Abgeschlossen» wird vom System abgeleitet, wenn alle Schritte erledigt sind")
    if current in ("completed", "inactive"):
        raise HTTPException(409, detail="Ein abgeschlossener/inaktiver Auftrag ist endgültig – bitte neuen Auftrag anlegen")
    if current == "released" and new == "draft":
        raise HTTPException(409, detail="Ein freigegebener Auftrag kann nicht in den Entwurf zurück – bitte «Abbrechen» verwenden")


def _assert_releasable(db: Session, order: Order) -> None:
    """Die Vorbedingungen der Auftrags-Freigabe – **eine** Stelle, drei Gates.

    Wirft ``HTTPException``; kehrt lautlos zurück, wenn der Auftrag startklar ist."""
    is_multiline = order.article_id is None and bool(order_lines_svc.lines_for(db, order))
    # Eine Abweichung ODER Retoure (Unter-Auftrag) hat ihr Subjekt bereits über fixierte
    # Instanzen (nicht über order_lines) – erbt bei einem Mehrpositionen-Eltern-Auftrag
    # dessen article_id=NULL, OHNE selbst eine Mehrpositionen-Struktur zu sein. Sie braucht
    # daher WEDER article_id/quantity NOCH order_lines zur Freigabe.
    if not is_multiline and not subject.is_fixed_subject(order) and (not order.article_id or not order.quantity):
        raise HTTPException(400, detail="Zur Freigabe sind Artikel und Menge erforderlich")

    # **Jeder Auftrag braucht einen Ablauf** – die Frage ist nur, welchen. Eine **Erzeugung**
    # hat ihn am Artikel (der beschreibt ja, wie das Ding entsteht); alles andere braucht
    # einen **eigenen**. Vorher genügte hier irgendein auflösbarer Schritt, und weil ein
    # Auftrag ohne eigene Schritte auf den Artikel-Prozess zurückfiel, liess sich ein Auftrag
    # mit ausgewählten Instanzen und leerem Ablauf freigeben – er fuhr dann den Artikel-
    # Prozess über fremdes Material (Testnotiz #392).
    if subject.subject_kind(db, order) == "produce":
        # Vorbedingung: der Artikel (Spezifikation + Prozess) muss freigegeben sein.
        art = db.query(Article).filter(Article.id == order.article_id).first()
        if not art or art.status != "released":
            raise HTTPException(
                400, detail="Der Artikel muss freigegeben sein, bevor der Prozess gestartet werden kann")
    elif not processes_svc.order_custom_steps(db, order.id):
        raise HTTPException(400, detail="Bitte zuerst mindestens einen Prozessschritt definieren")

    # Hat der Auftrag Beschaffungs-Schritte, muss je Schritt × betroffenem Artikel eine
    # auflösbare Bezugsquelle vorliegen (Schritt-Quelle ODER Artikel-Default).
    p_steps = [d for d in process.order_step_defs(db, order) if d.step_type == "purchase"]
    if not p_steps:
        return
    from ..services.purchase import has_source
    art_ids = ([order.article_id] if order.article_id
               else [l.article_id for l in order_lines_svc.lines_for(db, order)])
    arts = [db.query(Article).filter(Article.id == aid).first() for aid in art_ids]
    missing = sorted({a.name for step in p_steps for a in arts if a and not has_source(step, a)})
    if missing:
        names = ", ".join(f"«{n}»" for n in missing)
        raise HTTPException(
            400,
            detail=f"Beschaffung unvollständig: für {names} ist keine Bezugsquelle hinterlegt "
                   "(am Beschaffungs-Schritt oder als Artikel-Standard unter Spezifikation → Beschaffung).")


class _PickInputs(NamedTuple):
    """Was zur **Auswahl** gehört, nicht zum Auftrag – darum keine Modellfelder.

    Beide müssen aus dem Payload heraus, bevor die generische ``setattr``-Schleife
    darüberläuft; sonst landeten sie als Attribute auf dem Auftrag."""
    picks: list | None               # gewählte Anteile (Instanz · Menge · Halter)
    answers: dict[str, str] | None   # je Halter die Antwort auf seine Unterdeckung


def _pop_pick_inputs(data: OrderUpdate, payload: dict) -> _PickInputs:
    payload.pop("picks", None)
    return _PickInputs(
        picks=data.picks if "picks" in data.model_fields_set else None,
        answers=payload.pop("shortfall_responses", None),
    )


def _assert_payload(db: Session, order: Order, payload: dict) -> None:
    """Die Feld-Prüfungen einer Auftrags-Änderung – an EINER Stelle."""
    if ("article_id" in payload or "quantity" in payload) and order.article_id is None \
            and order_lines_svc.lines_for(db, order):
        # Ein Mehrpositionen-Auftrag hat seinen Bedarf auf ``order_lines`` – Artikel/Menge
        # nachträglich am Auftrag selbst zu setzen würde ihn inkonsistent (verwaiste
        # Positionen) auf einen Einzel-Artikel-Auftrag umbiegen.
        raise HTTPException(
            400, detail="Bei einem Mehrpositionen-Auftrag sind Artikel/Menge nicht direkt editierbar")
    if "article_id" in payload:
        _validate_article(db, payload["article_id"])
    if "quantity" in payload:
        _assert_quantity_serialization(db, payload.get("article_id", order.article_id), payload["quantity"])
    _assert_status_transition(order.status, payload.get("status"))


def _apply_fields(db: Session, order: Order, payload: dict, actor_id: int | None) -> None:
    """Felder setzen und jede echte Änderung protokollieren."""
    for key, value in payload.items():
        old_val = getattr(order, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "orders", key, new_str, actor_id,
                      object_id=order.object_id, old_value=old_str)
        setattr(order, key, value)


def _do_release(db: Session, order: Order, answers: dict[str, str] | None,
                actor_id: int | None) -> None:
    """Freigabe (draft → released) – stösst den Prozess an und stellt das Subjekt her.
    Anker ist immer Artikel + Menge:

      produce – KEIN eigener Ablauf → der **Artikel-Prozess** läuft, neue Instanzen entstehen.
      stock   – eigener Ablauf → er läuft auf ``quantity`` Instanzen des Artikels
                (FIFO ab Lager, optional durch fixierte Instanzen ergänzt).

    **Erst schreiben lassen, dann lesen** (wie in ``orders.release_order``): das Gate fragt
    den Bestand nach etwas, das dieselbe Anfrage eben erst geschrieben hat – «welche
    Instanzen sind gewählt?» entscheidet über Subjektart UND darüber, ob ein eigener Ablauf
    nötig ist. Ohne den Flush fände es nichts und liesse einen Auftrag mit ausgewählten
    Instanzen und leerem Ablauf durch (Testnotiz #392)."""
    db.flush()
    _assert_releasable(db, order)
    # **Jetzt – und erst jetzt – wird der Zugriff scharf** (Testnotiz #370). Bis hierhin
    # war die Instanz-Auswahl eine Vormerkung, die niemandem etwas wegnahm; mit der
    # Freigabe steht sie fest. Nimmt sie einem LAUFENDEN Auftrag sein Stück weg, will
    # dessen Unterdeckung im selben Zug beantwortet sein – sonst bliebe er ohne
    # Entscheidung hängen.
    holders = _enforce_claims(db, order, answers, actor_id)
    # Einheitliche Freigabe (setzt draft → released selbst): Subjekt herstellen (Fehlmenge ist
    # KEIN Fehler – der Schritt wird «blockiert» und über «Nachschub anlegen» gedeckt),
    # Beschaffung/Verkauf instanziieren, Komponenten reservieren.
    release_order(db, order, actor_id)
    # Die Antwort NACH der Freigabe anwenden: erst dort ist die Fehlmenge des anderen
    # Auftrags real, und «ersetzen»/«Menge reduzieren» rechnen mit dem echten Stand.
    _apply_shortfall_answer(db, holders, answers, actor_id, into=order)


@router.patch("/{object_id}", response_model=OrderResponse)
async def update_order(
    object_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    order = _get_staff_order(db, object_id)
    was_released = order.status == "released"

    payload = data.model_dump(exclude_unset=True)
    ensure_version(order, payload.pop("expected_updated_at", None))
    pick = _pop_pick_inputs(data, payload)
    # Inhalte – inklusive der Wiederkehr-Einstellung – sind NUR im Entwurf änderbar.
    # Nach der Freigabe ist der Auftrag „scharf"; ein einmal freigegebener Auftrag
    # lässt sich nicht mehr nachträglich auf wiederkehrend umstellen (ensure_mutable
    # erlaubt dann nur noch status/is_active).
    ensure_mutable(order.status, payload, "Auftrag")
    if pick.picks is not None:
        if order.status != "draft":
            raise HTTPException(409, detail="Instanzen lassen sich nur im Entwurf ändern")
        _set_chosen_instances(db, order, pick.picks)
    _assert_payload(db, order, payload)

    # Freigabe (draft → released) läuft AUSSCHLIESSLICH über ``release_order`` – dieser Pfad setzt
    # den Status selbst. Den Status hier NICHT vorab über die generische Schleife setzen: sonst ist
    # der Auftrag beim Aufruf bereits „released", ``release_order`` kehrt wegen „nicht mehr draft"
    # sofort zurück und es entsteht KEIN Subjekt – keine Instanzen, keine Objektnummern (stiller
    # Blindgänger). Der Statuswechsel wird nach erfolgreicher Freigabe protokolliert.
    wants_release = payload.get("status") == "released" and not was_released
    if wants_release:
        payload.pop("status")
    _apply_fields(db, order, payload, current_user.id)
    if wants_release:
        _do_release(db, order, pick.answers, current_user.id)

    # Ein freigegebener Auftrag wird NICHT direkt inaktiv gesetzt – der Abbruch läuft über
    # «Abbrechen» (POST /abort), das einen Folgeauftrag erzwingt (keine herrenlosen Teile).
    if order.status == "inactive" and was_released:
        raise HTTPException(
            409, detail="Bitte «Abbrechen» verwenden – ein freigegebener Auftrag braucht einen Folgeauftrag")

    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/replace", response_model=OrderResponse)
async def replace_order(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ersetzen: neuen Auftrag (Entwurf, gleicher Artikel/Menge) anlegen, verknüpfen,
    Original abbrechen. Liefert den **neuen** Auftrag zurück."""
    order = _get_staff_order(db, object_id)
    if order.status in ("inactive", "completed"):
        raise HTTPException(400, detail="Abgeschlossene/inaktive Aufträge können nicht ersetzt werden")
    if order.article_id is None and order_lines_svc.lines_for(db, order):
        raise HTTPException(400, detail="Ein Mehrpositionen-Auftrag kann (noch) nicht ersetzt werden")
    new = deactivation.duplicate_order(db, order, current_user.id)
    log_audit(db, "orders", "replaced_by_id", str(new.object_id), current_user.id,
              object_id=order.object_id)
    order.replaced_by_id = new.object_id
    was_released = order.status == "released"
    order.status = "inactive"
    if was_released:
        deactivation.cancel_order_effects(db, order, current_user.id)
    db.commit()
    db.refresh(new)
    return to_order_response(db, new)


@router.post("/{object_id}/abort", response_model=OrderResponse)
async def abort_order(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Abbruch eines Auftrags – **sofort und endgültig**, kein Antrag (siehe
    ``deviation.abort_parent``). Ein **Entwurf** oder ein Auftrag ohne aktive Instanzen wird
    direkt inaktiv. Sind noch Instanzen im Prozess, übernimmt sie ein **Abweichungsauftrag**
    (dort wird entschieden, was mit ihnen geschieht) – herrenlos wird nichts. Ein
    **Unter-Auftrag** wird stattdessen verworfen (Bindung zurück an den Eltern)."""
    order = _get_staff_order(db, object_id)
    if order.status in ("inactive", "completed"):
        raise HTTPException(400, detail="Auftrag ist bereits abgeschlossen/inaktiv")
    if order.abort_into_id:
        raise HTTPException(409, detail="Für diesen Auftrag ist bereits ein Folgeauftrag offen")

    # Ein **Unter-Auftrag** bekommt NIE einen eigenen Folgeauftrag: sein Subjekt gehört
    # ohnehin dem Eltern (Abweichung/Retoure) bzw. er transportiert nur (Bereitstellung) –
    # es gibt nichts zu übergeben. Er geht direkt inaktiv, aber ÜBER die eine Aufräum-Stelle
    # (`detach_sub_order`): Subjekt-Bindung zurück an den Eltern, Verarbeitungs-Links lösen,
    # `abort_into_id` löschen. Ohne das bliebe der Eltern für immer pausiert und liesse sich
    # nie wieder abbrechen («Für diesen Auftrag ist bereits ein Folgeauftrag offen»).
    if order.parent_order_id is not None:
        was_released = order.status == "released"
        parent = deviation.detach_sub_order(db, order, current_user.id)
        order.status = "inactive"
        if was_released:
            deactivation.cancel_order_effects(db, order, current_user.id)
        log_audit(db, "orders", "status", "inactive", current_user.id,
                  object_id=order.object_id, old_value="released" if was_released else "draft")
        # Der Eltern ist damit nicht mehr pausiert – er läuft weiter bzw. schliesst ab.
        if parent and parent.status == "released":
            process.recompute_completion(db, parent)
        db.commit()
        db.refresh(order)
        return to_order_response(db, order)

    # Entwurf oder ein Auftrag ohne (noch aktive) im Prozess befindliche Instanzen → direkt
    # inaktiv. Verschrottete/terminale Teile zählen nicht als «zu retten».
    if order.status == "draft" or not subject.order_active_instances(db, order):
        was_released = order.status == "released"
        order.status = "inactive"
        if was_released:
            deactivation.cancel_order_effects(db, order, current_user.id)
        db.commit()
        db.refresh(order)
        return to_order_response(db, order)

    # Ein laufender Auftrag MIT Instanzen wird nicht mehr über diesen Weg abgebrochen: dafür
    # gibt es den einen Knopf «Abweichungsauftrag» mit ``abort_parent=true`` – ein Vorgang,
    # ein Wort. Sonst gäbe es wieder zwei Wege für dieselbe Sache.
    raise HTTPException(
        409,
        detail="Dieser Auftrag hat Instanzen im Prozess – bitte über «Abweichungsauftrag» "
               "abbrechen (dort festlegen, was mit den Teilen geschieht).",
    )


@router.post("/{object_id}/revoke", response_model=OrderResponse)
async def revoke_followup(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """«Abbruch zurücknehmen / Folgeauftrag verwerfen»: einen noch im **Entwurf** befindlichen
    Folgeauftrag (Abbruch/Abweichung) zurücknehmen. Das Original läuft danach **unverändert**
    weiter (kein Vollzug, Reservierungen blieben erhalten). ``object_id`` = der Folgeauftrag.
    Liefert den wieder laufenden Eltern-Auftrag zurück."""
    followup = _get_staff_order(db, object_id)
    parent = deviation.revoke(db, followup, current_user.id)
    db.commit()
    target = parent or followup
    db.refresh(target)
    return to_order_response(db, target)


@router.post("/{object_id}/cover", response_model=OrderResponse)
async def cover_shortfall(
    object_id: int,
    data: OrderCoverStock,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """**«Ersetzen»** – die Fehlmenge eines blockierten Schritts decken, egal woher.

    EIN Endpunkt statt zweier Knöpfe («Aus Lager decken» + «Nachschub anlegen»): erst der
    freie Lagerbestand (FIFO bzw. die in ``instance_object_ids`` gezielt gewählten
    Instanzen), für den Rest ein Nachschub-Unter-Auftrag. Idempotent; liefert den Auftrag."""
    order = _get_staff_order(db, object_id)
    if order.status != "released":
        raise HTTPException(400, detail="Nur ein freigegebener Auftrag lässt sich decken")
    recovery.cover_shortfall(db, order, current_user.id, data.instance_object_ids)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/confirm-quantity", response_model=OrderResponse)
async def confirm_quantity(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """**«Menge bestätigen»** – der Auftrag wird mit dem fertig, was gesichert ist.

    Das Soll sinkt auf die gesicherte Menge (5 bestellt, 1 in Klärung → 4 bestellt); der
    blockierte Schritt ist damit frei. Bezahlte Verkaufspositionen sind ausgenommen – die
    korrigiert eine Retoure/Gutschrift."""
    order = _get_staff_order(db, object_id)
    if order.status != "released":
        raise HTTPException(400, detail="Nur bei einem freigegebenen Auftrag lässt sich die Menge bestätigen")
    recovery.confirm_quantity(db, order, current_user.id)
    db.commit()
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/purchase", response_model=OrderResponse)
async def update_order_purchase(
    object_id: int,
    data: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Beschaffungsschritt des Auftrags bearbeiten (rollenabhängig, läuft unter der
    Auftragsnummer – keine eigene Bestellnummer).

    EIN Schritt, auch bei mehreren Artikeln (Mehrpositionen-Auftrag): ``facts_for_step``
    liefert dann mehrere Bestellungen (eine je Artikel), ein reiner Statuswechsel gilt für
    alle gemeinsam (eine Sendung) – siehe ``purchase.apply_update_bulk``."""
    order = visible_orders(db, user).filter(Order.object_id == object_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    # Lieferanten-Fähigkeits-Gate serverseitig (Backstop zum Consent-Modal): ein Lieferant
    # mit offenen Pflicht-Bestätigungen (z. B. ``supplier_terms``-Publikums-Dokument) kann
    # nicht offerieren/bestätigen – auch nicht per direktem API-Aufruf. Personal bleibt
    # frei (interne Arbeit wird nicht durch das Kunden-/Lieferanten-Gate blockiert).
    if user.role == "supplier":
        from ..services import consent as consent_svc
        consent_svc.assert_acknowledged(db, user)
    step = process.resolve_exec_step(db, order, "purchase", data.step_id)
    pos = process.facts_for_step(db, order, step)
    apply_purchase_update_bulk(db, pos, data, user)
    db.refresh(order)
    return to_order_response(db, order, viewer=user)


@router.patch("/{object_id}/sale", response_model=OrderResponse)
async def update_order_sale(
    object_id: int,
    data: SaleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Verkauf» (kaufmännisch): Bestätigung → Rechnung → Zahlung.

    EIN Schritt, auch bei mehreren Artikeln (Mehrpositionen-Auftrag): ``facts_for_step``
    liefert dann mehrere Belege (einen je Artikel), die Aktualisierung (Kunde/Status/
    Zahlungsart) gilt für alle gemeinsam (eine Sendung, eine Zahlung) – siehe
    ``sale.apply_update_bulk``."""
    order = _get_staff_order(db, object_id)
    step = process.resolve_exec_step(db, order, "sale", data.step_id)
    sales = process.facts_for_step(db, order, step)
    sale_svc.apply_update_bulk(db, sales, data, current_user)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/inspection", response_model=OrderResponse)
async def update_order_inspection(
    object_id: int,
    data: InspectionUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Eingangskontrolle»: Stichprobenergebnis erfassen (passed/failed)."""
    order = _get_staff_order(db, object_id)
    record_inspection(db, order, data, current_user)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/document", response_model=OrderResponse)
async def update_order_document(
    object_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Dokument»: Inhalt verfassen (save) bzw. ausstellen (issue)."""
    order = _get_staff_order(db, object_id)
    record_document(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/document/signoff/{signoff_id}", response_model=OrderResponse)
async def act_order_document_signoff(
    object_id: int,
    signoff_id: int,
    data: SignoffAction,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Freigabe-Partei handelt inline am Auftrag (unterschreiben/bestätigen/ablehnen/zurückziehen).

    Für ANGEMELDETE Nutzer (nicht nur Personal): auch ein Kunde/Lieferant, der als Partei
    benannt ist, kann hier signieren – die Berechtigung prüft ``act_on_signoff`` über die
    Objektnummer. Der Auftrag muss für den Nutzer sichtbar sein."""
    order = db.query(Order).filter(Order.object_id == object_id, Order.is_active == True).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    signoff = get_signoff(db, signoff_id)
    if signoff.order_id != order.id:
        raise HTTPException(404, detail="Freigabe-Partei gehört nicht zu diesem Auftrag")
    act_on_signoff(db, signoff, data, current_user)
    db.refresh(order)
    return to_order_response(db, order, viewer=current_user)


@router.post("/{object_id}/document/withdraw", response_model=OrderResponse)
async def withdraw_order_document(
    object_id: int,
    step_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ausstellung eines Dokuments zurücknehmen (Personal) – Inhalt wieder editierbar, alle
    Freigabe-Parteien verworfen. Nur solange das Dokument noch nicht vollständig freigegeben ist."""
    order = _get_staff_order(db, object_id)
    withdraw_issuance(db, order, step_id, current_user)
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/document/substitute-signer", response_model=OrderResponse)
async def substitute_order_document_signer(
    object_id: int,
    data: SignerSubstitution,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """**Freigabe-Partei ersetzen** (Personal, auditiert) – auch am LAUFENDEN Auftrag: das
    offene (pending/abgelehnte) Signoff wandert auf eine neue, aktive Person; Position und
    Aktion bleiben. Bereits geleistete Unterschriften sind unveränderlich. So braucht ein
    Auftrag, dessen benannte Partei ausfällt, keinen Abbruch mehr."""
    order = _get_staff_order(db, object_id)
    substitute_signer(db, order, data.step_id, data.old_signer_object_id,
                      data.new_signer_object_id, current_user)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/movement", response_model=OrderResponse)
async def update_order_movement(
    object_id: int,
    data: MovementUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Bewegung»: Instanzen einlagern/umlagern (Zielstandort je Instanz)."""
    order = _get_staff_order(db, object_id)
    record_movement(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/shipment/quote", response_model=OrderResponse)
async def quote_order_shipment(
    object_id: int,
    data: ShipmentQuoteRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Versand (ADR 005): Tarife laden (Rate-Shopping) für den Bewegungs-Schritt.
    Der Versand-Beleg entsteht dabei idempotent; günstigster Tarif = Default-Auswahl."""
    order = _get_staff_order(db, object_id)
    step = process.resolve_exec_step(db, order, "movement", data.step_id)
    logistics.quote(db, order, step, _shipment_instances(db, order, step), current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.post("/{object_id}/shipment/buy", response_model=OrderResponse)
async def buy_order_shipment(
    object_id: int,
    data: ShipmentBuyRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Versand: gewähltes Angebot kaufen → Label (PDF) + Tracking-Nummer (idempotent)."""
    order = _get_staff_order(db, object_id)
    step = process.resolve_exec_step(db, order, "movement", data.step_id)
    logistics.buy(db, order, step, data.rate_id, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/shipment", response_model=OrderResponse)
async def update_order_shipment(
    object_id: int,
    data: ShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Versand: Transport-Modus je Auftrag übersteuern (auto/carrier/self/none) bzw.
    manuelle Versanddaten erfassen (Carrier, Tracking, Kosten – manual-Provider)."""
    order = _get_staff_order(db, object_id)
    step = process.resolve_exec_step(db, order, "movement", data.step_id)
    logistics.apply_update(db, order, step, _shipment_instances(db, order, step), data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


def _shipment_instances(db: Session, order, step) -> list:
    """Die Instanzen, die dieser Bewegungs-Schritt physisch bewegt (Paket-/Gefahrgut-Basis)
    – die EINE Auswahlregel der Ausführung (``movement.movable_instances``)."""
    from ..services.movement import movable_instances
    return movable_instances(db, order, step)


@router.patch("/{object_id}/resource", response_model=OrderResponse)
async def update_order_resource(
    object_id: int,
    data: ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Ressource»: Verbrauch (FIFO, Chargen-Teilentnahme) + Betriebsmittel."""
    order = _get_staff_order(db, object_id)
    record_resource(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/scrap", response_model=OrderResponse)
async def update_order_scrap(
    object_id: int,
    data: ScrapUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Verschrotten»: gewählte Instanzen ausschleusen (disposition='scrapped')."""
    order = _get_staff_order(db, object_id)
    record_scrap(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)


@router.patch("/{object_id}/block", response_model=OrderResponse)
async def update_order_block(
    object_id: int,
    data: ScrapUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Schritt «Sperren»: gewählte Instanzen vorübergehend sperren (quality='blocked').

    Gleiche Auswahl-Form wie das Verschrotten – nur eben umkehrbar: Standort, Menge und
    Reservierungen bleiben unangetastet, die Instanz ist nur nicht mehr verwendbar."""
    order = _get_staff_order(db, object_id)
    record_block(db, order, data, current_user.id)
    db.refresh(order)
    return to_order_response(db, order)
