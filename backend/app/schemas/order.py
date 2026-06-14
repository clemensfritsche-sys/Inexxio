from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_STATUS = ("draft", "released", "inactive")


class OrderCreate(BaseModel):
    """Anlage eines Auftrags über '+'. Status startet als 'draft'.
    Inhaltliche Pflichtfelder folgen noch – daher vorerst alles optional."""

    title: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _title_trim(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_STATUS:
            raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
        return v

    @field_validator("title")
    @classmethod
    def _title_trim(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip() or None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    title: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
