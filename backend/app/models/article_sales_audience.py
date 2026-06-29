from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticleSalesAudience(Base, TimestampMixin):
    """Zielgruppe eines **privaten/unlisted** Verkaufs-Artikels: welche Kunden ihn
    sehen/kaufen dürfen. Für ``sales_visibility='public'`` irrelevant (jeder sieht ihn)."""

    __tablename__ = "article_sales_audience"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
