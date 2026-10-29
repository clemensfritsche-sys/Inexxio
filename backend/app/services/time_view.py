"""Zeiterfassung – was die Karte zeigt: EINE Antwort für Kopf, Konto, Monat und Tag.

Jede Zahl kommt aus ``timekeeping.ledger`` (gerechnet, nie gespeichert); hier wird sie nur
in die Form gebracht, die über die API-Grenze geht.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..domain import timekeeping as tk
from ..models import CompanySettings, TimeEntry, UserProfile
from ..schemas.timekeeping import (
    AbsenceOut, ArtOut, BookingOut, ContractOut, DayOut, HintOut, Mark, StampOut, TaskOut,
    TimeVocab, TimeView,
)
from . import timekeeping as t


def vocab(proof: Optional[dict] = None) -> TimeVocab:
    """Die Wörter – die Nachweis-Regel der Gesellschaft eingesetzt."""
    proof = proof or {}
    return TimeVocab(
        arts=[ArtOut(key=a.key, label=a.label, icon=a.icon, effect=a.effect,
                     effect_label=tk.EFFECTS[a.effect][0], effect_tip=tk.EFFECTS[a.effect][1],
                     proof=a.proof, proof_from=tk.proof_from(a, proof)) for a in tk.ARTS],
        hints=[HintOut(key=k, label=v[0], tone=v[1], icon=v[2]) for k, v in tk.HINTS.items()],
        texts=tk.TEXTS, correction_days=tk.CORRECTION_DAYS, week_max=tk.WEEK_MAX)


def _when(book: t.Book, r: TimeEntry) -> tuple[str, str]:
    by = book.names.get(r.created_by or 0, "?")
    return by, t.local(r.created_at).strftime("%d.%m.%Y %H:%M")


def _mark(book: t.Book, r: TimeEntry) -> Optional[Mark]:
    """«geändert» · «nachgetragen» · «durch …» – die Einzelheiten stehen im Hover."""
    by, at = _when(book, r)
    old = book.replaced.get(r.id)
    if old is not None and old.at is not None:
        n, x = 1, old
        while book.replaced.get(x.id) is not None:
            n, x = n + 1, book.replaced[x.id]
        times = f" ({n}×)" if n > 1 else ""
        return Mark(kind="changed", label="geändert",
                    tip=f"Vorher {t.clock(old.at)} · geändert von {by}, {at}{times}")
    if r.source == "manual":
        return Mark(kind="added", label="nachgetragen", tip=f"Nachgetragen von {by}, {at}")
    if r.created_by and r.created_by != book.person.id:
        return Mark(kind="by", label=f"durch {by}", tip=f"Gestempelt von {by}, {at}")
    return None


def _absence(book: t.Book, actor: UserProfile, a: TimeEntry, d: date, today: date) -> AbsenceOut:
    under = None
    for o in t.absences(book):
        if book.rank(o) < book.rank(a) and o.day <= d <= (o.until or o.day) and \
                (under is None or book.rank(o) > book.rank(under)):
            under = o
    replaces = None
    if under is not None:
        label = tk.ART_BY_KEY[under.art].label if under.art in tk.ART_BY_KEY else under.art
        replaces = (f"Ersetzt «{label} {under.day:%d.%m.}–{(under.until or under.day):%d.%m.%Y}» "
                    f"an diesem Tag")
    due = t.proof_due(book, a)
    return AbsenceOut(
        id=a.id, art=a.art or "", day=a.day, until=a.until or a.day, minutes=a.minutes,
        minutes_on_day=round(t.absence_minutes(book, a, d)), note=a.note,
        proof_url=a.proof_url, proof_needed=due is not None,
        proof_missing=due is not None and due <= today and not a.proof_url,
        replaces=replaces, can_void=not t.locked(actor, a.day, today))


def _day(book: t.Book, actor: UserProfile, day: t.Day, today: date, now) -> DayOut:
    d = day.d
    missing = {b.start.id for b in day.blocks if b.end is None and not t.is_running(b, now)}
    stamps = sorted((s for b in day.blocks for s in (b.start, b.end) if s is not None),
                    key=lambda s: s.at)
    return DayOut(
        day=d, workday=t.is_workday(book, d), holiday=t.holiday(book, d),
        soll=round(day.soll), ist=round(day.ist), credit=round(day.credit),
        today=d == today, future=d > today,
        locked=t.locked(actor, d, today) and t.contract_on(book, d) is not None,
        open=day.open, hints=day.hints,
        stamps=[StampOut(id=s.id, kind=s.kind, at=s.at, time=t.clock(s.at), mark=_mark(book, s),
                         missing_out=s.id in missing) for s in stamps],
        absence=_absence(book, actor, day.absence, d, today) if day.absence else None)


def _contracts(db: Session, book: t.Book, led: t.Ledger, today: date) -> list[ContractOut]:
    ids = {c.company_object_id for c in book.contracts if c.company_object_id}
    names = {c.object_id: c.company_name for c in
             db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids)).all()} \
        if ids else {}
    current = None
    for c in book.contracts:
        if c.valid_from <= today:
            current = c
    out = []
    for c in book.contracts:
        state = "planned" if c.valid_from > today else ("current" if c is current else "replaced")
        closing = led.closings.get(c.id) if c.weekly_minutes == 0 else None
        out.append(ContractOut(
            id=c.id, valid_from=c.valid_from, weekly_minutes=c.weekly_minutes,
            workdays=tk.days_of(c.workdays), vacation_weeks=c.vacation_weeks,
            company_object_id=c.company_object_id, company_name=names.get(c.company_object_id),
            state=state,
            closing_day=c.valid_from - timedelta(days=1) if c.weekly_minutes == 0 else None,
            closing_account=round(closing[0]) if closing else None,
            closing_vacation=round(closing[1]) if closing else None))
    return out


def _day_soll(book: t.Book, today: date) -> float:
    """Ein «Tag» der Ferienanzeige: das Tagessoll des aktuellen (sonst letzten) Vertrags."""
    c = t.contract_on(book, today)
    if c is None:
        past = [x for x in book.contracts if x.weekly_minutes > 0 and x.valid_from <= today]
        c = past[-1] if past else next((x for x in book.contracts if x.weekly_minutes > 0), None)
    return t.daily_soll(c) if c is not None else 0.0


def view(db: Session, actor: UserProfile, person: UserProfile, month: Optional[str]) -> TimeView:
    """►►► **Die Zeiterfassung einer Person** – Kopf, Konto, Verträge, ein Monat. ◄◄◄"""
    now = t.now_utc()
    today = t.local(now).date()
    first = _month(month, today)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    book = t.load(db, person)
    led = t.ledger(book, last, now)
    run = t.running(book, now)
    outs = [r for r in book.live if r.kind == "out" and r.day == today]
    # Heute = der Tag des laufenden Blocks (eine Nachtschicht gehört zum Vortag).
    shift = run.day if run is not None else today
    tday = led.days.get(shift)
    since = None
    if run is not None:
        since = t.clock(run.at) if run.day == today else f"gestern {t.clock(run.at)}"
    full_today = (lambda a: a is not None and a.minutes is None)(t.absence_on(book, today))
    ds = _day_soll(book, today)
    month_days = []
    d = first
    while d <= last:
        month_days.append(_day(book, actor, led.days.get(d) or t.Day(d), today, now))
        d += timedelta(days=1)
    opened = [x for x in sorted(led.days) if led.days[x].open and today - timedelta(14) <= x < today]
    return TimeView(
        person_object_id=person.object_id, has_contract=bool(book.contracts), now=now,
        today=today, present_since=since,
        last_out=t.clock(max(r.at for r in outs)) if outs else None,
        # Der Balken: gearbeitet plus Absenz (ein Ferientag ist erfüllt) gegen das Soll.
        today_ist=round(tday.ist + tday.credit) if tday else 0,
        today_soll=round(tday.soll) if tday else 0,
        account=round(led.account), vacation=round(led.vacation),
        vacation_days=round(led.vacation / ds, 1) if ds else None, day_soll=round(ds),
        born=person.date_of_birth is not None,
        # Stempeln geht, wo es einen Vertrag gibt – an einem ganztägigen Absenztag nur noch
        # das «Gehen» einer laufenden Schicht.
        can_stamp=t.may_see(actor, person) and (run is not None or (
            t.contract_on(book, today) is not None and not full_today)),
        is_admin=actor.role == "admin",
        contracts=_contracts(db, book, led, today),
        bookings=[BookingOut(id=r.id, day=r.day, note=r.note or "", minutes=r.minutes or 0,
                             vacation_minutes=r.vacation_minutes or 0,
                             by=book.names.get(r.created_by or 0))
                  for r in sorted((r for r in book.live if r.kind == "booking"),
                                  key=lambda r: (r.day, r.id))],
        month=f"{first:%Y-%m}", days=month_days,
        default_day=opened[-1] if opened else today,
        tasks=[TaskOut(kind=k, day=x, label=label, age=(today - x).days)
               for k, x, label in led.tasks],
        vocab=vocab(t.proof_rules(book, today)))


def _month(month: Optional[str], today: date) -> date:
    if month:
        try:
            y, m = (int(x) for x in month.split("-"))
            return date(y, m, 1)
        except ValueError:
            pass
    return today.replace(day=1)
