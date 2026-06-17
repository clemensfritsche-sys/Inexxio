from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# Ein Standort ist immer ein Datensatzobjekt mit 9-stelliger Nummer:
#   lagerplatz → StorageLocation
#   user       → UserProfile (Mitarbeiter, Lieferant, Kunde)
#   instance   → andere Instanz (z. B. eingebaut in Maschine/Behälter)
LOCATION_TYPES = ("lagerplatz", "user", "instance")


class MovementTarget(BaseModel):
    """Zielstandort einer einzelnen Instanz (per Objektnummer adressiert)."""

    instance_id: int          # object_id der zu bewegenden Instanz
    location_type: str
    location_id: int          # object_id des Zielobjekts

    @field_validator("location_type")
    @classmethod
    def _loc_ok(cls, v: str) -> str:
        if v not in LOCATION_TYPES:
            raise ValueError(f"Standort-Typ muss eine von {', '.join(LOCATION_TYPES)} sein")
        return v


class MovementUpdate(BaseModel):
    """Erfassung des Bewegungsschritts: je Instanz ein Zielstandort + Notiz."""

    targets: list[MovementTarget] = []
    note: Optional[str] = None


class MovementEmbed(BaseModel):
    """Eingebetteter Stand der Bewegung (im Auftrag).

    Die aktuellen Standorte der Instanzen stehen in ``OrderResponse.instances``;
    dieser Embed trägt nur den Abschluss-Status und das (optionale) Vorgabe-Ziel
    aus der Prozessdefinition.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    done: bool = False
    note: Optional[str] = None
    moved_by_name: Optional[str] = None

    # Vorgabe-Ziel aus der Prozessdefinition (optional; vom Router denormalisiert)
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    target_location_label: Optional[str] = None
