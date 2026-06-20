from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class StorageLocation(Base, TimestampMixin):
    """Lagerplatz — ERP-Datensatztyp mit GPS-Standort.

    Statuswerte (`status`): draft → Entwurf | released → Freigegeben | inactive → Inaktiv
    Adressfelder werden im Frontend per Reverse-Geocoding aus den Koordinaten gefüllt.
    """

    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)

    # Identifikation (Lagerplätze werden über die Objektnummer angesprochen –
    # der Name ist nur ein interner Default; ``note`` ist eine freie Bemerkung)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(100))
    location_type: Mapped[Optional[str]] = mapped_column(String(30))
    note: Mapped[Optional[str]] = mapped_column(String(500))

    # Kapazität & Eigenschaften
    max_load_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    width_mm: Mapped[Optional[int]] = mapped_column(Integer)
    depth_mm: Mapped[Optional[int]] = mapped_column(Integer)
    height_mm: Mapped[Optional[int]] = mapped_column(Integer)
    is_dry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_tempered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Standort (GPS + per Reverse-Geocoding gefüllte Adresse)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    address_street: Mapped[Optional[str]] = mapped_column(String(255))
    address_zip: Mapped[Optional[str]] = mapped_column(String(20))
    address_city: Mapped[Optional[str]] = mapped_column(String(100))
    address_country: Mapped[Optional[str]] = mapped_column(String(100))

    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Lagerplatzes (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
