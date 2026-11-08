from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..domain.statuses import INITIAL_UNIT_STATUS
from .base import TimestampMixin


class InstanceUnit(Base, TimestampMixin):
    """Einzelinstanz – das **einzige Arbeitsobjekt** des Systems.

    Jede Ansicht höherer Ebene (Instanz, Artikel, Bestand) ist Filterung oder Summierung.
    **Keine Mengen-Spalte**: eine Einzelinstanz ist genau ein Stück.

    **Nummer = ``<Objektnummer der Instanz>-<suffix>``**, nicht aus ``object_id_seq``; der
    Suffix zählt ab 1 und entsteht nur in ``services/instances.create_instances``.
    **Vergeben bleibt vergeben**: nie gelöscht, nie deaktiviert.

    ``status`` ist der eigene Zustand dieses Stücks (``domain/statuses``), geändert nur in
    ``services/process._pass`` – mit dem Eintrag im Ereignis-Log.
    """

    __tablename__ = "instance_units"
    __table_args__ = (
        UniqueConstraint("instance_id", "suffix", name="uq_instance_units_instance_suffix"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("instances.id", ondelete="RESTRICT"), index=True, nullable=False)

    # Laufende Nummer innerhalb der Instanz, beginnend bei 1.
    suffix: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default=INITIAL_UNIT_STATUS, nullable=False,
    )

    #: **Wo dieses Stück liegt** – die Objektnummer seines Halters (``services/places``).
    #:
    #: Halter: eine **Instanz**, ein **Benutzer** oder ein **Unternehmen**; kein Typfeld
    #: (``objects.resolve_object_type``). ``NULL`` ist regulär: das Stück liegt nirgends.
    place_object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("objects.object_id", ondelete="RESTRICT"), nullable=True, index=True,
    )

    #: **Der Träger** – das *Stück*, in dem dieses Stück steckt (``services/places``).
    #:
    #: Nötig, weil eine Einzelinstanz keine Objektnummer trägt (Verbauen,
    #: ``consumption.plan``). Ein ``CHECK`` erlaubt höchstens einen der beiden Halter.
    #: **Nicht die Genealogie** (``payload.into`` im Log): diese Spalte sagt, *wo es jetzt
    #: liegt*, und wird beim Ausbau geräumt (PROCESS_CORE §9.6).
    place_unit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("instance_units.id", ondelete="RESTRICT"), nullable=True, index=True,
    )
