"""Zeiterfassung – was über die API-Grenze geht. Jede Zahl ist in **Minuten**."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── Eingaben ───────────────────────────────────────────────────────────────────────

class SwipeIn(BaseModel):
    """Ein Wisch: die Richtung, die der Knopf zeigte, und ein Schlüssel je Wisch – derselbe
    Schlüssel zweimal (Netz wackelt) schreibt nur einmal."""
    direction: Literal["in", "out"]
    key: str = Field(min_length=8, max_length=64)


class EntryIn(BaseModel):
    """EIN Eingang für alles, was einen Tag füllt oder ein Konto bewegt.

    * ``in``/``out`` – ein Stempel am ``day`` um ``time`` (nachgetragen); mit ``replaces_id``
      die Korrektur eines Stempels.
    * ``absence`` – ``art`` von ``day`` bis ``until``; ``minutes`` je Tag, leer = ganzer Tag.
    * ``proof`` – der Nachweis zu einer Absenz (``replaces_id``, ``proof_url``).
    * ``booking`` – nur Admin: ``minutes`` (Stundenkonto ±), ``vacation_minutes``, ``note``.
    * ``void`` – nimmt den Eintrag ``replaces_id`` zurück (festgehalten, nicht gelöscht).
    """
    kind: Literal["in", "out", "absence", "proof", "booking", "void"]
    day: Optional[date] = None
    time: Optional[str] = Field(None, pattern=r"^\d{1,2}:\d{2}$")
    until: Optional[date] = None
    art: Optional[str] = None
    minutes: Optional[int] = None
    vacation_minutes: Optional[int] = None
    note: Optional[str] = Field(None, max_length=500)
    proof_url: Optional[str] = Field(None, max_length=200)
    replaces_id: Optional[int] = None


class ContractIn(BaseModel):
    valid_from: date
    weekly_minutes: int = Field(ge=0)
    workdays: list[int] = []
    vacation_weeks: Optional[Decimal] = None
    company_object_id: Optional[int] = None


class HolidayIn(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=120)


class HolidaysIn(BaseModel):
    """Mehrere Feiertage auf einmal übernehmen (der bestätigte Vorschlag)."""
    holidays: list[HolidayIn]


class TimeRulesIn(BaseModel):
    """Was die Gesellschaft festlegt: der Kanton und ab welchem Arbeitstag ein Nachweis
    nötig ist (je Absenzart; ``None``/0 = nie)."""
    canton: Optional[str] = None
    proof: Optional[dict[str, Optional[int]]] = None


# ─── Ausgaben ───────────────────────────────────────────────────────────────────────

class Mark(BaseModel):
    """Was an einer Zeile vermerkt ist: «geändert», «nachgetragen», «durch …» – Einzelheiten
    im Hover."""
    kind: Literal["changed", "added", "by"]
    label: str
    tip: str


class StampOut(BaseModel):
    id: int
    kind: Literal["in", "out"]
    at: datetime
    time: str
    mark: Optional[Mark] = None


class AbsenceOut(BaseModel):
    id: int
    art: str
    day: date
    until: date
    minutes: Optional[int]
    #: Was sie an DIESEM Tag zählt.
    minutes_on_day: int
    note: Optional[str] = None
    proof_url: Optional[str] = None
    #: Ein Nachweis ist nötig (ab Tag …), ``proof_url`` sagt, ob er da ist.
    proof_needed: bool = False
    #: Welche ältere Absenz sie an diesem Tag ersetzt – Satz für den Hover.
    replaces: Optional[str] = None
    can_void: bool = False


class DayOut(BaseModel):
    day: date
    workday: bool
    holiday: Optional[str] = None
    soll: int
    ist: int
    credit: int
    today: bool = False
    future: bool = False
    #: Abgeschlossen – ändern kann nur der Admin (blass im Kalender).
    locked: bool = False
    open: bool = False
    hints: list[str] = []
    stamps: list[StampOut] = []
    absence: Optional[AbsenceOut] = None


class ContractOut(BaseModel):
    id: int
    valid_from: date
    weekly_minutes: int
    workdays: list[int]
    vacation_weeks: Decimal
    company_object_id: Optional[int]
    company_name: Optional[str]
    state: Literal["current", "planned", "replaced"]
    #: Austritt: Stundenkonto und Ferien am letzten Tag.
    closing_day: Optional[date] = None
    closing_account: Optional[int] = None
    closing_vacation: Optional[int] = None


class BookingOut(BaseModel):
    id: int
    day: date
    note: str
    minutes: int
    vacation_minutes: int
    by: Optional[str]


class TaskOut(BaseModel):
    kind: str
    day: date
    label: str
    age: int


class ArtOut(BaseModel):
    key: str
    label: str
    icon: str
    effect: str
    effect_label: str
    effect_tip: str
    proof: Optional[str] = None
    proof_from: Optional[int] = None


class HintOut(BaseModel):
    key: str
    label: str
    tone: str
    icon: str


class TimeVocab(BaseModel):
    """Die Wörter der Zeiterfassung – EINE Quelle (``domain/timekeeping``)."""
    arts: list[ArtOut]
    hints: list[HintOut]
    texts: dict[str, str]
    correction_days: int
    week_max: int


class TimeView(BaseModel):
    person_object_id: int
    #: Gibt es überhaupt einen Vertrag? Ohne ihn zeigt die Karte nur das Werkzeug «Vertrag».
    has_contract: bool
    now: datetime
    today: date
    #: Heute: läuft ein Kommen (seit «07:42»), wann zuletzt gegangen – Uhrzeit in Zürich.
    present_since: Optional[str] = None
    last_out: Optional[str] = None
    today_ist: int
    today_soll: int
    account: int
    vacation: int
    #: Ferien in Tagen (Tagessoll des aktuellen Vertrags), eine Nachkommastelle.
    vacation_days: Optional[float] = None
    day_soll: int
    born: bool
    can_stamp: bool
    is_admin: bool
    contracts: list[ContractOut]
    bookings: list[BookingOut]
    month: str
    days: list[DayOut]
    default_day: date
    tasks: list[TaskOut]
    vocab: TimeVocab


class EntryPreview(BaseModel):
    """►►► **Was dieser Eintrag bewirken würde** – vor dem Speichern, nach derselben Regel. ◄◄◄
    ``problem`` ist der Satz, warum es nicht geht (dann ist «Erfassen» gesperrt)."""
    problem: Optional[str] = None
    workdays: int = 0
    minutes: int = 0
    #: «Ferien an 2 Tagen» – was die neue Absenz an ihren Tagen ersetzt.
    replaces: Optional[str] = None
    #: Ferienguthaben heute, wenn dieser Eintrag gilt (Minuten).
    vacation_after: Optional[int] = None
    proof: Optional[str] = None
    proof_from: Optional[int] = None


class HolidayOut(BaseModel):
    id: Optional[int] = None
    day: date
    name: str
    #: Vorschlag: steht schon in der Liste.
    taken: bool = False


class CompanyTimeView(BaseModel):
    company_object_id: int
    canton: Optional[str]
    cantons: list[tuple[str, str]]
    year: int
    holidays: list[HolidayOut]
    proof: dict[str, Optional[int]]
    rules: list[tuple[str, str]]
    #: Fehlen die Feiertage eines Jahres? – die Aufgabe am Symbol.
    tasks: list[TaskOut]
    can_edit: bool
    vocab: TimeVocab


class TodoItem(BaseModel):
    section: str
    label: str
    count: int
    red: bool = False


class TodoOut(BaseModel):
    """►►► **Was an diesem Datensatz zu tun ist** – die Zahl am Symbol. ◄◄◄ Offene
    Nachrichten, Aufgaben der Zeiterfassung, fehlende Pflichtangaben; rot, sobald etwas
    dringend ist."""
    object_id: int
    count: int
    red: bool
    items: list[TodoItem]
