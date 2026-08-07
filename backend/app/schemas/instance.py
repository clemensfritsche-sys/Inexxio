"""Instanz und Einzelinstanz – die API-Form, **nur lesend**.

Die Menge steht überall als **Anzahl** da, nie als Dezimalzahl: eine Einzelinstanz ist
genau ein Stück, also ist die Menge einer Instanz ihre Anzahl Einzelinstanzen. Es gibt
kein Mengen-Feld, das man setzen könnte.

Es gibt auch keine **Eingabe**-Form mehr: eine Einzelinstanz entsteht mit ihrer Instanz
und die mit einem Auftrag; gelöscht wird nie. Und die Gruppe trägt **keinen Zustand** –
den haben nur ihre Stücke (Testnotizen #675/#678/#679).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class InstanceUnitResponse(BaseModel):
    """Eine Einzelinstanz – das Arbeitsobjekt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    suffix: int
    number: str          # <Objektnummer der Instanz>-<suffix>, die sichtbare Identität
    status: str
    created_at: datetime


class InstanceResponse(BaseModel):
    """Instanz mit ihren Einzelinstanzen.

    ``quantity`` ist **gezählt**, nicht gespeichert – die Instanz hat keine Mengen-Spalte.

    Einen ``status`` trägt sie nicht: eine Gruppe hat keinen Zustand, nur ihre Stücke
    haben einen (Testnotiz #675).
    """

    id: int
    object_id: int
    article_id: int
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    kind: str
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
    label: Optional[str] = None
    quantity: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


class ObjectReference(BaseModel):
    """Ein Verweis auf ein Objekt (Verwendungsnachweis) – generisch wiederverwendet."""

    kind: str          # menschenlesbare Rolle des Verweises
    ref_type: str      # instance | article | user | organization
    object_id: int
    label: str
    at: datetime
