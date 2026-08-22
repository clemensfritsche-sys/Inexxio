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
from sqlalchemy.orm import Session

from ..domain import modules
from ..domain.modules import Beschaffen
from ..models import Article, Order, OrderUnit, ProcessStep, Purchase, UserProfile

#: Die Zustände einer Angebotszeile. ``gewaehlt`` entsteht nicht durch Tippen, sondern
#: dadurch, dass bei dieser Zeile bestellt wurde – ein Zustand ist eine Folge.
ASKED, QUOTED, DECLINED, CHOSEN = "angefragt", "offeriert", "abgelehnt", "gewaehlt"

#: Was ein Aufrufer tun kann. **Eine Gegenhandlung** (``revoke``) statt zweier: was sie
#: bewirkt, sagt die Stufe – vor der Bestellung zieht sie die Anfrage zurück, danach
#: storniert sie. Zwei Verben für «zurück» wären zwei Wege zu derselben Sache.
ACTIONS = ("ask", "quote", "decline", "order", "note", "revoke", "clarified")

#: Was ein **Lieferant** selbst darf: seine eigene Zeile füllen oder ablehnen. Bestellen
#: tut der Besteller – die Verantwortungstrennung ist der Sinn des Portals.
SUPPLIER_ACTIONS = ("quote", "decline")


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


def steps_of(db: Session, order: Order) -> list[ProcessStep]:
    """Die Beschaffungs-Module dieses Auftrags, in ihrer Reihenfolge."""
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id,
                ProcessStep.module_type == modules.BESCHAFFEN)
        .order_by(ProcessStep.position)
        .all()
    )


def unit_count(db: Session, order: Order) -> int:
    """**Wie viele Einzelinstanzen gehören diesem Auftrag gerade?**

    Die offene Zugehörigkeit – dieselbe Grösse, aus der der Prozess überall rechnet. Sie
    ist die Grundlage der Bestellmenge und zugleich das, wogegen ``rebase`` prüft.
    """
    return (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
        .count()
    )


def quantity_of(db: Session, order: Order, row: Purchase) -> Decimal:
    """**Die Bestellmenge ist keine Eingabe – sie ist, was vor dem Modul steht.**

    Ein Beschaffungs-Modul sitzt in einem Prozess: wie viel bestellt wird, sagen die
    Einzelinstanzen, die diesem Auftrag gehören (``unit_count``). Sie zusätzlich tippen zu
    lassen wäre eine **zweite Aussage über dieselbe Sache** – und die getippte gewinnt,
    auch wenn sie falsch ist.

    **Ab der Bestellung ist sie eingefroren** (``ordered_for``): dort ist eine zweite
    Partei gebunden, und was bestellt wurde, ändert sich nicht mehr dadurch, dass der
    Auftrag später Stücke verliert. Genau diese Differenz meldet ``mismatch``.

    *Eine Mindestbestellmenge wird hier bewusst nicht aufgeschlagen*: das Modul erzeugt
    keine Einzelinstanzen (§9.9), für die Übermenge gäbe es also gar keine Stücke – sie
    käme an und existierte im System nicht.
    """
    if row.ordered_for is not None:
        return Decimal(row.ordered_for)
    return Decimal(unit_count(db, order))


def instantiate_for_order(db: Session, order: Order) -> list[Purchase]:
    """Bei der Freigabe: je Beschaffungs-Modul **einen** Beleg.

    **Ein Beleg je Modul, nicht je Position.** Was bestellt wird, steht in der
    Konfiguration des Moduls – es gibt also genau einen Artikel je Modul. Wer zwei Dinge
    einkauft, modelliert zwei Module; das ist dieselbe Antwort wie überall, wo eine Liste
    dieselbe Frage n-mal stellt.

    Idempotent: gibt es den Beleg schon, passiert nichts.
    """
    made: list[Purchase] = []
    for step in steps_of(db, order):
        if db.query(Purchase).filter(Purchase.step_id == step.id).first():
            continue
        wanted = (step.config or {}).get(Beschaffen.ARTICLE)
        article = (
            db.query(Article).filter(Article.object_id == wanted).first() if wanted else None
        )
        if article is None:
            raise HTTPException(
                status_code=400,
                detail=(f"«Beschaffen» verweist auf Artikel {wanted} – den gibt es nicht. "
                        f"Ohne ihn steht nicht fest, was bestellt werden soll."),
            )
        row = Purchase(
            order_id=order.id, step_id=step.id, article_id=article.id,
            stage=Beschaffen.STAGES[0], quotes=[],
        )
        db.add(row)
        made.append(row)
    if made:
        db.flush()
    return made


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


