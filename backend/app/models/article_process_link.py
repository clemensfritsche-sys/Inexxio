from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticleProcessLink(Base, TimestampMixin):
    """Prozessstückliste: Zuordnung eines **Prozesses** zu einem **Artikel** (n:m).

    Ein Artikel führt eine geordnete Liste von Prozessen (Entstehung, Verkauf,
    Wartung …); derselbe Prozess kann bei mehreren Artikeln hinterlegt sein.
    Diese Link-Tabelle ist die *einzige* Quelle der Zugehörigkeit – ``position``
    ordnet die Stückliste pro Artikel.

    Wichtige Konsequenz (Frage des Nutzers): **inaktiv/ersetzen** wirkt am
    Prozess-OBJEKT und betrifft damit alle Artikel, die ihn führen; **Hinzufügen/
    Entfernen** in der Stückliste (= Link an/aus) betrifft nur den einen Artikel.
    Standardprozesse (``Process.is_standard``) sind geerbt und brauchen KEINEN Link.
    """

    __tablename__ = "article_process_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    process_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
