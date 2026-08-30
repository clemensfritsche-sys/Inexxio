"""**Der Beschaffungs-Beleg: anlegen, führen, zurücknehmen.**

Die eine Stelle, an der ein ``Purchase`` geschrieben wird. Sie kennt drei Fragen:

* **Was steht an?** – die Stufe und ihre Eingaben (``embed``)
* **Was wird getan?** – Anfragen · Offerieren · Bestellen · Zurücknehmen (``apply``)
* **Was, wenn sich die Grundlage ändert?** – ``rebase``

**Ein Modul räumt selbst auf — und legt nie einen Auftrag an.** Jede Zusage nach aussen
hat ihre Gegenhandlung an derselben Stelle: die Anfrage wird zurückgezogen, die
Bestellung storniert. Es gibt keinen Endpunkt daneben und keinen zweiten Weg. Was
dagegen **Stücke** betrifft, entscheidet ein Mensch – dieses Modul legt keinen Auftrag an
und keine Abweichung.

**Die Stufen gehören dem Beleg, nicht dem Stück.** Eine Einzelinstanz ist von der Anfrage
bis zum Wareneingang durchgehend ``Im Prozess``.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain import modules, procurement
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderUnit, ProcessStep, Purchase,
    UserProfile,
)
from . import article_fields, places

#: Die Zustände einer Angebotszeile. ``gewaehlt`` entsteht nicht durch Tippen, sondern
#: dadurch, dass bei dieser Zeile bestellt wurde – ein Zustand ist eine Folge.
ASKED, QUOTED, DECLINED, CHOSEN = "angefragt", "offeriert", "abgelehnt", "gewaehlt"

#: Was ein Aufrufer tun kann. **Eine Gegenhandlung** (``revoke``) statt zweier: was sie
#: bewirkt, sagt die Stufe – vor der Bestellung zieht sie die Anfrage zurück, danach
#: storniert sie. Zwei Verben für «zurück» wären zwei Wege zu derselben Sache.
#: **Der Beleg entsteht** – die Handlung des **Moduls**, nicht des Belegs.
#:
#: Sie steht darum bewusst **nicht** in ``ACTIONS``: dort sind die Verben eines Belegs,
#: und die hängen an seiner Stufe (``_can`` ist ihr Tor). «Kaufe ich das überhaupt ein?»
#: ist eine Frage davor – sie hat keine Stufe, sondern eine Deklaration (``Module.buys``),
#: und die Oberfläche liest sie als ``ModuleFacts.buys``. Derselbe Endpunkt bedient
#: beides: ein zweiter wäre ein zweiter Weg zu einer Sache, die der Beleg verwaltet.
BUY = "buy"

ACTIONS = ("ask", "quote", "decline", "order", "note", "revoke", "clarified")

#: Was ein **Lieferant** selbst darf: seine eigene Zeile füllen oder ablehnen – und,
#: sobald bestellt ist, die **Sendungsnummer** nachtragen (er verschickt, er kennt sie).
#: Bestellen tut der Besteller – die Verantwortungstrennung ist der Sinn des Portals.
SUPPLIER_ACTIONS = ("quote", "decline", "note")

#: **Der Wareneingang.** Keine ``apply``-Handlung – er läuft über ``confirm_step`` –, aber
#: aus Sicht des Belegs das Verb seiner dritten Stufe. Er steht in derselben Liste wie die
#: übrigen (``_can``), weil «was darf ich hier tun» **eine** Frage ist; zwei Listen wären
#: zwei Massstäbe, und die Oberfläche müsste entscheiden, welcher gerade gilt.
RECEIVE = "receive"

#: Welche Handlungen eine Stufe überhaupt zulässt. Nach dem Wareneingang und nach einem
#: Storno ist es **keine** – dort ist der Beleg Vergangenheit.
STAGE_ACTIONS: dict[str, tuple[str, ...]] = {
    "anfrage": ("ask", "quote", "decline", "order", "revoke"),
    "bestellung": ("note", "revoke", "clarified", RECEIVE),
}


def _money(value: Any, *, field: str) -> Optional[Decimal]:
    """Ein Betrag – **als Decimal**, nie als ``float``.

    Er reist als String in die Datenbank und aus ihr heraus (``quotes``); wo es auf den
    Rappen ankommt, ist eine Fliesskommazahl der Anfang eines Rundungsfehlers, den
    niemand mehr findet.
    """
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Betrag ({field}).")
    if amount < 0:
        raise HTTPException(status_code=400, detail=f"Ein Betrag ist nicht negativ ({field}).")
    return amount.quantize(Decimal("0.01"))


def _int(value: Any, *, field: str) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"«{value}» ist keine Zahl ({field}).")
    return number


def steps_of(db: Session, order: Order,
             *, buys: Optional[str] = None) -> list[ProcessStep]:
    """Die Module dieses Auftrags, die einen **Beleg** tragen können – in ihrer Folge.

    **Nicht mehr EIN Modultyp.** Gefragt wird die Deklaration (``Module.buys``), nicht
    der Name: seit auch das Bewegen-Modul einkaufen kann, wäre ``module_type ==
    'beschaffen'`` die Stelle, an der ein zweiter Typ vergessen wird. ``buys`` verengt
    zusätzlich auf eine Art – ``BUY_ALWAYS`` sind die, die bei der Freigabe einen
    bekommen.
    """
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id,
                ProcessStep.module_type.in_(modules.buying_types(buys=buys)))
        .order_by(ProcessStep.position)
        .all()
    )


def process_lines(db: Session, order: Order) -> list[tuple[int, int]]:
    """**Was steht vor dem Modul?** – je Artikel eine Zeile ``(article_id, Stück)``.

    Der Weg ist derselbe, aus dem der Prozess überall rechnet: offene Zugehörigkeit →
    Einzelinstanz → Instanz → Artikel. Sortiert nach Objektnummer, damit die Reihenfolge
    des Belegs nicht von der Datenbank abhängt.
    """
    rows = (
        db.query(Instance.article_id, func.count(OrderUnit.id))
        .join(InstanceUnit, InstanceUnit.instance_id == Instance.id)
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
        .group_by(Instance.article_id)
        .all()
    )
    return sorted(((int(a), int(n)) for a, n in rows), key=lambda r: r[0])


def lines_of(db: Session, order: Order, row: Purchase) -> list[dict[str, Any]]:
    """**Die Zeilen des Belegs** – Artikel · Menge, und beides abgeleitet.

    Ein Beschaffungs-Modul sitzt in einem Prozess: **was** bestellt wird, sind die
    Einzelinstanzen, die davorstehen – also ihre Artikel; **wie viel**, ist ihre Zahl.
    Beides von Hand zu wählen wären zwei Aussagen über dieselbe Sache, und die gewählte
    gewinnt auch dann, wenn sie falsch ist.

    **Mit der Bestellung frieren die Zeilen ein** (``ordered_lines``): dort ist eine
    zweite Partei gebunden, und was bestellt wurde, ändert sich nicht mehr dadurch, dass
    der Auftrag später Stücke verliert. Genau diese Differenz meldet ``mismatch``.
    """
    if row.ordered_lines:
        return [dict(line) for line in row.ordered_lines]
    return [{"article": a, "quantity": n} for a, n in process_lines(db, order)]


def instantiate_for_order(db: Session, order: Order) -> list[Purchase]:
    """Bei der Freigabe: je Modul, das **immer** einkauft, einen Beleg.

    **Ein Beleg je Modul, nicht je Position** – was bestellt wird, sagt der Prozess
    (``lines_of``), und ein Beleg kann zwei Zeilen tragen.

    **Nur ``BUY_ALWAYS``.** Ein Modul, das seine Arbeit auch selbst erledigen kann
    (Bewegen), bekommt hier keinen: ein Beleg ohne Lieferant, den niemand wollte, wäre
    eine Bestellung, die es nicht gibt – und er würde ausserdem die Frage «wurde das
    eingekauft?» mit «ja» beantworten. Dort entsteht er erst mit der Wahl (``ensure``).

    Idempotent: gibt es den Beleg schon, passiert nichts.
    """
    made: list[Purchase] = []
    for step in steps_of(db, order, buys=modules.BUY_ALWAYS):
        row = _create(db, order=order, step=step)
        if row is not None:
            made.append(row)
    if made:
        db.flush()
    return made


def _create(db: Session, *, order: Order, step: ProcessStep) -> Optional[Purchase]:
    """Einen Beleg anlegen, wenn es noch keinen gibt. ``None`` = gab es schon."""
    if of_step(db, step.id) is not None:
        return None
    row = Purchase(order_id=order.id, step_id=step.id,
                   stage=procurement.STAGES[0], quotes=[])
    db.add(row)
    return row


def ensure(db: Session, *, order: Order, step: ProcessStep) -> Purchase:
    """►►► **«Das kaufe ich ein.»** ◄◄◄ – der Beleg entsteht mit der Wahl.

    Die eine Stelle, an der ein Modul zur Laufzeit einen Beleg bekommt. Sie ist der
    Gegenpart zu ``instantiate_for_order``: dort entsteht er, weil das Modul zum Kaufen
    da ist; hier, weil jemand entschieden hat, es nicht selbst zu tun.

    **Nur ein Modul, das das darf** – sonst hätte jeder Schritt eine Hintertür zu einem
    Beleg, und die Deklaration wäre eine Empfehlung.
    """
    module = modules.get(step.module_type)
    if module.buys != modules.BUY_IF_CHOSEN:
        raise HTTPException(
            status_code=400,
            detail=(f"«{module.label}» kann nichts einkaufen – ein Beleg entsteht nur "
                    f"dort, wo die Arbeit auch selbst erledigt werden könnte."),
        )
    row = _create(db, order=order, step=step) or of_step(db, step.id)
    db.flush()
    assert row is not None
    return row


def mine(db: Session, viewer: Optional[UserProfile]) -> Optional[list[Purchase]]:
    """**Woran ist dieser Betrachter beteiligt?** ``None`` = an allem (Personal).

    Die eine Frage, aus der die ganze Lieferanten-Sicht folgt – Feed *und* Detail lesen
    sie, und beide bekommen dieselbe Antwort. Ein Lieferant ist genau dort beteiligt, wo
    er **angefragt** wurde: seine Objektnummer steht in ``quotes``.

    Gefiltert wird in der **Datenbank** (JSONB-Containment ``@>``), nicht im Python: die
    Alternative wäre, für jede Feed-Anzeige sämtliche Belege des Hauses zu laden.

    Wer weder Personal noch angefragter Lieferant ist, ist an **nichts** beteiligt – die
    leere Liste ist die richtige Antwort, nicht ein Sonderfall.
    """
    if viewer is None or viewer.role in ("admin", "employee"):
        return None
    if viewer.role != "supplier" or viewer.object_id is None:
        return []
    return (
        db.query(Purchase)
        .filter(Purchase.quotes.contains([{"supplier": viewer.object_id}]))
        .all()
    )


def _can(row: Purchase, viewer: Optional[UserProfile]) -> list[str]:
    """►►► **Was darf DIESER Betrachter an DIESEM Beleg tun?** ◄◄◄

    Die eine Antwort – Stufe **mal** Rolle –, und sie reist mit der Antwort mit
    (``PurchaseEmbed.can``). Die Oberfläche rendert eine Aktion genau dann, wenn ihr Verb
    hier steht; sie weiss danach nicht mehr, was ein Lieferant ist.

    Vorher stand die Regel nur im **Dienst** (er wies mit 403 ab) – die Oberfläche zeigte
    einem Lieferanten trotzdem «Anfrage zurückziehen», «Bestellen», «Stornieren» und den
    Wareneingangs-Scan. Ein Knopf, der nie etwas tun kann, ist kein Angebot; und eine
    Rollenabfrage in der Oberfläche wäre die zweite Stelle, an der dieselbe Regel steht.

    Dieselbe Bauart wie ``articles.may_create`` und ``process.pick_problem``: die Regel
    gibt zurück, **was gilt** – nicht, wer fragt.
    """
    allowed = list(STAGE_ACTIONS.get(row.stage, ()))
    if viewer is not None and viewer.role == "supplier":
        allowed = [a for a in allowed if a in SUPPLIER_ACTIONS]
    return allowed


def _optional(step: ProcessStep) -> bool:
    """►►► **Kann dieses Modul seine Arbeit auch OHNE Beleg erledigen?** ◄◄◄

    Die eine Ableitung über ``Module.buys`` – und sie hat zwei Leser, die dieselbe Sache
    verschieden anwenden: ``_revoke`` (was «zurück» bewirkt) und ``_undo`` (wie es heisst).
    Zweimal ausgeschrieben wären es zwei Massstäbe, und der zweite wäre der, den man beim
    nächsten Modul vergisst.
    """
    return modules.get(step.module_type).buys == modules.BUY_IF_CHOSEN


def _undo(row: Purchase, step: ProcessStep) -> str:
    """**Wie heisst hier «zurück»?** – ein Wort aus Stufe × Deklaration.

    Es gibt genau **eine** Gegenhandlung (``revoke``); was sie bewirkt, hängt daran, ob
    schon etwas zugesagt ist und ob der Einkauf überhaupt der Zweck war. Das Wort dafür
    gehört darum an dieselbe Stelle wie die Wirkung – die Oberfläche schreibt es nicht
    selbst hin, sonst stünde beim nächsten Fall ein Satz da, den keine Regel deckt.
    """
    if row.stage != procurement.STAGES[0]:
        return "Bestellung stornieren"
    return "Doch selbst erledigen" if _optional(step) else "Anfrage zurückziehen"


def of_step(db: Session, step_id: int) -> Optional[Purchase]:
    """**Der Beleg dieses Moduls** – oder ``None``.

    Nur der **aktive**: ein zurückgenommener steht als Zeile weiter da (Soft-Delete),
    aber er ist keine Bestellung mehr. Und weil «gibt es einen Beleg?» zugleich die
    Antwort auf «wurde das eingekauft?» ist, wäre er hier eine falsche Aussage über die
    Wirklichkeit.
    """
    return (
        db.query(Purchase)
        .filter(Purchase.step_id == step_id, Purchase.is_active.is_(True))
        .first()
    )


# ─── Was sich ändert, wenn die Grundlage kleiner wird ────────────────────────


def mismatch(db: Session, order: Order, row: Purchase) -> Optional[int]:
    """**Rechnet dieser Beleg noch mit der richtigen Grundlage?** ``None`` = ja.

    Verglichen wird, womit **bestellt** wurde (``ordered_lines``), mit dem, was heute vor
    dem Modul steht. Vor der Bestellung gibt es nichts zu klären – dort zieht der Beleg
    still nach, weil ausser uns niemand beteiligt ist.

    Zurück kommt die **heutige Gesamtmenge**; welche Zeile sich geändert hat, steht in
    den Zeilen selbst.
    """
    if row.stage != procurement.BINDING or not row.ordered_lines:
        return None
    now = process_lines(db, order)
    ordered = [(int(l["article"]), int(l["quantity"])) for l in row.ordered_lines]
    return sum(n for _, n in now) if now != ordered else None


def rebase(db: Session, order: Order) -> None:
    """**Die Grundlage hat sich geändert** – was folgt, hängt an der Stufe.

    *Vor* der Bestellung ist niemand ausser uns beteiligt: die Zeilen werden gar nicht
    gespeichert, sie **sind** der Prozess (``lines_of``) und ziehen damit von selbst nach.
    *Ab* der Bestellung liegen sie beim Lieferanten – dann ändert das System nichts,
    sondern **meldet** (``mismatch``) und wartet auf ``clarified``.

    Bleibt **nichts** übrig, ist der Beleg gegenstandslos: ``storniert``. Das ist keine
    zusätzliche Regel, sondern dieselbe eine Stufe weiter – man bestellt nichts für null
    Stück.

    **Selbstheilend**: die Funktion vergleicht und tut nichts, wenn alles stimmt. Ein
    verpasster Aufruf korrigiert sich beim nächsten.
    """
    rows = db.query(Purchase).filter(Purchase.order_id == order.id).all()
    if not rows:
        return
    empty = not process_lines(db, order)
    for row in rows:
        if row.stage in (procurement.STAGES[-1], procurement.CANCELLED):
            continue                      # Vergangenheit wird nicht umgeschrieben
        if empty:
            row.stage = procurement.CANCELLED
    db.flush()


def _articles(db: Session, ids: list[int]) -> dict[int, Article]:
    """Die Artikel der Beleg-Zeilen – **eine** Abfrage, nicht eine je Zeile."""
    if not ids:
        return {}
    return {a.id: a for a in db.query(Article).filter(Article.id.in_(ids)).all()}


# ─── Was die Ausführungsstelle sieht ─────────────────────────────────────────


def _line_facts(db: Session, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Zeilen des Belegs als Auskunft – **mit der Spezifikation ihres Artikels**.

    Sie reist mit, statt ausgewählt zu werden (``services/article_fields``): der
    Lieferant sieht die Sache; **was er damit tun soll**, steht als ein Satz daneben.
    Ein Artikel, den es nicht mehr gibt, lässt die Zeile stehen (die Menge wurde
    bestellt) – tolerant lesen, streng schreiben.
    """
    found = _articles(db, [int(line["article"]) for line in lines])
    out: list[dict[str, Any]] = []
    for line in lines:
        article = found.get(int(line["article"]))
        out.append({
            "article_object_id": article.object_id if article else 0,
            "article_name": article.name if article else "",
            "unit": getattr(article, "unit", "") or "",
            "quantity": float(line.get("quantity") or 0),
            "spec": article_fields.specification(article),
        })
    return out


