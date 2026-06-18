from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Article(Base, TimestampMixin):
    """Stammdaten-Datensatz für einen Artikel (Phase 2 – Produktion).

    Statuswerte (`status`):
        draft     → Entwurf (neu angelegt, noch nicht freigegeben)
        released  → Freigegeben (für Prozesse/Bestellungen nutzbar)
        inactive  → inaktiv (auslaufend/gesperrt)

    `is_active` bleibt der Soft-Delete-Flag (Datensatz ausgeblendet),
    unabhängig vom fachlichen `status`.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)

    # Stammdaten (Pflichtfelder)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)  # Stk | m | kg | l
    serialization: Mapped[str] = mapped_column(String(20), nullable=False)  # unit | batch
    size: Mapped[str] = mapped_column(String(100), nullable=False)  # z. B. 3x40x600
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Optionale Stammdaten – nur bei Bedarf gepflegt (dynamische Feldliste im UI).
    material: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cad_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # CAD-Link
    surface: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Oberfläche
    min_order_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # MOQ
    safety_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # Sicherheitsbestand

    # Einstandspreis netto/Stück – read-only, aus der zuletzt freigegebenen
    # Bestellung (Purchase Order) automatisch zurückgeschrieben.
    landed_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
