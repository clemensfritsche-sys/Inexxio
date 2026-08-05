from typing import Optional

from pydantic import BaseModel, ConfigDict


class ScrapItem(BaseModel):
    """Eine zu verschrottende Instanz mit optionaler **Teilmenge** (Charge): ``quantity``
    weglassen = die ganze (Rest-)Menge der Instanz. Analog zum Ressourcenmodell, das eine
    Charge teilentnimmt (keine Teilung/keine neue Objektnummer – nur die Menge sinkt)."""
    instance_id: int
    quantity: Optional[int] = None


class ScrapUpdate(BaseModel):
    """Erfassung des Verschrottungsschritts: die zu verschrottenden Instanzen + optionale
    Notiz/Grund. Mindestens eine Instanz.

    ``items`` erlaubt je Instanz eine **Teilmenge** (Charge teilverschrotten); ``instance_ids``
    bleibt die Kurzform «ganze Instanz(en)» (beide Wege werden gemischt zusammengeführt)."""

    instance_ids: list[int] = []
    items: list[ScrapItem] = []
    note: Optional[str] = None
    step_id: Optional[int] = None   # konkrete Schritt-Definition (Mehr-Operationen-Routing)


class DisposalEmbed(BaseModel):
    """Eingebetteter Stand der Verschrottung (im Auftrag).

    Welche Instanzen verschrottet wurden, steht in ``OrderResponse.instances``
    (``disposition='scrapped'``); dieser Embed trägt nur den Abschluss-Status."""

    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    done: bool = False
    note: Optional[str] = None
    scrapped_by_name: Optional[str] = None
