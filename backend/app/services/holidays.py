"""Feiertage und Zeit-Regeln einer eigenen Gesellschaft (Zeiterfassung).

►►► **Es zählt nur, was ein Mensch bestätigt.** ◄◄◄ Der Vorschlag kommt aus OpenHolidays
(openholidaysapi.org, CC BY 4.0) für den Kanton der Gesellschaft; übernommen wird er erst
mit «Übernehmen». Ist der Dienst nicht erreichbar, sagt es ein Satz – von Hand geht immer.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import timekeeping as tk
from ..models import CompanySettings, Holiday, TimeContract, UserProfile
from ..schemas.timekeeping import CompanyTimeView, HolidayOut, TaskOut
from . import sites
from .admin import log_audit
from .time_view import vocab
from .timekeeping import local, now_utc

PROPOSAL_URL = "https://openholidaysapi.org/PublicHolidays"


def company(db: Session, object_id: int) -> CompanySettings:
    c = sites.by_object_id(db, object_id)
    if c is None or not c.is_own:
        raise HTTPException(404, detail=f"«{object_id}» ist keine unserer Gesellschaften.")
    return c


def _admin(actor: UserProfile) -> None:
    if actor.role != "admin":
        raise HTTPException(403, detail="Feiertage und Regeln pflegt die Administration.")


def holiday_tasks(db: Session, c: CompanySettings, today: date) -> list[TaskOut]:
    """►►► **Fehlen die Feiertage?** ◄◄◄ Das laufende Jahr ohne Feiertag ist sofort dringend;
    das nächste ist ab 1. Oktober fällig und ab 1. Dezember dringend. Nur für eine
    Gesellschaft, auf die ein Vertrag lautet – eine ohne Personal braucht keine."""
    if db.query(TimeContract.id).filter(TimeContract.company_object_id == c.object_id,
                                        TimeContract.weekly_minutes > 0).first() is None:
        return []
    years = {d.year for (d,) in db.query(Holiday.day).filter(
        Holiday.company_object_id == c.object_id, Holiday.is_active.is_(True)).all()}
    out = []
    if today.year not in years:
        out.append(TaskOut(kind="holidays", day=date(today.year, 1, 1),
                           label=f"Feiertage {today.year} fehlen", age=tk.URGENT_DAYS))
    nxt = today.year + 1
    if today.month >= tk.HOLIDAYS_DUE_MONTH and nxt not in years:
        urgent = today.month >= tk.HOLIDAYS_URGENT_MONTH
        out.append(TaskOut(kind="holidays", day=date(nxt, 1, 1),
                           label=f"Feiertage {nxt} übernehmen",
                           age=tk.URGENT_DAYS if urgent else 0))
    return out


def view(db: Session, actor: UserProfile, object_id: int, year: Optional[int]) -> CompanyTimeView:
    c = company(db, object_id)
    today = local(now_utc()).date()
    year = year or today.year
    rows = (db.query(Holiday).filter(Holiday.company_object_id == c.object_id,
                                     Holiday.is_active.is_(True),
                                     Holiday.day >= date(year, 1, 1),
                                     Holiday.day <= date(year, 12, 31))
            .order_by(Holiday.day).all())
    rules = c.time_rules or {}
    return CompanyTimeView(
        company_object_id=c.object_id, canton=rules.get("canton"), cantons=list(tk.CANTONS),
        year=year, holidays=[HolidayOut(id=h.id, day=h.day, name=h.name) for h in rows],
        proof={a.key: tk.proof_from(a, rules.get("proof", {})) for a in tk.ARTS if a.proof},
        rules=list(tk.RULE_FACTS), tasks=holiday_tasks(db, c, today),
        can_edit=actor.role == "admin", vocab=vocab(rules.get("proof", {})))


def add(db: Session, actor: UserProfile, object_id: int, items) -> None:
    """Feiertage übernehmen – was schon dasteht, bleibt (kein Doppel)."""
    _admin(actor)
    c = company(db, object_id)
    taken = {h.day for h in db.query(Holiday).filter(
        Holiday.company_object_id == c.object_id, Holiday.is_active.is_(True)).all()}
    for it in items:
        if it.day in taken:
            continue
        db.add(Holiday(company_object_id=c.object_id, day=it.day, name=it.name.strip(),
                       created_by=actor.id))
        taken.add(it.day)
        log_audit(db, "holidays", "day", f"{tk.dmy(it.day)} {it.name}", actor.id,
                  object_id=c.object_id)
    db.flush()


def remove(db: Session, actor: UserProfile, object_id: int, holiday_id: int) -> None:
    """Ein Feiertag ist Stammdaten – er fällt weg (Soft-Delete), festgehalten im Audit-Log."""
    _admin(actor)
    c = company(db, object_id)
    h = db.query(Holiday).filter(Holiday.id == holiday_id,
                                 Holiday.company_object_id == c.object_id,
                                 Holiday.is_active.is_(True)).first()
    if h is None:
        raise HTTPException(404, detail=f"Den Feiertag «{holiday_id}» gibt es nicht (mehr).")
    h.is_active = False
    log_audit(db, "holidays", "is_active", "false", actor.id, object_id=c.object_id,
              old_value=f"{tk.dmy(h.day)} {h.name}")


def set_rules(db: Session, actor: UserProfile, object_id: int, data) -> None:
    _admin(actor)
    c = company(db, object_id)
    rules = dict(c.time_rules or {})
    fields = data.model_dump(exclude_unset=True)
    if "canton" in fields:
        if fields["canton"] not in (None, *tk.CANTON_CODES):
            raise HTTPException(400, detail=f"«{fields['canton']}» ist kein Kanton.")
        rules["canton"] = fields["canton"]
    if fields.get("proof") is not None:
        proof = dict(rules.get("proof", {}))
        for key, n in fields["proof"].items():
            art = tk.ART_BY_KEY.get(key)
            if art is None or art.proof is None:
                raise HTTPException(400, detail=f"«{key}» braucht keinen Nachweis.")
            if n is not None and not 0 <= n <= 30:
                raise HTTPException(400, detail="Nachweis ab Tag 1 bis 30 (leer = nie).")
            proof[key] = n or 0
        rules["proof"] = proof
    log_audit(db, "company_settings", "time_rules", str(rules), actor.id,
              object_id=c.object_id, old_value=str(c.time_rules))
    c.time_rules = rules


def _text(names: list) -> str:
    for n in names:
        if (n.get("language") or "").upper() == "DE":
            return n.get("text") or ""
    return (names[0].get("text") if names else "") or ""


def proposal(db: Session, actor: UserProfile, object_id: int, year: int) -> list[HolidayOut]:
    """Der Vorschlag für ein Jahr – geholt, nicht gespeichert."""
    _admin(actor)
    c = company(db, object_id)
    canton = (c.time_rules or {}).get("canton")
    if not canton:
        raise HTTPException(400, detail="Zuerst den Kanton der Gesellschaft wählen.")
    params = {"countryIsoCode": "CH", "languageIsoCode": "DE", "subdivisionCode": f"CH-{canton}",
              "validFrom": f"{year}-01-01", "validTo": f"{year}-12-31"}
    try:
        r = httpx.get(PROPOSAL_URL, params=params, timeout=8,
                      headers={"accept": "application/json"})
        r.raise_for_status()
        items = r.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, detail=("Der Vorschlag ist gerade nicht erreichbar – "
                                         "Feiertage lassen sich von Hand eintragen."))
    taken = {h.day for h in db.query(Holiday).filter(
        Holiday.company_object_id == c.object_id, Holiday.is_active.is_(True)).all()}
    out: dict[date, HolidayOut] = {}
    for it in items if isinstance(items, list) else []:
        try:
            start = datetime.strptime(it["startDate"], "%Y-%m-%d").date()
            end = datetime.strptime(it.get("endDate") or it["startDate"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            continue
        d = start
        while d <= end and d.year == year:
            out.setdefault(d, HolidayOut(day=d, name=_text(it.get("name") or [])[:120],
                                         taken=d in taken))
            d += timedelta(days=1)
    return [out[d] for d in sorted(out)]