def embed_data(db: Session, *, order: Order, step: ProcessStep,
               viewer: Optional[UserProfile] = None) -> Optional[dict[str, Any]]:
    """Der Beleg als flacher Satz Werte – oder ``None`` bei jedem anderen Modultyp.

    **Ein Lieferant sieht nur seine eigene Angebotszeile.** Fremde Preise sind kein
    Nebeneffekt einer Ansicht: gefiltert wird hier, beim Aufbau der Antwort, und nicht in
    der Oberfläche – eine Filterung dort wäre eine Bitte.
    """
    row = of_step(db, step.id)
    if row is None:
        return None
    config = step.config or {}
    # **Beide Fäden hängen jetzt am Modul**, nicht an einer Klasse: wer zugelassen ist
    # und was zu tun ist. Beim Beschaffen steht beides in der Definition, beim Bewegen
    # ist das eine leer (der Spediteur wird zur Laufzeit benannt) und das andere
    # **abgeleitet** («von A nach B»).
    module = modules.get(step.module_type)
    allowed = module.suppliers_of(config)
    refs = {r["supplier"]: r["ref"] for r in allowed}
    names = _names(db, [r["supplier"] for r in allowed]
                   + [q["supplier"] for q in row.quotes or []])
    mine = viewer.object_id if viewer is not None and viewer.role == "supplier" else None

    quotes = [q for q in (row.quotes or []) if mine is None or q["supplier"] == mine]
    chosen = (
        db.query(UserProfile).filter(UserProfile.id == row.supplier_id).first()
        if row.supplier_id else None
    )
    # **Wer nicht den Zuschlag hat, sieht ihn auch nicht.** ``quotes`` war gefiltert, die
    # getroffene Wahl nicht – ein angefragter, nicht gewählter Lieferant las damit Namen
    # und Preis seines Konkurrenten. Gefiltert wird beim Aufbau der Antwort; in der
    # Oberfläche wäre es eine Bitte.
    won = mine is None or (chosen is not None and chosen.object_id == mine)
    can = _can(row, viewer)
    return {
        "stage": row.stage,
        "stages": _stages(row),
        "can": can,
        # **Die Identität des Vorgangs reist mit ihm** – wie Farbe und Beschriftung eines
        # Moduls (``ModuleFacts``). Die Ausführungsstelle schlägt nichts in einem Katalog
        # nach, den nur der Editor lädt; und weil beide dieselbe Quelle lesen, sieht ein
        # Einkauf im Bewegen-Modul aus wie einer im Beschaffen-Modul.
        "label": procurement.LABEL,
        "tone": procurement.TONE,
        # **Ein Wort für die eine Gegenhandlung** – oder keines, wenn sie hier nicht geht.
        "undo": _undo(row, step) if "revoke" in can else None,
        "lines": _line_facts(db, lines_of(db, order, row)),
        "instruction": module.instruction_for(config, facts=_route(db, step=step)),
        "allowed": [
            {"supplier_object_id": r["supplier"],
             "supplier_name": names.get(r["supplier"], ""),
             "ref": r["ref"], "state": ASKED}
            for r in allowed if mine is None or r["supplier"] == mine
        ],
        "quotes": [
            {"supplier_object_id": q["supplier"],
             "supplier_name": names.get(q["supplier"], ""),
             "ref": refs.get(q["supplier"], ""),
             "amount": float(q["amount"]) if q.get("amount") not in (None, "") else None,
             "lead_days": q.get("lead_days"), "state": q.get("state", ASKED)}
            for q in quotes
        ],
        "supplier_object_id": chosen.object_id if chosen and won else None,
        "supplier_name": chosen.display_name if chosen and won else None,
        "amount": float(row.amount) if row.amount is not None and won else None,
        "currency": row.currency,
        "tracking": row.tracking if won else None,
        "clarify_quantity": mismatch(db, order, row),
    }


