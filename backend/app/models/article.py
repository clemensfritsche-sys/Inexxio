from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..domain import statuses as st
from .base import TimestampMixin


class Article(Base, TimestampMixin):
    """Stammdaten-Datensatz für einen Artikel (Phase 2 – Produktion).

    **«Ausser Betrieb» ist keine eigene Angabe.** Ein Artikel wird nicht versioniert, er
    wird **ersetzt**; der Zustand ist die Projektion von ``replaced_by_id`` (``status``).
    **``is_active``** ist eine andere Achse: der Soft-Delete, im Prozessbereich nie gesetzt.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True
    )

    # **Kein ``status``-Mapping**: der Zustand folgt aus ``replaced_by_id`` (``status``).
    # Die Spalte steht noch in der Datenbank bis zu ihrem Drop.


    # Stammdaten. Pflicht ist nur der **Name**; Einheit/Serialisierung haben einen Default,
    # Grösse und Gewicht sind optional.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), default="Stk", server_default="Stk", nullable=False)  # Stk | m | kg | l
    serialization: Mapped[str] = mapped_column(String(20), default="unit", server_default="unit", nullable=False)  # unit | batch
    size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # z. B. 3x40x600 (optional)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # optional

    # Optionale Stammdaten – nur bei Bedarf gepflegt (dynamische Feldliste im UI).
    material: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cad_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # CAD-Link
    surface: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Oberfläche
    min_order_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # MOQ
    safety_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # Sicherheitsbestand
    # ►►► **Zoll: was die Ware IST, und woher sie kommt.** ◄◄◄ Eigenschaften der Sache;
    # sie reisen über die Spezifikation auf jeden Beleg. HS-Code: 6 bis 8 Stellen (die
    # ersten sechs sind weltweit gleich, das Importland ergänzt).
    hs_code: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    # **Ursprungsland ist NICHT aus dem HS-Code ableitbar** und auch nicht das
    # Versandland – es ist eine eigene Angabe (ISO-2, wie jedes Land im Haus).
    origin_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    # Gefahrgut: ein Spezifikationsfeld wie jedes andere – am Artikel, nicht auf dem Beleg.
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # ►►► **Ware oder Dienstleistung** (Zahlungsmodul): bei Ware folgt der Steuersatz der
    # Lieferadresse (Ausland → Export), bei einer Dienstleistung dem Sitz des Empfängers
    # (Ausland → Reverse Charge); eine Dienstleistung kennt keine Lieferbedingung.
    is_service: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Was erfasst wird, sagt das **Modul** im Prozess (``process_steps.config``), nicht
    # der Artikel.

    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Artikels (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("objects.object_id", ondelete="SET NULL",
                               name="fk_articles_replaced_by"),
        nullable=True, index=True)

    @property
    def status(self) -> str:
        """►►► **Der fachliche Zustand — ABGELEITET, nicht gespeichert.** ◄◄◄

        ``Freigegeben``, solange dieser Artikel die neueste Fassung ist; ``Inaktiv``, sobald
        ein Nachfolger ihn abgelöst hat. ``articles.may_create`` liest die Tatsache
        (``replaced_by_id``), nicht dieses Wort.
        """
        return st.INAKTIV if self.replaced_by_id else st.FREIGEGEBEN
