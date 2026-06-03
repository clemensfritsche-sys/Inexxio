from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Any]


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[Any] = None


class ObjectBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_type: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
