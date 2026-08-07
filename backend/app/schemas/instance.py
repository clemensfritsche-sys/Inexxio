"""Instanz, Einzelinstanz, Datenerfassung – die API-Form des neuen Datenmodells.

Die Menge steht überall als **Anzahl** da, nie als Dezimalzahl: eine Einzelinstanz ist
genau ein Stück, also ist die Menge einer Instanz ihre Anzahl Einzelinstanzen. Es gibt
kein Mengen-Feld, das man setzen könnte – wer mehr will, legt Einzelinstanzen an.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.instance import KINDS
from .process import CapturePoint


class InstanceUnitResponse(BaseModel):
    """Eine Einzelinstanz – das Arbeitsobjekt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    suffix: int
    number: str          # <Objektnummer der Instanz>-<suffix>, die sichtbare Identität
    status: str
    created_at: datetime


class InstanceCreate(BaseModel):
    """Neue Instanz. Typ und Anzahl werden ausdrücklich verlangt – nichts wird aus dem
    Artikel erraten, damit niemand später über eine stille Vorbelegung stolpert."""

    article_object_id: int
    kind: str
    count: int = Field(ge=1, description="Anzahl Einzelinstanzen, mindestens 1")
    label: Optional[str] = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"Unbekannter Typ «{v}». Erlaubt: {', '.join(KINDS)}.")
        return v


class InstanceUnitsAdd(BaseModel):
    """Weitere Einzelinstanzen zu einer bestehenden Instanz."""

    count: int = Field(ge=1)


class InstanceResponse(BaseModel):
    """Instanz mit ihren Einzelinstanzen.

    ``quantity`` ist **gezählt**, nicht gespeichert – die Instanz hat keine Mengen-Spalte.
    """

    id: int
    object_id: int
    article_id: int
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    kind: str
    status: str
    label: Optional[str] = None
    quantity: int
    units: list[InstanceUnitResponse]
    created_at: datetime
    updated_at: datetime
    is_active: bool


class InstanceSummary(BaseModel):
    """Feed-Zeile: ohne die Einzelinstanzen, aber mit ihrer Anzahl."""

    id: int
    object_id: int
    article_id: int
    article_name: Optional[str] = None
    kind: str
    status: str
    label: Optional[str] = None
    quantity: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


class CaptureResponse(BaseModel):
    """Eine Erfassung an einer Einzelinstanz – **nur lesend**.

    Es gibt kein ``CaptureCreate`` mehr: geschrieben wird ausschliesslich im Prozess,
    wenn ein Stück vor einem Modul steht und jemand bestätigt.

    ``points`` sind die Erfassungspunkte des Moduls, das erfasst hat – sie liegen bei,
    weil ``values`` ohne sie nur Schlüssel und Rohwerte wären. Sie kommen aus dem Modul
    und nicht aus einer Kopie an der Erfassung: der Punkt ist Definition, der Wert ist
    Messung, und die Definition rastet ohnehin ein.
    """

    id: int
    values: dict
    result: Optional[str]      # passed | failed | None (nichts Bewertbares)
    note: Optional[str] = None
    created_at: datetime
    step_name: Optional[str] = None
    points: list[CapturePoint] = Field(default_factory=list)


class ObjectReference(BaseModel):
    """Ein Verweis auf ein Objekt (Verwendungsnachweis) – generisch wiederverwendet."""

    kind: str          # menschenlesbare Rolle des Verweises
    ref_type: str      # instance | article | user | organization
    object_id: int
    label: str
    at: datetime
