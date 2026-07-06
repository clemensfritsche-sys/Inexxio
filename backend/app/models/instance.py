from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Instance(Base, TimestampMixin):
    """Bestandsobjekt – entsteht bei der **Auftragsfreigabe**.

    Aus der Artikel-Einstellung ``serialization`` abgeleitet:
        unit  → je Stück eine eigene Instanz (quantity = 1, eigene Nummer)
        batch → eine Charge-Instanz mit quantity = Bestellmenge

    Trägt eine eigene 9-stellige Objektnummer (etikettier-/QR-fähig) und ist die
    Grundlage des Bestands. Entsteht unter einem Auftrag (``order_id``).
    """

    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)

    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Nullable (F): Lager-Instanzen (``is_location``) entstehen NICHT aus einem Auftrag.
    order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    kind: Mapped[str] = mapped_column(String(10), default="unit", nullable=False)   # unit | batch
    # Menge als Dezimalzahl (NUMERIC(14,3)): ein Einzelteil trägt 1, eine Charge die
    # Bestellmenge – für kg/m²/m³/l auch als **Bruchmenge** (2.5 kg, 0.75 m²), nicht nur
    # ganze Stück. Arithmetik ausschliesslich über ``services/quantity.py`` (exakt, kein float).
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=1, nullable=False)
    serial_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # ZWEI getrennte Achsen statt eines überladenen qc_status:
    #   quality     = QC-Verdikt:  pending | passed | failed   («ist es gut?»)
    #   disposition = Verbleib:     in_process | in_stock | consumed | sold | scrapped  («wo ist es?»)
    # Verbrauchbar/zählbar ist eine Instanz nur, wenn quality=passed UND disposition=in_stock.
    quality: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), default="in_process", nullable=False)
    # Zeitpunkt der Freigabe (disposition → in_stock). Basis für FIFO beim Verbrauch
    # (Ressource-Schritt): ältester Freigabe-Zeitpunkt zuerst.
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Haltbarkeit (E): gesetzt bei Freigabe, wenn der Artikel eine ``shelf_life_days`` trägt.
    # Ein abgelaufenes Teil wird beim Sweep ausgebucht (disposition → scrapped).
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Lagerplatz-Instanz (F): eine Instanz eines is_location-Artikels IST ein Lagerplatz ──
    # ``is_location`` (denormalisiert vom Artikel) → aus dem Bestand ausgeschlossen. Geo/Adresse
    # (der Karten-Standort, per-Instanz – NICHT am Artikel-Typ) + freie Bemerkung. Die Kapazität
    # («Lagermenge») ist die normale ``quantity``.
    is_location: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    address_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Standort – eine Instanz hat IMMER einen Standort (ab Freigabe: Lieferant bzw. Wareneingang).
    # Der Standort ist stets ein Datensatzobjekt mit Nummer:
    #   lagerplatz → Lagerplatz-Instanz (is_location) | user → UserProfile | instance → andere Instanz
    location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # Reservierung – **mengengenau, ohne Teilung der Instanz** (die Objektnummer bleibt
    # IMMER erhalten – physisch sind die Teile mit dieser Nummer beschriftet):
    #   reservations      = {auftrag_db_id: menge}  – wer wie viel dieser Instanz beansprucht
    #   reserved_quantity = Summe der Reservierungen (denormalisiert, für SQL-Verfügbarkeit)
    # Frei verfügbar (für andere Aufträge) = quantity − reserved_quantity. Eine Charge von
    # 1000 Schrauben, von der 30 reserviert sind, bleibt also mit 970 frei verfügbar –
    # **ohne** dass eine zweite Instanz mit eigener Nummer entsteht.
    reservations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=0, server_default="0", nullable=False)

    # Einzel-Reservierungs-Zeiger (Altfeld / Schnellprüfung): gesetzt, solange genau EIN
    # Auftrag die Instanz (teil-)reserviert. Massgeblich ist die ``reservations``-Map.
    reserved_for_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # **Subjekt** eines Bestands-Auftrags (Prozess-Quelle ``stock``: Verkauf/Entnahme):
    # die FIFO-ausgewählten Instanzen, auf die der Auftrag wirkt (≠ Komponenten-
    # Reservierung). Bei Abschluss verlassen sie den Bestand (sold/consumed).
    subject_of_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