def _route(db: Session, *, step: ProcessStep) -> dict[str, Any]:
    """**Woher, wohin** – die Fakten, aus denen ein Modul seinen Auftrag formulieren kann.

    Der Dienst holt sie (er hat die Sitzung), das Modul formuliert (dort steht die
    Regel). Ein Modul, das nichts bewegt, fragt gar nicht danach – die Antwort ist dann
    ein leerer Satz, keine Fallunterscheidung.

    Die **Herkunft** ist der gemeinsame Halter der Stücke, die davorstehen; liegen sie
    nirgends oder an verschiedenen Orten, gibt es keine – dann sagt der Satz nur, wohin.
    Dieselbe Regel wie ``consumption.required_place``: wo nichts steht, wird nichts
    behauptet.
    """
    if not modules.get(step.module_type).moves:
        return {}
    units = (
        db.query(InstanceUnit)
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .filter(OrderUnit.released_at.is_(None), OrderUnit.current_step_id == step.id)
        .all()
    )
    here = places.common_holder(units)
    target = (step.config or {}).get(modules.Bewegen.TARGET)
    goal = places.station_of(db, int(target)) if target else None
    where = places.describe(db, here) if here else None
    return {"from": where.label if where else None, "to": goal.label if goal else None}


def _stages(row: Purchase) -> list[dict[str, Any]]:
    """Die drei Stufen mit ihrem Zustand.

    **Storniert ist keine Stufe**: dann ist keine aktiv – aber die Kette steht still da,
    wo sie stehengeblieben ist. Was einmal geschehen ist, bleibt gegangen; ein Storno
    macht die Bestellung nicht ungeschehen, es sagt nur, dass nichts mehr ankommt.
    Storniert wird ausschliesslich aus der Bestellung heraus (davor nimmt ``revoke`` die
    Anfrage zurück), also ist das die Stelle, an der die Kette endet.
    """
    order_of = {key: i for i, key in enumerate(procurement.STAGES)}
    cancelled = row.stage == procurement.CANCELLED
    here = order_of.get(row.stage, order_of[procurement.BINDING] if cancelled else -1)
    ends_here = (procurement.STAGES[-1], ) if not cancelled else procurement.STAGES
    return [
        {"key": key, "label": procurement.STAGE_LABELS[key],
         "verb": procurement.STAGE_VERBS.get(key, "") if i == here and not cancelled else "",
         "done": i < here or (i == here and key in ends_here),
         "active": i == here and not cancelled and key != procurement.STAGES[-1]}
        for i, key in enumerate(procurement.STAGES)
    ]


