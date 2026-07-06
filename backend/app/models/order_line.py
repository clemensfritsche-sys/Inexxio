from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class OrderLine(Base, TimestampMixin):
    """Eine Position eines **Mehrpositionen-Auftrags** («Verkaufen an Kunden» / Sammel-
    Bestandsoperation): Artikel + Menge, gebündelt unter einem Auftrag OHNE eigenen
    ``article_id``/``quantity`` (``orders.article_id IS NULL`` signalisiert «mehrzeilig»).

    Existiert NUR für Zeilen, die auf **vorhandenen Bestand** wirken (FIFO oder fixierte
    Instanzen) – eine «Herstellen/Beschaffen»-Zeile wird stattdessen ein **eigener**
    Auftrag (siehe ``routers/orders.py: create_order``), analog zum Shop («make-Positionen
    bleiben je ein eigener Auftrag»). Fixierte Instanzen laufen wie gehabt über
    ``instances.subject_of_order_id`` (kein eigenes Feld nötig)."""

    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Positionsmenge als Dezimalzahl (NUMERIC(14,3)) – ganze Stück ODER Bruchmenge.
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
