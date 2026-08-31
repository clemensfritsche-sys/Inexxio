"""**Der Beleg: anlegen, führen, zurücknehmen.** Einkauf wie Verkauf.

Die eine Stelle, an der ein ``Purchase`` geschrieben wird. Sie kennt drei Fragen:

* **Was steht an?** – die Stufe und ihre Eingaben (``embed``)
* **Was wird getan?** – Anfragen · Offerieren · Zusagen · Zurücknehmen (``apply``)
* **Was, wenn sich die Grundlage ändert?** – ``rebase``

**Es gibt sie genau einmal, für beide Richtungen.** Einkauf und Verkauf sind dasselbe
Geschäft aus zwei Blickwinkeln; was sie unterscheidet, steht als Daten im ``Flow``
(``domain/procurement``) und nicht als ``if`` in diesem Modul. Ein zweiter Dienst
«sales.py» wäre dieselbe Maschine ein zweites Mal – und die zweite bekäme den nächsten
Fehlerfix nicht mit.

**Ein Modul räumt selbst auf — und legt nie einen Auftrag an.** Jede Zusage nach aussen
hat ihre Gegenhandlung an derselben Stelle: die Anfrage wird zurückgezogen, die
Bestellung storniert. Es gibt keinen Endpunkt daneben und keinen zweiten Weg. Was
dagegen **Stücke** betrifft, entscheidet ein Mensch – dieses Modul legt keinen Auftrag an
und keine Abweichung.

**Die Stufen gehören dem Beleg, nicht dem Stück.** Eine Einzelinstanz ist von der ersten
bis zur letzten Stufe durchgehend ``Im Prozess``.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain import modules, money, procurement
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderUnit, ProcessStep, Purchase,
    UserProfile,
)
from . import article_fields, invoices, payments, places, stripe_pay

#: Die Zustände einer Angebotszeile – **sie stehen im Kern** (``domain/procurement``),
#: weil auch ``services/payments`` sie liest. Hier nur die vertrauten Namen.
ASKED = procurement.ASKED
QUOTED = procurement.QUOTED
DECLINED = procurement.DECLINED
CHOSEN = procurement.CHOSEN

#: Was ein Aufrufer tun kann. **Eine Gegenhandlung** (``revoke``) statt zweier: was sie
#: bewirkt, sagt die Stufe – vor der Bestellung zieht sie die Anfrage zurück, danach
#: storniert sie. Zwei Verben für «zurück» wären zwei Wege zu derselben Sache.
#: ►►► **«Da ist Geld geflossen.»** ◄◄◄ – eine Handlung ohne Stufe.
#:
#: Sie steht bewusst **nicht** in ``ACTIONS``: dort sind die Verben eines Belegs, und die
#: hängen an seiner Stufe (``_can`` ist ihr Tor). Diese hier hat keine.
#: Geld fliesst, **nachdem** zugesagt wurde – und auch noch, wenn längst geliefert oder
#: storniert ist (eine Erstattung nach einer Stornierung ist der Normalfall). Ihr Tor ist
#: darum ``payments.assert_payable`` statt ``_can``.
#:
#: **Ein Weg, zwei Hände**: eine Überweisung trägt ein Mensch hier ein, eine Kartenzahlung
#: der Webhook des Zahlungsdienstes – über dieselbe Funktion (``payments.record``).
PAY = "pay"

#: ►►► **«Das wird jetzt gefordert.»** ◄◄◄ – die dritte Handlung ohne Stufe.
#:
#: Die Rechnung ist die **dritte Achse** neben Ware und Geld (PROCESS_CORE §9.11). Sie hat
#: aus demselben Grund keine Stufe wie ``PAY``: sie darf **vor** der Lieferung stehen
#: (Vorauszahlung) und danach (Zahlungsziel), und beides ist derselbe Vorgang zu einem
#: anderen Zeitpunkt. Ein Modus «Vorkasse ja/nein» wäre die Reihenfolge als Einstellung –
#: und ab der zweiten Einstellung hat man eine Verzweigungs-Landschaft statt einer Regel.
INVOICE = "invoice"

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

#: Welche Handlungen eine Stufe überhaupt zulässt. Nach der Erfüllung und nach einem
#: Storno ist es **keine** – dort ist der Beleg Vergangenheit.
STAGE_ACTIONS: dict[str, tuple[str, ...]] = {
    procurement.STAGES[0]: ("ask", "quote", "decline", "order", "revoke"),
    procurement.STAGES[1]: ("note", "revoke", "clarified", RECEIVE),
}


def stage_of(row: Purchase) -> str:
    """**Die Stufe, wie sie heute heisst** – die eine Lesestelle.

    Sie hiessen einmal deutsch und einkaufsspezifisch (``anfrage``/``bestellung``/
    ``wareneingang``). Migration 122 schreibt sie um; ``procurement.normalize`` ist das
    zweite Netz für eine Datenbank, die die Migration nicht gesehen hat. Jeder Vergleich
    im Dienst geht hier durch, damit es nicht eine Stelle gibt, die den alten Wert noch
    für gültig hält.
    """
    return procurement.normalize(row.stage)


def flow_of(row: Purchase) -> procurement.Flow:
    """**Der Vorgang dieses Belegs** – Wörter, Gegenpartei, Verben.

    Gelesen wird die Richtung am **Beleg**, nicht am Modultyp: ein laufender Auftrag
    trägt seinen Prozess eingefroren, und ein Beleg soll auch dann noch sagen können, was
    er war, wenn sein Modul längst anders deklariert ist.
    """
    return procurement.of(row.direction)


def _money(value: Any, *, field: str) -> Optional[Decimal]:
    """Ein Betrag – oder ``None``, wenn nichts angegeben ist.

    Gerechnet wird in ``domain/money``; hier wird nur die Abwesenheit vom Fehler getrennt
    und der Fehler in die Sprache der API übersetzt (400 statt ``ValueError``).
    """
    if value in (None, ""):
        return None
    try:
        return money.parse(value, field=field)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _int(value: Any, *, field: str) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"«{value}» ist keine Zahl ({field}).")
    return number


def steps_of(db: Session, order: Order) -> list[ProcessStep]:
    """Die Module dieses Auftrags, die einen **Beleg** tragen – in ihrer Folge.

    **Nicht EIN Modultyp.** Gefragt wird die Deklaration (``Module.trades``), nicht der
    Name: ``module_type == 'einkauf'`` wäre die Stelle, an der der Verkauf vergessen
    wird – und der nächste handelnde Typ ebenso.
    """
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id,
                ProcessStep.module_type.in_(modules.trading_types()))
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

    **Jedes handelnde Modul bekommt einen** (``Module.trades``): ein Handel *ist* sein
    Beleg – es gibt hier nichts zu wählen. Die frühere Unterscheidung «immer ↔ falls
    gewählt» gehörte zum Beleg **im** Bewegen-Modul, und den gibt es nicht mehr: wer
    einkauft, setzt ein Einkaufs-Modul in die Kette.

    Idempotent: gibt es den Beleg schon, passiert nichts.
    """
    made: list[Purchase] = []
    for step in steps_of(db, order):
        row = _create(db, order=order, step=step)
        if row is not None:
            made.append(row)
    if made:
        db.flush()
    return made


