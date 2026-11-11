"""►►► **Aufgaben – wer macht was** (Projektakte `docs/konzept/aufgaben.md`). ◄◄◄

Eine **Aufgabe** ist eine Stelle im ERP, an der jemand etwas tun muss – abgeleitet, nie
angelegt, nie abgehakt (``collect``). Sie hat einen festen Schlüssel, einen Ort (Datensatz und
Stelle darin), die Kompetenz, die sie braucht, und ein Datum. **Die Kompetenz folgt dem Ort**
(§3.1): am Prozessschritt die des Schritts, an einer fremden Person «Kommunizieren», an mir nur
ich, an der eigenen Gesellschaft der Admin.

**Zuteilung** (``dispatch``, eine Schleife unter einer Sperre): wer frei und da ist – wer am
längsten frei ist zuerst – bekommt die Aufgabe mit dem frühesten Datum, die er darf und kann
(das Arztpraxis-Modell, §5). Eine Person hat höchstens eine, eine Aufgabe höchstens eine Person
(``task_focus``, zwei eindeutige Schlüssel). **Anwesenheit** in drei Sätzen (§6): Neues nur, wer
eingestempelt ist (ohne Zeiterfassung: da); was ich habe, bleibt bei mir; ausser bei einer Absenz.

Gespeichert wird nur ``task_focus`` (wer woran ist) und ``user_profiles.competences`` (wer was
kann); das Log schreibt die Datenbank selbst.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import any_, func, text
from sqlalchemy.orm import Session

from ..core import clock, locks
from ..domain import competences as comp
from ..domain import modules, policy
from ..domain.errors import Conflict, Invalid
from ..models import (CompanySettings, ObjectRef, Order, OrderUnit, ProcessStep, TaskFocus,
                      TimeContract, UserProfile, Voucher)
from ..schemas.tasks import TaskMark, TasksOut

#: Seit wann eine Zahlung im Blick bleibt, deren Geld ausgeglichen scheint (Papiere,
#: Ausfuhrnachweis, Erstattung nach einer späten Zahlung) – ein Vorfilter, die Regel ist
#: ``voucher_view.situation``.
_RECENT = timedelta(days=120)


@dataclass(frozen=True)
class Task:
    """Eine Aufgabe – mehr gibt es nicht über sie zu wissen (kein Satz: was zu tun ist, sieht
    man an der Stelle)."""
    key: str
    object_id: int
    #: Die Stelle im Datensatz (``data-todo``): ein Abschnitt oder ``step:<id>``.
    part: str
    #: Die nötige Kompetenz – ``None``: keine.
    competence: Optional[str]
    #: Das Datum (§5): seit wann es zu tun ist.
    since: datetime
    #: Nur diese Person (Objektnummer) – die eigene Zeiterfassung, die eigenen Angaben.
    only: Optional[int] = None
    #: Das nötige Recht (``domain/policy``).
    rule: str = "erp"
    #: Ein Hinweis, keine Aufgabe: nie zugeteilt, nur der Admin sieht das Zeichen.
    hint: bool = False


def _at(d: date) -> datetime:
    """Ein Tag als Zeitpunkt (Beginn, Europe/Zurich) – für das Datum einer Aufgabe."""
    from . import timekeeping
    return timekeeping.instant(d, 0)


def _hash(value: str) -> str:
    return hashlib.sha1(value.encode()).hexdigest()[:12]


# ─── Die Quellen ──────────────────────────────────────────────────────────────────────

def _messages(db: Session) -> list[Task]:
    """Offene Nachrichten (``communication.open_threads``): von aussen → an der fremden Person,
    «Kommunizieren»; intern an eine Mitarbeiterin → nur sie."""
    from . import communication
    out: list[Task] = []
    for t in communication.open_threads(db):
        out.append(Task(key=f"msg:{t.place}:{_hash(t.topic)}", object_id=t.place,
                        part="kommunikation", since=t.at,
                        competence=None if t.only else comp.KOMMUNIZIEREN, only=t.only))
    return out


def _steps(db: Session) -> list[Task]:
    """**Stücke warten an einem Schritt**, den ein Mensch ausführt – einer je (Auftrag, Schritt).

    Nicht, wenn das Modul von selbst durchlässt (die Zahlung kommt aus ``_payments``), wenn es
    auf eine Rückführung wartet, oder wenn am Verbrauch das Material nicht am Ort liegt
    (Nichtverfügbarkeit ist kein Zustand – es gibt dann keine Aufgabe)."""
    from . import consumption, order_state
    rows = (db.query(OrderUnit.order_id, OrderUnit.current_step_id,
                     func.min(OrderUnit.updated_at))
            .filter(OrderUnit.released_at.is_(None), OrderUnit.current_step_id.isnot(None))
            .group_by(OrderUnit.order_id, OrderUnit.current_step_id).all())
    if not rows:
        return []
    steps = {s.id: s for s in db.query(ProcessStep).filter(
        ProcessStep.id.in_({sid for _, sid, _ in rows})).all()}
    orders = {o.id: o for o in db.query(Order).filter(
        Order.id.in_({oid for oid, _, _ in rows})).all()}
    out: list[Task] = []
    for order_id, step_id, since in rows:
        step, order = steps.get(step_id), orders.get(order_id)
        if step is None or order is None:
            continue
        module = modules.get(step.module_type)
        if module.passes_itself:
            continue
        if order_state.pending_returns(db, order).get(step.id):
            continue
        if modules.lines_of(step.config):
            products = order_state.units_before(db, order, step)
            if any(n.here < n.required for n in consumption.needs(db, step, products=products)):
                continue
        out.append(Task(key=f"step:{order.object_id}:{step.id}", object_id=order.object_id,
                        part=f"step:{step.id}", since=since,
                        competence=module.competence_of(step.config)))
    return out


_PAYMENT_CANDIDATES = text("""
SELECT v.id FROM vouchers v
  LEFT JOIN (SELECT voucher_id,
                    sum(CASE WHEN kind = 'tip' THEN -amount ELSE amount END) AS paid,
                    max(created_at) AS last
               FROM voucher_entries GROUP BY voucher_id) e ON e.voucher_id = v.id
 WHERE v.stage IN ('offer', 'agreed')
    OR (v.stage = 'billed' AND (abs(coalesce(v.amount, 0) - coalesce(e.paid, 0)) > 0.005
                                OR v.updated_at > :recent OR e.last > :recent))
    OR (v.stage = 'cancelled' AND e.voucher_id IS NOT NULL)""")


def _payments(db: Session) -> list[Task]:
    """**Die Zahlung sagt «wir sind dran»** (``voucher_view.situation`` → ``ours``) – Offerte,
    Rechnung, Papier, Ausfuhrnachweis, Mahnen, Bezahlen, Erstatten: eine Quelle. In SQL
    vorgefiltert auf, was offen sein kann; entschieden hat ``situation``."""
    from . import voucher as vs
    from .voucher_view import situation
    ids = [r for (r,) in db.execute(_PAYMENT_CANDIDATES,
                                    {"recent": clock.utcnow() - _RECENT}).all()]
    if not ids:
        return []
    rows = db.query(Voucher).filter(Voucher.id.in_(ids)).all()
    orders = {o.id: o for o in db.query(Order).filter(
        Order.id.in_({r.order_id for r in rows})).all()}
    steps = {s.id: s for s in db.query(ProcessStep).filter(
        ProcessStep.id.in_({r.step_id for r in rows})).all()}
    out: list[Task] = []
    with vs.reading(db):
        for row in rows:
            order, step = orders.get(row.order_id), steps.get(row.step_id)
            if order is None or step is None:
                continue
            if not situation(db, row, order=order, step=step).get("ours"):
                continue
            since = _at(row.due_on) if row.stage == "billed" and row.due_on else row.updated_at
            out.append(Task(key=f"pay:{row.id}", object_id=order.object_id,
                            part=f"step:{step.id}", since=since,
                            competence=modules.get(step.module_type).competence_of(step.config)))
    return out


def _loops(db: Session) -> list[Task]:
    """Eine Wiederholung wartet oder geht nicht mehr – am neuesten Auftrag, mit der Kompetenz
    seines ersten Schritts (dort würde der Nachfolger beginnen)."""
    from . import loop, order_state
    out: list[Task] = []
    found = loop.todo_items(db)
    if not found:
        return out
    orders = {o.object_id: o for o in db.query(Order).filter(
        Order.object_id.in_({oid for oid, _, _ in found})).all()}
    for oid, _label, _final in found:
        order = orders.get(oid)
        if order is None:
            continue
        first = next(iter(order_state.steps_of(db, order)), None)
        need = modules.get(first.module_type).competence_of(first.config) if first else None
        out.append(Task(key=f"loop:{oid}", object_id=oid, part="wiederholung",
                        since=order.created_at, competence=need))
    return out


def _proposals(db: Session) -> list[Task]:
    """Offene Vorschläge aus Mails – am Datensatz, «Kommunizieren» (sie kommen aus Mails)."""
    from . import handgriff
    now = clock.utcnow()
    return [Task(key=f"proposal:{oid}", object_id=oid, part="handgriffe", since=now,
                 competence=comp.KOMMUNIZIEREN) for oid in handgriff.open_mail_counts(db)]


def _own_people(db: Session, staff: list[UserProfile], now: datetime) -> list[Task]:
    """Was nur die Person selbst kann: ihre Zeiterfassung («Gehen» fehlt, Nachweis) und ihre
    Pflichtangaben. Angaben eines Kunden sind keine Aufgabe – sie fehlen erst dort, wo etwas sie
    braucht (die Zahlung sagt es)."""
    from . import people, timekeeping
    out: list[Task] = []
    with_contract = {o for (o,) in db.query(TimeContract.person_object_id).distinct().all()}
    for person in staff:
        oid = person.object_id
        if oid in with_contract:
            for kind, day, _label in timekeeping.tasks(timekeeping.load(db, person), now):
                out.append(Task(key=f"time:{oid}:{kind}:{day.isoformat()}", object_id=oid,
                                part="zeiterfassung", since=_at(day), competence=None, only=oid))
        for m in people.missing_fields(person):
            out.append(Task(key=f"field:{oid}:{m['key']}", object_id=oid, part=m["section"],
                            since=person.created_at, competence=None, only=oid))
    return out


def _companies(db: Session) -> list[Task]:
    """An einer eigenen Gesellschaft: fehlende Feiertage und Rechtstexte – nur der Admin."""
    from . import holidays, legal
    out: list[Task] = []
    today = clock.today()
    own = [c for c in db.query(CompanySettings).filter(
        CompanySettings.is_own.is_(True), CompanySettings.is_active.is_(True)).all() if c.object_id]
    born = dict(db.query(ObjectRef.object_id, ObjectRef.created_at).filter(
        ObjectRef.object_id.in_([c.object_id for c in own])).all()) if own else {}
    for c in own:
        for kind in legal.FIELD_OF:
            if legal.document_of(db, c, kind) is None:
                out.append(Task(key=f"legal:{c.object_id}:{kind}", object_id=c.object_id,
                                part="dokumente", since=born.get(c.object_id) or clock.utcnow(),
                                competence=None,
                                rule="admin"))
        for found in holidays.holiday_tasks(db, c, today):
            out.append(Task(key=f"holidays:{c.object_id}:{_hash(found.label)}",
                            object_id=c.object_id, part="feiertage",
                            since=_at(found.day), competence=None,
                            rule="admin"))
    return out


def _hints(db: Session) -> list[Task]:
    """Hinweise ohne Handlung – heute einer: der Deckel der KI ist nahe (am Betreiber)."""
    from . import ai, sites
    if not ai.near_cap(db):
        return []
    op = sites.find_operator(db)
    if op is None or not op.object_id:
        return []
    return [Task(key="hint:ai-cap", object_id=op.object_id, part="ki", since=clock.utcnow(),
                 competence=None, rule="admin", hint=True)]


def _staff(db: Session) -> list[UserProfile]:
    return (db.query(UserProfile).filter(UserProfile.role.in_(policy.STAFF_ROLES),
                                         UserProfile.object_id.isnot(None))
            .order_by(UserProfile.object_id).all())


def collect(db: Session, staff: Optional[list[UserProfile]] = None) -> list[Task]:
    """►► **Alles, was zu tun ist** – jede Quelle einmal gefragt, nichts gespeichert. ◄◄"""
    staff = _staff(db) if staff is None else staff
    now = clock.utcnow()
    found = (_messages(db) + _steps(db) + _payments(db) + _loops(db) + _proposals(db)
             + _own_people(db, staff, now) + _companies(db) + _hints(db))
    unique: dict[str, Task] = {}
    for t in found:
        unique.setdefault(t.key, t)
    return list(unique.values())


# ─── Wer darf und kann, wer ist da ─────────────────────────────────────────────────────

def may(person: UserProfile, task: Task) -> bool:
    """►► **Darf und kann diese Person die Aufgabe?** – Recht (Tor) und Kompetenz (Zuteilung). ◄◄"""
    if task.hint:
        return False
    if task.only is not None:
        return person.object_id == task.only
    if not policy.may(person, task.rule):
        return False
    return task.competence is None or task.competence in (person.competences or [])


@dataclass(frozen=True)
class Presence:
    #: Neues bekommt nur, wer da ist (Satz 1).
    here: bool
    #: Eine Absenz heute – dann geht auch, was man hat, weiter (Satz 3).
    absent: bool


def presence(db: Session, person: UserProfile, now: datetime) -> Presence:
    """►► **Die Anwesenheit in drei Sätzen** (Akte §6), gelesen aus der Zeiterfassung. ◄◄
    Ohne Vertrag: da. Ein Vertrag mit 0 Stunden (Austritt) oder keiner, der heute gilt: nicht da."""
    from . import timekeeping
    book = timekeeping.load(db, person)
    if not book.contracts:
        return Presence(here=True, absent=False)
    today = timekeeping.local(now).date()
    current = timekeeping.contract_on(book, today)
    if current is None or not current.weekly_minutes:
        return Presence(here=False, absent=True)
    if timekeeping.covering(book, today) is not None:
        return Presence(here=False, absent=True)
    return Presence(here=timekeeping.running(book, now) is not None, absent=False)


# ─── Zuteilung ─────────────────────────────────────────────────────────────────────────

def _order(tasks: Iterable[Task]) -> list[Task]:
    """Das Arztpraxis-Modell: das früheste Datum zuerst (gleich alt: nach Schlüssel)."""
    return sorted(tasks, key=lambda t: (t.since, t.key))


def dispatch(db: Session, now: Optional[datetime] = None) -> list[Task]:
    """►►► **Die Zuteilung – eine Schleife.** ◄◄◄ Aufräumen (erledigt · nicht mehr berechtigt
    · Absenz), dann die Freien, wer am längsten frei ist zuerst; jede nimmt die Aufgabe mit dem
    frühesten Datum, die sie darf und kann. Gibt alle Aufgaben zurück (für die Ansicht)."""
    now = now or clock.utcnow()
    locks.xact(db, locks.TASKS)
    staff = _staff(db)
    tasks = collect(db, staff)
    by_key = {t.key: t for t in tasks if not t.hint}
    rows = {r.person_object_id: r for r in db.query(TaskFocus).all()}
    seen = {p.object_id: presence(db, p, now) for p in staff}
    people = {p.object_id: p for p in staff}
    for oid, row in rows.items():
        if row.task_key is None:
            continue
        task, person = by_key.get(row.task_key), people.get(oid)
        if task is None or person is None or not may(person, task) or seen[oid].absent:
            row.task_key, row.since = None, now
    db.flush()
    taken = {r.task_key for r in rows.values() if r.task_key}
    pool = [t for t in _order(by_key.values()) if t.key not in taken]
    epoch = datetime.min.replace(tzinfo=now.tzinfo)
    free = [p for p in staff if seen[p.object_id].here
            and not (rows.get(p.object_id) and rows[p.object_id].task_key)]
    free.sort(key=lambda p: (rows[p.object_id].since if p.object_id in rows else epoch,
                             p.object_id))
    for person in free:
        row = rows.get(person.object_id)
        handed = row.handed_key if row else None
        task = next((t for t in pool if may(person, t) and t.key != handed), None)
        if task is None:
            continue
        pool.remove(task)
        if row is None:
            row = TaskFocus(person_object_id=person.object_id)
            db.add(row)
            rows[person.object_id] = row
        row.task_key, row.since, row.handed_key = task.key, now, None
    db.flush()
    return tasks


def hand(db: Session, actor: UserProfile, key: str) -> None:
    """►► **Abgeben** – ein Klick, ohne Grund. Die Aufgabe ist wieder frei; wer abgab, bekommt
    sie erst nach einer anderen wieder (``handed_key``). ◄◄"""
    row = db.query(TaskFocus).filter(TaskFocus.person_object_id == actor.object_id).first()
    if row is None or row.task_key != key:
        raise Conflict("Diese Aufgabe ist nicht bei Ihnen.")
    row.task_key, row.handed_key, row.since = None, key, clock.utcnow()
    db.flush()
    dispatch(db)


def view(db: Session, actor: UserProfile) -> TasksOut:
    """►► **Was diese Person sieht** – ihre eine Aufgabe; die Zeichen: die eigene, beim Admin
    jede, bei allen die Aufgaben, die niemand Anwesendes kann («!»). ◄◄"""
    now = clock.utcnow()
    tasks = dispatch(db, now)
    holder = {r.task_key: r.person_object_id
              for r in db.query(TaskFocus).filter(TaskFocus.task_key.isnot(None)).all()}
    staff = _staff(db)
    here = [p for p in staff if presence(db, p, now).here]
    admin = policy.may(actor, "overview")
    mine: Optional[TaskMark] = None
    visible: list[TaskMark] = []
    for t in _order(tasks):
        is_mine = holder.get(t.key) == actor.object_id
        orphan = (not t.hint and t.key not in holder and t.only is None
                  and not any(may(p, t) for p in here))
        if not (is_mine or admin or orphan):
            continue
        out = TaskMark(key=t.key, object_id=t.object_id, part=t.part, mine=is_mine,
                      orphan=orphan)
        visible.append(out)
        if is_mine:
            mine = out
    return TasksOut(mine=mine, visible=visible)


# ─── Kompetenzen setzen ────────────────────────────────────────────────────────────────

def set_competences(db: Session, person: UserProfile, raw: Optional[list[str]]) -> None:
    """►► **Was eine Person kann – die eine Schreibstelle.** ◄◄ Nur Personal hat Kompetenzen;
    die letzte Person einer Kompetenz kann sie nicht verlieren (``competences.assert_drop``)."""
    wanted = comp.clean_list(raw)
    if wanted and not policy.is_staff(person):
        raise Invalid("Kompetenzen hat nur, wer im ERP arbeitet.", field="competences")
    db.flush()
    for lost in set(person.competences or []) - set(wanted):
        others = (db.query(func.count(UserProfile.id))
                  .filter(UserProfile.id != person.id,
                          UserProfile.role.in_(policy.STAFF_ROLES),
                          any_(UserProfile.competences) == lost).scalar())
        comp.assert_drop(lost, int(others or 0))
    person.competences = wanted
    db.flush()