def _names(db: Session, numbers: list[int]) -> dict[int, str]:
    """Objektnummer → Anzeigename, in **einer** Abfrage (kein N+1 je Angebotszeile)."""
    wanted = {int(n) for n in numbers if n}
    if not wanted:
        return {}
    return {
        u.object_id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.object_id.in_(wanted)).all()
    }


# ─── Die Ausführung ──────────────────────────────────────────────────────────


def assert_receivable(db: Session, *, step: ProcessStep) -> None:
    """Vor ``confirm_step``: **darf hier etwas ankommen?**

    Kein ``if module_type ==`` an der Ausführungsstelle – dieselbe Bauart wie
    ``consumption.plan``: wer nichts zu sagen hat, sagt nichts. Nur ein Beschaffungs-Modul
    hat einen Beleg, und nur bestellte Ware kann eintreffen.
    """
    row = of_step(db, step.id)
    if row is None:
        return
    if row.stage == procurement.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail="Diese Bestellung ist storniert – es kommt nichts mehr an.",
        )
    if row.stage == procurement.STAGES[0]:
        raise HTTPException(
            status_code=409,
            detail=("Es ist noch nichts bestellt. Erst bestellen, dann kann Ware "
                    "eintreffen – ein Wareneingang ohne Bestellung ist ein Beleg ohne "
                    "Anlass."),
        )


