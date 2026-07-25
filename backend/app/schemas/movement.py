from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .place import Place
from .shipment import ShipmentEmbed

# Ein Standort ist ein **Halter**. Vier Arten – drei davon Datensatzobjekte mit 9-stelliger
# Objektnummer, die vierte (`place`) eine Adresse direkt auf der Instanz:
#   place    → Adresse/GPS inline (KEINE Objektnummer)          ← das «Blatt» der Kette
#   user     → UserProfile (Mitarbeiter, Lieferant, Kunde)
#   instance → andere Instanz (Behälter, Palette, Maschine, LKW)
#   company  → das Unternehmen selbst (Betriebsadresse)
# Ein **benannter Platz** (Regal A, Wareneingang) ist eine Instanz, die andere Instanzen hält –
# das ersetzt den früheren eigenständigen `lagerplatz`-Datensatztyp.
LOCATION_TYPES = ("place", "user", "instance", "company")

# Halter, die eine Objektnummer tragen – nur auf sie ist eine Charge mengengenau
# **verteilbar** (``services/location_split.py`` schlüsselt nach Objektnummer).
ADDRESSABLE_LOCATION_TYPES = ("user", "instance", "company")


class MovementTarget(BaseModel):
    """Zielstandort einer einzelnen Instanz.

    Entweder ein Datensatzobjekt (``location_id`` = Objektnummer) ODER – bei
    ``location_type='place'`` – ein **Ort** (Adresse/GPS in ``place``, ohne Objektnummer)."""

    instance_id: int          # object_id der zu bewegenden Instanz
    location_type: str
    location_id: Optional[int] = None   # Objektnummer des Zielobjekts (nicht bei 'place')
    place: Optional[Place] = None       # nur bei 'place': Adresse/GPS

    @field_validator("location_type")
    @classmethod
    def _loc_ok(cls, v: str) -> str:
        if v not in LOCATION_TYPES:
            raise ValueError(f"Standort-Typ muss eine von {', '.join(LOCATION_TYPES)} sein")
        return v

    @model_validator(mode="after")
    def _target_complete(self):
        """Genau EINE Adressierung: Ort → ``place``, sonst → ``location_id``."""
        if self.location_type == "place":
            if self.place is None:
                raise ValueError("Für einen Ort ist eine Adresse bzw. ein Standort erforderlich")
            self.location_id = None
        else:
            if self.location_id is None:
                raise ValueError("Für dieses Ziel ist eine Objektnummer erforderlich")
            self.place = None
        return self


class MovementUpdate(BaseModel):
    """Erfassung des Bewegungsschritts: je Instanz ein Zielstandort + Notiz.

    Bei einem Versand zum Kunden (outbound) optional Sendungsverfolgung."""

    targets: list[MovementTarget] = []
    note: Optional[str] = None
    step_id: Optional[int] = None   # konkrete Schritt-Definition (Mehr-Operationen-Routing)
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None


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
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None

    # Vorgabe-Ziel aus der Prozessdefinition (optional; vom Router denormalisiert).
    # Bei einem Vorgabe-**Ort** ist ``target_location_id`` NULL und ``target_place`` gesetzt.
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    target_location_label: Optional[str] = None
    target_place: Optional[dict] = None
    # Bewegungs-Modus des Schritts: 'customer' = Pflicht-Versand zum Kunden (nur dann sind
    # VERKAUFTE Instanzen bewegbar). Das Frontend spiegelt damit exakt die Backend-Regel,
    # statt sie über den Ziel-Typ zu erraten (Ursache «Instanz gehört nicht zu diesem Auftrag»).
    mode: Optional[str] = None
    # Versand (ADR 005): abgeleitete Transportklasse + Versand-Beleg dieses Schritts.
    # Nur gesetzt, wenn die Bewegung ein klassifizierbares Ziel hat (sonst None → keine Box).
    shipment: Optional[ShipmentEmbed] = None