def _create(db: Session, *, order: Order, step: ProcessStep) -> Optional[Purchase]:
    """Einen Beleg anlegen, wenn es noch keinen gibt. ``None`` = gab es schon.

    **Die Richtung wird hier festgeschrieben**, aus der Deklaration des Moduls
    (``Module.direction``). Ab dann gehört sie dem Beleg: er soll auch in zehn Jahren noch
    sagen können, was er war – und nicht, was sein Modultyp inzwischen deklariert.
    """
    if of_step(db, step.id) is not None:
        return None
    row = Purchase(order_id=order.id, step_id=step.id,
                   direction=procurement.assert_direction(
                       modules.get(step.module_type).direction),
                   stage=procurement.STAGES[0], quotes=[])
    db.add(row)
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


#: **Die Zahlungsaufforderung** – kein Verb am Beleg, sondern eine Adresse
#: (``/payment-link``). Sie steht trotzdem in ``can``, weil «was darf ich hier tun» EINE
#: Frage ist: eine zweite Liste wäre ein zweiter Massstab, und die Oberfläche müsste
#: entscheiden, welcher gerade gilt (derselbe Grund wie bei ``RECEIVE``).
LINK = "link"


def _can(db: Optional[Session], row: Purchase,
         viewer: Optional[UserProfile]) -> list[str]:
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
    allowed = list(STAGE_ACTIONS.get(stage_of(row), ()))
    # **Geld läuft neben den Stufen.** Es fliesst, sobald eine Summe zugesagt ist – und
    # auch noch, wenn längst geliefert oder storniert ist (eine Erstattung nach einer
    # Stornierung ist der Normalfall). Darum steht ``pay`` nicht in ``STAGE_ACTIONS``,
    # sondern hängt an derselben Bedingung, die ``payments.assert_payable`` durchsetzt.
    if db is not None and row.amount is not None \
            and stage_of(row) != procurement.STAGES[0]:
        allowed.append(PAY)
        # **Die Forderung läuft ebenso neben den Stufen** – und aus demselben Grund: sie
        # darf vor der Lieferung stehen (Vorauszahlung) und danach (Zahlungsziel). Wer
        # sie an die Stufe hängte, machte aus der Reihenfolge eine Regel.
        allowed.append(INVOICE)
        # Der Zahllink zusätzlich nur, wo es einen Dienst gibt **und** etwas offen ist.
        # Ein Knopf, der nie etwas tun kann, ist kein Angebot.
        if stripe_pay.available() and payments.balance(db, row).open > 0:
            allowed.append(LINK)
    if viewer is not None and viewer.role == "supplier":
        allowed = [a for a in allowed if a in SUPPLIER_ACTIONS]
    return allowed


