from typing import Optional
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Shipment(Base, TimestampMixin):
    """Versand-Beleg eines Bewegungs-Schritts – unter dem Auftrag (KEINE eigene Nummer).

    «Versand wird ABGELEITET, nicht bestellt» (ADR 005): der Bewegungs-Schritt kennt
    Quelle und Ziel; liegt das Ziel ausserhalb des Betriebs-Geofence (bzw. ist es eine
    externe Person: Kunde/Lieferant), ist ein externer Transport nötig → dieser Beleg
    hält Rate-Shopping (Angebots-Snapshot), Label-Kauf und Tracking fest. Analog
    ``purchase_orders``/``movements``: eine Fachzeile je Schritt-Definition (``step_id``).

    Der physische Vollzug bleibt beim Bewegungs-Schritt scan-quittiert – der Versand
    ist die vorbereitende Geld-/Carrier-Seite (Label), die Bewegung der Vollzug.
    """

    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Routing: an welche Bewegungs-Schritt-Definition gebunden (mehrere je Auftrag möglich).
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # Richtung aus der Klassifikation: outbound (von uns nach draussen) | inbound
    # (Abholung beim Lieferanten / Kunden-Retoure – wir organisieren den Rücktransport).
    direction: Mapped[str] = mapped_column(String(10), default="outbound", nullable=False)
    # draft → quoted (Raten geladen) → purchased (Label gekauft) → done (Bewegung
    # quittiert) | cancelled. 'manual'/'self' überspringen quoted/purchased.
    status: Mapped[str] = mapped_column(String(12), default="draft", nullable=False)
    # Ausführender Provider: 'shippo' (Aggregator) | 'manual' (von Hand) | 'self' (Selbst-
    # transport, kein Carrier). Snapshot des zur Laufzeit aufgelösten Providers.
    provider: Mapped[str] = mapped_column(String(12), default="manual", nullable=False)
    # Per-Auftrag-Override des Transport-Modus (auto | carrier | self | none); leer = der
    # Modus der Schritt-Definition bzw. 'auto'. Lebt bewusst HIER (nicht am Artikel-Schritt),
    # damit ein Auftrag den Artikel-Prozess nicht mutiert.
    transport_mode: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Adress-Snapshots (beim Quote eingefroren; Format siehe services/logistics.py).
    address_from: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    address_to: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Paket-Schätzung aus den Artikel-Daten: [{weight_kg, length_cm, width_cm, height_cm}].
    parcels: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    hazmat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Rate-Shopping-Snapshot: [{rate_id, carrier, service, amount, currency, days, provider_rate_id}].
    rates: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    chosen_rate_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Ergebnis des Label-Kaufs bzw. der manuellen Erfassung.
    carrier: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    service: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    label_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tracking_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cost_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    cost_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    provider_shipment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
