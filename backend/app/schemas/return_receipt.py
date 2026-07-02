from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReturnItem(BaseModel):
    """Eine zurückzunehmende Instanz mit optionaler **Menge** (Charge): ``quantity`` weglassen
    = 1 Stück (Einzelteil). Analog ``ScrapItem``."""
    instance_id: int
    quantity: Optional[int] = None


class ReturnUpdate(BaseModel):
    """Erfassung des Schritts «Rücknahme»: welche verkauften Instanzen zurückkommen (+ Menge),
    an welchen Standort, ob zur Nachprüfung, optionale Notiz.

    ``items`` (mit Teilmenge) und die Kurzform ``instance_ids`` (1 Stück) werden zusammengeführt.
    Ohne Zielstandort geht die Ware an den automatischen Wareneingang («nie ohne Standort»)."""
    instance_ids: list[int] = []
    items: list[ReturnItem] = []
    location_type: Optional[str] = None   # lagerplatz | user | instance
    location_id: Optional[int] = None
    to_inspection: bool = False            # zurück als 'pending' (erst prüfen) statt sofort verkäuflich
    note: Optional[str] = None
    step_id: Optional[int] = None          # konkrete Schritt-Definition (Mehr-Operationen-Routing)


class ReturnEmbed(BaseModel):
    """Eingebetteter Stand der Rücknahme (im Auftrag) – Spiegel von ``DisposalEmbed``.
    Welche Instanzen zurückkamen, steht in ``OrderResponse.instances`` (wieder ``in_stock``)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    done: bool = False
    note: Optional[str] = None
    received_by_name: Optional[str] = None
    returned_count: int = 0
    to_inspection: bool = False
    location_label: Optional[str] = None
