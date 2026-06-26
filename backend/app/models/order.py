from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Order(Base, TimestampMixin):
    """Auftrag — interner Bedarf, der einen Artikel-Prozess auslöst.

    Beispiel: «5× Artikel 1003». Wird der Auftrag freigegeben (status=released)
    und besitzt der Artikel einen ``purchase``-Prozessschritt, instanziiert das
    System die zugehörige Bestellung (Purchase Order).

    Statuswerte (`status`): draft → Entwurf | released → Freigegeben | inactive → Inaktiv
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))

    # Auftrags-Modus: ``make`` (Artikel+Menge → fährt den Artikel-Prozess, ERZEUGT
    # Instanzen) | ``custom`` (eigener Prozess auf ausgewählte, vorhandene Instanzen).
    mode: Mapped[str] = mapped_column(String(10), default="make", server_default="make", nullable=False)

    # Bedarf: welcher Artikel in welcher Menge.
    #
    # ZWEI Auftrags-Modi (kein Prozess-Objekt mehr):
    #   MAKE   – ``article_id`` + ``quantity`` gesetzt, KEINE eigenen Schritte:
    #            der Auftrag fährt den **Prozess des Artikels** und ERZEUGT Instanzen.
    #   CUSTOM – der Auftrag trägt **eigene** Prozessschritte (``article_process_steps``
    #            mit ``order_id`` = dieser Auftrag) und wirkt auf **bereits vorhandene**,
    #            ausgewählte Instanzen (markiert über ``instances.subject_of_order_id``).
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    desired_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Prozess-Eckdaten für die Durchlaufzeit (Freigabe → Abschluss).
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Wiederkehrend (Compliance/Termine + Abos) – direkt am Auftrag, KEIN eigenes
    # Objekt: ist ``recurrence_active``, erzeugt der Auftrag beim **Abschluss**
    # automatisch den nächsten (Entwurf, Termin = ``recurrence_anchor`` + Periode).
    recurrence_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    recurrence_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recurrence_lead_time_days: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False)
    recurrence_anchor: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # nächster Soll-/Ablauftermin
    recurring_parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Auftrag, aus dem dieser entstand

    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Auftrags (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
