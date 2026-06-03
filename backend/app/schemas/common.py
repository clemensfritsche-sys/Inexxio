from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[Any] = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool


class ObjectBase(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True
