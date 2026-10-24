"""Zeiterfassung – dünn: lesen, ein Wisch, ein Eintrag, ein Vertrag; Feiertage und Regeln der
Gesellschaft; «zu tun» für den Feed. Jede Schreib-Route antwortet mit der neuen Ansicht."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.timekeeping import (
    CompanyTimeView, ContractIn, EntryIn, EntryPreview, HolidayOut, HolidaysIn, SwipeIn, TimeRulesIn,
    TimeView, TodoOut,
)
from ..services import holidays, time_view, timekeeping, todo

router = APIRouter(prefix="/api/v1/erp", tags=["timekeeping"])

MONTH = Query(None, pattern=r"^\d{4}-\d{2}$")


def _person(db: Session, actor: UserProfile, object_id: int) -> UserProfile:
    person = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if person is None:
        raise HTTPException(404, detail=f"«{object_id}» ist keine Person.")
    if not timekeeping.may_see(actor, person):
        raise HTTPException(403, detail=f"Die Zeiterfassung von «{person.display_name}» sieht "
                                        f"nur sie selbst und die Administration.")
    return person


def _done(db: Session, actor: UserProfile, person: UserProfile, month: Optional[str]) -> TimeView:
    db.commit()
    return time_view.view(db, actor, person, month)


@router.get("/time/{object_id}", response_model=TimeView)
def read_time(object_id: int, month: Optional[str] = MONTH, db: Session = Depends(get_db),
              actor: UserProfile = Depends(require_employee)):
    """Die Zeiterfassung einer Person – Kopf, Konto, Verträge, ein Monat."""
    return time_view.view(db, actor, _person(db, actor, object_id), month)


@router.post("/time/{object_id}/swipe", response_model=TimeView)
def swipe(object_id: int, data: SwipeIn, month: Optional[str] = MONTH,
          db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    """Kommen ↔ Gehen – Serverzeit, ein Schlüssel je Wisch."""
    person = _person(db, actor, object_id)
    notice = timekeeping.swipe(db, actor, person, data.direction, data.key)
    view = _done(db, actor, person, month)
    view.notice = notice
    return view


@router.post("/time/{object_id}/entries", response_model=TimeView)
def add_entry(object_id: int, data: EntryIn, month: Optional[str] = MONTH,
              db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    """Stempel nachtragen oder korrigieren, Absenz, Nachweis, Buchung, Rücknahme – EIN Weg."""
    person = _person(db, actor, object_id)
    timekeeping.record(db, actor, person, data)
    return _done(db, actor, person, month)


@router.post("/time/{object_id}/entries/preview", response_model=EntryPreview)
def preview_entry(object_id: int, data: EntryIn, db: Session = Depends(get_db),
                  actor: UserProfile = Depends(require_employee)):
    """Was dieser Eintrag bewirken würde – dieselbe Regel wie beim Speichern, ohne zu
    schreiben (Arbeitstage, Stunden, Ersetzt, Ferien danach, Nachweis, Grund)."""
    person = _person(db, actor, object_id)
    return EntryPreview(**timekeeping.preview(db, actor, person, data))


@router.post("/time/{object_id}/contracts", response_model=TimeView)
def add_contract(object_id: int, data: ContractIn, month: Optional[str] = MONTH,
                 db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    """Neuer Vertrag ab Stichtag (nur Admin); 0 h = Austritt."""
    person = _person(db, actor, object_id)
    timekeeping.add_contract(db, actor, person, data)
    return _done(db, actor, person, month)


@router.get("/time/companies/{object_id}", response_model=CompanyTimeView)
def company_time(object_id: int, year: Optional[int] = Query(None, ge=2000, le=2100),
                 db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    """Feiertage, Nachweis-Regeln und Regeln des Landes einer eigenen Gesellschaft."""
    return holidays.view(db, actor, object_id, year)


@router.get("/time/companies/{object_id}/proposal", response_model=list[HolidayOut])
def holiday_proposal(object_id: int, year: int = Query(..., ge=2000, le=2100),
                     db: Session = Depends(get_db),
                     actor: UserProfile = Depends(require_employee)):
    """Vorschlag der Feiertage (OpenHolidays) – geholt, nicht gespeichert."""
    return holidays.proposal(db, actor, object_id, year)


@router.post("/time/companies/{object_id}/holidays", response_model=CompanyTimeView)
def add_holidays(object_id: int, data: HolidaysIn, year: Optional[int] = Query(None),
                 db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    holidays.add(db, actor, object_id, data.holidays)
    db.commit()
    return holidays.view(db, actor, object_id, year)


@router.delete("/time/companies/{object_id}/holidays/{holiday_id}",
               response_model=CompanyTimeView)
def remove_holiday(object_id: int, holiday_id: int, year: Optional[int] = Query(None),
                   db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    holidays.remove(db, actor, object_id, holiday_id)
    db.commit()
    return holidays.view(db, actor, object_id, year)


@router.put("/time/companies/{object_id}/rules", response_model=CompanyTimeView)
def set_rules(object_id: int, data: TimeRulesIn, year: Optional[int] = Query(None),
              db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    holidays.set_rules(db, actor, object_id, data)
    db.commit()
    return holidays.view(db, actor, object_id, year)


@router.get("/todo", response_model=list[TodoOut])
def read_todo(db: Session = Depends(get_db), actor: UserProfile = Depends(require_employee)):
    """Je Datensatz, was zu tun ist – die Zahl am Symbol in Feed und Kopf."""
    return todo.todo(db, actor)
