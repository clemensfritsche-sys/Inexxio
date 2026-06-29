from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticlePrice(Base, TimestampMixin):
    """Ein Verkaufspreis eines Artikels (1:n, mutabel, Soft-Delete, geloggt).

    Mehrere Preise je Artikel sind möglich (z. B. Einmalkauf + Abo). Der Shop
    nutzt den als ``is_primary`` markierten Preis. Alle Beträge sind die
    **Netto-Basis in CHF**; Währung/Steuer/Rundung berechnet die Preis-Pipeline
    (``services/pricing.py``) zur Anzeigezeit und friert sie beim Kauf ein.
    """

    __tablename__ = "article_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    # one_time → Einmalkauf | subscription → Abonnement (mit ``interval``).
    kind: Mapped[str] = mapped_column(String(12), default="one_time", nullable=False)
    interval: Mapped[Optional[str]] = mapped_column(String(8))  # month | year (nur bei subscription)

    # Netto-Basisbetrag in CHF + optionaler durchgestrichener Vergleichspreis (rein visuell).
    amount_chf: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_chf: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))

    # Steuerklasse: standard (8.1%) | reduced (2.6%) | lodging (3.8%) | zero (0%).
    tax_class: Mapped[str] = mapped_column(String(16), default="standard", nullable=False)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Gepinnte Fremdwährungspreise (State of the Art statt Live-Umrechnung):
    # {"EUR": {"net": "990.00", "rate": "1.05", "base": "1000.00"}, "USD": {…}}.
    # Bleibt stabil bis Basis-Änderung oder Kurs-Drift > 3 % (services/pricing.py).
    pinned: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
