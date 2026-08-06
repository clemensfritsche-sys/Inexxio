from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class OrderUnit(Base, TimestampMixin):
    """Welche Einzelinstanz gehört zu welchem Auftrag – **und die Exklusivität**.

    Das ist die Definition aus PROCESS_CORE.md §2.1, materialisiert: bei der Freigabe
    entsteht je Stück eine Zeile, und danach kommt keine dazu und keine geht weg. Kein
    Nachschieben, kein Ersetzen zur Laufzeit.

    **Die Exklusivitätsregel steht als partieller Unique-Index in der Datenbank**
    (§3): ``released_at IS NULL`` heisst «aktiv», und ein Stück kann höchstens eine
    solche Zeile haben. Sie in der Anwendungslogik zu prüfen genügt nicht – zwei
    gleichzeitige Freigaben lesen beide «ist frei» und schreiben beide. Der Index ist
    die einzige Stelle, an der das nicht passieren kann.

    Der Unterschied, den §3 macht, steckt in genau dieser einen Spalte:

    ===================  ===============================================
    ``released_at`` NULL **aktiv** – exklusiv, das Stück ist im Prozess
    ``released_at`` Wert **referenziert** – Historie, beliebig oft
    ===================  ===============================================

    Frei wird ein Stück, sobald es das **Ende-Objekt** passiert hat – nicht erst, wenn
    der ganze Auftrag fertig ist. Der Auftrag ist fertig, wenn alle seine Stücke durch
    sind; das ist eine Folge, keine eigene Regel.

    ``current_step_id`` ist die Laufzeit-Projektion «wo steht dieses Stück» und gehört
    hierher, nicht an die Einzelinstanz: es ist eine Aussage über die Zugehörigkeit,
    nicht über das Stück selbst. ``NULL`` heisst «am Ende angekommen».
    """

    __tablename__ = "order_units"
    __table_args__ = (
        # Die eine Regel, an der einzigen Stelle, an der sie nicht umgangen werden kann.
        Index(
            "uq_order_units_active",
            "instance_unit_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    instance_unit_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    current_step_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
