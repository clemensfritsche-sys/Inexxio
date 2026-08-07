from typing import Any, Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticleProcessStep(Base, TimestampMixin):
    """Der **Erzeugungsprozess** eines Artikels — eine Vorlage, sonst nichts.

    Sie sieht aus wie ``ProcessStep`` und ist trotzdem eine andere Sache: diese Zeilen
    **laufen nie**. Sie tragen keinen Zustand, kein Stück steht je vor ihnen, und es
    gibt keinen Endpunkt, der sie ausführt. Ausgeführt wird ausschliesslich im Auftrag
    (PROCESS_CORE.md §8.2).

    Genau darum sind es **zwei Tabellen und nicht eine mit einem Schalter**. Eine
    gemeinsame Tabelle müsste an jeder Abfrage «und nur die, die zu einem Auftrag
    gehören» mitschleppen; wer es einmal vergisst, führt eine Vorlage aus. Was es nicht
    gibt, kann nicht aufgerufen werden.

    Auch hier gilt: **die ``id`` ist die Identität**, der Typ sagt den Namen. Ein
    Namensfeld gab es, es war immer «Datenerfassung», und es war trotzdem Pflicht – ein
    Feld, dessen einzige richtige Antwort feststeht, ist keine Frage (#682).

    **Kopie, nicht Verweis.** Bei der Freigabe wird diese Liste in ``process_steps``
    **kopiert** und mit ``Article.process_version`` gestempelt. Ein Verweis hiesse, dass
    eine spätere Artikeländerung rückwirkend laufende Aufträge umschreibt — das
    widerspricht «eingefroren» (§6.4) und wäre dieselbe Fehlerklasse, die das
    Vorgängersystem geprägt hat.
    """

    __tablename__ = "article_process_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    module_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status_before: Mapped[str] = mapped_column(String(30), nullable=False)
    status_after: Mapped[str] = mapped_column(String(30), nullable=False)
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
