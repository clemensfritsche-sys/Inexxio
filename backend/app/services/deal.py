"""**Der Geldvorgang — Anlage, Handlungen, Rechnung.**

Der Dienst hinter dem Prozessschrittmodul «Zahlung». Er steht **vollständig für sich**:
kein Import aus ``services/purchase``, ``services/invoices``, ``services/payments`` oder
``domain/procurement``. Wer die Module «Beschaffen» und «Verkauf» eines Tages ersatzlos
löscht, fasst hier keine Zeile an.

## Eine Handlung ist ein Befehl, kein Feld-Update

Sechs Verben, ein Endpunkt (``POST …/steps/{id}/deal``). Was an einer Stufe erlaubt ist,
steht in **einer** Tabelle (``ACTIONS``) – und dieselbe Tabelle ist **Auskunft und Tor**:
die Oberfläche rendert einen Knopf genau dann, wenn sein Verb in ``can`` steht, und
``apply`` weist ab, was nicht darin steht. Wäre ``can`` nur ein Anzeige-Hinweis, liefen
Knopf und Tür beim nächsten Verb auseinander.

## Was hier NICHT passiert

Kein Statuswechsel an einer Einzelinstanz, kein Ortswechsel, keine Objektnummer, kein
Auftrag. Dieses Modul hält die Stücke auf und lässt sie weiterlaufen; alles Physische tun
seine Nachbarn. Genau darum muss keine andere Regel im System von ihm wissen.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain import deal as dm
from ..domain import modules
from ..models import Deal, DealEntry, Order, ProcessStep, UserProfile
from ..models.order_unit import OrderUnit
from . import lookup

#: ►►► **Was an welcher Stufe erlaubt ist — Auskunft UND Tor.** ◄◄◄
#:
#: ``quote``   Gegenpartei, Betrag, Frist, Nummer, Notiz erfassen (noch nichts zugesagt).
#: ``agree``   zusagen bzw. beauftragen – ab hier ist eine zweite Partei gebunden.
#: ``revoke``  stornieren. **Nur ab der Schwelle**: davor gibt es nichts zurückzunehmen,
#:             dort ändert man einfach die Angaben.
#: ``charge``  eine **Forderung** buchen (negativ = Gutschrift).
#: ``pay``     eine **Zahlung** buchen (negativ = Erstattung).
#:
#: **Geld darf in jeder Stufe ab der Zusage fliessen** – auch nach dem Storno: eine
#: Anzahlung muss erstattet werden können, und eine Rechnung darf vor der Lieferung
#: stehen und danach. Wer das an die Stufe bände, hätte für jedes Szenario ein ``if``.
ACTIONS: dict[str, tuple[str, ...]] = {
    dm.OFFER: ("quote", "agree"),
    dm.AGREED: ("revoke", "charge", "pay"),
    dm.DONE: ("charge", "pay"),
    dm.CANCELLED: ("charge", "pay"),
}

#: **Stornieren einer Zeile geht immer** – ein Tippfehler ist keine Stufe. Es steht
#: getrennt, weil es keine Handlung am *Vorgang* ist, sondern an einer seiner Zeilen.
VOID = "void"


# ---------------------------------------------------------------------------
# ►► LESEN
# ---------------------------------------------------------------------------

def of_step(db: Session, step_id: int) -> Optional[Deal]:
    """Der aktive Vorgang eines Moduls – oder ``None``. **Die eine Lesestelle.**"""
    return (
        db.query(Deal)
        .filter(Deal.step_id == step_id, Deal.is_active.is_(True))
        .first()
    )


def _entries(db: Session, deal_id: int) -> list[DealEntry]:
    """Die Geld-Zeilen eines Vorgangs, älteste zuerst – nur die gültigen."""
    return (
        db.query(DealEntry)
        .filter(DealEntry.deal_id == deal_id, DealEntry.is_active.is_(True))
        .order_by(DealEntry.booked_on, DealEntry.id)
        .all()
    )


def balance_of(db: Session, row: Deal) -> dm.Balance:
    """Die vier Zahlen dieses Vorgangs – gerechnet in ``domain/deal``, gelesen hier."""
    return dm.balance(row.amount, [(e.kind, e.amount) for e in _entries(db, row.id)])


# ---------------------------------------------------------------------------
# ►► ANLAGE — mit der Freigabe, idempotent
# ---------------------------------------------------------------------------

def instantiate_for_order(db: Session, order: Order) -> None:
    """Jedes «Zahlung»-Modul dieses Auftrags bekommt seinen Vorgang.

    **Bei der Freigabe und nicht beim Erreichen**: mit wem und worüber gehandelt wird,
    steht in der Definition, und ein Angebot einzuholen dauert – wer erst beim Erreichen
    anfragt, wartet die Frist ab, nachdem alles andere fertig ist.

    Idempotent (der partielle Unique-Index trägt); ohne ein solches Modul ein No-op.
    """
    rows = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id,
                ProcessStep.module_type == modules.ZAHLUNG)
        .all()
    )
    for step in rows:
        if of_step(db, step.id) is None:
            db.add(Deal(
                order_id=order.id, step_id=step.id,
                direction=dm.assert_direction(
                    modules.get(step.module_type).direction_of(step.config)),
                stage=dm.OFFER,
            ))
    if rows:
        db.flush()


# ---------------------------------------------------------------------------
# ►► DAS TOR — dieselbe Tabelle, die auch die Knöpfe zeigt
# ---------------------------------------------------------------------------

def can(row: Deal, *, entries: int = 0) -> list[str]:
    """Was an diesem Vorgang **jetzt** möglich ist."""
    found = list(ACTIONS.get(row.stage, ()))
    if entries:
        found.append(VOID)
    return found


def _assert_allowed(row: Deal, action: str, *, entries: int) -> None:
    if action not in can(row, entries=entries):
        flow = dm.of(row.direction)
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» geht hier nicht: der Vorgang steht auf "
                    f"«{flow.label_of(row.stage)}»."),
        )


# ---------------------------------------------------------------------------
# ►► DIE HANDLUNGEN
# ---------------------------------------------------------------------------

def apply(db: Session, *, order: Order, step: ProcessStep, action: str,
          payload: dict[str, Any]) -> Deal:
    """**Eine Handlung am Geldvorgang** – ein Endpunkt, sechs Verben."""
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Zu diesem Modul gibt es keinen Geldvorgang.",
        )
    _assert_allowed(row, action, entries=len(_entries(db, row.id)))
    handler = {
        "quote": _quote, "agree": _agree, "revoke": _revoke,
        "charge": _charge, "pay": _pay, VOID: _void,
    }[action]
    handler(db, order=order, step=step, row=row, data=payload)
    db.flush()
    return row


def _quote(db: Session, *, order: Order, step: ProcessStep, row: Deal,
           data: dict[str, Any]) -> None:
    """Die Angaben erfassen – **bevor** irgendjemand gebunden ist.

    Alles in einem Aufruf, weil es eine Sache ist: mit wem, über wie viel, zu welcher
    Frist, unter welcher Nummer. Ein Feld-Update je Angabe wäre derselbe Vorgang
    fünfmal – und vier Gelegenheiten, den fünften zu vergessen.
    """
    flow = dm.of(row.direction)
    if "party" in data:
        row.party_id = _party(db, step=step, value=data.get("party"), flow=flow)
    if "amount" in data:
        row.amount = _amount(data.get("amount"))
    if "due_days" in data:
        row.due_days = _days(data.get("due_days"))
    if "reference" in data:
        row.reference = _text(data.get("reference"), 120)
    if "note" in data:
        row.note = _text(data.get("note"), 400)


def _agree(db: Session, *, order: Order, step: ProcessStep, row: Deal,
           data: dict[str, Any]) -> None:
    """Zusagen – **die Schwelle**. Ab hier ist eine zweite Partei gebunden.

    Beides ist Pflicht: **mit wem** und **über wie viel**. Eine Zusage ohne Gegenpartei
    ist keine, und eine ohne Betrag ist eine, über die sich später niemand einig ist.
    """
    _quote(db, order=order, step=step, row=row, data=data)
    flow = dm.of(row.direction)
    if row.party_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"Ohne {flow.party_word} gibt es keine Zusage – mit wem sonst?",
        )
    if row.amount is None:
        raise HTTPException(
            status_code=400,
            detail=("Ohne Betrag gibt es keine Zusage – über wie viel sonst? "
                    "(0.00 ist erlaubt und heisst «kostenlos».)"),
        )
    row.stage = dm.AGREED
    row.agreed_on = date.today()


def _revoke(db: Session, *, order: Order, step: ProcessStep, row: Deal,
            data: dict[str, Any]) -> None:
    """Stornieren – und der Vorgang **behält seinen Weg**.

    Ein Storno macht die Zusage nicht ungeschehen, er sagt nur, dass nichts mehr kommt.
    Die gegangenen Stufen bleiben darum stehen; das Geld darf weiterhin fliessen, denn
    eine Anzahlung muss erstattet werden können.
    """
    row.stage = dm.CANCELLED


def _charge(db: Session, *, order: Order, step: ProcessStep, row: Deal,
            data: dict[str, Any]) -> None:
    """Eine **Forderung** buchen. Negativ ist die Gutschrift.

    **Die Automatik steckt in den Vorgaben, nicht in einem Modus**: Betrag = *zugesagt −
    berechnet*, Fälligkeit = *heute + Frist*, Nummer = ``<Auftragsnummer>[-n]``, wo wir
    nummerieren. Der Normalfall ist damit ein Klick, und eine Anzahlung ist derselbe
    Klick mit einer anderen Zahl – kein Schalter «Teilrechnung».
    """
    rest = balance_of(db, row).uncharged
    given = _amount(data.get("amount"), allow_negative=True)
    value = given if given is not None else rest
    if value is None:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Rechnung.")
    booked = _day(data.get("booked_on")) or date.today()
    number = _text(data.get("reference"), 120)
    if row.direction == dm.IN and not number:
        number = _our_number(db, order)
    db.add(DealEntry(
        deal_id=row.id, kind=dm.CHARGE, amount=value, booked_on=booked,
        due_on=_day(data.get("due_on")) or _due(booked, row.due_days),
        reference=number, note=_text(data.get("note"), 200),
    ))


def _pay(db: Session, *, order: Order, step: ProcessStep, row: Deal,
         data: dict[str, Any]) -> None:
    """Eine **Zahlung** buchen. Negativ ist die Erstattung.

    Vorgabe ist der **offene** Betrag – das ist, was in aller Regel eintrifft. Eine
    Teilzahlung ist dieselbe Handlung mit einer kleineren Zahl.
    """
    given = _amount(data.get("amount"), allow_negative=True)
    value = given if given is not None else balance_of(db, row).open
    db.add(DealEntry(
        deal_id=row.id, kind=dm.PAYMENT, amount=value,
        booked_on=_day(data.get("booked_on")) or date.today(),
        reference=_text(data.get("reference"), 120),
        note=_text(data.get("note"), 200),
    ))


def _void(db: Session, *, order: Order, step: ProcessStep, row: Deal,
          data: dict[str, Any]) -> None:
    """Eine Geld-Zeile zurücknehmen – **weich**, sie bleibt lesbar.

    Ein Tippfehler ist keine Buchung und braucht keine Gegenbuchung; wer eine echte
    Gegenbuchung will, erfasst eine negative Zeile. Beides ist möglich, beides ehrlich.
    """
    entry = (
        db.query(DealEntry)
        .filter(DealEntry.id == data.get("entry"), DealEntry.deal_id == row.id,
                DealEntry.is_active.is_(True))
        .first()
    )
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Diese Zeile gehört nicht zu diesem Vorgang.",
        )
    entry.is_active = False


# ---------------------------------------------------------------------------
# ►► DIE SPERRE UND DER ABSCHLUSS — beide am EINEN Ausführungs-Mechanismus
# ---------------------------------------------------------------------------

def assert_completable(db: Session, *, step: ProcessStep) -> None:
    """**Darf dieses Modul bestätigt werden?** – gerufen von ``process.confirm_step``.

    Drei Gründe, warum nicht, und alle drei sind derselbe Satz: der Geldvorgang ist noch
    nicht so weit. Es gibt dafür **keinen Zustand am Stück** und keinen Pausenwert – das
    Modul ist schlicht nicht fertig (dieselbe Haltung wie ``StepNeed`` beim Verbrauch).

    Ohne Geldvorgang ein No-op: jedes andere Modul läuft hier unverändert durch.
    """
    row = of_step(db, step.id)
    if row is None:
        return
    flow = dm.of(row.direction)
    if row.stage == dm.OFFER:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» ist noch nicht zugesagt – bis dahin steht kein "
                    f"Betrag fest, und es gibt nichts abzuschliessen."),
        )
    if row.stage == dm.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» ist storniert. Die Stücke stehen still, bis "
                    f"jemand entscheidet, was mit ihnen geschieht – dafür gibt es den "
                    f"ganz gewöhnlichen Abweichungsauftrag."),
        )
    if not modules.prepaid(step.config):
        return
    money = balance_of(db, row)
    if not money.settled:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» wartet auf den Zahlungseingang: "
                    f"{money.paid} von {money.agreed} bezahlt. So ist dieses Modul "
                    f"eingestellt – erst das Geld, dann weiter."),
        )


def finish(db: Session, *, order: Order, step: ProcessStep) -> None:
    """Nach ``confirm_step``: steht nichts mehr davor, ist der Vorgang **erledigt**.

    Teilabschluss braucht dafür keine eigene Regel – ``confirm_step`` ist einer, und
    solange noch Stücke warten, bleibt der Vorgang zugesagt. **Nur das Geld ist damit
    nicht erledigt**: Forderungen und Zahlungen laufen weiter, denn ein Zahlungsziel
    endet nicht mit der Ware.
    """
    row = of_step(db, step.id)
    if row is None or row.stage != dm.AGREED:
        return
    waiting = (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
                OrderUnit.current_step_id == step.id)
        .count()
    )
    if waiting:
        return
    row.stage = dm.DONE
    db.flush()


# ---------------------------------------------------------------------------
# ►► DIE GEGENPARTEI
# ---------------------------------------------------------------------------

def search_parties(db: Session, *, search: str = "",
                   limit: int = 20) -> list[UserProfile]:
    """**Wer kommt als Gegenpartei in Frage?** – gesucht, nicht als Liste geladen.

    Dieselbe Suchbedingung wie überall (``services/lookup``: Nummer **oder** Name).

    **Ohne Rollenfilter, und das ist eine Entscheidung.** Eine Rolle sagt, was jemand
    *für uns* tut – nicht, ob wir mit ihm Geld austauschen dürfen: ein Mitarbeiter kauft
    eine Schraube, ein Kunde liefert einmal etwas zu. Wer einschränken will, nennt die
    zugelassenen Gegenparteien in der **Definition**; das ist die Stelle, an der eine
    solche Freigabe hingehört, und sie gilt dann auch beim Ausführen.
    """
    return (
        db.query(UserProfile)
        .filter(UserProfile.object_id.isnot(None),
                UserProfile.is_active.is_(True),
                lookup.matches(search, UserProfile.object_id,
                               UserProfile.company_name, UserProfile.first_name,
                               UserProfile.last_name, UserProfile.email))
        .order_by(UserProfile.object_id.desc())
        .limit(limit)
        .all()
    )


def _party(db: Session, *, step: ProcessStep, value: Any,
           flow: dm.Direction) -> Optional[int]:
    """Die gewählte Gegenpartei prüfen – gegen die Freigabe und gegen die Wirklichkeit.

    **Leer heisst frei, aber nicht «irgendwer»**: wo die Definition niemanden nennt,
    muss es die Objektnummer trotzdem geben. Eine Auswahl, die der Dienst danach
    abwiese, wäre keine.
    """
    if value in (None, "", 0):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine Objektnummer.")
    allowed = modules.parties_allowed(step.config)
    if allowed and number not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(f"{flow.party_word} {number} ist an diesem Modul nicht zugelassen. "
                    f"Erlaubt: " + ", ".join(str(n) for n in allowed) + "."),
        )
    found = (
        db.query(UserProfile)
        .filter(UserProfile.object_id == number, UserProfile.is_active.is_(True))
        .first()
    )
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=f"{number} ist kein Datensatz, mit dem man handeln kann.",
        )
    return number


# ---------------------------------------------------------------------------
# ►► KLEINE HELFER — jeder mit genau einer Aufgabe
# ---------------------------------------------------------------------------

def _amount(value: Any, *, allow_negative: bool = False) -> Optional[Decimal]:
    try:
        return dm.amount(value, allow_negative=allow_negative)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _days(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        found = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine Anzahl Tage.")
    if not 0 <= found <= 365:
        raise HTTPException(status_code=400,
                            detail="Eine Zahlungsfrist liegt zwischen 0 und 365 Tagen.")
    return found


def _day(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Datum.")


def _text(value: Any, limit: int) -> Optional[str]:
    found = str(value or "").strip()
    if len(found) > limit:
        raise HTTPException(status_code=400,
                            detail=f"Der Text ist zu lang (max. {limit} Zeichen).")
    return found or None


def _due(booked: date, days: Optional[int]) -> Optional[date]:
    """Fälligkeit = Rechnungsdatum + Frist. **Ohne Frist keine Fälligkeit** – ein
    erfundenes Datum wäre schlimmer als keines."""
    return None if days is None else booked + timedelta(days=days)


def _our_number(db: Session, order: Order) -> str:
    """``<Auftragsnummer>`` für die erste Rechnung, dann ``-2``, ``-3`` …

    Dieselbe Regel wie beim Suffix der Einzelinstanz: eine Rechnung braucht einen Namen,
    aber keine eigene Objektidentität. Gezählt wird über den **Auftrag** und nicht über
    den einzelnen Vorgang – zwei «Zahlung»-Module in einem Auftrag vergäben sonst
    dieselbe Nummer zweimal. Auch stornierte Zeilen zählen mit: eine einmal vergebene
    Nummer wird nicht erneut vergeben.

    **Gezählt wird nur, was WIR nummerieren** (``direction == IN``). Gemessen, nicht
    gelesen: in einem Auftrag, der zuerst eine Lieferantenrechnung erfasst und danach
    eine eigene stellt, hiess die erste eigene ``…-2`` – die fremde Nummer hatte die
    Zählung verbraucht. Eine Nummernserie mit Lücken ist buchhalterisch keine, und die
    Lücke wäre erst bei der Prüfung aufgefallen.

    *Die bewusste Grenze: es gibt dafür keinen Unique-Index. Bei einer **Ausgabe** steht
    hier die Nummer der Gegenpartei, und zwei Lieferanten dürfen sehr wohl beide eine
    «2026-001» schicken – ein Index darüber wiese eine richtige Eingabe ab. Bleibt der
    Doppelklick, und der erzeugt eine doppelte Anzeigenummer, keinen Datenfehler.*
    """
    used = (
        db.query(func.count(DealEntry.id))
        .join(Deal, DealEntry.deal_id == Deal.id)
        .filter(Deal.order_id == order.id, Deal.direction == dm.IN,
                DealEntry.kind == dm.CHARGE)
        .scalar()
    ) or 0
    return str(order.object_id) if used == 0 else f"{order.object_id}-{used + 1}"


# ---------------------------------------------------------------------------
# ►► DIE ANTWORT
# ---------------------------------------------------------------------------

def embed_data(db: Session, *, order: Order,
               step: ProcessStep) -> Optional[dict[str, Any]]:
    """Der Geldvorgang, wie ihn die Ausführungsstelle braucht – oder ``None``.

    **Alles, was die Oberfläche zum Zeichnen braucht, reist mit**: Wörter, Stufen,
    Verben, Zahlen und was man tun darf. Sie fragt damit nie nach der Richtung und nie
    nach dem Modultyp – ein ``if direction ===`` dort wäre die zweite Stelle für eine
    Regel, die hier schon steht.
    """
    row = of_step(db, step.id)
    if row is None:
        return None
    flow = dm.of(row.direction)
    entries = _entries(db, row.id)
    money = balance_of(db, row)
    today = date.today()
    return {
        "direction": row.direction,
        "label": flow.label,
        "party_word": flow.party_word,
        "party_plural": flow.party_plural,
        "charge_word": flow.charge_word,
        "payment_word": flow.payment_word,
        "open_word": flow.open_word,
        "undo": flow.undo if "revoke" in ACTIONS.get(row.stage, ()) else None,
        "stage": row.stage,
        "stages": _stages(row, flow),
        "can": can(row, entries=len(entries)),
        "subject": modules.subject_of(step.config),
        "prepaid": modules.prepaid(step.config),
        "allowed": _named(db, modules.parties_allowed(step.config)),
        "party_object_id": row.party_id,
        "party_name": (_named(db, [row.party_id])[0]["name"]
                       if row.party_id else None),
        "amount": _money(row.amount),
        "due_days": row.due_days,
        "reference": row.reference,
        "note": row.note,
        "agreed_on": row.agreed_on,
        "charged": _money(money.charged),
        "paid": _money(money.paid),
        "open": _money(money.open),
        "uncharged": _money(money.uncharged),
        "settled": money.settled,
        "entries": [
            {
                "id": e.id, "kind": e.kind, "amount": _money(e.amount),
                "booked_on": e.booked_on, "due_on": e.due_on,
                "reference": e.reference, "note": e.note,
                # **Überfällig ist eine Ableitung, kein Zustand**: eine Forderung, deren
                # Tag vorbei ist, solange überhaupt noch etwas offen ist.
                "overdue": bool(e.kind == dm.CHARGE and e.due_on and e.due_on < today
                                and money.open > 0),
            }
            for e in entries
        ],
    }


def _stages(row: Deal, flow: dm.Direction) -> list[dict[str, Any]]:
    """Die drei Stufen mit Beschriftung, Verb und Zustand.

    **Ein Storno ist keine Stufe**: keine ist dann aktiv, kein Verb wird angeboten – die
    gegangene Kette bleibt aber stehen, wo sie stand. Eine Fassung, die bei «storniert»
    alles grau setzt, liesse einen stornierten Vorgang aussehen wie einen, bei dem nie
    etwas geschehen ist.
    """
    order = list(dm.STAGES)
    # Storniert wird erst ab der Zusage – so weit war er also, und so weit bleibt die
    # Kette gegangen.
    reached = order.index(dm.AGREED if row.stage == dm.CANCELLED else row.stage)
    return [
        {
            "key": key,
            "label": flow.label_of(key),
            "verb": flow.stage_verbs.get(key),
            "done": i < reached,
            "active": row.stage != dm.CANCELLED and i == reached,
        }
        for i, key in enumerate(order)
    ]


def _named(db: Session, numbers: list[Optional[int]]) -> list[dict[str, Any]]:
    """Objektnummern auf ihren Anzeigenamen – **eine** Abfrage, nicht eine je Zeile."""
    wanted = [n for n in numbers if n]
    if not wanted:
        return []
    rows = {
        u.object_id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.object_id.in_(wanted)).all()
    }
    return [{"object_id": n, "name": rows.get(n, str(n))} for n in wanted]


def _money(value: Optional[Decimal]) -> Optional[str]:
    """Beträge reisen als **String**. Wo es auf den Rappen ankommt, wird nicht durch
    ``float`` gerechnet – auch nicht auf dem Weg durch JSON."""
    return None if value is None else f"{value:.2f}"
