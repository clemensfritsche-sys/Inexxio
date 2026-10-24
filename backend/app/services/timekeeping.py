"""Zeiterfassung – rechnen und schreiben (docs/zeiterfassung-spezifikation.md).

►►► **Gespeichert wird nur, was ein Mensch eingibt; alles andere wird gerechnet.** ◄◄◄
Stundenkonto, Ferienguthaben, Hinweise, offene Tage und fehlende Nachweise sind
Ableitungen aus Vertrag, Einträgen und Feiertagen (``Ledger``). Keine Spalte trägt eine
Summe – es gibt also keine zweite Wahrheit, die veralten könnte.

►►► **Eine Schreibstelle** (``record``, wie ``process._pass``). ◄◄◄ Jeder Stempel, jede
Absenz, jede Buchung und jede Rücknahme geht hier durch: die Person wird gesperrt
(``FOR UPDATE``), die Regel geprüft (``entry_problem`` ↔ ``assert_entry``), dann **ein**
neuer Eintrag geschrieben. Geändert oder gelöscht wird nie – das verbietet zusätzlich ein
Trigger in der Datenbank (``domain/timekeeping.append_only_sql``).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import timekeeping as tk
from ..models import CompanySettings, Holiday, TimeContract, TimeEntry, UserProfile
from . import people, sites


def now_utc() -> datetime:
    """Die Serverzeit – ein Stempel trägt nie die Uhr des Geräts."""
    return datetime.now(timezone.utc)


def local(at: datetime) -> datetime:
    return at.astimezone(tk.ZONE)


def instant(d: date, minute: int) -> datetime:
    """Tag + Minute in Europe/Zurich → Zeitpunkt (UTC); richtig auch an der Zeitumstellung."""
    return datetime.combine(d, time(minute // 60, minute % 60), tk.ZONE).astimezone(timezone.utc)


def clock(at: datetime) -> str:
    return local(at).strftime("%H:%M")


# ─── Was zu einer Person geladen wird ───────────────────────────────────────────────

@dataclass
class Book:
    person: UserProfile
    contracts: list[TimeContract]
    #: Alle Einträge der Person (auch ersetzte) – die Vorgeschichte einer Zeile.
    rows: list[TimeEntry]
    #: Was heute gilt: nicht ersetzt, keine Rücknahme.
    live: list[TimeEntry]
    replaced: dict[int, TimeEntry]          # neuer Eintrag → der, den er ersetzt hat
    holidays: dict[tuple[int, date], str]   # (Gesellschaft, Tag) → Name
    rules: dict[int, dict]                  # Gesellschaft → time_rules
    names: dict[int, str]                   # user_profiles.id → Name


def load(db: Session, person: UserProfile) -> Book:
    oid = person.object_id
    contracts = (db.query(TimeContract)
                 .filter(TimeContract.person_object_id == oid, TimeContract.is_active.is_(True))
                 .order_by(TimeContract.valid_from).all())
    rows = (db.query(TimeEntry).filter(TimeEntry.person_object_id == oid)
            .order_by(TimeEntry.id).all())
    by_id = {r.id: r for r in rows}
    gone = {r.replaces_id for r in rows if r.replaces_id}
    live = [r for r in rows if r.id not in gone and r.kind != "void"]
    replaced = {r.id: by_id[r.replaces_id] for r in rows if r.replaces_id in by_id}
    companies = {c.company_object_id for c in contracts if c.company_object_id}
    holidays = {}
    rules = {}
    if companies:
        for h in db.query(Holiday).filter(Holiday.company_object_id.in_(companies),
                                          Holiday.is_active.is_(True)).all():
            holidays[(h.company_object_id, h.day)] = h.name
        for c in db.query(CompanySettings).filter(
                CompanySettings.object_id.in_(companies)).all():
            rules[c.object_id] = c.time_rules or {}
    actors = {r.created_by for r in rows if r.created_by}
    names = {u.id: u.display_name for u in
             db.query(UserProfile).filter(UserProfile.id.in_(actors)).all()} if actors else {}
    return Book(person, contracts, rows, live, replaced, holidays, rules, names)


# ─── Vertrag und Soll ───────────────────────────────────────────────────────────────

def contract_on(book: Book, d: date) -> Optional[TimeContract]:
    """Der Vertrag am Tag ``d`` (neuester Stichtag ≤ d); ``None`` vor dem Eintritt und ab
    dem Austritt (0 h)."""
    found = None
    for c in book.contracts:
        if c.valid_from <= d:
            found = c
    return found if found is not None and found.weekly_minutes > 0 else None


def daily_soll(c: TimeContract) -> float:
    n = len(tk.days_of(c.workdays))
    return c.weekly_minutes / n if n else 0.0


def holiday(book: Book, d: date) -> Optional[str]:
    c = contract_on(book, d)
    return book.holidays.get((c.company_object_id, d)) if c and c.company_object_id else None


def in_pattern(book: Book, d: date) -> bool:
    c = contract_on(book, d)
    return bool(c and c.workdays & (1 << d.weekday()))


def is_workday(book: Book, d: date) -> bool:
    return in_pattern(book, d) and holiday(book, d) is None


def soll(book: Book, d: date) -> float:
    return daily_soll(contract_on(book, d)) if is_workday(book, d) else 0.0


def proof_rules(book: Book, d: date) -> dict:
    c = contract_on(book, d)
    return (book.rules.get(c.company_object_id) or {}).get("proof", {}) if c else {}


# ─── Stempel → Blöcke ───────────────────────────────────────────────────────────────

@dataclass
class Block:
    start: TimeEntry
    end: Optional[TimeEntry]

    @property
    def day(self) -> date:
        return self.start.day


def pair(stamps: list[TimeEntry]) -> list[Block]:
    """Kommen bis zum nächsten Gehen ist ein Block – er gehört zum Tag des Kommens (auch
    über Mitternacht). Ein Kommen ohne Gehen innert ``RUNNING_MAX`` bleibt offen."""
    blocks: list[Block] = []
    cur: Optional[TimeEntry] = None
    for s in sorted(stamps, key=lambda x: (x.at, x.id or 0)):
        if s.kind == "in":
            if cur is not None:
                blocks.append(Block(cur, None))
            cur = s
        elif cur is not None and (s.at - cur.at) <= timedelta(minutes=tk.RUNNING_MAX):
            blocks.append(Block(cur, s))
            cur = None
    if cur is not None:
        blocks.append(Block(cur, None))
    return blocks


def sequence_problem(stamps: list[TimeEntry]) -> Optional[str]:
    """►►► **Kommen und Gehen wechseln sich ab.** ◄◄◄ Ein Kommen, solange ein anderes noch
    läuft, oder ein Gehen ohne Kommen davor, ist ein Fehler – der Satz nennt die Uhrzeit."""
    cur: Optional[TimeEntry] = None
    span = timedelta(minutes=tk.RUNNING_MAX)
    for s in sorted(stamps, key=lambda x: (x.at, x.id or 0)):
        if s.kind == "in":
            if cur is not None and s.at - cur.at < span:
                return (f"Am {tk.dmy(cur.day)} um {clock(cur.at)} ist schon «Kommen» erfasst – "
                        f"dazwischen fehlt «Gehen».")
            cur = s
        else:
            if cur is None or s.at - cur.at > span:
                return f"Vor «Gehen» am {tk.dmy(s.day)} um {clock(s.at)} fehlt «Kommen»."
            if s.at <= cur.at:
                return f"«Gehen» um {clock(s.at)} liegt nicht nach «Kommen» um {clock(cur.at)}."
            cur = None
    return None


def running(book: Book, now: datetime) -> Optional[TimeEntry]:
    """Das Kommen, das gerade läuft – sonst ``None`` (die Person ist nicht da)."""
    blocks = pair([r for r in book.live if r.kind in tk.STAMPS])
    if blocks and blocks[-1].end is None and \
            now - blocks[-1].start.at < timedelta(minutes=tk.RUNNING_MAX):
        return blocks[-1].start
    return None


def minutes(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 60


# ─── Absenzen ───────────────────────────────────────────────────────────────────────

def absences(book: Book) -> list[TimeEntry]:
    return [r for r in book.live if r.kind == "absence"]


def absence_on(book: Book, d: date) -> Optional[TimeEntry]:
    """Die Absenz, die am Tag gilt: an einem Arbeitstag die **jüngste**, die ihn deckt –
    eine neue Absenz ersetzt an ihren Tagen eine ältere."""
    if not is_workday(book, d):
        return None
    best = None
    for a in absences(book):
        if a.day <= d <= (a.until or a.day) and (best is None or a.id > best.id):
            best = a
    return best


def absence_minutes(book: Book, a: TimeEntry, d: date) -> float:
    s = soll(book, d)
    return s if a.minutes is None else min(a.minutes, s)


def workdays_in(book: Book, a: date, b: date) -> list[date]:
    out, d = [], a
    while d <= b:
        if is_workday(book, d):
            out.append(d)
        d += timedelta(days=1)
    return out


def proof_due(book: Book, a: TimeEntry) -> Optional[date]:
    """Ab welchem Tag diese Absenz einen Nachweis braucht – ``None`` = keinen."""
    art = tk.ART_BY_KEY.get(a.art or "")
    if art is None:
        return None
    n = tk.proof_from(art, proof_rules(book, a.day))
    days = workdays_in(book, a.day, a.until or a.day)
    if not n or len(days) < n:
        return None
    return days[n - 1]


# ─── Ein Tag und das ganze Konto ────────────────────────────────────────────────────

@dataclass
class Day:
    d: date
    soll: float = 0.0           # nach «Entfällt»
    ist: float = 0.0
    credit: float = 0.0
    vacation_used: float = 0.0
    accrual: float = 0.0
    absence: Optional[TimeEntry] = None
    blocks: list[Block] = field(default_factory=list)
    open: bool = False
    hints: list[str] = field(default_factory=list)

    @property
    def saldo(self) -> float:
        return self.ist + self.credit - self.soll


@dataclass
class Ledger:
    days: dict[date, Day]
    account: float              # Stundenkonto, Stand gestern (+ Buchungen)
    vacation: float             # Ferienguthaben heute (Minuten)
    closings: dict[int, tuple[float, float]]   # Austritts-Vertrag → (Konto, Ferien)
    tasks: list[tuple[str, date, str]]         # (Art, Tag, Satz)


def _born(book: Book) -> Optional[date]:
    return book.person.date_of_birth


def _day(book: Book, d: date, blocks: list[Block], now: datetime) -> Day:
    day = Day(d, blocks=blocks)
    base = soll(book, d)
    day.soll = base
    a = absence_on(book, d)
    day.absence = a
    if a is not None:
        m = absence_minutes(book, a, d)
        effect = tk.ART_BY_KEY[a.art].effect if a.art in tk.ART_BY_KEY else "fulfilled"
        if effect == "unpaid":
            day.soll -= m
        else:
            day.credit = m
            if effect == "vacation":
                day.vacation_used = m
    for b in blocks:
        end = b.end.at if b.end else (now if b is blocks[-1] and _live(b, now) else None)
        if end is not None:
            day.ist += minutes(b.start.at, end)
        if b.end is None and not _live(b, now):
            day.open = True
    c = contract_on(book, d)
    if c is not None:
        weeks = float(c.vacation_weeks)
        if _born(book):
            weeks = max(weeks, tk.legal_weeks(_born(book), d))
        share = 1.0
        if a is not None and tk.ART_BY_KEY.get(a.art or "") and \
                tk.ART_BY_KEY[a.art].effect == "unpaid" and base:
            share = max(0.0, 1 - absence_minutes(book, a, d) / base)
        day.accrual = weeks * c.weekly_minutes / 365 * share
    return day


def _live(b: Block, now: datetime) -> bool:
    return b.end is None and now - b.start.at < timedelta(minutes=tk.RUNNING_MAX)


def _hints(book: Book, day: Day, prev_end: Optional[datetime], week: float) -> None:
    """Die Ampel eines Tages – sie warnt nur."""
    closed = [b for b in day.blocks if b.end is not None]
    if closed and prev_end is not None:
        limit = tk.REST_U18 if _u18(book, day.d) else tk.REST
        if minutes(prev_end, closed[0].start.at) < limit:
            day.hints.append("rest")
    for b in closed:
        s, e = local(b.start.at), local(b.end.at)
        sm, em = s.hour * 60 + s.minute, e.hour * 60 + e.minute
        if sm < tk.NIGHT_TO or em > tk.NIGHT_FROM or e.date() > s.date():
            day.hints.append("night")
            break
    work = sum(minutes(b.start.at, b.end.at) for b in closed)
    pause = sum(minutes(closed[i - 1].end.at, closed[i].start.at) for i in range(1, len(closed)))
    if closed and pause < tk.needed_pause(work):
        day.hints.append("pause")
    if _u18(book, day.d) and work > tk.DAY_MAX_U18:
        day.hints.append("u18")
    if week <= tk.WEEK_MAX < week + work:
        day.hints.append("week")
    if closed and day.d.weekday() == 6 and not in_pattern(book, day.d):
        day.hints.append("sunday")


def _u18(book: Book, d: date) -> bool:
    return bool(_born(book)) and tk.age(_born(book), d) < 18


def ledger(book: Book, until: date, now: Optional[datetime] = None) -> Ledger:
    """►►► **Das Konto – vom Eintritt bis ``until``, Tag für Tag gerechnet.** ◄◄◄

    Stundenkonto = Summe der Tagessaldi bis **gestern** (ein offener Tag zählt erst, wenn er
    vollständig ist) plus die Buchungen. Ferien = Anspruch Tag für Tag (auch am Wochenende;
    nicht bei «Entfällt») minus Bezug bis heute, plus Buchungen. Ein Austritt hält den
    Schlussstand am Vortag fest."""
    now = now or now_utc()
    today = local(now).date()
    blocks_by_day: dict[date, list[Block]] = defaultdict(list)
    for b in pair([r for r in book.live if r.kind in tk.STAMPS]):
        blocks_by_day[b.day].append(b)
    starts = [c.valid_from for c in book.contracts] + list(blocks_by_day) + \
        [a.day for a in absences(book)]
    first = min(starts) if starts else today
    days: dict[date, Day] = {}
    account = vacation = 0.0
    closings: dict[int, tuple[float, float]] = {}
    exits = {c.valid_from: c.id for c in book.contracts if c.weekly_minutes == 0}
    prev_end: Optional[datetime] = None
    week = 0.0
    d = first
    while d <= max(until, today):
        if d in exits:
            closings[exits[d]] = (account, vacation)
        if d.weekday() == 0:
            week = 0.0
        day = _day(book, d, blocks_by_day.get(d, []), now)
        if d < today:
            _hints(book, day, prev_end, week)
        elif day.blocks and prev_end is not None:
            _hints(book, day, prev_end, week)
            day.hints = [h for h in day.hints if h == "rest"]
        closed = [b for b in day.blocks if b.end is not None]
        if closed:
            prev_end = closed[-1].end.at
        week += day.ist
        if d < today and not day.open:
            account += day.saldo
        if d <= today:
            vacation += day.accrual - day.vacation_used
        if day.open:
            day.hints.insert(0, "open")
        days[d] = day
        d += timedelta(days=1)
    for r in book.live:
        if r.kind == "booking":
            account += r.minutes or 0
            vacation += r.vacation_minutes or 0
    return Ledger(days, account, vacation, closings, tasks(book, now))


def tasks(book: Book, now: Optional[datetime] = None) -> list[tuple[str, date, str]]:
    """Was die Person **selbst** erledigen muss: ein fehlendes «Gehen», ein fälliger
    Nachweis. Ein Hinweis (Pause, Ruhezeit) ist keine Aufgabe – nachträglich lässt er sich
    nicht erledigen. Gerechnet ohne das ganze Konto (die Zahl im Feed braucht nur das)."""
    now = now or now_utc()
    today = local(now).date()
    out = [("open", b.day, f"«Gehen» fehlt am {tk.dmy(b.day)}")
           for b in pair([r for r in book.live if r.kind in tk.STAMPS])
           if b.end is None and not _live(b, now)]
    for a in absences(book):
        due = proof_due(book, a)
        if due is not None and due <= today and not a.proof_url:
            art = tk.ART_BY_KEY[a.art]
            out.append(("proof", due, f"{art.proof} fehlt ({art.label} ab {tk.dmy(a.day)})"))
    return sorted(out, key=lambda t: t[1])


# ─── Wer darf was ───────────────────────────────────────────────────────────────────

def may_see(actor: UserProfile, person: UserProfile) -> bool:
    """Jede Person sieht nur ihre eigene Zeiterfassung, der Admin alle."""
    return actor.role == "admin" or (actor.id == person.id and actor.role in people.STAFF_ROLES)


def locked(actor: UserProfile, d: date, today: date) -> bool:
    """Abgeschlossen: älter als ``CORRECTION_DAYS`` – ändern kann ihn nur der Admin."""
    return actor.role != "admin" and d < today - timedelta(days=tk.CORRECTION_DAYS)


# ─── Die eine Schreibstelle ─────────────────────────────────────────────────────────

Problem = tuple[int, str]


def _minute(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    h, m = (int(x) for x in raw.split(":"))
    return h * 60 + m if h < 24 and m < 60 else None


def _no_contract(d: date) -> Problem:
    return 400, f"Am {tk.dmy(d)} besteht kein Vertrag – Eintritt und Austritt pflegt die Administration."


def _locked(d: date) -> Problem:
    return 403, (f"Der {tk.dmy(d)} ist abgeschlossen (älter als {tk.CORRECTION_DAYS} Tage) – "
                 f"ändern kann ihn nur die Administration.")


def _full_day(book: Book, d: date) -> Optional[Problem]:
    a = absence_on(book, d)
    if a is not None and a.minutes is None:
        return 400, (f"Am {tk.dmy(d)} ist «{tk.ART_BY_KEY[a.art].label}» als ganzer Tag erfasst – "
                     f"zuerst die Absenz zurücknehmen oder auf Stunden erfassen.")
    return None


def _live_row(book: Book, rid: Optional[int], kinds: tuple[str, ...]) -> Optional[TimeEntry]:
    return next((r for r in book.live if r.id == rid and r.kind in kinds), None)


def stamp_problem(book: Book, actor: UserProfile, kind: str, at: datetime, now: datetime,
                  old: Optional[TimeEntry] = None) -> Optional[Problem]:
    """Darf dieser Stempel so stehen? Gemeinsam für Wisch, Nachtrag und Korrektur."""
    d, today = local(at).date(), local(now).date()
    if locked(actor, d, today) or (old is not None and locked(actor, old.day, today)):
        return _locked(old.day if old is not None and old.day < d else d)
    if at > now + timedelta(seconds=tk.DOUBLE_SWIPE_S):
        return 400, f"Liegt in der Zukunft – jetzt ist es {clock(now)}."
    if contract_on(book, d) is None:
        return _no_contract(d)
    full = _full_day(book, d)
    if full is not None:
        return full
    stamps = [r for r in book.live if r.kind in tk.STAMPS and r is not old]
    candidate = TimeEntry(kind=kind, at=at, day=d, id=None)
    seq = sequence_problem(stamps + [candidate])
    return (400, seq) if seq else None


def _stamp(book: Book, actor: UserProfile, data, now: datetime
           ) -> tuple[Optional[TimeEntry], Optional[Problem]]:
    old = None
    if data.replaces_id is not None:
        old = _live_row(book, data.replaces_id, tk.STAMPS)
        if old is None:
            return None, (404, f"Den Stempel «{data.replaces_id}» gibt es nicht (mehr).")
    kind = old.kind if old is not None else data.kind
    d, minute = data.day or (old.day if old else None), _minute(data.time)
    if d is None or minute is None:
        return None, (400, "Uhrzeit als HH:MM angeben.")
    at = instant(d, minute)
    if old is not None and old.at == at:
        return None, None                       # unverändert = keine Änderung
    problem = stamp_problem(book, actor, kind, at, now, old)
    if problem is not None and kind == "out":
        # «Gehen» nach Mitternacht: 02:00 nach einem Kommen um 22:00 ist der Folgetag.
        later = at + timedelta(days=1)
        if later <= now and stamp_problem(book, actor, kind, later, now, old) is None:
            at, problem = later, None
    if problem is not None:
        return None, problem
    return TimeEntry(kind=kind, day=local(at).date(), at=at, source="manual",
                     replaces_id=old.id if old is not None else None), None


def _absence(book: Book, actor: UserProfile, data, now: datetime
             ) -> tuple[Optional[TimeEntry], Optional[Problem]]:
    art = tk.ART_BY_KEY.get(data.art or "")
    if art is None:
        return None, (400, f"«{data.art}» ist keine Absenzart.")
    if data.day is None:
        return None, (400, "Für eine Absenz fehlt der Tag.")
    d, until, today = data.day, data.until or data.day, local(now).date()
    if until < d:
        return None, (400, f"«Bis» liegt vor dem {tk.dmy(d)}.")
    if (until - d).days > 366:
        return None, (400, "Eine Absenz dauert höchstens ein Jahr – bitte aufteilen.")
    if locked(actor, d, today):
        return None, _locked(d)
    if not is_workday(book, d):
        return None, (400, f"Der {tk.dmy(d)} ist kein Arbeitstag.")
    if data.minutes is not None and data.minutes <= 0:
        return None, (400, "Dauer als H:MM, grösser als 0:00.")
    stamped = {r.day for r in book.live if r.kind in tk.STAMPS}
    x = d
    while x <= until:
        if contract_on(book, x) is None:
            return None, _no_contract(x)
        if is_workday(book, x):
            if data.minutes is not None and data.minutes > soll(book, x):
                return None, (400, f"Mehr als ein ganzer Tag ({tk.hm(soll(book, x))} h) am {tk.dmy(x)}.")
            if data.minutes is None and x in stamped:
                return None, (400, f"Am {tk.dmy(x)} gibt es Stempel – «Stunden» wählen.")
        x += timedelta(days=1)
    return TimeEntry(kind="absence", day=d, until=until, art=art.key, minutes=data.minutes,
                     note=(data.note or "").strip() or None, proof_url=data.proof_url,
                     source="manual"), None


def _other(book: Book, actor: UserProfile, data, now: datetime
           ) -> tuple[Optional[TimeEntry], Optional[Problem]]:
    """Nachweis, Rücknahme, Buchung."""
    today = local(now).date()
    if data.kind == "proof":
        old = _live_row(book, data.replaces_id, ("absence",))
        if old is None or not data.proof_url:
            return None, (400, "Den Nachweis an eine Absenz hängen.")
        # Ein Nachweis lässt sich JEDERZEIT nachreichen – auch an einem abgeschlossenen Tag.
        return TimeEntry(kind="absence", day=old.day, until=old.until, art=old.art,
                         minutes=old.minutes, note=old.note, proof_url=data.proof_url,
                         source=old.source, replaces_id=old.id), None
    if data.kind == "void":
        old = _live_row(book, data.replaces_id, tk.STAMPS + ("absence",))
        if old is None:
            return None, (404, f"Den Eintrag «{data.replaces_id}» gibt es nicht (mehr).")
        if locked(actor, old.day, today):
            return None, _locked(old.day)
        if old.kind in tk.STAMPS:
            seq = sequence_problem([r for r in book.live if r.kind in tk.STAMPS and r is not old])
            if seq:
                return None, (400, seq)
        return TimeEntry(kind="void", day=old.day, replaces_id=old.id), None
    if actor.role != "admin":
        return None, (403, "Buchungen macht nur die Administration.")
    if data.day is None:
        return None, (400, "Für eine Buchung fehlt das Datum.")
    hours, vac = data.minutes or 0, data.vacation_minutes or 0
    if not hours and not vac:
        return None, (400, "Stunden oder Ferien angeben.")
    if max(abs(hours), abs(vac)) > 5000 * 60:
        return None, (400, "So viele Stunden auf einmal sind kein Übertrag – bitte prüfen.")
    if not (data.note or "").strip():
        return None, (400, "Grund angeben – er steht später an der Buchung.")
    return TimeEntry(kind="booking", day=data.day, minutes=hours, vacation_minutes=vac,
                     note=data.note.strip()), None


def entry_problem(book: Book, actor: UserProfile, data, now: datetime
                  ) -> tuple[Optional[TimeEntry], Optional[Problem]]:
    """►►► **Darf dieser Eintrag geschrieben werden?** ◄◄◄ Gibt den neuen Eintrag zurück
    oder den Grund (Status, Satz). ``(None, None)`` = nichts zu tun (unverändert). Die
    zweite Form derselben Regel ist ``assert_entry``."""
    if not may_see(actor, book.person):
        return None, (403, f"Die Zeiterfassung von «{book.person.display_name}» führt nur "
                           f"sie selbst oder die Administration.")
    if data.kind in tk.STAMPS:
        return _stamp(book, actor, data, now)
    if data.kind == "absence":
        return _absence(book, actor, data, now)
    return _other(book, actor, data, now)


def assert_entry(book: Book, actor: UserProfile, data, now: datetime) -> Optional[TimeEntry]:
    entry, problem = entry_problem(book, actor, data, now)
    if problem is not None:
        raise HTTPException(problem[0], detail=problem[1])
    return entry


def _lock(db: Session, person: UserProfile) -> None:
    """Eine Person zur Zeit: zwei Wische oder zwei Korrekturen derselben Person laufen
    nacheinander, nie gegeneinander."""
    db.query(UserProfile.id).filter(UserProfile.id == person.id).with_for_update().one()


def _write(db: Session, actor: UserProfile, person: UserProfile, entry: TimeEntry) -> TimeEntry:
    entry.person_object_id = person.object_id
    entry.created_by = actor.id
    db.add(entry)
    db.flush()
    return entry


def _check_proof(db: Session, url: Optional[str]) -> None:
    if not url:
        return
    from . import attachments
    prefix = "/api/v1/attachments/"
    token = url[len(prefix):] if url.startswith(prefix) else ""
    try:
        attachments.get_by_token(db, token)
    except HTTPException:
        raise HTTPException(400, detail="Der Nachweis ist kein hochgeladenes Bild.")


def record(db: Session, actor: UserProfile, person: UserProfile, data) -> Optional[TimeEntry]:
    """►►► **Die EINE Schreibstelle der Zeiterfassung.** ◄◄◄ Sperren, prüfen, schreiben –
    committet nicht (der Router schliesst ab)."""
    _check_proof(db, data.proof_url)
    _lock(db, person)
    book = load(db, person)
    entry = assert_entry(book, actor, data, now_utc())
    return _write(db, actor, person, entry) if entry is not None else None


def preview(db: Session, actor: UserProfile, person: UserProfile, data) -> dict:
    """►►► **Die Wirkung vor dem Speichern** – dieselbe Prüfung wie ``record``, ohne zu
    schreiben. Für eine Absenz: Arbeitstage, Stunden, was sie ersetzt und die Ferien danach
    (Guthaben heute minus alle geplanten Ferien, mit dieser Absenz)."""
    now = now_utc()
    today = local(now).date()
    book = load(db, person)
    entry, problem = entry_problem(book, actor, data, now)
    out: dict = {"problem": problem[1] if problem else None}
    if entry is None or entry.kind != "absence":
        return out
    until = entry.until or entry.day
    horizon = max([until] + [a.until or a.day for a in absences(book)])
    old = ledger(book, horizon, now)
    entry.id = 1 << 62                          # die jüngste – sie gilt an ihren Tagen
    book.live.append(entry)
    new = ledger(book, horizon, now)
    book.live.pop()
    days = workdays_in(book, entry.day, until)
    labels: dict[str, int] = defaultdict(int)
    for d in days:
        was = old.days[d].absence
        if was is not None and was.art in tk.ART_BY_KEY:
            labels[tk.ART_BY_KEY[was.art].label] += 1
    planned = sum(new.days[d].vacation_used + old.days[d].accrual - new.days[d].accrual
                  for d in new.days if d > today)
    art = tk.ART_BY_KEY[entry.art]
    due = proof_due(book, entry)
    out.update(
        workdays=len(days), minutes=round(sum(absence_minutes(book, entry, d) for d in days)),
        replaces=", ".join(f"{k} an {n} Tag{'en' if n > 1 else ''}" for k, n in labels.items())
        or None,
        vacation_after=round(new.vacation - planned),
        proof=art.proof if due is not None else None,
        proof_from=tk.proof_from(art, proof_rules(book, entry.day)) if due is not None else None)
    return out


def swipe(db: Session, actor: UserProfile, person: UserProfile, direction: str,
          key: str) -> Optional[TimeEntry]:
    """Ein Wisch – Serverzeit. Derselbe Schlüssel zweimal, ein zweiter Wisch innert
    ``DOUBLE_SWIPE_S`` oder eine Richtung, die schon gilt (zweites Gerät), schreibt nichts."""
    _lock(db, person)
    if db.query(TimeEntry.id).filter(TimeEntry.idem_key == key).first() is not None:
        return None
    book = load(db, person)
    if not may_see(actor, person):
        raise HTTPException(403, detail=f"Die Zeiterfassung von «{person.display_name}» führt "
                                        f"nur sie selbst oder die Administration.")
    now = now_utc()
    if (running(book, now) is not None) == (direction == "in"):
        return None
    stamps = [r for r in book.live if r.kind in tk.STAMPS]
    if stamps and now - max(s.at for s in stamps) < timedelta(seconds=tk.DOUBLE_SWIPE_S):
        return None
    problem = stamp_problem(book, actor, direction, now, now)
    if problem is not None:
        raise HTTPException(problem[0], detail=problem[1])
    return _write(db, actor, person, TimeEntry(
        kind=direction, day=local(now).date(), at=now, source="swipe", idem_key=key))


# ─── Vertrag ────────────────────────────────────────────────────────────────────────

def contract_problem(db: Session, actor: UserProfile, book: Book, data) -> Optional[Problem]:
    """Darf dieser Vertrag angelegt werden? (Zweite Form: ``add_contract`` weist ab.)"""
    if actor.role != "admin":
        return 403, "Verträge pflegt die Administration."
    born = book.person.date_of_birth
    if born is None:
        return 400, ("Geburtsdatum fehlt in den Stammdaten – es bestimmt Jugendschutz und "
                     "gesetzliche Ferien.")
    if any(c.valid_from == data.valid_from for c in book.contracts):
        return 409, f"Für den {tk.dmy(data.valid_from)} gibt es schon einen Vertrag."
    if data.weekly_minutes == 0:
        before = [c for c in book.contracts if c.valid_from < data.valid_from]
        if not before or before[-1].weekly_minutes == 0:
            return 400, "Ein Austritt braucht einen Vertrag davor."
        return None
    if data.weekly_minutes > tk.WEEK_MAX:
        return 400, "Mehr als die gesetzliche Höchstarbeitszeit (45 h pro Woche)."
    if not tk.mask_of(data.workdays):
        return 400, "Mindestens einen Arbeitstag wählen."
    legal = tk.legal_weeks(born, data.valid_from)
    weeks = data.vacation_weeks if data.vacation_weeks is not None else legal
    if weeks < legal:
        return 400, f"Weniger Ferien als gesetzlich ({legal} Wochen am Stichtag)."
    if weeks > 12:
        return 400, "Mehr als 12 Ferienwochen – bitte prüfen."
    company = data.company_object_id or book.person.company_object_id
    if company is None:
        return 400, f"«{book.person.display_name}» braucht eine unserer Gesellschaften."
    own = sites.by_object_id(db, company)
    if own is None or not own.is_own:
        return 400, f"«{company}» ist keine unserer Gesellschaften."
    return None


def add_contract(db: Session, actor: UserProfile, person: UserProfile, data) -> TimeContract:
    _lock(db, person)
    book = load(db, person)
    problem = contract_problem(db, actor, book, data)
    if problem is not None:
        raise HTTPException(problem[0], detail=problem[1])
    if data.weekly_minutes == 0:
        prev = [c for c in book.contracts if c.valid_from < data.valid_from][-1]
        company, mask, weeks = prev.company_object_id, 0, 0
    else:
        company = data.company_object_id or person.company_object_id
        mask = tk.mask_of(data.workdays)
        weeks = data.vacation_weeks if data.vacation_weeks is not None else \
            tk.legal_weeks(person.date_of_birth, data.valid_from)
    c = TimeContract(person_object_id=person.object_id, valid_from=data.valid_from,
                     weekly_minutes=data.weekly_minutes, workdays=mask, vacation_weeks=weeks,
                     company_object_id=company, created_by=actor.id)
    db.add(c)
    db.flush()
    return c