def of_step(db: Session, step_id: int) -> Optional[Purchase]:
    return db.query(Purchase).filter(Purchase.step_id == step_id).first()


# ─── Was sich ändert, wenn die Grundlage kleiner wird ────────────────────────


def mismatch(db: Session, order: Order, row: Purchase) -> Optional[int]:
    """**Rechnet dieser Beleg noch mit der richtigen Menge?** ``None`` = ja.

    Verglichen wird, womit **bestellt** wurde (``ordered_for``), mit dem, was der Auftrag
    heute hält. Vor der Bestellung gibt es kein ``ordered_for`` – dort gibt es auch nichts
    zu klären, weil ``rebase`` die Zahl still nachzieht.
    """
    if row.stage != Beschaffen.BINDING or row.ordered_for is None:
        return None
    now = unit_count(db, order)
    return now if Decimal(now) != Decimal(row.ordered_for) else None


def rebase(db: Session, order: Order) -> None:
    """**Die Grundlage hat sich geändert** – was folgt, hängt an der Stufe.

    *Vor* der Bestellung ist niemand ausser uns beteiligt: die Menge zieht **still** nach.
    *Ab* der Bestellung liegt sie beim Lieferanten – dann ändert das System nichts,
    sondern **meldet** (``mismatch``) und wartet auf ``clarified``. Eine stille Änderung
    wäre ein Beleg, der nicht mehr stimmt, und niemand hätte es gemerkt.

    Bleibt **nichts** übrig, ist der Beleg gegenstandslos: ``storniert``. Das ist keine
    zusätzliche Regel, sondern dieselbe eine Stufe weiter – man bestellt nichts für null
    Stück.

    **Selbstheilend**: die Funktion vergleicht und tut nichts, wenn alles stimmt. Ein
    verpasster Aufruf korrigiert sich beim nächsten.
    """
    rows = db.query(Purchase).filter(Purchase.order_id == order.id).all()
    if not rows:
        return
    now = unit_count(db, order)
    for row in rows:
        if row.stage in (Beschaffen.STAGES[-1], Beschaffen.CANCELLED):
            continue                      # Vergangenheit wird nicht umgeschrieben
        if now == 0:
            row.stage = Beschaffen.CANCELLED
    db.flush()


def _article(db: Session, row: Purchase) -> Optional[Article]:
    return db.query(Article).filter(Article.id == row.article_id).first()


# ─── Was die Ausführungsstelle sieht ─────────────────────────────────────────


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
    article = _article(db, row)
    allowed = (step.config or {}).get(Beschaffen.SUPPLIERS) or []
    names = _names(db, allowed + [q["supplier"] for q in row.quotes or []])
    mine = viewer.object_id if viewer is not None and viewer.role == "supplier" else None

    quotes = [q for q in (row.quotes or []) if mine is None or q["supplier"] == mine]
    chosen = (
        db.query(UserProfile).filter(UserProfile.id == row.supplier_id).first()
        if row.supplier_id else None
    )
    return {
        "stage": row.stage,
        "stages": _stages(row),
        "article_object_id": article.object_id if article else 0,
        "article_name": article.name if article else "",
        "unit": getattr(article, "unit", "") or "",
        "quantity": float(quantity_of(db, order, row)),
        "allowed": [
            {"supplier_object_id": n, "supplier_name": names.get(n, ""), "state": ASKED}
            for n in allowed if mine is None or n == mine
        ],
        "quotes": [
            {"supplier_object_id": q["supplier"],
             "supplier_name": names.get(q["supplier"], ""),
             "amount": float(q["amount"]) if q.get("amount") not in (None, "") else None,
             "lead_days": q.get("lead_days"), "state": q.get("state", ASKED)}
            for q in quotes
        ],
        "supplier_object_id": chosen.object_id if chosen else None,
        "supplier_name": chosen.display_name if chosen else None,
        "amount": float(row.amount) if row.amount is not None else None,
        "currency": row.currency,
        "reference": row.reference,
        "clarify_quantity": mismatch(db, order, row),
    }


