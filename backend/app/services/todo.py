"""►►► **Was zu tun ist – die EINE Zahl am Symbol eines Datensatzes.** ◄◄◄

Offene Nachrichten (``communication.open_counts``), Aufgaben der Zeiterfassung
(``timekeeping.tasks``), überfällige Rechnungen (``payment_list.overdue_counts``), fehlende
Pflichtangaben (``people.missing_fields``), an einer
eigenen Gesellschaft fehlende Feiertage (``holidays.holiday_tasks``) und Rechtstexte
(``legal.FIELD_OF``), am Auftrag anstehende Papiere (``voucher_money.papers_due``) und erwartete
Dokumente (``requirements``). Jede Quelle rechnet
selbst; hier wird nur gezählt. Rot, sobald etwas dringend ist (überfällige Nachricht,
Aufgabe ab ``URGENT_DAYS`` Tagen).

Wer was sieht: Nachrichten und Pflichtangaben jedes Personal (wie bisher den Verlauf);
die Zeiterfassung nur die Person selbst und der Admin; die Feiertage nur der Admin.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session, selectinload

from ..domain import timekeeping as tk
from ..models import CompanySettings, TimeContract, UserProfile
from ..schemas.timekeeping import TodoItem, TodoOut
from . import communication, holidays, legal, payment_list, people, timekeeping


def _time_items(db: Session, actor: UserProfile) -> dict[int, list[TodoItem]]:
    oids = {o for (o,) in db.query(TimeContract.person_object_id).distinct().all()}
    if actor.role != "admin":
        oids &= {actor.object_id}
    out: dict[int, list[TodoItem]] = {}
    if not oids:
        return out
    now = timekeeping.now_utc()
    today = timekeeping.local(now).date()
    for person in db.query(UserProfile).filter(UserProfile.object_id.in_(oids)).all():
        found = timekeeping.tasks(timekeeping.load(db, person), now)
        if found:
            out[person.object_id] = [
                TodoItem(section="zeiterfassung", label=label, count=1,
                         red=(today - d).days >= tk.URGENT_DAYS) for _, d, label in found]
    return out


def _documents(db: Session) -> list[tuple[int, str]]:
    """Am Auftrag: ein Papier, das zur Freigabe ansteht, und ein Dokument, auf das ein Modul
    wartet (der Nachweis einer Absenz zählt schon bei der Zeiterfassung). Gelesen werden nur
    Belege, denen ein Papier fehlt (``voucher_money.paper_candidates``); ob es ansteht, sagt
    ``papers_due``."""
    from ..domain import voucher as vo
    from . import requirements, voucher, voucher_money
    out = [(r.object_id, r.label) for r in requirements.of_vouchers(db)]
    with voucher.reading(db):
        for row, oid in voucher_money.paper_candidates(db):
            for kind in voucher_money.papers_due(db, row):
                out.append((oid, f"{vo.document_word(kind)} freigeben"))
    return out


def todo(db: Session, actor: UserProfile) -> list[TodoOut]:
    items: dict[int, list[TodoItem]] = defaultdict(list)
    for c in communication.open_counts(db):
        items[c.object_id].append(TodoItem(
            section="kommunikation", count=c.open, red=bool(c.overdue),
            label=f"{c.open} offene Nachricht{'en' if c.open != 1 else ''}"))
    for oid, found in _time_items(db, actor).items():
        items[oid] += found
    # **Überfällige Rechnungen** – keine eigene Mahnliste: sie zählen an der Person.
    for oid, n in payment_list.overdue_counts(db).items():
        items[oid].append(TodoItem(section="zahlungen", count=n, red=True,
                                   label=f"{n} Rechnung{'en' if n != 1 else ''} überfällig"))
    for u in (db.query(UserProfile).options(selectinload(UserProfile.addresses))
              .filter(UserProfile.object_id.isnot(None), UserProfile.is_active.is_(True)).all()):
        for m in people.missing_fields(u):
            items[u.object_id].append(TodoItem(section=m["section"], count=1,
                                               label=f"{m['label']} fehlt"))
    for oid, label in _documents(db):
        items[oid].append(TodoItem(section="dokumente", count=1, label=label))
    if actor.role == "admin":
        for c in db.query(CompanySettings).filter(CompanySettings.is_own.is_(True),
                                                  CompanySettings.is_active.is_(True)).all():
            for kind in legal.FIELD_OF:
                if c.object_id and legal.document_of(db, c, kind) is None:
                    items[c.object_id].append(TodoItem(
                        section="dokumente", count=1, label=f"{legal.KINDS[kind][0]} fehlt"))
        today = timekeeping.local(timekeeping.now_utc()).date()
        for c in db.query(CompanySettings).filter(CompanySettings.is_own.is_(True),
                                                  CompanySettings.is_active.is_(True)).all():
            for task in holidays.holiday_tasks(db, c, today):
                items[c.object_id].append(TodoItem(section="feiertage", count=1, label=task.label,
                                                   red=task.age >= tk.URGENT_DAYS))
    return [TodoOut(object_id=oid, count=sum(i.count for i in its), red=any(i.red for i in its),
                    items=its) for oid, its in items.items() if its]
