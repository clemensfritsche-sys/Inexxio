from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin

#: Woher die Einzelinstanzen dieser Zeile kommen.
#:
#: ``neu``   – sie werden bei der Freigabe **erzeugt** (Erzeugungsauftrag). Das ist die
#:             EINZIGE Stelle im System, an der neue Einzelinstanznummern entstehen.
#: ``lager`` – es sind **bestehende** Einzelinstanzen. Hier entsteht nie eine Nummer.
NEU = "neu"
LAGER = "lager"
ORIGINS = (NEU, LAGER)


class OrderLine(Base, TimestampMixin):
    """Eine **Definitionszeile** des Auftrags: Artikel · Menge · Herkunft.

    Sie ist das, was der Mensch oberhalb des Start-Symbols eingetragen hat, und sie wird
    mit der Freigabe festgeschrieben — nicht weil eine Ansicht sie bräuchte (die Stücke
    hängen an ``order_units``), sondern weil die **Herkunft** sonst verloren ginge: dass
    diese drei Stücke erzeugt und jene zwei aus dem Lager geholt wurden, lässt sich
    hinterher aus dem Bestand nicht mehr ablesen.

    ``quantity`` referenziert **immer exakt Einzelinstanzen** — nie Instanzen, nie eine
    Artikelmenge. Menge 3 heisst: danach laufen genau 3 Einzelinstanzen im Prozess.
    Geprüft wird das an einer Stelle (``services/materialize.assert_quantity``), und der
    Verstoss bricht die Freigabe-Transaktion ab.
    """

    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