def _stages(row: Purchase) -> list[dict[str, Any]]:
    """Die drei Stufen mit ihrem Zustand.

    **Storniert ist keine Stufe**: dann ist keine aktiv – aber die Kette steht still da,
    wo sie stehengeblieben ist. Was einmal geschehen ist, bleibt gegangen; ein Storno
    macht die Bestellung nicht ungeschehen, es sagt nur, dass nichts mehr ankommt.
    Storniert wird ausschliesslich aus der Bestellung heraus (davor nimmt ``revoke`` die
    Anfrage zurück), also ist das die Stelle, an der die Kette endet.
    """
    order_of = {key: i for i, key in enumerate(Beschaffen.STAGES)}
    cancelled = row.stage == Beschaffen.CANCELLED
    here = order_of.get(row.stage, order_of[Beschaffen.BINDING] if cancelled else -1)
    ends_here = (Beschaffen.STAGES[-1], ) if not cancelled else Beschaffen.STAGES
    return [
        {"key": key, "label": Beschaffen.STAGE_LABELS[key],
         "verb": Beschaffen.STAGE_VERBS.get(key, "") if i == here and not cancelled else "",
         "done": i < here or (i == here and key in ends_here),
         "active": i == here and not cancelled and key != Beschaffen.STAGES[-1]}
        for i, key in enumerate(Beschaffen.STAGES)
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
    if row.stage == Beschaffen.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail="Diese Bestellung ist storniert – es kommt nichts mehr an.",
        )
    if row.stage == Beschaffen.STAGES[0]:
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
    if row is None or row.stage != Beschaffen.BINDING:
        return
    waiting = (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
                OrderUnit.current_step_id == step.id)
        .count()
    )
    if waiting:
        return
    row.stage = Beschaffen.STAGES[-1]
    article = _article(db, row)
    ordered = quantity_of(db, order, row)
    if article is not None and row.amount is not None and ordered:
        article.landed_unit_cost = (Decimal(row.amount) / ordered
                                    ).quantize(Decimal("0.0001"))
    db.flush()


# ─── Die sechs Handlungen ────────────────────────────────────────────────────


def apply(db: Session, *, order: Order, step: ProcessStep, action: str,
          payload: dict[str, Any], actor: UserProfile) -> Purchase:
    """**Eine Handlung am Beleg.** Was erlaubt ist, hängt an der Stufe und an der Rolle."""
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dieses Modul hat keinen Beleg.")
    if action not in ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"«{action}» ist keine Handlung. Bekannt: " + ", ".join(ACTIONS) + ".",
        )
    is_supplier = actor.role == "supplier"
    if is_supplier and action not in SUPPLIER_ACTIONS:
        raise HTTPException(
            status_code=403,
            detail=("Ein Lieferant offeriert oder lehnt ab – bestellt wird beim "
                    "Besteller."),
        )
    if row.stage == Beschaffen.CANCELLED:
        raise HTTPException(status_code=409, detail="Dieser Beleg ist storniert.")
    if row.stage == Beschaffen.STAGES[-1]:
        raise HTTPException(
            status_code=409,
            detail="Die Ware ist eingetroffen – daran ist nichts mehr zu ändern.",
        )

    allowed = (step.config or {}).get(Beschaffen.SUPPLIERS) or []
    handler = {
        "ask": _ask, "quote": _quote, "decline": _decline,
        "order": _order, "note": _note, "revoke": _revoke, "clarified": _clarified,
    }[action]
    handler(db, order=order, row=row, payload=payload, allowed=allowed, actor=actor)
    db.flush()
    return row


def _ask(db: Session, *, order: Order, row: Purchase, payload: dict[str, Any],
         allowed: list[int], actor: UserProfile) -> None:
    """Bei wem wird angefragt? Eine Zeile je genanntem Lieferanten."""
    _only_in(row, Beschaffen.STAGES[0], "Angefragt wird vor der Bestellung.")
    wanted = payload.get("suppliers") or []
    if not isinstance(wanted, (list, tuple)) or not wanted:
        raise HTTPException(status_code=400, detail="Bei wem soll angefragt werden?")
    numbers: list[int] = []
    for entry in wanted:
        number = _int(entry, field="Lieferant")
        if number not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(f"Lieferant {number} ist für dieses Modul nicht zugelassen. "
                        f"Zugelassen: " + ", ".join(str(n) for n in allowed) + "."),
            )
        if number not in numbers:
            numbers.append(number)
    known = {q["supplier"]: dict(q) for q in row.quotes or []}
    row.quotes = [
        known.get(n) or {"supplier": n, "amount": None, "lead_days": None, "state": ASKED}
        for n in numbers
    ]


