from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class InstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    article_id: int
    order_id: int
    kind: str
    quantity: int
    serial_number: Optional[str]
    qc_status: str
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Denormalisiert vom Router
    order_object_id: Optional[int] = None
    article_name: Optional[str] = None
    location_label: Optional[str] = None


class InstanceReference(BaseModel):
    """Ein Verwendungsnachweis: wo wird diese Instanz referenziert?"""

    kind: str          # Herkunftsauftrag | Datenerfassung | Eingebaut in | Enthält Instanz | Aktueller Standort
    ref_type: str      # order | instance | lagerplatz | user
    object_id: int
    label: str
    at: datetime


class InstanceEmbed(BaseModel):
    """Kurzform für die Einbettung in den Auftrag (Instanzen-/Bewegungs-Panel)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    kind: str
    quantity: int
    qc_status: str
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    location_label: Optional[str] = None   # vom Router denormalisiert
