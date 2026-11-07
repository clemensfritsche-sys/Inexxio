"""►►► **Die eine Uhr: «jetzt» und «heute» in Europe/Zurich.** ◄◄◄

Gespeichert wird in UTC; was ein Mensch als Tag oder Uhrzeit liest (ein Papier, ein
Zeitstempel, ein Stichtag), gilt in der Zone der Gesellschaft. Der Server läuft in UTC –
``date.today()`` wäre zwischen Mitternacht und 01:00/02:00 der Vortag.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Zurich")


def now() -> datetime:
    """Jetzt, in Europe/Zurich (mit Zone)."""
    return datetime.now(ZONE)


def today() -> date:
    """Der heutige Tag in Europe/Zurich."""
    return now().date()
