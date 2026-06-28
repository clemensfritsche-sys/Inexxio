from typing import Optional

from pydantic import BaseModel, ConfigDict


class ScrapUpdate(BaseModel):
    """Erfassung des Verschrottungsschritts: die zu verschrottenden Instanzen (per
    Objektnummer) + optionale Notiz/Grund. Mindestens eine Instanz."""

    instance_ids: list[int] = []
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
    scrapped_count: int = 0
