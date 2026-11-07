"""►►► **Die Einwilligung zum Newsletter – ein Nachweis, kein Häkchen.** ◄◄◄

Append-only wie der Prozess-Log: jede Anmeldung und jede Abmeldung ist eine Zeile, mit
Zeitpunkt, Quelle und dem **Wortlaut**, dem die Person zugestimmt hat. Ob jemand heute
angemeldet ist, ist eine **Ableitung** – die jüngste Zeile (``services/newsletter``).
Keine Zeile = nie angemeldet. Geändert wird nie etwas; eine Abmeldung ist eine neue Zeile.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin, utcnow


class NewsletterConsent(Base, TimestampMixin):
    __tablename__ = "newsletter_consents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: Wer (Objektnummer der Person).
    person_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    #: Angemeldet (``True``) oder abgemeldet (``False``).
    subscribed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: Woher (``domain/newsletter.SOURCES``).
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Der Satz, dem zugestimmt wurde – bei einer Abmeldung leer.
    wording: Mapped[Optional[str]] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                         default=utcnow)
    #: Wer es erfasst hat (``user_profiles.id``) – leer, wenn die Person selbst klickte.
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)
