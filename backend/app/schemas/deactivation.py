from typing import Optional

from pydantic import BaseModel, field_validator

ORDERS_MODES = ("phase_out", "cancel")


class ImpactArticle(BaseModel):
    object_id: Optional[int]
    name: str


class ImpactOrder(BaseModel):
    object_id: Optional[int]


class DeactivationImpact(BaseModel):
    """Wirkungsanalyse (Dry-Run) vor dem Inaktiv-Setzen/Ersetzen eines Artikels."""

    articles: list[ImpactArticle] = []   # mitbetroffene Eltern-Artikel (consume)
    orders: list[ImpactOrder] = []       # laufende (freigegebene) Aufträge
    stock: int = 0                       # freigegebener Lagerbestand (Stück)


class DeactivateRequest(BaseModel):
    """Optionen beim Inaktiv-Setzen/Ersetzen."""

    orders_mode: str = "phase_out"       # phase_out (auslaufen) | cancel (abbrechen)

    @field_validator("orders_mode")
    @classmethod
    def _mode_ok(cls, v: str) -> str:
        if v not in ORDERS_MODES:
            raise ValueError("orders_mode muss 'phase_out' oder 'cancel' sein")
        return v