def _undo(row: Purchase) -> str:
    """**Wie heisst hier «zurück»?** – ein Wort aus Stufe × Richtung.

    Es gibt genau **eine** Gegenhandlung (``revoke``); was sie bewirkt, hängt daran, ob
    schon etwas zugesagt ist. Das Wort dafür gehört an dieselbe Stelle wie die Wirkung –
    die Oberfläche schreibt es nicht selbst hin, sonst stünde beim nächsten Fall ein Satz
    da, den keine Regel deckt.

    Die dritte Fassung ist entfallen: «Doch selbst erledigen» gab es, solange ein
    Bewegen-Modul einen Beleg *wählen* konnte. Wer einkauft, setzt jetzt ein
    Einkaufs-Modul in die Kette – und ein Modul nimmt man nicht zurück, man löscht es.
    """
    flow = flow_of(row)
    if stage_of(row) != procurement.STAGES[0]:
        return flow.undo_after
    return flow.undo_before


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
    if stage_of(row) != procurement.BINDING or not row.ordered_lines:
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
        if stage_of(row) in (procurement.STAGES[-1], procurement.CANCELLED):
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
    flow = flow_of(row)
    allowed = module.parties_of(config)
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
    can = _can(db, row, viewer)
    balance = payments.balance(db, row)
    due = invoices.due_on(db, row)
    return {
        "stage": stage_of(row),
        "stages": _stages(row),
        "can": can,
        # **Die Identität des Vorgangs reist mit ihm** – wie Farbe und Beschriftung eines
        # Moduls (``ModuleFacts``). Die Ausführungsstelle schlägt nichts in einem Katalog
        # nach, den nur der Editor lädt; und weil beide dieselbe Quelle lesen, sieht ein
        # Einkauf im Bewegen-Modul aus wie einer im Beschaffen-Modul.
        "label": flow.label,
        "tone": flow.tone,
        # ►►► **In welche Richtung geht dieser Vorgang?** ◄◄◄ Die Oberfläche braucht sie
        # für kein einziges ``if`` – Wörter, Verben und Verben-Zustände reisen fertig mit.
        # Sie steht hier, damit eine **Liste** von Belegen sortiert und gefiltert werden
        # kann, ohne jeden einzeln zu befragen.
        "direction": flow.direction,
        # Wen die Auswahl anbieten darf. Sie kommt aus derselben Regel, die ``apply``
        # danach durchsetzt (``_assert_allowed``) – eine Liste, die etwas anbietet, das
        # der Dienst abweist, wäre schlimmer als keine.
        "party_role": flow.party_role,
        "party_word": flow.party_word,
        # **Ein Wort für die eine Gegenhandlung** – oder keines, wenn sie hier nicht geht.
        "undo": _undo(row) if "revoke" in can else None,
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
             "lead_days": q.get("lead_days"),
             "payment_days": q.get("payment_days"),
             "state": q.get("state", ASKED)}
            for q in quotes
        ],
        "supplier_object_id": chosen.object_id if chosen and won else None,
        "supplier_name": chosen.display_name if chosen and won else None,
        "amount": float(row.amount) if row.amount is not None and won else None,
        "currency": row.currency,
        "tracking": row.tracking if won else None,
        "clarify_quantity": mismatch(db, order, row),
        # ►►► **Forderung und Geld – lauter Ableitungen, keine Spalte.** ◄◄◄
        #
        # ``open`` ist **Forderungen − Zahlungen** und darf negativ sein (dann schulden
        # wir). ``uncharged`` ist «zugesagt, noch nicht berechnet» – die Zahl, die es vor
        # der dritten Achse gar nicht geben konnte, und zugleich die Vorgabe für die
        # nächste Rechnung. ``due_on`` ist die **früheste offene** Fälligkeit, nicht mehr
        # eine Rechnung aus dem Zusagedatum: zwei Rechnungen haben zwei Fälligkeiten.
        # Wer nicht den Zuschlag hat, sieht davon nichts – was ein anderer zahlt, geht ihn
        # nichts an.
        "paid": float(balance.paid) if won else None,
        "charged": float(balance.charged) if won else None,
        "uncharged": float(balance.uncharged)
        if won and balance.uncharged is not None else None,
        "open": float(balance.open) if won and balance.total is not None else None,
        "due_on": due.isoformat() if won and due else None,
        "overdue": invoices.is_overdue(db, row) if won else False,
        "entries": payments.entries(db, row) if won else [],
        "invoices": invoices.entries(db, row) if won else [],
        # **Die Vorgabe für die nächste Nummer** – sie kommt vom Server, weil dort die
        # Regel wohnt (``<Auftragsnummer>-<laufend>``, beim Einkauf ``None``: dort
        # nummeriert die Gegenpartei). Eine im Browser gebaute Nummer wäre die zweite
        # Fassung desselben Formats.
        "next_invoice_number": invoices.next_number(db, row) if won else None,
        # **Das Wort auf dem Knopf kommt vom Flow**, wie jedes andere: «Rechnung stellen»
        # ↔ «Rechnung erfassen». Wir stellen unsere, seine erfassen wir – und das ist
        # derselbe Unterschied wie bei der Nummer, nur in Worten.
        "invoice_verb": flow.invoice_verb,
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
    flow = flow_of(row)
    stage = stage_of(row)
    order_of = {key: i for i, key in enumerate(procurement.STAGES)}
    cancelled = stage == procurement.CANCELLED
    here = order_of.get(stage, order_of[procurement.BINDING] if cancelled else -1)
    ends_here = (procurement.STAGES[-1], ) if not cancelled else procurement.STAGES
    return [
        {"key": key, "label": flow.label_of(key),
         "verb": flow.stage_verbs.get(key, "") if i == here and not cancelled else "",
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
    flow = flow_of(row)
    if stage_of(row) == procurement.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label_of(procurement.BINDING)}» ist storniert – "
                    f"da kommt nichts mehr."),
        )
    if stage_of(row) == procurement.STAGES[0]:
        raise HTTPException(
            status_code=409,
            detail=(f"Es steht erst «{flow.label_of(procurement.STAGES[0])}» – ohne "
                    f"Zusage gibt es nichts zu erfüllen, und ein Beleg ohne Anlass ist "
                    f"keiner."),
        )


