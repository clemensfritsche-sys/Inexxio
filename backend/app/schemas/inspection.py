from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .article_process_step import CaptureField


class InspectionUpdate(BaseModel):
    """Erfassung der Datenerfassung/Eingangskontrolle.

    Bei Schritten mit Maske (``capture_fields``) leiten die erfassten ``values``
    das Ergebnis ab; ohne Maske wird ``result`` direkt gesetzt (passed/failed).
    """

    result: Optional[str] = None
    checked_count: Optional[int] = None
    note: Optional[str] = None
    values: Optional[dict] = None

    @field_validator("result")
    @classmethod
    def _result_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("passed", "failed"):
            raise ValueError("Ergebnis muss 'passed' oder 'failed' sein")
        return v

    @field_validator("checked_count")
    @classmethod
    def _count_ok(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Anzahl darf nicht negativ sein")
        return v


class InspectionEmbed(BaseModel):
    """Eingebetteter Stand der Datenerfassung (im Auftrag)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    result: str
    checked_count: Optional[int]
    note: Optional[str]
    values: dict = {}

    # Vom Router berechnet/denormalisiert
    sample_percent: Optional[int] = None
    required_count: Optional[int] = None
    inspector_name: Optional[str] = None
    fields: list[CaptureField] = []   # Maske (aus der Prozessdefinition)

    @field_validator("values", mode="before")
    @classmethod
    def _values_default(cls, v: Optional[dict]) -> dict:
        return v or {}
