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
    quality: str          # QC-Verdikt: pending | passed | failed
    disposition: str      # Verbleib: in_process | in_stock | consumed | sold | scrapped
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    reserved_for_order_id: Optional[int] = None
    reserved_quantity: int = 0   # mengengenau reservierte Stück (0 = frei)

    # Denormalisiert vom Router
    order_object_id: Optional[int] = None
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    location_label: Optional[str] = None
    # Physischer Standort bei Einbau (location_type == 'instance'): wo die Host-
    # Instanz tatsächlich liegt – die Komponente «wandert» mit ihr mit.
    physical_location_label: Optional[str] = None
    reserved_for_order_object_id: Optional[int] = None


class ObjectReference(BaseModel):
    """Ein Verweis auf ein Objekt (Verwendungsnachweis) – generisch wiederverwendet,
    z. B. für die lagernden Instanzen / referenzierenden Artikel eines Lagerplatzes."""

    kind: str          # menschenlesbare Rolle des Verweises
    ref_type: str      # order | instance | article | lagerplatz | user | claim
    object_id: int
    label: str
    at: datetime


class InstanceOrderRef(BaseModel):
    """Ein Auftrag, der diese Instanz angefasst hat – eine Instanz ist die Summe
    aller Prozesse, und Prozesse werden ausschliesslich durch Aufträge angestossen."""

    object_id: int       # Auftragsnummer (klickbar)
    status: str          # draft | released | completed | inactive
    roles: list[str]     # was der Auftrag mit der Instanz tat (z. B. Erzeugt, Datenerfassung)
    at: datetime         # Zeitpunkt (Sortierung/Anzeige)


class InstanceEmbed(BaseModel):
    """Kurzform für die Einbettung in den Auftrag (Instanzen-/Bewegungs-Panel)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    kind: str
    quantity: int
    quality: str          # QC-Verdikt: pending | passed | failed
    disposition: str      # Verbleib: in_process | in_stock | consumed | sold | scrapped
    reserved_for_order_id: Optional[int] = None   # fest reserviert (scharf ab Freigabe)
    reserved_quantity: int = 0                     # mengengenau reservierte Stück
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    location_label: Optional[str] = None   # vom Router denormalisiert
    physical_location_label: Optional[str] = None  # physischer Ort bei Einbau (instance-Kette)
