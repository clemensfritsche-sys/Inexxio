"""**Das Gedächtnis der KI – Bedeutungs-Zahlen je Fall** (Projektakte §4.3 «Lernen», Schritt 3.6).

Ein Fall ist ein Vorschlag im Log (``proposal``); hier stehen nur seine **Bedeutungs-Zahlen**
(``embedding``, 768 Zahlen von Vertex AI) und der Text, aus dem sie entstanden – eine
**Ableitung** aus dem Log, kein Wissen: geht die Tabelle verloren, entsteht sie im Takt neu.
Gesucht wird mit pgvector in der eigenen Datenbank (``memory.similar``).
"""

from typing import Any, Optional

from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from ..core.database import Base
from .base import TimestampMixin


class Vector(UserDefinedType):
    """Der Spaltentyp ``vector(n)`` von pgvector – geschrieben und gelesen als Text
    ``[0.1,0.2,…]``; gerechnet wird in der Datenbank."""

    cache_ok = True

    def __init__(self, dims: int):
        self.dims = dims

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dims})"

    def bind_processor(self, dialect: Any):
        def process(value: Optional[list[float]]) -> Optional[str]:
            return None if value is None else "[" + ",".join(f"{float(v):.7g}" for v in value) + "]"
        return process

    def result_processor(self, dialect: Any, coltype: Any):
        def process(value: Any) -> Optional[list[float]]:
            if value is None or isinstance(value, list):
                return value
            return [float(v) for v in str(value).strip("[]").split(",") if v]
        return process


class AiMemory(Base, TimestampMixin):
    __tablename__ = "ai_memory"

    #: Der Vorschlag im Log (``log.id`` eines ``proposal``) – je Fall genau eine Zeile.
    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    #: Was eingebettet wurde (Quelle + Vorschlag) – lesbar, damit man sieht, was die KI sah.
    text: Mapped[str] = mapped_column(Text, nullable=False)
