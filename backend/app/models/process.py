from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Process(Base, TimestampMixin):
    """Ein benannter Prozess – eine geordnete Liste von Prozessschritten.

    Zwei Heimaten, EIN Konzept (keine «Vorlagen»):
    - **Artikel-Prozess** (``article_id`` gesetzt, ``is_standard=False``): ein
      Verhalten des Artikels («Entstehung», «Verkauf», «Wartung» …). KIND des
      Artikels – KEINE eigene Objektnummer (wie die Schritte selbst).
    - **Standardprozess** (``is_standard=True``, ``article_id=NULL``): global,
      gilt automatisch für JEDEN Artikel (geerbt – z. B. «Entnahme», «Umlagern»,
      «Verschrotten», «Sonderkontrolle»). Eigenständiges Objekt mit Objektnummer
      (Feed-Typ «Standardprozesse»), Lebenszyklus draft → released → inactive.

    Die **Quelle** (``source``) – konzeptuell der «Start-Knoten» des Prozesses –
    legt fest, worauf der Prozess wirkt und was bei der Auftrags-Anlage gefragt
    wird. Der **Name** ist frei wählbar und bestimmt das Verhalten NICHT:

        produce   → der Prozess lässt **neue** Instanzen entstehen (Produktion);
                    fragt «Menge?»
        stock     → der Prozess greift **FIFO** auf vorhandenen Bestand zu
                    (Verkauf, Entnahme); fragt «Menge?»
        instance  → der Prozess wirkt auf eine **konkrete Instanz** (Wartung,
                    Kontrolle); fragt «welche Instanz?»
    """

    __tablename__ = "processes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Nur Standardprozesse sind eigenständige Objekte (Objektnummer); Artikel-
    # Prozesse sind Kinder des Artikels und bleiben ohne Nummer.
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)

    # NULL = globaler Standardprozess; gesetzt = Prozess dieses Artikels.
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="produce", nullable=False)
    is_standard: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    # Lebenszyklus (v. a. für Standardprozesse): draft | released | inactive.
    status: Mapped[str] = mapped_column(String(20), default="released", nullable=False)
