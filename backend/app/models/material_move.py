from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import utcnow


class MaterialMove(Base):
    """**Eine Journalzeile des Material-Journals** (ADR 007) – append-only.

    Menge X der Instanz I wechselte von Topf A nach Topf B. Ein Topf ist
    ``(Halter · Qualität · Verbleib)``: Halter = ein Auftrag oder niemand (frei). Entstehen
    hat keinen Quell-Topf (``src_*`` NULL); Verschrotten/Verkaufen/Verbauen führen in
    terminale Töpfe, aus denen nichts mehr herauskommt.

    Daraus folgen die drei Fragen des Nutzers ohne weitere Regeln:

        Passiert     = diese Zeilen, chronologisch. Es gibt KEINEN Update-/Delete-Pfad –
                       die Vergangenheit kann sich nicht ändern, weil kein Schreibweg
                       existiert.
        Jetzt        = der Kontostand (Summe der Zeilen je Topf, ``ledger.lots``).
        Als Nächstes = der Plan (Schritte) – der steht woanders, denn er darf sich ändern.

    Geschrieben wird **ausschliesslich** über ``services/ledger.py`` – die fachlichen
    Dienste rufen es an ihren semantischen Punkten (entstehen, übernehmen, freigeben,
    zurückgeben, verkaufen, verbauen, aussondern, sperren/entsperren).

    Kein Geschäftsobjekt: keine Objektnummer, kein Feed, kein Audit-Log – wie ``events``.
    ``kind='opening'`` ist die Eröffnungsbilanz einer Alt-Instanz (ihr Stand vor der ersten
    Buchung); Geschichte davor steht in ``events``/``instance_order_links``.
    """

    __tablename__ = "material_moves"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    instance_object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Warum – das semantische Ereignis (created | opening | taken | returned | released |
    # sold | consumed | scrapped | blocked | unblocked).
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    # Von wo … (NULL überall = Entstehung/Eröffnung)
    src_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    src_quality: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    src_disposition: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    # … nach wo.
    dst_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    dst_quality: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    dst_disposition: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)

    # **Welche Stücke bewegt wurden** – die laufenden Nummern (``[1, 2]`` = ``…-1``/``…-2``).
    # Sie gehören zur Buchung, nicht zur Instanz: was passiert ist, darf sich nicht mehr
    # ändern (ADR 007). Vorher wurden sie aus dem HEUTIGEN Halter abgeleitet – schloss ein
    # Abzweig ab und gab seine Stücke zurück, hielt er nichts mehr, und die Vergangenheit
    # zeigte plötzlich alle Nummern statt der richtigen (Testnotizen #543/#544).
    # ``NULL`` = Altbestand vor dieser Spalte (dort bleibt es bei der Ableitung).
    units: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # '!unbalanced' = der Aufrufer wollte mehr bewegen, als die Instanz hielt – sichtbar
    # markiert statt still verschluckt; ``ledger.verify`` findet es.
    note: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
