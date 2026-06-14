from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Order(Base, TimestampMixin):
    """Auftrag — neuer ERP-Datensatztyp.

    Inhaltliche Felder folgen noch; vorerst Status + optionaler Titel, plus
    gemeinsame Objektnummer und Soft-Delete (is_active via TimestampMixin).

    Statuswerte (`status`): draft → Entwurf | released → Freigegeben | inactive → Inaktiv
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
