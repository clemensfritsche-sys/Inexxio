from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from ..services.processes import SOURCES


def _check_source(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in SOURCES:
        raise ValueError(f"Quelle muss eine von {', '.join(SOURCES)} sein")
    return v


def _check_name(v: str) -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError("Name des Prozesses fehlt")
    return v


class ProcessCreate(BaseModel):
    """Anlage eines Prozesses (Artikel-eigen oder – im Standard-Feed – global).

    Der **Name** ist frei; das Verhalten bestimmt die **Quelle** (Start-Knoten),
    nicht der Name."""

    name: str
    source: str = "produce"
    position: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        return _check_name(v)

    @field_validator("source")
    @classmethod
    def _source_ok(cls, v: str) -> str:
        return _check_source(v)


class ProcessUpdate(BaseModel):
    name: Optional[str] = None
    source: Optional[str] = None
    position: Optional[int] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: Optional[str]) -> Optional[str]:
        return _check_name(v) if v is not None else v

    @field_validator("source")
    @classmethod
    def _source_ok(cls, v: Optional[str]) -> Optional[str]:
        return _check_source(v)

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("draft", "released", "inactive"):
            raise ValueError("Status muss draft, released oder inactive sein")
        return v


class ProcessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int] = None
    article_id: Optional[int] = None
    name: str
    source: str
    is_standard: bool
    position: int
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # denormalisiert (Router)
    step_count: int = 0
