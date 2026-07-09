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
    safety_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # Sicherheitsbestand = Meldebestand (E)
    supplier_article_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Lieferanten-Artikelnummer
    # Gefahrgut (optionales Spezifikationsfeld): fliesst als Warnung in den Versand (ADR 005)
    # – ein Paket mit Gefahrgut braucht Spezialbehandlung beim Carrier.
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # ── Meldebestand / Auto-Nachbestellung (E) ─────────────────────────────────────
    # «Nicht die Zeit soll bestellen, sondern der Bestand»: fällt der freie Bestand unter
    # ``safety_stock`` (= Meldebestand), legt das System einen Nachschub-Auftrag an (bis
    # ``reorder_target`` bzw. – wenn leer – zurück auf ``safety_stock``). Setzt einen
    # freigegebenen Artikel-Prozess voraus (produzierbar/beschaffbar).
    reorder_target: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)

    # ── Fixierter Standort (optionales Spezifikationsfeld) ──────────────────────────
    # Funktioniert exakt wie die Standort-Definition am Lagerplatz-Datensatz: GPS-Koordinaten
    # + per Reverse-Geocoding gefüllte Adresse (Strasse/PLZ/Ort/Land). Rein deskriptiv am
    # Artikel hinterlegt – der feste geografische Ort, an dem dieser Artikel verortet ist.
    fixed_location_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    fixed_location_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    fixed_location_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fixed_location_zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    fixed_location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fixed_location_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Beschaffungsquelle (Teil der Spezifikation, friert bei Freigabe ein) ───────────
    # WO dieser Artikel beschafft wird, gehört zur Produktspezifikation – nicht in jeden
    # einzelnen Beschaffungs-Prozessschritt. Der ``purchase``-Schritt bleibt der Auslöser und
    # **erbt diese Quelle als Default** (pro Fall am Schritt überschreibbar). Zwei Modi:
    #   supplier → Bestellung bei ``default_supplier_id`` (UserProfile, Rolle 'supplier')
    #   webshop  → Beschaffung über ``default_webshop_url`` (kein externer Lieferant)
    procurement_mode: Mapped[str] = mapped_column(
        String(20), default="supplier", server_default="supplier", nullable=False)
    default_supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    default_webshop_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

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
    # Sichtbarkeit: public (im Shop gelistet) | private (nur zugewiesene Kunden).
    sales_visibility: Mapped[str] = mapped_column(
        String(10), default="public", server_default="public", nullable=False)
    # **Verfügbarkeit (Achse B)** – unabhängig vom Preismodell (Einmalkauf/Abo):
    #   make  → «auf Bestellung gefertigt» (Made-to-Order): der Kauf löst einen
    #           Produktions-Auftrag aus, der den **Artikel-Prozess** fährt (kein Lager nötig).
    #   stock → «ab Lager / limitierte Auflage»: der Kauf bedient sich FIFO aus dem
    #           Bestand, bis dieser erschöpft ist.
    sales_fulfillment: Mapped[str] = mapped_column(
        String(10), default="make", server_default="make", nullable=False)
    # Lokalisierter Inhalt: {"de": {title, subtitle, description, images: [url]}, "en": {…}}.
    sales_content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
