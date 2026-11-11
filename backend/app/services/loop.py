"""►►► **Die Schlaufe** – wiederkehrende Aufträge (Projektakte ``docs/konzept/wiederkehr.md``). ◄◄◄

**Eine Wiederholung ist ein ganz gewöhnlicher Auftrag, nur ausgelöst vom Takt.** Er entsteht
über denselben Weg wie «Freigeben» (``orders.validate_draft`` → ``orders.create_order``); hier
steht nur, was die Schlaufe ausmacht. Gespeichert wird nichts als **drei Ereignisse im Log**:

| Ereignis | an | Nutzlast |
|---|---|---|
| ``loop.set`` | der Auftrag | die eingefrorene Schlaufe (``domain/loop.clean``) + wer sie begann |
| ``loop.next`` | der Nachfolger | ``from`` = der Vorgänger – **je Auftrag höchstens einer** |
| ``loop.ended`` | der Auftrag | – (nur am neuesten der Kette) |

Je Vorgänger höchstens ein ``loop.next`` sichert ein eindeutiger Index – ein zweiter Lauf
scheitert an der Datenbank. Alles andere ist abgeleitet: läuft, fällig, wartet, geht nicht
mehr, beendet, weiter in …

**Zwei Formen einer Regel**: ``problem`` sagt, warum der Nachfolger gerade nicht entsteht (der
Satz für Karte und «zu tun»); ``create_next`` fragt dieselbe Funktion, bevor es anlegt.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core import clock
from ..core.actor import act
from ..domain import loop as dl
from ..domain import statuses as st
from ..models import Article, Log, Order, OrderLine, OrderUnit, ProcessStep, UserProfile
from . import log as log_svc
from ..domain.errors import Conflict, Invalid, Rejected

SET = "loop.set"
NEXT = "loop.next"
ENDED = "loop.ended"
#: Die automatische Zusage in einer Wiederholung (Offerte und Zusage durch das System).
AGREED = "loop.agreed"

#: Was die Karte zeigt.
RUN, WAIT, STUCK, ENDED_STATE, DONE, CONTINUED = (
    "run", "wait", "stuck", "ended", "done", "continued")


# ---------------------------------------------------------------------------
# ►► LESEN – alles aus dem Log
# ---------------------------------------------------------------------------

def _event(db: Session, name: str, object_id: int) -> Optional[Log]:
    return (db.query(Log).filter(Log.event == name, Log.object_id == object_id)
            .order_by(Log.id.desc()).first())


def settings(db: Session, order: Order) -> Optional[dict[str, Any]]:
    """Die Schlaufe dieses Auftrags (``loop.set``) – oder ``None``."""
    row = _event(db, SET, order.object_id)
    return dict(row.payload) if row is not None and row.payload else None


def successor(db: Session, order: Order) -> Optional[int]:
    """Die Objektnummer des Nachfolgers – oder ``None``."""
    row = (db.query(Log.object_id).filter(Log.event == NEXT,
                                         Log.payload["from"].astext == str(order.object_id))
           .first())
    return int(row[0]) if row is not None else None


def predecessor(db: Session, order: Order) -> Optional[int]:
    row = _event(db, NEXT, order.object_id)
    return int(row.payload["from"]) if row is not None and row.payload else None


def is_ended(db: Session, order: Order) -> bool:
    return _event(db, ENDED, order.object_id) is not None


# ---------------------------------------------------------------------------
# ►► IM ENTWURF – prüfen und mit der Freigabe einfrieren
# ---------------------------------------------------------------------------

def draft_problems(db: Session, draft: dict[str, Any]) -> list[str]:
    """►► **Was an der Schlaufe eines Entwurfs fehlt** – für ``orders.validate_draft``. ◄◄

    Dazu die Regel «eine Schlaufe gibt es nur an einem regulären Auftrag» (Grundsatz 3): jedes
    gewählte Stück muss ruhen (``statuses.REGULAR_STARTS``) und in keinem Auftrag stecken."""
    raw = draft.get("loop")
    if not raw:
        return []
    lines = list(draft.get("lines") or [])
    out = dl.problems(raw, [str(ln.get("origin")) for ln in lines], clock.today())
    numbers = [str(u.get("number")) for ln in lines for u in (ln.get("units") or [])]
    out += [f"Eine Wiederholung gibt es nur an einem regulären Auftrag – {why}"
            for why in _not_resting(db, numbers)]
    return out


def freeze(db: Session, order: Order, draft: dict[str, Any],
           actor: Optional[UserProfile]) -> None:
    """►► **Mit der Freigabe einfrieren** – in derselben Transaktion wie der Auftrag. ◄◄

    Geprüft ist schon vor der Freigabe (``draft_problems``); jetzt stecken die Stücke im
    Auftrag selbst. ``clean`` wirft, falls die Einstellung unlesbar ist."""
    raw = draft.get("loop")
    if not raw:
        return
    try:
        frozen = dl.clean(raw, list(draft.get("lines") or []), clock.today())
    except ValueError as e:
        raise Invalid(str(e))
    frozen["by"] = actor.id if actor is not None else None
    frozen["by_object"] = actor.object_id if actor is not None else None
    log_svc.event(db, SET, order.object_id, frozen)


def _not_resting(db: Session, numbers: list[str]) -> list[str]:
    """Welche dieser Stücke ruhen **nicht** – je Stück ein Satz (leer = alle ruhen)."""
    from . import instances
    if not numbers:
        return []
    found = instances.find_units(db, numbers)
    busy = {iu: oid for iu, oid in (
        db.query(OrderUnit.instance_unit_id, Order.object_id)
        .join(Order, Order.id == OrderUnit.order_id)
        .filter(OrderUnit.released_at.is_(None),
                OrderUnit.instance_unit_id.in_([u.id for u in found.values()]))
        .all())} if found else {}
    out: list[str] = []
    for number in numbers:
        unit = found.get(number)
        if unit is None:
            out.append(f"Einzelinstanz {number} gibt es nicht.")
        elif unit.id in busy:
            out.append(f"{number} ist in Auftrag {busy[unit.id]}.")
        elif unit.status not in st.REGULAR_STARTS:
            out.append(f"{number} steht auf «{st.label(unit.status)}».")
    return out


# ---------------------------------------------------------------------------
# ►► DER NACHFOLGER – eine 1:1-Kopie, über denselben Weg wie «Freigeben»
# ---------------------------------------------------------------------------

def _draft(db: Session, order: Order, loop: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """►► **Der Entwurf des Nachfolgers** und was dabei fehlt (Sätze). ◄◄

    Zeilen nach der eingefrorenen Wahl: gleiche Einzelinstanzen (die Nummern aus ``loop.set``),
    FIFO (``consumption.free_numbers`` – nur, was bei uns frei ist, also nie eine Abweichung),
    «Neu» wie im Vorgänger. Die Module als Kopie der eingefrorenen Schritte."""
    from . import consumption
    rows = (db.query(OrderLine, Article).join(Article, Article.id == OrderLine.article_id)
            .filter(OrderLine.order_id == order.id)
            .order_by(OrderLine.position).all())
    takes = loop.get("lines") or []
    lines: list[dict[str, Any]] = []
    short: list[str] = []
    for i, (ln, art) in enumerate(rows):
        take = (takes[i] if i < len(takes) else {}).get("take", dl.NEW)
        units: list[str] = []
        if take == dl.SAME:
            units = list((takes[i] or {}).get("units") or [])
        elif take == dl.FIFO:
            units = consumption.free_numbers(db, art.object_id, ln.quantity)
            if len(units) < ln.quantity:
                short.append(f"{art.name}: {ln.quantity} gebraucht, {len(units)} frei.")
        lines.append({"article_object_id": art.object_id, "quantity": ln.quantity,
                      "origin": ln.origin, "returns": True,
                      "units": [{"number": n, "from_order": None} for n in units]})
    steps = [{"module_type": s.module_type, "config": dict(s.config or {})}
             for s in db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
             .order_by(ProcessStep.position).all()]
    return {"lines": lines, "steps": steps}, short


def _gone(db: Session, loop: dict[str, Any], order: Order) -> Optional[str]:
    """**Was nie mehr geht** – eine verschrottete Einzelinstanz, ein Artikel, der nichts Neues
    mehr erzeugt. Dann «geht nicht mehr»: nur Beenden (O6, O13)."""
    from . import articles, instances
    for row in loop.get("lines") or []:
        if row.get("take") != dl.SAME:
            continue
        found = instances.find_units(db, row.get("units") or [])
        for number in row.get("units") or []:
            unit = found.get(number)
            if unit is None or st.is_terminal(unit.status):
                return f"{number} ist «{st.label(unit.status) if unit else 'weg'}»."
    news = [art for (ln, art) in (
        db.query(OrderLine, Article).join(Article, Article.id == OrderLine.article_id)
        .filter(OrderLine.order_id == order.id, OrderLine.origin == "neu").all())]
    for art in news:
        why = articles.may_create(art)
        if why:
            return why
    return None


def problem(db: Session, order: Order,
            loop: Optional[dict[str, Any]] = None) -> Optional[tuple[str, bool]]:
    """►►► **Warum der Nachfolger gerade nicht entsteht** – ``(Satz, endgültig)``, oder
    ``None``, wenn nichts fehlt. ◄◄◄ Dieselbe Frage wie der Knopf «Freigeben»
    (``orders.validate_draft``), dazu: keine Abweichung (jedes Stück ruht) und nichts, was nie
    mehr geht. Ein Nachfolger geht nie mit einem Teil der Stücke los."""
    from . import orders
    loop = loop if loop is not None else settings(db, order)
    if loop is None:
        return None
    gone = _gone(db, loop, order)
    if gone:
        return gone, True
    draft, short = _draft(db, order, loop)
    if short:
        return short[0], False
    numbers = [u["number"] for ln in draft["lines"] for u in ln["units"]]
    resting = _not_resting(db, numbers)
    if resting:
        return resting[0], False
    missing = orders.validate_draft(db, draft)
    if missing:
        return missing[0], False
    return None


def due(db: Session, today: Optional[date] = None) -> list[Order]:
    """►► **Welche Aufträge brauchen jetzt einen Nachfolger?** – die neuesten ihrer Kette,
    nicht beendet, Termin erreicht, Kette nicht zu Ende. Älteste Termine zuerst. ◄◄"""
    today = today or clock.today()
    rows = db.execute(text(
        "SELECT s.object_id, s.payload FROM log s "
        "WHERE s.event = :set "
        "AND NOT EXISTS (SELECT 1 FROM log n WHERE n.event = :next "
        "                AND n.payload ->> 'from' = s.object_id::text) "
        "AND NOT EXISTS (SELECT 1 FROM log e WHERE e.event = :ended "
        "                AND e.object_id = s.object_id) "
        "ORDER BY s.payload ->> 'next', s.id"),
        {"set": SET, "next": NEXT, "ended": ENDED}).all()
    numbers = [int(oid) for oid, payload in rows
               if payload and dl.go_on(payload) and date.fromisoformat(payload["next"]) <= today]
    if not numbers:
        return []
    found = {o.object_id: o for o in db.query(Order).filter(Order.object_id.in_(numbers)).all()}
    return [found[n] for n in numbers if n in found]


@contextmanager
def _on_behalf(db: Session, person: Optional[int]) -> Iterator[None]:
    """**Das System handelt im Namen der Person, die die Kette begann** – so steht ihr
    Entscheid im Log (O7). Danach wieder das System allein."""
    act(db, "system", person, "job")
    try:
        yield
    finally:
        act(db, "system", None, "job")


def create_next(db: Session, order: Order) -> Optional[Order]:
    """►►► **Den Nachfolger anlegen** – wenn nichts fehlt; sonst nichts. ◄◄◄

    Über ``orders.create_order``, in derselben Transaktion ``loop.next`` und das ``loop.set``
    des Nachfolgers (der nächste Termin, bei «nach Anzahl» eins weniger). Danach die Zahlung:
    stützt sie sich auf eine Zusage zur Schlaufe, führt das System Anbieten und Zusagen aus
    (``_carry_agreement``)."""
    from . import orders
    loop = settings(db, order)
    if loop is None or not dl.go_on(loop) or successor(db, order) or is_ended(db, order):
        return None
    if problem(db, order, loop) is not None:
        return None
    draft, _ = _draft(db, order, loop)
    draft["date"] = _next_date(db, order, date.fromisoformat(str(loop["next"])))
    with _on_behalf(db, loop.get("by_object")):
        new = orders.create_order(db, draft, actor_id=loop.get("by"))
        log_svc.event(db, NEXT, new.object_id, {"from": order.object_id, "on": loop["next"]})
        log_svc.event(db, SET, new.object_id, dl.follow(loop))
        db.flush()
        _carry_agreement(db, order, new)
    return new


def _term(db: Session, order: Order) -> date:
    """Der Termin, an dem ein Auftrag der Kette entstand: beim Nachfolger der aus ``loop.next``,
    beim ersten der Tag seiner Freigabe."""
    row = _event(db, NEXT, order.object_id)
    if row is not None and row.payload and row.payload.get("on"):
        return date.fromisoformat(str(row.payload["on"]))
    return order.created_at.astimezone(clock.ZONE).date()


def _next_date(db: Session, order: Order, term: date) -> Optional[dict[str, Any]]:
    """►► **Das Datum des Nachfolgers** – mit demselben Wort («bis» · «ab») und demselben
    Abstand zu seinem Termin wie beim Vorgänger; nie vor heute (wartete er, gilt heute). ◄◄"""
    if order.date_on is None:
        return None
    on = term + (order.date_on - _term(db, order))
    return {"kind": order.date_kind, "on": max(on, clock.today())}


def end(db: Session, order: Order) -> None:
    """►► **Beenden** – am neuesten Auftrag der Kette, auch wenn er abgeschlossen ist. Der
    Auftrag ändert sich nicht; geschrieben wird nur ``loop.ended``. Endgültig. ◄◄"""
    if settings(db, order) is None:
        raise Conflict(f"Auftrag {order.object_id} wiederholt sich nicht.")
    nxt = successor(db, order)
    if nxt is not None:
        raise Conflict(f"Die Wiederholung läuft in Auftrag {nxt} weiter – beendet wird sie dort.")
    if is_ended(db, order):
        raise Conflict("Die Wiederholung ist schon beendet.")
    log_svc.event(db, ENDED, order.object_id, {})


# ---------------------------------------------------------------------------
# ►► DIE ZAHLUNG IN DER WIEDERHOLUNG – dieselben Schritte, automatisch und dokumentiert
# ---------------------------------------------------------------------------

def _carry_agreement(db: Session, prev: Order, new: Order) -> None:
    """►► **Offerte → Zusage, durch das System – gestützt auf die Zusage zur Schlaufe.** ◄◄

    Je Zahlungsmodul: hat die Partei beim Vorgänger zugesagt und sind **alle** Preise vom
    Modul vorgegeben, führt das System ``ask`` und ``agree`` aus (dieselben Verben, nichts
    geht hinaus, ``voucher_docs.quietly``); sonst bleibt der Beleg bei der Offerte stehen
    (O1, O21). Dazu ``loop.agreed`` mit der ursprünglichen Zusage."""
    from ..domain import voucher as vo
    from . import voucher as vs, voucher_actions, voucher_docs, voucher_head
    before = {s.position: s for s in db.query(ProcessStep).filter(
        ProcessStep.order_id == prev.id, ProcessStep.module_type == "beleg").all()}
    for step in (db.query(ProcessStep).filter(ProcessStep.order_id == new.id,
                                              ProcessStep.module_type == "beleg")
                 .order_by(ProcessStep.position).all()):
        old = before.get(step.position)
        old_row = vs.of_step(db, old.id) if old is not None else None
        row = vs.of_step(db, step.id)
        if old_row is None or row is None or old_row.stage not in (vo.AGREED, vo.BILLED):
            continue
        party = vs.party_of(db, old_row)
        lines = voucher_head.sync_lines(db, row, new, step)
        fixed = voucher_head.preset_prices(db, row, step)
        if party is None or not lines or any(ln.article_id not in fixed for ln in lines):
            continue
        basis = _basis(db, prev, old.position, old_row)
        point = db.begin_nested()
        try:
            with voucher_docs.quietly():
                voucher_actions.apply(db, order=new, step=step, action="ask",
                                      payload={"parties": [party]})
                voucher_actions.apply(db, order=new, step=step, action="agree",
                                      payload={"party": party})
            point.commit()
        except Rejected:
            point.rollback()
            continue
        log_svc.event(db, AGREED, new.object_id, {"position": step.position, **basis})


def _basis(db: Session, prev: Order, position: int, old_row) -> dict[str, Any]:
    """**Worauf sich die Zusage stützt** – die ursprüngliche Annahme der Kette."""
    for row in (db.query(Log).filter(Log.event == AGREED, Log.object_id == prev.object_id)
                .all()):
        if (row.payload or {}).get("position") == position:
            return {"basis_order": row.payload["basis_order"], "basis_on": row.payload["basis_on"]}
    return {"basis_order": prev.object_id,
            "basis_on": old_row.agreed_on.isoformat() if old_row.agreed_on else None}


# ---------------------------------------------------------------------------
# ►► DIE ANSICHT und «zu tun»
# ---------------------------------------------------------------------------

def view(db: Session, order: Order) -> Optional[dict[str, Any]]:
    """►► **Die Schlaufe eines Auftrags, wie die Karte sie zeigt** – oder ``None``. ◄◄"""
    loop = settings(db, order)
    if loop is None:
        return None
    nxt = successor(db, order)
    state, reason = RUN, None
    if nxt is not None:
        state = CONTINUED
    elif is_ended(db, order):
        state = ENDED_STATE
        ended = _event(db, ENDED, order.object_id)
        reason = f"Beendet am {clock.day(ended.at)}." \
            if ended is not None else None
    elif not dl.go_on(loop):
        state = DONE
    elif date.fromisoformat(loop["next"]) <= clock.today():
        found = problem(db, order, loop)
        if found is not None:
            reason, final = found
            state = STUCK if final else WAIT
    names = [a.name for (_, a) in (
        db.query(OrderLine, Article).join(Article, Article.id == OrderLine.article_id)
        .filter(OrderLine.order_id == order.id).order_by(OrderLine.position).all())]
    rows = loop.get("lines") or []
    agreed = (db.query(Log).filter(Log.event == AGREED, Log.object_id == order.object_id)
              .order_by(Log.id).first())
    return {
        "every": loop["every"], "every_label": dl.label(loop["every"]),
        "next": loop["next"], "until": loop.get("until"), "left": loop.get("left"),
        "sentence": dl.sentence(loop),
        "lines": [{"position": i, "article_name": names[i] if i < len(names) else "",
                   "take": r.get("take"), "take_label": dl.TAKES.get(r.get("take"), "")}
                  for i, r in enumerate(rows)],
        "state": state, "state_label": dl.STATES[state][0], "tone": dl.STATES[state][1],
        "reason": reason, "successor": nxt,
        "predecessor": predecessor(db, order),
        "agreed_from": agreed.payload.get("basis_order") if agreed and agreed.payload else None,
        "agreed_on": agreed.payload.get("basis_on") if agreed and agreed.payload else None,
        "may_end": state in (RUN, WAIT, STUCK),
    }


def todo_items(db: Session) -> list[tuple[int, str, bool]]:
    """►► **Was an Schlaufen zu tun ist** – je wartendem oder unmöglichem Nachfolger ein Satz
    am neuesten Auftrag der Kette (``services/todo``); rot, wenn es nie mehr geht. ◄◄"""
    out: list[tuple[int, str, bool]] = []
    for order in due(db):
        found = problem(db, order)
        if found is not None:
            reason, final = found
            word = "Wiederholung geht nicht mehr" if final else "Wiederholung wartet"
            out.append((order.object_id, f"{word}: {reason}", final))
    return out
