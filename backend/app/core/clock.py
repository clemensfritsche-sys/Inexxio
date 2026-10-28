"""**Die Uhr des Hauses** – ein Tag beginnt und endet in Europe/Zurich, nicht in UTC."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Zurich")


def now() -> datetime:
    """Jetzt, in der Zeitzone des Hauses."""
    return datetime.now(ZONE)


def today() -> date:
    """Der heutige Tag in der Zeitzone des Hauses."""
    return now().date()
