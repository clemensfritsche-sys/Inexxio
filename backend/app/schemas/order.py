from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .inspection import InspectionEmbed
from .instance import InstanceEmbed
from .movement import MovementEmbed
from .purchase_order import PurchaseEmbed
from .resource import ResourceEmbed


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
    """Anlage eines Auftrags über '+'. Status startet als 'draft'.
    Der Auftrag trägt keinen freien Namen – er heisst immer «Auftrag»."""

    article_id: Optional[int] = None
    quantity: Optional[int] = None
    desired_delivery_date: Optional[date] = None

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


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    article_id: Optional[int] = None
    quantity: Optional[int] = None
    desired_delivery_date: Optional[date] = None
    is_active: Optional[bool] = None

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
    replaced_by_id: Optional[int] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    title: Optional[str]
    article_id: Optional[int]
    quantity: Optional[int]
    desired_delivery_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Denormalisierter Artikel + eingebetteter Prozess (Beschaffung)
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    article_size: Optional[str] = None
    article_unit: Optional[str] = None
    article_weight_kg: Optional[Decimal] = None
    article_serialization: Optional[str] = None
    article_supplier_article_number: Optional[str] = None
    purchase: Optional[PurchaseEmbed] = None
    instances: list[InstanceEmbed] = []
    inspection: Optional[InspectionEmbed] = None
    movement: Optional[MovementEmbed] = None
    resource: Optional[ResourceEmbed] = None
    steps: list[OrderStepInfo] = []
    # Ersetzen (Nachvollziehbarkeit): Nachfolger / Vorgänger (Objektnummern)
    replaced_by_id: Optional[int] = None
    replaces_id: Optional[int] = None
