from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..domain import statuses as st
from .base import TimestampMixin


class Article(Base, TimestampMixin):
    """Stammdaten-Datensatz für einen Artikel (Phase 2 – Produktion).

    Statuswerte (``status``) — **aus der EINEN Liste** (``domain/statuses``):
        ``freigegeben``  → angelegt heisst freigegeben (siehe unten)
        ``inaktiv``      → auslaufend/gesperrt

    **Zwei Achsen, die beide «aktiv» heissen — und sie meinen Verschiedenes:**
    ``is_active`` ist der **Soft-Delete** («den Datensatz gibt es nicht»), ``status``
    der **fachliche** Zustand. Ausser Betrieb genommen wird über ``status``; darum nimmt
    ``ArticleUpdate`` ``is_active`` gar nicht mehr entgegen.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    # ``freigegeben`` | ``inaktiv``. **``draft`` kommt nicht mehr vor**: ein Artikel
    # entsteht erst mit seiner Freigabe (services/articles.py), und bis dahin gibt es
    # keine Zeile. Der Wert bleibt als Spalte, weil «inaktiv» ein Zustand ist.
    #
    # **Der Standardwert kommt aus dem Katalog, nicht aus einem Literal.** Migration
    # ``107`` hat die Daten und den *Server*-Default auf die deutsche Liste gezogen – der
    # *ORM*-Default blieb auf ``"released"`` stehen und gewinnt gegen den Server-Default:
    # jede Zeile, die ohne ausdrücklichen Status entsteht, hätte das alte Wort
    # zurückgebracht. Aufgefallen ist es erst, als mit ``articles.may_create`` der erste
    # Leser kam, der die Frage «ist dieser Artikel freigegeben?» wirklich beantworten muss.
    status: Mapped[str] = mapped_column(
        String(20), default=st.FREIGEGEBEN, server_default=st.FREIGEGEBEN, nullable=False,
    )

    # Versionsstempel des **Erzeugungsprozesses** (``article_process_steps``). Er zählt
    # bei jeder Änderung der Vorlage hoch und wird auf die Kopie im Auftrag geschrieben.
    # Damit ist an einem laufenden Auftrag ablesbar, welchen Stand er fährt – und eine
    # spätere Artikeländerung kann ihn nicht rückwirkend umschreiben (PROCESS_CORE.md §6.4).
    process_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )

    # Stammdaten. Pflicht ist einzig der **Name**; Einheit/Serialisierung tragen einen
    # Default (Stk / unit), Grösse & Gewicht sind optional (physische Attribute, die z. B.
    # ein Dokument-Artikel nicht braucht). Es gibt KEINE Typ-Unterscheidung physisch/nicht-
    # physisch mehr: ob ein Dokument entsteht, entscheidet allein der Prozessschritt «document».
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
    supplier_article_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Lieferanten-Artikelnummer
    # Gefahrgut: ein Spezifikationsfeld wie jedes andere – es reist mit dem
    # Beschaffungs-Beleg zum Lieferanten (``services/article_fields``), damit er weiss,
    # was er in die Hand nimmt.
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Die frühere Erfassungsmaske am Artikel (``capture_fields``) ist entfallen: was
    # erfasst wird, sagt das **Modul** im Prozess (``process_steps.config``). Am Artikel
    # war sie eine zweite Stelle für dieselbe Frage – und sie hing an keinem Prozess, man
    # konnte also an einem Stück erfassen, ohne dass es irgendwo davorstand.

    # Einstandspreis netto/Stück – read-only, aus dem zuletzt bestellten
    # Beschaffungs-Beleg automatisch zurückgeschrieben (``services/purchase``).
    landed_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Artikels (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
