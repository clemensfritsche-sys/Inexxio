from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BOMLineCreate(BaseModel):
    component_item_id: int
    quantity: Decimal = Field(..., gt=0)
    unit: str = "Stk"
    position: int = 1
    note: Optional[str] = None


class BOMCreate(BaseModel):
    parent_item_id: int
    note: Optional[str] = None
    lines: list[BOMLineCreate] = []


class BOMLineUpdate(BaseModel):
    component_item_id: Optional[int] = None
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = None
    position: Optional[int] = None
    note: Optional[str] = None


class BOMUpdate(BaseModel):
    note: Optional[str] = None
    lines: Optional[list[BOMLineCreate]] = None


class BOMLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    component_item_id: int
    quantity: Decimal
    unit: str
    position: int
    note: Optional[str]


class BOMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_item_id: int
    note: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    lines: list[BOMLineResponse] = []
