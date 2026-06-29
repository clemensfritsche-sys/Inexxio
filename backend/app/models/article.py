from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Article(Base, TimestampMixin):
    """Stammdaten-Datensatz für einen Artikel (Phase 2 – Produktion).

    Statuswerte (`status`):
        draft     → Entwurf (neu angelegt, noch nicht freigegeben)
        released  → Freigegeben (für Prozesse/Bestellungen nutzbar)
        inactive  → inaktiv (auslaufend/gesperrt)

    `is_active` bleibt der Soft-Delete-Flag (Datensatz ausgeblendet),
    unabhängig vom fachlichen `status`.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)

    # Stammdaten (Pflichtfelder)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)  # Stk | m | kg | l
    serialization: Mapped[str] = mapped_column(String(20), nullable=False)  # unit | batch
    size: Mapped[str] = mapped_column(String(100), nullable=False)  # z. B. 3x40x600
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Optionale Stammdaten – nur bei Bedarf gepflegt (dynamische Feldliste im UI).
    material: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cad_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # CAD-Link
    surface: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Oberfläche
    min_order_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # MOQ
    safety_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # Sicherheitsbestand
    supplier_article_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Lieferanten-Artikelnummer

    # Einstandspreis netto/Stück – read-only, aus der zuletzt freigegebenen
    # Bestellung (Purchase Order) automatisch zurückgeschrieben.
    landed_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Artikels (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # ── Verkauf / Shop (dritte, bewusst LEBENDE Ebene am Artikel) ───────────────────
    # Anders als Spezifikation + Prozess (die mit der Freigabe einfrieren) bleibt die
    # Verkaufs-Ebene in JEDEM Status editierbar (analog ``landed_unit_cost``): Preise,
    # Texte/Bilder, Sichtbarkeit und Zielgruppe ändern sich, während der Artikel
    # produktiv verkauft wird. Kein eigenes «Angebot»-Objekt, keine Objektnummer.
    sales_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    # Sichtbarkeit: public (im Shop gelistet) | private (nur zugewiesene Kunden) |
    # unlisted (nur per direktem Link, nicht gelistet).
    sales_visibility: Mapped[str] = mapped_column(
        String(10), default="public", server_default="public", nullable=False)
    # Lokalisierter Inhalt: {"de": {title, subtitle, description, images: [url]}, "en": {…}}.
    sales_content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
