from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .inspection import InspectionEmbed
from .instance import InstanceEmbed
from .movement import MovementEmbed
from .purchase_order import PurchaseEmbed
from .resource import ResourceEmbed
from .sale import SaleEmbed


class OrderStepInfo(BaseModel):
    """Ein Schritt im Auftrag-Stepper (für die Fortschritts-Visualisierung).

    Mehr-Operationen-Routing: ``id`` (Schritt-Definition) ist der eindeutige
    Schlüssel; je Schritt ist – passend zum Typ – genau ein Ausführungs-Embed
    gesetzt, damit mehrere gleichartige Schritte unabhängig bedient werden."""

    id: int = 0
    step_type: str
    position: int
    label: str
    state: str   # done | active | locked | failed
    completed_by: Optional[str] = None   # wer hat den Schritt abgeschlossen
    completed_at: Optional[datetime] = None  # wann

    # Ausführungs-Embed des konkreten Schritts (nur das zum Typ passende ist gesetzt)
    purchase: Optional[PurchaseEmbed] = None
    sale: Optional[SaleEmbed] = None
    inspection: Optional[InspectionEmbed] = None
    movement: Optional[MovementEmbed] = None
    resource: Optional[ResourceEmbed] = None

# completed wird automatisch gesetzt (alle Prozessschritte erledigt)
ALLOWED_STATUS = ("draft", "released", "inactive", "completed")


def _validate_future_date(v: Optional[date]) -> Optional[date]:
    """Wunsch-Liefertermin darf nicht in der Vergangenheit liegen."""
    if v is None:
        return v
    if v < date.today():
        raise ValueError("Wunsch-Liefertermin darf nicht in der Vergangenheit liegen")
    return v


class OrderCreate(BaseModel):
    """Anlage eines Auftrags über '+'. Status startet als 'draft'. Zwei Modi:

    MAKE   – ``article_id`` + ``quantity`` (beide Pflicht): fährt den **Prozess des
             Artikels** und ERZEUGT bei Freigabe die Instanzen.
    CUSTOM – ``instance_object_ids`` (≥1, gleicher Artikel): ein **individueller
             Prozess** (eigene Schritte) wirkt auf bereits vorhandene Instanzen."""

    mode: str = "make"
    article_id: Optional[int] = None
    quantity: Optional[int] = None
    instance_object_ids: Optional[list[int]] = None
    desired_delivery_date: Optional[date] = None
    # Wiederkehrend (direkt am Auftrag, kein eigenes Objekt)
    recurrence_active: Optional[bool] = None
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: Optional[int] = None
    recurrence_anchor: Optional[date] = None

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: str) -> str:
        if v not in ("make", "custom"):
            raise ValueError("Modus muss 'make' oder 'custom' sein")
        return v

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Menge muss grösser als 0 sein")
        return v

    @field_validator("desired_delivery_date")
    @classmethod
    def _date_future(cls, v: Optional[date]) -> Optional[date]:
        return _validate_future_date(v)

    @model_validator(mode="after")
    def _consistent(self) -> "OrderCreate":
        if self.mode == "make":
            if not self.article_id or not self.quantity:
                raise ValueError("Für einen Artikel-Auftrag sind Artikel und Menge Pflicht")
        else:
            if not self.instance_object_ids:
                raise ValueError("Für einen individuellen Auftrag mindestens eine Instanz wählen")
        return self


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    article_id: Optional[int] = None
    quantity: Optional[int] = None
    desired_delivery_date: Optional[date] = None
    recurrence_active: Optional[bool] = None
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: Optional[int] = None
    recurrence_anchor: Optional[date] = None
    is_active: Optional[bool] = None
    expected_updated_at: Optional[datetime] = None   # Optimistic Locking (optional)

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_STATUS:
            raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
        return v

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Menge muss grösser als 0 sein")
        return v

    @field_validator("desired_delivery_date")
    @classmethod
    def _date_future(cls, v: Optional[date]) -> Optional[date]:
        return _validate_future_date(v)


class OrderSummary(BaseModel):
    """Schlanke Auftrags-Sicht für den Feed (OHNE Prozess-Embeds).

    Der Feed braucht nur Kopf-Daten; die teuren Embeds (FIFO-Vorschau, Stichproben,
    Verlauf) werden erst im Detail (``GET /orders/{id}``) berechnet."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    mode: str = "make"
    article_id: Optional[int]
    quantity: Optional[int]
    desired_delivery_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # denormalisiert (Batch-geladen, nicht je Auftrag)
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    article_unit: Optional[str] = None
    purchase_status: Optional[str] = None   # für das Status-Badge im Feed
    recurrence_active: bool = False         # wiederkehrender Auftrag (Badge)
    recurrence_due: bool = False            # fällig (Termin − Vorlaufzeit erreicht)
    replaced_by_id: Optional[int] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    mode: str = "make"
    title: Optional[str]
    article_id: Optional[int]
    quantity: Optional[int]
    desired_delivery_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Wiederkehrend (am Auftrag)
    recurrence_active: bool = False
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: int = 0
    recurrence_anchor: Optional[date] = None
    recurring_parent_id: Optional[int] = None
    recurrence_due: bool = False

    # Denormalisierter Artikel + eingebetteter Prozess (Beschaffung/Verkauf)
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    article_size: Optional[str] = None
    article_unit: Optional[str] = None
    article_weight_kg: Optional[Decimal] = None
    article_serialization: Optional[str] = None
    article_supplier_article_number: Optional[str] = None
    purchase: Optional[PurchaseEmbed] = None
    sale: Optional[SaleEmbed] = None
    instances: list[InstanceEmbed] = []
    inspection: Optional[InspectionEmbed] = None
    movement: Optional[MovementEmbed] = None
    resource: Optional[ResourceEmbed] = None
    steps: list[OrderStepInfo] = []
    # Ersetzen (Nachvollziehbarkeit): Nachfolger / Vorgänger (Objektnummern)
    replaced_by_id: Optional[int] = None
    replaces_id: Optional[int] = None
