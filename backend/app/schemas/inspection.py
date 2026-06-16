from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class InspectionUpdate(BaseModel):
    """Erfassung des Eingangskontroll-Ergebnisses."""

    result: str                       # passed | failed
    checked_count: Optional[int] = None
    note: Optional[str] = None

    @field_validator("result")
    @classmethod
    def _result_ok(cls, v: str) -> str:
        if v not in ("passed", "failed"):
            raise ValueError("Ergebnis muss 'passed' oder 'failed' sein")
        return v

    @field_validator("checked_count")
    @classmethod
    def _count_ok(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Anzahl darf nicht negativ sein")
        return v


class InspectionEmbed(BaseModel):
    """Eingebetteter Stand der Eingangskontrolle (im Auftrag)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    result: str
    checked_count: Optional[int]
    note: Optional[str]

    # Vom Router berechnet/denormalisiert
    sample_percent: Optional[int] = None
    required_count: Optional[int] = None
    inspector_name: Optional[str] = None