def note_receipt(db: Session, *, order: Order, step: ProcessStep) -> None:
    """Nach ``confirm_step``: steht nichts mehr davor, ist die Ware **da**.

    Teillieferung braucht dafür keine eigene Regel: ``confirm_step`` ist ein
    Teilabschluss, und solange noch Stücke vor dem Modul stehen, bleibt der Beleg in
    «Bestellung». Der Einstandspreis wandert beim Abschluss an den Artikel – Summe ÷
    Menge, an genau einer Stelle gerechnet.
    """
    row = of_step(db, step.id)
    if row is None or row.stage != procurement.BINDING:
        return
    waiting = (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
                OrderUnit.current_step_id == step.id)
        .count()
    )
    if waiting:
        return
    row.stage = procurement.STAGES[-1]
    _write_landed_cost(db, step=step, row=row)
    db.flush()


def _write_landed_cost(db: Session, *, step: ProcessStep, row: Purchase) -> None:
    """Summe ÷ Menge → Einstandspreis am Artikel – **nur bei EINER Zeile**.

    Bei zwei Artikeln auf einem Beleg ist die Bestellsumme eine gemeinsame; sie durch die
    Gesamtmenge zu teilen ergäbe für beide denselben Preis, und das wäre für beide falsch.
    Eine Aufteilung müsste jemand vornehmen – also wird hier nichts geschrieben, statt
    eine Zahl zu erfinden, mit der später kalkuliert wird.

    **Und nur, wo der Beleg für die WARE zahlt** (``Module.landed_cost``). Beim Einkauf
    ist er das – auch bei einer Leistung am Teil, denn die erhöht dessen Kosten. Bei
    einem **Transport** ist er es nicht: derselbe Artikel, zweimal verschickt, hätte als
    Einstandspreis den Frachttarif, und damit würde danach kalkuliert. Ein stiller
    Datenfehler, und darum eine Deklaration statt eines ``if module_type``.
    """
    if not modules.get(step.module_type).landed_cost:
        return
    lines = row.ordered_lines or []
    if len(lines) != 1 or row.amount is None:
        return
    quantity = Decimal(str(lines[0].get("quantity") or 0))
    if not quantity:
        return
    article = db.query(Article).filter(Article.id == int(lines[0]["article"])).first()
    if article is not None:
        article.landed_unit_cost = (Decimal(row.amount) / quantity).quantize(
            Decimal("0.0001"))


