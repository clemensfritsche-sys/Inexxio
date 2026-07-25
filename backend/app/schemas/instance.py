from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class InstanceLocation(BaseModel):
    """Eine Teilmenge einer Charge an einem Standort (Verteilung ohne Instanz-Teilung).
    Bei einer nicht verteilten Instanz enthält die Liste genau EINEN Eintrag. Read-only –
    die Verteilung entsteht ausschliesslich über einen Auftrag + Bewegungsschritt."""

    location_type: str
    location_id: int
    quantity: float
    location_label: Optional[str] = None   # vom Router denormalisiert


class LocationHop(BaseModel):
    """Eine Station der Standort-Kette (von innen nach aussen).

    ``location_type='address'`` markiert den abschliessenden geografischen Eintrag –
    er trägt keine Objektnummer, sondern die Anschrift."""

    location_type: str
    location_id: Optional[int] = None
    label: Optional[str] = None


class InstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    article_id: int
    order_id: int
    kind: str
    quantity: float       # Bruchmenge möglich (kg/m²/m³/l) – nicht nur ganze Stück
    serial_number: Optional[str]
    quality: str          # QC-Verdikt: pending | passed | failed
    disposition: str      # Verbleib: in_process | in_stock | consumed | sold | scrapped
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Standort-Verteilung (vom Router denormalisiert): bei EINEM Ort ein Eintrag, bei einer
    # verteilten Charge mehrere (300 @ Band A · 700 @ Band B). Summe = quantity.
    locations: list[InstanceLocation] = []

    reserved_for_order_id: Optional[int] = None
    reserved_quantity: float = 0   # mengengenau reservierte Menge (0 = frei)

    # Das Modell-Attribut ``locations`` ist die rohe JSONB-Map (dict) – die Antwort trägt
    # aber die denormalisierte Liste. Beim ``model_validate`` die rohe dict/None auf ``[]``
    # normalisieren; der Router füllt danach die effektive Verteilung ein.
    @field_validator("locations", mode="before")
    @classmethod
    def _loc_list(cls, v):
        return v if isinstance(v, list) else []

    # Denormalisiert vom Router
    order_object_id: Optional[int] = None
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    location_label: Optional[str] = None
    # Physischer Standort bei Einbau (location_type == 'instance'): wo die Host-
    # Instanz tatsächlich liegt – die Komponente «wandert» mit ihr mit.
    physical_location_label: Optional[str] = None
    reserved_for_order_object_id: Optional[int] = None
    # **Standort-Kette** (nur im Detail gefüllt, nicht im Feed): Instanz → Behälter →
    # Lagerplatz → Anschrift. Beantwortet «wo genau liegt das?» in einem Blick.
    location_path: list[LocationHop] = []


class ObjectReference(BaseModel):
    """Ein Verweis auf ein Objekt (Verwendungsnachweis) – generisch wiederverwendet,
    z. B. für die lagernden Instanzen / referenzierenden Artikel eines Lagerplatzes."""

    kind: str          # menschenlesbare Rolle des Verweises
    ref_type: str      # order | instance | article | lagerplatz | user
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
    article_id: int   # welcher Position (Mehrpositionen-Auftrag) die Instanz zugehört
    kind: str
    quantity: float       # Bruchmenge möglich (kg/m²/m³/l)
    quality: str          # QC-Verdikt: pending | passed | failed
    disposition: str      # Verbleib: in_process | in_stock | consumed | sold | scrapped
    reserved_for_order_id: Optional[int] = None   # fest reserviert (scharf ab Freigabe)
    reserved_quantity: float = 0                   # mengengenau reservierte Menge
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    location_label: Optional[str] = None   # vom Router denormalisiert
    physical_location_label: Optional[str] = None  # physischer Ort bei Einbau (instance-Kette)
    # Wie viel dieser (Chargen-)Instanz der Auftrag bewegt: die vom Auftrag reservierte
    # Teilmenge, wenn er nur EINEN Teil der Charge betrifft (z. B. 10 von 1000); sonst NULL
    # (= ganze Instanz). Nur zur Anzeige im Bewegungs-Panel (vom Router denormalisiert).
    move_quantity: Optional[float] = None
