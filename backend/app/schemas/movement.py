from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .shipment import ShipmentEmbed

# Ein Standort ist immer ein **Halter** – ein Datensatzobjekt mit 9-stelliger Nummer:
#   user     → UserProfile (Mitarbeiter, Lieferant, Kunde)
#   instance → andere Instanz (Behälter, Palette, Maschine, LKW)
#   company  → das Unternehmen selbst («im Betrieb», Adresse aus den Firmen-Stammdaten)
#
# Der frühere Typ **lagerplatz** ist ersatzlos entfallen: ein Lagerplatz war ein eigener
# Datensatztyp, dessen Felder (Masse, Traglast, Flags, Adresse) nirgends Logik trugen. Wer
# einen benannten Platz braucht, führt ihn als **Instanz** (ein Behälter ist ein Ding, das
# man besitzt); wer keinen braucht, lässt den Standort offen – **standortlos ist erlaubt**
# und im ganzen System ein regulärer Zustand (NULL = «noch nicht festgelegt»).
LOCATION_TYPES = ("user", "instance", "company")


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

    # Vorgabe-Ziel aus der Prozessdefinition (optional; vom Router denormalisiert)
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    target_location_label: Optional[str] = None
    # Bewegungs-Modus des Schritts: 'customer' = Pflicht-Versand zum Kunden (nur dann sind
    # VERKAUFTE Instanzen bewegbar). Das Frontend spiegelt damit exakt die Backend-Regel,
    # statt sie über den Ziel-Typ zu erraten (Ursache «Instanz gehört nicht zu diesem Auftrag»).
    mode: Optional[str] = None
    # Versand (ADR 005): abgeleitete Transportklasse + Versand-Beleg dieses Schritts.
    # Nur gesetzt, wenn die Bewegung ein klassifizierbares Ziel hat (sonst None → keine Box).
    shipment: Optional[ShipmentEmbed] = None