# ─── Die sechs Handlungen ────────────────────────────────────────────────────


def apply(db: Session, *, order: Order, step: ProcessStep, action: str,
          payload: dict[str, Any], actor: UserProfile) -> Purchase:
    """**Eine Handlung am Beleg.** Was erlaubt ist, hängt an der Stufe und an der Rolle."""
    if action not in ACTIONS and action != BUY:
        raise HTTPException(
            status_code=400,
            detail=f"«{action}» ist keine Handlung. Bekannt: "
                   + ", ".join((BUY, ) + ACTIONS) + ".",
        )
    # ►► **«Das kaufe ich ein.»** ◄◄ Die eine Handlung, die *vor* dem Beleg kommt – sie
    # legt ihn an. Danach ist es derselbe Vorgang wie jeder Einkauf. Sie geht nicht durch
    # ``_can``, weil sie keine Stufe hat: was sie erlaubt, ist die Deklaration des Moduls.
    if action == BUY:
        return ensure(db, order=order, step=step)
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dieses Modul hat keinen Beleg.")
    if row.stage == procurement.CANCELLED:
        raise HTTPException(status_code=409, detail="Dieser Beleg ist storniert.")
    if row.stage == procurement.STAGES[-1]:
        raise HTTPException(
            status_code=409,
            detail="Die Ware ist eingetroffen – daran ist nichts mehr zu ändern.",
        )
    # **Dieselbe Tabelle, die es der Oberfläche sagt, weist hier ab.** Sonst wäre ``can``
    # eine Behauptung neben der Regel – und die beiden liefen beim nächsten Verb
    # auseinander. Der Unterschied ist nur, **warum** es nicht geht: die Stufe (409) oder
    # die Rolle (403).
    if action not in _can(row, actor):
        if action in STAGE_ACTIONS.get(row.stage, ()):
            raise HTTPException(
                status_code=403,
                detail=("Ein Lieferant offeriert oder lehnt ab und trägt die "
                        "Sendungsnummer nach – bestellt wird beim Besteller."),
            )
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» geht an dieser Stelle nicht – der Beleg steht auf "
                    f"«{procurement.STAGE_LABELS[row.stage]}»."),
        )

    # **Wer zugelassen ist, sagt das Modul** – der erste der beiden Fäden, die den Beleg
    # einmal an «Beschaffen» banden. Leer heisst frei (``Module.suppliers_of``).
    allowed = modules.get(step.module_type).allowed_numbers(step.config)
    handler = {
        "ask": _ask, "quote": _quote, "decline": _decline,
        "order": _order, "note": _note, "revoke": _revoke, "clarified": _clarified,
    }[action]
    handler(db, order=order, step=step, row=row, payload=payload,
            allowed=allowed, actor=actor)
    db.flush()
    return row


