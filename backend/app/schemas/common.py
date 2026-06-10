from typing import Any, Optional

from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Any]


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[Any] = None
