"""Newsletter – Zustand und Nachweis einer Person (``services/newsletter``)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ConsentRow(BaseModel):
    """Eine An- oder Abmeldung – der Nachweis."""

    subscribed: bool
    #: Woher, als Wort («Konto», «Abmeldelink» …).
    source: str
    at: datetime
    #: Der Satz, dem zugestimmt wurde (nur bei einer Anmeldung).
    wording: Optional[str] = None


class NewsletterState(BaseModel):
    """Angemeldet oder nicht – die jüngste Zeile; dazu der Satz, dem man zustimmt."""

    subscribed: bool
    #: Seit wann (die jüngste Zeile) – leer = nie angemeldet.
    since: Optional[datetime] = None
    source: Optional[str] = None
    #: Der Wortlaut der Einwilligung – neben dem Schalter im Konto.
    wording: str
    #: Nur im ERP: der Nachweis, jüngste Zeile zuerst.
    history: list[ConsentRow] = []


class NewsletterIn(BaseModel):
    subscribed: bool
