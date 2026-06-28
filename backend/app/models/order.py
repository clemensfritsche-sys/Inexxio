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

    # Bedarf: welcher Artikel in welcher Menge. Die **Subjektart wird abgeleitet**
    # (kein Modus-Flag, siehe ``services/subject.py``):
    #   produce – ``article_id`` + ``quantity``, KEINE eigenen Schritte → fährt den
    #             **Prozess des Artikels** und ERZEUGT Instanzen.
    #   stock   – eigene Schritte (``article_process_steps`` mit ``order_id``) ohne
    #             vorgewählte Instanzen → Subjekt FIFO ab Lager (Verkauf/Entnahme).
    #   chosen  – wirkt auf vorgewählte, vorhandene Instanzen (``instances.subject_of_order_id``).
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

    # **Abweichung** (vereinheitlicht Reklamation/Fehler/Nacharbeit/Abbruch-Folgeauftrag):
    # Ein Auftrag mit ``parent_order_id`` ist ein **Unter-Auftrag**, der aus einem laufenden
    # Eltern-Auftrag heraus entsteht und auf dessen Instanzen wirkt. Der Eltern-Auftrag
    # **pausiert** (schliesst nicht ab), solange eine Abweichung offen ist. Objektnummer des
    # Eltern-Auftrags (eine Abweichung ist selbst ein vollwertiger Auftrag mit eigener Nummer).
    parent_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # Abbruch erzwingt einen **Folgeauftrag**: ``abort_into_id`` zeigt auf die Objektnummer
    # des Folgeauftrags. Solange gesetzt, ist der Auftrag «Abbruch ausstehend»; **inaktiv**
    # wird er erst, wenn der Folgeauftrag **freigegeben** ist (die Instanzen gehen über).
    abort_into_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