def _assert_allowed(db: Session, number: Optional[int], allowed: list[int]) -> None:
    """**Darf bei diesem hier bestellt werden?** – die EINE Prüfung, zwei Aufrufer.

    **Leer heisst frei, nicht «niemand».** Beim Beschaffen steht immer mindestens ein
    Lieferant da (``clean_config`` verlangt es); beim **Bewegen** entscheidet sich der
    Spediteur zur Laufzeit – genau wie dort das offene Ziel. Ohne diese Unterscheidung
    könnte man an einem Transport nirgends anfragen.

    Sie steht hier und nicht zweimal ausgeschrieben: Anfragen und Bestellen fragen
    dasselbe, und zwei Formulierungen wären zwei Massstäbe.
    """
    if allowed:
        if number not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(f"Lieferant {number} ist für dieses Modul nicht zugelassen. "
                        f"Zugelassen: " + ", ".join(str(n) for n in allowed) + "."),
            )
        return
    # **Frei heisst nicht «irgendwer».** Wo die Definition niemanden nennt, wird zur
    # Laufzeit gesucht (``/orders/supplier-options``) – und die Suche bietet nur
    # Lieferanten an. Der Dienst muss dasselbe verlangen, sonst wäre die Auswahlliste eine
    # Bitte: dieselbe Haltung wie bei ``places.search``.
    found = (
        db.query(UserProfile)
        .filter(UserProfile.object_id == number,
                UserProfile.is_active.is_(True),
                UserProfile.role == "supplier")
        .first()
    )
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=(f"{number} ist kein Lieferant – bei diesem Modul ist niemand vorab "
                    f"zugelassen, gefragt werden kann trotzdem nur, wer als Lieferant "
                    f"geführt ist."),
        )


def _ask(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
         payload: dict[str, Any], allowed: list[int],
         actor: UserProfile) -> None:
    """Bei wem wird angefragt? Eine Zeile je genanntem Lieferanten."""
    wanted = payload.get("suppliers") or []
    if not isinstance(wanted, (list, tuple)) or not wanted:
        raise HTTPException(status_code=400, detail="Bei wem soll angefragt werden?")
    numbers: list[int] = []
    for entry in wanted:
        number = _int(entry, field="Lieferant")
        _assert_allowed(db, number, allowed)
        if number not in numbers:
            numbers.append(number)
    known = {q["supplier"]: dict(q) for q in row.quotes or []}
    row.quotes = [
        known.get(n) or {"supplier": n, "amount": None, "lead_days": None, "state": ASKED}
        for n in numbers
    ]


def _quote(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
           payload: dict[str, Any], allowed: list[int],
           actor: UserProfile) -> None:
    """Ein Preis kommt herein – **von dir getippt oder vom Lieferanten selbst**.

    Derselbe Weg, andere Hand: genau das ist der Grund, warum es keinen «Webshop-Modus»
    gibt. Ein Lieferant füllt ausschliesslich **seine** Zeile.
    """
    number = _target(row, payload, actor)
    amount = _money(payload.get("amount"), field="Offerte")
    if amount is None:
        raise HTTPException(status_code=400, detail="Eine Offerte ohne Betrag ist keine.")
    # **Ohne Lieferfrist keine Offerte.** Sie ist nicht die Kür, sondern die halbe
    # Aussage: aus ihr kommt der Liefertermin, und ohne sie gibt es kein «überfällig» –
    # zwei Angebote, von denen nur eines eine Frist nennt, sind nicht vergleichbar.
    lead = _int(payload.get("lead_days"), field="Lieferfrist")
    if lead is None or lead < 0:
        raise HTTPException(
            status_code=400,
            detail="Ohne Lieferfrist keine Offerte – aus ihr kommt der Liefertermin.",
        )
    _write(row, number, amount=str(amount), lead_days=lead, state=QUOTED)


def _decline(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
             payload: dict[str, Any], allowed: list[int],
             actor: UserProfile) -> None:
    _write(row, _target(row, payload, actor), amount=None, state=DECLINED)


def _order(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
           payload: dict[str, Any], allowed: list[int],
           actor: UserProfile) -> None:
    """**Die Zusage nach aussen.** Ab hier ist eine zweite Partei gebunden."""
    number = _int(payload.get("supplier"), field="Lieferant")
    _assert_allowed(db, number, allowed)
    amount = _money(payload.get("amount"), field="Bestellsumme")
    if amount is None:
        raise HTTPException(
            status_code=400,
            detail=("Ohne Bestellsumme keine Bestellung – aus ihr kommt der "
                    "Einstandspreis, und ein Beleg ohne Betrag sagt später nichts."),
        )
    supplier = db.query(UserProfile).filter(UserProfile.object_id == number).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"Lieferant {number} gibt es nicht.")
    row.supplier_id = supplier.id
    row.amount = amount
    row.stage = procurement.BINDING
    # **Womit bestellt wurde** – aus dem Prozess gelesen, im Moment der Zusage
    # eingefroren. Ab hier sind es die Zeilen des Belegs; ``mismatch`` vergleicht sie mit
    # dem, was heute vor dem Modul steht.
    row.ordered_lines = [{"article": a, "quantity": n}
                         for a, n in process_lines(db, order)]
    row.quotes = [
        {**q, "state": CHOSEN if q["supplier"] == number else q["state"]}
        for q in (row.quotes or [])
    ] or [{"supplier": number, "amount": str(amount), "lead_days": None, "state": CHOSEN}]


