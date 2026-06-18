from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_STATUS = ("open", "accepted", "rejected", "closed")
ALLOWED_DIRECTION = ("internal", "supplier", "customer")
ALLOWED_REASON = ("defect", "damage", "wrong_item", "quantity", "documentation", "other")
ALLOWED_RESOLUTION = ("none", "rework", "replace", "return", "credit")


def _check(value: Optional[str], allowed: tuple[str, ...], field: str) -> Optional[str]:
    if value is None:
        return value
    if value not in allowed:
        raise ValueError(f"{field} muss eine von {', '.join(allowed)} sein")
    return value


def _strip(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    return v or None


class ClaimCreate(BaseModel):
    """Anlage einer Reklamation über '+'. Status startet als 'open'.

    Es wird genau eine Instanz (über ihre Objektnummer) reklamiert; Artikel- und
    Auftragsbezug leitet der Server daraus ab."""

    instance_object_id: int
    direction: Optional[str] = "internal"
    reason: Optional[str] = "defect"
    title: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None

    @field_validator("direction")
    @classmethod
    def _dir(cls, v: Optional[str]) -> Optional[str]:
        return _check(v, ALLOWED_DIRECTION, "Richtung")

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: Optional[str]) -> Optional[str]:
        return _check(v, ALLOWED_REASON, "Grund")

    @field_validator("title", "description")
    @classmethod
    def _trim(cls, v: Optional[str]) -> Optional[str]:
        return _strip(v)

    @field_validator("quantity")
    @classmethod
    def _qty(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Menge muss grösser als 0 sein")
        return v


class ClaimUpdate(BaseModel):
    status: Optional[str] = None
    direction: Optional[str] = None
    reason: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    resolution: Optional[str] = None
    resolution_note: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: Optional[str]) -> Optional[str]:
        return _check(v, ALLOWED_STATUS, "Status")

    @field_validator("direction")
    @classmethod
    def _dir(cls, v: Optional[str]) -> Optional[str]:
        return _check(v, ALLOWED_DIRECTION, "Richtung")

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: Optional[str]) -> Optional[str]:
        return _check(v, ALLOWED_REASON, "Grund")

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, v: Optional[str]) -> Optional[str]:
        return _check(v, ALLOWED_RESOLUTION, "Lösung")

    @field_validator("title", "description", "resolution_note")
    @classmethod
    def _trim(cls, v: Optional[str]) -> Optional[str]:
        return _strip(v)

    @field_validator("quantity")
    @classmethod
    def _qty(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Menge muss grösser als 0 sein")
        return v


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    direction: str
    instance_object_id: Optional[int]
    article_object_id: Optional[int]
    order_object_id: Optional[int]
    reason: str
    title: Optional[str]
    description: Optional[str]
    quantity: Optional[int]
    resolution: str
    resolution_note: Optional[str]
    source: str
    reported_by_id: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Denormalisiert vom Service
    article_name: Optional[str] = None
    instance_kind: Optional[str] = None
    instance_qc_status: Optional[str] = None
    reported_by_name: Optional[str] = None
