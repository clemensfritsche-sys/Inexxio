"""►►► **Die eine Uhr: «jetzt» und «heute» in Europe/Zurich.** ◄◄◄

Gespeichert wird in UTC; was ein Mensch als Tag oder Uhrzeit liest (ein Papier, ein
Zeitstempel, ein Stichtag), gilt in der Zone der Gesellschaft. Der Server läuft in UTC –
``date.today()`` wäre zwischen Mitternacht und 01:00/02:00 der Vortag.
"""

from datetime import date, datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Zurich")


def now() -> datetime:
    """Jetzt, in Europe/Zurich (mit Zone)."""
    return datetime.now(ZONE)


def today() -> date:
    """Der heutige Tag in Europe/Zurich."""
    return now().date()


def utcnow() -> datetime:
    """Jetzt in UTC – so wird gespeichert."""
    return datetime.now(timezone.utc)


def day(value: Optional[Union[date, datetime]]) -> str:
    """►► Ein Tag, wie ein Mensch ihn liest – «24.10.2026» (ein Zeitpunkt in Europe/Zurich);
    nichts → leer. ◄◄"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.astimezone(ZONE) if value.tzinfo else value
    return value.strftime("%d.%m.%Y")


def stamp(value: datetime) -> str:
    """Tag und Uhrzeit in Europe/Zurich – «24.10.2026 14:05»."""
    return value.astimezone(ZONE).strftime("%d.%m.%Y %H:%M")