def _note(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
          payload: dict[str, Any], allowed: list[int],
          actor: UserProfile) -> None:
    """**Die Sendungsnummer.**

    Eine eigene Handlung, weil sie einen eigenen Moment hat: sie entsteht **nach** der
    Bestellung. Sie am Bestellen mitzugeben hiesse, sie zu erfinden oder das Bestellen zu
    verzögern, bis sie da ist.

    Und sie ist die eine Angabe, die ein **Lieferant** nach der Bestellung beisteuert –
    er verschickt, er kennt sie. Wo man bei ihm bestellt (seine Artikelnummer, der
    Shop-Link), steht dagegen in der **Definition**: das ist eine Eigenschaft der Paarung
    Modul × Lieferant und ändert sich nicht je Bestellung.
    """
    row.tracking = (payload.get("tracking") or "").strip() or None


def _revoke(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
            payload: dict[str, Any], allowed: list[int], actor: UserProfile) -> None:
    """**Die eine Gegenhandlung.** Was sie bewirkt, sagt die Stufe.

    Vor der Bestellung nimmt sie die Anfrage zurück (es war nichts zugesagt); ab ihr
    storniert sie – dort liegt eine Bestellung beim Lieferanten, und «zurück» heisst
    dann, ihm abzusagen.

    **Und was «die Anfrage zurücknehmen» heisst, sagt das Modul.** Wo der Einkauf der
    Zweck ist, bleibt der Beleg stehen und verliert seine Angebote. Wo er eine **Wahl**
    war (``BUY_IF_CHOSEN``), verschwindet er – sonst bliebe ein leerer Beleg zurück, und
    die Frage «wurde das eingekauft?» beantwortete sich mit «ja», obwohl es die Wahl
    nicht mehr gibt. Das ist keine zweite Regel, sondern dieselbe eine Ebene tiefer:
    zurückgenommen wird, was zugesagt war.
    """
    if row.stage != procurement.STAGES[0]:
        row.stage = procurement.CANCELLED
    if _optional(step):
        # ►► **Wer auch selbst kann, ist damit wieder bei «selbst».** ◄◄
        #
        # Der Vorgang ist beendet: die Absage bleibt als Zeile stehen (ein Storno macht
        # die Bestellung nicht ungeschehen), aber sie ist nicht mehr *der* Beleg dieses
        # Moduls – ``of_step`` liest nur den aktiven. Ohne das war ein storniertes
        # Bewegen-Modul eine **Sackgasse**: ``can`` leer, ``assert_receivable`` weist mit
        # 409 ab, und ``ensure`` fand die tote Zeile wieder. Der Auftrag stand für immer.
        row.is_active = False
        return
    row.quotes = []


def _clarified(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
               payload: dict[str, Any], allowed: list[int],
               actor: UserProfile) -> None:
    """«Der Lieferant hat zugestimmt» – jetzt darf die Menge nachziehen."""
    if mismatch(db, order, row) is None:
        raise HTTPException(
            status_code=409,
            detail="An diesem Beleg gibt es nichts zu klären – die Menge stimmt.",
        )
    row.ordered_lines = [{"article": a, "quantity": n}
                         for a, n in process_lines(db, order)]


def _target(row: Purchase, payload: dict[str, Any], actor: UserProfile) -> int:
    """Welche Angebotszeile ist gemeint? Ein Lieferant kann nur **seine** meinen."""
    number = (actor.object_id if actor.role == "supplier"
              else _int(payload.get("supplier"), field="Lieferant"))
    if any(q["supplier"] == number for q in row.quotes or []):
        return number
    raise HTTPException(
        status_code=404,
        detail=f"Lieferant {number} wurde bei diesem Beleg nicht angefragt.",
    )


def _write(row: Purchase, number: int, **fields: Any) -> None:
    """Eine Angebotszeile ändern – **durch Neubau, nie an Ort**.

    Der geladene JSONB-Wert darf nicht verändert werden: SQLAlchemy vergleicht beim
    Flush den geladenen mit dem aktuellen Wert. Ändert man die dicts in der Liste,
    sind beide gleich, die Spalte fällt aus dem ``UPDATE`` und die Offerte ist weg –
    dieselbe Falle wie in ``units._runs`` (Testnotizen #560–#562).
    """
    row.quotes = [
        {**q, **fields} if q["supplier"] == number else dict(q)
        for q in (row.quotes or [])
    ]