def _quote(db: Session, *, order: Order, row: Purchase, payload: dict[str, Any],
           allowed: list[int], actor: UserProfile) -> None:
    """Ein Preis kommt herein – **von dir getippt oder vom Lieferanten selbst**.

    Derselbe Weg, andere Hand: genau das ist der Grund, warum es keinen «Webshop-Modus»
    gibt. Ein Lieferant füllt ausschliesslich **seine** Zeile.
    """
    _only_in(row, Beschaffen.STAGES[0], "Offeriert wird vor der Bestellung.")
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


def _decline(db: Session, *, order: Order, row: Purchase, payload: dict[str, Any],
             allowed: list[int], actor: UserProfile) -> None:
    _only_in(row, Beschaffen.STAGES[0], "Abgelehnt wird vor der Bestellung.")
    _write(row, _target(row, payload, actor), amount=None, state=DECLINED)


def _order(db: Session, *, order: Order, row: Purchase, payload: dict[str, Any],
           allowed: list[int], actor: UserProfile) -> None:
    """**Die Zusage nach aussen.** Ab hier ist eine zweite Partei gebunden."""
    _only_in(row, Beschaffen.STAGES[0], "Bestellt wird aus der Anfrage heraus.")
    number = _int(payload.get("supplier"), field="Lieferant")
    if number not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Lieferant {number} ist für dieses Modul nicht zugelassen.",
        )
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
    row.reference = (payload.get("reference") or "").strip() or None
    row.stage = Beschaffen.BINDING
    # **Womit bestellt wurde** – aus dem Prozess gelesen, im Moment der Zusage
    # eingefroren. Ab hier ist es die Menge des Belegs; ``mismatch`` vergleicht sie mit
    # dem, was der Auftrag heute hält.
    row.ordered_for = Decimal(unit_count(db, order))
    row.quotes = [
        {**q, "state": CHOSEN if q["supplier"] == number else q["state"]}
        for q in (row.quotes or [])
    ] or [{"supplier": number, "amount": str(amount), "lead_days": None, "state": CHOSEN}]


def _note(db: Session, *, order: Order, row: Purchase, payload: dict[str, Any],
          allowed: list[int], actor: UserProfile) -> None:
    """**Was der Lieferant zurückgibt** – Bestellnummer, Link, Sendungsnummer, Termin.

    Eine eigene Handlung, weil sie einen eigenen Moment hat: die Nummer kommt **nach** der
    Bestellung. Sie am Bestellen mitzugeben hiesse, sie zu erfinden oder das Bestellen zu
    verzögern, bis sie da ist.

    **Ein** Feld für die Referenz, weil es **eine** Frage ist: woran erkennt er den
    Vorgang? Drei Felder für drei Bestellarten wären dieselbe Angabe dreimal.
    """
    _only_in(row, Beschaffen.BINDING, "Ergänzt wird an der Bestellung.")
    row.reference = (payload.get("reference") or "").strip() or None


def _revoke(db: Session, *, order: Order, row: Purchase, payload: dict[str, Any],
            allowed: list[int], actor: UserProfile) -> None:
    """**Die eine Gegenhandlung.** Was sie bewirkt, sagt die Stufe.

    Vor der Bestellung nimmt sie die Anfrage zurück (es war nichts zugesagt); ab ihr
    storniert sie – dort liegt eine Bestellung beim Lieferanten, und «zurück» heisst
    dann, ihm abzusagen.
    """
    if row.stage == Beschaffen.STAGES[0]:
        row.quotes = []
        return
    row.stage = Beschaffen.CANCELLED


def _clarified(db: Session, *, order: Order, row: Purchase, payload: dict[str, Any],
               allowed: list[int], actor: UserProfile) -> None:
    """«Der Lieferant hat zugestimmt» – jetzt darf die Menge nachziehen."""
    now = mismatch(db, order, row)
    if now is None:
        raise HTTPException(
            status_code=409,
            detail="An diesem Beleg gibt es nichts zu klären – die Menge stimmt.",
        )
    row.ordered_for = Decimal(now)


def _only_in(row: Purchase, stage: str, message: str) -> None:
    if row.stage != stage:
        raise HTTPException(
            status_code=409,
            detail=f"{message} Dieser Beleg steht auf «{Beschaffen.STAGE_LABELS[row.stage]}».",
        )


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