def note_receipt(db: Session, *, order: Order, step: ProcessStep) -> None:
    """Nach ``confirm_step``: steht nichts mehr davor, ist die Ware **da**.

    Teillieferung braucht dafür keine eigene Regel: ``confirm_step`` ist ein
    Teilabschluss, und solange noch Stücke vor dem Modul stehen, bleibt der Beleg in
    «Bestellung». Der Einstandspreis wandert beim Abschluss an den Artikel – Summe ÷
    Menge, an genau einer Stelle gerechnet.
    """
    row = of_step(db, step.id)
    if row is None or stage_of(row) != procurement.BINDING:
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

    **Und nur, wo der Beleg für das TEIL zahlt** (``Module.landed_cost_for``). Beim
    Verkauf nie; beim Einkauf sagt es die Definition. Die Frage hing einmal am
    **Modultyp** – «Beschaffen» ja, «Bewegen» (der Transport) nein –, und seit der
    Transport ein ganz gewöhnliches Einkaufs-Modul ist, kann der Typ sie nicht mehr
    beantworten: beide sind Einkäufe. Ohne die Angabe hätte derselbe Artikel, zweimal
    verschickt, den **Frachttarif als Einstandspreis** – ein stiller Datenfehler, mit dem
    danach kalkuliert wird.
    """
    if not modules.get(step.module_type).landed_cost_for(step.config):
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
    if action not in ACTIONS and action not in (PAY, INVOICE):
        raise HTTPException(
            status_code=400,
            detail=f"«{action}» ist keine Handlung. Bekannt: "
                   + ", ".join((PAY, INVOICE) + ACTIONS) + ".",
        )
    # ►► **«Da ist Geld geflossen.»** ◄◄ Die Handlung, die *neben* den Stufen läuft. Sie
    # geht aus demselben Grund nicht durch ``_can``: Geld fliesst auch noch, wenn längst
    # geliefert oder storniert ist. Ihr Tor ist, ob überhaupt eine Summe zugesagt wurde.
    if action == PAY:
        return _pay(db, step=step, payload=payload)
    # ►► **«Das wird jetzt gefordert.»** ◄◄ Die dritte Handlung neben den Stufen, aus
    # demselben Grund ohne Tor in ``_can``: eine Rechnung darf vor der Lieferung stehen
    # und danach. Ihr Tor ist dasselbe wie beim Geld – es muss eine Summe zugesagt sein.
    if action == INVOICE:
        return _invoice(db, step=step, payload=payload)
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dieses Modul hat keinen Beleg.")
    flow = flow_of(row)
    if stage_of(row) == procurement.CANCELLED:
        raise HTTPException(status_code=409, detail="Dieser Beleg ist storniert.")
    if stage_of(row) == procurement.STAGES[-1]:
        raise HTTPException(
            status_code=409,
            detail=(f"Der Beleg steht auf «{flow.label_of(procurement.STAGES[-1])}» – "
                    f"daran ist nichts mehr zu ändern."),
        )
    # **Dieselbe Tabelle, die es der Oberfläche sagt, weist hier ab.** Sonst wäre ``can``
    # eine Behauptung neben der Regel – und die beiden liefen beim nächsten Verb
    # auseinander. Der Unterschied ist nur, **warum** es nicht geht: die Stufe (409) oder
    # die Rolle (403).
    if action not in _can(db, row, actor):
        if action in STAGE_ACTIONS.get(stage_of(row), ()):
            raise HTTPException(
                status_code=403,
                detail=("Ein Lieferant offeriert oder lehnt ab und trägt die "
                        "Sendungsnummer nach – bestellt wird beim Besteller."),
            )
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» geht an dieser Stelle nicht – der Beleg steht auf "
                    f"«{flow.label_of(stage_of(row))}»."),
        )

    # **Wer zugelassen ist, sagt das Modul** – der erste der beiden Fäden, die den Beleg
    # einmal an «Beschaffen» banden. Leer heisst frei (``Module.parties_of``).
    allowed = modules.get(step.module_type).allowed_numbers(step.config)
    handler = {
        "ask": _ask, "quote": _quote, "decline": _decline,
        "order": _order, "note": _note, "revoke": _revoke, "clarified": _clarified,
    }[action]
    handler(db, order=order, step=step, row=row, payload=payload,
            allowed=allowed, actor=actor)
    db.flush()
    return row


def _pay(db: Session, *, step: ProcessStep, payload: dict[str, Any]) -> Purchase:
    """**Eine Zeile Geld buchen** – und den Beleg unverändert zurückgeben.

    Was hier **nicht** passiert: die Stufe ändern. Geld und Ware sind zwei Ebenen; eine
    Zahlung macht aus einem Angebot keine Zusage, und eine ausbleibende macht aus einer
    Lieferung keine Nicht-Lieferung. Wer beides koppelte, könnte weder Vorkasse noch
    Rechnung abbilden – und «bezahlt» wäre eine vierte Stufe, obwohl nur drei Dinge
    unumkehrbar sind.
    """
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dieses Modul hat keinen Beleg.")
    payments.assert_payable(row)
    payments.record(
        db, purchase=row,
        amount=payload.get("amount"),
        method=payload.get("method"),
        reference=payload.get("reference"),
        paid_at=_as_date(payload.get("paid_at")),
        note=payload.get("note_text"),
        # ►► **Die Menschentür ist enger als die Tabelle** (Testnotiz #782). ◄◄
        #
        # Eine Kartenzahlung tippt niemand ab – sie entsteht beim Zahlungsdienst und kommt
        # über den Webhook, der ``payments.record`` **ohne** diese Verengung ruft. Wer sie
        # hier von Hand erfassen könnte, öffnete eine zweite Quelle für dieselbe Buchung:
        # die eine aus der Wirklichkeit, die andere aus einer Erinnerung.
        manual=True,
    )
    return row


def _invoice(db: Session, *, step: ProcessStep, payload: dict[str, Any]) -> Purchase:
    """►►► **Eine Forderung stellen** – die dritte Achse neben Ware und Geld. ◄◄◄

    **Sie hat keine Stufe** (wie ``pay`` und ``buy``): eine Rechnung macht aus einem
    Angebot keine Zusage und aus nicht gelieferter Ware keine gelieferte. Sie darf
    **vor** der Lieferung stehen (Vorauszahlung) oder danach (Zahlungsziel) – und genau
    deshalb gibt es keinen Modus, keinen Schalter und keine Einstellung dafür. Wer zuerst
    Geld sehen will, stellt zuerst die Rechnung; das System hält fest, in welcher
    Reihenfolge gehandelt wurde, statt eine vorzuschreiben (PROCESS_CORE §9.11).

    **Die Automatik steckt in den Vorgaben, nicht in einem Modus:** der Betrag ist
    vorbelegt mit *zugesagt − bereits berechnet*, die Fälligkeit mit *heute + vereinbarte
    Zahlungsfrist*, die Nummer mit ``<Auftragsnummer>-<laufend>`` (beim Einkauf mit
    nichts – dort nummeriert die Gegenpartei). Der Normalfall ist damit ein Klick, und
    jede Abweichung ist eine Eingabe statt eines zweiten Wegs.
    """
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dieses Modul hat keinen Beleg.")
    payments.assert_payable(row)
    issued = _as_date(payload.get("issued_on")) or date.today()
    amount = payload.get("amount")
    if amount in (None, ""):
        amount = payments.balance(db, row).uncharged
    invoices.record(
        db, purchase=row,
        amount=amount,
        number=payload.get("number") or invoices.next_number(db, row),
        issued_on=issued,
        due_on=_as_date(payload.get("due_on"))
        or invoices.default_due(row, issued=issued),
        note=payload.get("note_text"),
    )
    return row


def _as_date(value: Any) -> Optional[date]:
    """``YYYY-MM-DD`` – oder ``None``. Alles andere ist ein Fehler mit dem Wert im Satz."""
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"«{value}» ist kein Datum (erwartet: JJJJ-MM-TT).",
        )


def _assert_allowed(db: Session, row: Purchase, number: Optional[int],
                    allowed: list[int]) -> None:
    """**Darf mit diesem hier gehandelt werden?** – die EINE Prüfung, zwei Aufrufer.

    **Leer heisst frei, nicht «niemand».** Beim Beschaffen steht immer mindestens ein
    Lieferant da (``parties = REQUIRED``); beim **Bewegen** entscheidet sich der Spediteur
    zur Laufzeit – genau wie dort das offene Ziel –, und beim **Verkauf** weiss beim
    Modellieren niemand, wer einmal kauft. Ohne diese Unterscheidung könnte man an einem
    Transport nirgends anfragen und nichts verkaufen.

    Sie steht hier und nicht zweimal ausgeschrieben: Anfragen und Zusagen fragen dasselbe,
    und zwei Formulierungen wären zwei Massstäbe.
    """
    flow = flow_of(row)
    if allowed:
        if number not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(f"{flow.party_word} {number} ist für dieses Modul nicht "
                        f"zugelassen. Zugelassen: "
                        + ", ".join(str(n) for n in allowed) + "."),
            )
        return
    # **Wo die Definition niemanden nennt, wird zur Laufzeit gesucht**
    # (``/orders/party-options``) – und die Suche liest **dieselbe** Angabe wie diese
    # Prüfung (``Flow.party_roles``). Zwei Listen wären zwei Massstäbe, und die Auswahl
    # böte an, was der Dienst danach abweist.
    #
    # **Leer heisst frei** (Testnotiz #779): beim Verkauf darf jeder kaufen – auch ein
    # Mitarbeiter, auch ein Lieferant. Beim Einkauf ist «Lieferant» dagegen eine
    # Zulassung, die wir vergeben; dort bleibt die Rolle eine echte Bedingung.
    query = db.query(UserProfile).filter(UserProfile.object_id == number,
                                         UserProfile.is_active.is_(True))
    if flow.party_roles:
        query = query.filter(UserProfile.role.in_(flow.party_roles))
    if query.first() is None:
        who = f"ist kein {flow.party_word}" if flow.party_roles else "gibt es nicht"
        raise HTTPException(
            status_code=400,
            detail=(f"{number} {who} – bei diesem Modul ist niemand vorab zugelassen, "
                    f"gehandelt werden kann trotzdem nur mit einem Datensatz, den es "
                    f"gibt."),
        )


def _ask(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
         payload: dict[str, Any], allowed: list[int],
         actor: UserProfile) -> None:
    """**Mit wem?** Eine Zeile je genannter Gegenpartei.

    Beim Einkauf ist das die Anfrage bei einem oder mehreren Lieferanten; beim **Verkauf**
    ist es das Angebot an einen Kunden. Derselbe Vorgang, und darum dieselbe Handlung –
    ein «offer»-Verb daneben wäre ein zweiter Weg zu einer Sache, die es schon gibt.
    """
    flow = flow_of(row)
    wanted = payload.get("suppliers") or []
    if not isinstance(wanted, (list, tuple)) or not wanted:
        raise HTTPException(
            status_code=400,
            detail=f"Welcher {flow.party_word} ist gemeint?",
        )
    numbers: list[int] = []
    for entry in wanted:
        number = _int(entry, field=flow.party_word)
        _assert_allowed(db, row, number, allowed)
        if number not in numbers:
            numbers.append(number)
    known = {q["supplier"]: dict(q) for q in row.quotes or []}
    row.quotes = [
        known.get(n) or {"supplier": n, "amount": None, "lead_days": None,
                         "payment_days": None, "state": ASKED}
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
    # **Die Zahlungsfrist steht daneben, und sie ist freiwillig.** Sie beantwortet dieselbe
    # Art Frage wie die Lieferfrist, nur für das Geld – darum derselbe Ort. Fehlt sie, gibt
    # es kein Fälligkeitsdatum und damit kein «überfällig»: was nicht bekannt ist, wird
    # weggelassen statt geraten (dieselbe Regel wie bei der Herkunft in ``_route``).
    days = _int(payload.get("payment_days"), field="Zahlungsfrist")
    if days is not None and days < 0:
        raise HTTPException(
            status_code=400, detail="Eine Zahlungsfrist ist nicht negativ.")
    _write(row, number, amount=str(amount), lead_days=lead, payment_days=days,
           state=QUOTED)


def _decline(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
             payload: dict[str, Any], allowed: list[int],
             actor: UserProfile) -> None:
    _write(row, _target(row, payload, actor), amount=None, state=DECLINED)


def _order(db: Session, *, order: Order, step: ProcessStep, row: Purchase,
           payload: dict[str, Any], allowed: list[int],
           actor: UserProfile) -> None:
    """**Die Zusage nach aussen.** Ab hier ist eine zweite Partei gebunden.

    Beim Einkauf ist es unsere Bestellung, beim Verkauf die Zusage des Kunden – in beiden
    Fällen der Moment, ab dem eine stille Änderung ein Beleg wäre, der nicht mehr stimmt.
    """
    flow = flow_of(row)
    number = _int(payload.get("supplier"), field=flow.party_word)
    _assert_allowed(db, row, number, allowed)
    amount = _money(payload.get("amount"), field="Summe")
    if amount is None:
        raise HTTPException(
            status_code=400,
            detail=(f"Ohne Summe keine «{flow.label_of(procurement.BINDING)}» – aus ihr "
                    f"kommt, was offen ist, und ein Beleg ohne Betrag sagt später nichts."),
        )
    supplier = db.query(UserProfile).filter(UserProfile.object_id == number).first()
    if supplier is None:
        raise HTTPException(
            status_code=404, detail=f"{flow.party_word} {number} gibt es nicht.")
    row.supplier_id = supplier.id
    row.amount = amount
    row.stage = procurement.BINDING
    # **Wann das Geld fällig wird, hängt an der Zusage** – ab hier läuft die Frist.
    row.committed_on = date.today()
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

    **Der Beleg bleibt stehen und verliert seine Angebote.** Er ist der Zweck des Moduls –
    ihn zu löschen hiesse, den Schritt seiner Sache zu berauben; wer gar nicht handeln
    will, entfernt das Modul aus der Kette. (Die frühere zweite Fassung – der Beleg
    verschwindet – gehörte zum Beleg *im* Bewegen-Modul, wo der Handel eine Wahl war.)
    """
    if row.stage != procurement.STAGES[0]:
        row.stage = procurement.CANCELLED
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


