from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Process(Base, TimestampMixin):
    """Ein benannter Prozess – eine geordnete Liste von Prozessschritten.

    **Jeder Prozess ist ein eigenständiges Objekt** mit Objektnummer (Feed-Typ
    «Prozesse»), Name und eigenem Lebenszyklus (draft → released → inactive,
    Ersetzen via ``replaced_by_id``). Artikel referenzieren Prozesse über eine
    **Prozessstückliste** (``article_process_links``) – ein Prozess kann bei
    mehreren Artikeln hinterlegt sein.

    - **Standard** (``is_standard=True``): gilt automatisch für JEDEN Artikel
      (geerbt – z. B. «Entnahme», «Umlagern», «Verschrotten», «Sonderkontrolle»),
      ohne expliziten Link. Das Flag ist **nur bei der Anlage** setzbar und nach
      der Freigabe gesperrt.
    - ``article_id`` ist nur noch die **Herkunft** (unter welchem Artikel der
      Prozess angelegt wurde) – die Zugehörigkeit/Stückliste steckt in den Links.

    Die **Quelle** (``source``) – konzeptuell der «Start-Knoten» des Prozesses –
    legt das **Subjekt** fest (worauf der Prozess wirkt) und was bei der
    Auftrags-Anlage gefragt wird. Sie ist KEINE Richtungswahl mehr – die
    Lager-Richtung (erhöhend/mindernd/neutral) wird aus den Schritten abgeleitet
    (siehe ``services/processes.py: stock_effect``). Der **Name** ist frei:

        produce   → **neues** Subjekt entsteht (Produktion);     fragt «Menge?»
        stock     → **bestehender** Bestand, FIFO (Verkauf …);   fragt «Menge?»
        instance  → eine **konkrete bestehende** Instanz (Wartung); «welche Instanz?»
    """

    __tablename__ = "processes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Jeder Prozess ist ein Objekt mit eigener Objektnummer.
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)

    # Herkunft: unter welchem Artikel angelegt (NULL = direkt im Prozess-Feed /
    # Standard). Die tatsächliche Zugehörigkeit liegt in ``article_process_links``.
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="produce", nullable=False)
    is_standard: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    # Lebenszyklus: draft | released | inactive.
    status: Mapped[str] = mapped_column(String(20), default="released", nullable=False)
    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Prozesses (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
